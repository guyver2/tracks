from datetime import datetime
from pathlib import Path

import pytest

from app.services.gpx import (
    GpxStats,
    TrackStats,
    aggregate_track_stats,
    apply_trim,
    downsample_coordinates,
    merge_bounds,
    parse_gpx_file,
    parse_track,
)

FIXTURES = Path(__file__).parent / "fixtures"
SIMPLE_TRACK = FIXTURES / "simple_track.gpx"


def test_parse_gpx_file_reads_distance_duration_and_elevation():
    stats = parse_gpx_file(SIMPLE_TRACK)

    assert stats.distance_km > 0
    assert stats.duration_sec == 30 * 60
    assert stats.elevation_gain_m == 30.0
    assert stats.bounds["min_lat"] == pytest.approx(45.0)
    assert stats.bounds["max_lat"] == pytest.approx(45.003)
    assert len(stats.coordinates) == 4


def test_parse_track_respects_trim():
    full = parse_track(SIMPLE_TRACK, trim_start=0, trim_end=0)
    trimmed = parse_track(SIMPLE_TRACK, trim_start=1, trim_end=1)

    assert full.point_count == 4
    assert trimmed.point_count == 2
    assert trimmed.distance_km < full.distance_km
    assert trimmed.track_start_time.replace(tzinfo=None) == datetime(2024, 6, 1, 8, 10, 0)


def test_apply_trim_rejects_invalid_values():
    points = [(45.0, 6.0, 1000.0, None)] * 4

    with pytest.raises(ValueError, match="zero or positive"):
        apply_trim(points, trim_start=-1, trim_end=0)

    with pytest.raises(ValueError, match="Trim removes too many points"):
        apply_trim(points, trim_start=2, trim_end=2)

    with pytest.raises(ValueError, match="At least 2 points must remain"):
        apply_trim(points, trim_start=3, trim_end=0)


def test_aggregate_track_stats_combines_tracks():
    first = TrackStats(
        distance_km=5.0,
        duration_sec=3600,
        elevation_gain_m=100.0,
        bounds={"min_lat": 45.0, "max_lat": 45.1, "min_lng": 6.0, "max_lng": 6.1},
        coordinates=[[6.0, 45.0], [6.1, 45.1]],
        point_count=2,
        track_start_time=None,
    )
    second = TrackStats(
        distance_km=3.5,
        duration_sec=1800,
        elevation_gain_m=50.0,
        bounds={"min_lat": 45.2, "max_lat": 45.3, "min_lng": 6.2, "max_lng": 6.3},
        coordinates=[[6.2, 45.2], [6.3, 45.3]],
        point_count=2,
        track_start_time=None,
    )

    aggregated = aggregate_track_stats([first, second])

    assert isinstance(aggregated, GpxStats)
    assert aggregated.distance_km == 8.5
    assert aggregated.duration_sec == 5400
    assert aggregated.elevation_gain_m == 150.0
    assert aggregated.bounds["min_lat"] == 45.0
    assert aggregated.bounds["max_lng"] == 6.3
    assert len(aggregated.coordinates) == 4


def test_aggregate_track_stats_empty_returns_none():
    assert aggregate_track_stats([]) is None


def test_downsample_coordinates_limits_points():
    coords = [[float(i), float(i)] for i in range(20)]
    sampled = downsample_coordinates(coords, max_points=5)

    assert len(sampled) == 5
    assert sampled[0] == coords[0]
    assert sampled[-1] == coords[-1]


def test_merge_bounds_combines_extents():
    merged = merge_bounds(
        [
            {"min_lat": 45.0, "max_lat": 45.5, "min_lng": 6.0, "max_lng": 6.5},
            {"min_lat": 44.5, "max_lat": 46.0, "min_lng": 5.5, "max_lng": 7.0},
        ]
    )

    assert merged == {
        "min_lat": 44.5,
        "max_lat": 46.0,
        "min_lng": 5.5,
        "max_lng": 7.0,
    }
