"""assign ownership to unscoped single-school timetables

Revision ID: 4f5a6b7c8d9e
Revises: 3e4f5a6b7c8d
Create Date: 2026-07-19

An unscoped timetable is safe to assign only when every slot's course belongs
to exactly one school. Mixed-school timetables remain unscoped deliberately so
management can split or explicitly classify them instead of leaking them.
"""

from alembic import op


revision = "4f5a6b7c8d9e"
down_revision = "3e4f5a6b7c8d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE timetables AS timetable
        SET school_id = inferred.school_id
        FROM (
            SELECT slot.timetable_id, min(department.school_id) AS school_id
            FROM timetable_slots AS slot
            JOIN courses AS course ON course.id = slot.course_id
            JOIN departments AS department ON department.id = course.department_id
            WHERE department.school_id IS NOT NULL
            GROUP BY slot.timetable_id
            HAVING count(DISTINCT department.school_id) = 1
        ) AS inferred
        WHERE timetable.id = inferred.timetable_id
          AND timetable.school_id IS NULL
    """)


def downgrade() -> None:
    # Do not erase an ownership decision once it has been applied.
    pass
