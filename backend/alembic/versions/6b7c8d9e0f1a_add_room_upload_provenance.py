"""record the coordinator who loaded each room

Revision ID: 6b7c8d9e0f1a
Revises: 5a6b7c8d9e0f
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa


revision = "6b7c8d9e0f1a"
down_revision = "5a6b7c8d9e0f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rooms", sa.Column("created_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_rooms_created_by_user", "rooms", "users", ["created_by_id"], ["id"])
    op.create_index("ix_rooms_created_by_id", "rooms", ["created_by_id"])


def downgrade() -> None:
    op.drop_index("ix_rooms_created_by_id", table_name="rooms")
    op.drop_constraint("fk_rooms_created_by_user", "rooms", type_="foreignkey")
    op.drop_column("rooms", "created_by_id")
