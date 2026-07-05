from datetime import date

from app.db.models import Activity, ActivityType
from app.routers.activities import (
    DEFAULT_SORT,
    _filtered_activities_query,
    _next_sort,
    _parse_sort,
)


def _seed_activities(db):
    db.add_all(
        [
            Activity(
                name="Old short",
                activity_type=ActivityType.hike,
                date=date(2024, 1, 1),
                distance_km=5.0,
                duration_sec=3600,
                elevation_gain_m=200.0,
            ),
            Activity(
                name="Recent long",
                activity_type=ActivityType.bike,
                date=date(2024, 6, 1),
                distance_km=80.0,
                duration_sec=14400,
                elevation_gain_m=1200.0,
            ),
            Activity(
                name="Mid climb",
                activity_type=ActivityType.climbing,
                date=date(2024, 3, 1),
                distance_km=2.0,
                duration_sec=7200,
                elevation_gain_m=400.0,
            ),
        ]
    )
    db.commit()


def test_default_sort_is_newest_date(db):
    _seed_activities(db)

    activities = _filtered_activities_query(db, activity_type=None, date_from=None, date_to=None).all()

    assert [activity.name for activity in activities] == [
        "Recent long",
        "Mid climb",
        "Old short",
    ]


def test_sort_by_distance_desc(db):
    _seed_activities(db)

    activities = _filtered_activities_query(
        db,
        activity_type=None,
        date_from=None,
        date_to=None,
        sort="distance_desc",
    ).all()

    assert [activity.name for activity in activities] == [
        "Recent long",
        "Old short",
        "Mid climb",
    ]


def test_sort_by_duration_desc(db):
    _seed_activities(db)

    activities = _filtered_activities_query(
        db,
        activity_type=None,
        date_from=None,
        date_to=None,
        sort="duration_desc",
    ).all()

    assert [activity.name for activity in activities] == [
        "Recent long",
        "Mid climb",
        "Old short",
    ]


def test_sort_by_elevation_asc(db):
    _seed_activities(db)

    activities = _filtered_activities_query(
        db,
        activity_type=None,
        date_from=None,
        date_to=None,
        sort="elevation_asc",
    ).all()

    assert [activity.name for activity in activities] == [
        "Old short",
        "Mid climb",
        "Recent long",
    ]


def test_invalid_sort_falls_back_to_default(db):
    _seed_activities(db)

    activities = _filtered_activities_query(
        db,
        activity_type=None,
        date_from=None,
        date_to=None,
        sort="invalid",
    ).all()

    assert activities[0].name == "Recent long"
    assert DEFAULT_SORT == "date_desc"


def test_next_sort_toggles_direction_for_same_column():
    assert _next_sort("date", "date_desc") == "date_asc"
    assert _next_sort("date", "date_asc") == "date_desc"


def test_next_sort_switches_column_with_desc_default():
    assert _next_sort("distance", "date_desc") == "distance_desc"
    assert _parse_sort(_next_sort("duration", "distance_asc")) == ("duration", "desc")
