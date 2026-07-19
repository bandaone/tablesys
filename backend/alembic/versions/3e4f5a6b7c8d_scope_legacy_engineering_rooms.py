"""scope explicitly identified legacy engineering rooms

Revision ID: 3e4f5a6b7c8d
Revises: 2d3e4f5a6b7c
Create Date: 2026-07-19

Only rooms whose name or building explicitly identifies Engineering are
backfilled. Ambiguous venues (for example School of Mines or Annex Building)
are deliberately left untouched for management to classify.
"""

from alembic import op


revision = "3e4f5a6b7c8d"
down_revision = "2d3e4f5a6b7c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agricultural Engineering is a known SOE department, so these rooms can
    # safely receive both school and department ownership.
    op.execute("""
        UPDATE rooms AS room
        SET school_id = school.id,
            department_id = department.id
        FROM schools AS school
        JOIN departments AS department
          ON department.school_id = school.id
         AND department.code = 'AEN'
        WHERE room.university_id = school.university_id
          AND school.code = 'SOE'
          AND room.school_id IS NULL
          AND lower(coalesce(room.building, '')) LIKE '%agricultural engineering%'
    """)

    # Shared SOE venues are school-owned.  Do not infer a department for them.
    op.execute("""
        UPDATE rooms AS room
        SET school_id = school.id
        FROM schools AS school
        WHERE room.university_id = school.university_id
          AND school.code = 'SOE'
          AND room.school_id IS NULL
          AND (
              lower(coalesce(room.name, '')) LIKE '%engineering%'
              OR lower(coalesce(room.building, '')) LIKE '%engineering%'
          )
    """)


def downgrade() -> None:
    # A safe reversal must not erase ownership that management may have set
    # after this migration, so this migration is intentionally irreversible.
    pass
