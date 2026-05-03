from datetime import time

import pytest
from fastapi import HTTPException

from app.models import Course, Department, Room, RoomType, StudentGroup, Timetable, University
from app.routers.timetables import _raise_validation_errors
from app.services.validation_service import ValidationService


def test_validate_room_assignment_allows_largest_room_overflow_fallback(db_session):
    univ = University(name="Room Mapping Univ", domain="room-mapping.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE-RMV")
    db_session.add(dept)
    db_session.commit()

    course = Course(
        code="EEE4501",
        name="Signals",
        department_id=dept.id,
        level=400,
        credits=3,
        lecture_hours=2,
        preferred_room_type=RoomType.LECTURE_HALL,
    )
    room = Room(
        university_id=univ.id,
        name="LH-1",
        building="Main",
        capacity=100,
        room_type="lecture_hall",
    )
    group_a = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE 4A",
        level=400,
        size=60,
    )
    group_b = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE 4B",
        level=400,
        size=55,
    )
    db_session.add_all([course, room, group_a, group_b])
    db_session.commit()

    validator = ValidationService(db_session)
    is_valid = validator.validate_room_assignment(
        room.id,
        course_id=course.id,
        primary_group_id=group_a.id,
        shared_group_ids=[group_b.id],
        session_type="lecture",
    )

    assert is_valid is True
    assert any(
        error.severity == "warning" and "largest compatible fallback room available" in error.message
        for error in validator.errors
    )


def test_validate_room_assignment_rejects_smaller_room_when_larger_one_exists(db_session):
    univ = University(name="Room Ranking Univ", domain="room-ranking.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE-RRK")
    db_session.add(dept)
    db_session.commit()

    course = Course(
        code="EEE4509",
        name="Networks",
        department_id=dept.id,
        level=400,
        credits=3,
        lecture_hours=2,
        preferred_room_type=RoomType.LECTURE_HALL,
    )
    smaller_room = Room(
        university_id=univ.id,
        name="LH-100",
        building="Main",
        capacity=100,
        room_type="lecture_hall",
    )
    larger_room = Room(
        university_id=univ.id,
        name="LH-300",
        building="Main",
        capacity=300,
        room_type="lecture_hall",
    )
    group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE 4",
        level=400,
        size=650,
    )
    db_session.add_all([course, smaller_room, larger_room, group])
    db_session.commit()

    validator = ValidationService(db_session)
    is_valid = validator.validate_room_assignment(
        smaller_room.id,
        course_id=course.id,
        primary_group_id=group.id,
        session_type="lecture",
    )

    assert is_valid is False
    assert any(error.severity == "error" and "300 seats" in error.message for error in validator.errors)


def test_validate_room_assignment_rejects_absurdly_small_overflow_fallback(db_session):
    univ = University(name="Fallback Threshold Univ", domain="fallback-threshold.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE-FTH")
    db_session.add(dept)
    db_session.commit()

    course = Course(
        code="EEE4510",
        name="Power Systems",
        department_id=dept.id,
        level=400,
        credits=3,
        lecture_hours=2,
        preferred_room_type=RoomType.LECTURE_HALL,
    )
    tiny_room = Room(
        university_id=univ.id,
        name="LH-50",
        building="Main",
        capacity=50,
        room_type="lecture_hall",
    )
    fallback_room = Room(
        university_id=univ.id,
        name="LH-350",
        building="Main",
        capacity=350,
        room_type="lecture_hall",
    )
    group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE 4 Mega",
        level=400,
        size=650,
    )
    db_session.add_all([course, tiny_room, fallback_room, group])
    db_session.commit()

    validator = ValidationService(db_session)
    is_valid = validator.validate_room_assignment(
        tiny_room.id,
        course_id=course.id,
        primary_group_id=group.id,
        session_type="lecture",
    )

    assert is_valid is False
    assert any(error.field == "capacity_threshold" and "at least 325 students" in error.message for error in validator.errors)


def test_validate_room_assignment_rejects_incompatible_room_type(db_session):
    univ = University(name="Room Type Univ", domain="room-type.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Mechanical Engineering", code="MEC-RTV")
    db_session.add(dept)
    db_session.commit()

    course = Course(
        code="MEC4502",
        name="Thermo Lab",
        department_id=dept.id,
        level=400,
        credits=3,
        lecture_hours=1,
        practical_hours=2,
        preferred_room_type=RoomType.LAB,
    )
    room = Room(
        university_id=univ.id,
        name="SR-1",
        building="North",
        capacity=40,
        room_type="seminar_room",
    )
    group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="MEC 4",
        level=400,
        size=30,
    )
    db_session.add_all([course, room, group])
    db_session.commit()

    validator = ValidationService(db_session)
    is_valid = validator.validate_room_assignment(
        room.id,
        course_id=course.id,
        primary_group_id=group.id,
        session_type="practical",
    )

    assert is_valid is False
    assert any(error.field == "room_type" for error in validator.errors)


def test_validate_room_assignment_allows_small_lecture_in_seminar_room_when_no_lecture_room_exists(db_session):
    univ = University(name="Seminar Fallback Univ", domain="seminar-fallback.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Business", code="BUS-SFU")
    db_session.add(dept)
    db_session.commit()

    course = Course(
        code="BUS2101",
        name="Business Communication",
        department_id=dept.id,
        level=200,
        credits=3,
        lecture_hours=2,
        preferred_room_type=RoomType.LECTURE_HALL,
    )
    seminar_room = Room(
        university_id=univ.id,
        name="Seminar A",
        building="Admin",
        capacity=45,
        room_type="seminar_room",
    )
    group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="BUS 2A",
        level=200,
        size=35,
    )
    db_session.add_all([course, seminar_room, group])
    db_session.commit()

    validator = ValidationService(db_session)
    is_valid = validator.validate_room_assignment(
        seminar_room.id,
        course_id=course.id,
        primary_group_id=group.id,
        session_type="lecture",
    )

    assert is_valid is True
    assert any(error.field == "room_type_fallback" and error.severity == "warning" for error in validator.errors)


def test_validate_room_assignment_rejects_fallback_room_when_better_match_exists(db_session):
    univ = University(name="Room Match Univ", domain="room-match.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Business", code="BUS-RMU")
    db_session.add(dept)
    db_session.commit()

    course = Course(
        code="BUS2102",
        name="Marketing Principles",
        department_id=dept.id,
        level=200,
        credits=3,
        lecture_hours=2,
        preferred_room_type=RoomType.LECTURE_HALL,
    )
    lecture_room = Room(
        university_id=univ.id,
        name="Lecture B",
        building="Main",
        capacity=80,
        room_type="lecture_hall",
    )
    seminar_room = Room(
        university_id=univ.id,
        name="Seminar B",
        building="Admin",
        capacity=50,
        room_type="seminar_room",
    )
    group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="BUS 2B",
        level=200,
        size=35,
    )
    db_session.add_all([course, lecture_room, seminar_room, group])
    db_session.commit()

    validator = ValidationService(db_session)
    is_valid = validator.validate_room_assignment(
        seminar_room.id,
        course_id=course.id,
        primary_group_id=group.id,
        session_type="lecture",
    )

    assert is_valid is False
    assert any(error.field == "room_type" and "better-matched room type" in error.message for error in validator.errors)


def test_validate_timetable_slot_accepts_day_of_week_and_reports_warnings(db_session):
    univ = University(name="Slot Day Univ", domain="slot-day.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Civil Engineering", code="CEE-SDV")
    db_session.add(dept)
    db_session.commit()

    timetable = Timetable(name="Main TT", university_id=univ.id, semester="1", year=2026)
    course = Course(
        code="CEE4503",
        name="Structures",
        department_id=dept.id,
        level=400,
        credits=3,
        lecture_hours=2,
        preferred_room_type=RoomType.LECTURE_HALL,
    )
    room = Room(
        university_id=univ.id,
        name="LH-2",
        building="South",
        capacity=150,
        room_type="lecture_hall",
    )
    group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="CEE 4",
        level=400,
        size=40,
    )
    db_session.add_all([timetable, course, room, group])
    db_session.commit()

    validator = ValidationService(db_session)
    is_valid, errors = validator.validate_timetable_slot(
        {
            "course_id": course.id,
            "room_id": room.id,
            "group_id": group.id,
            "day_of_week": 0,
            "start_time": time(8, 0),
            "end_time": time(10, 0),
            "session_type": "lecture",
        },
        timetable.id,
    )

    assert is_valid is True
    assert any(error["severity"] == "warning" for error in errors)


def test_validate_timetable_slot_allows_practical_without_room(db_session):
    univ = University(name="Practical Null Room Univ", domain="practical-null-room.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Mechanical Engineering", code="MEC-PNR")
    db_session.add(dept)
    db_session.commit()

    timetable = Timetable(name="Main TT", university_id=univ.id, semester="1", year=2026)
    course = Course(
        code="MEC3201",
        name="Mechanics Lab",
        department_id=dept.id,
        level=300,
        credits=3,
        lecture_hours=1,
        practical_hours=2,
        preferred_room_type=RoomType.LAB,
    )
    group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="MEC 3",
        level=300,
        size=28,
    )
    db_session.add_all([timetable, course, group])
    db_session.commit()

    validator = ValidationService(db_session)
    is_valid, errors = validator.validate_timetable_slot(
        {
            "course_id": course.id,
            "room_id": None,
            "group_id": group.id,
            "day_of_week": 2,
            "start_time": time(10, 0),
            "end_time": time(12, 0),
            "session_type": "practical",
        },
        timetable.id,
    )

    assert is_valid is True
    assert any(error["severity"] == "info" and "without a room" in error["message"] for error in errors)


def test_validate_timetable_slot_rejects_lecture_without_room(db_session):
    univ = University(name="Lecture Room Required Univ", domain="lecture-room-required.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE-LRR")
    db_session.add(dept)
    db_session.commit()

    timetable = Timetable(name="Main TT", university_id=univ.id, semester="1", year=2026)
    course = Course(
        code="EEE2201",
        name="Circuits",
        department_id=dept.id,
        level=200,
        credits=3,
        lecture_hours=2,
        preferred_room_type=RoomType.LECTURE_HALL,
    )
    group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE 2",
        level=200,
        size=48,
    )
    db_session.add_all([timetable, course, group])
    db_session.commit()

    validator = ValidationService(db_session)
    is_valid, errors = validator.validate_timetable_slot(
        {
            "course_id": course.id,
            "room_id": None,
            "group_id": group.id,
            "day_of_week": 1,
            "start_time": time(9, 0),
            "end_time": time(11, 0),
            "session_type": "lecture",
        },
        timetable.id,
    )

    assert is_valid is False
    assert any(error["field"] == "room_id" and error["severity"] == "error" for error in errors)


def test_raise_validation_errors_blocks_on_error():
    with pytest.raises(HTTPException) as excinfo:
        _raise_validation_errors(
            [
                {"severity": "warning", "message": "warning"},
                {"severity": "error", "message": "boom"},
            ]
        )

    assert excinfo.value.status_code == 422
