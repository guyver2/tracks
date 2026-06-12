import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ActivityType(str, enum.Enum):
    hike = "hike"
    bike = "bike"


class ObjectiveMetric(str, enum.Enum):
    distance_km = "distance_km"
    duration_hours = "duration_hours"
    activity_count = "activity_count"


class ObjectiveActivityType(str, enum.Enum):
    hike = "hike"
    bike = "bike"
    any = "any"


class ObjectivePeriod(str, enum.Enum):
    month = "month"
    year = "year"
    custom = "custom"


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_type: Mapped[ActivityType] = mapped_column(Enum(ActivityType), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    place: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    gpx_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    photo_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    bounds_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric: Mapped[ObjectiveMetric] = mapped_column(Enum(ObjectiveMetric), nullable=False)
    activity_type: Mapped[ObjectiveActivityType] = mapped_column(
        Enum(ObjectiveActivityType), nullable=False
    )
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    period: Mapped[ObjectivePeriod] = mapped_column(Enum(ObjectivePeriod), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
