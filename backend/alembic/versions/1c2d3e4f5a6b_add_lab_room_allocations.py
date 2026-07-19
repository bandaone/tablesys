"""add department lab room allocations

Revision ID: 1c2d3e4f5a6b
Revises: 0b1c2d3e4f5a
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "1c2d3e4f5a6b"
down_revision = "0b1c2d3e4f5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_room_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("university_id", sa.Integer(), sa.ForeignKey("universities.id"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("department_id", "room_id", name="uq_lab_room_allocation_department_room"),
    )
    op.create_index("ix_lab_room_allocations_university_id", "lab_room_allocations", ["university_id"])
    op.create_index("ix_lab_room_allocations_department_id", "lab_room_allocations", ["department_id"])
    op.create_index(
        "ix_lab_room_allocation_university_department",
        "lab_room_allocations",
        ["university_id", "department_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lab_room_allocation_university_department", table_name="lab_room_allocations")
    op.drop_index("ix_lab_room_allocations_department_id", table_name="lab_room_allocations")
    op.drop_index("ix_lab_room_allocations_university_id", table_name="lab_room_allocations")
    op.drop_table("lab_room_allocations")
