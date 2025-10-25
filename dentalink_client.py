import httpx
from typing import Optional

class DentalinkClient:
    """
    Cliente mínimo para Dentalink. Ajusta las rutas según tu documentación.
    Todas las llamadas incluyen Authorization: Bearer <API_KEY>.
    """
    def __init__(self, base_url: str, api_key: str):
        self.base = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def get_my_appointments_by_identifier(self, identifier: str):
        # TODO: reemplazar con tu endpoint real, ejemplo:
        # GET {base}/v1/appointments?identifier={identifier}&status=upcoming
        url = f"{self.base}/v1/appointments"
        params = {"identifier": identifier, "status": "upcoming"}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=self._headers(), params=params)
            r.raise_for_status()
            items = r.json().get("items", [])
            mapped = []
            for it in items:
                mapped.append({
                    "fecha": it.get("date"),
                    "hora": it.get("time"),
                    "profesional": (it.get("doctor") or {}).get("name"),
                    "especialidad": it.get("specialty"),
                    "code": it.get("id"),
                })
            return mapped

    async def search_availability(self, especialidad: Optional[str] = None, fecha: Optional[str] = None):
        # GET {base}/v1/availability?specialty=...&date=YYYY-MM-DD
        url = f"{self.base}/v1/availability"
        params = {}
        if especialidad:
            params["specialty"] = especialidad
        if fecha:
            params["date"] = fecha
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=self._headers(), params=params)
            r.raise_for_status()
            return r.json().get("slots", [])

    async def book_slot(self, user_identifier: str, fecha: str, hora: str) -> bool:
        # POST {base}/v1/appointments
        url = f"{self.base}/v1/appointments"
        payload = {"identifier": user_identifier, "date": fecha, "time": hora}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, headers=self._headers(), json=payload)
            return r.status_code in (200, 201)

    async def cancel_booking(self, code: str) -> bool:
        # DELETE {base}/v1/appointments/{code}
        url = f"{self.base}/v1/appointments/{code}"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.delete(url, headers=self._headers())
            return r.status_code in (200, 204)
