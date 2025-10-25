# Ceinsa WhatsApp Bot (Render-ready)

Asistente WhatsApp para Clínica Ceinsa con integración a Dentalink.

## Despliegue rápido en Render
1. Crea un repo y sube estos archivos.
2. En Render: **New → Web Service → Use Docker** y conecta el repo.
3. Agrega variables de entorno (Environment):
   - `VERIFY_TOKEN`
   - `WHATSAPP_TOKEN`
   - `APP_SECRET`
   - `WA_PHONE_ID`
   - `DENTALINK_BASE`
   - `DENTALINK_API_KEY`
   - `DATABASE_URL` (opcional; si no, usa SQLite local)
4. Deploy. Copia la URL pública ex: `https://ceinsa-bot.onrender.com`.

## Configurar Webhook en Meta (WhatsApp Cloud API)
- Callback URL: `https://<tu-render>/webhook`
- Verify Token: mismo valor que `VERIFY_TOKEN`
- Suscribe el campo **messages**
- Usa **Phone Number ID** y **WHATSAPP_TOKEN** en variables.

## Probar
- `GET /healthz` → `{"ok": true}`
- Desde WhatsApp al número de la app: `Hola`, `MENU`, `MIS HORAS`, `AGENDAR Odontología 2025-10-27`

## Editar Dentalink
Ajusta endpoints reales en `dentalink_client.py` y los campos (`date`, `time`, `doctor.name`, etc.).
