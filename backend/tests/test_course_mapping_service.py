from app.models import (
    Course,
    CourseGroupLink,
    Department,
    GroupAssignment,
    GroupType,
    StudentGroup,
    University,
)
from app.services.course_mapping_service import CourseMappingService
from app.services.timetable_generator import TimetableGenerator


def test_shared_course_eligible_groups_follow_owner_and_shared_departments(db_session):
    univ = University(name="Mapping Univ", domain="mapping-univ.test")
    db_session.add(univ)
    db_session.commit()

    dept_owner = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    dept_shared = Department(university_id=univ.id, name="Mechanical Engineering", code="MEC")
    dept_other = Department(university_id=univ.id, name="Civil Engineering", code="CEE")
    db_session.add_all([dept_owner, dept_shared, dept_other])
    db_session.commit()

    owner_group = StudentGroup(
        university_id=univ.id,
        department_id=dept_owner.id,
        name="EEE Year 4",
        level=400,
        size=120,
    )
    shared_group = StudentGroup(
        university_id=univ.id,
        department_id=dept_shared.id,
        name="MEC Year 4",
        level=400,
        size=95,
    )
    other_group = StudentGroup(
        university_id=univ.id,
        department_id=dept_other.id,
        name="CEE Year 4",
        level=400,
        size=80,
    )
    db_session.add_all([owner_group, shared_group, other_group])
    db_session.commit()

    course = Course(
        code="EEE4010",
        name="Shared Controls",
        department_id=dept_owner.id,
        level=4,
        credits=3,
        lecture_hours=2,
        shared_with_department_ids=[dept_shared.id],
    )
    db_session.add(course)
    db_session.commit()

    service = CourseMappingService(db_session)
    eligible = service.eligible_main_groups_for_course(course)

    assert [item.group.id for item in eligible] == [owner_group.id, shared_group.id]
    assert [item.ownership_kind for item in eligible] == ["owner", "shared"]


def test_save_main_group_mapping_rebuilds_main_links_and_clears_selected_streams(db_session):
    univ = University(name="Mapping Save Univ", domain="mapping-save.test")
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
    sibling_group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 Evening",
        level=400,
        size=70,
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
    db_session.add_all([parent_group, sibling_group, stream_emp])
    db_session.commit()

    course = Course(
        code="EEE4020",
        name="Signal Processing",
        department_id=dept.id,
        level=4,
        credits=3,
        lecture_hours=2,
    )
    db_session.add(course)
    db_session.commit()

    db_session.add(GroupAssignment(group_id=stream_emp.id, course_id=course.id))
    db_session.add(
        CourseGroupLink(
            course_id=course.id,
            group_id=stream_emp.id,
            is_shared=False,
            shared_batch_id=None,
            session_type="lecture",
        )
    )
    db_session.commit()

    service = CourseMappingService(db_session)
    result = service.save_main_group_mapping(
        course,
        [parent_group.id, sibling_group.id],
        "shared",
    )
    db_session.commit()

    assignment_group_ids = {
        row.group_id
        for row in db_session.query(GroupAssignment).filter(GroupAssignment.course_id == course.id).all()
    }
    lecture_links = db_session.query(CourseGroupLink).filter(
        CourseGroupLink.course_id == course.id,
        CourseGroupLink.session_type == "lecture",
    ).all()

    assert result["lecture_mode"] == "shared"
    assert assignment_group_ids == {parent_group.id, sibling_group.id}
    assert {link.group_id for link in lecture_links} == {parent_group.id, sibling_group.id}
    assert all(link.is_shared for link in lecture_links)
    assert len({link.shared_batch_id for link in lecture_links}) == 1


def test_tutorials_and_practicals_follow_shared_course_mapping(db_session):
    univ = University(name="Derived Sessions Univ", domain="derived-sessions.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    db_session.add(dept)
    db_session.commit()

    main_a = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 A",
        level=400,
        size=80,
    )
    main_b = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 B",
        level=400,
        size=70,
    )
    tut_a = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 A - T1",
        level=400,
        size=40,
        group_type=GroupType.TUTORIAL_GROUP,
        parent_group=main_a,
    )
    tut_b = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 B - T1",
        level=400,
        size=35,
        group_type=GroupType.TUTORIAL_GROUP,
        parent_group=main_b,
    )
    lab_a = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 A - L1",
        level=400,
        size=20,
        group_type=GroupType.LAB_GROUP,
        parent_group=main_a,
    )
    lab_b = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 B - L1",
        level=400,
        size=18,
        group_type=GroupType.LAB_GROUP,
        parent_group=main_b,
    )
    course = Course(
        code="EEE4030",
        name="Embedded Systems",
        department_id=dept.id,
        level=4,
        credits=3,
        lecture_hours=2,
        tutorial_hours=1,
        practical_hours=2,
    )
    db_session.add_all([main_a, main_b, tut_a, tut_b, lab_a, lab_b, course])
    db_session.commit()

    service = CourseMappingService(db_session)
    service.save_main_group_mapping(course, [main_a.id, main_b.id], "shared")
    db_session.commit()

    timetable = Timetable(university_id=univ.id, name="Derived", semester="1", year=2026, academic_half="1")
    db_session.add(timetable)
    db_session.commit()

    generator = TimetableGenerator(db_session, timetable.id)
    group_ctx = generator._build_level_group_context(400)
    lecture_units = generator._resolve_session_units(course, "lecture", group_ctx)
    tutorial_units = generator._resolve_session_units(course, "tutorial", group_ctx, lecture_units)
    practical_units = generator._resolve_session_units(course, "practical", group_ctx, lecture_units)

    assert len(lecture_units) == 1
    assert set(lecture_units[0]["covered_group_ids"]) == {main_a.id, main_b.id}
    assert {unit["primary_group_id"] for unit in tutorial_units} == {tut_a.id, tut_b.id}
    assert len(practical_units) == 2
    assert {unit["primary_group_id"] for unit in practical_units} == {lab_a.id, lab_b.id}
