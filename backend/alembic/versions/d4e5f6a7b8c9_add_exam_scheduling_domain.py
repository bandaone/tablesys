"""
Add coordinator exam scheduling domain

Revision ID: d4e5f6a7b8c9
Revises: 22fabd14da9d
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "22fabd14da9d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "exam_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("semester", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=True),
        sa.Column("is_locked", sa.Boolean(), nullable=True),
        sa.Column("constraint_settings", sa.JSON(), nullable=True),
        sa.Column("generation_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exam_periods_id", "exam_periods", ["id"], unique=False)
    op.create_index("ix_exam_periods_university_id", "exam_periods", ["university_id"], unique=False)
    op.create_index("ix_exam_periods_year", "exam_periods", ["year"], unique=False)
    op.create_index("ix_exam_periods_start_date", "exam_periods", ["start_date"], unique=False)
    op.create_index("ix_exam_periods_end_date", "exam_periods", ["end_date"], unique=False)
    op.create_index("ix_exam_period_university_year", "exam_periods", ["university_id", "year"], unique=False)

    op.create_table(
        "exam_session_windows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exam_period_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("allow_weekends", sa.Boolean(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["exam_period_id"], ["exam_periods.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exam_session_windows_id", "exam_session_windows", ["id"], unique=False)
    op.create_index("ix_exam_session_windows_exam_period_id", "exam_session_windows", ["exam_period_id"], unique=False)
    op.create_index("ix_exam_session_window_period_order", "exam_session_windows", ["exam_period_id", "display_order"], unique=False)

    op.create_table(
        "exam_seating_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("capacity_factor", sa.Integer(), nullable=False),
        sa.Column("fixed_capacity", sa.Integer(), nullable=True),
        sa.Column("requires_computers", sa.Boolean(), nullable=True),
        sa.Column("spacing_strategy", sa.String(), nullable=True),
        sa.Column("profile_metadata", sa.JSON(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exam_seating_profiles_id", "exam_seating_profiles", ["id"], unique=False)
    op.create_index("ix_exam_seating_profiles_university_id", "exam_seating_profiles", ["university_id"], unique=False)
    op.create_index("ix_exam_seating_profile_university_name", "exam_seating_profiles", ["university_id", "name"], unique=False)

    op.create_table(
        "exam_papers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exam_period_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("paper_code", sa.String(), nullable=False),
        sa.Column("paper_name", sa.String(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=True),
        sa.Column("group_ids", sa.JSON(), nullable=False),
        sa.Column("preferred_room_type", sa.String(), nullable=True),
        sa.Column("preferred_seating_profile_id", sa.Integer(), nullable=True),
        sa.Column("max_rooms", sa.Integer(), nullable=True),
        sa.Column("allow_custom_window", sa.Boolean(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["exam_period_id"], ["exam_periods.id"]),
        sa.ForeignKeyConstraint(["preferred_seating_profile_id"], ["exam_seating_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exam_papers_id", "exam_papers", ["id"], unique=False)
    op.create_index("ix_exam_papers_exam_period_id", "exam_papers", ["exam_period_id"], unique=False)
    op.create_index("ix_exam_papers_course_id", "exam_papers", ["course_id"], unique=False)
    op.create_index("ix_exam_papers_paper_code", "exam_papers", ["paper_code"], unique=False)
    op.create_index("ix_exam_paper_period_code", "exam_papers", ["exam_period_id", "paper_code"], unique=False)

    op.create_table(
        "exam_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exam_period_id", sa.Integer(), nullable=False),
        sa.Column("exam_paper_id", sa.Integer(), nullable=False),
        sa.Column("session_window_id", sa.Integer(), nullable=False),
        sa.Column("seating_profile_id", sa.Integer(), nullable=True),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("total_allocated_capacity", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("generated_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exam_paper_id"], ["exam_papers.id"]),
        sa.ForeignKeyConstraint(["exam_period_id"], ["exam_periods.id"]),
        sa.ForeignKeyConstraint(["seating_profile_id"], ["exam_seating_profiles.id"]),
        sa.ForeignKeyConstraint(["session_window_id"], ["exam_session_windows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exam_slots_id", "exam_slots", ["id"], unique=False)
    op.create_index("ix_exam_slots_exam_period_id", "exam_slots", ["exam_period_id"], unique=False)
    op.create_index("ix_exam_slots_exam_paper_id", "exam_slots", ["exam_paper_id"], unique=False)
    op.create_index("ix_exam_slots_session_window_id", "exam_slots", ["session_window_id"], unique=False)
    op.create_index("ix_exam_slots_seating_profile_id", "exam_slots", ["seating_profile_id"], unique=False)
    op.create_index("ix_exam_slots_exam_date", "exam_slots", ["exam_date"], unique=False)
    op.create_index("ix_exam_slot_period_date", "exam_slots", ["exam_period_id", "exam_date"], unique=False)
    op.create_index("ix_exam_slot_paper_date", "exam_slots", ["exam_paper_id", "exam_date"], unique=False)

    op.create_table(
        "exam_slot_rooms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exam_slot_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("seating_profile_id", sa.Integer(), nullable=True),
        sa.Column("allocated_capacity", sa.Integer(), nullable=False),
        sa.Column("allocated_group_ids", sa.JSON(), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["exam_slot_id"], ["exam_slots.id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.ForeignKeyConstraint(["seating_profile_id"], ["exam_seating_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exam_slot_rooms_id", "exam_slot_rooms", ["id"], unique=False)
    op.create_index("ix_exam_slot_rooms_exam_slot_id", "exam_slot_rooms", ["exam_slot_id"], unique=False)
    op.create_index("ix_exam_slot_rooms_room_id", "exam_slot_rooms", ["room_id"], unique=False)
    op.create_index("ix_exam_slot_rooms_seating_profile_id", "exam_slot_rooms", ["seating_profile_id"], unique=False)
    op.create_index("ix_exam_slot_room_slot_room", "exam_slot_rooms", ["exam_slot_id", "room_id"], unique=False)


def downgrade():
    op.drop_index("ix_exam_slot_room_slot_room", table_name="exam_slot_rooms")
    op.drop_index("ix_exam_slot_rooms_seating_profile_id", table_name="exam_slot_rooms")
    op.drop_index("ix_exam_slot_rooms_room_id", table_name="exam_slot_rooms")
    op.drop_index("ix_exam_slot_rooms_exam_slot_id", table_name="exam_slot_rooms")
    op.drop_index("ix_exam_slot_rooms_id", table_name="exam_slot_rooms")
    op.drop_table("exam_slot_rooms")

    op.drop_index("ix_exam_slot_paper_date", table_name="exam_slots")
    op.drop_index("ix_exam_slot_period_date", table_name="exam_slots")
    op.drop_index("ix_exam_slots_exam_date", table_name="exam_slots")
    op.drop_index("ix_exam_slots_seating_profile_id", table_name="exam_slots")
    op.drop_index("ix_exam_slots_session_window_id", table_name="exam_slots")
    op.drop_index("ix_exam_slots_exam_paper_id", table_name="exam_slots")
    op.drop_index("ix_exam_slots_exam_period_id", table_name="exam_slots")
    op.drop_index("ix_exam_slots_id", table_name="exam_slots")
    op.drop_table("exam_slots")

    op.drop_index("ix_exam_paper_period_code", table_name="exam_papers")
    op.drop_index("ix_exam_papers_paper_code", table_name="exam_papers")
    op.drop_index("ix_exam_papers_course_id", table_name="exam_papers")
    op.drop_index("ix_exam_papers_exam_period_id", table_name="exam_papers")
    op.drop_index("ix_exam_papers_id", table_name="exam_papers")
    op.drop_table("exam_papers")

    op.drop_index("ix_exam_seating_profile_university_name", table_name="exam_seating_profiles")
    op.drop_index("ix_exam_seating_profiles_university_id", table_name="exam_seating_profiles")
    op.drop_index("ix_exam_seating_profiles_id", table_name="exam_seating_profiles")
    op.drop_table("exam_seating_profiles")

    op.drop_index("ix_exam_session_window_period_order", table_name="exam_session_windows")
    op.drop_index("ix_exam_session_windows_exam_period_id", table_name="exam_session_windows")
    op.drop_index("ix_exam_session_windows_id", table_name="exam_session_windows")
    op.drop_table("exam_session_windows")

    op.drop_index("ix_exam_period_university_year", table_name="exam_periods")
    op.drop_index("ix_exam_periods_end_date", table_name="exam_periods")
    op.drop_index("ix_exam_periods_start_date", table_name="exam_periods")
    op.drop_index("ix_exam_periods_year", table_name="exam_periods")
    op.drop_index("ix_exam_periods_university_id", table_name="exam_periods")
    op.drop_index("ix_exam_periods_id", table_name="exam_periods")
    op.drop_table("exam_periods")
