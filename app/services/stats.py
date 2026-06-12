from calendar import monthrange
from datetime import date

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityType


def get_totals(db: Session) -> dict:
    rows = (
        db.query(
            Activity.activity_type,
            func.count(Activity.id),
            func.coalesce(func.sum(Activity.distance_km), 0),
            func.coalesce(func.sum(Activity.elevation_gain_m), 0),
            func.coalesce(func.sum(Activity.duration_sec), 0),
        )
        .group_by(Activity.activity_type)
        .all()
    )

    totals = {
        "all": {"count": 0, "distance_km": 0.0, "elevation_m": 0.0, "duration_sec": 0},
        "hike": {"count": 0, "distance_km": 0.0, "elevation_m": 0.0, "duration_sec": 0},
        "bike": {"count": 0, "distance_km": 0.0, "elevation_m": 0.0, "duration_sec": 0},
    }

    for activity_type, count, distance, elevation, duration in rows:
        key = activity_type.value
        totals[key] = {
            "count": count,
            "distance_km": round(float(distance), 1),
            "elevation_m": round(float(elevation), 0),
            "duration_sec": int(duration or 0),
        }
        totals["all"]["count"] += count
        totals["all"]["distance_km"] += float(distance)
        totals["all"]["elevation_m"] += float(elevation)
        totals["all"]["duration_sec"] += int(duration or 0)

    totals["all"]["distance_km"] = round(totals["all"]["distance_km"], 1)
    totals["all"]["elevation_m"] = round(totals["all"]["elevation_m"], 0)
    return totals


def get_period_totals(db: Session, start: date, end: date) -> dict:
    rows = (
        db.query(
            Activity.activity_type,
            func.count(Activity.id),
            func.coalesce(func.sum(Activity.distance_km), 0),
        )
        .filter(Activity.date >= start, Activity.date <= end)
        .group_by(Activity.activity_type)
        .all()
    )

    result = {
        "count": 0,
        "distance_km": 0.0,
        "hike_count": 0,
        "bike_count": 0,
        "hike_km": 0.0,
        "bike_km": 0.0,
    }
    for activity_type, count, distance in rows:
        result["count"] += count
        result["distance_km"] += float(distance)
        if activity_type == ActivityType.hike:
            result["hike_count"] = count
            result["hike_km"] = round(float(distance), 1)
        else:
            result["bike_count"] = count
            result["bike_km"] = round(float(distance), 1)
    result["distance_km"] = round(result["distance_km"], 1)
    return result


def get_monthly_series(db: Session) -> dict:
    rows = (
        db.query(
            extract("year", Activity.date).label("year"),
            extract("month", Activity.date).label("month"),
            func.count(Activity.id),
            func.coalesce(func.sum(Activity.distance_km), 0),
            func.coalesce(func.sum(Activity.elevation_gain_m), 0),
        )
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )

    labels = []
    counts = []
    distances = []
    elevations = []

    for year, month, count, distance, elevation in rows:
        labels.append(f"{int(year)}-{int(month):02d}")
        counts.append(int(count))
        distances.append(round(float(distance), 1))
        elevations.append(round(float(elevation), 0))

    return {
        "labels": labels,
        "counts": counts,
        "distances": distances,
        "elevations": elevations,
    }


def get_type_breakdown(db: Session) -> dict:
    totals = get_totals(db)
    return {
        "labels": ["Hikes", "Bike rides"],
        "counts": [totals["hike"]["count"], totals["bike"]["count"]],
        "distances": [totals["hike"]["distance_km"], totals["bike"]["distance_km"]],
    }


def month_bounds(reference: date | None = None) -> tuple[date, date]:
    ref = reference or date.today()
    last_day = monthrange(ref.year, ref.month)[1]
    return date(ref.year, ref.month, 1), date(ref.year, ref.month, last_day)
