"""activity tracks

Revision ID: 002
Revises: 001
Create Date: 2026-06-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activity_tracks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("gpx_filename", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trim_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trim_end", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("track_start_time", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_activity_tracks_activity_id"), "activity_tracks", ["activity_id"], unique=False
    )

    conn = op.get_bind()
    activities = conn.execute(
        sa.text("SELECT id, gpx_filename FROM activities WHERE gpx_filename IS NOT NULL")
    ).fetchall()
    for activity_id, gpx_filename in activities:
        conn.execute(
            sa.text(
                "INSERT INTO activity_tracks "
                "(activity_id, gpx_filename, sort_order, trim_start, trim_end) "
                "VALUES (:activity_id, :gpx_filename, 0, 0, 0)"
            ),
            {"activity_id": activity_id, "gpx_filename": gpx_filename},
        )

    with op.batch_alter_table("activities") as batch_op:
        batch_op.drop_column("gpx_filename")


def downgrade() -> None:
    with op.batch_alter_table("activities") as batch_op:
        batch_op.add_column(sa.Column("gpx_filename", sa.String(length=512), nullable=True))

    conn = op.get_bind()
    tracks = conn.execute(
        sa.text(
            "SELECT activity_id, gpx_filename FROM activity_tracks "
            "WHERE sort_order = 0 ORDER BY id"
        )
    ).fetchall()
    seen: set[int] = set()
    for activity_id, gpx_filename in tracks:
        if activity_id in seen:
            continue
        seen.add(activity_id)
        conn.execute(
            sa.text("UPDATE activities SET gpx_filename = :gpx_filename WHERE id = :activity_id"),
            {"activity_id": activity_id, "gpx_filename": gpx_filename},
        )

    op.drop_index(op.f("ix_activity_tracks_activity_id"), table_name="activity_tracks")
    op.drop_table("activity_tracks")
