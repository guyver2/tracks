import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import Activity
from app.db.session import get_db
from app.services.objectives import all_objectives_with_progress
from app.services.stats import get_monthly_series, get_period_totals, get_totals, get_type_breakdown, month_bounds

router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request, db: Session = Depends(get_db)):
    month_start, month_end = month_bounds()
    recent = db.query(Activity).order_by(desc(Activity.date), desc(Activity.id)).limit(5).all()
    objectives = all_objectives_with_progress(db)[:5]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "active_nav": "dashboard",
            "totals": get_totals(db),
            "month": get_period_totals(db, month_start, month_end),
            "recent": recent,
            "objectives": objectives,
            "month_label": date.today().strftime("%B %Y"),
        },
    )


@router.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request, db: Session = Depends(get_db)):
    monthly = get_monthly_series(db)
    breakdown = get_type_breakdown(db)

    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "request": request,
            "active_nav": "stats",
            "totals": get_totals(db),
            "monthly_labels": json.dumps(monthly["labels"]),
            "monthly_counts": json.dumps(monthly["counts"]),
            "monthly_distances": json.dumps(monthly["distances"]),
            "monthly_elevations": json.dumps(monthly["elevations"]),
            "type_labels": json.dumps(breakdown["labels"]),
            "type_counts": json.dumps(breakdown["counts"]),
            "type_distances": json.dumps(breakdown["distances"]),
        },
    )


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
