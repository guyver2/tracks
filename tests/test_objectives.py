from datetime import date

import pytest

from app.db.models import (
    Activity,
    ActivityType,
    Objective,
    ObjectiveActivityType,
    ObjectiveMetric,
    ObjectivePeriod,
)
from app.services.objectives import compute_progress, objective_label, period_dates


def test_period_dates_for_month_and_year():
    ref = date(2024, 6, 15)

    month_start, month_end = period_dates(ObjectivePeriod.month, ref)
    year_start, year_end = period_dates(ObjectivePeriod.year, ref)

    assert month_start == date(2024, 6, 1)
    assert month_end == date(2024, 6, 30)
    assert year_start == date(2024, 1, 1)
    assert year_end == date(2024, 12, 31)


def test_period_dates_custom_requires_explicit_dates():
    with pytest.raises(ValueError):
        period_dates(ObjectivePeriod.custom)


def test_objective_label_uses_custom_label():
    objective = Objective(
        metric=ObjectiveMetric.distance_km,
        activity_type=ObjectiveActivityType.bike,
        target_value=100,
        period=ObjectivePeriod.year,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        label="Century challenge",
    )

    assert objective_label(objective) == "Century challenge"


def test_compute_progress_counts_matching_activities(db):
    objective = Objective(
        metric=ObjectiveMetric.activity_count,
        activity_type=ObjectiveActivityType.bike,
        target_value=3,
        period=ObjectivePeriod.custom,
        start_date=date(2024, 6, 1),
        end_date=date(2024, 6, 30),
    )
    db.add(objective)
    db.add_all(
        [
            Activity(
                name="Ride 1",
                activity_type=ActivityType.bike,
                date=date(2024, 6, 5),
            ),
            Activity(
                name="Ride 2",
                activity_type=ActivityType.bike,
                date=date(2024, 6, 10),
            ),
            Activity(
                name="Hike",
                activity_type=ActivityType.hike,
                date=date(2024, 6, 12),
            ),
            Activity(
                name="Old ride",
                activity_type=ActivityType.bike,
                date=date(2024, 5, 30),
            ),
        ]
    )
    db.commit()

    progress = compute_progress(db, objective)

    assert progress["current"] == 2.0
    assert progress["target"] == 3
    assert progress["pct"] == pytest.approx(66.7, abs=0.1)


def test_compute_progress_sums_distance_and_caps_percent(db):
    objective = Objective(
        metric=ObjectiveMetric.distance_km,
        activity_type=ObjectiveActivityType.any,
        target_value=10,
        period=ObjectivePeriod.custom,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    db.add(objective)
    db.add_all(
        [
            Activity(
                name="Long day",
                activity_type=ActivityType.hike,
                date=date(2024, 3, 1),
                distance_km=8.0,
            ),
            Activity(
                name="Extra",
                activity_type=ActivityType.bike,
                date=date(2024, 4, 1),
                distance_km=5.0,
            ),
        ]
    )
    db.commit()

    progress = compute_progress(db, objective)

    assert progress["current"] == 13.0
    assert progress["pct"] == 100.0
