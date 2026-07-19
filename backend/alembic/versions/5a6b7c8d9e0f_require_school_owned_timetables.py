"""require every timetable to be owned by a school

Revision ID: 5a6b7c8d9e0f
Revises: 4f5a6b7c8d9e
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa


revision = "5a6b7c8d9e0f"
down_revision = "4f5a6b7c8d9e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    missing = op.get_bind().exec_driver_sql(
        "SELECT id FROM timetables WHERE school_id IS NULL LIMIT 10"
    ).fetchall()
    if missing:
        identifiers = ", ".join(str(row[0]) for row in missing)
        raise RuntimeError(
            "Every timetable must be assigned to a school before this upgrade. "
            "Unassigned timetable IDs: " + identifiers
        )
    op.alter_column("timetables", "school_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    op.alter_column("timetables", "school_id", existing_type=sa.Integer(), nullable=True)
