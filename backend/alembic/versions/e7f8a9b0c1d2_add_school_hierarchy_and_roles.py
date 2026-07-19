"""add school hierarchy and tenant admin roles

Revision ID: e7f8a9b0c1d2
Revises: 6a7b8c9d0e1f, da3592bf282d
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = ("6a7b8c9d0e1f", "da3592bf282d")
branch_labels = None
depends_on = None


def _extend_user_role_enum() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for value in ("TENANT_ADMIN", "SCHOOL_COORDINATOR", "LECTURER", "STUDENT"):
        op.execute(
            sa.text(
                f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{value}'"
            )
        )


def upgrade() -> None:
    _extend_user_role_enum()

    op.create_table(
        "schools",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("academic_calendar_id", sa.Integer(), nullable=True),
        sa.Column("scheduling_policy", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["academic_calendar_id"], ["academic_calendars.id"]),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("university_id", "code", name="uq_school_univ_code"),
        sa.UniqueConstraint("university_id", "name", name="uq_school_univ_name"),
    )
    op.create_index(op.f("ix_schools_id"), "schools", ["id"], unique=False)
    op.create_index(op.f("ix_schools_university_id"), "schools", ["university_id"], unique=False)
    op.create_index(op.f("ix_schools_academic_calendar_id"), "schools", ["academic_calendar_id"], unique=False)

    with op.batch_alter_table("departments") as batch_op:
        batch_op.add_column(sa.Column("school_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_departments_school_id"), ["school_id"], unique=False)
        batch_op.create_foreign_key("fk_departments_school_id_schools", "schools", ["school_id"], ["id"])

    with op.batch_alter_table("rooms") as batch_op:
        batch_op.add_column(sa.Column("school_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_rooms_school_id"), ["school_id"], unique=False)
        batch_op.create_foreign_key("fk_rooms_school_id_schools", "schools", ["school_id"], ["id"])

    with op.batch_alter_table("timetables") as batch_op:
        batch_op.add_column(sa.Column("school_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_timetables_school_id"), ["school_id"], unique=False)
        batch_op.create_foreign_key("fk_timetables_school_id_schools", "schools", ["school_id"], ["id"])

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("school_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_users_school_id"), ["school_id"], unique=False)
        batch_op.create_foreign_key("fk_users_school_id_schools", "schools", ["school_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_school_id_schools", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_users_school_id"))
        batch_op.drop_column("school_id")

    with op.batch_alter_table("timetables") as batch_op:
        batch_op.drop_constraint("fk_timetables_school_id_schools", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_timetables_school_id"))
        batch_op.drop_column("school_id")

    with op.batch_alter_table("rooms") as batch_op:
        batch_op.drop_constraint("fk_rooms_school_id_schools", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_rooms_school_id"))
        batch_op.drop_column("school_id")

    with op.batch_alter_table("departments") as batch_op:
        batch_op.drop_constraint("fk_departments_school_id_schools", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_departments_school_id"))
        batch_op.drop_column("school_id")

    op.drop_index(op.f("ix_schools_academic_calendar_id"), table_name="schools")
    op.drop_index(op.f("ix_schools_university_id"), table_name="schools")
    op.drop_index(op.f("ix_schools_id"), table_name="schools")
    op.drop_table("schools")
