import pytest

from app.models import Course, Department, University, User, UserRole
from app.routers.courses import get_courses


@pytest.mark.asyncio
async def test_gen_hod_sees_gen_owned_courses_even_without_matching_gen_groups(db_session):
    univ = University(name="Gen Visibility Univ", domain="gen-visibility.test")
    db_session.add(univ)
    db_session.commit()

    dept_gen = Department(university_id=univ.id, name="General Engineering", code="GEN")
    dept_eee = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    db_session.add_all([dept_gen, dept_eee])
    db_session.commit()

    gen_hod = User(
        university_id=univ.id,
        email="genhod@test.local",
        username="genhod",
        hashed_password="x",
        full_name="GEN HOD",
        role=UserRole.HOD,
        department_id=dept_gen.id,
        is_active=True,
    )
    db_session.add(gen_hod)
    db_session.commit()

    gen_year4 = Course(
        code="GEN4010",
        name="Advanced Service Course",
        department_id=dept_gen.id,
        level=4,
        credits=3,
        lecture_hours=2,
        tutorial_hours=0,
        practical_hours=0,
    )
    gen_year5 = Course(
        code="GEN5010",
        name="Capstone Support",
        department_id=dept_gen.id,
        level=5,
        credits=3,
        lecture_hours=2,
        tutorial_hours=0,
        practical_hours=0,
        shared_with_department_ids=[dept_eee.id],
    )
    db_session.add_all([gen_year4, gen_year5])
    db_session.commit()

    courses = await get_courses(current_user=gen_hod, db=db_session)

    assert {course.code for course in courses} == {"GEN4010", "GEN5010"}
