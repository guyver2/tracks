import json
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.gpx import downsample_coordinates

if TYPE_CHECKING:
    from app.db.models import ActivityTrack


def map_geojson_cache_path(
    cache_dir: Path, gpx_filename: str, trim_start: int, trim_end: int
) -> Path:
    return cache_dir / f"{gpx_filename}.{trim_start}.{trim_end}.json"


def delete_map_caches_for_gpx(cache_dir: Path, gpx_filename: str) -> None:
    for path in cache_dir.glob(f"{gpx_filename}.*.json"):
        path.unlink(missing_ok=True)


def read_track_map_geojson_cache(track: "ActivityTrack", cache_dir: Path) -> dict | None:
    path = map_geojson_cache_path(
        cache_dir, track.gpx_filename, track.trim_start, track.trim_end
    )
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_track_map_geojson_cache(
    track: "ActivityTrack", feature: dict, cache_dir: Path
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = map_geojson_cache_path(
        cache_dir, track.gpx_filename, track.trim_start, track.trim_end
    )
    path.write_text(json.dumps(feature, separators=(",", ":")), encoding="utf-8")


def build_track_map_feature(track: "ActivityTrack", upload_dir: Path) -> dict | None:
    from app.services.gpx import _parse_activity_track

    path = upload_dir / track.gpx_filename
    if not path.exists():
        return None
    try:
        stats = _parse_activity_track(track, path)
    except ValueError:
        return None
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": downsample_coordinates(stats.coordinates),
        },
        "properties": {
            "track_id": track.id,
            "activity_id": track.activity_id,
            "bounds": stats.bounds,
        },
    }


def refresh_track_map_cache(
    track: "ActivityTrack", upload_dir: Path, cache_dir: Path
) -> dict | None:
    feature = build_track_map_feature(track, upload_dir)
    if feature is None:
        return None
    write_track_map_geojson_cache(track, feature, cache_dir)
    return feature


def get_track_map_geojson(
    track: "ActivityTrack", upload_dir: Path, cache_dir: Path
) -> dict | None:
    cached = read_track_map_geojson_cache(track, cache_dir)
    if cached is not None:
        cached.setdefault("properties", {})
        cached["properties"]["track_id"] = track.id
        cached["properties"]["activity_id"] = track.activity_id
        return cached
    return refresh_track_map_cache(track, upload_dir, cache_dir)


def track_map_bounds(
    track: "ActivityTrack", upload_dir: Path, cache_dir: Path
) -> dict[str, float] | None:
    cached = read_track_map_geojson_cache(track, cache_dir)
    if cached is not None:
        bounds = cached.get("properties", {}).get("bounds")
        if bounds:
            return bounds
    feature = refresh_track_map_cache(track, upload_dir, cache_dir)
    if feature is None:
        return None
    return feature.get("properties", {}).get("bounds")
