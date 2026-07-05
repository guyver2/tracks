from datetime import date
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from app.config import (
    GPX_UPLOAD_DIR,
    MAP_GEOJSON_CACHE_DIR,
    MAX_PHOTOS_PER_ACTIVITY,
    MAX_TRACKS_PER_ACTIVITY,
    PHOTO_UPLOAD_DIR,
    elevation_enabled,
)
from app.db.models import Activity, ActivityPhoto, ActivityTrack, ActivityType
from app.db.session import get_db
from app.services.elevation import (
    delete_elevation_cache,
    enqueue_elevation_job,
    get_elevation_cache_state,
)
from app.services.elevation_worker import get_worker
from app.services.gpx import (
    activities_map_manifest,
    aggregate_track_stats,
    bounds_to_json,
    build_stacked_elevation_profile,
    build_stacked_speed_profile,
    build_tracks_preview,
    parse_gpx_file,
    parse_track,
    recompute_track_start_time,
    track_color,
    track_label,
    tracks_to_geojson,
    sorted_activity_tracks,
)
from app.services.map_cache import (
    delete_map_caches_for_gpx,
    get_track_map_geojson,
    refresh_track_map_cache,
)
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


def _clear_gpx_data(activity: Activity) -> None:
    for track in list(activity.tracks):
        delete_file(GPX_UPLOAD_DIR, track.gpx_filename)
        delete_map_caches_for_gpx(MAP_GEOJSON_CACHE_DIR, track.gpx_filename)
        delete_elevation_cache(track.gpx_filename)
        get_worker().cancel(track.gpx_filename)
        activity.tracks.remove(track)
    activity.elevation_gain_m = None
    activity.bounds_json = None


def _clear_track_data(activity: Activity) -> None:
    _clear_gpx_data(activity)
    activity.distance_km = None
    activity.duration_sec = None


def _recompute_activity_from_tracks(activity: Activity) -> None:
    if not activity.tracks:
        activity.distance_km = None
        activity.duration_sec = None
        activity.elevation_gain_m = None
        activity.bounds_json = None
        return

    track_stats = []
    for track in activity.tracks:
        path = GPX_UPLOAD_DIR / track.gpx_filename
        if not path.exists():
            continue
        try:
            stats = parse_track(
                path,
                track.trim_start,
                track.trim_end,
                gpx_filename=track.gpx_filename,
            )
            recompute_track_start_time(track, GPX_UPLOAD_DIR)
            track_stats.append(stats)
        except ValueError:
            continue

    aggregated = aggregate_track_stats(track_stats)
    if aggregated is None:
        activity.distance_km = None
        activity.duration_sec = None
        activity.elevation_gain_m = None
        activity.bounds_json = None
        return

    activity.distance_km = aggregated.distance_km
    activity.duration_sec = aggregated.duration_sec
    activity.elevation_gain_m = aggregated.elevation_gain_m
    activity.bounds_json = bounds_to_json(aggregated.bounds)


def _activity_date_from_tracks(tracks: list[ActivityTrack]) -> date | None:
    starts = [track.track_start_time for track in tracks if track.track_start_time is not None]
    if not starts:
        return None
    return min(starts).date()


def _apply_gpx_activity_date(activity: Activity, form_date: date) -> None:
    gpx_date = _activity_date_from_tracks(activity.tracks)
    if gpx_date is None:
        return
    if form_date == date.today() or gpx_date != form_date:
        activity.date = gpx_date


def _track_form_context(activity: Activity) -> list[dict]:
    items: list[dict] = []
    sorted_tracks = sorted_activity_tracks(activity.tracks, GPX_UPLOAD_DIR)
    label_by_id = {track.id: track_label(track, index) for index, track in enumerate(sorted_tracks)}
    color_by_id = {track.id: track_color(index) for index, track in enumerate(sorted_tracks)}
    for index, track in enumerate(activity.tracks):
        path = GPX_UPLOAD_DIR / track.gpx_filename
        raw_point_count = 0
        point_count = 0
        if path.exists():
            try:
                raw_stats = parse_track(path, 0, 0)
                trimmed_stats = parse_track(path, track.trim_start, track.trim_end)
                raw_point_count = raw_stats.point_count
                point_count = trimmed_stats.point_count
            except ValueError:
                raw_point_count = 0
                point_count = 0
        max_trim = max(0, raw_point_count - 2)
        items.append(
            {
                "track": track,
                "label": label_by_id.get(track.id, track_label(track, index)),
                "color": color_by_id.get(track.id, track_color(0)),
                "raw_point_count": raw_point_count,
                "point_count": point_count,
                "max_trim": max_trim,
            }
        )
    return items


def _enqueue_elevation_jobs(
    activity: Activity, tracks: list[ActivityTrack] | None = None
) -> None:
    if not elevation_enabled():
        return

    target_tracks = tracks if tracks is not None else activity.tracks
    for track in target_tracks:
        state = get_elevation_cache_state(track.gpx_filename)
        if state and state.get("status") == "ready":
            continue
        path = GPX_UPLOAD_DIR / track.gpx_filename
        if not path.exists():
            continue
        try:
            stats = parse_track(path, gpx_filename=track.gpx_filename)
        except ValueError:
            continue
        enqueue_elevation_job(track.gpx_filename, activity.id, stats.point_count)


async def _add_gpx_tracks(
    activity: Activity,
    uploads: list[UploadFile],
    errors: list[str],
) -> list[ActivityTrack]:
    valid_uploads = [upload for upload in uploads if upload.filename]
    added_tracks: list[ActivityTrack] = []
    if not valid_uploads:
        return added_tracks

    current_count = len(activity.tracks)
    if current_count + len(valid_uploads) > MAX_TRACKS_PER_ACTIVITY:
        errors.append(f"Maximum {MAX_TRACKS_PER_ACTIVITY} GPX tracks per activity")
        return added_tracks

    max_sort = max((track.sort_order for track in activity.tracks), default=-1)
    for upload in valid_uploads:
        saved_filename: str | None = None
        try:
            saved_filename = await save_gpx(upload)
            path = GPX_UPLOAD_DIR / saved_filename
            parse_gpx_file(path)
            max_sort += 1
            track = ActivityTrack(
                activity=activity,
                gpx_filename=saved_filename,
                original_filename=upload.filename,
                sort_order=max_sort,
                trim_start=0,
                trim_end=0,
            )
            recompute_track_start_time(track, GPX_UPLOAD_DIR)
            refresh_track_map_cache(track, GPX_UPLOAD_DIR, MAP_GEOJSON_CACHE_DIR)
            added_tracks.append(track)
            saved_filename = None
        except ValueError as e:
            errors.append(str(e))
            if saved_filename:
                delete_file(GPX_UPLOAD_DIR, saved_filename)
                delete_map_caches_for_gpx(MAP_GEOJSON_CACHE_DIR, saved_filename)
    return added_tracks


def _cleanup_added_tracks(tracks: list[ActivityTrack], activity: Activity) -> None:
    for track in tracks:
        delete_file(GPX_UPLOAD_DIR, track.gpx_filename)
        delete_map_caches_for_gpx(MAP_GEOJSON_CACHE_DIR, track.gpx_filename)
        if track in activity.tracks:
            activity.tracks.remove(track)


async def _add_photos(
    activity: Activity,
    uploads: list[UploadFile],
    errors: list[str],
) -> list[ActivityPhoto]:
    valid_uploads = [upload for upload in uploads if upload.filename]
    added_photos: list[ActivityPhoto] = []
    if not valid_uploads:
        return added_photos

    current_count = len(activity.photos)
    if current_count + len(valid_uploads) > MAX_PHOTOS_PER_ACTIVITY:
        errors.append(f"Maximum {MAX_PHOTOS_PER_ACTIVITY} photos per activity")
        return added_photos

    max_sort = max((photo.sort_order for photo in activity.photos), default=-1)
    for upload in valid_uploads:
        saved_filename: str | None = None
        try:
            saved_filename = await save_photo(upload)
            max_sort += 1
            photo = ActivityPhoto(
                activity=activity,
                filename=saved_filename,
                sort_order=max_sort,
            )
            added_photos.append(photo)
            saved_filename = None
        except ValueError as e:
            errors.append(str(e))
            if saved_filename:
                delete_file(PHOTO_UPLOAD_DIR, saved_filename)
    return added_photos


def _cleanup_added_photos(photos: list[ActivityPhoto], activity: Activity) -> None:
    for photo in photos:
        delete_file(PHOTO_UPLOAD_DIR, photo.filename)
        if photo in activity.photos:
            activity.photos.remove(photo)


def _apply_photo_removals(activity: Activity, form) -> None:
    for photo in list(activity.photos):
        if form.get(f"remove_photo_{photo.id}") == "1":
            delete_file(PHOTO_UPLOAD_DIR, photo.filename)
            activity.photos.remove(photo)


def _validate_existing_tracks(
    activity: Activity, form, errors: list[str]
) -> tuple[list[tuple[ActivityTrack, int, int]], list[ActivityTrack], int]:
    updates: list[tuple[ActivityTrack, int, int]] = []
    removals: list[ActivityTrack] = []
    sorted_tracks = sorted_activity_tracks(activity.tracks, GPX_UPLOAD_DIR)
    label_by_id = {t.id: track_label(t, index) for index, t in enumerate(sorted_tracks)}

    for track in list(activity.tracks):
        label = label_by_id.get(track.id, track_label(track, 0))
        if form.get(f"remove_track_{track.id}") == "1":
            removals.append(track)
            continue

        trim_start_raw = form.get(f"track_{track.id}_trim_start", "0")
        trim_end_raw = form.get(f"track_{track.id}_trim_end", "0")
        try:
            trim_start = int(trim_start_raw)
            trim_end = int(trim_end_raw)
        except (TypeError, ValueError):
            errors.append(f"{label}: invalid trim values")
            continue

        path = GPX_UPLOAD_DIR / track.gpx_filename
        try:
            parse_track(path, trim_start, trim_end)
        except ValueError as e:
            errors.append(f"{label}: {e}")
            continue

        updates.append((track, trim_start, trim_end))

    remaining = len(activity.tracks) - len(removals)
    if remaining < 0:
        remaining = 0
    return updates, removals, remaining


def _apply_existing_track_updates(
    updates: list[tuple[ActivityTrack, int, int]],
    removals: list[ActivityTrack],
    activity: Activity,
) -> None:
    for track, trim_start, trim_end in updates:
        if track.trim_start != trim_start or track.trim_end != trim_end:
            delete_map_caches_for_gpx(MAP_GEOJSON_CACHE_DIR, track.gpx_filename)
        track.trim_start = trim_start
        track.trim_end = trim_end
        recompute_track_start_time(track, GPX_UPLOAD_DIR)
        refresh_track_map_cache(track, GPX_UPLOAD_DIR, MAP_GEOJSON_CACHE_DIR)

    for track in removals:
        delete_file(GPX_UPLOAD_DIR, track.gpx_filename)
        delete_map_caches_for_gpx(MAP_GEOJSON_CACHE_DIR, track.gpx_filename)
        delete_elevation_cache(track.gpx_filename)
        get_worker().cancel(track.gpx_filename)
        activity.tracks.remove(track)


def _parse_optional_float(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid distance") from e
    if parsed < 0:
        raise HTTPException(status_code=400, detail="Invalid distance")
    return round(parsed, 2)


def _parse_optional_duration_min(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        minutes = int(float(value))
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid duration") from e
    if minutes < 0:
        raise HTTPException(status_code=400, detail="Invalid duration")
    return minutes * 60


def _apply_manual_stats(activity: Activity, distance_km: str, duration_min: str) -> None:
    activity.distance_km = _parse_optional_float(distance_km)
    activity.duration_sec = _parse_optional_duration_min(duration_min)


def _apply_activity_type(activity: Activity, activity_type: ActivityType) -> None:
    had_tracks = bool(activity.tracks)
    previous_type = activity.activity_type
    activity.activity_type = activity_type

    if activity_type.supports_track:
        return

    _clear_gpx_data(activity)

    if activity_type == ActivityType.climbing:
        activity.distance_km = None
        activity.duration_sec = None
    elif had_tracks or previous_type.supports_track:
        activity.distance_km = None
        activity.duration_sec = None


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


def _form_context(
    request: Request,
    activity: Activity | None,
    *,
    form_action: str,
    errors: list[str] | None = None,
) -> dict:
    context = {
        "request": request,
        "active_nav": "activities",
        "activity": activity,
        "default_date": date.today().isoformat(),
        "form_action": form_action,
        "form_method": "post",
        "errors": errors or [],
        "track_infos": _track_form_context(activity) if activity else [],
    }
    return context


def _filtered_activities_query(
    db: Session,
    *,
    activity_type: str | None,
    date_from: str | None,
    date_to: str | None,
):
    query = db.query(Activity).order_by(desc(Activity.date), desc(Activity.id))

    if activity_type in VALID_ACTIVITY_TYPES:
        query = query.filter(Activity.activity_type == ActivityType(activity_type))
    if date_from:
        query = query.filter(Activity.date >= _parse_date(date_from))
    if date_to:
        query = query.filter(Activity.date <= _parse_date(date_to))

    return query


def _activity_filter_params(
    activity_type: str | None,
    date_from: str | None,
    date_to: str | None,
) -> dict[str, str]:
    params: dict[str, str] = {}
    if activity_type in VALID_ACTIVITY_TYPES:
        params["activity_type"] = activity_type
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    return params


def _map_manifest_url(filter_params: dict[str, str]) -> str:
    if not filter_params:
        return "/activities/map/manifest.json"
    return "/activities/map/manifest.json?" + urlencode(filter_params)


@router.get("", response_class=HTMLResponse)
def list_activities(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    activity_type: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    filter_params = _activity_filter_params(activity_type, date_from, date_to)
    activities = (
        _filtered_activities_query(db, activity_type=activity_type, date_from=date_from, date_to=date_to)
        .options(joinedload(Activity.tracks))
        .all()
    )
    has_tracks = any(activity.tracks for activity in activities)
    return templates.TemplateResponse(
        request,
        "activities/list.html",
        {
            "request": request,
            "active_nav": "activities",
            "activities": activities,
            "has_tracks": has_tracks,
            "map_manifest_url": _map_manifest_url(filter_params),
            "filters": {
                "activity_type": activity_type or "",
                "date_from": date_from or "",
                "date_to": date_to or "",
            },
        },
    )


@router.get("/map/manifest.json")
def activities_map_manifest_json(
    db: Annotated[Session, Depends(get_db)],
    activity_type: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    activities = (
        _filtered_activities_query(db, activity_type=activity_type, date_from=date_from, date_to=date_to)
        .options(joinedload(Activity.tracks))
        .all()
    )
    return JSONResponse(activities_map_manifest(activities, GPX_UPLOAD_DIR, MAP_GEOJSON_CACHE_DIR))


@router.get("/map/tracks/{track_id}.geojson")
def activities_map_track_geojson(track_id: int, db: Annotated[Session, Depends(get_db)]):
    track = db.get(ActivityTrack, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    geojson = get_track_map_geojson(track, GPX_UPLOAD_DIR, MAP_GEOJSON_CACHE_DIR)
    if geojson is None:
        raise HTTPException(status_code=404, detail="Track file missing")
    return JSONResponse(geojson)


@router.get("/new", response_class=HTMLResponse)
def new_activity_form(request: Request):
    return templates.TemplateResponse(
        request,
        "activities/form.html",
        _form_context(request, None, form_action="/activities"),
    )


@router.post("/preview-gpx", response_class=HTMLResponse)
async def preview_gpx(request: Request, gpx_files: list[UploadFile] = File(default=[])):
    valid_files = [upload for upload in gpx_files if upload.filename]
    if not valid_files:
        return templates.TemplateResponse(
            request,
            "activities/partials/gpx_preview.html",
            {"request": request, "stats": None, "error": "No file selected"},
        )
    try:
        filename = await save_gpx(valid_files[0])
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
    distance_km: Annotated[str, Form()] = "",
    duration_min: Annotated[str, Form()] = "",
    gpx_files: list[UploadFile] = File(default=[]),
    photo_files: list[UploadFile] = File(default=[]),
):
    if activity_type not in VALID_ACTIVITY_TYPES:
        raise HTTPException(status_code=400, detail="Invalid activity type")

    parsed_type = ActivityType(activity_type)
    parsed_date = _parse_date(activity_date)
    activity = Activity(
        name=name.strip(),
        activity_type=parsed_type,
        date=parsed_date,
        place=place.strip(),
        comment=comment.strip() or None,
    )

    errors: list[str] = []
    added_tracks: list[ActivityTrack] = []
    added_photos: list[ActivityPhoto] = []

    try:
        if parsed_type.supports_manual_stats:
            _apply_manual_stats(activity, distance_km, duration_min)
    except HTTPException as e:
        errors.append(str(e.detail))

    if parsed_type.supports_track:
        added_tracks = await _add_gpx_tracks(activity, gpx_files, errors)
        if activity.tracks and not errors:
            _recompute_activity_from_tracks(activity)
            _apply_gpx_activity_date(activity, parsed_date)

    added_photos = await _add_photos(activity, photo_files, errors)

    if errors:
        _cleanup_added_tracks(added_tracks, activity)
        _cleanup_added_photos(added_photos, activity)
        return templates.TemplateResponse(
            request,
            "activities/form.html",
            _form_context(request, activity, form_action="/activities", errors=errors),
            status_code=400,
        )

    db.add(activity)
    db.commit()
    db.refresh(activity)
    if parsed_type.supports_track and added_tracks:
        _enqueue_elevation_jobs(activity, added_tracks)
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
            "has_gpx": bool(activity.tracks),
        },
    )


@router.get("/{activity_id}/gpx.geojson")
def activity_geojson(activity_id: int, db: Annotated[Session, Depends(get_db)]):
    activity = _get_activity_or_404(db, activity_id)
    if not activity.tracks:
        raise HTTPException(status_code=404, detail="No GPX for this activity")
    geojson = tracks_to_geojson(activity.tracks, GPX_UPLOAD_DIR)
    if isinstance(geojson, dict) and geojson.get("type") == "FeatureCollection":
        if not geojson.get("features"):
            raise HTTPException(status_code=404, detail="GPX files missing")
    return JSONResponse(geojson)


@router.get("/{activity_id}/elevation.json")
def activity_elevation(activity_id: int, db: Annotated[Session, Depends(get_db)]):
    activity = _get_activity_or_404(db, activity_id)
    if not activity.tracks:
        raise HTTPException(status_code=404, detail="No GPX for this activity")
    profile = build_stacked_elevation_profile(activity.tracks, GPX_UPLOAD_DIR)
    return JSONResponse(profile)


@router.get("/{activity_id}/speed.json")
def activity_speed(activity_id: int, db: Annotated[Session, Depends(get_db)]):
    activity = _get_activity_or_404(db, activity_id)
    if not activity.tracks:
        raise HTTPException(status_code=404, detail="No GPX for this activity")
    profile = build_stacked_speed_profile(activity.tracks, GPX_UPLOAD_DIR)
    if not profile.get("has_speed"):
        return JSONResponse({"has_speed": False, "distances_km": [], "speeds_kmh": []})
    return JSONResponse(profile)


@router.get("/{activity_id}/tracks-preview.json")
def activity_tracks_preview(
    request: Request,
    activity_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    activity = _get_activity_or_404(db, activity_id)
    if not activity.tracks:
        raise HTTPException(status_code=404, detail="No GPX for this activity")

    query_params = {key: value for key, value in request.query_params.multi_items()}
    active_track_id: int | None = None
    active_raw = request.query_params.get("active_track_id")
    if active_raw:
        try:
            active_track_id = int(active_raw)
        except ValueError:
            active_track_id = None

    preview = build_tracks_preview(
        activity.tracks,
        GPX_UPLOAD_DIR,
        query_params,
        active_track_id=active_track_id,
    )
    return JSONResponse(preview)


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
        _form_context(request, activity, form_action=f"/activities/{activity_id}"),
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
    distance_km: Annotated[str, Form()] = "",
    duration_min: Annotated[str, Form()] = "",
    gpx_files: list[UploadFile] = File(default=[]),
    photo_files: list[UploadFile] = File(default=[]),
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
    added_tracks: list[ActivityTrack] = []
    added_photos: list[ActivityPhoto] = []
    form = await request.form()

    try:
        if parsed_type.supports_manual_stats:
            _apply_manual_stats(activity, distance_km, duration_min)
    except HTTPException as e:
        errors.append(str(e.detail))

    if parsed_type.supports_track:
        updates, removals, remaining = _validate_existing_tracks(activity, form, errors)
        valid_new_uploads = [upload for upload in gpx_files if upload.filename]
        if remaining + len(valid_new_uploads) > MAX_TRACKS_PER_ACTIVITY:
            errors.append(f"Maximum {MAX_TRACKS_PER_ACTIVITY} GPX tracks per activity")

        if not errors:
            _apply_existing_track_updates(updates, removals, activity)
            added_tracks = await _add_gpx_tracks(activity, gpx_files, errors)
            if not errors:
                _recompute_activity_from_tracks(activity)

    _apply_photo_removals(activity, form)
    added_photos = await _add_photos(activity, photo_files, errors)

    if errors:
        _cleanup_added_tracks(added_tracks, activity)
        _cleanup_added_photos(added_photos, activity)
        db.rollback()
        activity = _get_activity_or_404(db, activity_id)
        return templates.TemplateResponse(
            request,
            "activities/form.html",
            _form_context(
                request,
                activity,
                form_action=f"/activities/{activity_id}",
                errors=errors,
            ),
            status_code=400,
        )

    db.commit()
    if parsed_type.supports_track and added_tracks:
        _enqueue_elevation_jobs(activity, added_tracks)
    return RedirectResponse(url=f"/activities/{activity_id}?flash=updated", status_code=303)


@router.post("/{activity_id}/delete")
def delete_activity(activity_id: int, db: Annotated[Session, Depends(get_db)]):
    activity = _get_activity_or_404(db, activity_id)
    for track in activity.tracks:
        delete_file(GPX_UPLOAD_DIR, track.gpx_filename)
        delete_map_caches_for_gpx(MAP_GEOJSON_CACHE_DIR, track.gpx_filename)
        delete_elevation_cache(track.gpx_filename)
        get_worker().cancel(track.gpx_filename)
    for photo in activity.photos:
        delete_file(PHOTO_UPLOAD_DIR, photo.filename)
    db.delete(activity)
    db.commit()
    return RedirectResponse(url="/activities?flash=deleted", status_code=303)
