"""add course profile status and nullable details

Revision ID: c4f5d6e7a8b9
Revises: a9ee854b9a69
Create Date: 2026-05-26 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4f5d6e7a8b9"
down_revision: Union[str, None] = "a9ee854b9a69"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("profile_status", sa.String(), nullable=True, server_default="profile_complete"))
    op.execute("UPDATE courses SET profile_status = 'profile_complete' WHERE profile_status IS NULL")
    op.alter_column("courses", "profile_status", nullable=False, existing_type=sa.String(), server_default="profile_complete")
    op.alter_column("courses", "credits", existing_type=sa.Integer(), nullable=True)
    op.alter_column("courses", "lecture_hours", existing_type=sa.Integer(), nullable=True)
    op.alter_column("courses", "tutorial_hours", existing_type=sa.Integer(), nullable=True)
    op.alter_column("courses", "practical_hours", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE courses SET credits = COALESCE(credits, 3)")
    op.execute("UPDATE courses SET lecture_hours = COALESCE(lecture_hours, 0)")
    op.execute("UPDATE courses SET tutorial_hours = COALESCE(tutorial_hours, 0)")
    op.execute("UPDATE courses SET practical_hours = COALESCE(practical_hours, 0)")
    op.alter_column("courses", "practical_hours", existing_type=sa.Integer(), nullable=False)
    op.alter_column("courses", "tutorial_hours", existing_type=sa.Integer(), nullable=False)
    op.alter_column("courses", "lecture_hours", existing_type=sa.Integer(), nullable=False)
    op.alter_column("courses", "credits", existing_type=sa.Integer(), nullable=False)
    op.drop_column("courses", "profile_status")
