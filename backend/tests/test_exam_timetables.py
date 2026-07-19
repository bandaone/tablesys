from datetime import date

import pytest
from httpx import AsyncClient

from app.auth import get_password_hash
from app.models import Course, Department, Room, StudentGroup, University, User, UserRole


def _seed_exam_generation_data(db_session):
    general_department = db_session.query(Department).filter(Department.code == "GEN").first()
    if not general_department:
        general_department = Department(name="General Studies", code="GEN", university_id=1)
        db_session.add(general_department)
        db_session.flush()

    course = Course(
        code="CSC4010",
        name="Distributed Systems",
        department_id=general_department.id,
        level=4,
        credits=3,
        lecture_hours=3,
        tutorial_hours=0,
        practical_hours=0,
        preferred_room_type="lecture_hall",
    )
    db_session.add(course)
    db_session.flush()

    group_a = StudentGroup(
        university_id=1,
        name="CSC 4A EXAM",
        level=4,
        department_id=general_department.id,
        size=120,
    )
    group_b = StudentGroup(
        university_id=1,
        name="CSC 4B EXAM",
        level=4,
        department_id=general_department.id,
        size=80,
    )
    db_session.add_all([group_a, group_b])
    db_session.flush()

    rooms = [
        Room(
            university_id=1,
            name="LH-401",
            building="Main Campus",
            capacity=130,
            room_type="lecture_hall",
            is_blocked=False,
            priority_level=10,
        ),
        Room(
            university_id=1,
            name="LH-402",
            building="Main Campus",
            capacity=110,
            room_type="lecture_hall",
            is_blocked=False,
            priority_level=9,
        ),
        Room(
            university_id=1,
            name="LH-403",
            building="Main Campus",
            capacity=60,
            room_type="lecture_hall",
            is_blocked=False,
            priority_level=8,
        ),
    ]
    db_session.add_all(rooms)
    db_session.commit()

    return {
        "course_id": course.id,
        "group_ids": [group_a.id, group_b.id],
        "room_names": [room.name for room in rooms],
    }


async def _login(async_client: AsyncClient, username: str, password: str = "pass") -> dict:
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_exam_generation_supports_multi_room_allocations(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    seeded = _seed_exam_generation_data(db_session)

    period_response = await async_client.post(
        "/api/v1/exam-timetables/periods",
        headers=auth_headers,
        json={
            "name": "Semester 1 Main Exams",
            "semester": "Semester 1",
            "year": 2026,
            "start_date": "2026-06-01",
            "end_date": "2026-06-10",
            "constraint_settings": {
                "preferred_max_papers_per_day": 1,
                "hard_max_papers_per_day": 2,
                "min_gap_hours": 12,
                "allow_same_day_multiple_papers": True,
            },
        },
    )
    assert period_response.status_code == 201, period_response.text
    period_id = period_response.json()["id"]

    profile_response = await async_client.post(
        "/api/v1/exam-timetables/seating-profiles",
        headers=auth_headers,
        json={
            "name": "Spaced Seating",
            "description": "Every other seat used",
            "capacity_factor": 75,
            "is_default": True,
        },
    )
    assert profile_response.status_code == 201, profile_response.text
    profile_id = profile_response.json()["id"]

    morning_window_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/session-windows",
        headers=auth_headers,
        json={
            "name": "Morning",
            "start_time": "08:00:00",
            "end_time": "12:00:00",
            "display_order": 1,
            "allow_weekends": False,
            "is_active": True,
        },
    )
    assert morning_window_response.status_code == 201, morning_window_response.text

    paper_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/papers",
        headers=auth_headers,
        json={
            "paper_code": "CSC4010-MAIN",
            "paper_name": "Distributed Systems Final",
            "course_id": seeded["course_id"],
            "duration_minutes": 180,
            "candidate_count": 200,
            "group_ids": seeded["group_ids"],
            "preferred_room_type": "lecture_hall",
            "preferred_seating_profile_id": profile_id,
            "max_rooms": 3,
        },
    )
    assert paper_response.status_code == 201, paper_response.text

    generate_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/generate",
        headers=auth_headers,
        json={"replace_existing": True},
    )
    assert generate_response.status_code == 200, generate_response.text
    generated_payload = generate_response.json()
    assert generated_payload["scheduled_count"] == 1
    assert generated_payload["unscheduled_count"] == 0
    assert generated_payload["diagnostics_summary"]["multi_room_allocations"] >= 1
    assert generated_payload["diagnostics_summary"]["scheduled_with_flags"] >= 1

    slots_response = await async_client.get(
        f"/api/v1/exam-timetables/periods/{period_id}/slots",
        headers=auth_headers,
    )
    assert slots_response.status_code == 200, slots_response.text
    slots = slots_response.json()
    assert len(slots) == 1
    slot = slots[0]
    assert slot["total_allocated_capacity"] >= 200
    assert len(slot["room_allocations"]) >= 2

    allocated_room_names = {
        allocation["room"]["name"]
        for allocation in slot["room_allocations"]
        if allocation.get("room")
    }
    assert allocated_room_names.issubset(set(seeded["room_names"]))
    assert slot["notes"] is not None

    period_detail_response = await async_client.get(
        f"/api/v1/exam-timetables/periods/{period_id}",
        headers=auth_headers,
    )
    assert period_detail_response.status_code == 200, period_detail_response.text
    generation_metadata = period_detail_response.json()["generation_metadata"]
    assert generation_metadata["diagnostics_summary"]["multi_room_allocations"] >= 1
    assert generation_metadata["scheduled_flags"][0]["paper_code"] == "CSC4010-MAIN"


@pytest.mark.asyncio
async def test_exam_publish_locks_period_and_marks_slots_published(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    seeded = _seed_exam_generation_data(db_session)

    period_response = await async_client.post(
        "/api/v1/exam-timetables/periods",
        headers=auth_headers,
        json={
            "name": "Semester 2 Main Exams",
            "semester": "Semester 2",
            "year": 2026,
            "start_date": "2026-11-01",
            "end_date": "2026-11-15",
        },
    )
    assert period_response.status_code == 201, period_response.text
    period_id = period_response.json()["id"]

    await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/session-windows",
        headers=auth_headers,
        json={
            "name": "Afternoon",
            "start_time": "14:00:00",
            "end_time": "17:00:00",
            "display_order": 2,
        },
    )

    profile_response = await async_client.post(
        "/api/v1/exam-timetables/seating-profiles",
        headers=auth_headers,
        json={"name": "Standard Seating", "capacity_factor": 100},
    )
    profile_id = profile_response.json()["id"]

    paper_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/papers",
        headers=auth_headers,
        json={
            "paper_code": "CSC4010-ALT",
            "paper_name": "Distributed Systems Supplementary",
            "course_id": seeded["course_id"],
            "duration_minutes": 120,
            "candidate_count": 100,
            "group_ids": [seeded["group_ids"][0]],
            "preferred_room_type": "lecture_hall",
            "preferred_seating_profile_id": profile_id,
            "max_rooms": 1,
        },
    )
    assert paper_response.status_code == 201, paper_response.text

    generate_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/generate",
        headers=auth_headers,
        json={"replace_existing": True},
    )
    assert generate_response.status_code == 200, generate_response.text

    publish_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/publish",
        headers=auth_headers,
        json={"lock_after_publish": True},
    )
    assert publish_response.status_code == 200, publish_response.text
    published = publish_response.json()
    assert published["is_published"] is True
    assert published["is_locked"] is True
    assert published["published_at"] is not None

    slots_response = await async_client.get(
        f"/api/v1/exam-timetables/periods/{period_id}/slots",
        headers=auth_headers,
    )
    slots = slots_response.json()
    assert slots
    assert all(slot["status"] == "published" for slot in slots)

    locked_update_response = await async_client.put(
        f"/api/v1/exam-timetables/periods/{period_id}",
        headers=auth_headers,
        json={"name": "Edited After Publish"},
    )
    assert locked_update_response.status_code == 409


@pytest.mark.asyncio
async def test_exam_periods_are_scoped_to_the_current_university(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    seeded = _seed_exam_generation_data(db_session)

    period_response = await async_client.post(
        "/api/v1/exam-timetables/periods",
        headers=auth_headers,
        json={
            "name": "Tenant 1 Protected Period",
            "semester": "Semester 1",
            "year": 2026,
            "start_date": "2026-07-01",
            "end_date": "2026-07-05",
        },
    )
    assert period_response.status_code == 201, period_response.text
    period_id = period_response.json()["id"]

    tenant_two = db_session.query(University).filter(University.id == 2).first()
    if tenant_two is None:
        tenant_two = University(
            id=2,
            name="Tenant Two University",
            short_name="T2U",
            domain="tenant2.test.local",
            timezone="Africa/Harare",
            is_active=True,
            plan_tier="free",
            max_users=50,
        )
        db_session.add(tenant_two)
        db_session.flush()

    tenant_two_user = db_session.query(User).filter(User.username == "exam_coord_u2").first()
    if tenant_two_user is None:
        tenant_two_user = User(
            username="exam_coord_u2",
            email="exam_coord_u2@tenant2.test.local",
            full_name="Exam Coordinator U2",
            role=UserRole.COORDINATOR,
            hashed_password=get_password_hash("pass"),
            is_active=True,
            university_id=tenant_two.id,
        )
        db_session.add(tenant_two_user)
        db_session.flush()

    db_session.commit()

    tenant_two_headers = await _login(async_client, "exam_coord_u2")

    list_response = await async_client.get(
        "/api/v1/exam-timetables/periods",
        headers=tenant_two_headers,
    )
    assert list_response.status_code == 200, list_response.text
    assert all(period["id"] != period_id for period in list_response.json())

    detail_response = await async_client.get(
        f"/api/v1/exam-timetables/periods/{period_id}",
        headers=tenant_two_headers,
    )
    assert detail_response.status_code == 404, detail_response.text

    delete_response = await async_client.delete(
        f"/api/v1/exam-timetables/periods/{period_id}",
        headers=tenant_two_headers,
    )
    assert delete_response.status_code == 404, delete_response.text


@pytest.mark.asyncio
async def test_publish_rejects_periods_with_unscheduled_papers(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    seeded = _seed_exam_generation_data(db_session)

    period_response = await async_client.post(
        "/api/v1/exam-timetables/periods",
        headers=auth_headers,
        json={
            "name": "Semester 1 Mixed Feasibility Exams",
            "semester": "Semester 1",
            "year": 2026,
            "start_date": "2026-08-01",
            "end_date": "2026-08-03",
        },
    )
    assert period_response.status_code == 201, period_response.text
    period_id = period_response.json()["id"]

    window_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/session-windows",
        headers=auth_headers,
        json={
            "name": "Morning",
            "start_time": "08:00:00",
            "end_time": "12:00:00",
            "display_order": 1,
        },
    )
    assert window_response.status_code == 201, window_response.text

    profile_response = await async_client.post(
        "/api/v1/exam-timetables/seating-profiles",
        headers=auth_headers,
        json={"name": "Standard Seating", "capacity_factor": 100, "is_default": True},
    )
    assert profile_response.status_code == 201, profile_response.text
    profile_id = profile_response.json()["id"]

    schedulable_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/papers",
        headers=auth_headers,
        json={
            "paper_code": "CSC4010-OK",
            "paper_name": "Distributed Systems Main",
            "course_id": seeded["course_id"],
            "duration_minutes": 180,
            "candidate_count": 110,
            "group_ids": [seeded["group_ids"][0]],
            "preferred_room_type": "lecture_hall",
            "preferred_seating_profile_id": profile_id,
            "max_rooms": 1,
        },
    )
    assert schedulable_response.status_code == 201, schedulable_response.text

    unschedulable_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/papers",
        headers=auth_headers,
        json={
            "paper_code": "CSC4010-BLOCKED",
            "paper_name": "Distributed Systems Overflow",
            "course_id": seeded["course_id"],
            "duration_minutes": 180,
            "candidate_count": 500,
            "group_ids": [seeded["group_ids"][1]],
            "preferred_room_type": "lecture_hall",
            "preferred_seating_profile_id": profile_id,
            "max_rooms": 1,
        },
    )
    assert unschedulable_response.status_code == 201, unschedulable_response.text

    generate_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/generate",
        headers=auth_headers,
        json={"replace_existing": True},
    )
    assert generate_response.status_code == 200, generate_response.text
    payload = generate_response.json()
    assert payload["scheduled_count"] == 1
    assert payload["unscheduled_count"] == 1

    publish_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/publish",
        headers=auth_headers,
        json={"lock_after_publish": True},
    )
    assert publish_response.status_code == 422, publish_response.text
    assert "Resolve all unscheduled papers" in publish_response.text


@pytest.mark.asyncio
async def test_published_period_cannot_be_deleted_or_mutated_via_status_fields(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    seeded = _seed_exam_generation_data(db_session)

    period_response = await async_client.post(
        "/api/v1/exam-timetables/periods",
        headers=auth_headers,
        json={
            "name": "Protected Published Exams",
            "semester": "Semester 2",
            "year": 2026,
            "start_date": "2026-10-01",
            "end_date": "2026-10-07",
        },
    )
    assert period_response.status_code == 201, period_response.text
    period_id = period_response.json()["id"]

    await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/session-windows",
        headers=auth_headers,
        json={
            "name": "Morning",
            "start_time": "08:00:00",
            "end_time": "12:00:00",
            "display_order": 1,
        },
    )

    profile_response = await async_client.post(
        "/api/v1/exam-timetables/seating-profiles",
        headers=auth_headers,
        json={"name": "Delete Guard Profile", "capacity_factor": 100},
    )
    profile_id = profile_response.json()["id"]

    await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/papers",
        headers=auth_headers,
        json={
            "paper_code": "CSC4010-FINAL",
            "paper_name": "Distributed Systems Final",
            "course_id": seeded["course_id"],
            "duration_minutes": 120,
            "candidate_count": 100,
            "group_ids": [seeded["group_ids"][0]],
            "preferred_room_type": "lecture_hall",
            "preferred_seating_profile_id": profile_id,
            "max_rooms": 1,
        },
    )

    generate_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/generate",
        headers=auth_headers,
        json={"replace_existing": True},
    )
    assert generate_response.status_code == 200, generate_response.text

    publish_response = await async_client.post(
        f"/api/v1/exam-timetables/periods/{period_id}/publish",
        headers=auth_headers,
        json={"lock_after_publish": True},
    )
    assert publish_response.status_code == 200, publish_response.text

    delete_response = await async_client.delete(
        f"/api/v1/exam-timetables/periods/{period_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 409, delete_response.text

    invalid_update_response = await async_client.put(
        f"/api/v1/exam-timetables/periods/{period_id}",
        headers=auth_headers,
        json={"is_published": False},
    )
    assert invalid_update_response.status_code == 422, invalid_update_response.text
