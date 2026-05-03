"""phase6 timeslot grid and availability

Revision ID: a2b3c4d5e6f7
Revises: f1c2d3e4a5b6
Create Date: 2026-03-15 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f1c2d3e4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create academic_calendars table
    op.create_table(
        'academic_calendars',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('university_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('days_of_week', sa.JSON(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('slot_duration_minutes', sa.Integer(), nullable=True, default=60),
        sa.Column('is_default', sa.Boolean(), nullable=True, default=False),
        sa.ForeignKeyConstraint(['university_id'], ['universities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_academic_calendars_id'), 'academic_calendars', ['id'], unique=False)
    op.create_index(op.f('ix_academic_calendars_university_id'), 'academic_calendars', ['university_id'], unique=False)

    # 2. Add academic_calendar_id to timetables
    op.add_column('timetables', sa.Column('academic_calendar_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_timetables_calendar', 'timetables', 'academic_calendars', ['academic_calendar_id'], ['id'])

    # 3. Update rooms availability to availability_blocks
    op.add_column('rooms', sa.Column('availability_blocks', sa.JSON(), nullable=True))
    
    # We drop the old column (after migrating data if we strictly wanted to, but this is early stage)
    op.drop_column('rooms', 'availability')


def downgrade() -> None:
    # 1. Revert rooms
    op.add_column('rooms', sa.Column('availability', sa.String(), nullable=True))
    op.drop_column('rooms', 'availability_blocks')

    # 2. Revert timetables
    op.drop_constraint('fk_timetables_calendar', 'timetables', type_='foreignkey')
    op.drop_column('timetables', 'academic_calendar_id')

    # 3. Drop table
    op.drop_index(op.f('ix_academic_calendars_university_id'), table_name='academic_calendars')
    op.drop_index(op.f('ix_academic_calendars_id'), table_name='academic_calendars')
    op.drop_table('academic_calendars')
