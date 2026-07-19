"""
Tenant Data Export Router

GDPR / POPIA compliance endpoint — lets a COORDINATOR (or higher) download
a complete structured export of their university's data.

Endpoint
--------
GET /api/v1/export/tenant-data
    Returns a JSON attachment containing all tenant-scoped records.
    Personally identifiable data notes:
    - Lecturer full_name is included (it is institutional data).
    - Lecturer email is intentionally EXCLUDED (private contact detail).
    - No individual student records exist (students are managed as groups).
    - User account emails are included in the users section for account holders.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user, is_tenant_admin
from ..models import (
    User, UserRole, University, Department, Room, Course,
    Lecturer, StudentGroup, Timetable, TimetableSlot,
    ExamPeriod, UsageMonthlySummary,
)
from ..middleware.tenant import get_current_tenant_id

logger = logging.getLogger("app.data_export")

router = APIRouter(prefix="/api/v1/export", tags=["data-export"])


def _require_coordinator(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.COORDINATOR, UserRole.SCHOOL_COORDINATOR, UserRole.TENANT_ADMIN, UserRole.SUPERADMIN):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Data export requires a school operator, tenant admin, or superadmin role.")
    return current_user


@router.get(
    "/tenant-data",
    summary="Export all tenant data",
    description=(
        "Download a structured JSON export of all data belonging to the current tenant. "
        "Intended for GDPR/POPIA data portability compliance. "
        "Lecturer emails are excluded; no individual student records exist."
    ),
)
def export_tenant_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_coordinator),
) -> Response:
    tenant_id = get_current_tenant_id()
    if not tenant_id and current_user.university_id:
        tenant_id = current_user.university_id

    if not tenant_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Tenant context could not be resolved.")

    logger.info(
        "Data export requested by user_id=%d for university_id=%d",
        current_user.id, tenant_id,
    )

    # ── University ────────────────────────────────────────────────────────────
    uni = db.query(University).filter(University.id == tenant_id).first()
    university_data: dict[str, Any] = {}
    if uni:
        university_data = {
            "id": uni.id,
            "name": uni.name,
            "domain": uni.domain,
            "plan_tier": uni.plan_tier,
            "is_active": uni.is_active,
            "registered_at": str(uni.registered_at) if uni.registered_at else None,
            "timezone": getattr(uni, "timezone", None),
        }

    # ── Users (account holders only — not student individuals) ────────────────
    users = db.query(User).filter(User.university_id == tenant_id)
    if getattr(current_user, "school_id", None) is not None and not is_tenant_admin(current_user) and current_user.role != UserRole.SUPERADMIN:
        users = users.filter((User.school_id == current_user.school_id) | (User.id == current_user.id))
    users = users.all()
    users_data = [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value if hasattr(u.role, "value") else str(u.role),
            "is_active": u.is_active,
        }
        for u in users
    ]

    # ── Departments ───────────────────────────────────────────────────────────
    departments = db.query(Department).filter(Department.university_id == tenant_id)
    if getattr(current_user, "school_id", None) is not None and not is_tenant_admin(current_user) and current_user.role != UserRole.SUPERADMIN:
        departments = departments.filter(Department.school_id == current_user.school_id)
    departments = departments.all()
    departments_data = [
        {"id": d.id, "name": d.name, "code": d.code}
        for d in departments
    ]

    # ── Rooms ─────────────────────────────────────────────────────────────────
    rooms = db.query(Room).filter(Room.university_id == tenant_id)
    if getattr(current_user, "school_id", None) is not None and not is_tenant_admin(current_user) and current_user.role != UserRole.SUPERADMIN:
        rooms = rooms.filter((Room.school_id == current_user.school_id) | (Room.school_id == None))
    rooms = rooms.all()
    rooms_data = [
        {
            "id": r.id,
            "name": r.name,
            "building": r.building,
            "capacity": r.capacity,
            "room_type": r.room_type,
        }
        for r in rooms
    ]

    # ── Courses ───────────────────────────────────────────────────────────────
    dept_ids = {d.id for d in departments}
    courses = db.query(Course).filter(Course.department_id.in_(dept_ids)).all() if dept_ids else []
    courses_data = [
        {
            "id": c.id,
            "code": c.code,
            "name": c.name,
            "level": c.level,
            "credits": c.credits,
            "lecture_hours": c.lecture_hours,
            "tutorial_hours": c.tutorial_hours,
            "practical_hours": c.practical_hours,
        }
        for c in courses
    ]

    # ── Lecturers (email intentionally excluded) ──────────────────────────────
    lecturers = db.query(Lecturer).filter(Lecturer.department_id.in_(dept_ids)).all() if dept_ids else []
    lecturers_data = [
        {
            "id": l.id,
            "staff_number": l.staff_number,
            "full_name": l.full_name,
            # email excluded — private contact detail
            "department_id": l.department_id,
            "max_hours_per_week": l.max_hours_per_week,
        }
        for l in lecturers
    ]

    # ── Student Groups ────────────────────────────────────────────────────────
    groups = db.query(StudentGroup).filter(StudentGroup.university_id == tenant_id)
    if getattr(current_user, "school_id", None) is not None and not is_tenant_admin(current_user) and current_user.role != UserRole.SUPERADMIN:
        groups = groups.join(Department, StudentGroup.department_id == Department.id).filter(Department.school_id == current_user.school_id)
    groups = groups.all()
    groups_data = [
        {
            "id": g.id,
            "name": g.name,
            "level": g.level,
            "size": g.size,
            "department_id": g.department_id,
            "parent_group_id": g.parent_group_id,
        }
        for g in groups
    ]

    # ── Timetables ────────────────────────────────────────────────────────────
    timetables = db.query(Timetable).filter(Timetable.university_id == tenant_id)
    if getattr(current_user, "school_id", None) is not None and not is_tenant_admin(current_user) and current_user.role != UserRole.SUPERADMIN:
        timetables = timetables.filter((Timetable.school_id == current_user.school_id) | (Timetable.school_id == None))
    timetables = timetables.all()
    timetable_ids = [t.id for t in timetables]
    slots = db.query(TimetableSlot).filter(TimetableSlot.timetable_id.in_(timetable_ids)).all() if timetable_ids else []

    timetables_data = []
    slots_by_timetable: dict[int, list] = {}
    for slot in slots:
        slots_by_timetable.setdefault(slot.timetable_id, []).append({
            "id": slot.id,
            "course_id": slot.course_id,
            "lecturer_id": slot.lecturer_id,
            "room_id": slot.room_id,
            "group_id": slot.group_id,
            "day_of_week": slot.day_of_week,
            "start_time": str(slot.start_time),
            "end_time": str(slot.end_time),
            "session_type": slot.session_type,
        })

    for t in timetables:
        timetables_data.append({
            "id": t.id,
            "name": t.name,
            "semester": t.semester,
            "year": t.year,
            "is_active": t.is_active,
            "slots": slots_by_timetable.get(t.id, []),
        })

    # ── Exam Periods ──────────────────────────────────────────────────────────
    exam_periods = db.query(ExamPeriod).filter(ExamPeriod.university_id == tenant_id).all()
    exam_periods_data = [
        {
            "id": ep.id,
            "name": ep.name,
            "semester": ep.semester,
            "year": ep.year,
            "start_date": str(ep.start_date),
            "end_date": str(ep.end_date),
            "is_published": ep.is_published,
        }
        for ep in exam_periods
    ]

    # ── Usage Summary (last 3 months) ─────────────────────────────────────────
    usage_summaries = (
        db.query(UsageMonthlySummary)
        .filter(UsageMonthlySummary.tenant_id == tenant_id)
        .order_by(UsageMonthlySummary.period_start.desc())
        .limit(36)  # 12 metrics × 3 months
        .all()
    )
    usage_data = [
        {
            "metric_key": s.metric_key,
            "period_start": str(s.period_start),
            "period_end": str(s.period_end),
            "total_quantity": int(s.total_quantity),
        }
        for s in usage_summaries
    ]

    # ── Assemble export payload ───────────────────────────────────────────────
    export_payload = {
        "export_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "exported_by_user_id": current_user.id,
            "university_id": tenant_id,
            "format_version": "1.0",
            "notes": "Lecturer emails excluded per data minimisation policy. No individual student records exist.",
        },
        "university": university_data,
        "users": users_data,
        "departments": departments_data,
        "rooms": rooms_data,
        "courses": courses_data,
        "lecturers": lecturers_data,
        "student_groups": groups_data,
        "timetables": timetables_data,
        "exam_periods": exam_periods_data,
        "usage_summary": usage_data,
    }

    logger.info(
        "Data export completed for university_id=%d — "
        "%d courses, %d timetables, %d slots",
        tenant_id, len(courses_data), len(timetables_data), len(slots),
    )

    filename = f"tablesys_export_{tenant_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    content = json.dumps(export_payload, indent=2, default=str)

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-University-Id": str(tenant_id),
        },
    )
