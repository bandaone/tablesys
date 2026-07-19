"""add_exam_periods_columns

Revision ID: 023bbafa2c3e
Revises: b3c4d5e6f7a8
Create Date: 2026-05-19 22:55:11.504251

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '023bbafa2c3e'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('exam_periods', sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('exam_periods', sa.Column('created_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_exam_periods_created_by_id_users', 'exam_periods', 'users', ['created_by_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_exam_periods_created_by_id_users', 'exam_periods', type_='foreignkey')
    op.drop_column('exam_periods', 'created_by_id')
    op.drop_column('exam_periods', 'published_at')
