from io import BytesIO

import pytest

from app.models import Course, Department, Lecturer, LecturerAssignment, School


async def _create_school(db_session, name: str = "School of Engineering", code: str = "ENG") -> School:
    school = School(university_id=1, name=name, code=code, is_active=True)
    db_session.add(school)
    db_session.commit()
    db_session.refresh(school)
    return school


@pytest.mark.asyncio
async def test_school_profile_preview_and_apply(async_client, auth_headers, db_session):
    school = await _create_school(db_session, name="School of Engineering A", code="ENGA")

    csv_content = (
        "school,programme,year_level,course_code,course_name,lecturer_name\n"
        f"{school.name},Civil Engineering,Year 1,CEE101,Introduction to Civil Engineering,Jane Banda\n"
    ).encode("utf-8")

    preview_response = await async_client.post(
        f"/api/v1/schools/{school.id}/profile-upload/preview",
        headers=auth_headers,
        files={"file": ("school-profile.csv", BytesIO(csv_content), "text/csv")},
    )

    assert preview_response.status_code == 200, preview_response.text
    preview_payload = preview_response.json()
    assert preview_payload["summary"]["ready_rows"] == 1
    assert preview_payload["summary"]["departments_to_create"] == 1
    assert preview_payload["rows"][0]["year_level"] == 100

    apply_response = await async_client.post(
        f"/api/v1/schools/{school.id}/profile-upload/apply",
        headers=auth_headers,
        json={
            "fingerprint": preview_payload["fingerprint"],
            "expires_at": preview_payload["expires_at"],
            "rows": preview_payload["rows"],
        },
    )
    assert apply_response.status_code == 200, apply_response.text
    apply_payload = apply_response.json()
    assert apply_payload["created_departments"] == 1
    assert apply_payload["created_courses"] == 1
    assert apply_payload["created_lecturers"] == 1
    assert apply_payload["created_assignments"] == 1

    department = db_session.query(Department).filter(Department.school_id == school.id).one()
    course = db_session.query(Course).filter(Course.department_id == department.id, Course.code == "CEE101").one()
    lecturer = db_session.query(Lecturer).filter(Lecturer.department_id == department.id).one()
    assignment = db_session.query(LecturerAssignment).filter(
        LecturerAssignment.course_id == course.id,
        LecturerAssignment.lecturer_id == lecturer.id,
    ).one()

    assert department.name == "Civil Engineering"
    assert course.level == 100
    assert course.credits is None
    assert course.lecture_hours is None
    assert course.profile_status == "profile_seeded"
    assert lecturer.full_name == "Jane Banda"
    assert assignment.session_type == "lecture"


@pytest.mark.asyncio
async def test_school_profile_preview_rejects_wrong_school(async_client, auth_headers, db_session):
    school = await _create_school(db_session, name="School of Engineering B", code="ENGB")
    csv_content = (
        "school,programme,year_level,course_code,course_name,lecturer_name\n"
        "School of Medicine,Civil Engineering,Year 1,CEE101,Introduction to Civil Engineering,Jane Banda\n"
    ).encode("utf-8")

    response = await async_client.post(
        f"/api/v1/schools/{school.id}/profile-upload/preview",
        headers=auth_headers,
        files={"file": ("school-profile.csv", BytesIO(csv_content), "text/csv")},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["ready_rows"] == 0
    assert payload["summary"]["conflicted_rows"] == 1
    assert "does not match the selected school" in payload["rows"][0]["issues"][0]


@pytest.mark.asyncio
async def test_school_profile_preview_flags_lecturer_cross_programme_conflict(async_client, auth_headers, db_session):
    school = await _create_school(db_session, name="School of Engineering C", code="ENGC")
    csv_content = (
        "school,programme,year_level,course_code,course_name,lecturer_name\n"
        f"{school.name},Civil Engineering,Year 1,CEE101,Introduction to Civil Engineering,Alex Banda\n"
        f"{school.name},Mechanical Engineering,Year 1,MEC101,Introduction to Mechanical Engineering,Alex Banda\n"
    ).encode("utf-8")

    response = await async_client.post(
        f"/api/v1/schools/{school.id}/profile-upload/preview",
        headers=auth_headers,
        files={"file": ("school-profile.csv", BytesIO(csv_content), "text/csv")},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["ready_rows"] == 0
    assert payload["summary"]["conflicted_rows"] == 2
    assert all(not row["can_apply"] for row in payload["rows"])
    assert any("multiple programmes" in issue for issue in payload["rows"][0]["issues"])


@pytest.mark.asyncio
async def test_seeded_course_can_be_completed_later(async_client, auth_headers, db_session):
    school = await _create_school(db_session, name="School of Engineering D", code="ENGD")
    department = Department(university_id=1, school_id=school.id, name="Computer Science", code="CSC")
    db_session.add(department)
    db_session.commit()
    db_session.refresh(department)

    course = Course(
        code="CSC101",
        name="Introduction to Computer Science",
        department_id=department.id,
        level=100,
        credits=None,
        lecture_hours=None,
        tutorial_hours=None,
        practical_hours=None,
        profile_status="profile_seeded",
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    response = await async_client.put(
        f"/api/v1/courses/{course.id}",
        headers=auth_headers,
        json={
            "code": "CSC101",
            "name": "Introduction to Computer Science",
            "department_id": department.id,
            "level": 100,
            "credits": 4,
            "lecture_hours": 3,
            "tutorial_hours": 1,
            "practical_hours": 0,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["credits"] == 4
    assert payload["lecture_hours"] == 3
    assert payload["profile_status"] == "profile_complete"
