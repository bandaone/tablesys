"""normalize academic levels to the canonical hundred-level format

Revision ID: 0b1c2d3e4f5a
Revises: e88371c99363
Create Date: 2026-07-18

The application historically accepted both ``3`` and ``300`` for Year 3.
That produced duplicate Year 3 sections in the course UI and made data imports
look redundant.  Store all academic levels as 100, 200, …, 700.
"""

from alembic import op


revision = "0b1c2d3e4f5a"
down_revision = "e88371c99363"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Courses and groups participate together in timetable generation, so they
    # must use the same representation. Values outside 1–7 are left untouched.
    op.execute("UPDATE courses SET level = level * 100 WHERE level BETWEEN 1 AND 7")
    op.execute("UPDATE student_groups SET level = level * 100 WHERE level BETWEEN 1 AND 7")


def downgrade() -> None:
    op.execute("UPDATE courses SET level = level / 100 WHERE level IN (100, 200, 300, 400, 500, 600, 700)")
    op.execute("UPDATE student_groups SET level = level / 100 WHERE level IN (100, 200, 300, 400, 500, 600, 700)")
