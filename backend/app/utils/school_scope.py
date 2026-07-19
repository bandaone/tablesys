from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import false
from sqlalchemy.orm import Session

from ..auth import is_tenant_admin, is_school_operator, resolve_effective_school_scope
from ..models import Course, Department, Lecturer, Room, School, StudentGroup, Timetable, User, UserRole


def get_accessible_school_id(user: User, requested_school_id: Optional[int] = None) -> Optional[int]:
    return resolve_effective_school_scope(user, requested_school_id)


def ensure_school_belongs_to_university(db: Session, school_id: Optional[int], university_id: Optional[int]) -> Optional[School]:
    if school_id is None:
        return None
    school = db.query(School).filter(School.id == school_id).first()
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    if university_id is not None and school.university_id != university_id:
        raise HTTPException(status_code=403, detail="School does not belong to your institution")
    return school


def ensure_user_can_manage_school(db: Session, user: User, school_id: Optional[int]) -> Optional[School]:
    school = ensure_school_belongs_to_university(db, school_id, getattr(user, "university_id", None))
    get_accessible_school_id(user, school_id)
    return school


def ensure_user_can_manage_department(db: Session, user: User, department_id: Optional[int]) -> Optional[Department]:
    if department_id is None:
        return None
    department = db.query(Department).filter(Department.id == department_id).first()
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    if getattr(user, "university_id", None) is not None and department.university_id != user.university_id:
        raise HTTPException(status_code=403, detail="Department does not belong to your institution")
    if getattr(user, "role", None) == UserRole.COORDINATOR and getattr(user, "department_id", None) is not None:
        if department.id != user.department_id:
            raise HTTPException(status_code=403, detail="You can only manage your own department.")
    ensure_user_can_manage_school(db, user, department.school_id)
    return department


def filter_department_query_for_user(query, user: User):
    if getattr(user, "university_id", None):
        query = query.filter(Department.university_id == user.university_id)
    if is_tenant_admin(user):
        return query
    if getattr(user, "department_id", None) is not None:
        return query.filter(Department.id == user.department_id)
    if is_school_operator(user) and getattr(user, "school_id", None) is not None:
        return query.filter(Department.school_id == user.school_id)
    return query


def filter_room_query_for_user(query, user: User):
    if getattr(user, "university_id", None):
        query = query.filter(Room.university_id == user.university_id)
    if is_tenant_admin(user):
        return query
    if getattr(user, "department_id", None) is not None:
        return query.filter(Room.department_id == user.department_id)
    school_id = getattr(user, "school_id", None)
    if is_school_operator(user) and school_id is not None:
        # An unowned room is a data-quality problem, not a room visible to
        # every school. Only a tenant admin may manage truly global rooms.
        return query.filter(Room.school_id == school_id)
    return query


def filter_course_query_for_user(query, user: User):
    if getattr(user, "university_id", None) is not None:
        query = query.join(Department, Course.department_id == Department.id).filter(
            Department.university_id == user.university_id
        )
    if is_tenant_admin(user):
        return query
    if getattr(user, "department_id", None) is not None:
        return query.filter(Course.department_id == user.department_id)
    school_id = getattr(user, "school_id", None)
    if is_school_operator(user) and school_id is not None:
        return query.filter(Department.school_id == school_id)
    return query


def filter_group_query_for_user(query, user: User):
    if getattr(user, "university_id", None) is not None:
        query = query.filter(StudentGroup.university_id == user.university_id)
    if is_tenant_admin(user):
        return query
    if getattr(user, "department_id", None) is not None:
        return query.filter(StudentGroup.department_id == user.department_id)
    school_id = getattr(user, "school_id", None)
    if is_school_operator(user) and school_id is not None:
        query = query.join(Department, StudentGroup.department_id == Department.id).filter(
            Department.school_id == school_id
        )
        return query
    return query


def filter_lecturer_query_for_user(query, user: User):
    if getattr(user, "university_id", None) is not None:
        query = query.join(Department, Lecturer.department_id == Department.id).filter(
            Department.university_id == user.university_id
        )
    if is_tenant_admin(user):
        return query
    if getattr(user, "department_id", None) is not None:
        return query.filter(Lecturer.department_id == user.department_id)
    school_id = getattr(user, "school_id", None)
    if is_school_operator(user) and school_id is not None:
        return query.filter(Department.school_id == school_id)
    return query


def filter_timetable_query_for_user(query, user: User):
    if getattr(user, "university_id", None):
        query = query.filter(Timetable.university_id == user.university_id)
    if is_tenant_admin(user):
        return query
    school_id = getattr(user, "school_id", None)
    if school_id is not None:
        # A non-tenant user must never fall back to another school's timetable.
        return query.filter(Timetable.school_id == school_id)
    # Missing school membership is a configuration error, not permission to
    # view the tenant-wide timetable set.
    return query.filter(false())
