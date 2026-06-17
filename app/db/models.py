import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ActivityType(str, enum.Enum):
    hike = "hike"
    bike = "bike"
    skitouring = "skitouring"
    climbing = "climbing"
    swimming = "swimming"

    @property
    def supports_track(self) -> bool:
        return self in {
            ActivityType.hike,
            ActivityType.bike,
            ActivityType.skitouring,
        }

    @property
    def supports_manual_stats(self) -> bool:
        return self is ActivityType.swimming


class ObjectiveMetric(str, enum.Enum):
    distance_km = "distance_km"
    duration_hours = "duration_hours"
    elevation_gain_m = "elevation_gain_m"
    activity_count = "activity_count"


class ObjectiveActivityType(str, enum.Enum):
    hike = "hike"
    bike = "bike"
    skitouring = "skitouring"
    climbing = "climbing"
    swimming = "swimming"
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
    photo_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    bounds_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    tracks: Mapped[list["ActivityTrack"]] = relationship(
        back_populates="activity",
        cascade="all, delete-orphan",
        order_by="ActivityTrack.sort_order",
    )


class ActivityTrack(Base):
    __tablename__ = "activity_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gpx_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trim_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trim_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    track_start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    activity: Mapped["Activity"] = relationship(back_populates="tracks")


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
