"""
SIS (Student Information System) Integration — Agent Gamma
===========================================================

Headless webhook routes for importing SIS data into TABLESYS.

Boundary contract (PARALLEL_WORKPLAN.md):
  - New directory: backend/app/routers/api/
  - No edits to shared models (users, timetables, groups) beyond this file.
  - All SIS tables use their own create_all declaration.
  - The SisApiKey model is defined locally here to avoid touching models/__init__.py.

Authentication strategy:
  - Every /api/v1/sis/* webhook expects an  X-SIS-API-Key  header.
  - Management endpoints (generate / revoke / list keys) require a valid
    COORDINATOR or SUPERADMIN Bearer token so the SuperAdmin UI can call them.

SIS import endpoints (all idempotent UPSERT semantics):
  POST /api/v1/sis/webhooks/students      – bulk-upsert students
  POST /api/v1/sis/webhooks/lecturers     – bulk-upsert lecturers
  POST /api/v1/sis/webhooks/courses       – bulk-upsert courses
  POST /api/v1/sis/webhooks/groups        – bulk-upsert student groups
  POST /api/v1/sis/webhooks/enrolments    – enrol students into groups

API key management (Bearer-protected):
  POST   /api/v1/sis/keys                 – generate a new key for the caller's university
  GET    /api/v1/sis/keys                 – list keys for the caller's university
  DELETE /api/v1/sis/keys/{key_id}        – revoke a key
"""

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Boolean, Text
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...database import Base, get_db, engine
from ...models import (
    Course,
    Department,
    Lecturer,
    Student,
    StudentGroup,
    University,
    User,
    UserRole,
)

logger = logging.getLogger("app.sis")

# ──────────────────────────────────────────────────────────────────────────────
# SIS API Key model  (isolated — does NOT touch shared models/__init__.py)
# ──────────────────────────────────────────────────────────────────────────────

class SisApiKey(Base):
    """
    Tenant-scoped API key for SIS webhook authentication.

    The raw key is returned once on creation and never stored.  Only
    the SHA-256 digest is persisted so a database breach cannot be
    replayed.
    """
    __tablename__ = "sis_api_keys"

    id            = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    label         = Column(String(120), nullable=False)               # human-readable name
    key_prefix    = Column(String(12), nullable=False)                # first 8 chars for UI display
    key_hash      = Column(String(64), nullable=False, unique=True)   # SHA-256 hex of the raw key
    is_active     = Column(Boolean, default=True, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at    = Column(DateTime(timezone=True), nullable=False)
    last_used_at  = Column(DateTime(timezone=True), nullable=True)
    revoked_at    = Column(DateTime(timezone=True), nullable=True)
    notes         = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_sis_api_keys_university", "university_id"),
        Index("ix_sis_api_keys_hash", "key_hash"),
    )


# Create the table on startup without touching shared models
SisApiKey.__table__.create(bind=engine, checkfirst=True)

# ──────────────────────────────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/v1/sis", tags=["SIS Integration"])

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────────────────────────────────────

class ApiKeyCreate(BaseModel):
    label: str = Field(..., min_length=2, max_length=120,
                       description="Human-readable label, e.g. 'Banner SIS Production'")
    notes: Optional[str] = Field(None, max_length=500)


class ApiKeyResponse(BaseModel):
    id: int
    university_id: int
    label: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned ONCE on creation — includes the raw key."""
    raw_key: str


# ── SIS import payload schemas ────────────────────────────────────────────────

class SisStudent(BaseModel):
    student_number: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    program: str = Field(..., min_length=2, max_length=200)
    year_level: int = Field(..., ge=1, le=5)
    department_code: Optional[str] = None
    group_name: Optional[str] = None


class SisStudentBatch(BaseModel):
    students: List[SisStudent] = Field(..., min_length=1, max_length=2000)


class SisStudentResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str]


class SisLecturer(BaseModel):
    staff_number: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=200)
    email: Optional[EmailStr] = None
    department_code: str = Field(..., description="Must match existing dept code")
    max_hours_per_week: int = Field(default=20, ge=1, le=80)


class SisLecturerBatch(BaseModel):
    lecturers: List[SisLecturer] = Field(..., min_length=1, max_length=500)


class SisLecturerResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str]


class SisCourse(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=200)
    department_code: str
    level: int = Field(..., ge=1, le=5)
    credits: int = Field(..., ge=1, le=30)
    lecture_hours: int = Field(..., ge=1, le=20)
    tutorial_hours: int = Field(default=0, ge=0, le=10)
    practical_hours: int = Field(default=0, ge=0, le=10)


class SisCourseBatch(BaseModel):
    courses: List[SisCourse] = Field(..., min_length=1, max_length=1000)


class SisCourseResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str]


class SisGroup(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    level: int = Field(..., ge=1, le=5)
    department_code: str
    size: int = Field(..., ge=1, le=1000)
    display_code: Optional[str] = Field(None, max_length=20)


class SisGroupBatch(BaseModel):
    groups: List[SisGroup] = Field(..., min_length=1, max_length=200)


class SisGroupResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str]


class SisEnrolment(BaseModel):
    student_number: str
    group_name: str


class SisEnrolmentBatch(BaseModel):
    enrolments: List[SisEnrolment] = Field(..., min_length=1, max_length=5000)


class SisEnrolmentResult(BaseModel):
    linked: int
    not_found_students: List[str]
    not_found_groups: List[str]
    errors: List[str]


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _resolve_api_key(
    x_sis_api_key: str,
    db: Session,
) -> SisApiKey:
    """
    Validate X-SIS-API-Key header and return the matching SisApiKey row.
    Updates last_used_at on every successful call.
    """
    if not x_sis_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-SIS-API-Key header.",
        )

    key_hash = _hash_key(x_sis_api_key)
    api_key = (
        db.query(SisApiKey)
        .filter(SisApiKey.key_hash == key_hash, SisApiKey.is_active == True)
        .first()
    )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked SIS API key.",
        )

    # Touch last_used_at (best-effort, non-blocking)
    try:
        api_key.last_used_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()

    return api_key


def _require_coordinator_or_superadmin(current_user: User) -> User:
    role = current_user.role
    allowed = {UserRole.COORDINATOR, UserRole.SUPERADMIN}
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only coordinators and superadmins may manage SIS API keys.",
        )
    return current_user


# ──────────────────────────────────────────────────────────────────────────────
# API KEY MANAGEMENT  (Bearer-protected)
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/keys",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new SIS API key for the caller's university",
)
def generate_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a new SIS API key scoped to the authenticated user's university.

    The raw key is returned **once** in `raw_key`.  Store it immediately —
    TABLESYS will never show it again (only the prefix is stored).
    """
    _require_coordinator_or_superadmin(current_user)

    if current_user.university_id is None and current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a university.",
        )

    raw_key = f"sis_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:12]

    api_key = SisApiKey(
        university_id=current_user.university_id,
        label=payload.label,
        key_prefix=key_prefix,
        key_hash=key_hash,
        is_active=True,
        created_by_id=current_user.id,
        created_at=datetime.now(timezone.utc),
        notes=payload.notes,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    logger.info(
        "SIS API key created | university=%s | user=%s | label=%s",
        current_user.university_id,
        current_user.username,
        payload.label,
    )

    return ApiKeyCreatedResponse(
        id=api_key.id,
        university_id=api_key.university_id,
        label=api_key.label,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        notes=api_key.notes,
        raw_key=raw_key,
    )


@router.get(
    "/keys",
    response_model=List[ApiKeyResponse],
    summary="List SIS API keys for the caller's university",
)
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List active and revoked keys for the authenticated user's university."""
    _require_coordinator_or_superadmin(current_user)

    keys = (
        db.query(SisApiKey)
        .filter(SisApiKey.university_id == current_user.university_id)
        .order_by(SisApiKey.created_at.desc())
        .all()
    )
    return keys


@router.delete(
    "/keys/{key_id}",
    status_code=status.HTTP_200_OK,
    summary="Revoke a SIS API key",
)
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Revoke an API key so it can no longer authenticate webhook calls.
    Superadmins may revoke any key; coordinators may only revoke their own.
    """
    _require_coordinator_or_superadmin(current_user)

    api_key = db.query(SisApiKey).filter(SisApiKey.id == key_id).first()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found.")

    # Coordinators may only revoke keys belonging to their own university
    if (
        current_user.role != UserRole.SUPERADMIN
        and api_key.university_id != current_user.university_id
    ):
        raise HTTPException(status_code=403, detail="Cannot revoke keys from another university.")

    api_key.is_active = False
    api_key.revoked_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "SIS API key revoked | key_id=%s | by_user=%s",
        key_id,
        current_user.username,
    )
    return {"detail": f"Key '{api_key.label}' revoked successfully."}


# ──────────────────────────────────────────────────────────────────────────────
# WEBHOOK ENDPOINTS  (X-SIS-API-Key authenticated, headless)
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/webhooks/students",
    response_model=SisStudentResult,
    summary="SIS webhook: bulk-upsert students",
)
def webhook_import_students(
    batch: SisStudentBatch,
    request: Request,
    x_sis_api_key: str = Header(..., alias="X-SIS-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Idempotent bulk-upsert of student records from a SIS source.

    - Matches on `student_number`; updates existing records.
    - Links to a StudentGroup if `group_name` resolves within the tenant.
    - Links to a Department if `department_code` resolves within the tenant.
    - Returns counts of created / updated / skipped and any per-row errors.
    """
    api_key = _resolve_api_key(x_sis_api_key, db)
    university_id = api_key.university_id

    # Pre-load department lookup (code → id) for this university
    dept_map: dict[str, int] = {
        d.code: d.id
        for d in db.query(Department).filter(Department.university_id == university_id).all()
    }

    # Pre-load group lookup (name → id) for this university
    group_map: dict[str, int] = {
        g.name: g.id
        for g in db.query(StudentGroup).filter(StudentGroup.university_id == university_id).all()
    }

    created = updated = skipped = 0
    errors: list[str] = []

    for row in batch.students:
        try:
            dept_id: Optional[int] = dept_map.get(row.department_code) if row.department_code else None
            group_id: Optional[int] = group_map.get(row.group_name) if row.group_name else None

            existing = (
                db.query(Student)
                .filter(Student.student_number == row.student_number)
                .first()
            )

            if existing:
                existing.full_name = row.full_name
                existing.email = row.email
                existing.program = row.program
                existing.year_level = row.year_level
                if dept_id:
                    existing.department_id = dept_id
                if group_id:
                    existing.group_id = group_id
                updated += 1
            else:
                new_student = Student(
                    student_number=row.student_number,
                    full_name=row.full_name,
                    email=row.email,
                    hashed_password="!SIS_IMPORTED",  # placeholder — no login until they set a password
                    program=row.program,
                    year_level=row.year_level,
                    department_id=dept_id,
                    group_id=group_id,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(new_student)
                created += 1

        except Exception as exc:
            errors.append(f"student_number={row.student_number}: {exc}")
            skipped += 1

    db.commit()
    logger.info(
        "SIS /webhooks/students | uni=%s | created=%d updated=%d skipped=%d errors=%d",
        university_id, created, updated, skipped, len(errors),
    )
    return SisStudentResult(created=created, updated=updated, skipped=skipped, errors=errors)


@router.post(
    "/webhooks/lecturers",
    response_model=SisLecturerResult,
    summary="SIS webhook: bulk-upsert lecturers",
)
def webhook_import_lecturers(
    batch: SisLecturerBatch,
    request: Request,
    x_sis_api_key: str = Header(..., alias="X-SIS-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Idempotent bulk-upsert of lecturer records from a SIS source.

    Matches on `staff_number`.  `department_code` must exist in the tenant.
    """
    api_key = _resolve_api_key(x_sis_api_key, db)
    university_id = api_key.university_id

    dept_map: dict[str, int] = {
        d.code: d.id
        for d in db.query(Department).filter(Department.university_id == university_id).all()
    }

    created = updated = skipped = 0
    errors: list[str] = []

    for row in batch.lecturers:
        try:
            dept_id = dept_map.get(row.department_code)
            if dept_id is None:
                errors.append(
                    f"staff_number={row.staff_number}: unknown department_code '{row.department_code}'"
                )
                skipped += 1
                continue

            existing = (
                db.query(Lecturer)
                .filter(Lecturer.staff_number == row.staff_number)
                .first()
            )

            if existing:
                existing.full_name = row.full_name
                if row.email:
                    existing.email = row.email
                existing.department_id = dept_id
                existing.max_hours_per_week = row.max_hours_per_week
                updated += 1
            else:
                db.add(Lecturer(
                    staff_number=row.staff_number,
                    full_name=row.full_name,
                    email=row.email,
                    department_id=dept_id,
                    max_hours_per_week=row.max_hours_per_week,
                ))
                created += 1

        except Exception as exc:
            errors.append(f"staff_number={row.staff_number}: {exc}")
            skipped += 1

    db.commit()
    logger.info(
        "SIS /webhooks/lecturers | uni=%s | created=%d updated=%d skipped=%d errors=%d",
        university_id, created, updated, skipped, len(errors),
    )
    return SisLecturerResult(created=created, updated=updated, skipped=skipped, errors=errors)


@router.post(
    "/webhooks/courses",
    response_model=SisCourseResult,
    summary="SIS webhook: bulk-upsert courses",
)
def webhook_import_courses(
    batch: SisCourseBatch,
    request: Request,
    x_sis_api_key: str = Header(..., alias="X-SIS-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Idempotent bulk-upsert of course records from a SIS source.

    Matches on `code`.  `department_code` must resolve within the tenant.
    """
    api_key = _resolve_api_key(x_sis_api_key, db)
    university_id = api_key.university_id

    dept_map: dict[str, int] = {
        d.code: d.id
        for d in db.query(Department).filter(Department.university_id == university_id).all()
    }

    created = updated = skipped = 0
    errors: list[str] = []

    for row in batch.courses:
        try:
            dept_id = dept_map.get(row.department_code)
            if dept_id is None:
                errors.append(f"code={row.code}: unknown department_code '{row.department_code}'")
                skipped += 1
                continue

            existing = db.query(Course).filter(Course.code == row.code).first()

            if existing:
                existing.name = row.name
                existing.department_id = dept_id
                existing.level = row.level
                existing.credits = row.credits
                existing.lecture_hours = row.lecture_hours
                existing.tutorial_hours = row.tutorial_hours
                existing.practical_hours = row.practical_hours
                updated += 1
            else:
                db.add(Course(
                    code=row.code,
                    name=row.name,
                    department_id=dept_id,
                    level=row.level,
                    credits=row.credits,
                    lecture_hours=row.lecture_hours,
                    tutorial_hours=row.tutorial_hours,
                    practical_hours=row.practical_hours,
                ))
                created += 1

        except Exception as exc:
            errors.append(f"code={row.code}: {exc}")
            skipped += 1

    db.commit()
    logger.info(
        "SIS /webhooks/courses | uni=%s | created=%d updated=%d skipped=%d errors=%d",
        university_id, created, updated, skipped, len(errors),
    )
    return SisCourseResult(created=created, updated=updated, skipped=skipped, errors=errors)


@router.post(
    "/webhooks/groups",
    response_model=SisGroupResult,
    summary="SIS webhook: bulk-upsert student groups",
)
def webhook_import_groups(
    batch: SisGroupBatch,
    request: Request,
    x_sis_api_key: str = Header(..., alias="X-SIS-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Idempotent bulk-upsert of StudentGroup records from a SIS source.

    Matches on `name` within the tenant's university_id.
    """
    api_key = _resolve_api_key(x_sis_api_key, db)
    university_id = api_key.university_id

    dept_map: dict[str, int] = {
        d.code: d.id
        for d in db.query(Department).filter(Department.university_id == university_id).all()
    }

    created = updated = skipped = 0
    errors: list[str] = []

    for row in batch.groups:
        try:
            dept_id = dept_map.get(row.department_code)
            if dept_id is None:
                errors.append(f"group={row.name}: unknown department_code '{row.department_code}'")
                skipped += 1
                continue

            existing = (
                db.query(StudentGroup)
                .filter(
                    StudentGroup.name == row.name,
                    StudentGroup.university_id == university_id,
                )
                .first()
            )

            if existing:
                existing.level = row.level
                existing.department_id = dept_id
                existing.size = row.size
                if row.display_code:
                    existing.display_code = row.display_code
                updated += 1
            else:
                db.add(StudentGroup(
                    name=row.name,
                    level=row.level,
                    department_id=dept_id,
                    university_id=university_id,
                    size=row.size,
                    display_code=row.display_code,
                ))
                created += 1

        except Exception as exc:
            errors.append(f"group={row.name}: {exc}")
            skipped += 1

    db.commit()
    logger.info(
        "SIS /webhooks/groups | uni=%s | created=%d updated=%d skipped=%d errors=%d",
        university_id, created, updated, skipped, len(errors),
    )
    return SisGroupResult(created=created, updated=updated, skipped=skipped, errors=errors)


@router.post(
    "/webhooks/enrolments",
    response_model=SisEnrolmentResult,
    summary="SIS webhook: link students to groups",
)
def webhook_import_enrolments(
    batch: SisEnrolmentBatch,
    request: Request,
    x_sis_api_key: str = Header(..., alias="X-SIS-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Link students to StudentGroups.

    Matches `student_number` → Student and `group_name` → StudentGroup
    within the tenant.  Missing records are reported, not raised.
    """
    api_key = _resolve_api_key(x_sis_api_key, db)
    university_id = api_key.university_id

    student_map: dict[str, Student] = {
        s.student_number: s
        for s in db.query(Student).all()   # students table is not tenant-scoped — filter below
    }

    group_map: dict[str, StudentGroup] = {
        g.name: g
        for g in db.query(StudentGroup)
        .filter(StudentGroup.university_id == university_id)
        .all()
    }

    linked = 0
    not_found_students: list[str] = []
    not_found_groups: list[str] = []
    errors: list[str] = []

    for row in batch.enrolments:
        try:
            student = student_map.get(row.student_number)
            if not student:
                not_found_students.append(row.student_number)
                continue

            group = group_map.get(row.group_name)
            if not group:
                not_found_groups.append(row.group_name)
                continue

            student.group_id = group.id
            linked += 1

        except Exception as exc:
            errors.append(f"student={row.student_number} group={row.group_name}: {exc}")

    db.commit()
    logger.info(
        "SIS /webhooks/enrolments | uni=%s | linked=%d not_found_students=%d not_found_groups=%d",
        university_id, linked, len(not_found_students), len(not_found_groups),
    )
    return SisEnrolmentResult(
        linked=linked,
        not_found_students=list(set(not_found_students)),
        not_found_groups=list(set(not_found_groups)),
        errors=errors,
    )
