"""repair missing scheduling columns

Revision ID: 6a7b8c9d0e1f
Revises: f3c4d5e6a7b8
Create Date: 2026-05-11 07:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6a7b8c9d0e1f"
down_revision = "f3c4d5e6a7b8"
branch_labels = None
depends_on = None


def _column_exists(inspector: sa.engine.reflection.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _table_exists(inspector: sa.engine.reflection.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "universities"):
        if not _column_exists(inspector, "universities", "scheduling_policy"):
            op.add_column("universities", sa.Column("scheduling_policy", sa.JSON(), nullable=True))
        if not _column_exists(inspector, "universities", "onboarding_completed_at"):
            op.add_column(
                "universities",
                sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
            )

    if _table_exists(inspector, "courses") and not _column_exists(inspector, "courses", "activity_requirements"):
        op.add_column("courses", sa.Column("activity_requirements", sa.JSON(), nullable=True))

    if _table_exists(inspector, "rooms") and not _column_exists(inspector, "rooms", "tags"):
        op.add_column("rooms", sa.Column("tags", sa.JSON(), nullable=True))

    if _table_exists(inspector, "student_groups") and not _column_exists(inspector, "student_groups", "custom_subtype"):
        op.add_column("student_groups", sa.Column("custom_subtype", sa.String(), nullable=True))

    if not _table_exists(inspector, "activity_types"):
        op.create_table(
            "activity_types",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("university_id", sa.Integer(), sa.ForeignKey("universities.id"), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("display_name", sa.String(), nullable=False),
            sa.Column("color", sa.String(), nullable=True),
            sa.Column("default_duration_periods", sa.Integer(), nullable=True),
            sa.Column("default_frequency_per_week", sa.Integer(), nullable=True),
            sa.Column("requires_subgroups", sa.Boolean(), nullable=True),
            sa.Column("resource_tags_required", sa.JSON(), nullable=True),
            sa.Column("counts_toward_contact_hours", sa.Boolean(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.UniqueConstraint("university_id", "key", name="uq_activity_type_univ_key"),
        )
        op.create_index(op.f("ix_activity_types_id"), "activity_types", ["id"], unique=False)
        op.create_index(op.f("ix_activity_types_university_id"), "activity_types", ["university_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "activity_types"):
        op.drop_index(op.f("ix_activity_types_university_id"), table_name="activity_types")
        op.drop_index(op.f("ix_activity_types_id"), table_name="activity_types")
        op.drop_table("activity_types")

    if _table_exists(inspector, "student_groups") and _column_exists(inspector, "student_groups", "custom_subtype"):
        op.drop_column("student_groups", "custom_subtype")

    if _table_exists(inspector, "rooms") and _column_exists(inspector, "rooms", "tags"):
        op.drop_column("rooms", "tags")

    if _table_exists(inspector, "courses") and _column_exists(inspector, "courses", "activity_requirements"):
        op.drop_column("courses", "activity_requirements")

    if _table_exists(inspector, "universities") and _column_exists(inspector, "universities", "onboarding_completed_at"):
        op.drop_column("universities", "onboarding_completed_at")

    if _table_exists(inspector, "universities") and _column_exists(inspector, "universities", "scheduling_policy"):
        op.drop_column("universities", "scheduling_policy")