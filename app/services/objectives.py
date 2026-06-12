from calendar import monthrange
from datetime import date

from sqlalchemy.orm import Session

from app.db.models import (
    Activity,
    ActivityType,
    Objective,
    ObjectiveActivityType,
    ObjectiveMetric,
    ObjectivePeriod,
)


def period_dates(period: ObjectivePeriod, ref: date | None = None) -> tuple[date, date]:
    today = ref or date.today()
    if period == ObjectivePeriod.month:
        last = monthrange(today.year, today.month)[1]
        return date(today.year, today.month, 1), date(today.year, today.month, last)
    if period == ObjectivePeriod.year:
        return date(today.year, 1, 1), date(today.year, 12, 31)
    raise ValueError("Custom period requires explicit dates")


def objective_label(obj: Objective) -> str:
    if obj.label:
        return obj.label
    metric_labels = {
        ObjectiveMetric.distance_km: "Distance",
        ObjectiveMetric.duration_hours: "Duration",
        ObjectiveMetric.elevation_gain_m: "Elevation",
        ObjectiveMetric.activity_count: "Activities",
    }
    type_labels = {
        ObjectiveActivityType.hike: "hikes",
        ObjectiveActivityType.bike: "bike rides",
        ObjectiveActivityType.skitouring: "ski tours",
        ObjectiveActivityType.climbing: "climbing sessions",
        ObjectiveActivityType.swimming: "swims",
        ObjectiveActivityType.any: "activities",
    }
    metric_units = {
        ObjectiveMetric.distance_km: "km",
        ObjectiveMetric.duration_hours: "h",
        ObjectiveMetric.elevation_gain_m: "m",
        ObjectiveMetric.activity_count: "",
    }
    unit = metric_units[obj.metric]
    target = f"{obj.target_value:g}{unit}"
    return f"{target} {type_labels[obj.activity_type]} ({obj.period.value})"


def compute_progress(db: Session, objective: Objective) -> dict:
    query = db.query(Activity).filter(
        Activity.date >= objective.start_date,
        Activity.date <= objective.end_date,
    )

    if objective.activity_type == ObjectiveActivityType.hike:
        query = query.filter(Activity.activity_type == ActivityType.hike)
    elif objective.activity_type == ObjectiveActivityType.bike:
        query = query.filter(Activity.activity_type == ActivityType.bike)
    elif objective.activity_type == ObjectiveActivityType.skitouring:
        query = query.filter(Activity.activity_type == ActivityType.skitouring)
    elif objective.activity_type == ObjectiveActivityType.climbing:
        query = query.filter(Activity.activity_type == ActivityType.climbing)
    elif objective.activity_type == ObjectiveActivityType.swimming:
        query = query.filter(Activity.activity_type == ActivityType.swimming)

    activities = query.all()

    if objective.metric == ObjectiveMetric.activity_count:
        current = float(len(activities))
    elif objective.metric == ObjectiveMetric.distance_km:
        current = sum(a.distance_km or 0 for a in activities)
    elif objective.metric == ObjectiveMetric.elevation_gain_m:
        current = sum(a.elevation_gain_m or 0 for a in activities)
    else:
        current = sum((a.duration_sec or 0) for a in activities) / 3600

    current = round(current, 2)
    target = objective.target_value
    pct = min(100.0, round(current / target * 100, 1)) if target > 0 else 0.0

    return {
        "current": current,
        "target": target,
        "pct": pct,
        "label": objective_label(objective),
        "metric": objective.metric.value,
    }


def all_objectives_with_progress(db: Session) -> list[dict]:
    objectives = db.query(Objective).order_by(Objective.end_date.desc()).all()
    return [{"objective": obj, "progress": compute_progress(db, obj)} for obj in objectives]
