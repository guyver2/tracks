import pytest

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.db.models import Activity, ActivityTrack, ActivityType
from app.services.gpx import best_effort_time_sec, load_stacked_track_points
from app.services.personal_records import (
    format_race_time,
    get_personal_records,
    read_personal_records_cache,
    records_for_activity,
    refresh_personal_records_cache,
)

def _straight_track(total_km: float, speed_kmh: float) -> list:
    points = []
    start = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
    segments = max(int(total_km * 10), 1)
    sec_per_segment = (total_km / segments) * 3600 / speed_kmh
    for index in range(segments + 1):
        dist = index * (total_km / segments)
        lat = 45.0 + dist / 111.0
        ts = start + timedelta(seconds=index * sec_per_segment)
        points.append((lat, 6.0, 1000.0, ts))
    return points


def test_best_effort_time_sec_finds_fastest_segment():
    points = _straight_track(10.0, 12.0)

    assert best_effort_time_sec(points, 5.0) == 1500
    assert best_effort_time_sec(points, 10.0) == 3000


def test_best_effort_time_sec_returns_none_without_timestamps():
    points = [(45.0, 6.0, 1000.0, None), (45.001, 6.001, 1000.0, None)]
    assert best_effort_time_sec(points, 5.0) is None


def test_format_race_time():
    assert format_race_time(1500) == "25:00"
    assert format_race_time(3661) == "1:01:01"


def test_get_personal_records_picks_distance_and_elevation_leaders(db, tmp_path):
    db.add_all(
        [
            Activity(
                name="Short hike",
                activity_type=ActivityType.hike,
                date=date(2024, 6, 1),
                distance_km=8.0,
                elevation_gain_m=400.0,
                duration_sec=7200,
            ),
            Activity(
                name="Long ride",
                activity_type=ActivityType.bike,
                date=date(2024, 6, 2),
                distance_km=120.0,
                elevation_gain_m=2500.0,
                duration_sec=18000,
            ),
            Activity(
                name="Climb day",
                activity_type=ActivityType.climbing,
                date=date(2024, 6, 3),
                distance_km=2.0,
                elevation_gain_m=800.0,
                duration_sec=3600,
            ),
        ]
    )
    db.commit()

    cache_path = tmp_path / "personal_records.json"
    records = get_personal_records(db, tmp_path, cache_path)
    by_key = {record.key: record for record in records}

    assert by_key["longest_distance"].activity_name == "Long ride"
    assert by_key["longest_distance_bike"].activity_name == "Long ride"
    assert by_key["most_elevation"].activity_name == "Long ride"
    assert by_key["longest_duration"].activity_name == "Long ride"


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


def test_get_personal_records_includes_best_efforts_from_gpx(db, tmp_path):
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    gpx_path = gpx_dir / "fast.gpx"
    _write_gpx(gpx_path, _straight_track(10.0, 12.0))

    activity = Activity(
        name="Tempo run",
        activity_type=ActivityType.hike,
        date=date(2024, 7, 1),
        distance_km=10.0,
        elevation_gain_m=50.0,
        duration_sec=3000,
    )
    db.add(activity)
    db.flush()
    db.add(
        ActivityTrack(
            activity_id=activity.id,
            gpx_filename="fast.gpx",
            sort_order=0,
        )
    )
    db.commit()

    cache_path = tmp_path / "personal_records.json"
    records = get_personal_records(db, gpx_dir, cache_path)
    by_key = {record.key: record for record in records}

    assert by_key["best_5k"].activity_name == "Tempo run"
    assert by_key["best_5k"].value_display == "25:00"
    assert records_for_activity(activity.id, records)


def test_load_stacked_track_points_honors_trim(db, tmp_path):
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    gpx_path = gpx_dir / "track.gpx"
    gpx_path.write_text((Path(__file__).parent / "fixtures" / "simple_track.gpx").read_text(), encoding="utf-8")

    activity = Activity(
        name="Trimmed",
        activity_type=ActivityType.hike,
        date=date(2024, 7, 2),
        distance_km=1.0,
    )
    db.add(activity)
    db.flush()
    db.add(
        ActivityTrack(
            activity_id=activity.id,
            gpx_filename="track.gpx",
            trim_start=1,
            trim_end=1,
            sort_order=0,
        )
    )
    db.commit()
    db.refresh(activity)

    points = load_stacked_track_points(activity.tracks, gpx_dir)
    assert len(points) == 2


def test_personal_records_cache_avoids_recompute_when_valid(db, tmp_path):
    cache_path = tmp_path / "personal_records.json"
    db.add(
        Activity(
            name="Cached ride",
            activity_type=ActivityType.bike,
            date=date(2024, 6, 1),
            distance_km=50.0,
            elevation_gain_m=1000.0,
            duration_sec=7200,
        )
    )
    db.commit()

    refresh_personal_records_cache(db, tmp_path, cache_path)
    payload = read_personal_records_cache(cache_path)
    assert payload is not None
    assert payload["activity_count"] == 1

    records = get_personal_records(db, tmp_path, cache_path)
    assert records[0].activity_name == "Cached ride"


def test_personal_records_cache_refreshes_when_activities_change(db, tmp_path):
    cache_path = tmp_path / "personal_records.json"
    db.add(
        Activity(
            name="Short",
            activity_type=ActivityType.hike,
            date=date(2024, 6, 1),
            distance_km=5.0,
            elevation_gain_m=100.0,
            duration_sec=3600,
        )
    )
    db.commit()
    refresh_personal_records_cache(db, tmp_path, cache_path)

    db.add(
        Activity(
            name="Longer",
            activity_type=ActivityType.bike,
            date=date(2024, 6, 2),
            distance_km=100.0,
            elevation_gain_m=2000.0,
            duration_sec=7200,
        )
    )
    db.commit()

    by_key = {record.key: record for record in get_personal_records(db, tmp_path, cache_path)}
    assert by_key["longest_distance"].activity_name == "Longer"
