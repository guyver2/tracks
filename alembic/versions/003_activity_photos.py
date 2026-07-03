"""activity photos

Revision ID: 003
Revises: 002
Create Date: 2026-07-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activity_photos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_activity_photos_activity_id"), "activity_photos", ["activity_id"], unique=False
    )

    conn = op.get_bind()
    activities = conn.execute(
        sa.text("SELECT id, photo_filename FROM activities WHERE photo_filename IS NOT NULL")
    ).fetchall()
    for activity_id, photo_filename in activities:
        conn.execute(
            sa.text(
                "INSERT INTO activity_photos (activity_id, filename, sort_order) "
                "VALUES (:activity_id, :filename, 0)"
            ),
            {"activity_id": activity_id, "filename": photo_filename},
        )

    with op.batch_alter_table("activities") as batch_op:
        batch_op.drop_column("photo_filename")


def downgrade() -> None:
    with op.batch_alter_table("activities") as batch_op:
        batch_op.add_column(sa.Column("photo_filename", sa.String(length=512), nullable=True))

    conn = op.get_bind()
    photos = conn.execute(
        sa.text(
            "SELECT activity_id, filename FROM activity_photos "
            "WHERE sort_order = 0 ORDER BY id"
        )
    ).fetchall()
    seen: set[int] = set()
    for activity_id, filename in photos:
        if activity_id in seen:
            continue
        seen.add(activity_id)
        conn.execute(
            sa.text("UPDATE activities SET photo_filename = :filename WHERE id = :activity_id"),
            {"activity_id": activity_id, "filename": filename},
        )

    op.drop_index(op.f("ix_activity_photos_activity_id"), table_name="activity_photos")
    op.drop_table("activity_photos")
