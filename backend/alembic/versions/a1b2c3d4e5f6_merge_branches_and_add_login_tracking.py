"""Merge branches and add login tracking to lecturers and students

Revision ID: a1b2c3d4e5f6
Revises: 62bec6a9d2c1, f6a1b2c3d4e5
Create Date: 2026-05-17 17:00:00.000000

Merges the viewer_activity branch (f6a1b2c3d4e5) with the main
62bec6a9d2c1 branch, and adds last_login_at columns to lecturers
and students for accurate active-user dashboard metrics.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = ('62bec6a9d2c1', 'f6a1b2c3d4e5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_login_at to lecturers table
    op.add_column(
        'lecturers',
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True)
    )
    # Add last_login_at to students table
    op.add_column(
        'students',
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('students', 'last_login_at')
    op.drop_column('lecturers', 'last_login_at')
