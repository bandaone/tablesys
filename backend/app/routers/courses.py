from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import difflib
import re
import pandas as pd
import io
from ..database import get_db
from ..schemas import (
    Course, CourseCreate, CourseUpdate, CourseEnrollmentMapping, CourseEnrollmentUpdate
)
from ..models import Course as CourseModel, User, UserRole, Department
from ..auth import get_current_user, get_current_active_coordinator, get_current_active_hod
from ..config import settings
from ..utils.sanitization import sanitize_input
from ..utils.audit_logger import AuditLogger
from ..services.notification_service import NotificationService
from ..services.course_mapping_service import CourseMappingService
from ..utils.bulk_import_helpers import (
    resolve_department_id, ffill_department_columns, normalize_column_names, safe_int
)
from ..utils.department_utils import find_general_department, is_general_department

router = APIRouter(prefix="/api/v1/courses", tags=["courses"])


def _can_manage_course_enrollment(current_user: User, course: CourseModel) -> bool:
    if current_user.role == UserRole.COORDINATOR:
        return True
    if current_user.role == UserRole.HOD and current_user.department_id == course.department_id:
        return True
    return False

# Validation helpers
def validate_course_fields(code: str, name: str, level: int, credits: int, lecture_hours: int, 
                          tutorial_hours: int, practical_hours: int) -> Optional[dict]:
    """Validate course field values. Returns error dict if invalid, None if valid."""
    if not code or len(code.strip()) == 0:
        return {"detail": "Course code cannot be empty", "field": "code"}
    if len(code) > 20:
        return {"detail": "Course code must be 20 characters or less", "field": "code"}
    if not name or len(name.strip()) == 0:
        return {"detail": "Course name cannot be empty", "field": "name"}
    if len(name) > 200:
        return {"detail": "Course name must be 200 characters or less", "field": "name"}
    if level not in [1, 2, 3, 4, 5, 6, 7]:
        return {"detail": "Level must be 1, 2, 3, 4, 5, 6, or 7", "field": "level"}
    if credits < 1 or credits > 12:
        return {"detail": "Credits must be between 1 and 12", "field": "credits"}
    if lecture_hours < 0 or lecture_hours > 10:
        return {"detail": "Lecture hours must be between 0 and 10", "field": "lecture_hours"}
    if tutorial_hours < 0 or tutorial_hours > 10:
        return {"detail": "Tutorial hours must be between 0 and 10", "field": "tutorial_hours"}
    if practical_hours < 0 or practical_hours > 10:
        return {"detail": "Practical hours must be between 0 and 10", "field": "practical_hours"}
    total_hours = lecture_hours + tutorial_hours + practical_hours
    if total_hours == 0:
        return {"detail": "Total hours (lecture + tutorial + practical) must be at least 1", "field": "lecture_hours"}
    if total_hours > 15:
        return {"detail": "Total hours (lecture + tutorial + practical) cannot exceed 15", "field": "lecture_hours"}
    return None

@router.get("/", response_model=List[Course])
async def get_courses(
    skip: int = 0,
    limit: int = 1000,
    level: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Shared-course visibility rules (level-strict for consumers, owner-based for owners):
    - Own dept HOD: own courses + GEN universal/targeted + cross-dept shared with them
    - GEN HOD: all GEN-owned courses, plus any other courses explicitly shared with GEN
    - Coordinator/Admin: all courses
    """
    from sqlalchemy import or_, and_, cast
    from sqlalchemy.dialects.postgresql import JSONB

    query = db.query(CourseModel)

    # Tenant isolation
    if current_user.university_id:
        query = query.join(Department).filter(
            Department.university_id == current_user.university_id
        )

    if current_user.role == UserRole.HOD and current_user.department_id is not None:
        dept_id = current_user.department_id

        # Resolve General Engineering regardless of local code (GEN/ENG).
        gen_dept = find_general_department(db)
        gen_dept_id = gen_dept.id if gen_dept else -1

        if dept_id == gen_dept_id:
            # GEN owns service courses that may target other departments'
            # cohorts even when GEN itself has no cohort at that level.
            dept_in_shared = cast(CourseModel.shared_with_department_ids, JSONB).contains([dept_id])
            query = query.filter(
                or_(
                    CourseModel.department_id == dept_id,
                    dept_in_shared,
                )
            )
        else:
            # Regular dept HOD: own + GEN shared + cross-dept shared (all level-strict)
            dept_in_shared = cast(CourseModel.shared_with_department_ids, JSONB).contains([dept_id])
            query = query.filter(
                or_(
                    # (a) Own dept courses
                    CourseModel.department_id == dept_id,
                    # (b) GEN universal (null = all depts take it) or GEN targeted at this dept
                    and_(
                        CourseModel.department_id == gen_dept_id,
                        or_(
                            CourseModel.shared_with_department_ids.is_(None),
                            dept_in_shared
                        )
                    ),
                    # (c) Any other dept's course explicitly shared with this dept
                    and_(
                        CourseModel.department_id != dept_id,
                        CourseModel.department_id != gen_dept_id,
                        dept_in_shared
                    )
                )
            )

    # Optional level filter — normalise 400 → 4 etc.
    if level is not None:
        normalised = level if level <= 7 else level // 100
        query = query.filter(CourseModel.level == normalised)

    return query.offset(skip).limit(limit).all()


@router.get("/{course_id}", response_model=Course)
async def get_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific course."""
    course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # HODs can view courses in their department or general courses (dept_id=0)
    if current_user.role == UserRole.HOD:
        if course.department_id != 0 and course.department_id != current_user.department_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return course


@router.get("/{course_id}/enrollment-map", response_model=CourseEnrollmentMapping)
async def get_course_enrollment_map(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return the main-group enrolment truth for a course plus lecture delivery mode."""
    course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Reuse course visibility semantics from the page itself.
    if current_user.role == UserRole.HOD and course.department_id != current_user.department_id:
        gen_dept = find_general_department(db)
        gen_dept_id = gen_dept.id if gen_dept else -1
        dept_shared = current_user.department_id in (course.shared_with_department_ids or [])
        if not (
            course.department_id == gen_dept_id
            or dept_shared
        ):
            raise HTTPException(status_code=403, detail="Access denied")

    mapping_service = CourseMappingService(db)
    eligible_groups = mapping_service.eligible_main_groups_for_course(course)
    eligible_group_ids = [item.group.id for item in eligible_groups]
    selected_group_ids = mapping_service.current_selected_main_group_ids(course, eligible_group_ids)
    selected_lookup = set(selected_group_ids)

    return {
        "course_id": course.id,
        "course_code": course.code,
        "course_name": course.name,
        "course_department_id": course.department_id,
        "course_department_name": course.department.name if course.department else None,
        "lecture_mode": mapping_service.current_lecture_mode(course, selected_group_ids),
        "selected_group_ids": selected_group_ids,
        "eligible_groups": [
            {
                "id": item.group.id,
                "name": item.group.name,
                "display_code": item.group.display_code,
                "level": item.group.level,
                "size": item.group.size,
                "department_id": item.group.department_id,
                "department_name": item.group.department.name if item.group.department else None,
                "department_code": item.group.department.code if item.group.department else None,
                "ownership_kind": item.ownership_kind,
                "selected": item.group.id in selected_lookup,
            }
            for item in eligible_groups
        ],
        "stream_mapping_note": (
            "Main-cohort enrolment is managed here. Stream-specific electives and exclusions stay on the Groups page."
        ),
    }


@router.put("/{course_id}/enrollment-map", response_model=CourseEnrollmentMapping)
async def update_course_enrollment_map(
    request: Request,
    course_id: int,
    payload: CourseEnrollmentUpdate,
    current_user: User = Depends(get_current_active_hod),
    db: Session = Depends(get_db)
):
    """
    Update the course-side source of truth for main-group enrolment and lecture delivery.

    Owner-department HODs and coordinators can manage this mapping. Shared target
    departments consume the mapping but do not control it from the course page.
    """
    course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if not _can_manage_course_enrollment(current_user, course):
        raise HTTPException(
            status_code=403,
            detail="Only the owning department HOD or a coordinator can manage this course enrolment.",
        )

    mapping_service = CourseMappingService(db)
    try:
        result = mapping_service.save_main_group_mapping(course, payload.group_ids, payload.lecture_mode)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))

    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UPDATE",
        resource_type="course_enrollment",
        resource_id=course_id,
        details={
            "course_code": course.code,
            "group_ids": payload.group_ids,
            "lecture_mode": result["lecture_mode"],
        }
    )
    NotificationService(db).notify_coordinators(
        title="Course Enrolment Updated",
        message=(
            f"{current_user.username} updated enrolment for {course.code} across "
            f"{result['selected_group_count']} main group(s)."
        ),
        type="info",
    )

    return await get_course_enrollment_map(course_id=course_id, current_user=current_user, db=db)

@router.post("/", response_model=Course, status_code=status.HTTP_201_CREATED)
async def create_course(
    request: Request,
    course: CourseCreate,
    current_user: User = Depends(get_current_active_hod),
    db: Session = Depends(get_db)
):
    """Create a new course. Coordinator or HOD."""
    # Validate field values
    validation_error = validate_course_fields(
        course.code, course.name, course.level, course.credits,
        course.lecture_hours, course.tutorial_hours, course.practical_hours
    )
    if validation_error:
        raise HTTPException(status_code=422, detail=validation_error["detail"])
    
    # Verify department exists if specified
    if course.department_id != 0:
        dept = db.query(Department).filter(Department.id == course.department_id).first()
        if not dept:
            raise HTTPException(status_code=422, detail=[{"loc": ["body", "department_id"], "msg": "Invalid department_id", "type": "value_error"}])
    
    # Check if course code already exists
    existing = db.query(CourseModel).filter(CourseModel.code == course.code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Course with code '{course.code}' already exists")
    
    # Sanitize inputs
    course_data = course.model_dump()
    course_data['code'] = sanitize_input(course.code, max_length=20)
    course_data['name'] = sanitize_input(course.name, max_length=200)
    
    db_course = CourseModel(**course_data)
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    
    # World Monitor & Notification Hub
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="CREATE",
        resource_type="course",
        resource_id=db_course.id,
        details={"course_code": db_course.code}
    )
    NotificationService(db).notify_coordinators(
        title="New Course Added",
        message=f"{current_user.username} has added course {db_course.code} ({db_course.name}).",
        type="info"
    )
    
    return db_course


@router.put("/{course_id}", response_model=Course)
async def update_course(
    request: Request,
    course_id: int,
    course_update: CourseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a course. Coordinator or HOD (within their department)."""
    # Only coordinators and HODs may edit courses
    allowed_roles = [UserRole.COORDINATOR, UserRole.HOD]
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Only coordinators and HODs can edit courses")

    db_course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    if current_user.role == UserRole.HOD and db_course.department_id != current_user.department_id:
        raise HTTPException(status_code=403, detail="Access denied. You can only update courses in your department.")
    
    update_data = course_update.model_dump(exclude_unset=True)
    
    # Build full course data for validation (merge existing with updates)
    current_data = {
        "code": db_course.code,
        "name": db_course.name,
        "level": db_course.level,
        "credits": db_course.credits,
        "lecture_hours": db_course.lecture_hours,
        "tutorial_hours": db_course.tutorial_hours,
        "practical_hours": db_course.practical_hours,
    }
    current_data.update(update_data)
    
    # Validate updated field values
    validation_error = validate_course_fields(
        current_data["code"], current_data["name"], current_data["level"],
        current_data["credits"], current_data["lecture_hours"],
        current_data["tutorial_hours"], current_data["practical_hours"]
    )
    if validation_error:
        raise HTTPException(status_code=422, detail=validation_error["detail"])
    
    # Verify department exists if being updated
    if "department_id" in update_data and update_data["department_id"] != 0:
        dept = db.query(Department).filter(Department.id == update_data["department_id"]).first()
        if not dept:
            raise HTTPException(status_code=422, detail="Invalid department_id")
    
    # Check for duplicate code if code is being updated
    if "code" in update_data and update_data["code"] != db_course.code:
        existing = db.query(CourseModel).filter(CourseModel.code == update_data["code"]).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Course with code '{update_data['code']}' already exists")
    
    # Sanitize string inputs
    if "code" in update_data:
        update_data["code"] = sanitize_input(update_data["code"], max_length=20)
    if "name" in update_data:
        update_data["name"] = sanitize_input(update_data["name"], max_length=200)
    
    for field, value in update_data.items():
        setattr(db_course, field, value)
    
    db.commit()
    db.refresh(db_course)
    
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UPDATE",
        resource_type="course",
        resource_id=db_course.id,
        details={"course_code": db_course.code, "updates": list(update_data.keys())}
    )
    
    return db_course

@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    request: Request,
    course_id: int,
    current_user: User = Depends(get_current_active_hod),
    db: Session = Depends(get_db)
):
    """Delete a course. Coordinator or HOD."""
    db_course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")

    if current_user.role == UserRole.HOD and db_course.department_id != current_user.department_id:
        raise HTTPException(status_code=403, detail="Access denied. You can only delete courses in your department.")
    
    # Delete related records first to avoid foreign key constraint violations
    from ..models import LecturerAssignment, GroupAssignment, TimetableSlot
    
    db.query(TimetableSlot).filter(TimetableSlot.course_id == course_id).delete()
    db.query(GroupAssignment).filter(GroupAssignment.course_id == course_id).delete()
    db.query(LecturerAssignment).filter(LecturerAssignment.course_id == course_id).delete()
    
    db.delete(db_course)
    db.commit()
    
    code = db_course.code
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="DELETE",
        resource_type="course",
        resource_id=course_id,
        details={"course_code": code}
    )
    NotificationService(db).notify_coordinators(
        title="Course Deleted",
        message=f"Course {code} was deleted by {current_user.username}.",
        type="warning"
    )
    
    return None

@router.delete("/", status_code=status.HTTP_200_OK)
async def delete_all_courses(
    request: Request,
    current_user: User = Depends(get_current_active_hod),
    db: Session = Depends(get_db)
):
    """Delete courses. Coordinator can delete all, HOD can delete their department courses."""
    try:
        from ..models import LecturerAssignment, GroupAssignment, TimetableSlot
        
        if current_user.role == UserRole.HOD:
            count = db.query(CourseModel).filter(CourseModel.department_id == current_user.department_id).count()
            
            courses = db.query(CourseModel).filter(CourseModel.department_id == current_user.department_id).all()
            course_ids = [c.id for c in courses]
            
            if course_ids:
                db.query(TimetableSlot).filter(TimetableSlot.course_id.in_(course_ids)).delete()
                db.query(GroupAssignment).filter(GroupAssignment.course_id.in_(course_ids)).delete()
                db.query(LecturerAssignment).filter(LecturerAssignment.course_id.in_(course_ids)).delete()
                db.query(CourseModel).filter(CourseModel.department_id == current_user.department_id).delete()
        else:
            count = db.query(CourseModel).count()
            
            # Delete related records first to avoid foreign key constraint violations
            
            # Delete all assignments and slots that reference courses
            db.query(TimetableSlot).delete()
            db.query(GroupAssignment).delete()
            db.query(LecturerAssignment).delete()
            
            # Now delete all courses
            db.query(CourseModel).delete()
            
        db.commit()
        
        AuditLogger.log_data_modification(
            request=request,
            user_id=current_user.id,
            username=current_user.username,
            operation="DELETE",
            resource_type="course_bulk",
            details={"count_deleted": count}
        )
        NotificationService(db).notify_coordinators(
            title="All Courses Cleared",
            message=f"A bulk clear of all {count} courses was executed by {current_user.username}.",
            type="warning"
        )
        
        return {"status": "success", "deleted": count, "message": f"Deleted {count} courses"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting courses. Please try again.")

@router.post("/bulk-upload", response_model=dict)
async def bulk_upload_courses(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_hod),
    db: Session = Depends(get_db)
):
    """
    Bulk upload courses from Excel/CSV file.
    Coordinators can upload for any department.
    HODs can only upload for their department.
    
    Expected columns: code, name, level, credits, lecture_hours
    Optional department columns (provide at least one): department_id, department_code, or department_name
    Optional hours: tutorial_hours, practical_hours
    """
    if file.content_type not in ["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")
    
    try:
        contents = await file.read()
        
        # Read file based on type
        if file.content_type == "text/csv":
            text = contents.decode("utf-8", errors="replace")
            if "\t" in text and text.count("\t") > text.count(","):
                sep = "\t"
            else:
                sep = ";" if text.count(";") > text.count(",") else ","
            df = pd.read_csv(io.StringIO(text), sep=sep)
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        # ── Normalise columns ──────────────────────────────────────────────
        column_aliases = {
            'course code': 'code',
            'course name': 'name',
            'year (level)': 'level',
            'year': 'level',
            'lecture hrs/wk': 'lecture_hours',
            'tutorial hrs/wk': 'tutorial_hours',
            'practical hrs/wk': 'practical_hours',
            'department code': 'department_code',
            'department name': 'department_name',
        }
        df = normalize_column_names(df, column_aliases)

        # Generic 'Department' column → dual-map
        if 'department' in df.columns and 'department_name' not in df.columns and 'department_code' not in df.columns:
            df['department_code'] = df['department']
            df['department_name'] = df['department']

        # Forward-fill department columns (Excel grouped-row style)
        df = ffill_department_columns(df)

        # ── Required column validation ─────────────────────────────────────
        required_columns = ['code', 'name', 'level', 'credits', 'lecture_hours']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"The uploaded file is missing required columns: {', '.join(missing_columns)}"
            )

        dept_columns = ['department_id', 'department_code', 'department_name', 'department']
        if not any(col in df.columns for col in dept_columns):
            raise HTTPException(
                status_code=400,
                detail="Must provide at least one department column: department_id, department_code, or department_name"
            )

        if 'tutorial_hours' not in df.columns:
            df['tutorial_hours'] = 0
        if 'practical_hours' not in df.columns:
            df['practical_hours'] = 0

        # ── Pre-fetch departments (single DB query) ────────────────────────
        departments = db.query(Department).all()
        dept_id_map   = {d.id: d.id for d in departments}
        dept_id_map[0] = 0
        dept_code_map = {d.code.upper(): d.id for d in departments if d.code}
        dept_name_map = {d.name.lower(): d.id for d in departments if d.name}
        general_dept = next((d for d in departments if is_general_department(d)), None)
        general_dept_id = general_dept.id if general_dept else 0
        dept_id_map[0] = general_dept_id
        dept_code_map['GEN'] = general_dept_id
        dept_code_map['ENG'] = general_dept_id

        created_count = 0
        skipped_count = 0
        errors = []

        for idx, row in df.iterrows():
            try:
                # ── Resolve department (shared, tenant-agnostic) ───────────
                resolved_dept_id = resolve_department_id(
                    row, departments, dept_id_map, dept_code_map, dept_name_map
                )

                if resolved_dept_id is None:
                    bad_val = str(row.get('department_code', row.get('department_name', row.get('department', 'MISSING'))))
                    errors.append(f"Row {idx + 2}: Could not match department '{bad_val}' to any department in the system.")
                    skipped_count += 1
                    continue

                # HODs restricted to their own department
                if current_user.role == UserRole.HOD:
                    if resolved_dept_id != 0 and resolved_dept_id != current_user.department_id:
                        errors.append(f"Row {idx + 2}: Access denied — not your department")
                        skipped_count += 1
                        continue

                # ── Course code ────────────────────────────────────────────
                code_val = str(row.get('code', '')).strip()
                if not code_val or code_val.lower() == 'nan':
                    errors.append(f"Row {idx + 2}: Missing course code")
                    skipped_count += 1
                    continue

                existing = db.query(CourseModel).filter(CourseModel.code == code_val.upper()).first()
                if existing:
                    skipped_count += 1
                    continue

                # ── Resolve shared_with departments column (optional) ──────
                shared_ids = None
                shared_raw = str(row.get('shared_with', row.get('shared_departments', ''))).strip()
                if shared_raw and shared_raw.lower() not in ('', 'nan', 'none'):
                    if shared_raw.upper() != 'ALL':
                        parsed_ids = []
                        for c in re.split(r'[,;/\s]+', shared_raw):
                            c = c.strip().upper()
                            if c in dept_code_map:
                                parsed_ids.append(dept_code_map[c])
                        shared_ids = parsed_ids if parsed_ids else None

                # ── Auto-set course_type ───────────────────────────────────
                _gen_id = general_dept.id if general_dept else -1
                from ..models import CourseType as CT
                _ctype = CT.GENERAL if resolved_dept_id == _gen_id else (CT.MULTI_DEPARTMENT if shared_ids else CT.DEPARTMENT_SPECIFIC)

                # ── Create course ──────────────────────────────────────────
                course = CourseModel(
                    code=sanitize_input(code_val, max_length=20).upper(),
                    name=sanitize_input(str(row.get('name', '')), max_length=200),
                    department_id=resolved_dept_id,
                    level=safe_int(row.get('level'), 1),
                    credits=safe_int(row.get('credits'), 3),
                    lecture_hours=safe_int(row.get('lecture_hours'), 2),
                    tutorial_hours=safe_int(row.get('tutorial_hours'), 0),
                    practical_hours=safe_int(row.get('practical_hours'), 0),
                    shared_with_department_ids=shared_ids,
                    course_type=_ctype,
                )
                db.add(course)
                created_count += 1
                
            except Exception as e:
                error_msg = str(e) if isinstance(e, ValueError) else "Database constraint or validation error"
                errors.append(f"Row {idx + 2}: {error_msg}")
                skipped_count += 1
        
        db.commit()
        
        # Log successful bulk upload
        AuditLogger.log_bulk_upload(
            request=request,
            user_id=current_user.id,
            username=current_user.username,
            resource_type="course",
            count=created_count,
            success=True,
            details={"filename": file.filename, "created": created_count, "skipped": skipped_count}
        )
        
        return {
            "status": "success",
            "created": created_count,
            "skipped": skipped_count,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        # Log failed bulk upload
        AuditLogger.log_bulk_upload(
            request=request,
            user_id=current_user.id,
            username=current_user.username,
            resource_type="course",
            count=0,
            success=False,
            details={"filename": file.filename, "error": str(e)}
        )
        if isinstance(e, HTTPException):
            raise e
        print(f"Bulk upload error: {str(e)}")
        raise HTTPException(status_code=400, detail="Could not process the uploaded file. Please check the format and try again.")

