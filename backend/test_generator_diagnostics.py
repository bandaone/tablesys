import os
import sys
from datetime import time
from types import SimpleNamespace

sys.path.append(os.getcwd())

from app.models import RoomType
from app.services.timetable_generator import TimetableGenerator


def make_generator():
    gen = object.__new__(TimetableGenerator)
    gen.start_hour = 7
    gen.days = ["Monday", "Tuesday"]
    gen.num_slots = 2
    gen.time_slots = [(time(7 + i, 0), time(8 + i, 0)) for i in range(gen.num_slots)]
    gen.all_slots = []
    gen.existing_slots = []
    gen.generation_diagnostics = []
    gen.solver_status_by_level = {}
    gen.fallback_levels = []
    gen.saved_slot_annotations = []
    gen.requested_components = None
    gen.components = None
    return gen


def test_normalize_shared_group_ids():
    gen = make_generator()
    assert gen._normalize_shared_group_ids(None) == []
    assert gen._normalize_shared_group_ids([2, "3"]) == [2, 3]
    assert gen._normalize_shared_group_ids("[4, 5]") == [4, 5]


def test_zero_candidate_due_to_missing_rooms():
    gen = make_generator()
    course = SimpleNamespace(id=1, code="TEST101", preferred_room_type=RoomType.LECTURE_HALL)
    result = gen._diagnose_zero_candidate_session(
        level=2,
        course=course,
        session_type="lecture",
        duration=1,
        primary_group_id=10,
        covered_group_ids=[10],
        group_size_required=40,
        all_rooms=[],
        lecturer_ids=[None],
    )
    assert result["reason_code"] == "no_rooms_defined"


def test_zero_candidate_due_to_existing_group_block():
    gen = make_generator()
    gen.existing_slots = [
        {
            "course_id": 99,
            "lecturer_id": 7,
            "room_id": 1,
            "group_id": 10,
            "day_of_week": 0,
            "start_time": time(7, 0),
            "end_time": time(8, 0),
            "session_type": "lecture",
            "shared_group_ids": None,
        },
        {
            "course_id": 98,
            "lecturer_id": 7,
            "room_id": 1,
            "group_id": 10,
            "day_of_week": 0,
            "start_time": time(8, 0),
            "end_time": time(9, 0),
            "session_type": "lecture",
            "shared_group_ids": None,
        },
        {
            "course_id": 97,
            "lecturer_id": 7,
            "room_id": 1,
            "group_id": 10,
            "day_of_week": 1,
            "start_time": time(7, 0),
            "end_time": time(8, 0),
            "session_type": "lecture",
            "shared_group_ids": None,
        },
        {
            "course_id": 96,
            "lecturer_id": 7,
            "room_id": 1,
            "group_id": 10,
            "day_of_week": 1,
            "start_time": time(8, 0),
            "end_time": time(9, 0),
            "session_type": "lecture",
            "shared_group_ids": None,
        },
    ]
    course = SimpleNamespace(id=1, code="TEST101", preferred_room_type=RoomType.LECTURE_HALL)
    room = SimpleNamespace(id=1, room_type="lecture_hall", capacity=60, availability_blocks=[])
    result = gen._diagnose_zero_candidate_session(
        level=2,
        course=course,
        session_type="lecture",
        duration=1,
        primary_group_id=10,
        covered_group_ids=[10],
        group_size_required=40,
        all_rooms=[room],
        lecturer_ids=[None],
    )
    assert result["reason_code"] == "group_blocked_by_existing_slots"


def test_parse_course_sessions_uses_explicit_operational_defaults():
    gen = make_generator()
    course = SimpleNamespace(
        id=1,
        lecture_hours=2,
        tutorial_hours=1,
        practical_hours=3,
        session_configuration=None,
    )
    sessions = gen._parse_course_sessions(course)
    assert [s["type"] for s in sessions] == ["lecture", "lecture", "tutorial", "practical"]
    assert [s["duration"] for s in sessions] == [2, 2, 1, 3]


def test_parse_course_sessions_respects_component_filter():
    gen = make_generator()
    gen.components = ["lecture"]
    course = SimpleNamespace(
        id=1,
        lecture_hours=2,
        tutorial_hours=2,
        practical_hours=2,
        session_configuration=None,
    )
    sessions = gen._parse_course_sessions(course)
    assert [s["type"] for s in sessions] == ["lecture", "lecture"]
    assert [s["duration"] for s in sessions] == [2, 2]


def test_component_sequence_defaults_to_layered_generation():
    gen = make_generator()
    assert gen._component_sequence() == ["lecture", "practical", "tutorial"]


def test_rotation_groups_block_group_conflicts():
    gen = make_generator()
    gen.existing_slots = [
        {
            "course_id": 50,
            "lecturer_id": 2,
            "room_id": 1,
            "group_id": 11,
            "day_of_week": 0,
            "start_time": time(7, 0),
            "end_time": time(8, 0),
            "session_type": "practical",
            "shared_group_ids": None,
            "rotation_group_ids": [12, 13],
        }
    ]
    assert gen._resource_blocked("group", 12, 0, 0, 1) is True


if __name__ == "__main__":
    test_normalize_shared_group_ids()
    test_zero_candidate_due_to_missing_rooms()
    test_zero_candidate_due_to_existing_group_block()
    test_parse_course_sessions_uses_explicit_operational_defaults()
    test_parse_course_sessions_respects_component_filter()
    test_component_sequence_defaults_to_layered_generation()
    test_rotation_groups_block_group_conflicts()
    print("test_generator_diagnostics.py: PASS")
