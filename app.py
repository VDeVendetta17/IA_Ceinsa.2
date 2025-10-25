import os, hmac, hashlib, json
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTasks
import httpx

from utils import rut_is_valid, mask_rut, safe_hash
from dentalink_client import DentalinkClient
from database import init_db, get_session
from models import User, AuditLog

APP_NAME = "Ceinsa WhatsApp Bot"

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "changeme")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
APP_SECRET = os.getenv("APP_SECRET", "")  # Meta App Secret
WA_BASE = os.getenv("WA_BASE", "https://graph.facebook.com/v21.0")
WA_PHONE_ID = os.getenv("WA_PHONE_ID", "")  # Phone Number ID from Meta

DENTALINK_BASE = os.getenv("DENTALINK_BASE", "https://api.dentalink.example")
DENTALINK_API_KEY = os.getenv("DENTALINK_API_KEY", "")

REQUIRE_CONSENT = os.getenv("REQUIRE_CONSENT", "true").lower() == "true"

app = FastAPI(title=APP_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    init_db()

async def wa_reply_text(to: str, text: str):
    url = f"{WA_BASE}/{WA_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()

def verify_signature(app_secret: str, body: bytes, signature_header: str) -> bool:
    if not app_secret:
        return True  # dev only; in prod require signature
    if not signature_header:
        return False
    mac = hmac.new(app_secret.encode(), msg=body, digestmod=hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature_header)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/webhook")
def verify(mode: Optional[str] = None, challenge: Optional[str] = None, verify_token: Optional[str] = None):
    if mode == "subscribe" and verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook")
async def receive(request: Request, background: BackgroundTasks, db=Depends(get_session)):
    raw = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(APP_SECRET, raw, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                from_ = msg.get("from")  # phone number
                text = (msg.get("text", {}) or {}).get("body", "").strip()

                user = db.query(User).filter(User.phone == from_).one_or_none()
                if not user:
                    user = User(phone=from_)
                    db.add(user)
                    db.commit(); db.refresh(user)

                if REQUIRE_CONSENT and not user.consent_at:
                    if text.lower() in ["acepto", "si", "sí", "ok"]:
                        user.give_consent()
                        db.add(user); db.commit()
                        await wa_reply_text(from_, "Gracias. Consentimiento registrado ✅. Escribe *MENU* para continuar.")
                        continue
                    await wa_reply_text(from_, (
                        "Hola 👋 Soy el asistente virtual de Clínica Ceinsa.\n"
                        "Para continuar, necesito tu consentimiento para usar tus datos solo con fines de agendamiento y recordatorios.\n"
                        "Responde *ACEPTO* para continuar."
                    ))
                    continue

                if text.lower() in ("hola", "menu", "buenas", "start"):
                    await wa_reply_text(from_, (
                        "Hola 👋 Soy el asistente virtual de *Clínica Ceinsa*.\n"
                        "¿Cómo te identificas?\n1) Con mi RUT\n2) Con mi número de WhatsApp\n\n"
                        "Comandos: MIS HORAS • AGENDAR • RESERVAR • CANCELAR • AYUDA"
                    ))
                    continue

                if ("-" in text) or text.lower().startswith(("1", "rut")):
                    candidate = text.split()[-1]
                    if rut_is_valid(candidate):
                        user.rut_hash = safe_hash(candidate)
                        user.rut_masked = mask_rut(candidate)
                        db.add(user); db.commit()
                        await wa_reply_text(from_, f"RUT verificado ✅ ({user.rut_masked}). ¿Qué deseas? *MIS HORAS* o *AGENDAR*.")
                    else:
                        await wa_reply_text(from_, "El RUT no parece válido. Ejemplo: 12.345.678-5")
                    continue

                if text.startswith("2"):
                    await wa_reply_text(from_, "Te identificaré por tu número de WhatsApp ✅. ¿Deseas *MIS HORAS* o *AGENDAR*?")
                    continue

                if text.upper() == "MIS HORAS":
                    dl = DentalinkClient(DENTALINK_BASE, DENTALINK_API_KEY)
                    identifier = user.rut_hash or user.phone
                    try:
                        appts = await dl.get_my_appointments_by_identifier(identifier)
                        if not appts:
                            await wa_reply_text(from_, "No encontré horas agendadas. ¿Deseas *AGENDAR*?")
                        else:
                            lines = ["Tus próximas horas:"]
                            for a in appts[:5]:
                                lines.append(f"- {a['fecha']} {a['hora']} · {a.get('especialidad','')} · {a.get('profesional','')}")
                            await wa_reply_text(from_, "\n".join(lines))
                    except Exception:
                        await wa_reply_text(from_, "Hubo un problema al consultar Dentalink. Intenta más tarde.")
                    background.add_task(log_action, db, user, "MIS_HORAS", {"ok": True})
                    continue

                if text.upper().startswith("AGENDAR"):
                    parts = text.split()
                    especialidad = parts[1] if len(parts) > 1 else None
                    fecha = parts[2] if len(parts) > 2 else None
                    dl = DentalinkClient(DENTALINK_BASE, DENTALINK_API_KEY)
                    try:
                        slots = await dl.search_availability(especialidad=especialidad, fecha=fecha)
                        if not slots:
                            await wa_reply_text(from_, "No vi disponibilidad con esos filtros. Prueba otra fecha/especialidad.")
                        else:
                            joined = "\n".join([f"- {s['fecha']} {s['hora']} · {s.get('profesional','')} ({s.get('especialidad','')})" for s in slots[:6]])
                            await wa_reply_text(from_, (
                                "Estas son algunas disponibilidades:\n" + joined +
                                "\n\nResponde: *RESERVAR YYYY-MM-DD HH:MM*"
                            ))
                    except Exception:
                        await wa_reply_text(from_, "No pude obtener disponibilidad ahora mismo.")
                    background.add_task(log_action, db, user, "AGENDAR_QUERY", {"ok": True})
                    continue

                if text.upper().startswith("RESERVAR"):
                    parts = text.split()
                    if len(parts) >= 3:
                        fecha, hora = parts[1], parts[2]
                        dl = DentalinkClient(DENTALINK_BASE, DENTALINK_API_KEY)
                        try:
                            ok = await dl.book_slot(user_identifier=(user.rut_hash or user.phone), fecha=fecha, hora=hora)
                            if ok:
                                await wa_reply_text(from_, f"Listo ✅. Hora reservada para {fecha} {hora}.")
                            else:
                                await wa_reply_text(from_, "No fue posible reservar ese horario. Intenta otro.")
                        except Exception:
                            await wa_reply_text(from_, "No pude completar la reserva en este momento.")
                        background.add_task(log_action, db, user, "RESERVAR", {"fecha": fecha, "hora": hora})
                        continue
                    else:
                        await wa_reply_text(from_, "Formato: RESERVAR YYYY-MM-DD HH:MM")
                        continue

                if text.upper() == "CANCELAR":
                    await wa_reply_text(from_, "Indica el código de la reserva a cancelar (ej.: CANCELAR ABC123).")
                    continue

                if text.upper().startswith("CANCELAR "):
                    code = text.split(maxsplit=1)[1]
                    dl = DentalinkClient(DENTALINK_BASE, DENTALINK_API_KEY)
                    try:
                        ok = await dl.cancel_booking(code)
                        await wa_reply_text(from_, "Reserva cancelada ✅" if ok else "No pude cancelar esa reserva.")
                    except Exception:
                        await wa_reply_text(from_, "No pude cancelar ahora mismo.")
                    background.add_task(log_action, db, user, "CANCELAR", {"code": code})
                    continue

                if text.upper() == "AYUDA":
                    await wa_reply_text(from_, (
                        "Comandos:\n"
                        "- MENU\n- MIS HORAS\n- AGENDAR <Especialidad> <YYYY-MM-DD>\n"
                        "- RESERVAR <YYYY-MM-DD> <HH:MM>\n- CANCELAR <codigo>\n"
                    ))
                    continue

                await wa_reply_text(from_, "No entendí 🤔. Escribe *MENU* para ver opciones.")
    return {"status": "ok"}

async def log_action(db, user: User, action: str, payload: dict):
    log = AuditLog(user_id=user.id, action=action, payload=json.dumps(payload))
    db.add(log); db.commit()
