"""
Phase 11: Add University branding fields and SUPERADMIN role

Revision ID: c3d4e5f6a7b8
Revises: f1c2d3e4a5b6
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'f1c2d3e4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    # Add branding and plan columns to universities table
    op.add_column('universities', sa.Column('short_name', sa.String(), nullable=True))
    op.add_column('universities', sa.Column('logo_url', sa.String(), nullable=True))
    op.add_column('universities', sa.Column('primary_color', sa.String(), nullable=True, server_default='#1976d2'))
    op.add_column('universities', sa.Column('secondary_color', sa.String(), nullable=True, server_default='#9c27b0'))
    op.add_column('universities', sa.Column('tagline', sa.String(), nullable=True))
    op.add_column('universities', sa.Column('plan_tier', sa.String(), nullable=True, server_default='free'))
    op.add_column('universities', sa.Column('max_users', sa.Integer(), nullable=True, server_default='50'))
    op.add_column('universities', sa.Column('registered_at', sa.DateTime(timezone=True), nullable=True))

    # Add SUPERADMIN to the userrole enum
    # PostgreSQL requires a special approach to alter enums
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'superadmin'")


def downgrade():
    # Remove branding columns
    op.drop_column('universities', 'registered_at')
    op.drop_column('universities', 'max_users')
    op.drop_column('universities', 'plan_tier')
    op.drop_column('universities', 'tagline')
    op.drop_column('universities', 'secondary_color')
    op.drop_column('universities', 'primary_color')
    op.drop_column('universities', 'logo_url')
    op.drop_column('universities', 'short_name')
    # Note: PostgreSQL does not support removing enum values, so downgrade cannot
    # remove 'superadmin' from the userrole enum without dropping and recreating the type.
