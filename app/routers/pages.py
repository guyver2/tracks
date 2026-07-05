import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityType
from app.db.session import get_db
from app.config import GPX_UPLOAD_DIR, PERSONAL_RECORDS_CACHE_FILE
from app.services.heatmap import get_heatmap_data
from app.services.objectives import all_objectives_with_progress
from app.services.personal_records import HIGHLIGHT_RECORD_KEYS, get_personal_records
from app.services.stats import (
    get_activity_calendar,
    get_time_series,
    get_period_totals,
    get_totals,
    get_type_breakdown,
    month_bounds,
    resolve_date_range,
)

router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

VALID_ACTIVITY_TYPES = frozenset(t.value for t in ActivityType)


def _stats_heatmap_url(
    activity_type: str | None,
    preset: str,
    date_from: str | None,
    date_to: str | None,
) -> str:
    params: dict[str, str] = {}
    if activity_type in VALID_ACTIVITY_TYPES:
        params["activity_type"] = activity_type
    if preset != "all":
        params["preset"] = preset
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    if not params:
        return "/stats/heatmap.json"
    return "/stats/heatmap.json?" + urlencode(params)


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request, db: Session = Depends(get_db)):
    month_start, month_end = month_bounds()
    recent = db.query(Activity).order_by(desc(Activity.date), desc(Activity.id)).limit(5).all()
    objectives = all_objectives_with_progress(db)[:5]
    personal_records = [
        record
        for record in get_personal_records(db, GPX_UPLOAD_DIR, PERSONAL_RECORDS_CACHE_FILE)
        if record.key in HIGHLIGHT_RECORD_KEYS
    ]

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
            "personal_records": personal_records,
            "show_all_records_link": True,
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

    chart_series = {
        group: get_time_series(
            db, group_by=group, activity_type=parsed_type, start=start, end=end
        )
        for group in ("year", "month", "week")
    }
    breakdown = get_type_breakdown(db, start=start, end=end)
    totals = get_totals(db, activity_type=parsed_type, start=start, end=end)
    personal_records = get_personal_records(db, GPX_UPLOAD_DIR, PERSONAL_RECORDS_CACHE_FILE)

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
            "chart_series": json.dumps(chart_series),
            "type_labels": json.dumps(breakdown["labels"]),
            "type_counts": json.dumps(breakdown["counts"]),
            "type_distances": json.dumps(breakdown["distances"]),
            "calendar": get_activity_calendar(db),
            "personal_records": personal_records,
            "show_all_records_link": False,
            "heatmap_url": _stats_heatmap_url(activity_type, preset, date_from, date_to),
        },
    )


@router.get("/stats/heatmap.json")
def stats_heatmap_json(
    db: Session = Depends(get_db),
    activity_type: str | None = Query(None),
    preset: str = Query("all"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    start, end, _period_label = resolve_date_range(preset, date_from, date_to)
    parsed_type = (
        ActivityType(activity_type)
        if activity_type in VALID_ACTIVITY_TYPES
        else None
    )
    return JSONResponse(
        get_heatmap_data(
            db,
            GPX_UPLOAD_DIR,
            activity_type=parsed_type,
            start=start,
            end=end,
        )
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
