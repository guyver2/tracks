import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import PERSONAL_RECORDS_CACHE_FILE
from app.db.models import Activity, ActivityTrack, ActivityType
from app.services.gpx import best_effort_time_sec, load_stacked_track_points

CACHE_VERSION = 1

BEST_EFFORT_TARGETS: tuple[tuple[float, str, str], ...] = (
    (5.0, "best_5k", "Best 5 km"),
    (10.0, "best_10k", "Best 10 km"),
    (21.0975, "best_half", "Best half marathon"),
)

HIGHLIGHT_RECORD_KEYS = frozenset(
    {
        "longest_distance",
        "most_elevation",
        "longest_duration",
        "best_5k",
        "best_10k",
        "best_half",
    }
)

TYPE_LABELS = {
    ActivityType.hike: "Hike",
    ActivityType.bike: "Bike",
    ActivityType.skitouring: "Ski touring",
    ActivityType.climbing: "Climbing",
    ActivityType.swimming: "Swimming",
}


@dataclass(frozen=True)
class PersonalRecord:
    key: str
    label: str
    activity_id: int
    activity_name: str
    activity_date: date
    activity_type: ActivityType
    value_display: str


def format_race_time(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _record_order(column):
    return desc(column), desc(Activity.date), desc(Activity.id)


def _holder_for_max(db: Session, column, *, activity_type: ActivityType | None = None) -> Activity | None:
    query = db.query(Activity).filter(column.isnot(None))
    if activity_type is not None:
        query = query.filter(Activity.activity_type == activity_type)
    return query.order_by(*_record_order(column)).first()


def _record_from_activity(key: str, label: str, activity: Activity, value_display: str) -> PersonalRecord:
    return PersonalRecord(
        key=key,
        label=label,
        activity_id=activity.id,
        activity_name=activity.name,
        activity_date=activity.date,
        activity_type=activity.activity_type,
        value_display=value_display,
    )


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _simple_records(db: Session) -> list[PersonalRecord]:
    records: list[PersonalRecord] = []

    distance = _holder_for_max(db, Activity.distance_km)
    if distance is not None:
        records.append(
            _record_from_activity(
                "longest_distance",
                "Longest distance",
                distance,
                f"{distance.distance_km:g} km",
            )
        )

    for activity_type in ActivityType:
        typed = _holder_for_max(db, Activity.distance_km, activity_type=activity_type)
        if typed is None:
            continue
        type_label = TYPE_LABELS[activity_type]
        records.append(
            _record_from_activity(
                f"longest_distance_{activity_type.value}",
                f"Longest {type_label.lower()}",
                typed,
                f"{typed.distance_km:g} km",
            )
        )

    elevation = _holder_for_max(db, Activity.elevation_gain_m)
    if elevation is not None:
        records.append(
            _record_from_activity(
                "most_elevation",
                "Most elevation gain",
                elevation,
                f"{int(round(elevation.elevation_gain_m))} m",
            )
        )

    duration = _holder_for_max(db, Activity.duration_sec)
    if duration is not None:
        records.append(
            _record_from_activity(
                "longest_duration",
                "Longest duration",
                duration,
                _format_duration(duration.duration_sec),
            )
        )

    return records


def _best_effort_records(db: Session, upload_dir: Path) -> list[PersonalRecord]:
    holders: dict[str, tuple[int, Activity]] = {}
    min_target_km = min(target for target, _, _ in BEST_EFFORT_TARGETS)

    activities = (
        db.query(Activity)
        .join(ActivityTrack)
        .filter(Activity.distance_km.isnot(None), Activity.distance_km >= min_target_km)
        .distinct()
        .all()
    )

    for activity in activities:
        if not activity.tracks:
            continue
        points = load_stacked_track_points(activity.tracks, upload_dir)
        if len(points) < 2:
            continue
        for target_km, key, _label in BEST_EFFORT_TARGETS:
            elapsed = best_effort_time_sec(points, target_km)
            if elapsed is None:
                continue
            current = holders.get(key)
            if current is None or elapsed < current[0]:
                holders[key] = (elapsed, activity)

    records: list[PersonalRecord] = []
    for _target_km, key, label in BEST_EFFORT_TARGETS:
        holder = holders.get(key)
        if holder is None:
            continue
        elapsed, activity = holder
        records.append(
            _record_from_activity(
                key,
                label,
                activity,
                format_race_time(elapsed),
            )
        )
    return records


def compute_personal_records(db: Session, upload_dir: Path) -> list[PersonalRecord]:
    records = _simple_records(db)
    records.extend(_best_effort_records(db, upload_dir))
    return records


def _record_to_dict(record: PersonalRecord) -> dict:
    return {
        "key": record.key,
        "label": record.label,
        "activity_id": record.activity_id,
        "activity_name": record.activity_name,
        "activity_date": record.activity_date.isoformat(),
        "activity_type": record.activity_type.value,
        "value_display": record.value_display,
    }


def _record_from_dict(data: dict) -> PersonalRecord:
    return PersonalRecord(
        key=data["key"],
        label=data["label"],
        activity_id=data["activity_id"],
        activity_name=data["activity_name"],
        activity_date=date.fromisoformat(data["activity_date"]),
        activity_type=ActivityType(data["activity_type"]),
        value_display=data["value_display"],
    )


def _cache_metadata(db: Session) -> dict:
    count, max_updated = db.query(
        func.count(Activity.id),
        func.max(Activity.updated_at),
    ).one()
    return {
        "activity_count": int(count or 0),
        "max_updated_at": max_updated.isoformat() if max_updated else None,
    }


def _cache_is_valid(db: Session, payload: dict) -> bool:
    if payload.get("version") != CACHE_VERSION:
        return False
    meta = _cache_metadata(db)
    return (
        payload.get("activity_count") == meta["activity_count"]
        and payload.get("max_updated_at") == meta["max_updated_at"]
    )


def read_personal_records_cache(cache_path: Path) -> dict | None:
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def refresh_personal_records_cache(
    db: Session,
    upload_dir: Path,
    cache_path: Path = PERSONAL_RECORDS_CACHE_FILE,
) -> list[PersonalRecord]:
    records = compute_personal_records(db, upload_dir)
    payload = {
        "version": CACHE_VERSION,
        **_cache_metadata(db),
        "records": [_record_to_dict(record) for record in records],
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return records


def invalidate_personal_records_cache(
    cache_path: Path = PERSONAL_RECORDS_CACHE_FILE,
) -> None:
    cache_path.unlink(missing_ok=True)


def get_personal_records(
    db: Session,
    upload_dir: Path,
    cache_path: Path = PERSONAL_RECORDS_CACHE_FILE,
) -> list[PersonalRecord]:
    payload = read_personal_records_cache(cache_path)
    if payload and _cache_is_valid(db, payload):
        return [_record_from_dict(item) for item in payload["records"]]
    return refresh_personal_records_cache(db, upload_dir, cache_path)


def records_for_activity(
    activity_id: int,
    records: list[PersonalRecord],
) -> list[PersonalRecord]:
    return [record for record in records if record.activity_id == activity_id]
