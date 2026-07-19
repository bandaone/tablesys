"""Merge usage models and exam domain

Revision ID: da3592bf282d
Revises: d4e5f6a7b8c9, e1f2a3b4c5d6
Create Date: 2026-05-05 19:55:31.359274

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da3592bf282d'
down_revision: Union[str, None] = ('d4e5f6a7b8c9', 'e1f2a3b4c5d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
