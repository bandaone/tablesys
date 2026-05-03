from app.models import Course, Department, GroupAssignment, GroupType, StudentGroup, University
from app.services.group_course_mapping_service import GroupCourseMappingService


def test_group_course_mapping_recommends_same_level_own_general_and_shared_courses(db_session):
    univ = University(name="Group Mapping Univ", domain="group-mapping.test")
    db_session.add(univ)
    db_session.commit()

    dept_owner = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    dept_general = Department(university_id=univ.id, name="General Engineering", code="GEN")
    dept_shared = Department(university_id=univ.id, name="Mechanical Engineering", code="MEC")
    db_session.add_all([dept_owner, dept_general, dept_shared])
    db_session.commit()

    group = StudentGroup(
        university_id=univ.id,
        department_id=dept_owner.id,
        name="EEE Year 2",
        level=200,
        size=120,
    )
    db_session.add(group)
    db_session.commit()

    own_course = Course(
        code="EEE2010",
        name="Circuits",
        department_id=dept_owner.id,
        level=2,
        credits=3,
        lecture_hours=2,
    )
    general_course = Course(
        code="GEN2010",
        name="Communication Skills",
        department_id=dept_general.id,
        level=200,
        credits=2,
        lecture_hours=2,
        course_type="general",
        shared_with_department_ids=None,
    )
    shared_course = Course(
        code="MEC2010",
        name="Engineering Drawing",
        department_id=dept_shared.id,
        level=2,
        credits=3,
        lecture_hours=2,
        shared_with_department_ids=[dept_owner.id],
    )
    wrong_level_course = Course(
        code="EEE3010",
        name="Signals",
        department_id=dept_owner.id,
        level=3,
        credits=3,
        lecture_hours=2,
    )
    db_session.add_all([own_course, general_course, shared_course, wrong_level_course])
    db_session.commit()

    service = GroupCourseMappingService(db_session)
    eligible = service.eligible_courses_for_group(group)

    assert [item.course.code for item in eligible] == ["EEE2010", "GEN2010", "MEC2010"]
    assert [item.source_kind for item in eligible] == ["own", "general", "shared"]
    assert service.recommended_course_ids(group) == [own_course.id, general_course.id, shared_course.id]


def test_group_course_mapping_uses_recommendations_until_explicit_selection_exists(db_session):
    univ = University(name="Group Mapping Seed Univ", domain="group-mapping-seed.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    db_session.add(dept)
    db_session.commit()

    group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 1",
        level=100,
        size=90,
    )
    db_session.add(group)
    db_session.commit()

    course_a = Course(
        code="EEE1010",
        name="Intro A",
        department_id=dept.id,
        level=1,
        credits=3,
        lecture_hours=2,
    )
    course_b = Course(
        code="EEE1020",
        name="Intro B",
        department_id=dept.id,
        level=100,
        credits=3,
        lecture_hours=2,
    )
    db_session.add_all([course_a, course_b])
    db_session.commit()

    service = GroupCourseMappingService(db_session)
    available_ids = [course_a.id, course_b.id]

    assert service.initial_selected_course_ids(group, available_ids) == available_ids

    db_session.add(GroupAssignment(group_id=group.id, course_id=course_b.id))
    db_session.commit()

    assert service.initial_selected_course_ids(group, available_ids) == [course_b.id]


def test_stream_keeps_parent_external_course_selected_while_allowing_local_refinement(db_session):
    univ = University(name="Stream Mapping Univ", domain="stream-mapping.test")
    db_session.add(univ)
    db_session.commit()

    dept_eee = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    dept_gen = Department(university_id=univ.id, name="General Engineering", code="GEN")
    db_session.add_all([dept_eee, dept_gen])
    db_session.commit()

    parent = StudentGroup(
        university_id=univ.id,
        department_id=dept_eee.id,
        name="EEE Year 2",
        level=200,
        size=120,
    )
    stream = StudentGroup(
        university_id=univ.id,
        department_id=dept_eee.id,
        name="EEE Year 2 Power",
        level=200,
        size=60,
        group_type=GroupType.STREAM,
        parent_group=parent,
    )
    db_session.add_all([parent, stream])
    db_session.commit()

    local_parent_course = Course(
        code="EEE2010",
        name="Circuits",
        department_id=dept_eee.id,
        level=2,
        credits=3,
        lecture_hours=2,
    )
    local_stream_course = Course(
        code="EEE2020",
        name="Electives",
        department_id=dept_eee.id,
        level=2,
        credits=3,
        lecture_hours=2,
    )
    external_parent_course = Course(
        code="GEN2010",
        name="Communication Skills",
        department_id=dept_gen.id,
        level=2,
        credits=2,
        lecture_hours=2,
        shared_with_department_ids=[dept_eee.id],
    )
    db_session.add_all([local_parent_course, local_stream_course, external_parent_course])
    db_session.commit()

    db_session.add_all([
        GroupAssignment(group_id=parent.id, course_id=local_parent_course.id),
        GroupAssignment(group_id=parent.id, course_id=external_parent_course.id),
        GroupAssignment(group_id=stream.id, course_id=local_stream_course.id),
    ])
    db_session.commit()

    service = GroupCourseMappingService(db_session)
    selected_ids = service.selected_course_ids_for_group_map(
        stream,
        editable_available_ids=[local_parent_course.id, local_stream_course.id],
        readonly_available_ids=[external_parent_course.id],
    )

    assert set(selected_ids) == {local_stream_course.id, external_parent_course.id}
    assert service.inherited_parent_course_ids_for_stream(stream) == {
        local_parent_course.id,
        external_parent_course.id,
    }
