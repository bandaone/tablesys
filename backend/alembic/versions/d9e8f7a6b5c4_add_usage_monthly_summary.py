"""Add usage monthly summaries table

Revision ID: d9e8f7a6b5c4
Revises: c7a1b2c3d4e5
Create Date: 2026-05-05 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d9e8f7a6b5c4"
down_revision: Union[str, None] = "c7a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_monthly_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_key", sa.String(), nullable=False),
        sa.Column("total_quantity", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["universities.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "period_start", "metric_key", name="uq_usage_summary_period"),
    )
    op.create_index(op.f("ix_usage_monthly_summaries_id"), "usage_monthly_summaries", ["id"], unique=False)
    op.create_index("ix_usage_summary_tenant_period", "usage_monthly_summaries", ["tenant_id", "period_start"], unique=False)
    op.create_index(op.f("ix_usage_monthly_summaries_metric_key"), "usage_monthly_summaries", ["metric_key"], unique=False)
    op.create_index(op.f("ix_usage_monthly_summaries_period_start"), "usage_monthly_summaries", ["period_start"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_usage_monthly_summaries_period_start"), table_name="usage_monthly_summaries")
    op.drop_index(op.f("ix_usage_monthly_summaries_metric_key"), table_name="usage_monthly_summaries")
    op.drop_index("ix_usage_summary_tenant_period", table_name="usage_monthly_summaries")
    op.drop_index(op.f("ix_usage_monthly_summaries_id"), table_name="usage_monthly_summaries")
    op.drop_table("usage_monthly_summaries")
