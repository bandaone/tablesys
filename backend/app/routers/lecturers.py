from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import pandas as pd
import io
import re
from ..database import get_db
from ..schemas import Lecturer, LecturerCreate, LecturerUpdate
from ..models import UserRole, Lecturer as LecturerModel, User, Department, LecturerAssignment, Course
from ..auth import get_current_user, get_current_active_school_operator
from ..utils.sanitization import sanitize_input
from ..utils.audit_logger import AuditLogger
from ..services.notification_service import NotificationService
from ..utils.email_service import EmailService
from ..config import settings
from ..utils.bulk_import_helpers import resolve_department_id, ffill_department_columns, safe_int
from ..utils.school_scope import ensure_user_can_manage_department, filter_lecturer_query_for_user

router = APIRouter(prefix="/api/v1/lecturers", tags=["lecturers"])


def _append_issue(issue_summary: dict, key: str, message: str, limit: int = 8) -> None:
    bucket = issue_summary.setdefault(key, {"count": 0, "examples": []})
    bucket["count"] += 1
    if len(bucket["examples"]) < limit:
        bucket["examples"].append(message)


def normalize_staff_number(value: str) -> str:
    """Staff numbers are a platform-wide, case-insensitive identity."""
    return sanitize_input(str(value or "").strip(), max_length=50).upper()

# Validation helpers
def validate_lecturer_fields(staff_number: str, full_name: str, email: str, 
                            max_hours_per_week: int) -> Optional[dict]:
    """Validate lecturer field values. Returns error dict if invalid, None if valid."""
    if not staff_number or len(staff_number.strip()) == 0:
        return {"detail": "Staff number cannot be empty", "field": "staff_number"}
    if len(staff_number) > 50:
        return {"detail": "Staff number must be 50 characters or less", "field": "staff_number"}
    if not full_name or len(full_name.strip()) == 0:
        return {"detail": "Full name cannot be empty", "field": "full_name"}
    if len(full_name) > 200:
        return {"detail": "Full name must be 200 characters or less", "field": "full_name"}
    
    # Email validation
    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if email and not re.match(email_regex, email):
        return {"detail": "Invalid email format", "field": "email"}
    if email and len(email) > 200:
        return {"detail": "Email must be 200 characters or less", "field": "email"}
    
    if max_hours_per_week < 1 or max_hours_per_week > 40:
        return {"detail": "Max hours per week must be between 1 and 40", "field": "max_hours_per_week"}
    
    return None

@router.get("/", response_model=List[Lecturer])
async def get_lecturers(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all lecturers. HODs see only their department's lecturers."""
    from sqlalchemy.orm import joinedload
    from ..models import UserRole, LecturerAssignment
    
    query = db.query(LecturerModel).options(
        joinedload(LecturerModel.assignments).joinedload(LecturerAssignment.course)
    )
    query = filter_lecturer_query_for_user(query, current_user)
    
    lecturers = query.offset(skip).limit(limit).all()
    return lecturers

@router.post("/", response_model=Lecturer, status_code=status.HTTP_201_CREATED)
async def create_lecturer(
    request: Request,
    lecturer: LecturerCreate,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db)
):
    """Create a new lecturer. Coordinator only."""
    # Validate field values
    normalized_staff_number = normalize_staff_number(lecturer.staff_number)
    validation_error = validate_lecturer_fields(
        normalized_staff_number, lecturer.full_name, lecturer.email,
        lecturer.max_hours_per_week
    )
    if validation_error:
        raise HTTPException(status_code=422, detail=validation_error["detail"])
    
    # Verify department exists
    if lecturer.department_id:
        dept = ensure_user_can_manage_department(db, current_user, lecturer.department_id)
        if dept is None:
            raise HTTPException(status_code=422, detail="Invalid department_id")
    
    # Check for duplicates
    existing = db.query(LecturerModel).filter(
        (func.lower(LecturerModel.staff_number) == normalized_staff_number.lower()) |
        (LecturerModel.email == lecturer.email)
    ).first()
    
    if existing:
        if existing.staff_number.lower() == normalized_staff_number.lower():
            raise HTTPException(status_code=409, detail=f"Staff number '{normalized_staff_number}' is already assigned in TABLESYS")
        else:
            raise HTTPException(status_code=409, detail=f"Lecturer with email '{lecturer.email}' already exists")
    
    # Sanitize inputs
    lecturer_data = lecturer.model_dump()
    lecturer_data['staff_number'] = normalized_staff_number
    lecturer_data['full_name'] = sanitize_input(lecturer.full_name, max_length=200)
    if lecturer.email:
        lecturer_data['email'] = sanitize_input(lecturer.email, max_length=200)
    
    # Handle course_ids separately
    course_ids = lecturer_data.pop('course_ids', None)

    db_lecturer = LecturerModel(**lecturer_data)
    db.add(db_lecturer)
    db.flush() # Flush to get db_lecturer.id
    
    if course_ids:
        # verify courses exist and are part of the university
        if current_user.university_id:
            courses_query = db.query(Course).join(Department, Course.department_id == Department.id).filter(
                Course.id.in_(course_ids),
                Department.university_id == current_user.university_id
            )
            if getattr(current_user, "school_id", None) is not None and current_user.role != UserRole.TENANT_ADMIN:
                courses_query = courses_query.filter(Department.school_id == current_user.school_id)
        else:
            courses_query = db.query(Course).filter(Course.id.in_(course_ids))

        valid_courses = {c.id for c in courses_query.all()}

        for cid in set(course_ids):
            if cid in valid_courses:
                db.add(LecturerAssignment(
                    lecturer_id=db_lecturer.id,
                    course_id=cid,
                    session_type="lecture"
                ))

    db.commit()
    db.refresh(db_lecturer)

    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="CREATE",
        resource_type="lecturer",
        resource_id=db_lecturer.id,
        details={"staff_number": db_lecturer.staff_number, "full_name": db_lecturer.full_name}
    )
    NotificationService(db).notify_coordinators(
        title="New Lecturer Added",
        message=f"{current_user.username} has added lecturer {db_lecturer.full_name} ({db_lecturer.staff_number}).",
        type="info"
    )

    # Send welcome email if email is provided; track it to avoid duplicates
    if db_lecturer.email:
        assigned_courses = []
        if db_lecturer.id:
            from ..models import Course, LecturerAssignment
            assigned_courses_query = db.query(Course.code, Course.name).join(LecturerAssignment, LecturerAssignment.course_id == Course.id).filter(LecturerAssignment.lecturer_id == db_lecturer.id).all()
            assigned_courses = [f"{c[0]} - {c[1]}" for c in assigned_courses_query]

        sent = EmailService.send_lecturer_welcome_email(
            recipient=db_lecturer.email,
            user_name=db_lecturer.full_name,
            staff_number=db_lecturer.staff_number,
            login_url=f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3002')}/lecturer",
            assigned_courses=assigned_courses
        )
        if sent:
            db_lecturer.welcome_email_sent = True
            db.commit()

    return db_lecturer

@router.put("/{lecturer_id}", response_model=Lecturer)
async def update_lecturer(
    request: Request,
    lecturer_id: int,
    lecturer_update: LecturerUpdate,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db)
):
    """Update a lecturer. Coordinator only."""
    db_lecturer = filter_lecturer_query_for_user(
        db.query(LecturerModel), current_user
    ).filter(LecturerModel.id == lecturer_id).first()

    if not db_lecturer:
        raise HTTPException(status_code=404, detail="Lecturer not found")
    
    update_data = lecturer_update.model_dump(exclude_unset=True)
    if "staff_number" in update_data:
        update_data["staff_number"] = normalize_staff_number(update_data["staff_number"])
    
    # Build full lecturer data for validation (merge existing with updates)
    current_data = {
        "staff_number": db_lecturer.staff_number,
        "full_name": db_lecturer.full_name,
        "email": db_lecturer.email or "",
        "max_hours_per_week": db_lecturer.max_hours_per_week,
    }
    current_data.update(update_data)
    
    # Validate updated field values
    validation_error = validate_lecturer_fields(
        current_data["staff_number"], current_data["full_name"],
        current_data["email"], current_data["max_hours_per_week"]
    )
    if validation_error:
        raise HTTPException(status_code=422, detail=validation_error["detail"])
    
    # Verify department exists if being updated
    if "department_id" in update_data and update_data["department_id"]:
        dept = ensure_user_can_manage_department(db, current_user, update_data["department_id"])
        if dept is None:
            raise HTTPException(status_code=422, detail="Invalid department_id")
    
    # Check for duplicate staff_number if being updated
    if "staff_number" in update_data and update_data["staff_number"].lower() != db_lecturer.staff_number.lower():
        existing = db.query(LecturerModel).filter(
            func.lower(LecturerModel.staff_number) == update_data["staff_number"].lower(),
            LecturerModel.id != db_lecturer.id,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Staff number '{update_data['staff_number']}' is already assigned in TABLESYS")
    
    # Check for duplicate email if being updated
    if "email" in update_data and update_data["email"] != db_lecturer.email:
        existing = filter_lecturer_query_for_user(db.query(LecturerModel), current_user).filter(
            LecturerModel.email == update_data["email"]
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Lecturer with email '{update_data['email']}' already exists")
    
    # Sanitize string inputs
    if "full_name" in update_data:
        update_data["full_name"] = sanitize_input(update_data["full_name"], max_length=200)
    if "email" in update_data:
        update_data["email"] = sanitize_input(update_data["email"], max_length=200)
    
    course_ids = update_data.pop("course_ids", None)
    for field, value in update_data.items():
        setattr(db_lecturer, field, value)
    
    if course_ids is not None:
        # clear existing assignments
        db.query(LecturerAssignment).filter(LecturerAssignment.lecturer_id == db_lecturer.id).delete()
        
        # verify courses exist and are part of the university
        if current_user.university_id:
            courses_query = db.query(Course).join(Department, Course.department_id == Department.id).filter(
                Course.id.in_(course_ids),
                Department.university_id == current_user.university_id
            )
            if getattr(current_user, "school_id", None) is not None and current_user.role != UserRole.TENANT_ADMIN:
                courses_query = courses_query.filter(Department.school_id == current_user.school_id)
        else:
            courses_query = db.query(Course).filter(Course.id.in_(course_ids))
        
        valid_courses = {c.id for c in courses_query.all()}
        for cid in set(course_ids):
            if cid in valid_courses:
                db.add(LecturerAssignment(
                    lecturer_id=db_lecturer.id,
                    course_id=cid,
                    session_type="lecture"
                ))

    db.commit()
    db.refresh(db_lecturer)

    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UPDATE",
        resource_type="lecturer",
        resource_id=db_lecturer.id,
        details={"staff_number": db_lecturer.staff_number, "updates": list(update_data.keys())}
    )

    # If an email was just added and the welcome email has never been sent, send it now
    if db_lecturer.email and not db_lecturer.welcome_email_sent:
        assigned_courses = []
        if db_lecturer.id:
            from ..models import Course, LecturerAssignment
            assigned_courses_query = db.query(Course.code, Course.name).join(LecturerAssignment, LecturerAssignment.course_id == Course.id).filter(LecturerAssignment.lecturer_id == db_lecturer.id).all()
            assigned_courses = [f"{c[0]} - {c[1]}" for c in assigned_courses_query]

        sent = EmailService.send_lecturer_welcome_email(
            recipient=db_lecturer.email,
            user_name=db_lecturer.full_name,
            staff_number=db_lecturer.staff_number,
            login_url=f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3002')}/lecturer",
            assigned_courses=assigned_courses
        )
        if sent:
            db_lecturer.welcome_email_sent = True
            db.commit()

    return db_lecturer

@router.delete("/{lecturer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lecturer(
    request: Request,
    lecturer_id: int,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db)
):
    """Delete a lecturer. Coordinator only."""
    db_lecturer = filter_lecturer_query_for_user(
        db.query(LecturerModel), current_user
    ).filter(LecturerModel.id == lecturer_id).first()

    if not db_lecturer:
        raise HTTPException(status_code=404, detail="Lecturer not found")

    db.delete(db_lecturer)
    db.commit()
    
    name = db_lecturer.full_name
    staff_num = db_lecturer.staff_number
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="DELETE",
        resource_type="lecturer",
        resource_id=lecturer_id,
        details={"staff_number": staff_num}
    )
    NotificationService(db).notify_coordinators(
        title="Lecturer Deleted",
        message=f"Lecturer {name} ({staff_num}) was deleted by {current_user.username}.",
        type="warning"
    )
    
    return None

@router.delete("/", status_code=status.HTTP_200_OK)
async def delete_all_lecturers(
    request: Request,
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db)
):
    """Delete all lecturers. Coordinator only. Use before bulk re-upload."""
    query = filter_lecturer_query_for_user(db.query(LecturerModel), current_user)
        
    lecturers_to_delete = query.all()
    if not lecturers_to_delete:
        return {"status": "success", "deleted": 0, "message": "Deleted 0 lecturers"}
        
    lecturer_ids = [lec.id for lec in lecturers_to_delete]
    
    # Pre-flight check: timetable slots
    from ..models import UserRole, TimetableSlot, LecturerUnavailability
    slots_count = db.query(TimetableSlot).filter(TimetableSlot.lecturer_id.in_(lecturer_ids)).count()
    if slots_count > 0:
        raise HTTPException(
            status_code=400, 
            detail="Cannot clear lecturers because some are already scheduled in active timetables. Please clear generated timetables first."
        )
        
    # Delete dependent child objects safely
    db.query(LecturerAssignment).filter(LecturerAssignment.lecturer_id.in_(lecturer_ids)).delete(synchronize_session=False)
    db.query(LecturerUnavailability).filter(LecturerUnavailability.lecturer_id.in_(lecturer_ids)).delete(synchronize_session=False)
    
    # Finally, delete all lecturers for this tenant
    count = len(lecturer_ids)
    db.query(LecturerModel).filter(LecturerModel.id.in_(lecturer_ids)).delete(synchronize_session=False)
    
    db.commit()
    
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="DELETE",
        resource_type="lecturer_bulk",
        details={"count_deleted": count}
    )
    NotificationService(db).notify_coordinators(
        title="All Lecturers Cleared",
        message=f"A bulk clear of all {count} lecturers was executed by {current_user.username}.",
        type="warning"
    )
    
    return {"status": "success", "deleted": count, "message": f"Deleted {count} lecturers"}

@router.post("/bulk-upload", response_model=dict)
async def bulk_upload_lecturers(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db)
):
    """
    Bulk upload lecturers from CSV / Excel.

    Accepts the school's standard format:
        Staff Number | Full Name | Courses Responsible For | No. of Courses

    Also accepts the legacy format:
        staff_number | full_name | email | department_id | ...

    Column headers are matched case-insensitively.
    Staff Number can be any format (numeric, alphanumeric, e.g. L001, 2345, ENG-12).
    'Courses Responsible For' is parsed (comma or semicolon separated) and
    LecturerAssignment records are created automatically in the same upload.
    Department is optional — lecturer is saved without a department if not found.
    Existing lecturers (matched by staff_number) are updated, not duplicated.
    """
    if file.content_type not in [
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel"
    ]:
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")

    # ── Column alias map ─────────────────────────────────────────────────────
    _COL_ALIASES = {
        # staff number
        "staff number":          "staff_number",
        "staff_number":          "staff_number",
        "staffnumber":           "staff_number",
        "staff no":              "staff_number",
        "staff no.":             "staff_number",
        "employee number":       "staff_number",
        "employee id":           "staff_number",
        "id":                    "staff_number",
        # full name
        "full name":             "full_name",
        "full_name":             "full_name",
        "name":                  "full_name",
        "lecturer name":         "full_name",
        "lecturer":              "full_name",
        # email
        "email":                 "email",
        "email address":         "email",
        "e-mail":                "email",
        # department
        "department_id":         "department_id",
        "department id":         "department_id",
        "department_code":       "department_code",
        "department code":       "department_code",
        "dept code":             "department_code",
        "dept":                  "department_code",
        "department_name":       "department_name",
        "department name":       "department_name",
        "department":            "department_name",
        # courses
        "courses responsible for": "courses",
        "courses":               "courses",
        "course codes":          "courses",
        "course code":           "courses",
        "assigned courses":      "courses",
        "teaching":              "courses",
        # max hours
        "max_hours_per_week":    "max_hours",
        "max hours per week":    "max_hours",
        "max hours":             "max_hours",
        "hours per week":        "max_hours",
        # skip
        "no. of courses":        "__skip",
        "no of courses":         "__skip",
        "number of courses":     "__skip",
    }

    try:
        contents = await file.read()

        if file.content_type == "text/csv":
            text = contents.decode("utf-8", errors="replace")
            if "\t" in text and text.count("\t") > text.count(","):
                sep = "\t"
            else:
                sep = ";" if text.count(";") > text.count(",") else ","
            df = pd.read_csv(io.StringIO(text), sep=sep)
        else:
            df = pd.read_excel(io.BytesIO(contents))

        # Normalise and apply aliases
        df.columns = [c.strip().lower() for c in df.columns]
        rename_map = {col: _COL_ALIASES[col] for col in df.columns if col in _COL_ALIASES}
        df = df.rename(columns=rename_map)
        # Drop __skip columns
        df = df[[c for c in df.columns if c != "__skip"]]
        df = df.loc[:, ~df.columns.duplicated()]

        if "staff_number" not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="Cannot find a staff number column. Expected: 'Staff Number', 'staff_number', or 'Staff No.'"
            )
        if "full_name" not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="Cannot find a name column. Expected: 'Full Name', 'full_name', or 'Name'."
            )

        # Ensure optional columns exist as None
        for col in ("email", "department_id", "courses", "max_hours"):
            if col not in df.columns:
                df[col] = None

        # Pre-fetch departments
        dept_query = db.query(Department)
        if current_user.university_id:
            dept_query = dept_query.filter(Department.university_id == current_user.university_id)
        if getattr(current_user, "school_id", None) is not None and current_user.role != UserRole.TENANT_ADMIN:
            dept_query = dept_query.filter(Department.school_id == current_user.school_id)
        departments = dept_query.all()
        dept_id_map    = {d.id: d.id for d in departments}
        dept_code_map  = {d.code.upper(): d.id for d in departments if d.code}
        dept_name_map  = {d.name.lower(): d.id for d in departments if d.name}

        # Pre-fetch courses by code for fast assignment lookup
        courses_query = db.query(Course)
        if current_user.university_id:
            courses_query = courses_query.join(Department, Course.department_id == Department.id)\
                                         .filter(Department.university_id == current_user.university_id)
            if getattr(current_user, "school_id", None) is not None and current_user.role != UserRole.TENANT_ADMIN:
                courses_query = courses_query.filter(Department.school_id == current_user.school_id)
        all_courses = courses_query.all()
        # Shape courses natively by removing spaces, dashes, dots, and forcing upper
        course_code_map = {re.sub(r'[^A-Z0-9]', '', c.code.upper()): c.id for c in all_courses if c.code}
        created_count  = 0
        updated_count  = 0
        skipped_count  = 0
        assigned_count = 0
        errors: list[str] = []
        issue_summary: dict = {}

        for idx, row in df.iterrows():
            try:
                row_label = f"Row {idx + 2}"
                # ── Staff number: accept any format, stringify ────────────
                raw_staff = row.get("staff_number")
                if pd.isna(raw_staff) or str(raw_staff).strip() == "":
                    _append_issue(issue_summary, "missing_staff_number", f"{row_label}: Staff number is blank.")
                    skipped_count += 1
                    continue
                staff_number = str(raw_staff).strip()
                # If it came out as "12345.0" from numeric Excel cells, clean it
                if re.match(r'^\d+\.0$', staff_number):
                    staff_number = staff_number[:-2]
                staff_number = normalize_staff_number(staff_number)

                full_name = str(row.get("full_name", "")).strip()
                if not full_name:
                    message = f"{row_label}: Full name is empty."
                    errors.append(message)
                    _append_issue(issue_summary, "missing_full_name", message)
                    skipped_count += 1
                    continue

                # ── Email (optional) ─────────────────────────────────────
                email_val = str(row.get("email", "")).strip()
                if email_val.lower() == "nan" or email_val == "":
                    email_val = None

                # ── Department (shared, tenant-agnostic fuzzy resolver) ────
                resolved_dept_id = resolve_department_id(
                    row, departments, dept_id_map, dept_code_map, dept_name_map
                )
                
                # Check for existing
                existing = db.query(LecturerModel).filter(
                    func.lower(LecturerModel.staff_number) == staff_number.lower()
                ).first()

                # If creating new, department is strictly required by Postgres schema
                if not existing and resolved_dept_id is None:
                    raise ValueError("Missing or invalid department. Include a valid 'Department Name', 'Department Code', or 'Department ID'.")

                # ── Max hours ────────────────────────────────────────────
                max_hours = 20
                if pd.notna(row.get("max_hours")):
                    try:
                        max_hours = int(float(str(row["max_hours"]).replace(",", "")))
                    except Exception:
                        pass

                # ── Upsert lecturer ──────────────────────────────────────
                if existing:
                    existing.full_name = sanitize_input(full_name, max_length=200)
                    if email_val:
                        existing.email = sanitize_input(email_val, max_length=200)
                    if resolved_dept_id is not None:
                        existing.department_id = resolved_dept_id
                    existing.max_hours_per_week = max_hours
                    lecturer_obj = existing
                    updated_count += 1
                else:
                    lecturer_obj = LecturerModel(
                        staff_number=sanitize_input(staff_number, max_length=50),
                        full_name=sanitize_input(full_name, max_length=200),
                        email=sanitize_input(email_val, max_length=200) if email_val else None,
                        department_id=resolved_dept_id,
                        max_hours_per_week=max_hours,
                    )
                    db.add(lecturer_obj)
                    db.flush()  # get lecturer_obj.id before course assignment
                    created_count += 1

                # ── Assign courses from 'Courses Responsible For' ────────
                raw_courses = str(row.get("courses", "") or "").strip()
                if raw_courses and raw_courses.lower() not in ("nan", "none", "-", ""):
                    # Keep raw chunks for descriptive errors, use shaped text for map lookup
                    raw_chunks = [c.strip() for c in re.split(r'[,;]+', raw_courses) if c.strip()]
                    for original_code in raw_chunks:
                        clean_code = re.sub(r'[^A-Z0-9]', '', original_code.upper())
                        if not clean_code: continue
                        
                        course_id = course_code_map.get(clean_code)
                        if not course_id:
                            message = f"{row_label}: Course '{original_code}' was not found in the current courses list."
                            errors.append(message)
                            _append_issue(issue_summary, "missing_course_match", message)
                            continue
                        # Skip if assignment already exists
                        already = db.query(LecturerAssignment).filter(
                            LecturerAssignment.lecturer_id == lecturer_obj.id,
                            LecturerAssignment.course_id == course_id,
                        ).first()
                        if not already:
                            db.add(LecturerAssignment(
                                lecturer_id=lecturer_obj.id,
                                course_id=course_id,
                                session_type="lecture",
                            ))
                            assigned_count += 1

            except Exception as exc:
                row_label = f"Row {idx + 2}"
                error_msg = str(exc) if isinstance(exc, ValueError) else "Database constraint or validation error"
                message = f"{row_label}: {error_msg}"
                errors.append(message)
                issue_key = "invalid_department" if "department" in error_msg.lower() else "row_validation_error"
                _append_issue(issue_summary, issue_key, message)
                skipped_count += 1

        db.commit()

        # ── Send welcome emails post-commit ──────────────────────────────
        # Re-query so we have full DB state with IDs set
        missing_email_staff = []
        for idx, row in df.iterrows():
            raw_staff = row.get("staff_number", "")
            if not raw_staff or str(raw_staff).strip().lower() in ("nan", ""):
                continue
            sn = str(raw_staff).strip()
            if re.match(r"^\d+\.0$", sn):
                sn = sn[:-2]
            lecturer_obj = db.query(LecturerModel).filter(
                func.lower(LecturerModel.staff_number) == sn.lower()
            ).first()
            if not lecturer_obj:
                continue
            if not lecturer_obj.email:
                missing_email_staff.append(sn)
            elif not lecturer_obj.welcome_email_sent:
                assigned_courses = []
                if lecturer_obj.id:
                    from ..models import Course, LecturerAssignment
                    assigned_courses_query = db.query(Course.code, Course.name).join(LecturerAssignment, LecturerAssignment.course_id == Course.id).filter(LecturerAssignment.lecturer_id == lecturer_obj.id).all()
                    assigned_courses = [f"{c[0]} - {c[1]}" for c in assigned_courses_query]

                sent = EmailService.send_lecturer_welcome_email(
                    recipient=lecturer_obj.email,
                    user_name=lecturer_obj.full_name,
                    staff_number=lecturer_obj.staff_number,
                    login_url=f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3002')}/lecturer",
                    assigned_courses=assigned_courses
                )
                if sent:
                    lecturer_obj.welcome_email_sent = True
        db.commit()

        if missing_email_staff:
            _append_issue(
                issue_summary,
                "missing_email",
                f"{len(missing_email_staff)} lecturer(s) have no email — portal access link not sent: {', '.join(missing_email_staff[:8])}"
            )

        return {
            "status":   "success",
            "created":  created_count,
            "updated":  updated_count,
            "assigned": assigned_count,
            "skipped":  skipped_count,
            "issue_summary": issue_summary or None,
            "errors":   errors if errors else None,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Error processing file. Please ensure it is correctly formatted.")



@router.post("/bulk-assign-courses", response_model=dict)
async def bulk_assign_courses(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_school_operator),
    db: Session = Depends(get_db)
):
    """
    Bulk-assign lecturers to courses from a CSV or Excel file.

    Accepted column layouts (flexible — any combination works):

    Layout A — one row per assignment:
        staff_number | course_code | session_type (optional)

    Layout B — one row per lecturer with comma-separated codes:
        staff_number | full_name | courses              (e.g. "EEE311,EEE313,EEE315")

    Lecturer matching: tries staff_number first, then falls back to full_name.
    Course matching: by code (case-insensitive).
    Existing assignments are skipped (idempotent).

    Returns:
        assigned  - total new LecturerAssignment records created
        skipped   - already-existing pairs
        errors    - list of row-level issues
    """
    ALLOWED_TYPES = [
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ]
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")

    try:
        contents = await file.read()
        if file.content_type == "text/csv":
            text = contents.decode("utf-8", errors="replace")
            if "\t" in text and text.count("\t") > text.count(","):
                sep = "\t"
            else:
                sep = ";" if text.count(";") > text.count(",") else ","
            df = pd.read_csv(io.StringIO(text), sep=sep)
        else:
            df = pd.read_excel(io.BytesIO(contents))
        df.columns = [c.strip().lower() for c in df.columns]

        column_aliases = {
            "staff number": "staff_number",
            "staff_number": "staff_number",
            "staff no": "staff_number",
            "staff no.": "staff_number",
            "staffnumber": "staff_number",
            "full name": "full_name",
            "full_name": "full_name",
            "name": "full_name",
            "lecturer name": "full_name",
            "course code": "course_code",
            "course_code": "course_code",
            "course codes": "courses",
            "courses responsible for": "courses",
            "assigned courses": "courses",
            "courses": "courses",
            "session type": "session_type",
            "session_type": "session_type",
        }
        rename_map = {col: column_aliases[col] for col in df.columns if col in column_aliases}
        df = df.rename(columns=rename_map)
        df = df.loc[:, ~df.columns.duplicated()]

        # Build look-up caches
        all_lecturers = filter_lecturer_query_for_user(db.query(LecturerModel), current_user).all()
        lecturer_by_staff  = {l.staff_number.strip(): l for l in all_lecturers if l.staff_number}
        lecturer_by_name   = {l.full_name.strip().lower(): l for l in all_lecturers if l.full_name}

        courses_query = db.query(Course)
        if current_user.university_id:
            courses_query = courses_query.join(Department, Course.department_id == Department.id)\
                                         .filter(Department.university_id == current_user.university_id)
            if getattr(current_user, "school_id", None) is not None and current_user.role != UserRole.TENANT_ADMIN:
                courses_query = courses_query.filter(Department.school_id == current_user.school_id)
        all_courses = courses_query.all()
        course_by_code = {
            re.sub(r'[^A-Z0-9]', '', c.code.upper()): c
            for c in all_courses if c.code
        }

        assigned_count = 0
        skipped_count  = 0
        processed_rows = 0
        errors: list   = []
        issue_summary: dict = {}

        def _resolve_lecturer(row) -> Optional[LecturerModel]:
            """Try staff_number, then full_name."""
            if 'staff_number' in row and pd.notna(row['staff_number']):
                key = str(row['staff_number']).strip()
                if re.match(r'^\d+\.0$', key):
                    key = key[:-2]
                if key in lecturer_by_staff:
                    return lecturer_by_staff[key]
            if 'full_name' in row and pd.notna(row['full_name']):
                key = str(row['full_name']).strip().lower()
                if key in lecturer_by_name:
                    return lecturer_by_name[key]
            return None

        def _resolve_codes(row) -> list:
            """Collect formatted course codes from either a 'course_code' column or 'courses'."""
            codes = []
            if 'course_code' in row and pd.notna(row['course_code']):
                codes.append(str(row['course_code']).strip())
            if 'courses' in row and pd.notna(row['courses']):
                for c in re.split(r'[,;]+', str(row['courses'])):
                    if c.strip():
                        codes.append(c.strip())
            return codes

        for idx, row in df.iterrows():
            row_label = f"Row {idx + 2}"
            processed_rows += 1
            lecturer = _resolve_lecturer(row)
            if not lecturer:
                message = f"{row_label}: Lecturer not found. Check the staff number or full name."
                errors.append(message)
                _append_issue(issue_summary, "missing_lecturer_match", message)
                continue

            session_type = str(row.get('session_type', 'lecture') or 'lecture').strip().lower()
            if session_type not in ('lecture', 'practical', 'tutorial'):
                session_type = 'lecture'

            codes = _resolve_codes(row)
            if not codes:
                message = f"{row_label}: No course code value was found."
                errors.append(message)
                _append_issue(issue_summary, "missing_course_value", message)
                continue

            for original_code in codes:
                clean_code = re.sub(r'[^A-Z0-9]', '', original_code.upper())
                course = course_by_code.get(clean_code)
                if not course:
                    message = f"{row_label}: Course '{original_code}' was not found in the current courses list."
                    errors.append(message)
                    _append_issue(issue_summary, "missing_course_match", message)
                    continue

                existing = db.query(LecturerAssignment).filter(
                    LecturerAssignment.lecturer_id == lecturer.id,
                    LecturerAssignment.course_id   == course.id,
                ).first()
                if existing:
                    skipped_count += 1
                    continue

                db.add(LecturerAssignment(
                    lecturer_id=lecturer.id,
                    course_id=course.id,
                    session_type=session_type,
                    expertise_level='primary',
                ))
                assigned_count += 1

        db.commit()
        return {
            "status": "success",
            "assigned": assigned_count,
            "skipped": skipped_count,
            "processed_rows": processed_rows,
            "issue_summary": issue_summary or None,
            "errors": errors or None,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail="Error processing file. Please ensure it is correctly formatted.")
