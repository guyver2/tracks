from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.db.models import Activity, ActivityTrack, ActivityType
from app.services.heatmap import (
    compute_heatmap_data,
    get_heatmap_data,
    invalidate_heatmap_cache,
    refresh_heatmap_cache,
)


def _write_gpx(path: Path, points: list) -> None:
    segments = []
    for lat, lon, elev, ts in points:
        time_text = ts.strftime("%Y-%m-%dT%H:%M:%SZ") if ts else ""
        segments.append(
            f'      <trkpt lat="{lat:.6f}" lon="{lon:.6f}">'
            f"<ele>{elev}</ele><time>{time_text}</time></trkpt>"
        )
    path.write_text(
        "\n".join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<gpx version="1.1" creator="tracks-test"><trk><trkseg>',
                *segments,
                "</trkseg></trk></gpx>",
            ]
        ),
        encoding="utf-8",
    )


def _straight_track(total_km: float, speed_kmh: float, start_lat: float = 45.0) -> list:
    points = []
    start = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
    segments = max(int(total_km * 10), 1)
    sec_per_segment = (total_km / segments) * 3600 / speed_kmh
    for index in range(segments + 1):
        dist = index * (total_km / segments)
        lat = start_lat + dist / 111.0
        ts = start + timedelta(seconds=index * sec_per_segment)
        points.append((lat, 6.0, 1000.0, ts))
    return points


def test_compute_heatmap_data_empty_without_tracks(db, tmp_path):
    db.add(
        Activity(
            name="No track",
            activity_type=ActivityType.climbing,
            date=date(2024, 6, 1),
        )
    )
    db.commit()

    data = compute_heatmap_data(db, tmp_path)
    assert data["has_data"] is False
    assert data["points"] == []


def test_compute_heatmap_data_includes_sampled_track_points(db, tmp_path):
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    _write_gpx(gpx_dir / "ride.gpx", _straight_track(5.0, 20.0))

    activity = Activity(
        name="Local ride",
        activity_type=ActivityType.bike,
        date=date(2024, 6, 1),
        distance_km=5.0,
    )
    db.add(activity)
    db.flush()
    db.add(
        ActivityTrack(
            activity_id=activity.id,
            gpx_filename="ride.gpx",
            sort_order=0,
        )
    )
    db.commit()

    data = compute_heatmap_data(db, gpx_dir)
    assert data["has_data"] is True
    assert len(data["points"]) >= 2
    assert data["bounds"]["min_lat"] < data["bounds"]["max_lat"]


def test_heatmap_cache_reuses_valid_payload(db, tmp_path):
    gpx_dir = tmp_path / "gpx"
    cache_dir = tmp_path / "cache"
    gpx_dir.mkdir()
    _write_gpx(gpx_dir / "ride.gpx", _straight_track(3.0, 18.0))

    activity = Activity(
        name="Cached ride",
        activity_type=ActivityType.bike,
        date=date(2024, 6, 1),
        distance_km=3.0,
    )
    db.add(activity)
    db.flush()
    db.add(
        ActivityTrack(
            activity_id=activity.id,
            gpx_filename="ride.gpx",
            sort_order=0,
        )
    )
    db.commit()

    refresh_heatmap_cache(db, gpx_dir, cache_dir=cache_dir)
    cached = get_heatmap_data(db, gpx_dir, cache_dir=cache_dir)
    assert cached["has_data"] is True
    assert len(list(cache_dir.glob("*.json"))) == 1


def test_invalidate_heatmap_cache_clears_files(db, tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "abc.json").write_text("{}", encoding="utf-8")

    invalidate_heatmap_cache(cache_dir)
    assert list(cache_dir.glob("*.json")) == []
