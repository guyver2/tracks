from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import GPX_UPLOAD_DIR, PHOTO_UPLOAD_DIR
from app.db.models import Activity, ActivityType
from app.db.session import get_db
from app.services.gpx import bounds_to_json, build_elevation_profile, gpx_to_geojson, parse_gpx_file
from app.services.uploads import delete_file, save_gpx, save_photo

router = APIRouter(prefix="/activities", tags=["activities"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

VALID_ACTIVITY_TYPES = frozenset(t.value for t in ActivityType)


def _get_activity_or_404(db: Session, activity_id: int) -> Activity:
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid date format") from e


def _clear_track_data(activity: Activity) -> None:
    delete_file(GPX_UPLOAD_DIR, activity.gpx_filename)
    activity.gpx_filename = None
    activity.distance_km = None
    activity.duration_sec = None
    activity.elevation_gain_m = None
    activity.bounds_json = None


def _apply_activity_type(activity: Activity, activity_type: ActivityType) -> None:
    activity.activity_type = activity_type
    if not activity_type.supports_track:
        _clear_track_data(activity)


def _duplicate_activity(source: Activity) -> Activity:
    return Activity(
        name=source.name,
        activity_type=source.activity_type,
        date=date.today(),
        place=source.place,
        comment=source.comment,
        distance_km=source.distance_km,
        duration_sec=source.duration_sec,
        elevation_gain_m=source.elevation_gain_m,
        bounds_json=source.bounds_json,
    )


@router.get("", response_class=HTMLResponse)
def list_activities(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    activity_type: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    query = db.query(Activity).order_by(desc(Activity.date), desc(Activity.id))

    if activity_type in VALID_ACTIVITY_TYPES:
        query = query.filter(Activity.activity_type == ActivityType(activity_type))
    if date_from:
        query = query.filter(Activity.date >= _parse_date(date_from))
    if date_to:
        query = query.filter(Activity.date <= _parse_date(date_to))

    activities = query.all()
    return templates.TemplateResponse(
        request,
        "activities/list.html",
        {
            "request": request,
            "active_nav": "activities",
            "activities": activities,
            "filters": {
                "activity_type": activity_type or "",
                "date_from": date_from or "",
                "date_to": date_to or "",
            },
        },
    )


@router.get("/new", response_class=HTMLResponse)
def new_activity_form(request: Request):
    return templates.TemplateResponse(
        request,
        "activities/form.html",
        {
            "request": request,
            "active_nav": "activities",
            "activity": None,
            "default_date": date.today().isoformat(),
            "form_action": "/activities",
            "form_method": "post",
        },
    )


@router.post("/preview-gpx", response_class=HTMLResponse)
async def preview_gpx(request: Request, gpx_file: UploadFile = File(...)):
    try:
        filename = await save_gpx(gpx_file)
        path = GPX_UPLOAD_DIR / filename
        stats = parse_gpx_file(path)
        path.unlink(missing_ok=True)
        return templates.TemplateResponse(
            request,
            "activities/partials/gpx_preview.html",
            {"request": request, "stats": stats, "error": None},
        )
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "activities/partials/gpx_preview.html",
            {"request": request, "stats": None, "error": str(e)},
        )


@router.post("")
async def create_activity(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    activity_type: Annotated[str, Form()],
    activity_date: Annotated[str, Form(alias="date")],
    place: Annotated[str, Form()] = "",
    comment: Annotated[str, Form()] = "",
    gpx_file: UploadFile | None = File(None),
    photo_file: UploadFile | None = File(None),
):
    if activity_type not in VALID_ACTIVITY_TYPES:
        raise HTTPException(status_code=400, detail="Invalid activity type")

    parsed_type = ActivityType(activity_type)
    activity = Activity(
        name=name.strip(),
        activity_type=parsed_type,
        date=_parse_date(activity_date),
        place=place.strip(),
        comment=comment.strip() or None,
    )

    errors: list[str] = []

    if parsed_type.supports_track and gpx_file and gpx_file.filename:
        try:
            activity.gpx_filename = await save_gpx(gpx_file)
            stats = parse_gpx_file(GPX_UPLOAD_DIR / activity.gpx_filename)
            activity.distance_km = stats.distance_km
            activity.duration_sec = stats.duration_sec
            activity.elevation_gain_m = stats.elevation_gain_m
            activity.bounds_json = bounds_to_json(stats.bounds)
        except ValueError as e:
            errors.append(str(e))
            if activity.gpx_filename:
                delete_file(GPX_UPLOAD_DIR, activity.gpx_filename)
                activity.gpx_filename = None

    if photo_file and photo_file.filename:
        try:
            activity.photo_filename = await save_photo(photo_file)
        except ValueError as e:
            errors.append(str(e))

    if errors:
        return templates.TemplateResponse(
            request,
            "activities/form.html",
            {
                "request": request,
                "active_nav": "activities",
                "activity": activity,
                "default_date": date.today().isoformat(),
                "form_action": "/activities",
                "form_method": "post",
                "errors": errors,
            },
            status_code=400,
        )

    db.add(activity)
    db.commit()
    return RedirectResponse(url=f"/activities/{activity.id}", status_code=303)


@router.get("/{activity_id}", response_class=HTMLResponse)
def activity_detail(
    request: Request,
    activity_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    activity = _get_activity_or_404(db, activity_id)
    flash = request.query_params.get("flash")
    flash_msg = None
    if flash == "created":
        flash_msg = {"type": "success", "message": "Activity saved."}
    elif flash == "updated":
        flash_msg = {"type": "success", "message": "Activity updated."}
    elif flash == "deleted":
        flash_msg = {"type": "success", "message": "Activity deleted."}

    return templates.TemplateResponse(
        request,
        "activities/detail.html",
        {
            "request": request,
            "active_nav": "activities",
            "activity": activity,
            "flash": flash_msg,
            "has_gpx": bool(activity.gpx_filename),
        },
    )


@router.get("/{activity_id}/gpx.geojson")
def activity_geojson(activity_id: int, db: Annotated[Session, Depends(get_db)]):
    activity = _get_activity_or_404(db, activity_id)
    if not activity.gpx_filename:
        raise HTTPException(status_code=404, detail="No GPX for this activity")
    path = GPX_UPLOAD_DIR / activity.gpx_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="GPX file missing")
    return JSONResponse(gpx_to_geojson(path))


@router.get("/{activity_id}/elevation.json")
def activity_elevation(activity_id: int, db: Annotated[Session, Depends(get_db)]):
    activity = _get_activity_or_404(db, activity_id)
    if not activity.gpx_filename:
        raise HTTPException(status_code=404, detail="No GPX for this activity")
    path = GPX_UPLOAD_DIR / activity.gpx_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="GPX file missing")
    return JSONResponse(build_elevation_profile(path))


@router.post("/{activity_id}/duplicate")
def duplicate_activity(
    activity_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    source = _get_activity_or_404(db, activity_id)
    duplicate = _duplicate_activity(source)
    db.add(duplicate)
    db.commit()
    db.refresh(duplicate)
    return RedirectResponse(url=f"/activities/{duplicate.id}/edit", status_code=303)


@router.get("/{activity_id}/edit", response_class=HTMLResponse)
def edit_activity_form(
    request: Request,
    activity_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    activity = _get_activity_or_404(db, activity_id)
    return templates.TemplateResponse(
        request,
        "activities/form.html",
        {
            "request": request,
            "active_nav": "activities",
            "activity": activity,
            "default_date": date.today().isoformat(),
            "form_action": f"/activities/{activity_id}",
            "form_method": "post",
        },
    )


@router.post("/{activity_id}")
async def update_activity(
    request: Request,
    activity_id: int,
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    activity_type: Annotated[str, Form()],
    activity_date: Annotated[str, Form(alias="date")],
    place: Annotated[str, Form()] = "",
    comment: Annotated[str, Form()] = "",
    remove_gpx: Annotated[str, Form()] = "",
    remove_photo: Annotated[str, Form()] = "",
    gpx_file: UploadFile | None = File(None),
    photo_file: UploadFile | None = File(None),
):
    activity = _get_activity_or_404(db, activity_id)
    if activity_type not in VALID_ACTIVITY_TYPES:
        raise HTTPException(status_code=400, detail="Invalid activity type")

    activity.name = name.strip()
    parsed_type = ActivityType(activity_type)
    _apply_activity_type(activity, parsed_type)
    activity.date = _parse_date(activity_date)
    activity.place = place.strip()
    activity.comment = comment.strip() or None

    errors: list[str] = []

    if parsed_type.supports_track and remove_gpx == "1":
        _clear_track_data(activity)

    if parsed_type.supports_track and gpx_file and gpx_file.filename:
        delete_file(GPX_UPLOAD_DIR, activity.gpx_filename)
        try:
            activity.gpx_filename = await save_gpx(gpx_file)
            stats = parse_gpx_file(GPX_UPLOAD_DIR / activity.gpx_filename)
            activity.distance_km = stats.distance_km
            activity.duration_sec = stats.duration_sec
            activity.elevation_gain_m = stats.elevation_gain_m
            activity.bounds_json = bounds_to_json(stats.bounds)
        except ValueError as e:
            errors.append(str(e))

    if remove_photo == "1":
        delete_file(PHOTO_UPLOAD_DIR, activity.photo_filename)
        activity.photo_filename = None

    if photo_file and photo_file.filename:
        delete_file(PHOTO_UPLOAD_DIR, activity.photo_filename)
        try:
            activity.photo_filename = await save_photo(photo_file)
        except ValueError as e:
            errors.append(str(e))

    if errors:
        return templates.TemplateResponse(
            request,
            "activities/form.html",
            {
                "request": request,
                "active_nav": "activities",
                "activity": activity,
                "default_date": date.today().isoformat(),
                "form_action": f"/activities/{activity_id}",
                "form_method": "post",
                "errors": errors,
            },
            status_code=400,
        )

    db.commit()
    return RedirectResponse(url=f"/activities/{activity_id}?flash=updated", status_code=303)


@router.post("/{activity_id}/delete")
def delete_activity(activity_id: int, db: Annotated[Session, Depends(get_db)]):
    activity = _get_activity_or_404(db, activity_id)
    delete_file(GPX_UPLOAD_DIR, activity.gpx_filename)
    delete_file(PHOTO_UPLOAD_DIR, activity.photo_filename)
    db.delete(activity)
    db.commit()
    return RedirectResponse(url="/activities?flash=deleted", status_code=303)
