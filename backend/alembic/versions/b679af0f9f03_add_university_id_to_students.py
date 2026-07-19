"""add_university_id_to_students

Revision ID: b679af0f9f03
Revises: e7f8a9b0c1d2
Create Date: 2026-05-12 02:55:08.009610

Safe migration: adds a nullable university_id column and index to the students
table.  Existing rows remain unaffected (column is NULL until backfilled).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b679af0f9f03'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add university_id to students (nullable so existing rows are unaffected)
    op.add_column('students', sa.Column('university_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_students_university_id'), 'students', ['university_id'], unique=False)
    op.create_foreign_key(
        'fk_students_university_id', 'students', 'universities',
        ['university_id'], ['id'], ondelete='SET NULL'
    )

    # Backfill university_id from the student's assigned group
    op.execute("""
        UPDATE students s
        SET university_id = sg.university_id
        FROM student_groups sg
        WHERE s.group_id = sg.id
          AND s.university_id IS NULL
    """)


def downgrade() -> None:
    op.drop_constraint('fk_students_university_id', 'students', type_='foreignkey')
    op.drop_index(op.f('ix_students_university_id'), table_name='students')
    op.drop_column('students', 'university_id')
