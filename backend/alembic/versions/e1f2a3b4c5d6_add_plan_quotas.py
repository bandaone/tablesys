"""Add plan quotas table and seed data

Revision ID: e1f2a3b4c5d6
Revises: d9e8f7a6b5c4
Create Date: 2026-05-05 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d9e8f7a6b5c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_quotas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_tier", sa.String(), nullable=False),
        sa.Column("metric_key", sa.String(), nullable=False),
        sa.Column("limit_quantity", sa.BigInteger(), nullable=False),
        sa.Column("enforcement", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_tier", "metric_key", name="uq_plan_quota_tier_metric"),
    )
    op.create_index(op.f("ix_plan_quotas_id"), "plan_quotas", ["id"], unique=False)
    op.create_index("ix_plan_quota_tier_metric", "plan_quotas", ["plan_tier", "metric_key"], unique=False)

    plan_quota_table = sa.table(
        "plan_quotas",
        sa.column("plan_tier", sa.String()),
        sa.column("metric_key", sa.String()),
        sa.column("limit_quantity", sa.BigInteger()),
        sa.column("enforcement", sa.String()),
    )

    gb = 1024 ** 3
    seed_rows = [
        # Starter
        {"plan_tier": "starter", "metric_key": "seats_active", "limit_quantity": 1000, "enforcement": "warn"},
        {"plan_tier": "starter", "metric_key": "timetable_generations", "limit_quantity": 10, "enforcement": "block"},
        {"plan_tier": "starter", "metric_key": "department_count", "limit_quantity": 15, "enforcement": "warn"},
        {"plan_tier": "starter", "metric_key": "course_count", "limit_quantity": 150, "enforcement": "warn"},
        {"plan_tier": "starter", "metric_key": "storage_bytes", "limit_quantity": 5 * gb, "enforcement": "warn"},
        # Professional
        {"plan_tier": "professional", "metric_key": "seats_active", "limit_quantity": 5000, "enforcement": "warn"},
        {"plan_tier": "professional", "metric_key": "timetable_generations", "limit_quantity": 30, "enforcement": "block"},
        {"plan_tier": "professional", "metric_key": "department_count", "limit_quantity": 50, "enforcement": "warn"},
        {"plan_tier": "professional", "metric_key": "course_count", "limit_quantity": 500, "enforcement": "warn"},
        {"plan_tier": "professional", "metric_key": "storage_bytes", "limit_quantity": 25 * gb, "enforcement": "warn"},
        # Enterprise
        {"plan_tier": "enterprise", "metric_key": "seats_active", "limit_quantity": 50000, "enforcement": "warn"},
        {"plan_tier": "enterprise", "metric_key": "timetable_generations", "limit_quantity": 100, "enforcement": "block"},
        {"plan_tier": "enterprise", "metric_key": "department_count", "limit_quantity": 200, "enforcement": "warn"},
        {"plan_tier": "enterprise", "metric_key": "course_count", "limit_quantity": 2000, "enforcement": "warn"},
        {"plan_tier": "enterprise", "metric_key": "storage_bytes", "limit_quantity": 100 * gb, "enforcement": "warn"},
    ]
    op.bulk_insert(plan_quota_table, seed_rows)


def downgrade() -> None:
    op.drop_index("ix_plan_quota_tier_metric", table_name="plan_quotas")
    op.drop_index(op.f("ix_plan_quotas_id"), table_name="plan_quotas")
    op.drop_table("plan_quotas")
