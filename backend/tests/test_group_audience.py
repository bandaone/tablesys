from app.models import (
    Course,
    GroupAssignment,
    Department,
    GroupType,
    StudentGroup,
    Timetable,
    TimetableSlot,
    University,
)
from app.utils.group_audience import resolve_slot_audience_labels


def test_parent_slot_expands_to_stream_labels(db_session):
    univ = University(name="Audience Labels Univ", domain="audience-labels.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    db_session.add(dept)
    db_session.commit()

    parent_group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4",
        display_code="EEE4",
        level=400,
        size=140,
    )
    stream_emp = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 EMP",
        display_code="EMP",
        level=400,
        size=87,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    stream_et = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 ET",
        display_code="ET",
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
    )
    timetable = Timetable(university_id=univ.id, name="Combined", semester="1", year=2026, academic_half="1")
    db_session.add_all([parent_group, stream_emp, stream_et, course, timetable])
    db_session.commit()

    slot = TimetableSlot(
        course_id=course.id,
        group_id=parent_group.id,
        day_of_week=0,
        session_type="lecture",
        timetable_id=timetable.id,
    )

    labels = resolve_slot_audience_labels(db_session, slot)

    assert labels == ["EMP", "ET"]


def test_shared_slot_uses_explicit_groups_without_stream_expansion(db_session):
    univ = University(name="Audience Shared Univ", domain="audience-shared.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE")
    db_session.add(dept)
    db_session.commit()

    parent_group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4",
        display_code="EEE4",
        level=400,
        size=140,
    )
    stream_emp = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 EMP",
        display_code="EMP",
        level=400,
        size=87,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    stream_et = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE Year 4 ET",
        display_code="ET",
        level=400,
        size=53,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    course = Course(
        code="EEE4999",
        name="Shared Stream Course",
        department_id=dept.id,
        level=400,
        credits=3,
        lecture_hours=2,
    )
    timetable = Timetable(university_id=univ.id, name="Separate", semester="1", year=2026, academic_half="1")
    db_session.add_all([parent_group, stream_emp, stream_et, course, timetable])
    db_session.commit()

    slot = TimetableSlot(
        course_id=course.id,
        group_id=stream_emp.id,
        day_of_week=0,
        session_type="lecture",
        timetable_id=timetable.id,
        shared_group_ids=[stream_et.id],
    )

    labels = resolve_slot_audience_labels(db_session, slot)

    assert labels == ["EMP", "ET"]


def test_parent_slot_prefers_stream_course_assignments_over_blanket_expansion(db_session):
    univ = University(name="Audience Assignment Univ", domain="audience-assignment.test")
    db_session.add(univ)
    db_session.commit()

    dept = Department(university_id=univ.id, name="Electrical Engineering", code="EEE-ASN")
    db_session.add(dept)
    db_session.commit()

    parent_group = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE5",
        display_code="EEE5",
        level=5,
        size=140,
    )
    stream_emp = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE5 EMP",
        display_code="EMP",
        level=500,
        size=87,
        group_type=GroupType.STREAM,
        parent_group=parent_group,
    )
    stream_et = StudentGroup(
        university_id=univ.id,
        department_id=dept.id,
        name="EEE5 ET",
        display_code="ET",
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
    )
    timetable = Timetable(university_id=univ.id, name="Mapped", semester="1", year=2026, academic_half="1")
    db_session.add_all([parent_group, stream_emp, stream_et, course, timetable])
    db_session.commit()

    db_session.add(GroupAssignment(group_id=stream_et.id, course_id=course.id))
    db_session.commit()

    slot = TimetableSlot(
        course_id=course.id,
        group_id=parent_group.id,
        day_of_week=0,
        session_type="lecture",
        timetable_id=timetable.id,
    )

    labels = resolve_slot_audience_labels(db_session, slot)

    assert labels == ["ET"]
