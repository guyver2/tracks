from datetime import date

from app.db.models import Activity, ActivityType
from app.services.stats import get_time_series, get_totals, resolve_date_range


def test_get_totals_aggregates_by_type(db):
    db.add_all(
        [
            Activity(
                name="Morning hike",
                activity_type=ActivityType.hike,
                date=date(2024, 6, 1),
                distance_km=10.0,
                elevation_gain_m=500.0,
                duration_sec=3600,
            ),
            Activity(
                name="Evening ride",
                activity_type=ActivityType.bike,
                date=date(2024, 6, 2),
                distance_km=25.0,
                elevation_gain_m=300.0,
                duration_sec=5400,
            ),
            Activity(
                name="Another hike",
                activity_type=ActivityType.hike,
                date=date(2024, 6, 3),
                distance_km=8.0,
                elevation_gain_m=400.0,
                duration_sec=3000,
            ),
        ]
    )
    db.commit()

    totals = get_totals(db)

    assert totals["all"]["count"] == 3
    assert totals["all"]["distance_km"] == 43.0
    assert totals["hike"]["count"] == 2
    assert totals["hike"]["distance_km"] == 18.0
    assert totals["bike"]["count"] == 1
    assert totals["bike"]["distance_km"] == 25.0


def test_get_totals_filters_by_type_and_date(db):
    db.add_all(
        [
            Activity(
                name="June hike",
                activity_type=ActivityType.hike,
                date=date(2024, 6, 15),
                distance_km=12.0,
            ),
            Activity(
                name="July hike",
                activity_type=ActivityType.hike,
                date=date(2024, 7, 1),
                distance_km=9.0,
            ),
            Activity(
                name="June ride",
                activity_type=ActivityType.bike,
                date=date(2024, 6, 20),
                distance_km=30.0,
            ),
        ]
    )
    db.commit()

    totals = get_totals(
        db,
        activity_type=ActivityType.hike,
        start=date(2024, 6, 1),
        end=date(2024, 6, 30),
    )

    assert totals["all"]["count"] == 1
    assert totals["all"]["distance_km"] == 12.0


def test_get_time_series_groups_by_month(db):
    db.add_all(
        [
            Activity(
                name="June outing",
                activity_type=ActivityType.hike,
                date=date(2024, 6, 10),
                distance_km=10.0,
                elevation_gain_m=100.0,
            ),
            Activity(
                name="July outing",
                activity_type=ActivityType.hike,
                date=date(2024, 7, 5),
                distance_km=15.0,
                elevation_gain_m=200.0,
            ),
        ]
    )
    db.commit()

    series = get_time_series(db, group_by="month")

    assert series["labels"] == ["2024-06", "2024-07"]
    assert series["counts"] == [1, 1]
    assert series["distances"] == [10.0, 15.0]
    assert series["elevations"] == [100.0, 200.0]


def test_resolve_date_range_custom_swaps_inverted_bounds():
    start, end, label = resolve_date_range(
        "custom",
        date_from="2024-12-01",
        date_to="2024-01-01",
    )

    assert start == date(2024, 1, 1)
    assert end == date(2024, 12, 1)
    assert "2024-01-01" in label
