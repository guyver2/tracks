import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityType
from app.db.session import get_db
from app.services.objectives import all_objectives_with_progress
from app.services.stats import (
    get_activity_calendar,
    get_monthly_series,
    get_period_totals,
    get_totals,
    get_type_breakdown,
    month_bounds,
    resolve_date_range,
)

router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

VALID_ACTIVITY_TYPES = frozenset(t.value for t in ActivityType)


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
            "calendar": get_activity_calendar(db),
        },
    )


@router.get("/stats", response_class=HTMLResponse)
def stats_page(
    request: Request,
    db: Session = Depends(get_db),
    activity_type: str | None = Query(None),
    preset: str = Query("all"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    start, end, period_label = resolve_date_range(preset, date_from, date_to)
    parsed_type = (
        ActivityType(activity_type)
        if activity_type in VALID_ACTIVITY_TYPES
        else None
    )

    monthly = get_monthly_series(db, activity_type=parsed_type, start=start, end=end)
    breakdown = get_type_breakdown(db, start=start, end=end)
    totals = get_totals(db, activity_type=parsed_type, start=start, end=end)

    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "request": request,
            "active_nav": "stats",
            "totals": totals,
            "type_cards": breakdown["cards"],
            "period_label": period_label,
            "filters": {
                "activity_type": activity_type or "",
                "preset": preset,
                "date_from": date_from or "",
                "date_to": date_to or "",
            },
            "monthly_labels": json.dumps(monthly["labels"]),
            "monthly_counts": json.dumps(monthly["counts"]),
            "monthly_distances": json.dumps(monthly["distances"]),
            "monthly_elevations": json.dumps(monthly["elevations"]),
            "type_labels": json.dumps(breakdown["labels"]),
            "type_counts": json.dumps(breakdown["counts"]),
            "type_distances": json.dumps(breakdown["distances"]),
            "calendar": get_activity_calendar(db),
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
