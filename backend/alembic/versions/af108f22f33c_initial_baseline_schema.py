"""Initial baseline schema

Revision ID: af108f22f33c
Revises: 
Create Date: 2026-03-15 12:59:29.802217

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'af108f22f33c'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass

def upgrade_old() -> None:
    pass


def downgrade() -> None:
    pass

def downgrade_old() -> None:
    pass
