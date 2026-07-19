"""Regression coverage for in-place course editing.

Editing a course's descriptive or delivery fields must never manufacture a
new course, group, or enrolment mapping.  Group mapping is intentionally a
separate explicit action in the UI.
"""

import pytest
from starlette.requests import Request

from app.models import Course, CourseGroupLink, Department, GroupAssignment, StudentGroup, University, User, UserRole
from app.routers.courses import update_course
from app.schemas import CourseUpdate


def _request() -> Request:
    return Request({
        "type": "http",
        "method": "PUT",
        "path": "/api/v1/courses/1",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "server": ("testserver", 80),
    })


@pytest.mark.asyncio
async def test_course_edit_updates_same_record_without_creating_group_mapping(db_session):
    university = University(name="Edit Mapping University", domain="course-edit-mapping.test")
    db_session.add(university)
    db_session.commit()

    department = Department(university_id=university.id, name="Edit Engineering", code="EED")
    coordinator = User(
        university_id=university.id,
        username="edit-coordinator",
        email="edit-coordinator@test.local",
        full_name="Edit Coordinator",
        hashed_password="unused",
        role=UserRole.TENANT_ADMIN,
        is_active=True,
    )
    group = StudentGroup(
        university_id=university.id,
        department=department,
        name="EED Year 3",
        level=300,
        size=40,
    )
    course = Course(
        code="EED301",
        name="Original Name",
        department=department,
        level=300,
        credits=3,
        lecture_hours=2,
        tutorial_hours=0,
        practical_hours=0,
    )
    db_session.add_all([department, coordinator, group, course])
    db_session.commit()
    db_session.add_all([
        GroupAssignment(group_id=group.id, course_id=course.id),
        CourseGroupLink(course_id=course.id, group_id=group.id, session_type="lecture"),
    ])
    db_session.commit()

    original_course_id = course.id
    await update_course(
        request=_request(),
        course_id=course.id,
        course_update=CourseUpdate(name="Updated Name", lecture_hours=3),
        current_user=coordinator,
        db=db_session,
    )

    assert db_session.query(Course).filter(Course.id == original_course_id).count() == 1
    updated = db_session.query(Course).filter(Course.id == original_course_id).one()
    assert updated.name == "Updated Name"
    assert updated.lecture_hours == 3
    assert db_session.query(GroupAssignment).filter(GroupAssignment.course_id == original_course_id).count() == 1
    assert db_session.query(CourseGroupLink).filter(CourseGroupLink.course_id == original_course_id).count() == 1
