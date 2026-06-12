from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityType


def _apply_activity_filters(
    query,
    *,
    activity_type: ActivityType | None = None,
    start: date | None = None,
    end: date | None = None,
):
    if activity_type is not None:
        query = query.filter(Activity.activity_type == activity_type)
    if start is not None:
        query = query.filter(Activity.date >= start)
    if end is not None:
        query = query.filter(Activity.date <= end)
    return query


def get_totals(
    db: Session,
    *,
    activity_type: ActivityType | None = None,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    query = _apply_activity_filters(
        db.query(
            Activity.activity_type,
            func.count(Activity.id),
            func.coalesce(func.sum(Activity.distance_km), 0),
            func.coalesce(func.sum(Activity.elevation_gain_m), 0),
            func.coalesce(func.sum(Activity.duration_sec), 0),
        ),
        activity_type=activity_type,
        start=start,
        end=end,
    )
    rows = query.group_by(Activity.activity_type).all()

    totals = {
        "all": {"count": 0, "distance_km": 0.0, "elevation_m": 0.0, "duration_sec": 0},
        **{
            t.value: {"count": 0, "distance_km": 0.0, "elevation_m": 0.0, "duration_sec": 0}
            for t in ActivityType
        },
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
    }
    for activity_type, count, distance in rows:
        result["count"] += count
        result["distance_km"] += float(distance)
        result[f"{activity_type.value}_count"] = count
        result[f"{activity_type.value}_km"] = round(float(distance), 1)
    result["distance_km"] = round(result["distance_km"], 1)
    return result


def get_monthly_series(
    db: Session,
    *,
    activity_type: ActivityType | None = None,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    query = _apply_activity_filters(
        db.query(
            extract("year", Activity.date).label("year"),
            extract("month", Activity.date).label("month"),
            func.count(Activity.id),
            func.coalesce(func.sum(Activity.distance_km), 0),
            func.coalesce(func.sum(Activity.elevation_gain_m), 0),
        ),
        activity_type=activity_type,
        start=start,
        end=end,
    )
    rows = query.group_by("year", "month").order_by("year", "month").all()

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


def get_type_breakdown(
    db: Session,
    *,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    totals = get_totals(db, start=start, end=end)
    type_labels = {
        ActivityType.hike: "Hikes",
        ActivityType.bike: "Bike rides",
        ActivityType.skitouring: "Ski touring",
        ActivityType.climbing: "Climbing",
        ActivityType.swimming: "Swimming",
    }
    return {
        "labels": [type_labels[t] for t in ActivityType],
        "counts": [totals[t.value]["count"] for t in ActivityType],
        "distances": [totals[t.value]["distance_km"] for t in ActivityType],
        "cards": [
            {"label": type_labels[t], "count": totals[t.value]["count"]}
            for t in ActivityType
        ],
    }


def month_bounds(reference: date | None = None) -> tuple[date, date]:
    ref = reference or date.today()
    last_day = monthrange(ref.year, ref.month)[1]
    return date(ref.year, ref.month, 1), date(ref.year, ref.month, last_day)


def year_bounds(reference: date | None = None) -> tuple[date, date]:
    ref = reference or date.today()
    return date(ref.year, 1, 1), date(ref.year, 12, 31)


def resolve_date_range(
    preset: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[date | None, date | None, str]:
    if preset == "month":
        start, end = month_bounds()
        return start, end, f"{start.strftime('%b %Y')}"
    if preset == "year":
        start, end = year_bounds()
        return start, end, str(start.year)
    if preset == "custom" and date_from and date_to:
        start, end = date.fromisoformat(date_from), date.fromisoformat(date_to)
        if start > end:
            start, end = end, start
        label = f"{start.isoformat()} – {end.isoformat()}"
        return start, end, label
    return None, None, "All time"


def get_activity_calendar(db: Session, weeks: int = 52) -> dict:
    today = date.today()
    range_end = today
    range_start = today - timedelta(days=weeks * 7 - 1)
    range_start -= timedelta(days=range_start.weekday())

    rows = (
        db.query(Activity.date, func.count(Activity.id))
        .filter(Activity.date >= range_start, Activity.date <= range_end)
        .group_by(Activity.date)
        .all()
    )
    counts_by_date = {d: int(c) for d, c in rows}

    cells: list[dict] = []
    month_labels: list[dict] = []
    total_active_days = 0
    current = range_start
    week_col = 0
    prev_month: int | None = None

    while current <= range_end:
        if current.month != prev_month:
            month_labels.append({"col": week_col, "label": current.strftime("%b")})
            prev_month = current.month

        for day_offset in range(7):
            d = current + timedelta(days=day_offset)
            if d > range_end:
                break
            count = counts_by_date.get(d, 0)
            active = count > 0
            if active:
                total_active_days += 1
            cells.append({"date": d, "count": count, "active": active, "is_today": d == today})

        current += timedelta(days=7)
        week_col += 1

    range_label = (
        f"{range_start.strftime('%b %Y')} – {range_end.strftime('%b %Y')}"
    )

    return {
        "cells": cells,
        "weeks": week_col,
        "month_labels": month_labels,
        "total_active_days": total_active_days,
        "range_label": range_label,
    }
