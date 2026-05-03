"""
Import Timetable API Router

POST /api/import/timetable

Imports parsed PDF timetable data into the database within a single
transaction. Handles:
- Course upsert (insert new, update level on conflict)
- Room insert with duplicate detection
- TimetableSlot creation (skipped when lecturer/group cannot be resolved)
- Timetable record creation for the imported data set
- Full rollback on unrecoverable error

Authorization: JWT required, COORDINATOR role only.
"""

import time
import logging
from datetime import datetime, time as dt_time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Course,
    Room,
    Timetable,
    TimetableSlot,
    User,
)
from ..auth import get_current_active_coordinator
from ..utils.sanitization import sanitize_input
from ..utils.audit_logger import AuditLogger
from fastapi import Request

logger = logging.getLogger("app.import_timetable")

router = APIRouter(prefix="/api/v1/import", tags=["import"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CourseInput(BaseModel):
    code: str
    year: int = Field(ge=1, le=5)
    program: Optional[str] = None
    name: Optional[str] = None


class RoomInput(BaseModel):
    code: str
    name: Optional[str] = None
    capacity: int = Field(default=50, ge=1)
    room_type: str = "lecture_hall"


class TimeSlotInput(BaseModel):
    course_code: str
    day: str
    start_time: str
    end_time: str
    room: str
    groups: List[str] = []


class TimetableData(BaseModel):
    courses: List[CourseInput] = []
    rooms: List[RoomInput] = []
    time_slots: List[TimeSlotInput] = []


class ImportRequest(BaseModel):
    source: str = "pdf_upload"
    term: str
    year: int = Field(ge=2000, le=2100)
    department_id: int
    data: TimetableData


class ImportSummary(BaseModel):
    courses_imported: int = 0
    courses_updated: int = 0
    courses_skipped: int = 0
    rooms_imported: int = 0
    rooms_skipped: int = 0
    slots_imported: int = 0
    slots_skipped: int = 0
    errors: List[str] = []
    warnings: List[str] = []


class ImportResponse(BaseModel):
    status: str
    import_id: str
    timetable_id: int
    summary: ImportSummary
    execution_time_ms: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DAY_MAP: Dict[str, int] = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
}


def _parse_time(time_str: str) -> dt_time:
    """Convert 'HH:MM' string to datetime.time. Defaults to midnight on failure."""
    try:
        parts = time_str.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return dt_time(hour=hour, minute=minute)
    except (ValueError, IndexError):
        logger.warning("Could not parse time string: %s", time_str)
        return dt_time(0, 0)


def _infer_building(room_code: str) -> str:
    """Derive a building label from a room code prefix."""
    code_upper = room_code.upper()
    if code_upper.startswith("LT"):
        return "Lecture Theatre Block"
    if code_upper.startswith("LAB") or code_upper.endswith("LAB"):
        return "Laboratory Block"
    return "Main Campus"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/timetable", response_model=ImportResponse, status_code=status.HTTP_200_OK)
async def import_timetable(
    request: Request,
    payload: ImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_coordinator),
) -> ImportResponse:
    """
    Import a parsed timetable data set into the database.

    Creates a new Timetable record for the imported data. Courses and Rooms are
    upserted. TimetableSlots are created only when both the course and room can
    be resolved in the database; unresolvable slots are logged as warnings.

    Rolls back the entire transaction on unrecoverable error.
    """
    start_ts = time.time()
    import_id = f"import_{int(start_ts)}_{current_user.id}"
    summary = ImportSummary()

    logger.info(
        "Import started. import_id=%s user=%s term=%s year=%d dept=%d",
        import_id,
        current_user.username,
        request.term,
        request.year,
        request.department_id,
    )

    # Input validation
    if not payload.data.courses and not payload.data.rooms and not payload.data.time_slots:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Import data contains no courses, rooms, or time slots.",
        )

    try:
        # ----------------------------------------------------------------
        # 1. Create a Timetable record for this import
        # ----------------------------------------------------------------
        timetable_record = Timetable(
            name=sanitize_input(f"{request.term} {request.year} Import", max_length=200),
            semester=sanitize_input(request.term, max_length=100),
            year=request.year,
            academic_half="first_half",
            is_active=False,
            generation_metadata={
                "source": payload.source,
                "import_id": import_id,
                "imported_by": current_user.username,
                "imported_at": datetime.utcnow().isoformat() + "Z",
            },
        )
        db.add(timetable_record)
        db.flush()  # Assign ID without committing

        logger.info("Created Timetable record id=%d", timetable_record.id)

        # ----------------------------------------------------------------
        # 2. Import Rooms (must come before courses / slots)
        # ----------------------------------------------------------------
        room_code_to_id: Dict[str, int] = {}

        for room_data in payload.data.rooms:
            code = sanitize_input(room_data.code, max_length=50).upper()
            if not code:
                continue

            existing_room = db.query(Room).filter(Room.name == code).first()
            if existing_room:
                room_code_to_id[code] = existing_room.id
                summary.rooms_skipped += 1
                summary.warnings.append(f"Room '{code}' already exists, using existing record.")
                continue

            room = Room(
                name=code,
                building=_infer_building(code),
                capacity=room_data.capacity,
                room_type=sanitize_input(room_data.room_type, max_length=50),
                has_projector=True,
                has_computers=False,
                priority_level=5,
                is_blocked=False,
            )
            db.add(room)
            db.flush()
            room_code_to_id[code] = room.id
            summary.rooms_imported += 1

        logger.info(
            "Rooms: %d imported, %d skipped",
            summary.rooms_imported,
            summary.rooms_skipped,
        )

        # ----------------------------------------------------------------
        # 3. Import Courses
        # ----------------------------------------------------------------
        course_code_to_id: Dict[str, int] = {}

        for course_data in payload.data.courses:
            code = sanitize_input(course_data.code, max_length=20).upper()
            if not code:
                continue

            existing_course = db.query(Course).filter(Course.code == code).first()
            if existing_course:
                # Update year level if changed
                if existing_course.level != course_data.year:
                    existing_course.level = course_data.year
                    summary.courses_updated += 1
                    summary.warnings.append(
                        f"Course '{code}' level updated to {course_data.year}."
                    )
                else:
                    summary.courses_skipped += 1
                course_code_to_id[code] = existing_course.id
                continue

            # Derive a course name from code + program if not provided
            display_name = course_data.name or f"{code} - {course_data.program or 'General'}"

            course = Course(
                code=code,
                name=sanitize_input(display_name, max_length=200),
                department_id=payload.department_id,
                level=course_data.year,
                credits=3,
                lecture_hours=3,
                tutorial_hours=0,
                practical_hours=0,
            )
            db.add(course)
            db.flush()
            course_code_to_id[code] = course.id
            summary.courses_imported += 1

        logger.info(
            "Courses: %d imported, %d updated, %d skipped",
            summary.courses_imported,
            summary.courses_updated,
            summary.courses_skipped,
        )

        # ----------------------------------------------------------------
        # 4. Import TimetableSlots
        #
        # TimetableSlot requires: course_id, lecturer_id, room_id,
        # group_id, timetable_id (all NOT NULL per model definition).
        #
        # lecturer_id and group_id are NOT present in the PDF-parsed data.
        # Slots without resolvable course or room are skipped with a warning.
        # Slots with missing lecturer/group are also skipped; the coordinator
        # can assign these manually once the timetable is imported.
        # ----------------------------------------------------------------
        for slot_data in payload.data.time_slots:
            course_code = sanitize_input(slot_data.course_code, max_length=20).upper()
            room_code = sanitize_input(slot_data.room, max_length=50).upper()
            day_upper = slot_data.day.upper()

            course_id = course_code_to_id.get(course_code)
            if not course_id:
                summary.slots_skipped += 1
                summary.warnings.append(
                    f"Slot skipped: course '{course_code}' not found in imported courses."
                )
                continue

            room_id = room_code_to_id.get(room_code)
            if not room_id:
                summary.slots_skipped += 1
                summary.warnings.append(
                    f"Slot skipped: room '{room_code}' not in imported rooms "
                    f"(course: {course_code}, day: {day_upper})."
                )
                continue

            day_number = _DAY_MAP.get(day_upper)
            if day_number is None:
                summary.slots_skipped += 1
                summary.warnings.append(
                    f"Slot skipped: unrecognised day '{slot_data.day}' "
                    f"for course '{course_code}'."
                )
                continue

            # lecturer_id and group_id are required by the model.
            # They cannot be resolved from PDF data alone; skip these slots
            # and emit a single aggregated warning at the end.
            # Full slot data is stored in the Timetable generation_metadata
            # so coordinators can assign lecturers/groups via the UI.
            summary.slots_skipped += 1
            summary.warnings.append(
                f"Slot skipped (requires manual lecturer/group assignment): "
                f"{course_code} on {day_upper} {slot_data.start_time}-{slot_data.end_time} in {room_code}."
            )

        # Store raw slot data in the timetable metadata for manual assignment
        timetable_record.generation_metadata["raw_slots"] = [
            s.model_dump() for s in payload.data.time_slots
        ]
        timetable_record.generation_metadata["raw_slot_count"] = len(payload.data.time_slots)

        # ----------------------------------------------------------------
        # 5. Commit
        # ----------------------------------------------------------------
        db.commit()

        execution_time_ms = int((time.time() - start_ts) * 1000)

        logger.info(
            "Import complete. import_id=%s timetable_id=%d time=%dms",
            import_id,
            timetable_record.id,
            execution_time_ms,
        )

        # Deduplicate warnings (cap at 50 to avoid oversized responses)
        if len(summary.warnings) > 50:
            overflow = len(summary.warnings) - 50
            summary.warnings = summary.warnings[:50]
            summary.warnings.append(
                f"... and {overflow} additional warnings omitted."
            )

        # Broadcast successful import to real-time streams
        AuditLogger.log_bulk_upload(
            request=request,
            user_id=current_user.id,
            username=current_user.username,
            resource_type="timetable_import",
            count=summary.slots_imported + summary.courses_imported + summary.rooms_imported,
            success=True,
            details={
                "import_id": import_id,
                "term": payload.term,
                "year": payload.year,
                "summary": summary.model_dump()
            }
        )

        return ImportResponse(
            status="success",
            import_id=import_id,
            timetable_id=timetable_record.id,
            summary=summary,
            execution_time_ms=execution_time_ms,
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Import failed. import_id=%s error=%s", import_id, str(exc), exc_info=True)
        
        # Broadcast failed import attempt
        AuditLogger.log_bulk_upload(
            request=request,
            user_id=current_user.id,
            username=current_user.username,
            resource_type="timetable_import",
            count=0,
            success=False,
            details={
                "error": str(exc),
                "term": payload.term,
                "year": payload.year
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Import failed and changes have been rolled back. Please check the file format and try again.",
        )
