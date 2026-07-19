"""
Tenant Offboarding Router — SUPERADMIN only

Two-phase offboarding pipeline:

Phase 1 — Deactivate  (POST /api/v1/superadmin/offboard/{university_id}/deactivate)
    Marks the tenant inactive.  All logins for this university immediately fail.
    Reversible — a Superadmin can reactivate via the existing Superadmin panel.

Phase 2 — Purge       (POST /api/v1/superadmin/offboard/{university_id}/purge)
    Permanently and irreversibly deletes all tenant-scoped rows.
    Requires a confirmation token (the university's domain string) to prevent
    accidental deletion.  Writes a full audit log entry before deletion starts.

Separation rationale:
    Having two distinct endpoints with different confirmation requirements
    makes it operationally impossible to accidentally trigger a purge when
    you meant to deactivate. They also have independent audit events.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from ..models import (
    User, UserRole, University, Department, Room, Course, Lecturer,
    StudentGroup, GroupAssignment, LecturerAssignment, LecturerUnavailability,
    CourseGroupLink, Timetable, TimetableSlot,
    ExamPeriod, ExamPaper, ExamSlot, ExamSlotRoom, ExamSeatingProfile,
    ExamSessionWindow, Notification, UsageEvent, UsageMonthlySummary,
    PendingRegistration,
)

logger = logging.getLogger("app.offboarding")

router = APIRouter(prefix="/api/v1/superadmin/offboard", tags=["offboarding"])


def _superadmin_only(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Only SUPERADMIN accounts may perform offboarding actions.")
    return current_user


def _get_university_or_404(db: Session, university_id: int) -> University:
    uni = db.query(University).filter(University.id == university_id).first()
    if not uni:
        raise HTTPException(status_code=404, detail=f"University {university_id} not found.")
    return uni


# ── Phase 1: Deactivate ───────────────────────────────────────────────────────

@router.post(
    "/{university_id}/deactivate",
    summary="Phase 1: Deactivate a tenant",
    description=(
        "Marks the university as inactive. All user logins for this tenant "
        "will immediately fail. This action is reversible."
    ),
)
def deactivate_tenant(
    university_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_superadmin_only),
):
    uni = _get_university_or_404(db, university_id)

    if not uni.is_active:
        return {
            "status": "no_op",
            "message": f"University '{uni.name}' is already inactive.",
            "university_id": university_id,
        }

    uni.is_active = False
    db.commit()

    logger.warning(
        "OFFBOARD DEACTIVATE: university_id=%d domain=%s deactivated by superadmin user_id=%d",
        university_id, uni.domain, current_user.id,
    )

    return {
        "status": "deactivated",
        "message": f"University '{uni.name}' ({uni.domain}) has been deactivated. All logins blocked.",
        "university_id": university_id,
        "reversible": True,
    }


# ── Phase 2: Purge ────────────────────────────────────────────────────────────

class PurgeConfirmation(BaseModel):
    confirmation_token: str  # Must match the university's domain exactly


@router.post(
    "/{university_id}/purge",
    summary="Phase 2: Permanently purge all tenant data",
    description=(
        "IRREVERSIBLE. Deletes all data belonging to the specified university "
        "in safe dependency order. Requires the university's domain as a "
        "confirmation_token in the request body to prevent accidental deletion."
    ),
)
def purge_tenant(
    university_id: int,
    body: PurgeConfirmation = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(_superadmin_only),
):
    uni = _get_university_or_404(db, university_id)

    # ── Confirmation guard ────────────────────────────────────────────────────
    if body.confirmation_token != uni.domain:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Confirmation token does not match. "
                f"To purge, you must supply the university domain as the confirmation_token."
            ),
        )

    if uni.is_active:
        raise HTTPException(
            status_code=409,
            detail=(
                "University must be deactivated before purging. "
                "Call /deactivate first."
            ),
        )

    now = datetime.now(timezone.utc)

    # ── Audit log entry BEFORE any deletions ─────────────────────────────────
    logger.critical(
        "OFFBOARD PURGE INITIATED: university_id=%d domain=%s name=%s "
        "by superadmin user_id=%d at %s",
        university_id, uni.domain, uni.name, current_user.id, now.isoformat(),
    )

    # ── Department IDs (needed for scoped deletes) ────────────────────────────
    dept_ids = [d.id for d in db.query(Department.id).filter(Department.university_id == university_id).all()]

    # ── Safe deletion order (children before parents) ────────────────────────
    purge_counts: dict[str, int] = {}

    # 1. Exam slot rooms (deepest child)
    if dept_ids:
        exam_slot_ids = [
            row.id for row in
            db.query(ExamSlot.id)
            .join(ExamPeriod, ExamSlot.exam_period_id == ExamPeriod.id)
            .filter(ExamPeriod.university_id == university_id)
            .all()
        ]
        if exam_slot_ids:
            n = db.query(ExamSlotRoom).filter(ExamSlotRoom.exam_slot_id.in_(exam_slot_ids)).delete(synchronize_session=False)
            purge_counts["exam_slot_rooms"] = n
            n = db.query(ExamSlot).filter(ExamSlot.id.in_(exam_slot_ids)).delete(synchronize_session=False)
            purge_counts["exam_slots"] = n

    # 2. Exam papers
    exam_period_ids = [
        row.id for row in db.query(ExamPeriod.id).filter(ExamPeriod.university_id == university_id).all()
    ]
    if exam_period_ids:
        n = db.query(ExamPaper).filter(ExamPaper.exam_period_id.in_(exam_period_ids)).delete(synchronize_session=False)
        purge_counts["exam_papers"] = n
        n = db.query(ExamSessionWindow).filter(ExamSessionWindow.exam_period_id.in_(exam_period_ids)).delete(synchronize_session=False)
        purge_counts["exam_session_windows"] = n

    # 3. Exam periods and seating profiles
    n = db.query(ExamPeriod).filter(ExamPeriod.university_id == university_id).delete(synchronize_session=False)
    purge_counts["exam_periods"] = n
    n = db.query(ExamSeatingProfile).filter(ExamSeatingProfile.university_id == university_id).delete(synchronize_session=False)
    purge_counts["exam_seating_profiles"] = n

    # 4. Timetable slots
    timetable_ids = [
        row.id for row in db.query(Timetable.id).filter(Timetable.university_id == university_id).all()
    ]
    if timetable_ids:
        n = db.query(TimetableSlot).filter(TimetableSlot.timetable_id.in_(timetable_ids)).delete(synchronize_session=False)
        purge_counts["timetable_slots"] = n

    # 5. Timetables
    n = db.query(Timetable).filter(Timetable.university_id == university_id).delete(synchronize_session=False)
    purge_counts["timetables"] = n

    # 6. Course-group links and group assignments
    if dept_ids:
        group_ids = [row.id for row in db.query(StudentGroup.id).filter(StudentGroup.university_id == university_id).all()]
        course_ids = [row.id for row in db.query(Course.id).filter(Course.department_id.in_(dept_ids)).all()]
        if group_ids:
            n = db.query(CourseGroupLink).filter(CourseGroupLink.group_id.in_(group_ids)).delete(synchronize_session=False)
            purge_counts["course_group_links"] = n
            n = db.query(GroupAssignment).filter(GroupAssignment.group_id.in_(group_ids)).delete(synchronize_session=False)
            purge_counts["group_assignments"] = n
        if course_ids:
            n = db.query(LecturerAssignment).filter(LecturerAssignment.course_id.in_(course_ids)).delete(synchronize_session=False)
            purge_counts["lecturer_assignments"] = n

    # 7. Student groups, courses
    n = db.query(StudentGroup).filter(StudentGroup.university_id == university_id).delete(synchronize_session=False)
    purge_counts["student_groups"] = n
    if dept_ids:
        n = db.query(Course).filter(Course.department_id.in_(dept_ids)).delete(synchronize_session=False)
        purge_counts["courses"] = n

    # 8. Lecturers and unavailability
    if dept_ids:
        lecturer_ids = [row.id for row in db.query(Lecturer.id).filter(Lecturer.department_id.in_(dept_ids)).all()]
        if lecturer_ids:
            n = db.query(LecturerUnavailability).filter(LecturerUnavailability.lecturer_id.in_(lecturer_ids)).delete(synchronize_session=False)
            purge_counts["lecturer_unavailability"] = n
        n = db.query(Lecturer).filter(Lecturer.department_id.in_(dept_ids)).delete(synchronize_session=False)
        purge_counts["lecturers"] = n

    # 9. Rooms, departments
    n = db.query(Room).filter(Room.university_id == university_id).delete(synchronize_session=False)
    purge_counts["rooms"] = n
    n = db.query(Department).filter(Department.university_id == university_id).delete(synchronize_session=False)
    purge_counts["departments"] = n

    # 10. Notifications
    user_ids = [row.id for row in db.query(User.id).filter(User.university_id == university_id).all()]
    if user_ids:
        n = db.query(Notification).filter(Notification.user_id.in_(user_ids)).delete(synchronize_session=False)
        purge_counts["notifications"] = n

    # 11. Users
    n = db.query(User).filter(User.university_id == university_id).delete(synchronize_session=False)
    purge_counts["users"] = n

    # 12. Usage events and summaries
    n = db.query(UsageEvent).filter(UsageEvent.tenant_id == university_id).delete(synchronize_session=False)
    purge_counts["usage_events"] = n
    n = db.query(UsageMonthlySummary).filter(UsageMonthlySummary.tenant_id == university_id).delete(synchronize_session=False)
    purge_counts["usage_summaries"] = n

    # 13. Pending registrations for this domain
    n = db.query(PendingRegistration).filter(PendingRegistration.subdomain == uni.domain).delete(synchronize_session=False)
    purge_counts["pending_registrations"] = n

    # 14. University record itself
    db.delete(uni)

    db.commit()

    total_deleted = sum(purge_counts.values())
    logger.critical(
        "OFFBOARD PURGE COMPLETE: university_id=%d domain=%s — %d total rows deleted. Breakdown: %s",
        university_id, uni.domain, total_deleted, purge_counts,
    )

    return {
        "status": "purged",
        "message": f"University '{uni.name}' ({uni.domain}) and all associated data have been permanently deleted.",
        "university_id": university_id,
        "rows_deleted": total_deleted,
        "deletion_breakdown": purge_counts,
        "purged_at": now.isoformat(),
        "purged_by_user_id": current_user.id,
        "reversible": False,
    }
