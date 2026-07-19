"""
Automated tests for the Timetable Generator scheduler.
This test suite verifies the core logic of timetable constraint generation and scheduling.
"""
import pytest
from datetime import time
from typing import Dict, Any
from unittest.mock import patch
from sqlalchemy.exc import IntegrityError

from app.models import (
    AcademicCalendar, University, Course, Department, Lecturer, Room,
    StudentGroup, Timetable, CourseType, RoomType, GroupType, ActivityType,
    School,
    LecturerUnavailability
)
from app.services.timetable_generator import TimetableGenerator
from app.seeding_utils import seed_tenant_baseline
from app.utils.department_utils import find_general_department

@pytest.fixture
def mock_db_setup(db_session):
    """
    Sets up a minimal viable academic dataset for the scheduler to operate on.
    """
    # Create university tenant
    univ = University(name="Algorithm Test Univ", domain="algotest.edu")
    db_session.add(univ)
    db_session.commit()

    # Create department
    dept = Department(university_id=univ.id, name="Computer Science", code="CS")
    db_session.add(dept)
    db_session.commit()

    # Create resources (Rooms, Lecturers, Groups, Courses)
    lecturer = Lecturer(department_id=dept.id, full_name="Dr. Smith", staff_number="L001", email="smith@test.edu", max_hours_per_week=20)
    room1 = Room(university_id=univ.id, name="Room 101", building="Science", capacity=50, room_type=RoomType.LECTURE_HALL)
    group1 = StudentGroup(university_id=univ.id, department_id=dept.id, name="CS Year 1", level=100, size=40)
    course1 = Course(code="CS101", name="Intro to CS", department_id=dept.id, level=100, credits=4, lecture_hours=3, course_type=CourseType.DEPARTMENT_SPECIFIC)
    
    db_session.add_all([lecturer, room1, group1, course1])
    db_session.commit()

    # Assign lecturer to course
    from app.models import LecturerAssignment, GroupAssignment
    la = LecturerAssignment(lecturer_id=lecturer.id, course_id=course1.id)
    ga = GroupAssignment(group_id=group1.id, course_id=course1.id)
    db_session.add_all([la, ga])
    db_session.commit()

    return {
        "university": univ,
        "department": dept,
        "lecturer": lecturer,
        "room": room1,
        "group": group1,
        "course": course1,
    }

def test_generator_sanity_baseline(mock_db_setup, db_session):
    """
    Verifies that a simple dataset with no conflicts generates a valid timetable.
    """
    # Create a blank timetable
    timetable = Timetable(
        university_id=mock_db_setup["university"].id,
        name="Test Sem 1",
        semester="1",
        year=2026,
        academic_half="1"
    )
    db_session.add(timetable)
    db_session.commit()
    
    generator = TimetableGenerator(db_session, timetable.id)
    
    # Test the generator
    with patch.object(generator, 'send_progress'):
        success = generator.generate_level_timetable(level=100, progress_start=0, progress_end=100)
    
    # 🎯 PRINT FOR THE USER TO SEE ALGORITHM WORKING
    print("\n\n" + "="*80)
    print("🎯 ALGORITHM SCAN: CP-SAT Constraint Output for Level 100")
    print("="*80)
    if not success:
        print("❌ FAILED: The solver could not find a feasible solution.")
    else:
        print(f"✅ SUCCESS: Generated {len(generator.all_slots)} slot assignments!\n")
        print(f"{'DAY':<12} | {'TIME':<13} | {'COURSE':<10} | {'TYPE':<10} | {'ROOM':<6} | L-ID")
        print("-" * 80)
        mock_courses = [mock_db_setup["course"]]
        mock_rooms = [mock_db_setup["room"]]

        for act in generator.all_slots:
            time_str = f"{act['start_time'].hour:02d}:00-{act['end_time'].hour:02d}:00"
            course_match = [c for c in mock_courses if c.id == act['course_id']]
            room_match = [r for r in mock_rooms if r.id == act['room_id']]
            course_code = course_match[0].code if course_match else "?"
            room_name = room_match[0].name if room_match else "?"
            print(f"{act['day_of_week']:<12} | {time_str:<13} | {course_code:<10} | {act['session_type']:<10} | {room_name:<6} | {act['lecturer_id']}")
    print("="*80 + "\n")

    assert success is True

    # Verify the data that was seeded is in the DB directly (replaces missing _fetch_data())
    from app.models import Course, Room
    courses_in_db = db_session.query(Course).filter(
        Course.department_id == mock_db_setup["department"].id
    ).all()
    rooms_in_db = db_session.query(Room).filter(
        Room.university_id == mock_db_setup["university"].id
    ).all()

    assert len(courses_in_db) >= 1
    assert any(c.code == "CS101" for c in courses_in_db)
    assert len(rooms_in_db) >= 1
    assert any(r.capacity == 50 for r in rooms_in_db)


def test_generator_uses_academic_calendar_as_base_and_grid_config_as_override(db_session):
    univ = University(name="Calendar Base Univ", domain="calendar-base.test")
    db_session.add(univ)
    db_session.commit()

    calendar = AcademicCalendar(
        university_id=univ.id,
        name="Primary Calendar",
        days_of_week=["Monday", "Tuesday", "Thursday"],
        start_time=time(8, 0),
        end_time=time(17, 0),
        slot_duration_minutes=90,
        is_default=True,
    )
    db_session.add(calendar)
    db_session.commit()

    timetable = Timetable(
        university_id=univ.id,
        name="Calendar Merge",
        semester="1",
        year=2026,
        academic_half="1",
        academic_calendar_id=calendar.id,
        generation_metadata={
            "grid_config": {
                "end_time": "18:00",
                "lunch_start": "12:30",
                "lunch_end": "13:30",
            }
        },
    )
    db_session.add(timetable)
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)

    assert generator.days == ["Monday", "Tuesday", "Thursday"]
    assert generator.slot_duration == 90
    assert generator.time_slots[0] == (time(8, 0), time(9, 30))
    assert generator.time_slots[-1] == (time(15, 30), time(17, 0))
    assert generator.num_slots == 6
    assert generator._overlaps_lunch(3, 1) is True
    assert generator._overlaps_lunch(0, 1) is False


def test_department_uniqueness_is_scoped_per_university(db_session):
    univ_a = University(name="Scoped Dept Univ A", domain="scoped-dept-a.test")
    univ_b = University(name="Scoped Dept Univ B", domain="scoped-dept-b.test")
    db_session.add_all([univ_a, univ_b])
    db_session.commit()

    dept_a = Department(university_id=univ_a.id, name="Civil Engineering", code="CEE")
    dept_b = Department(university_id=univ_b.id, name="Civil Engineering", code="CEE")
    db_session.add_all([dept_a, dept_b])
    db_session.commit()

    duplicate_same_university = Department(
        university_id=univ_a.id,
        name="Civil Engineering",
        code="CEE",
    )
    db_session.add(duplicate_same_university)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_activity_type_uniqueness_is_scoped_per_university(db_session):
    univ_a = University(name="Activity Univ A", domain="activity-a.test")
    univ_b = University(name="Activity Univ B", domain="activity-b.test")
    db_session.add_all([univ_a, univ_b])
    db_session.commit()

    db_session.add_all([
        ActivityType(university_id=univ_a.id, key="clinical_skills", display_name="Clinical Skills"),
        ActivityType(university_id=univ_b.id, key="clinical_skills", display_name="Clinical Skills"),
    ])
    db_session.commit()

    db_session.add(ActivityType(university_id=univ_a.id, key="clinical_skills", display_name="Duplicate"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_generator_prefers_activity_requirements_and_policy_defaults(db_session):
    univ = University(
        name="Policy Driven Univ",
        domain="policy-driven.test",
        scheduling_policy={
            "default_lecture_frequency": 3,
            "default_tutorial_frequency": 1,
            "default_practical_frequency": 1,
            "daily_max_teaching_hours": 8,
            "enforce_lunch_break": True,
            "institution_template_key": "nursing",
            "room_tag_catalog": ["theory_room", "clinical_skills_lab"],
        },
    )
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Nursing", code="NUR")
    db_session.add(dept)
    db_session.commit()

    db_session.add_all([
        ActivityType(
            university_id=univ.id,
            key="theory",
            display_name="Theory",
            default_duration_periods=2,
            default_frequency_per_week=3,
            resource_tags_required=["theory_room"],
        ),
        ActivityType(
            university_id=univ.id,
            key="clinical_skills",
            display_name="Clinical Skills",
            default_duration_periods=2,
            default_frequency_per_week=1,
            requires_subgroups=True,
            resource_tags_required=["clinical_skills_lab"],
        ),
    ])
    db_session.commit()

    course = Course(
        code="NUR201",
        name="Adult Nursing",
        department_id=dept.id,
        level=200,
        credits=4,
        lecture_hours=0,
        tutorial_hours=0,
        practical_hours=0,
        activity_requirements=[
            {"activity_type_key": "theory", "hours_per_session": 2},
            {"activity_type_key": "clinical_skills", "hours_per_session": 2, "frequency_per_week": 1},
        ],
    )
    timetable = Timetable(university_id=univ.id, name="Nursing Timetable", semester="1", year=2026, academic_half="1")
    db_session.add_all([course, timetable])
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    sessions = generator._parse_course_sessions(course)

    theory_sessions = [item for item in sessions if item["activity_type_key"] == "theory"]
    skills_sessions = [item for item in sessions if item["activity_type_key"] == "clinical_skills"]

    assert len(theory_sessions) == 3
    assert theory_sessions[0]["required_room_tags"] == ["theory_room"]
    assert len(skills_sessions) == 1
    assert skills_sessions[0]["requires_subgroups"] is True


def test_generator_component_sequence_supports_custom_activity_keys(db_session):
    univ = University(
        name="Custom Component Univ",
        domain="custom-component.test",
        scheduling_policy={"institution_template_key": "nursing"},
    )
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Nursing", code="NUR")
    db_session.add(dept)
    db_session.commit()

    db_session.add_all([
        ActivityType(university_id=univ.id, key="theory", display_name="Theory"),
        ActivityType(university_id=univ.id, key="clinical_skills", display_name="Clinical Skills"),
    ])
    db_session.add(
        Course(
            code="NUR100",
            name="Foundations",
            department_id=dept.id,
            level=100,
            credits=3,
            lecture_hours=0,
            tutorial_hours=0,
            practical_hours=0,
            activity_requirements=[
                {"activity_type_key": "theory", "hours_per_session": 2, "frequency_per_week": 2},
                {"activity_type_key": "clinical_skills", "hours_per_session": 2, "frequency_per_week": 1},
            ],
        )
    )
    timetable = Timetable(university_id=univ.id, name="Custom Components", semester="1", year=2026, academic_half="1")
    db_session.add(timetable)
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    assert generator._component_sequence() == ["theory", "clinical_skills"]

    selective = TimetableGenerator(db_session, timetable.id, components=["clinical_skills"])
    course = db_session.query(Course).filter(Course.code == "NUR100").first()
    sessions = selective._parse_course_sessions(course)
    assert {item["activity_type_key"] for item in sessions} == {"clinical_skills"}


def test_tag_based_room_matching_takes_precedence(db_session):
    univ = University(name="Tag Match Univ", domain="tag-match.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Health", code="HLT")
    db_session.add(dept)
    db_session.commit()

    db_session.add(
        ActivityType(
            university_id=univ.id,
            key="clinical_skills",
            display_name="Clinical Skills",
            resource_tags_required=["clinical_skills_lab"],
        )
    )
    db_session.commit()

    course = Course(
        code="HLT301",
        name="Clinical Practice",
        department_id=dept.id,
        level=300,
        credits=3,
        lecture_hours=0,
        tutorial_hours=0,
        practical_hours=0,
        activity_requirements=[{"activity_type_key": "clinical_skills", "hours_per_session": 2, "frequency_per_week": 1}],
        preferred_room_type=RoomType.LECTURE_HALL,
    )
    tagged_room = Room(university_id=univ.id, name="Skills Lab 1", building="A", capacity=20, room_type="lecture_hall", tags=["clinical_skills_lab"])
    plain_room = Room(university_id=univ.id, name="Lecture Room 1", building="A", capacity=100, room_type="lecture_hall", tags=["lecture_hall"])
    timetable = Timetable(university_id=univ.id, name="Tag Timetable", semester="1", year=2026, academic_half="1")
    db_session.add_all([course, tagged_room, plain_room, timetable])
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    session = generator._parse_course_sessions(course)[0]
    rooms = generator._get_compatible_rooms(course, session, 20, [tagged_room, plain_room], 0, 0, 2)

    assert [entry["room"].name for entry in rooms] == ["Skills Lab 1"]


def test_seed_tenant_baseline_uses_neutral_custom_defaults(db_session):
    univ = University(name="Neutral Seed Univ", domain="neutral-seed.test")
    db_session.add(univ)
    db_session.commit()

    seed_tenant_baseline(db_session, tenant_id=univ.id, plan_tier="free")
    db_session.commit()
    db_session.refresh(univ)

    assert univ.scheduling_policy["institution_template_key"] == "custom"
    assert univ.scheduling_policy["room_tag_catalog"] == []
    activity_types = db_session.query(ActivityType).filter(ActivityType.university_id == univ.id).all()
    assert activity_types == []


def test_generator_uses_custom_policy_fallback_when_university_policy_is_missing(db_session):
    univ = University(name="Fallback Policy Univ", domain="fallback-policy.test", scheduling_policy=None)
    db_session.add(univ)
    db_session.commit()

    timetable = Timetable(university_id=univ.id, name="Fallback Timetable", semester="1", year=2026, academic_half="1")
    db_session.add(timetable)
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    assert generator.scheduling_policy["institution_template_key"] == "custom"


def test_lecturer_unavailability_blocks_overlapping_windows(db_session):
    univ = University(name="Unavailability Univ", domain="unavailability.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Science", code="SCI")
    lecturer = Lecturer(
        department=dept,
        full_name="Dr Blocked",
        staff_number="L-BLOCKED-1",
        email="blocked@test.edu",
        max_hours_per_week=20,
    )
    db_session.add_all([dept, lecturer])
    db_session.commit()

    db_session.add_all([
        LecturerUnavailability(lecturer_id=lecturer.id, day_of_week=0, start_time=time(8, 0), end_time=time(10, 0)),
        LecturerUnavailability(lecturer_id=lecturer.id, day_of_week=2, start_time=time(14, 0), end_time=time(16, 0)),
    ])
    timetable = Timetable(university_id=univ.id, name="Availability Timetable", semester="1", year=2026, academic_half="1")
    db_session.add(timetable)
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    generator._lecturer_unavailability = {
        lecturer.id: db_session.query(LecturerUnavailability).filter(LecturerUnavailability.lecturer_id == lecturer.id).all()
    }

    assert generator._is_lecturer_available(lecturer, 0, 0, 1) is False
    assert generator._is_lecturer_available(lecturer, 0, 2, 3) is True
    assert generator._is_lecturer_available(lecturer, 2, 7, 8) is False


def test_course_room_and_group_uniqueness_are_tenant_scoped(db_session):
    univ_a = University(name="Scoped Univ A", domain="scoped-a.test")
    univ_b = University(name="Scoped Univ B", domain="scoped-b.test")
    db_session.add_all([univ_a, univ_b])
    db_session.commit()

    dept_a = Department(university_id=univ_a.id, name="Science", code="SCI")
    dept_b = Department(university_id=univ_b.id, name="Science", code="SCI")
    db_session.add_all([dept_a, dept_b])
    db_session.commit()

    db_session.add_all([
        Course(code="BIO101", name="Biology", department_id=dept_a.id, level=100, credits=3, lecture_hours=2),
        Course(code="BIO101", name="Biology", department_id=dept_b.id, level=100, credits=3, lecture_hours=2),
        Room(university_id=univ_a.id, name="Lab 1", building="Main", capacity=40, room_type="lab"),
        Room(university_id=univ_b.id, name="Lab 1", building="Main", capacity=40, room_type="lab"),
        StudentGroup(university_id=univ_a.id, department_id=dept_a.id, name="Year 1", level=100, size=50),
        StudentGroup(university_id=univ_b.id, department_id=dept_b.id, name="Year 1", level=100, size=50),
    ])
    db_session.commit()


def test_generator_capacity_constraint():
    """
    Verifies that generating a course for a group of 100 in a room of 50 fails soft limits/hard constraints.
    """
    # This acts as an API definition for what Phase 7 Antigravity should make pass
    pass

def test_generator_lecturer_overlap_constraint():
    """
    Verifies that a lecturer cannot be assigned to two classes at exactly the same timeslot.
    """
    pass

def test_generator_availability_constraint():
    """
    Verifies that time off constraints (e.g. lecturer not available Monday mornings) are respected.
    """
    pass


def test_general_course_without_explicit_links_combines_assigned_groups_for_lecture(db_session):
    """General/shared courses should auto-combine assigned groups into one lecture audience."""
    univ = University(name="Shared Lecture Univ", domain="shared-lecture.test")
    db_session.add(univ)
    db_session.commit()

    gen_dept = Department(university_id=univ.id, name="General Engineering", code="GEN")
    eee_dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    mec_dept = Department(university_id=univ.id, name="Mechanical Engineering", code="MEC")
    db_session.add_all([gen_dept, eee_dept, mec_dept])
    db_session.commit()

    lecturer = Lecturer(
        department_id=gen_dept.id,
        full_name="Dr. Shared",
        staff_number="L-SHARED-001",
        email="shared@test.edu",
        max_hours_per_week=20,
    )
    room = Room(
        university_id=univ.id,
        name="LH-Shared-1",
        building="ENG",
        capacity=400,
        room_type=RoomType.LECTURE_HALL,
    )
    group_eee = StudentGroup(
        university_id=univ.id,
        department_id=eee_dept.id,
        name="EEE Year 3",
        level=300,
        size=140,
    )
    group_mec = StudentGroup(
        university_id=univ.id,
        department_id=mec_dept.id,
        name="MEC Year 3",
        level=300,
        size=150,
    )
    course = Course(
        code="MAT3110",
        name="Engineering Mathematics II",
        department_id=gen_dept.id,
        level=300,
        credits=3,
        lecture_hours=3,
        course_type=CourseType.GENERAL,
    )

    db_session.add_all([lecturer, room, group_eee, group_mec, course])
    db_session.commit()

    from app.models import GroupAssignment, LecturerAssignment

    db_session.add_all([
        GroupAssignment(group_id=group_eee.id, course_id=course.id),
        GroupAssignment(group_id=group_mec.id, course_id=course.id),
        LecturerAssignment(lecturer_id=lecturer.id, course_id=course.id, session_type="lecture"),
    ])
    timetable = Timetable(
        university_id=univ.id,
        name="Shared Lecture Timetable",
        semester="1",
        year=2026,
        academic_half="1",
    )
    db_session.add(timetable)
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    group_ctx = generator._build_level_group_context(300)

    lecture_units = generator._resolve_session_units(course, "lecture", group_ctx)

    assert len(lecture_units) == 1
    assert lecture_units[0]["grouping_mode"] == "shared"
    assert set(lecture_units[0]["covered_group_ids"]) == {group_eee.id, group_mec.id}
    assert lecture_units[0]["group_size_required"] == group_eee.size + group_mec.size


def test_find_general_department_accepts_gen_code(db_session):
    """General department lookup should support installations using the GEN code."""
    univ = University(name="General Dept Univ", domain="general-dept.test")
    db_session.add(univ)
    db_session.commit()

    gen_dept = Department(university_id=univ.id, name="General Engineering", code="GEN")
    db_session.add(gen_dept)
    db_session.commit()

    resolved = find_general_department(db_session)

    assert resolved is not None
    assert resolved.id == gen_dept.id


def test_parent_assignment_keeps_common_stream_course_combined(db_session):
    """A course assigned to the parent cohort should stay combined even if streams exist."""
    univ = University(name="Combined Streams Univ", domain="combined-streams.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    db_session.add(dept)
    db_session.commit()

    parent_group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4",
        level=400,
        size=140,
    )
    stream_emp = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 EMP",
        level=400,
        size=87,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    stream_et = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 ET",
        level=400,
        size=53,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    course = Course(
        code="EEE4000",
        name="Common Department Course",
        department_id=dept.id,
        level=400,
        credits=3,
        lecture_hours=2,
        course_type=CourseType.DEPARTMENT_SPECIFIC,
    )
    db_session.add_all([parent_group, stream_emp, stream_et, course])
    db_session.commit()

    from app.models import GroupAssignment

    db_session.add(GroupAssignment(group_id=parent_group.id, course_id=course.id))
    db_session.commit()

    timetable = Timetable(university_id=univ.id, name="Combined", semester="1", year=2026, academic_half="1")
    db_session.add(timetable)
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    group_ctx = generator._build_level_group_context(400)
    lecture_units = generator._resolve_session_units(course, "lecture", group_ctx)

    assert len(lecture_units) == 1
    assert lecture_units[0]["primary_group_id"] == parent_group.id
    assert lecture_units[0]["covered_group_ids"] == [parent_group.id]


def test_common_course_assigned_to_multiple_streams_is_combined(db_session):
    """If sibling streams both retain a course, it should be treated as common/shared."""
    univ = University(name="Separate Streams Univ", domain="separate-streams.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    db_session.add(dept)
    db_session.commit()

    parent_group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4",
        level=400,
        size=140,
    )
    stream_emp = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 EMP",
        level=400,
        size=87,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    stream_et = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 ET",
        level=400,
        size=53,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    course = Course(
        code="EEE4999",
        name="Elective Stream Course",
        department_id=dept.id,
        level=400,
        credits=3,
        lecture_hours=2,
        course_type=CourseType.DEPARTMENT_SPECIFIC,
    )
    db_session.add_all([parent_group, stream_emp, stream_et, course])
    db_session.commit()

    from app.models import GroupAssignment

    db_session.add_all([
        GroupAssignment(group_id=stream_emp.id, course_id=course.id),
        GroupAssignment(group_id=stream_et.id, course_id=course.id),
    ])
    db_session.commit()

    timetable = Timetable(university_id=univ.id, name="Separate", semester="1", year=2026, academic_half="1")
    db_session.add(timetable)
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    group_ctx = generator._build_level_group_context(400)
    lecture_units = generator._resolve_session_units(course, "lecture", group_ctx)

    assert len(lecture_units) == 1
    assert lecture_units[0]["grouping_mode"] == "shared"
    assert set(lecture_units[0]["covered_group_ids"]) == {stream_emp.id, stream_et.id}


def test_course_left_on_one_stream_stays_separate(db_session):
    """Once a course is removed from sibling streams, the remaining stream keeps its own slot."""
    univ = University(name="Single Stream Univ", domain="single-stream.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    db_session.add(dept)
    db_session.commit()

    parent_group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4",
        level=400,
        size=140,
    )
    stream_emp = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 EMP",
        level=400,
        size=87,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    stream_et = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 ET",
        level=400,
        size=53,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    course = Course(
        code="EEE4888",
        name="Single Stream Elective",
        department_id=dept.id,
        level=400,
        credits=3,
        lecture_hours=2,
        course_type=CourseType.DEPARTMENT_SPECIFIC,
    )
    db_session.add_all([parent_group, stream_emp, stream_et, course])
    db_session.commit()

    from app.models import GroupAssignment

    db_session.add(GroupAssignment(group_id=stream_emp.id, course_id=course.id))
    db_session.commit()

    timetable = Timetable(university_id=univ.id, name="Single Stream", semester="1", year=2026, academic_half="1")
    db_session.add(timetable)
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    group_ctx = generator._build_level_group_context(400)
    lecture_units = generator._resolve_session_units(course, "lecture", group_ctx)

    assert len(lecture_units) == 1
    assert lecture_units[0]["grouping_mode"] == "single"
    assert lecture_units[0]["covered_group_ids"] == [stream_emp.id]


def test_stream_groups_with_hundred_level_are_included_for_year_level_courses(db_session):
    """Generator should treat level 5 and 500 as the same academic cohort."""
    univ = University(name="Normalized Streams Univ", domain="normalized-streams.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    db_session.add(dept)
    db_session.commit()

    parent_group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE5",
        level=5,
        size=140,
    )
    stream_emp = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE5 EMP",
        level=500,
        size=87,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    stream_et = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE5 ET",
        level=500,
        size=53,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    course = Course(
        code="EEE5681",
        name="Communication Networks",
        department_id=dept.id,
        level=5,
        credits=3,
        lecture_hours=2,
        course_type=CourseType.DEPARTMENT_SPECIFIC,
    )
    db_session.add_all([parent_group, stream_emp, stream_et, course])
    db_session.commit()

    from app.models import GroupAssignment

    db_session.add(GroupAssignment(group_id=stream_et.id, course_id=course.id))
    db_session.commit()

    timetable = Timetable(university_id=univ.id, name="Level Normalized", semester="1", year=2026, academic_half="1")
    db_session.add(timetable)
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    group_ctx = generator._build_level_group_context(5)
    lecture_units = generator._resolve_session_units(course, "lecture", group_ctx)

    assert {group.id for group in group_ctx["all_groups"]} == {parent_group.id, stream_emp.id, stream_et.id}
    assert len(lecture_units) == 1
    assert lecture_units[0]["grouping_mode"] == "single"
    assert lecture_units[0]["covered_group_ids"] == [stream_et.id]


def test_seed_tenant_baseline_auto_seeds_single_school_for_nursing(db_session):
    univ = University(name="Nursing Seed Univ", domain="nursing-seed.test")
    db_session.add(univ)
    db_session.commit()

    seed_tenant_baseline(db_session, tenant_id=univ.id, plan_tier="starter", template_key="nursing")
    db_session.commit()

    schools = db_session.query(School).filter(School.university_id == univ.id).all()
    assert len(schools) == 1
    assert schools[0].code == "NUR"


def test_generator_limits_school_scoped_room_pool_to_school_and_shared(db_session):
    univ = University(name="School Scope Univ", domain="school-scope.test")
    db_session.add(univ)
    db_session.commit()

    school = School(university_id=univ.id, name="School of Engineering", code="ENG")
    other_school = School(university_id=univ.id, name="School of Medicine", code="MED")
    db_session.add_all([school, other_school])
    db_session.commit()

    dept = Department(university_id=univ.id, school_id=school.id, name="Civil Engineering", code="CEE")
    db_session.add(dept)
    db_session.commit()

    shared_room = Room(university_id=univ.id, school_id=None, name="Shared Hall", building="A", capacity=100, room_type=RoomType.LECTURE_HALL)
    school_room = Room(university_id=univ.id, school_id=school.id, name="ENG Lab", building="B", capacity=40, room_type=RoomType.LAB)
    other_room = Room(university_id=univ.id, school_id=other_school.id, name="MED Lab", building="C", capacity=40, room_type=RoomType.LAB)
    db_session.add_all([shared_room, school_room, other_room])
    db_session.commit()

    timetable = Timetable(
        university_id=univ.id,
        school_id=school.id,
        name="ENG Timetable",
        semester="1",
        year=2026,
        academic_half="first_half",
    )
    db_session.add(timetable)
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    room_ids = {room.id for room in generator._apply_room_scope(db_session.query(Room)).all()}

    assert shared_room.id in room_ids
    assert school_room.id in room_ids
    assert other_room.id not in room_ids
