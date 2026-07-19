"""Add platform alerts table

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-17 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "platform_alerts" not in inspector.get_table_names():
        op.create_table(
            "platform_alerts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("severity", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("detail", sa.String(), nullable=True),
            sa.Column("tenant_name", sa.String(), nullable=True),
            sa.Column("tenant_id", sa.Integer(), nullable=True),
            sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("acknowledged_by", sa.String(), nullable=True),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("alert_key", sa.String(), nullable=False),
            sa.Column("auto_resolve", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.ForeignKeyConstraint(["tenant_id"], ["universities.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("alert_key"),
        )

    existing_indexes = {index["name"] for index in inspector.get_indexes("platform_alerts")}
    for index_name, columns in [
        (op.f("ix_platform_alerts_id"), ["id"]),
        (op.f("ix_platform_alerts_severity"), ["severity"]),
        (op.f("ix_platform_alerts_category"), ["category"]),
        (op.f("ix_platform_alerts_tenant_id"), ["tenant_id"]),
        (op.f("ix_platform_alerts_triggered_at"), ["triggered_at"]),
        (op.f("ix_platform_alerts_resolved_at"), ["resolved_at"]),
        (op.f("ix_platform_alerts_alert_key"), ["alert_key"]),
    ]:
        if index_name not in existing_indexes:
            op.create_index(index_name, "platform_alerts", columns, unique=False)


def downgrade() -> None:
    for index_name in [
        op.f("ix_platform_alerts_alert_key"),
        op.f("ix_platform_alerts_resolved_at"),
        op.f("ix_platform_alerts_triggered_at"),
        op.f("ix_platform_alerts_tenant_id"),
        op.f("ix_platform_alerts_category"),
        op.f("ix_platform_alerts_severity"),
        op.f("ix_platform_alerts_id"),
    ]:
        op.drop_index(index_name, table_name="platform_alerts")
    op.drop_table("platform_alerts")
