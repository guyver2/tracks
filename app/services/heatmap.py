import hashlib
import json
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.config import HEATMAP_CACHE_DIR
from app.db.models import Activity, ActivityTrack, ActivityType
from app.services.gpx import GpxPoint, load_stacked_track_points, merge_bounds
from app.services.stats import _apply_activity_filters

CACHE_VERSION = 1
MAX_HEATMAP_POINTS = 15000
MAX_POINTS_PER_TRACK = 40


def _filtered_track_activities_query(
    db: Session,
    *,
    activity_type: ActivityType | None = None,
    start: date | None = None,
    end: date | None = None,
):
    query = db.query(Activity).join(ActivityTrack)
    query = _apply_activity_filters(
        query,
        activity_type=activity_type,
        start=start,
        end=end,
    )
    return query.distinct()


def _cache_metadata(
    db: Session,
    *,
    activity_type: ActivityType | None = None,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    rows = (
        _filtered_track_activities_query(
            db,
            activity_type=activity_type,
            start=start,
            end=end,
        )
        .with_entities(Activity.updated_at)
        .all()
    )
    max_updated = max(
        (updated_at for (updated_at,) in rows if updated_at is not None),
        default=None,
    )
    return {
        "activity_count": len(rows),
        "max_updated_at": max_updated.isoformat() if max_updated else None,
    }


def _cache_key(
    *,
    activity_type: ActivityType | None,
    start: date | None,
    end: date | None,
) -> str:
    parts = [
        activity_type.value if activity_type else "all",
        start.isoformat() if start else "all",
        end.isoformat() if end else "all",
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _cache_path(
    *,
    activity_type: ActivityType | None,
    start: date | None,
    end: date | None,
    cache_dir: Path = HEATMAP_CACHE_DIR,
) -> Path:
    return cache_dir / f"{_cache_key(activity_type=activity_type, start=start, end=end)}.json"


def _sample_track_points(
    points: list[GpxPoint],
    max_points: int = MAX_POINTS_PER_TRACK,
) -> list[tuple[float, float]]:
    if not points:
        return []
    if len(points) <= max_points:
        return [(lat, lon) for lat, lon, _, _ in points]
    step = max(1, (len(points) - 1) // (max_points - 1))
    sampled = [points[index] for index in range(0, len(points), step)]
    if sampled[-1] is not points[-1]:
        sampled.append(points[-1])
    return [(lat, lon) for lat, lon, _, _ in sampled[:max_points]]


def _bounds_from_points(points: list[tuple[float, float]]) -> dict[str, float]:
    lats = [point[0] for point in points]
    lngs = [point[1] for point in points]
    return {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lng": min(lngs),
        "max_lng": max(lngs),
    }


def compute_heatmap_data(
    db: Session,
    upload_dir: Path,
    *,
    activity_type: ActivityType | None = None,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    activities = (
        _filtered_track_activities_query(
            db,
            activity_type=activity_type,
            start=start,
            end=end,
        )
        .options(joinedload(Activity.tracks))
        .order_by(Activity.date.desc(), Activity.id.desc())
        .all()
    )

    heat_points: list[list[float]] = []
    bounds_list: list[dict[str, float]] = []

    for activity in activities:
        if not activity.tracks:
            continue
        stacked = load_stacked_track_points(activity.tracks, upload_dir)
        if len(stacked) < 2:
            continue

        for lat, lng in _sample_track_points(stacked):
            heat_points.append([round(lat, 6), round(lng, 6)])

        if activity.bounds_json:
            try:
                bounds_list.append(json.loads(activity.bounds_json))
            except json.JSONDecodeError:
                pass

        if len(heat_points) >= MAX_HEATMAP_POINTS:
            heat_points = heat_points[:MAX_HEATMAP_POINTS]
            break

    bounds = merge_bounds(bounds_list)
    if bounds is None and heat_points:
        bounds = _bounds_from_points([(point[0], point[1]) for point in heat_points])

    return {
        "has_data": bool(heat_points),
        "activity_count": len(activities),
        "point_count": len(heat_points),
        "bounds": bounds,
        "points": heat_points,
    }


def invalidate_heatmap_cache(cache_dir: Path = HEATMAP_CACHE_DIR) -> None:
    if not cache_dir.exists():
        return
    for path in cache_dir.glob("*.json"):
        path.unlink(missing_ok=True)


def refresh_heatmap_cache(
    db: Session,
    upload_dir: Path,
    *,
    activity_type: ActivityType | None = None,
    start: date | None = None,
    end: date | None = None,
    cache_dir: Path = HEATMAP_CACHE_DIR,
) -> dict:
    payload = {
        "version": CACHE_VERSION,
        **_cache_metadata(db, activity_type=activity_type, start=start, end=end),
        **compute_heatmap_data(
            db,
            upload_dir,
            activity_type=activity_type,
            start=start,
            end=end,
        ),
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(
        activity_type=activity_type,
        start=start,
        end=end,
        cache_dir=cache_dir,
    )
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return payload


def get_heatmap_data(
    db: Session,
    upload_dir: Path,
    *,
    activity_type: ActivityType | None = None,
    start: date | None = None,
    end: date | None = None,
    cache_dir: Path = HEATMAP_CACHE_DIR,
) -> dict:
    path = _cache_path(
        activity_type=activity_type,
        start=start,
        end=end,
        cache_dir=cache_dir,
    )
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        else:
            meta = _cache_metadata(
                db,
                activity_type=activity_type,
                start=start,
                end=end,
            )
            if (
                payload.get("version") == CACHE_VERSION
                and payload.get("activity_count") == meta["activity_count"]
                and payload.get("max_updated_at") == meta["max_updated_at"]
            ):
                return payload

    return refresh_heatmap_cache(
        db,
        upload_dir,
        activity_type=activity_type,
        start=start,
        end=end,
        cache_dir=cache_dir,
    )
