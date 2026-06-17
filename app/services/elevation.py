import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import (
    ELEVATION_CACHE_DIR,
    OPENTOPODATA_BASE_URL,
    OPENTOPODATA_DATASET,
    elevation_enabled,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100
_BATCH_DELAY_SEC = 1.0
_REQUEST_TIMEOUT_SEC = 30.0

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_READY = "ready"
STATUS_FAILED = "failed"


def cache_path(gpx_filename: str) -> Path:
    stem = Path(gpx_filename).stem
    return ELEVATION_CACHE_DIR / f"{stem}.json"


def get_elevation_cache_state(gpx_filename: str) -> dict | None:
    path = cache_path(gpx_filename)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def load_cached_elevations(
    gpx_filename: str, expected_point_count: int
) -> list[float | None] | None:
    state = get_elevation_cache_state(gpx_filename)
    if not state or state.get("status") != STATUS_READY:
        return None
    if state.get("point_count") != expected_point_count:
        return None
    elevations = state.get("elevations_m")
    if not isinstance(elevations, list) or len(elevations) != expected_point_count:
        return None
    return elevations


def _write_cache(gpx_filename: str, payload: dict) -> None:
    path = cache_path(gpx_filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f)


def delete_elevation_cache(gpx_filename: str) -> None:
    path = cache_path(gpx_filename)
    path.unlink(missing_ok=True)


def enqueue_elevation_job(
    gpx_filename: str, activity_id: int, point_count: int
) -> None:
    if not elevation_enabled():
        return

    _write_cache(
        gpx_filename,
        {
            "status": STATUS_PENDING,
            "point_count": point_count,
            "activity_id": activity_id,
        },
    )

    from app.services.elevation_worker import get_worker

    get_worker().enqueue(gpx_filename, activity_id)


def fetch_elevations(points: list[tuple[float, float]]) -> list[float | None]:
    if not points:
        return []

    url = f"{OPENTOPODATA_BASE_URL}/v1/{OPENTOPODATA_DATASET}"
    elevations: list[float | None] = []

    with httpx.Client(timeout=_REQUEST_TIMEOUT_SEC) as client:
        for start in range(0, len(points), _BATCH_SIZE):
            batch = points[start : start + _BATCH_SIZE]
            locations = "|".join(f"{lat},{lon}" for lat, lon in batch)
            response = client.post(
                url,
                data={"locations": locations, "interpolation": "bilinear"},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "OK":
                raise RuntimeError(payload.get("error") or "Open Topo Data request failed")

            results = payload.get("results") or []
            for item in results:
                elevation = item.get("elevation")
                elevations.append(float(elevation) if elevation is not None else None)

            if start + _BATCH_SIZE < len(points):
                time.sleep(_BATCH_DELAY_SEC)

    return elevations


def populate_elevation_cache(
    gpx_filename: str,
    points: list[tuple[float, float]],
    activity_id: int,
) -> bool:
    existing = get_elevation_cache_state(gpx_filename) or {}
    _write_cache(
        gpx_filename,
        {
            "status": STATUS_PROCESSING,
            "point_count": len(points),
            "activity_id": activity_id,
        },
    )

    try:
        elevations = fetch_elevations(points)
        if len(elevations) != len(points):
            raise RuntimeError(
                f"Expected {len(points)} elevations, got {len(elevations)}"
            )

        dataset = OPENTOPODATA_DATASET.split(",")[0]
        _write_cache(
            gpx_filename,
            {
                "status": STATUS_READY,
                "point_count": len(points),
                "activity_id": activity_id,
                "dataset": dataset,
                "elevations_m": elevations,
            },
        )
        return True
    except Exception as exc:
        logger.warning("Elevation fetch failed for %s: %s", gpx_filename, exc)
        _write_cache(
            gpx_filename,
            {
                "status": STATUS_FAILED,
                "point_count": len(points),
                "activity_id": activity_id,
                "error": str(exc),
            },
        )
        return False


def track_elevation_status(gpx_filename: str, point_count: int) -> str:
    state = get_elevation_cache_state(gpx_filename)
    if not state:
        return "missing"
    status = state.get("status", "missing")
    if status == STATUS_READY and state.get("point_count") != point_count:
        return STATUS_PENDING
    return status


def aggregate_elevation_meta(
    track_point_counts: list[tuple[str, int]],
) -> tuple[str, str]:
    if not elevation_enabled() or not track_point_counts:
        return "ready", "gps"

    statuses: list[str] = []
    for filename, point_count in track_point_counts:
        statuses.append(track_elevation_status(filename, point_count))

    if any(status == STATUS_PROCESSING for status in statuses):
        return STATUS_PROCESSING, "gps"
    if any(status == STATUS_PENDING for status in statuses):
        return STATUS_PENDING, "gps"
    if any(status == "missing" for status in statuses):
        return STATUS_PENDING, "gps"
    if statuses and all(status == STATUS_READY for status in statuses):
        return STATUS_READY, "dem"
    if any(status == STATUS_FAILED for status in statuses):
        return STATUS_FAILED, "gps"
    return "missing", "gps"
