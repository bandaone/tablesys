"""add viewer activity table

Revision ID: f6a1b2c3d4e5
Revises: da3592bf282d
Create Date: 2026-05-14 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "f6a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "da3592bf282d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "viewer_activity" not in inspector.get_table_names():
        op.create_table(
            "viewer_activity",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("audience", sa.String(), nullable=False),
            sa.Column("viewer_id", sa.String(), nullable=True),
            sa.Column("lecturer_id", sa.Integer(), nullable=True),
            sa.Column("group_id", sa.Integer(), nullable=True),
            sa.Column("route_key", sa.String(), nullable=False),
            sa.Column("method", sa.String(), nullable=False, server_default="GET"),
            sa.Column("status_code", sa.Integer(), nullable=False, server_default="200"),
            sa.Column("response_time_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["group_id"], ["student_groups.id"]),
            sa.ForeignKeyConstraint(["lecturer_id"], ["lecturers.id"]),
            sa.ForeignKeyConstraint(["tenant_id"], ["universities.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = {index["name"] for index in inspector.get_indexes("viewer_activity")}

    for index_name, columns in [
        (op.f("ix_viewer_activity_audience"), ["audience"]),
        (op.f("ix_viewer_activity_group_id"), ["group_id"]),
        (op.f("ix_viewer_activity_id"), ["id"]),
        (op.f("ix_viewer_activity_lecturer_id"), ["lecturer_id"]),
        (op.f("ix_viewer_activity_occurred_at"), ["occurred_at"]),
        (op.f("ix_viewer_activity_route_key"), ["route_key"]),
        (op.f("ix_viewer_activity_tenant_id"), ["tenant_id"]),
        (op.f("ix_viewer_activity_viewer_id"), ["viewer_id"]),
        ("ix_viewer_activity_tenant_audience_time", ["tenant_id", "audience", "occurred_at"]),
        ("ix_viewer_activity_tenant_route_time", ["tenant_id", "route_key", "occurred_at"]),
    ]:
        if index_name not in existing_indexes:
            op.create_index(index_name, "viewer_activity", columns, unique=False)


def downgrade() -> None:
    op.drop_index("ix_viewer_activity_tenant_route_time", table_name="viewer_activity")
    op.drop_index("ix_viewer_activity_tenant_audience_time", table_name="viewer_activity")
    op.drop_index(op.f("ix_viewer_activity_viewer_id"), table_name="viewer_activity")
    op.drop_index(op.f("ix_viewer_activity_tenant_id"), table_name="viewer_activity")
    op.drop_index(op.f("ix_viewer_activity_route_key"), table_name="viewer_activity")
    op.drop_index(op.f("ix_viewer_activity_occurred_at"), table_name="viewer_activity")
    op.drop_index(op.f("ix_viewer_activity_lecturer_id"), table_name="viewer_activity")
    op.drop_index(op.f("ix_viewer_activity_id"), table_name="viewer_activity")
    op.drop_index(op.f("ix_viewer_activity_group_id"), table_name="viewer_activity")
    op.drop_index(op.f("ix_viewer_activity_audience"), table_name="viewer_activity")
    op.drop_table("viewer_activity")
