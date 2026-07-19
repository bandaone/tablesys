"""add universal scheduling meta model

Revision ID: f3c4d5e6a7b8
Revises: b12f6a4c9d10
Create Date: 2026-05-10 18:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f3c4d5e6a7b8"
down_revision = "b12f6a4c9d10"
branch_labels = None
depends_on = None


def _drop_unique_if_exists(table_name: str, constraint_name: str) -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {constraint_name}")
        return

    inspector = sa.inspect(bind)
    unique_constraints = {
        item.get("name")
        for item in inspector.get_unique_constraints(table_name)
        if item.get("name")
    }
    if constraint_name in unique_constraints:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="unique")


def upgrade() -> None:
    op.add_column("universities", sa.Column("scheduling_policy", sa.JSON(), nullable=True))
    op.add_column("universities", sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True))

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

    op.add_column("courses", sa.Column("activity_requirements", sa.JSON(), nullable=True))
    op.add_column("rooms", sa.Column("tags", sa.JSON(), nullable=True))
    op.add_column("student_groups", sa.Column("custom_subtype", sa.String(), nullable=True))

    _drop_unique_if_exists("courses", "courses_code_key")
    _drop_unique_if_exists("rooms", "rooms_name_key")
    _drop_unique_if_exists("student_groups", "student_groups_name_key")

    op.create_unique_constraint("uq_course_dept_code", "courses", ["department_id", "code"])
    op.create_unique_constraint("uq_room_univ_name", "rooms", ["university_id", "name"])
    op.create_unique_constraint("uq_student_group_univ_name", "student_groups", ["university_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_student_group_univ_name", "student_groups", type_="unique")
    op.drop_constraint("uq_room_univ_name", "rooms", type_="unique")
    op.drop_constraint("uq_course_dept_code", "courses", type_="unique")

    op.execute("ALTER TABLE student_groups ADD CONSTRAINT student_groups_name_key UNIQUE (name)")
    op.execute("ALTER TABLE rooms ADD CONSTRAINT rooms_name_key UNIQUE (name)")
    op.execute("ALTER TABLE courses ADD CONSTRAINT courses_code_key UNIQUE (code)")

    op.drop_column("student_groups", "custom_subtype")
    op.drop_column("rooms", "tags")
    op.drop_column("courses", "activity_requirements")

    op.drop_index(op.f("ix_activity_types_university_id"), table_name="activity_types")
    op.drop_index(op.f("ix_activity_types_id"), table_name="activity_types")
    op.drop_table("activity_types")

    op.drop_column("universities", "onboarding_completed_at")
    op.drop_column("universities", "scheduling_policy")
