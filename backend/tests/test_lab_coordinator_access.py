from datetime import time

import pytest
from httpx import AsyncClient

from app.models import Course, Department, GroupType, LabSession, StudentGroup, Timetable, TimetableSlot, University


@pytest.mark.auth
@pytest.mark.asyncio
async def test_lab_coordinator_can_manage_lab_workflow(
    async_client: AsyncClient,
    db_session,
    lab_headers: dict,
):
    department = db_session.query(Department).filter(Department.code == "CEE").first()
    assert department is not None

    parent_group = StudentGroup(
        university_id=1,
        name="CEE Year 2",
        level=200,
        department_id=department.id,
        size=120,
        group_type=GroupType.DEPARTMENT,
    )
    db_session.add(parent_group)
    db_session.commit()
    db_session.refresh(parent_group)

    activity_response = await async_client.post(
        "/api/v1/activity-types/",
        headers=lab_headers,
        json={
            "key": "lab_tutorial",
            "display_name": "Lab Tutorial",
            "color": "#16A34A",
            "default_duration_periods": 1,
            "default_frequency_per_week": 2,
            "requires_subgroups": True,
            "resource_tags_required": ["tutorial_room"],
            "counts_toward_contact_hours": True,
            "is_active": True,
        },
    )
    assert activity_response.status_code == 201

    subgroup_response = await async_client.post(
        f"/api/v1/groups/{parent_group.id}/subgroups/bulk",
        headers=lab_headers,
        json={
            "count": 2,
            "size_per_group": 12,
            "naming_mode": "alpha",
            "group_type": "tutorial_group",
            "prefix": "T",
        },
    )
    assert subgroup_response.status_code == 201
    assert len(subgroup_response.json()) == 2

    timetable_response = await async_client.post(
        "/api/v1/timetables/",
        headers=lab_headers,
        json={
            "name": "Lab Timetable",
            "semester": "Semester 1",
            "year": 2026,
            "academic_half": "first_half",
            "school_id": None,
            "grid_config": {
                "start_time": "07:00",
                "end_time": "17:00",
                "lunch_start": "13:00",
                "lunch_end": "14:00",
                "slot_duration_minutes": 60,
            },
        },
    )
    assert timetable_response.status_code == 201


@pytest.mark.auth
@pytest.mark.asyncio
async def test_lab_session_creation_builds_master_rotation_schedule(
    async_client: AsyncClient,
    db_session,
    lab_headers: dict,
):
    department = db_session.query(Department).filter(Department.code == "CEE").first()
    assert department is not None

    parent_group = StudentGroup(
        university_id=1,
        name="CEE Year 5",
        level=500,
        department_id=department.id,
        size=120,
        group_type=GroupType.DEPARTMENT,
    )
    db_session.add(parent_group)
    db_session.commit()
    db_session.refresh(parent_group)

    subgroup_a = StudentGroup(
        university_id=1,
        name="CEE Year 5 - A",
        level=500,
        department_id=department.id,
        size=30,
        group_type=GroupType.LAB_GROUP,
        parent_group_id=parent_group.id,
    )
    subgroup_b = StudentGroup(
        university_id=1,
        name="CEE Year 5 - B",
        level=500,
        department_id=department.id,
        size=30,
        group_type=GroupType.LAB_GROUP,
        parent_group_id=parent_group.id,
    )
    course = Course(
        code="CEE501",
        name="Structural Lab",
        department_id=department.id,
        level=500,
    )
    db_session.add_all([subgroup_a, subgroup_b, course])
    db_session.commit()
    db_session.refresh(subgroup_a)
    db_session.refresh(subgroup_b)
    db_session.refresh(course)

    response = await async_client.post(
        "/api/v1/lab-coordinator/sessions",
        headers=lab_headers,
        json={
            "course_id": course.id,
            "group_id": parent_group.id,
            "parent_group_id": parent_group.id,
            "day_of_week": 0,
            "start_time": "08:00",
            "end_time": "10:00",
            "session_type": "lab",
            "duration_minutes": 120,
            "frequency_weeks": 1,
            "subgroup_ids": [subgroup_a.id, subgroup_b.id],
        },
    )
    assert response.status_code == 201

    payload = response.json()
    assert payload["has_conflict"] is False

    session = db_session.query(LabSession).filter(LabSession.id == payload["id"]).first()
    assert session is not None
    assert session.group_id == parent_group.id
    assert session.rotation_cycle_length == 2
    assert session.rotation_configuration == {
        "1": [subgroup_a.id],
        "2": [subgroup_b.id],
    }


@pytest.mark.auth
@pytest.mark.asyncio
async def test_timetable_view_filters_rotating_labs_by_academic_week(
    async_client: AsyncClient,
    db_session,
    auth_headers: dict,
):
    university = db_session.query(University).filter(University.id == 1).first()
    department = db_session.query(Department).filter(Department.code == "CEE").first()
    assert university is not None and department is not None

    parent_group = StudentGroup(
        university_id=1,
        name="CEE Year 4",
        level=400,
        department_id=department.id,
        size=120,
        group_type=GroupType.DEPARTMENT,
    )
    subgroup_a = StudentGroup(
        university_id=1,
        name="CEE Year 4 - A",
        level=400,
        department_id=department.id,
        size=30,
        group_type=GroupType.LAB_GROUP,
        parent_group_id=None,
    )
    subgroup_b = StudentGroup(
        university_id=1,
        name="CEE Year 4 - B",
        level=400,
        department_id=department.id,
        size=30,
        group_type=GroupType.LAB_GROUP,
        parent_group_id=None,
    )
    course = Course(
        code="CEE401",
        name="Soil Mechanics",
        department_id=department.id,
        level=400,
    )
    timetable = Timetable(
        university_id=university.id,
        name="CEE 2026",
        semester="Semester 1",
        year=2026,
        academic_half="first_half",
        is_active=True,
    )
    db_session.add_all([parent_group, subgroup_a, subgroup_b, course, timetable])
    db_session.commit()
    db_session.refresh(parent_group)
    db_session.refresh(subgroup_a)
    db_session.refresh(subgroup_b)
    db_session.refresh(course)
    db_session.refresh(timetable)

    db_session.add(
        TimetableSlot(
            course_id=course.id,
            group_id=parent_group.id,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(11, 0),
            session_type="lecture",
            timetable_id=timetable.id,
        )
    )
    db_session.add(
        LabSession(
            university_id=university.id,
            timetable_id=timetable.id,
            course_id=course.id,
            group_id=parent_group.id,
            day_of_week=0,
            start_time=time(14, 0),
            end_time=time(16, 0),
            session_type="lab",
            duration_minutes=120,
            frequency_weeks=1,
            rotation_cycle_length=2,
            rotation_configuration={"1": [subgroup_a.id], "2": [subgroup_b.id]},
        )
    )
    db_session.commit()

    week_one = await async_client.get(
        "/api/v1/timetables/view",
        headers=auth_headers,
        params={
            "year": 4,
            "program": "ALL",
            "academic_week": 1,
            "lab_subgroup_ids": str(subgroup_a.id),
        },
    )
    assert week_one.status_code == 200
    week_one_slots = week_one.json()["slots"]
    assert any(slot.get("is_lab_session") and slot.get("lab_session_id") is not None for slot in week_one_slots)

    week_two = await async_client.get(
        "/api/v1/timetables/view",
        headers=auth_headers,
        params={
            "year": 4,
            "program": "ALL",
            "academic_week": 1,
            "lab_subgroup_ids": str(subgroup_b.id),
        },
    )
    assert week_two.status_code == 200
    assert not any(slot.get("is_lab_session") for slot in week_two.json()["slots"])
