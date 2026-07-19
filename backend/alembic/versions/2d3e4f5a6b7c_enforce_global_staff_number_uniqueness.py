"""enforce global case-insensitive lecturer staff numbers

Revision ID: 2d3e4f5a6b7c
Revises: 1c2d3e4f5a6b
Create Date: 2026-07-18
"""

from alembic import op


revision = "2d3e4f5a6b7c"
down_revision = "1c2d3e4f5a6b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Do not pick a winner automatically: a duplicate staff number can have
    # timetable history and must be resolved by management before go-live.
    duplicates = op.get_bind().exec_driver_sql("""
        SELECT lower(trim(staff_number)), count(*)
        FROM lecturers
        GROUP BY lower(trim(staff_number))
        HAVING count(*) > 1
    """).fetchall()
    if duplicates:
        values = ", ".join(str(row[0]) for row in duplicates[:10])
        raise RuntimeError(
            "Cannot enforce global staff-number uniqueness. Resolve duplicate staff numbers first: " + values
        )

    # Canonical uppercase storage makes lookup and imports predictable. The
    # unique expression index prevents case-only duplicates in every path.
    op.execute("UPDATE lecturers SET staff_number = upper(trim(staff_number))")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_lecturers_staff_number_ci "
        "ON lecturers (lower(staff_number))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_lecturers_staff_number_ci")
