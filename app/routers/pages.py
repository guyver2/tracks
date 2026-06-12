from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/geocode")
async def geocode_place(q: str):
    import httpx

    if not q.strip():
        return {"lat": None, "lng": None}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 1},
            headers={"User-Agent": "Tracks/1.0"},
            timeout=10.0,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return {"lat": None, "lng": None}
        return {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}
