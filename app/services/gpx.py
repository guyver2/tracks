import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import gpxpy

from app.config import elevation_enabled
from app.services.elevation import aggregate_elevation_meta, load_cached_elevations

if TYPE_CHECKING:
    from app.db.models import ActivityTrack

GpxPoint = tuple[float, float, float | None, datetime | None]

TRACE_COLOR = "#FC4C02"

TRACK_COLORS = [
    TRACE_COLOR,
    "#5b8dee",
    "#e8a64c",
    "#e85b8d",
    "#9b59b6",
    "#1abc9c",
    "#f1c40f",
    "#e74c3c",
]

ELEVATION_GAP_KM = 0.1
_MIN_POINTS_AFTER_TRIM = 2
_MIN_ELEVATION_DELTA_M = 5.0
_MAX_PROFILE_POINTS = 300
_MIN_SPEED_DT_SEC = 1
_SPEED_WINDOW_M = 100


@dataclass
class GpxStats:
    distance_km: float
    duration_sec: int | None
    elevation_gain_m: float
    bounds: dict[str, float]
    coordinates: list[list[float]]


@dataclass
class TrackStats:
    distance_km: float
    duration_sec: int | None
    elevation_gain_m: float
    bounds: dict[str, float]
    coordinates: list[list[float]]
    point_count: int
    track_start_time: datetime | None


def track_color(index: int) -> str:
    return TRACE_COLOR


def track_fill_color(hex_color: str) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, 0.2)"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def _extract_points(gpx) -> list[GpxPoint]:
    points: list[GpxPoint] = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append(
                    (point.latitude, point.longitude, point.elevation, point.time)
                )

    if not points:
        for waypoint in gpx.waypoints:
            points.append(
                (waypoint.latitude, waypoint.longitude, waypoint.elevation, waypoint.time)
            )

    if not points:
        raise ValueError("GPX file contains no track points")
    return points


def _load_gpx_points(path: Path) -> list[GpxPoint]:
    with path.open("r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)
    return _extract_points(gpx)


def _apply_dem_elevations(
    points: list[GpxPoint], gpx_filename: str | None
) -> list[GpxPoint]:
    if not elevation_enabled() or not gpx_filename:
        return points

    dem = load_cached_elevations(gpx_filename, len(points))
    if dem is None:
        return points

    return [
        (lat, lon, dem[i] if dem[i] is not None else elev, ts)
        for i, (lat, lon, elev, ts) in enumerate(points)
    ]


def _load_track_points(path: Path, gpx_filename: str | None = None) -> list[GpxPoint]:
    points = _load_gpx_points(path)
    return _apply_dem_elevations(points, gpx_filename)


def _normalize_trim(trim_start: int | None, trim_end: int | None) -> tuple[int, int]:
    return trim_start or 0, trim_end or 0


def apply_trim(
    points: list[GpxPoint], trim_start: int | None, trim_end: int | None
) -> list[GpxPoint]:
    trim_start, trim_end = _normalize_trim(trim_start, trim_end)
    if trim_start < 0 or trim_end < 0:
        raise ValueError("Trim values must be zero or positive")
    if trim_start + trim_end >= len(points):
        raise ValueError(
            f"Trim removes too many points ({len(points)} total, "
            f"trim start {trim_start}, trim end {trim_end})"
        )
    end_index = len(points) - trim_end if trim_end else len(points)
    trimmed = points[trim_start:end_index]
    if len(trimmed) < _MIN_POINTS_AFTER_TRIM:
        raise ValueError(
            f"At least {_MIN_POINTS_AFTER_TRIM} points must remain after trimming"
        )
    return trimmed


def _dedupe_consecutive_points(points: list[GpxPoint]) -> list[GpxPoint]:
    if not points:
        return points

    deduped = [points[0]]
    for lat, lon, elev, ts in points[1:]:
        prev_lat, prev_lon, _, _ = deduped[-1]
        if lat == prev_lat and lon == prev_lon:
            continue
        deduped.append((lat, lon, elev, ts))
    return deduped


def _prepare_trimmed_points(points: list[GpxPoint]) -> list[GpxPoint]:
    prepared = _dedupe_consecutive_points(points)
    if len(prepared) < _MIN_POINTS_AFTER_TRIM:
        raise ValueError(
            f"At least {_MIN_POINTS_AFTER_TRIM} points must remain after trimming"
        )
    return prepared


def _elevation_gain_from_points(points: list[GpxPoint]) -> float:
    reference_elev: float | None = None
    gain = 0.0

    for _, _, elev, _ in points:
        if elev is None:
            continue
        if reference_elev is None:
            reference_elev = elev
            continue

        delta = elev - reference_elev
        if delta > _MIN_ELEVATION_DELTA_M:
            gain += delta
            reference_elev = elev
        elif elev < reference_elev:
            reference_elev = elev

    return gain


def _stats_from_points(points: list[GpxPoint]) -> TrackStats:
    distance_m = 0.0
    timestamps: list[datetime] = []

    for i, (lat, lon, _, ts) in enumerate(points):
        if i > 0:
            prev_lat, prev_lon, _, _ = points[i - 1]
            distance_m += _haversine_km(prev_lat, prev_lon, lat, lon) * 1000
        if ts is not None:
            timestamps.append(ts)

    elevation_gain = _elevation_gain_from_points(points)

    duration_sec = None
    if len(timestamps) >= 2:
        duration_sec = int((max(timestamps) - min(timestamps)).total_seconds())

    track_start_time = None
    for _, _, _, ts in points:
        if ts is not None:
            track_start_time = ts
            break

    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    bounds = {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lng": min(lngs),
        "max_lng": max(lngs),
    }
    coordinates = [[p[1], p[0]] for p in points]

    return TrackStats(
        distance_km=round(distance_m / 1000, 2),
        duration_sec=duration_sec,
        elevation_gain_m=round(elevation_gain, 1),
        bounds=bounds,
        coordinates=coordinates,
        point_count=len(points),
        track_start_time=track_start_time,
    )


def parse_track(
    path: Path,
    trim_start: int = 0,
    trim_end: int = 0,
    gpx_filename: str | None = None,
) -> TrackStats:
    points = _load_track_points(path, gpx_filename)
    trimmed = apply_trim(points, trim_start, trim_end)
    prepared = _prepare_trimmed_points(trimmed)
    return _stats_from_points(prepared)


def parse_gpx_file(path: Path, trim_start: int = 0, trim_end: int = 0) -> GpxStats:
    track = parse_track(path, trim_start, trim_end)
    return GpxStats(
        distance_km=track.distance_km,
        duration_sec=track.duration_sec,
        elevation_gain_m=track.elevation_gain_m,
        bounds=track.bounds,
        coordinates=track.coordinates,
    )


def aggregate_track_stats(track_stats: list[TrackStats]) -> GpxStats | None:
    if not track_stats:
        return None

    total_distance = sum(t.distance_km for t in track_stats)
    total_gain = sum(t.elevation_gain_m for t in track_stats)
    durations = [t.duration_sec for t in track_stats if t.duration_sec is not None]
    total_duration = sum(durations) if durations else None

    all_coords: list[list[float]] = []
    min_lat = min(t.bounds["min_lat"] for t in track_stats)
    max_lat = max(t.bounds["max_lat"] for t in track_stats)
    min_lng = min(t.bounds["min_lng"] for t in track_stats)
    max_lng = max(t.bounds["max_lng"] for t in track_stats)
    for t in track_stats:
        all_coords.extend(t.coordinates)

    return GpxStats(
        distance_km=round(total_distance, 2),
        duration_sec=total_duration,
        elevation_gain_m=round(total_gain, 1),
        bounds={
            "min_lat": min_lat,
            "max_lat": max_lat,
            "min_lng": min_lng,
            "max_lng": max_lng,
        },
        coordinates=all_coords,
    )


def track_label(track: "ActivityTrack", index: int) -> str:
    return f"Track {index + 1}"


def _track_label(track: "ActivityTrack", index: int) -> str:
    return track_label(track, index)


def _track_sort_key(track: "ActivityTrack", upload_dir: Path) -> tuple:
    start = track.track_start_time
    if start is None:
        path = upload_dir / track.gpx_filename
        if path.exists():
            try:
                start = _parse_activity_track(track, path).track_start_time
            except ValueError:
                start = None
    return (start is None, start or datetime.min, track.sort_order, track.id)


def sorted_activity_tracks(
    tracks: list["ActivityTrack"], upload_dir: Path | None = None
) -> list["ActivityTrack"]:
    return _sorted_tracks(tracks, upload_dir)


def _sorted_tracks(tracks: list["ActivityTrack"], upload_dir: Path | None = None) -> list["ActivityTrack"]:
    if upload_dir is None:
        upload_dir = Path(".")
    return sorted(tracks, key=lambda track: _track_sort_key(track, upload_dir))


def _parse_activity_track(track: "ActivityTrack", path: Path) -> TrackStats:
    trim_start, trim_end = _normalize_trim(track.trim_start, track.trim_end)
    return parse_track(path, trim_start, trim_end, gpx_filename=track.gpx_filename)


def tracks_to_geojson(tracks: list["ActivityTrack"], upload_dir: Path) -> dict:
    sorted_tracks = _sorted_tracks(tracks, upload_dir)
    features = []
    for index, track in enumerate(sorted_tracks):
        path = upload_dir / track.gpx_filename
        if not path.exists():
            continue
        stats = _parse_activity_track(track, path)
        color = track_color(index)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": stats.coordinates},
                "properties": {
                    "color": color,
                    "label": _track_label(track, index),
                    "track_id": track.id,
                    "distance_km": stats.distance_km,
                },
            }
        )

    if len(features) == 1:
        return features[0]

    return {"type": "FeatureCollection", "features": features}


def gpx_to_geojson(path: Path) -> dict:
    stats = parse_gpx_file(path)
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": stats.coordinates},
        "properties": {
            "distance_km": stats.distance_km,
            "bounds": stats.bounds,
            "color": TRACE_COLOR,
        },
    }


def bounds_to_json(bounds: dict[str, float]) -> str:
    return json.dumps(bounds)


def _downsample_profile(
    distances_km: list[float],
    elevations_m: list[float | None],
    coordinates: list[list[float]] | None = None,
) -> tuple:
    n = len(distances_km)
    if n <= _MAX_PROFILE_POINTS:
        if coordinates is None:
            return distances_km, elevations_m
        return distances_km, elevations_m, coordinates
    step = (n - 1) / (_MAX_PROFILE_POINTS - 1)
    indices = [round(i * step) for i in range(_MAX_PROFILE_POINTS)]
    indices[-1] = n - 1
    if coordinates is None:
        return (
            [distances_km[i] for i in indices],
            [elevations_m[i] for i in indices],
        )
    return (
        [distances_km[i] for i in indices],
        [elevations_m[i] for i in indices],
        [coordinates[i] for i in indices],
    )


def _profile_from_points(points: list[GpxPoint]) -> tuple[list[float], list[float | None], float]:
    distances_km: list[float] = [0.0]
    elevations_m: list[float | None] = [points[0][2]]
    distance_m = 0.0

    for i in range(1, len(points)):
        lat, lon, elev, _ = points[i]
        prev_lat, prev_lon, _, _ = points[i - 1]
        distance_m += _haversine_km(prev_lat, prev_lon, lat, lon) * 1000
        distances_km.append(round(distance_m / 1000, 3))
        elevations_m.append(elev)

    return distances_km, elevations_m, distance_m / 1000


def build_elevation_profile(
    path: Path,
    trim_start: int = 0,
    trim_end: int = 0,
    gpx_filename: str | None = None,
) -> dict:
    points = _load_track_points(path, gpx_filename)
    trimmed = apply_trim(points, trim_start, trim_end)
    distances_km, elevations_m, total_km = _profile_from_points(trimmed)

    has_elevation = any(e is not None for e in elevations_m)
    if not has_elevation:
        return {"has_elevation": False, "distances_km": [], "elevations_m": []}

    coordinates = _coords_from_points(trimmed)
    distances_km, elevations_m, coordinates = _downsample_profile(
        distances_km, elevations_m, coordinates
    )
    color = TRACE_COLOR
    chart_max_km = distances_km[-1] if distances_km else round(total_km, 3)
    return {
        "has_elevation": True,
        "gap_km": ELEVATION_GAP_KM,
        "total_distance_km": chart_max_km,
        "segments": [
            {
                "label": "Track 1",
                "color": color,
                "distances_km": distances_km,
                "elevations_m": elevations_m,
                "coordinates": coordinates,
            }
        ],
    }


def _effective_trim(
    track: "ActivityTrack",
    trim_overrides: dict[int, tuple[int, int]] | None,
) -> tuple[int, int]:
    if trim_overrides and track.id in trim_overrides:
        return trim_overrides[track.id]
    return _normalize_trim(track.trim_start, track.trim_end)


def parse_trim_overrides(
    tracks: list["ActivityTrack"], query_params: dict[str, str]
) -> dict[int, tuple[int, int]]:
    overrides: dict[int, tuple[int, int]] = {}
    for track in tracks:
        start_key = f"track_{track.id}_trim_start"
        end_key = f"track_{track.id}_trim_end"
        if start_key not in query_params and end_key not in query_params:
            continue
        try:
            trim_start = int(query_params.get(start_key, track.trim_start or 0))
            trim_end = int(query_params.get(end_key, track.trim_end or 0))
        except (TypeError, ValueError):
            continue
        overrides[track.id] = (trim_start, trim_end)
    return overrides


def parse_removed_track_ids(
    tracks: list["ActivityTrack"], query_params: dict[str, str]
) -> set[int]:
    removed: set[int] = set()
    for track in tracks:
        if query_params.get(f"remove_track_{track.id}") == "1":
            removed.add(track.id)
    return removed


def _coords_from_points(points: list[GpxPoint]) -> list[list[float]]:
    return [[p[1], p[0]] for p in points]


def tracks_to_editor_geojson(
    tracks: list["ActivityTrack"],
    upload_dir: Path,
    trim_overrides: dict[int, tuple[int, int]] | None = None,
    excluded_track_ids: set[int] | None = None,
    active_track_id: int | None = None,
) -> dict:
    excluded_track_ids = excluded_track_ids or set()
    sorted_tracks = _sorted_tracks(
        [track for track in tracks if track.id not in excluded_track_ids], upload_dir
    )
    features: list[dict] = []

    for index, track in enumerate(sorted_tracks):
        path = upload_dir / track.gpx_filename
        if not path.exists():
            continue

        trim_start, trim_end = _effective_trim(track, trim_overrides)
        points = _load_gpx_points(path)
        color = track_color(index)
        label = _track_label(track, index)
        dimmed = active_track_id is not None and track.id != active_track_id
        opacity = 0.35 if dimmed else 1.0

        try:
            trimmed = apply_trim(points, trim_start, trim_end)
        except ValueError:
            continue

        if trim_start > 0:
            head_points = points[:trim_start]
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": _coords_from_points(head_points),
                    },
                    "properties": {
                        "role": "trimmed",
                        "track_id": track.id,
                        "color": "#7a82a8",
                        "opacity": opacity * 0.6,
                    },
                }
            )

        kept_coords = _coords_from_points(trimmed)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": kept_coords},
                "properties": {
                    "role": "kept",
                    "track_id": track.id,
                    "color": color,
                    "label": label,
                    "opacity": opacity,
                    "weight": 5 if not dimmed else 3,
                },
            }
        )

        if trim_end > 0:
            tail_points = points[len(points) - trim_end :]
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": _coords_from_points(tail_points),
                    },
                    "properties": {
                        "role": "trimmed",
                        "track_id": track.id,
                        "color": "#7a82a8",
                        "opacity": opacity * 0.6,
                    },
                }
            )

        if kept_coords:
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": kept_coords[0]},
                    "properties": {
                        "role": "cut-marker",
                        "track_id": track.id,
                        "color": color,
                        "marker": "start",
                        "opacity": opacity,
                    },
                }
            )
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": kept_coords[-1]},
                    "properties": {
                        "role": "cut-marker",
                        "track_id": track.id,
                        "color": color,
                        "marker": "end",
                        "opacity": opacity,
                    },
                }
            )

    return {"type": "FeatureCollection", "features": features}


def build_track_stats_with_overrides(
    tracks: list["ActivityTrack"],
    upload_dir: Path,
    trim_overrides: dict[int, tuple[int, int]] | None = None,
    excluded_track_ids: set[int] | None = None,
) -> GpxStats | None:
    excluded_track_ids = excluded_track_ids or set()
    track_stats: list[TrackStats] = []
    for track in tracks:
        if track.id in excluded_track_ids:
            continue
        path = upload_dir / track.gpx_filename
        if not path.exists():
            continue
        trim_start, trim_end = _effective_trim(track, trim_overrides)
        try:
            track_stats.append(
                parse_track(
                    path,
                    trim_start,
                    trim_end,
                    gpx_filename=track.gpx_filename,
                )
            )
        except ValueError:
            continue
    return aggregate_track_stats(track_stats)


def build_stacked_elevation_profile(
    tracks: list["ActivityTrack"],
    upload_dir: Path,
    gap_km: float = ELEVATION_GAP_KM,
    trim_overrides: dict[int, tuple[int, int]] | None = None,
    excluded_track_ids: set[int] | None = None,
) -> dict:
    excluded_track_ids = excluded_track_ids or set()
    sorted_tracks = _sorted_tracks(
        [track for track in tracks if track.id not in excluded_track_ids], upload_dir
    )
    segments: list[dict] = []
    offset_km = 0.0
    total_distance_km = 0.0
    has_any_elevation = False
    track_point_counts: list[tuple[str, int]] = []

    for index, track in enumerate(sorted_tracks):
        path = upload_dir / track.gpx_filename
        if not path.exists():
            continue

        raw_points = _load_gpx_points(path)
        track_point_counts.append((track.gpx_filename, len(raw_points)))
        points = _apply_dem_elevations(raw_points, track.gpx_filename)
        trim_start, trim_end = _effective_trim(track, trim_overrides)
        try:
            trimmed = apply_trim(points, trim_start, trim_end)
        except ValueError:
            continue
        distances_km, elevations_m, segment_km = _profile_from_points(trimmed)

        if not any(e is not None for e in elevations_m):
            offset_km += segment_km
            if index < len(sorted_tracks) - 1:
                offset_km += gap_km
            total_distance_km += segment_km
            continue

        has_any_elevation = True
        offset_distances = [round(offset_km + d, 3) for d in distances_km]
        coordinates = _coords_from_points(trimmed)
        distances_km, elevations_m, coordinates = _downsample_profile(
            offset_distances, elevations_m, coordinates
        )
        color = track_color(index)
        segments.append(
            {
                "label": _track_label(track, index),
                "color": color,
                "track_id": track.id,
                "distances_km": distances_km,
                "elevations_m": elevations_m,
                "coordinates": coordinates,
            }
        )

        offset_km += segment_km
        total_distance_km += segment_km
        if index < len(sorted_tracks) - 1:
            offset_km += gap_km

    elevation_status, elevation_source = aggregate_elevation_meta(track_point_counts)
    elevation_gain_m = None
    if sorted_tracks:
        track_stats = []
        for track in sorted_tracks:
            path = upload_dir / track.gpx_filename
            if not path.exists():
                continue
            trim_start, trim_end = _effective_trim(track, trim_overrides)
            try:
                track_stats.append(
                    parse_track(
                        path,
                        trim_start,
                        trim_end,
                        gpx_filename=track.gpx_filename,
                    )
                )
            except ValueError:
                continue
        aggregated = aggregate_track_stats(track_stats)
        if aggregated is not None:
            elevation_gain_m = aggregated.elevation_gain_m

    if not has_any_elevation:
        return {
            "has_elevation": False,
            "distances_km": [],
            "elevations_m": [],
            "elevation_status": elevation_status,
            "elevation_source": elevation_source,
            "elevation_gain_m": elevation_gain_m,
        }

    chart_max_km = segments[-1]["distances_km"][-1] if segments else 0.0
    return {
        "has_elevation": True,
        "gap_km": ELEVATION_GAP_KM,
        "total_distance_km": chart_max_km,
        "segments": segments,
        "elevation_status": elevation_status,
        "elevation_source": elevation_source,
        "elevation_gain_m": elevation_gain_m,
    }


def _track_has_speed_timestamps(points: list[GpxPoint]) -> bool:
    timestamps = [ts for _, _, _, ts in points if ts is not None]
    if len(timestamps) < 2:
        return False
    return (max(timestamps) - min(timestamps)).total_seconds() >= _MIN_SPEED_DT_SEC


def _speed_profile_from_points(
    points: list[GpxPoint],
    window_m: float = _SPEED_WINDOW_M,
) -> tuple[list[float], list[float], list[list[float]]]:
    if len(points) < 2:
        return [], [], []

    distances_m: list[float] = [0.0]
    timestamps: list[datetime | None] = [points[0][3]]

    for i in range(1, len(points)):
        lat, lon, _, ts = points[i]
        prev_lat, prev_lon, _, _ = points[i - 1]
        distances_m.append(
            distances_m[-1] + _haversine_km(prev_lat, prev_lon, lat, lon) * 1000
        )
        timestamps.append(ts)

    coordinates = _coords_from_points(points)
    distances_km: list[float] = []
    speeds_kmh: list[float] = []
    out_coordinates: list[list[float]] = []

    start_idx = 0
    for end_idx in range(1, len(points)):
        while (
            start_idx < end_idx - 1
            and distances_m[end_idx] - distances_m[start_idx + 1] >= window_m
        ):
            start_idx += 1

        span_m = distances_m[end_idx] - distances_m[start_idx]
        if span_m < window_m:
            continue

        end_ts = timestamps[end_idx]
        start_ts = timestamps[start_idx]
        if end_ts is None or start_ts is None:
            continue

        dt_sec = (end_ts - start_ts).total_seconds()
        if dt_sec < _MIN_SPEED_DT_SEC:
            continue

        speed_kmh = round((span_m / 1000) / (dt_sec / 3600.0), 1)
        distances_km.append(round(distances_m[end_idx] / 1000, 3))
        speeds_kmh.append(speed_kmh)
        out_coordinates.append(coordinates[end_idx])

    return distances_km, speeds_kmh, out_coordinates


def build_stacked_speed_profile(
    tracks: list["ActivityTrack"],
    upload_dir: Path,
    gap_km: float = ELEVATION_GAP_KM,
    trim_overrides: dict[int, tuple[int, int]] | None = None,
    excluded_track_ids: set[int] | None = None,
) -> dict:
    excluded_track_ids = excluded_track_ids or set()
    sorted_tracks = _sorted_tracks(
        [track for track in tracks if track.id not in excluded_track_ids], upload_dir
    )

    segments: list[dict] = []
    offset_km = 0.0
    has_any_speed = False

    for index, track in enumerate(sorted_tracks):
        path = upload_dir / track.gpx_filename
        if not path.exists():
            continue

        points = _load_gpx_points(path)
        trim_start, trim_end = _effective_trim(track, trim_overrides)
        try:
            trimmed = apply_trim(points, trim_start, trim_end)
        except ValueError:
            continue

        if not _track_has_speed_timestamps(trimmed):
            _, _, segment_km = _profile_from_points(trimmed)
            offset_km += segment_km
            if index < len(sorted_tracks) - 1:
                offset_km += gap_km
            continue

        distances_km, speeds_kmh, coordinates = _speed_profile_from_points(trimmed)
        if len(distances_km) < 2:
            _, _, segment_km = _profile_from_points(trimmed)
            offset_km += segment_km
            if index < len(sorted_tracks) - 1:
                offset_km += gap_km
            continue

        has_any_speed = True
        segment_km = distances_km[-1]
        offset_distances = [round(offset_km + d, 3) for d in distances_km]
        distances_km, speeds_kmh, coordinates = _downsample_profile(
            offset_distances, speeds_kmh, coordinates
        )
        color = track_color(index)
        segments.append(
            {
                "label": _track_label(track, index),
                "color": color,
                "track_id": track.id,
                "distances_km": distances_km,
                "speeds_kmh": speeds_kmh,
                "coordinates": coordinates,
            }
        )

        offset_km += segment_km
        if index < len(sorted_tracks) - 1:
            offset_km += gap_km

    if not has_any_speed:
        return {"has_speed": False, "distances_km": [], "speeds_kmh": []}

    chart_max_km = segments[-1]["distances_km"][-1] if segments else 0.0
    return {
        "has_speed": True,
        "gap_km": gap_km,
        "total_distance_km": chart_max_km,
        "segments": segments,
    }


def recompute_track_start_time(track: "ActivityTrack", upload_dir: Path) -> None:
    path = upload_dir / track.gpx_filename
    if not path.exists():
        track.track_start_time = None
        return
    try:
        points = _load_gpx_points(path)
        trimmed = apply_trim(points, track.trim_start, track.trim_end)
        prepared = _prepare_trimmed_points(trimmed)
        stats = _stats_from_points(prepared)
        track.track_start_time = stats.track_start_time
    except ValueError:
        track.track_start_time = None


def build_tracks_preview(
    tracks: list["ActivityTrack"],
    upload_dir: Path,
    query_params: dict[str, str],
    active_track_id: int | None = None,
) -> dict:
    trim_overrides = parse_trim_overrides(tracks, query_params)
    excluded_track_ids = parse_removed_track_ids(tracks, query_params)
    stats = build_track_stats_with_overrides(
        tracks, upload_dir, trim_overrides, excluded_track_ids
    )
    elevation = build_stacked_elevation_profile(
        tracks,
        upload_dir,
        trim_overrides=trim_overrides,
        excluded_track_ids=excluded_track_ids,
    )
    speed = build_stacked_speed_profile(
        tracks,
        upload_dir,
        trim_overrides=trim_overrides,
        excluded_track_ids=excluded_track_ids,
    )
    geojson = tracks_to_editor_geojson(
        tracks,
        upload_dir,
        trim_overrides=trim_overrides,
        excluded_track_ids=excluded_track_ids,
        active_track_id=active_track_id,
    )

    preview_stats = {
        "distance_km": stats.distance_km if stats else None,
        "duration_sec": stats.duration_sec if stats else None,
        "elevation_gain_m": stats.elevation_gain_m if stats else None,
    }
    return {
        "stats": preview_stats,
        "geojson": geojson,
        "elevation": elevation,
        "speed": speed,
    }
