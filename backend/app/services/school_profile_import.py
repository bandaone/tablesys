from __future__ import annotations

import hashlib
import hmac
import io
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Course, Department, Lecturer, LecturerAssignment, School, User
from ..schemas import (
    SchoolProfileUploadApplyRequest,
    SchoolProfileUploadApplyResponse,
    SchoolProfileUploadPreviewResponse,
    SchoolProfileUploadPreviewRow,
    SchoolProfileUploadPreviewSummary,
)
from ..utils.course_profile import (
    COURSE_PROFILE_STATUS_COMPLETE,
    COURSE_PROFILE_STATUS_SEEDED,
    normalize_course_level,
)
from ..utils.sanitization import sanitize_input


ALLOWED_UPLOAD_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}
PREVIEW_TTL_MINUTES = 15
REQUIRED_COLUMNS = [
    "school",
    "programme",
    "year_level",
    "course_code",
    "course_name",
    "lecturer_name",
]
COLUMN_ALIASES = {
    "school name": "school",
    "program": "programme",
    "programme": "programme",
    "year level": "year_level",
    "year": "year_level",
    "course code": "course_code",
    "course name": "course_name",
    "lecturer": "lecturer_name",
    "lecturer name": "lecturer_name",
}


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).strip()


def _normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _normalize_text(value).lower()).strip()


def _normalize_code(value: Any) -> str:
    return re.sub(r"\s+", "", _normalize_text(value).upper())


def _read_dataframe(contents: bytes, content_type: str) -> pd.DataFrame:
    if content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")

    if content_type == "text/csv":
        text = contents.decode("utf-8", errors="replace")
        if "\t" in text and text.count("\t") > text.count(","):
            sep = "\t"
        else:
            sep = ";" if text.count(";") > text.count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep)
    else:
        df = pd.read_excel(io.BytesIO(contents))

    df.columns = [str(col).strip().lower() for col in df.columns]
    df = df.rename(columns={key: value for key, value in COLUMN_ALIASES.items() if key in df.columns})
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"The uploaded file is missing required columns: {', '.join(missing)}",
        )
    return df[REQUIRED_COLUMNS].copy()


def _base_department_code(programme: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", programme.upper())
    if not words:
        return "DEPT"
    if len(words) == 1:
        word = words[0]
        return word[:6]
    initials = "".join(word[0] for word in words[:6])
    return initials[:10]


def _generate_department_code(programme: str, reserved_codes: set[str]) -> str:
    base = _base_department_code(programme) or "DEPT"
    candidate = base
    suffix = 1
    while candidate in reserved_codes:
        suffix += 1
        candidate = f"{base[:8]}{suffix}"
    reserved_codes.add(candidate)
    return candidate


def _generate_staff_number(full_name: str, reserved_staff_numbers: set[str]) -> str:
    words = re.findall(r"[A-Za-z0-9]+", full_name.upper())
    if words:
        base = "AUTO-" + "".join(word[0] for word in words[:4])
    else:
        base = "AUTO-LECT"
    candidate = base
    suffix = 1
    while candidate in reserved_staff_numbers:
        suffix += 1
        candidate = f"{base[:12]}-{suffix}"
    reserved_staff_numbers.add(candidate)
    return candidate


class SchoolProfileImportService:
    def __init__(self, db: Session, current_user: User, school: School):
        self.db = db
        self.current_user = current_user
        self.school = school

    def build_preview(self, *, contents: bytes, content_type: str) -> SchoolProfileUploadPreviewResponse:
        df = _read_dataframe(contents, content_type)
        school_match_keys = {_normalize_key(self.school.name), _normalize_key(self.school.code)}

        school_departments = (
            self.db.query(Department)
            .filter(
                Department.university_id == self.current_user.university_id,
                Department.school_id == self.school.id,
            )
            .all()
        )
        tenant_departments = (
            self.db.query(Department)
            .filter(Department.university_id == self.current_user.university_id)
            .all()
        )
        department_by_name = {_normalize_key(item.name): item for item in school_departments}
        reserved_department_codes = {
            _normalize_code(item.code)
            for item in tenant_departments
            if item.code
        }

        school_courses = (
            self.db.query(Course)
            .join(Department, Course.department_id == Department.id)
            .filter(
                Department.university_id == self.current_user.university_id,
                Department.school_id == self.school.id,
            )
            .all()
        )
        course_by_key = {(item.department_id, _normalize_code(item.code)): item for item in school_courses}

        school_lecturers = (
            self.db.query(Lecturer)
            .join(Department, Lecturer.department_id == Department.id)
            .filter(
                Department.university_id == self.current_user.university_id,
                Department.school_id == self.school.id,
            )
            .all()
        )
        lecturers_by_name: Dict[str, List[Lecturer]] = {}
        for lecturer in school_lecturers:
            lecturers_by_name.setdefault(_normalize_key(lecturer.full_name), []).append(lecturer)

        school_assignments = (
            self.db.query(LecturerAssignment)
            .join(Course, LecturerAssignment.course_id == Course.id)
            .join(Department, Course.department_id == Department.id)
            .filter(
                Department.university_id == self.current_user.university_id,
                Department.school_id == self.school.id,
            )
            .all()
        )
        assignment_pairs = {(item.course_id, item.lecturer_id) for item in school_assignments}

        program_to_generated_code: Dict[str, str] = {}
        raw_rows: List[Dict[str, Any]] = []

        for idx, row in df.iterrows():
            row_number = idx + 2

            school_value = str(row.get("school", ""))
            if school_value.lower() == "nan": school_value = ""
            school_value = _normalize_text(school_value)

            programme_raw = str(row.get("programme", ""))
            if programme_raw.lower() == "nan": programme_raw = ""
            programme = sanitize_input(_normalize_text(programme_raw), max_length=200)

            course_code_raw = str(row.get("course_code", ""))
            if course_code_raw.lower() == "nan": course_code_raw = ""
            course_code = _normalize_code(course_code_raw)

            course_name_raw = str(row.get("course_name", ""))
            if course_name_raw.lower() == "nan": course_name_raw = ""
            course_name = sanitize_input(_normalize_text(course_name_raw), max_length=200)

            lecturer_name_raw = str(row.get("lecturer_name", ""))
            if lecturer_name_raw.lower() in ("nan", "none", "null"): lecturer_name_raw = ""
            
            # Split lecturers by comma or 'and'
            lecturer_names = [
                sanitize_input(_normalize_text(n), max_length=200)
                for n in re.split(r",|&|\band\b", lecturer_name_raw, flags=re.IGNORECASE)
                if n.strip()
            ]
            if not lecturer_names:
                lecturer_names = [""]

            for lecturer_name in lecturer_names:
                issues: List[str] = []

                if not school_value:
                    issues.append("School value is required.")
                elif _normalize_key(school_value) not in school_match_keys:
                    issues.append(f"Row school '{school_value}' does not match the selected school.")

                if not programme:
                    issues.append("Programme is required.")

                try:
                    year_level_raw = str(row.get("year_level", ""))
                    if year_level_raw.lower() == "nan": year_level_raw = ""
                    year_level = normalize_course_level(year_level_raw)
                except ValueError as exc:
                    issues.append(str(exc))
                    year_level = 0

                if not course_code:
                    issues.append("Course code is required.")
                if not course_name:
                    issues.append("Course name is required.")

                department = department_by_name.get(_normalize_key(programme)) if programme else None
                department_name = programme or "Unknown Programme"
                department_code: Optional[str] = department.code if department else None
                department_action = "reuse" if department else "create"

                if programme and department is None:
                    program_key = _normalize_key(programme)
                    if program_key not in program_to_generated_code:
                        course_prefix = re.match(r"^[A-Za-z]+", course_code) if course_code else None
                        if course_prefix:
                            base_code = course_prefix.group(0).upper()
                        else:
                            base_code = _base_department_code(programme) or "DEPT"
                        
                        candidate = base_code
                        suffix = 1
                        while candidate in reserved_department_codes:
                            candidate = f"{base_code[:8]}{suffix}"
                            suffix += 1
                        reserved_department_codes.add(candidate)
                        program_to_generated_code[program_key] = candidate
                    department_code = program_to_generated_code[program_key]

                lecturer_key = _normalize_key(lecturer_name) if lecturer_name else ""

                raw_rows.append(
                    {
                        "row_number": row_number,
                        "school": school_value,
                        "programme": programme,
                        "year_level": year_level,
                        "course_code": course_code,
                        "course_name": course_name,
                        "lecturer_name": lecturer_name if lecturer_name else None,
                        "department_name": department_name,
                        "department_code": department_code,
                        "department_action": department_action,
                        "issues": issues,
                    }
                )

        duplicate_keys: set[tuple[Any, ...]] = set()
        seen_row_keys: set[tuple[Any, ...]] = set()
        for item in raw_rows:
            row_key = (
                _normalize_key(item["programme"]),
                item["year_level"],
                _normalize_code(item["course_code"]),
                _normalize_key(item["course_name"]),
                _normalize_key(item["lecturer_name"] or ""),
            )
            if row_key in seen_row_keys:
                duplicate_keys.add(row_key)
            else:
                seen_row_keys.add(row_key)

        preview_rows: List[SchoolProfileUploadPreviewRow] = []
        summary = {
            "total_rows": 0,
            "ready_rows": 0,
            "conflicted_rows": 0,
            "skipped_rows": 0,
            "departments_to_create": 0,
            "departments_reused": 0,
            "courses_to_create": 0,
            "courses_to_update": 0,
            "courses_unchanged": 0,
            "lecturers_to_create": 0,
            "lecturers_reused": 0,
            "assignments_to_create": 0,
            "assignments_reused": 0,
        }

        counted_department_create: set[str] = set()
        counted_department_reuse: set[int] = set()

        for item in raw_rows:
            summary["total_rows"] += 1
            issues = list(item["issues"])
            department = department_by_name.get(_normalize_key(item["programme"])) if item["programme"] else None
            course = course_by_key.get((department.id, item["course_code"])) if department else None

            lecturer_action = "skipped"
            assignment_action = "skipped"
            course_action = "create"

            row_key = (
                _normalize_key(item["programme"]),
                item["year_level"],
                _normalize_code(item["course_code"]),
                _normalize_key(item["course_name"]),
                _normalize_key(item["lecturer_name"] or ""),
            )
            if row_key in duplicate_keys:
                issues.append("Duplicate row in upload.")

            lecturer_key = _normalize_key(item["lecturer_name"] or "")

            if course is not None:
                if course.name != item["course_name"] or course.level != item["year_level"]:
                    course_action = "update"
                else:
                    course_action = "unchanged"

            if item["lecturer_name"]:
                matches = lecturers_by_name.get(lecturer_key, [])
                if len(matches) > 1:
                    issues.append("Lecturer name matches multiple existing lecturers in this school.")
                    lecturer_action = "conflict"
                elif len(matches) == 1:
                    lecturer_action = "reuse"
                    if course is not None:
                        assignment_action = "reuse" if (course.id, matches[0].id) in assignment_pairs else "create"
                else:
                    lecturer_action = "create"
                    assignment_action = "create"

            can_apply = len(issues) == 0
            status = "ready" if can_apply else "conflict"

            if can_apply:
                summary["ready_rows"] += 1
            else:
                summary["conflicted_rows"] += 1
                summary["skipped_rows"] += 1

            if item["department_action"] == "create":
                if item["department_code"] not in counted_department_create:
                    summary["departments_to_create"] += 1
                    counted_department_create.add(item["department_code"] or "")
            elif department and department.id not in counted_department_reuse:
                summary["departments_reused"] += 1
                counted_department_reuse.add(department.id)

            summary_key = {
                "create": "courses_to_create",
                "update": "courses_to_update",
                "unchanged": "courses_unchanged",
            }.get(course_action)
            if can_apply and summary_key:
                summary[summary_key] += 1

            if can_apply and lecturer_action == "create":
                summary["lecturers_to_create"] += 1
            elif can_apply and lecturer_action == "reuse":
                summary["lecturers_reused"] += 1

            if can_apply and assignment_action == "create":
                summary["assignments_to_create"] += 1
            elif can_apply and assignment_action == "reuse":
                summary["assignments_reused"] += 1

            preview_rows.append(
                SchoolProfileUploadPreviewRow(
                    row_number=item["row_number"],
                    school=item["school"],
                    programme=item["programme"],
                    year_level=item["year_level"],
                    course_code=item["course_code"],
                    course_name=item["course_name"],
                    lecturer_name=item["lecturer_name"],
                    status=status,
                    can_apply=can_apply,
                    department_name=item["department_name"],
                    department_code=item["department_code"],
                    department_action=item["department_action"],
                    course_action=course_action,
                    lecturer_action=lecturer_action,
                    assignment_action=assignment_action,
                    issues=issues,
                )
            )

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=PREVIEW_TTL_MINUTES)
        fingerprint = self._fingerprint(rows=preview_rows, expires_at=expires_at)
        return SchoolProfileUploadPreviewResponse(
            school_id=self.school.id,
            fingerprint=fingerprint,
            expires_at=expires_at,
            rows=preview_rows,
            summary=SchoolProfileUploadPreviewSummary(**summary),
        )

    def apply_preview(self, payload: SchoolProfileUploadApplyRequest) -> SchoolProfileUploadApplyResponse:
        now = datetime.now(timezone.utc)
        expires_at = payload.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            raise HTTPException(status_code=409, detail="Preview has expired. Please upload and preview the file again.")

        expected_fingerprint = self._fingerprint(rows=payload.rows, expires_at=expires_at)
        if not hmac.compare_digest(expected_fingerprint, payload.fingerprint):
            raise HTTPException(status_code=409, detail="Preview payload no longer matches the signed preview. Please preview the file again.")

        created_departments = 0
        created_courses = 0
        updated_courses = 0
        created_lecturers = 0
        reused_lecturers = 0
        created_assignments = 0
        skipped_rows = 0
        issues: List[str] = []

        school_departments = (
            self.db.query(Department)
            .filter(
                Department.university_id == self.current_user.university_id,
                Department.school_id == self.school.id,
            )
            .all()
        )
        department_by_name = {_normalize_key(item.name): item for item in school_departments}
        tenant_department_codes = {
            _normalize_code(item.code)
            for item in self.db.query(Department).filter(Department.university_id == self.current_user.university_id).all()
            if item.code
        }
        staff_numbers = {
            _normalize_code(item.staff_number)
            for item in self.db.query(Lecturer).all()
            if item.staff_number
        }

        # Build a school-wide name->lecturer map so cross-department lecturers are reused
        all_school_lecturers = (
            self.db.query(Lecturer)
            .join(Department, Lecturer.department_id == Department.id)
            .filter(
                Department.university_id == self.current_user.university_id,
                Department.school_id == self.school.id,
            )
            .all()
        )
        lecturer_by_name: Dict[str, Lecturer] = {}
        for lect in all_school_lecturers:
            key = _normalize_key(lect.full_name)
            if key not in lecturer_by_name:
                lecturer_by_name[key] = lect

        for row in payload.rows:
            if not row.can_apply:
                skipped_rows += 1
                issues.extend([f"Row {row.row_number}: {message}" for message in row.issues])
                continue

            department_key = _normalize_key(row.programme)
            department = department_by_name.get(department_key)
            if department is None:
                code = row.department_code or _generate_department_code(row.programme, tenant_department_codes)
                department = Department(
                    university_id=self.current_user.university_id,
                    school_id=self.school.id,
                    name=sanitize_input(row.programme, max_length=200),
                    code=code,
                )
                self.db.add(department)
                self.db.flush()
                department_by_name[department_key] = department
                tenant_department_codes.add(_normalize_code(code))
                created_departments += 1

            course = (
                self.db.query(Course)
                .filter(Course.department_id == department.id, Course.code == row.course_code)
                .first()
            )
            if course is None:
                course = Course(
                    code=sanitize_input(row.course_code, max_length=20).upper(),
                    name=sanitize_input(row.course_name, max_length=200),
                    department_id=department.id,
                    level=row.year_level,
                    credits=None,
                    lecture_hours=None,
                    tutorial_hours=None,
                    practical_hours=None,
                    profile_status=COURSE_PROFILE_STATUS_SEEDED,
                )
                self.db.add(course)
                self.db.flush()
                created_courses += 1
            else:
                changed = False
                if course.name != row.course_name:
                    course.name = sanitize_input(row.course_name, max_length=200)
                    changed = True
                if course.level != row.year_level:
                    course.level = row.year_level
                    changed = True
                if changed:
                    updated_courses += 1

            lecturer = None
            if row.lecturer_name:
                lecturer_key = _normalize_key(row.lecturer_name)
                if lecturer_key in lecturer_by_name:
                    # Reuse existing lecturer found anywhere in this school
                    lecturer = lecturer_by_name[lecturer_key]
                    reused_lecturers += 1
                else:
                    lecturer = Lecturer(
                        staff_number=_generate_staff_number(row.lecturer_name, staff_numbers),
                        full_name=sanitize_input(row.lecturer_name, max_length=200),
                        email=None,
                        department_id=department.id,
                        max_hours_per_week=20,
                    )
                    self.db.add(lecturer)
                    self.db.flush()
                    lecturer_by_name[lecturer_key] = lecturer
                    created_lecturers += 1

            if lecturer is not None:
                assignment = (
                    self.db.query(LecturerAssignment)
                    .filter(
                        LecturerAssignment.course_id == course.id,
                        LecturerAssignment.lecturer_id == lecturer.id,
                    )
                    .first()
                )
                if assignment is None:
                    self.db.add(
                        LecturerAssignment(
                            course_id=course.id,
                            lecturer_id=lecturer.id,
                            session_type="lecture",
                        )
                    )
                    created_assignments += 1

        self.db.commit()
        return SchoolProfileUploadApplyResponse(
            school_id=self.school.id,
            created_departments=created_departments,
            created_courses=created_courses,
            updated_courses=updated_courses,
            created_lecturers=created_lecturers,
            reused_lecturers=reused_lecturers,
            created_assignments=created_assignments,
            skipped_rows=skipped_rows,
            issues=issues,
        )

    def _fingerprint(self, *, rows: List[Any], expires_at: datetime) -> str:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        payload = {
            "school_id": self.school.id,
            "tenant_id": self.current_user.university_id,
            "expires_at": expires_at.isoformat(),
            "rows": [row.model_dump(mode="json") if hasattr(row, "model_dump") else row for row in rows],
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            serialized.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
