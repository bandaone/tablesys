"""Backfill university data and enforce NOT NULL

Revision ID: f1c2d3e4a5b6
Revises: 8e6e4dd249bd
Create Date: 2026-03-15 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1c2d3e4a5b6'
down_revision: Union[str, None] = '8e6e4dd249bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Backfill default university if it doesn't exist
    op.execute(
        """
        INSERT INTO universities (id, name, domain, timezone, is_active)
        VALUES (1, 'University of Zambia', 'unza.zm', 'Africa/Harare', true)
        ON CONFLICT (id) DO NOTHING
        """
    )

    # 2. Update existing rows in all tables with university_id
    tables = [
        'users', 
        'departments', 
        'rooms', 
        'student_groups', 
        'timetables', 
        'template_profiles'
    ]
    
    for table in tables:
        op.execute(f"UPDATE {table} SET university_id = 1 WHERE university_id IS NULL")

    # 3. Alter columns to be NOT NULL
    for table in tables:
        op.alter_column(table, 'university_id',
               existing_type=sa.INTEGER(),
               nullable=False)


def downgrade() -> None:
    # We don't remove the default university, but we do allow NULLs again
    tables = [
        'users', 
        'departments', 
        'rooms', 
        'student_groups', 
        'timetables', 
        'template_profiles'
    ]
    for table in tables:
        op.alter_column(table, 'university_id',
               existing_type=sa.INTEGER(),
               nullable=True)
