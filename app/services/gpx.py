import json
import math
from dataclasses import dataclass
from pathlib import Path

import gpxpy


@dataclass
class GpxStats:
    distance_km: float
    duration_sec: int | None
    elevation_gain_m: float
    bounds: dict[str, float]
    coordinates: list[list[float]]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def _extract_points(gpx) -> list[tuple[float, float, float | None]]:
    points: list[tuple[float, float, float | None]] = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append((point.latitude, point.longitude, point.elevation))

    if not points:
        for waypoint in gpx.waypoints:
            points.append((waypoint.latitude, waypoint.longitude, waypoint.elevation))

    if not points:
        raise ValueError("GPX file contains no track points")
    return points


def parse_gpx_file(path: Path) -> GpxStats:
    with path.open("r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)
    points = _extract_points(gpx)

    distance_m = 0.0
    elevation_gain = 0.0
    timestamps: list = []

    for i, (lat, lon, elev) in enumerate(points):
        if i > 0:
            prev_lat, prev_lon, prev_elev = points[i - 1]
            distance_m += _haversine_km(prev_lat, prev_lon, lat, lon) * 1000
            if elev is not None and prev_elev is not None and elev > prev_elev:
                elevation_gain += elev - prev_elev

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.time:
                    timestamps.append(point.time)

    duration_sec = None
    if len(timestamps) >= 2:
        duration_sec = int((max(timestamps) - min(timestamps)).total_seconds())

    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    bounds = {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lng": min(lngs),
        "max_lng": max(lngs),
    }
    coordinates = [[p[1], p[0]] for p in points]

    return GpxStats(
        distance_km=round(distance_m / 1000, 2),
        duration_sec=duration_sec,
        elevation_gain_m=round(elevation_gain, 1),
        bounds=bounds,
        coordinates=coordinates,
    )


def gpx_to_geojson(path: Path) -> dict:
    stats = parse_gpx_file(path)
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": stats.coordinates},
        "properties": {
            "distance_km": stats.distance_km,
            "bounds": stats.bounds,
        },
    }


def bounds_to_json(bounds: dict[str, float]) -> str:
    return json.dumps(bounds)


_MAX_PROFILE_POINTS = 300


def _downsample_profile(distances_km: list[float], elevations_m: list[float | None]) -> tuple[list[float], list[float | None]]:
    n = len(distances_km)
    if n <= _MAX_PROFILE_POINTS:
        return distances_km, elevations_m
    step = (n - 1) / (_MAX_PROFILE_POINTS - 1)
    indices = [round(i * step) for i in range(_MAX_PROFILE_POINTS)]
    indices[-1] = n - 1
    return (
        [distances_km[i] for i in indices],
        [elevations_m[i] for i in indices],
    )


def _load_gpx_points(path: Path) -> list[tuple[float, float, float | None]]:
    with path.open("r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)
    return _extract_points(gpx)


def build_elevation_profile(path: Path) -> dict:
    points = _load_gpx_points(path)

    distances_km: list[float] = [0.0]
    elevations_m: list[float | None] = [points[0][2]]
    distance_m = 0.0

    for i in range(1, len(points)):
        lat, lon, elev = points[i]
        prev_lat, prev_lon, _ = points[i - 1]
        distance_m += _haversine_km(prev_lat, prev_lon, lat, lon) * 1000
        distances_km.append(round(distance_m / 1000, 3))
        elevations_m.append(elev)

    has_elevation = any(e is not None for e in elevations_m)
    if not has_elevation:
        return {"has_elevation": False, "distances_km": [], "elevations_m": []}

    distances_km, elevations_m = _downsample_profile(distances_km, elevations_m)
    return {
        "has_elevation": True,
        "distances_km": distances_km,
        "elevations_m": elevations_m,
        "distance_km": round(distance_m / 1000, 2),
    }
