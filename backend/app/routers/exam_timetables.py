from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_active_hod, get_current_active_school_operator, get_current_user, is_school_operator
from ..database import get_db
from ..models import (
    Course,
    ExamPaper,
    ExamPeriod,
    ExamSeatingProfile,
    ExamSessionWindow,
    ExamSlot,
    ExamSlotRoom,
    StudentGroup,
    University,
    User,
    UserRole,
)
from ..schemas import (
    ExamGenerateRequest,
    ExamPaper as ExamPaperSchema,
    ExamPaperCandidate,
    ExamPaperCandidateGroup,
    ExamPaperCreate,
    ExamPaperSyncRequest,
    ExamPaperSyncResponse,
    ExamPaperUpdate,
    ExamPeriod as ExamPeriodSchema,
    ExamPeriodCreate,
    ExamPeriodUpdate,
    ExamPublishRequest,
    ExamSeatingProfile as ExamSeatingProfileSchema,
    ExamSeatingProfileCreate,
    ExamSeatingProfileUpdate,
    ExamSessionWindow as ExamSessionWindowSchema,
    ExamSessionWindowCreate,
    ExamSessionWindowUpdate,
    ExamSlot as ExamSlotSchema,
)
from ..services.exam_timetable_generator import ExamTimetableGenerator
from ..services.exam_validation_service import ExamValidationService
from ..services.course_mapping_service import CourseMappingService
from ..services.notification_service import NotificationService
from ..utils.audit_logger import AuditLogger
from ..middleware.quota import enforce_generation_quota
from ..utils.department_utils import find_general_department, is_general_department
from ..utils.school_scope import filter_course_query_for_user, filter_group_query_for_user

router = APIRouter(prefix="/api/v1/exam-timetables", tags=["exam-timetables"])


def resolve_university_id(db: Session, current_user: User) -> int:
    if getattr(current_user, "university_id", None):
        return current_user.university_id
    university = db.query(University).order_by(University.id.asc()).first()
    if not university:
        raise HTTPException(status_code=500, detail="No university found for exam scheduling")
    return university.id


def get_period_or_404(db: Session, current_user: User, period_id: int) -> ExamPeriod:
    university_id = resolve_university_id(db, current_user)
    period = (
        db.query(ExamPeriod)
        .options(
            selectinload(ExamPeriod.session_windows),
            selectinload(ExamPeriod.papers),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.room_allocations).selectinload(ExamSlotRoom.room),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.room_allocations).selectinload(ExamSlotRoom.seating_profile),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.paper),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.session_window),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.seating_profile),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.chief_invigilator),
        )
        .filter(
            ExamPeriod.id == period_id,
            ExamPeriod.university_id == university_id,
        )
        .first()
    )
    if not period:
        raise HTTPException(status_code=404, detail="Exam period not found")
    return period


def ensure_profile_access(profile: ExamSeatingProfile, current_user: User, db: Session) -> None:
    if not profile:
        raise HTTPException(status_code=404, detail="Exam seating profile not found")
    if profile.university_id != resolve_university_id(db, current_user):
        raise HTTPException(status_code=404, detail="Exam seating profile not found")


def _room_type_value(value):
    return getattr(value, "value", value)


def _course_visible_to_exam_user(db: Session, current_user: User, course: Course) -> bool:
    if current_user.role in [UserRole.COORDINATOR, UserRole.SCHOOL_COORDINATOR, UserRole.TENANT_ADMIN, UserRole.SUPERADMIN]:
        return True
    if current_user.role != UserRole.HOD or current_user.department_id is None:
        return False

    dept_id = current_user.department_id
    if course.department_id == dept_id:
        return True

    gen_dept = find_general_department(db)
    gen_dept_id = gen_dept.id if gen_dept else -1
    dept_shared = dept_id in (course.shared_with_department_ids or [])

    if dept_id == gen_dept_id:
        return dept_shared

    if course.department_id == gen_dept_id:
        return is_general_department(getattr(course, "department", None)) and (
            course.shared_with_department_ids is None or dept_shared
        )

    return dept_shared


def _course_manageable_by_exam_user(current_user: User, course: Course) -> bool:
    if current_user.role in {UserRole.COORDINATOR, UserRole.SCHOOL_COORDINATOR, UserRole.TENANT_ADMIN}:
        return True
    return current_user.role == UserRole.HOD and current_user.department_id == course.department_id


def build_exam_paper_candidates(db: Session, period: ExamPeriod, current_user: User) -> List[ExamPaperCandidate]:
    from ..routers.groups import _effective_course_ids_for_group
    mapping_service = CourseMappingService(db)
    existing_papers = {
        paper.course_id: paper
        for paper in period.papers
        if paper.course_id is not None
    }

    courses = (
        filter_course_query_for_user(db.query(Course), current_user)
        .filter(Course.department.has(university_id=period.university_id))
        .order_by(Course.level.asc(), Course.code.asc())
        .all()
    )

    all_uni_groups = db.query(StudentGroup).filter(StudentGroup.university_id == period.university_id).all()
    parents_with_streams = {
        g.parent_group_id for g in all_uni_groups if getattr(g.group_type, "value", str(g.group_type)) == "stream" and g.parent_group_id
    }
    
    valid_groups = []
    for g in all_uni_groups:
        g_type = getattr(g.group_type, "value", str(g.group_type)) if g.group_type else None
        if g_type == "stream":
            valid_groups.append(g)
        elif g.parent_group_id is None and g_type in ["general", "department", None]:
            if g.id not in parents_with_streams:
                valid_groups.append(g)

    group_courses = {
        g.id: _effective_course_ids_for_group(db, g)
        for g in valid_groups
    }

    candidates: List[ExamPaperCandidate] = []
    for course in courses:
        if not _course_visible_to_exam_user(db, current_user, course):
            continue

        selected_groups = [g for g in valid_groups if course.id in group_courses.get(g.id, set())]
        if not selected_groups:
            continue

        selected_group_ids = [g.id for g in selected_groups]
        candidate_count = sum(int(group.size or 0) for group in selected_groups)
        existing_paper = existing_papers.get(course.id)

        candidates.append(
            ExamPaperCandidate(
                course_id=course.id,
                course_code=course.code,
                course_name=course.name,
                course_level=course.level,
                department_id=course.department_id,
                department_name=course.department.name if course.department else None,
                preferred_room_type=_room_type_value(course.preferred_room_type),
                candidate_count=candidate_count,
                group_ids=selected_group_ids,
                groups=[
                    ExamPaperCandidateGroup(
                        id=group.id,
                        name=group.name,
                        size=int(group.size or 0),
                        level=int(group.level or 0),
                        department_id=group.department_id,
                        department_name=group.department.name if group.department else None,
                    )
                    for group in selected_groups
                ],
                ownership_kind="owner" if course.department_id == current_user.department_id else "shared",
                can_manage=_course_manageable_by_exam_user(current_user, course),
                already_included=existing_paper is not None,
                existing_paper_id=existing_paper.id if existing_paper else None,
                existing_paper_code=existing_paper.paper_code if existing_paper else None,
                existing_paper_name=existing_paper.paper_name if existing_paper else None,
                existing_duration_minutes=existing_paper.duration_minutes if existing_paper else None,
                existing_max_rooms=existing_paper.max_rooms if existing_paper else None,
                existing_preferred_seating_profile_id=(
                    existing_paper.preferred_seating_profile_id if existing_paper else None
                ),
            )
        )

    return candidates


@router.get("/periods", response_model=List[ExamPeriodSchema])
async def get_exam_periods(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    university_id = resolve_university_id(db, current_user)
    return (
        db.query(ExamPeriod)
        .options(
            selectinload(ExamPeriod.session_windows),
            selectinload(ExamPeriod.papers),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.room_allocations).selectinload(ExamSlotRoom.room),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.room_allocations).selectinload(ExamSlotRoom.seating_profile),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.paper),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.session_window),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.seating_profile),
            selectinload(ExamPeriod.slots).selectinload(ExamSlot.chief_invigilator),
        )
        .filter(ExamPeriod.university_id == university_id)
        .order_by(ExamPeriod.start_date.desc(), ExamPeriod.id.desc())
        .all()
    )


@router.post("/periods", response_model=ExamPeriodSchema, status_code=status.HTTP_201_CREATED)
async def create_exam_period(
    request: Request,
    payload: ExamPeriodCreate,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    period = ExamPeriod(
        university_id=resolve_university_id(db, current_user),
        name=payload.name,
        semester=payload.semester,
        year=payload.year,
        start_date=payload.start_date,
        end_date=payload.end_date,
        constraint_settings=payload.constraint_settings.model_dump() if payload.constraint_settings else None,
        created_at=datetime.utcnow(),
        created_by_id=current_user.id,
    )
    errors = ExamValidationService(db).validate_period(period)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    db.add(period)
    db.commit()
    db.refresh(period)

    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="CREATE",
        resource_type="exam_period",
        resource_id=period.id,
        details={"name": period.name, "semester": period.semester, "year": period.year},
    )
    return period


@router.get("/periods/{period_id}", response_model=ExamPeriodSchema)
async def get_exam_period(
    period_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_period_or_404(db, current_user, period_id)


@router.put("/periods/{period_id}", response_model=ExamPeriodSchema)
async def update_exam_period(
    request: Request,
    period_id: int,
    payload: ExamPeriodUpdate,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    period = get_period_or_404(db, current_user, period_id)
    if period.is_locked:
        raise HTTPException(status_code=409, detail="Exam period is locked")

    updates = payload.model_dump(exclude_unset=True)
    if "constraint_settings" in updates and updates["constraint_settings"] is not None:
        updates["constraint_settings"] = payload.constraint_settings.model_dump()
    for field, value in updates.items():
        setattr(period, field, value)

    errors = ExamValidationService(db).validate_period(period)
    if errors:
        db.rollback()
        raise HTTPException(status_code=422, detail=errors)

    db.commit()
    db.refresh(period)
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UPDATE",
        resource_type="exam_period",
        resource_id=period.id,
        details={"updated_fields": list(updates.keys())},
    )
    return period


@router.delete("/periods/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam_period(
    request: Request,
    period_id: int,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    period = get_period_or_404(db, current_user, period_id)
    if period.is_locked or period.is_published:
        raise HTTPException(status_code=409, detail="Published or locked exam periods cannot be deleted")
    period_name = period.name
    slot_ids = [slot.id for slot in (period.slots or [])]

    if slot_ids:
        db.query(ExamSlotRoom).filter(ExamSlotRoom.exam_slot_id.in_(slot_ids)).delete(synchronize_session=False)
        db.query(ExamSlot).filter(ExamSlot.id.in_(slot_ids)).delete(synchronize_session=False)

    db.query(ExamPaper).filter(ExamPaper.exam_period_id == period.id).delete(synchronize_session=False)
    db.query(ExamSessionWindow).filter(ExamSessionWindow.exam_period_id == period.id).delete(synchronize_session=False)
    db.query(ExamPeriod).filter(ExamPeriod.id == period.id).delete(synchronize_session=False)
    db.commit()
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="DELETE",
        resource_type="exam_period",
        resource_id=period_id,
        details={"name": period_name},
    )


@router.post("/periods/{period_id}/session-windows", response_model=ExamSessionWindowSchema, status_code=status.HTTP_201_CREATED)
async def create_session_window(
    request: Request,
    period_id: int,
    payload: ExamSessionWindowCreate,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    period = get_period_or_404(db, current_user, period_id)
    if period.is_locked:
        raise HTTPException(status_code=409, detail="Exam period is locked")

    session_window = ExamSessionWindow(exam_period_id=period.id, **payload.model_dump())
    errors = ExamValidationService(db).validate_session_window(session_window)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    db.add(session_window)
    db.commit()
    db.refresh(session_window)
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="CREATE",
        resource_type="exam_session_window",
        resource_id=session_window.id,
        details={"period_id": period.id, "name": session_window.name},
    )
    return session_window


@router.put("/session-windows/{session_window_id}", response_model=ExamSessionWindowSchema)
async def update_session_window(
    request: Request,
    session_window_id: int,
    payload: ExamSessionWindowUpdate,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    session_window = db.query(ExamSessionWindow).filter(ExamSessionWindow.id == session_window_id).first()
    if not session_window:
        raise HTTPException(status_code=404, detail="Exam session window not found")
    period = get_period_or_404(db, current_user, session_window.exam_period_id)
    if period.is_locked:
        raise HTTPException(status_code=409, detail="Exam period is locked")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(session_window, field, value)

    errors = ExamValidationService(db).validate_session_window(session_window)
    if errors:
        db.rollback()
        raise HTTPException(status_code=422, detail=errors)

    db.commit()
    db.refresh(session_window)
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UPDATE",
        resource_type="exam_session_window",
        resource_id=session_window.id,
        details={"updated_fields": list(updates.keys())},
    )
    return session_window


@router.get("/seating-profiles", response_model=List[ExamSeatingProfileSchema])
async def get_seating_profiles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    university_id = resolve_university_id(db, current_user)
    return (
        db.query(ExamSeatingProfile)
        .filter(ExamSeatingProfile.university_id == university_id)
        .order_by(ExamSeatingProfile.is_default.desc(), ExamSeatingProfile.name.asc())
        .all()
    )


@router.post("/seating-profiles", response_model=ExamSeatingProfileSchema, status_code=status.HTTP_201_CREATED)
async def create_seating_profile(
    request: Request,
    payload: ExamSeatingProfileCreate,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    university_id = resolve_university_id(db, current_user)
    if payload.is_default:
        db.query(ExamSeatingProfile).filter(ExamSeatingProfile.university_id == university_id).update({"is_default": False})

    profile = ExamSeatingProfile(university_id=university_id, **payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="CREATE",
        resource_type="exam_seating_profile",
        resource_id=profile.id,
        details={"name": profile.name},
    )
    return profile


@router.put("/seating-profiles/{profile_id}", response_model=ExamSeatingProfileSchema)
async def update_seating_profile(
    request: Request,
    profile_id: int,
    payload: ExamSeatingProfileUpdate,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    profile = db.query(ExamSeatingProfile).filter(ExamSeatingProfile.id == profile_id).first()
    ensure_profile_access(profile, current_user, db)

    updates = payload.model_dump(exclude_unset=True)
    if updates.get("is_default"):
        db.query(ExamSeatingProfile).filter(
            ExamSeatingProfile.university_id == profile.university_id,
            ExamSeatingProfile.id != profile.id,
        ).update({"is_default": False})
    for field, value in updates.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UPDATE",
        resource_type="exam_seating_profile",
        resource_id=profile.id,
        details={"updated_fields": list(updates.keys())},
    )
    return profile


@router.post("/periods/{period_id}/papers", response_model=ExamPaperSchema, status_code=status.HTTP_201_CREATED)
async def create_exam_paper(
    request: Request,
    period_id: int,
    payload: ExamPaperCreate,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    period = get_period_or_404(db, current_user, period_id)
    if period.is_locked:
        raise HTTPException(status_code=409, detail="Exam period is locked")

    if payload.course_id and not db.query(Course).filter(Course.id == payload.course_id).first():
        raise HTTPException(status_code=422, detail="Invalid course_id")

    groups = filter_group_query_for_user(
        db.query(StudentGroup), current_user
    ).filter(StudentGroup.id.in_(payload.group_ids)).all() if payload.group_ids else []
    if len(groups) != len(set(payload.group_ids)):
        raise HTTPException(status_code=422, detail="One or more group_ids are invalid")

    paper = ExamPaper(exam_period_id=period.id, **payload.model_dump())
    errors = ExamValidationService(db).validate_paper(period, paper)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    db.add(paper)
    db.commit()
    db.refresh(paper)
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="CREATE",
        resource_type="exam_paper",
        resource_id=paper.id,
        details={"paper_code": paper.paper_code, "period_id": period.id},
    )
    return paper


@router.put("/papers/{paper_id}", response_model=ExamPaperSchema)
async def update_exam_paper(
    request: Request,
    paper_id: int,
    payload: ExamPaperUpdate,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Exam paper not found")
    period = get_period_or_404(db, current_user, paper.exam_period_id)
    if period.is_locked:
        raise HTTPException(status_code=409, detail="Exam period is locked")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(paper, field, value)

    errors = ExamValidationService(db).validate_paper(period, paper)
    if errors:
        db.rollback()
        raise HTTPException(status_code=422, detail=errors)

    db.commit()
    db.refresh(paper)
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UPDATE",
        resource_type="exam_paper",
        resource_id=paper.id,
        details={"updated_fields": list(updates.keys())},
    )
    return paper


@router.get("/periods/{period_id}/paper-candidates", response_model=List[ExamPaperCandidate])
async def get_exam_paper_candidates(
    period_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    period = get_period_or_404(db, current_user, period_id)
    return build_exam_paper_candidates(db, period, current_user)


@router.post("/periods/{period_id}/sync-papers", response_model=ExamPaperSyncResponse)
async def sync_exam_papers(
    request: Request,
    period_id: int,
    payload: ExamPaperSyncRequest,
    current_user: User = Depends(get_current_active_hod),
    db: Session = Depends(get_db),
):
    period = get_period_or_404(db, current_user, period_id)
    if period.is_locked:
        raise HTTPException(status_code=409, detail="Exam period is locked")

    if payload.default_duration_minutes <= 0:
        raise HTTPException(status_code=422, detail="default_duration_minutes must be greater than zero")
    if payload.default_max_rooms <= 0:
        raise HTTPException(status_code=422, detail="default_max_rooms must be greater than zero")

    selected_course_ids = sorted({int(course_id) for course_id in payload.course_ids})
    candidates = build_exam_paper_candidates(db, period, current_user)
    candidate_map = {candidate.course_id: candidate for candidate in candidates}
    invalid_course_ids = [course_id for course_id in selected_course_ids if course_id not in candidate_map]
    if invalid_course_ids:
        raise HTTPException(status_code=422, detail=f"Invalid or unmapped course_ids: {invalid_course_ids}")

    if payload.preferred_seating_profile_id is not None:
        profile = db.query(ExamSeatingProfile).filter(
            ExamSeatingProfile.id == payload.preferred_seating_profile_id
        ).first()
        ensure_profile_access(profile, current_user, db)

    manageable_candidate_ids = {
        candidate.course_id
        for candidate in candidates
        if candidate.can_manage
    }
    existing_papers = {
        paper.course_id: paper
        for paper in period.papers
        if paper.course_id is not None
    }
    removable_papers = [
        paper
        for paper in period.papers
        if (
            paper.course_id is not None
            and paper.course_id in manageable_candidate_ids
            and paper.course_id not in selected_course_ids
        )
    ]

    if current_user.role == UserRole.HOD:
        unmanaged_selected_ids = [course_id for course_id in selected_course_ids if course_id not in manageable_candidate_ids]
        if unmanaged_selected_ids:
            raise HTTPException(status_code=403, detail="You can only mark papers for courses owned by your department.")

    created_count = 0
    updated_count = 0
    removed_count = 0

    for paper in removable_papers:
        for slot in db.query(ExamSlot).filter(ExamSlot.exam_paper_id == paper.id).all():
            db.delete(slot)
        db.delete(paper)
        removed_count += 1

    for course_id in selected_course_ids:
        candidate = candidate_map[course_id]
        if not candidate.can_manage:
            if current_user.role == UserRole.HOD:
                continue
        paper = existing_papers.get(course_id)
        if paper is None:
            paper = ExamPaper(
                exam_period_id=period.id,
                course_id=course_id,
                paper_code=candidate.course_code,
                paper_name=candidate.course_name,
                duration_minutes=payload.default_duration_minutes,
                candidate_count=candidate.candidate_count,
                group_ids=candidate.group_ids,
                preferred_room_type=candidate.preferred_room_type,
                preferred_seating_profile_id=payload.preferred_seating_profile_id,
                max_rooms=payload.default_max_rooms,
                allow_custom_window=payload.allow_custom_window,
                metadata_json={"source": "course_sync"},
            )
            errors = ExamValidationService(db).validate_paper(period, paper)
            if errors:
                raise HTTPException(status_code=422, detail=errors)
            db.add(paper)
            created_count += 1
            continue

        paper.group_ids = candidate.group_ids
        paper.candidate_count = candidate.candidate_count
        if not paper.preferred_room_type and candidate.preferred_room_type:
            paper.preferred_room_type = candidate.preferred_room_type
        if payload.preferred_seating_profile_id is not None and paper.preferred_seating_profile_id is None:
            paper.preferred_seating_profile_id = payload.preferred_seating_profile_id
        if paper.max_rooms is None:
            paper.max_rooms = payload.default_max_rooms
        if not paper.duration_minutes:
            paper.duration_minutes = payload.default_duration_minutes
        errors = ExamValidationService(db).validate_paper(period, paper)
        if errors:
            raise HTTPException(status_code=422, detail=errors)
        updated_count += 1

    db.commit()
    db.refresh(period)
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="SYNC",
        resource_type="exam_papers",
        resource_id=period.id,
        details={
            "selected_count": len(selected_course_ids),
            "created_count": created_count,
            "updated_count": updated_count,
            "removed_count": removed_count,
        },
    )
    return ExamPaperSyncResponse(
        selected_count=len(selected_course_ids),
        created_count=created_count,
        updated_count=updated_count,
        removed_count=removed_count,
    )


@router.get("/periods/{period_id}/slots", response_model=List[ExamSlotSchema])
async def get_exam_slots(
    period_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    period = get_period_or_404(db, current_user, period_id)
    return period.slots


@router.delete("/periods/{period_id}/slots", status_code=status.HTTP_204_NO_CONTENT)
async def clear_exam_draft_slots(
    request: Request,
    period_id: int,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    period = get_period_or_404(db, current_user, period_id)
    if period.is_locked or period.is_published:
        raise HTTPException(status_code=409, detail="Published or locked exam periods cannot have their draft cleared")

    cleared_slots = len(period.slots or [])
    for slot in list(period.slots):
        db.delete(slot)

    period.generation_metadata = None
    db.commit()
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="CLEAR_DRAFT",
        resource_type="exam_period",
        resource_id=period.id,
        details={"cleared_slots": cleared_slots},
    )


@router.post("/periods/{period_id}/generate")
async def generate_exam_timetable(
    request: Request,
    period_id: int,
    payload: ExamGenerateRequest,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    period = get_period_or_404(db, current_user, period_id)
    quota_info = enforce_generation_quota(db, getattr(current_user, "university_id", None))
    generator = ExamTimetableGenerator(db, period.id)
    try:
        result = generator.generate(replace_existing=payload.replace_existing)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if quota_info and isinstance(result, dict):
        result["quota"] = quota_info

    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="GENERATE",
        resource_type="exam_period",
        resource_id=period.id,
        details=result,
    )
    return result


@router.post("/periods/{period_id}/publish", response_model=ExamPeriodSchema)
async def publish_exam_timetable(
    request: Request,
    period_id: int,
    payload: ExamPublishRequest,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    period = get_period_or_404(db, current_user, period_id)
    if not period.slots:
        raise HTTPException(status_code=422, detail="Generate the exam timetable before publishing")
    if period.is_published:
        raise HTTPException(status_code=409, detail="Exam period is already published")

    scheduled_paper_ids = {slot.exam_paper_id for slot in (period.slots or [])}
    unscheduled_papers = [
        paper
        for paper in (period.papers or [])
        if paper.id not in scheduled_paper_ids
    ]
    if unscheduled_papers:
        raise HTTPException(
            status_code=422,
            detail="Resolve all unscheduled papers before publishing the exam timetable",
        )

    period.is_published = True
    period.published_at = datetime.utcnow()
    if payload.lock_after_publish:
        period.is_locked = True
    for slot in period.slots:
        slot.status = "published"

    db.commit()
    db.refresh(period)
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="PUBLISH",
        resource_type="exam_period",
        resource_id=period.id,
        details={"lock_after_publish": payload.lock_after_publish},
    )
    NotificationService(db).notify_coordinators(
        title="Exam Timetable Published",
        message=f"{current_user.username} published the exam timetable for {period.name}.",
        type="success",
    )
    return period


@router.post("/periods/{period_id}/unpublish", response_model=ExamPeriodSchema)
async def unpublish_exam_timetable(
    request: Request,
    period_id: int,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db),
):
    period = get_period_or_404(db, current_user, period_id)
    if not period.is_published:
        raise HTTPException(status_code=409, detail="Exam period is not published")

    period.is_published = False
    period.published_at = None
    period.is_locked = False
    for slot in period.slots:
        slot.status = "draft"

    db.commit()
    db.refresh(period)
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UNPUBLISH",
        resource_type="exam_period",
        resource_id=period.id,
        details={},
    )
    return period

