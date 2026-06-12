"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_type", sa.Enum("hike", "bike", name="activitytype"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("place", sa.String(length=255), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("gpx_filename", sa.String(length=512), nullable=True),
        sa.Column("photo_filename", sa.String(length=512), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("elevation_gain_m", sa.Float(), nullable=True),
        sa.Column("bounds_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_activities_date"), "activities", ["date"], unique=False)

    op.create_table(
        "objectives",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "metric",
            sa.Enum("distance_km", "duration_hours", "activity_count", name="objectivemetric"),
            nullable=False,
        ),
        sa.Column(
            "activity_type",
            sa.Enum("hike", "bike", "any", name="objectiveactivitytype"),
            nullable=False,
        ),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("period", sa.Enum("month", "year", "custom", name="objectiveperiod"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("objectives")
    op.drop_index(op.f("ix_activities_date"), table_name="activities")
    op.drop_table("activities")
