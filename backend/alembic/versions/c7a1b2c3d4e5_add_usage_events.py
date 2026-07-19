"""Add usage events table

Revision ID: c7a1b2c3d4e5
Revises: 22fabd14da9d
Create Date: 2026-05-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7a1b2c3d4e5"
down_revision: Union[str, None] = "22fabd14da9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["universities.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usage_events_id"), "usage_events", ["id"], unique=False)
    op.create_index("ix_usage_events_tenant_metric", "usage_events", ["tenant_id", "metric_key"], unique=False)
    op.create_index("ix_usage_events_occurred_at", "usage_events", ["occurred_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_usage_events_occurred_at", table_name="usage_events")
    op.drop_index("ix_usage_events_tenant_metric", table_name="usage_events")
    op.drop_index(op.f("ix_usage_events_id"), table_name="usage_events")
    op.drop_table("usage_events")
