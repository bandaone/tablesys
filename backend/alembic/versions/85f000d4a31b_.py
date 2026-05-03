"""empty message

Revision ID: 85f000d4a31b
Revises: 85beba529589, c3d4e5f6a7b8
Create Date: 2026-03-18 23:16:13.421677

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85f000d4a31b'
down_revision: Union[str, None] = ('85beba529589', 'c3d4e5f6a7b8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
