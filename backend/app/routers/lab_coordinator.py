"""
Lab Coordinator Scheduling Router
──────────────────────────────────
Endpoints for:
  • Listing lab-eligible rooms and groups
  • Creating, listing, updating, deleting LabSession rows
  • Smart schedule generation: auto-assign groups → rooms respecting
    lecture timetable conflicts and applying morning/afternoon rotation
"""

from datetime import datetime, time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..auth import get_current_active_lab_coordinator_writer
from ..database import get_db
from ..models import (
    Course,
    LabSession,
    LabSessionStatus,
    LabRoomAllocation,
    Room,
    StudentGroup,
    Timetable,
    TimetableSlot,
    University,
    User,
    UserRole,
)
from ..utils.school_scope import filter_course_query_for_user
from ..utils.transit import DEFAULT_TRANSIT_MINUTES, insufficient_transit_time, times_overlap

router = APIRouter(prefix="/api/v1/lab-coordinator", tags=["lab-coordinator"], redirect_slashes=False)

# ─── Pydantic schemas (kept local to avoid touching shared schemas.py) ────────

class LabSessionCreate(BaseModel):
    course_id: int
    group_id: int
    parent_group_id: Optional[int] = None
    room_id: Optional[int] = None
    day_of_week: int           # 0=Mon … 6=Sun
    start_time: str            # "HH:MM"
    end_time: str              # "HH:MM"
    session_type: str = "lab"  # lab | tutorial | drawing
    duration_minutes: int = 120
    frequency_weeks: int = 1
    notes: Optional[str] = None
    timetable_id: Optional[int] = None
    rotation_cycle_length: int = 1
    rotation_configuration: Optional[dict] = None
    subgroup_ids: Optional[List[int]] = None


class LabSessionUpdate(BaseModel):
    room_id: Optional[int] = None
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    frequency_weeks: Optional[int] = None
    rotation_cycle_length: Optional[int] = None
    rotation_configuration: Optional[dict] = None


class SmartScheduleRequest(BaseModel):
    timetable_id: Optional[int] = None          # active timetable if None
    course_id: int
    parent_group_id: int
    group_ids: List[int]                         # subgroups to rotate
    room_ids: List[int]                          # available lab rooms
    subgroups_per_session: int = 1
    duration_minutes: int = 120
    frequency_weeks: int = 1
    session_type: str = "lab"
    preferred_days: Optional[List[int]] = None  # 0-4 by default
    start_hour: int = 7                         # earliest start
    end_hour: int = 17                          # latest end


class LabRoomCreate(BaseModel):
    name: str
    capacity: int
    building: str = ""
    room_type: str = "lab"


class LabRoomAllocationUpdate(BaseModel):
    room_ids: List[int]


def _is_published_lab_status(value: object) -> bool:
    """Legacy scheduled rows remain visible while new work starts as a draft."""
    normalized = getattr(value, "value", value)
    return str(normalized).lower() in {
        LabSessionStatus.PUBLISHED.value,
        LabSessionStatus.SCHEDULED.value,
    }

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_time(value: str, field: str) -> time:
    try:
        return datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} must be in HH:MM format")


def _times_overlap(s1: time, e1: time, s2: time, e2: time) -> bool:
    return times_overlap(s1, e1, s2, e2)


def _has_transit_clash(
    start_time: time,
    end_time: time,
    room_id: Optional[int],
    existing_start: time,
    existing_end: time,
    existing_room_id: Optional[int],
) -> bool:
    return insufficient_transit_time(
        start_time, end_time, room_id,
        existing_start, existing_end, existing_room_id,
    )


def _group_lineage_ids(db: Session, group_id: int) -> set[int]:
    """Return a group and its parents so child labs respect cohort teaching."""
    ids: set[int] = set()
    current_id: Optional[int] = group_id
    for _ in range(10):
        if current_id is None or current_id in ids:
            break
        ids.add(current_id)
        current = db.query(StudentGroup).filter(StudentGroup.id == current_id).first()
        current_id = current.parent_group_id if current else None
    return ids


def _dedupe_group_ids(group_ids: Optional[List[int]]) -> List[int]:
    seen: set[int] = set()
    deduped: List[int] = []
    for raw_id in group_ids or []:
        try:
            group_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if group_id not in seen:
            deduped.append(group_id)
            seen.add(group_id)
    return deduped


def _build_rotation_configuration(group_ids: List[int], subgroups_per_session: int) -> tuple[int, Optional[dict[str, List[int]]]]:
    ordered_group_ids = _dedupe_group_ids(group_ids)
    if not ordered_group_ids:
        return 1, None

    chunk_size = max(1, int(subgroups_per_session or 1))
    rotation_cycle_length = (len(ordered_group_ids) + chunk_size - 1) // chunk_size
    configuration: dict[str, List[int]] = {}
    for index in range(rotation_cycle_length):
        start = index * chunk_size
        end = start + chunk_size
        chunk = ordered_group_ids[start:end]
        if chunk:
            configuration[str(index + 1)] = chunk
    return max(rotation_cycle_length, 1), configuration or None


def _resolve_rotation_group_ids(
    db: Session,
    parent_group_id: int,
    subgroup_ids: Optional[List[int]] = None,
) -> List[int]:
    if subgroup_ids:
        return _dedupe_group_ids(subgroup_ids)

    children = (
        db.query(StudentGroup.id)
        .filter(
            StudentGroup.parent_group_id == parent_group_id,
            StudentGroup.group_type.in_(["lab_group", "tutorial_group", "drawing_group", "stream"]),
        )
        .order_by(StudentGroup.name.asc())
        .all()
    )
    return [group_id for (group_id,) in children]


def _course_supports_lab(course: Course) -> bool:
    return (course.practical_hours or 0) > 0


def _coordinator_department_id(user: User) -> Optional[int]:
    if getattr(user, "role", None) in {UserRole.COORDINATOR, UserRole.LAB_COORDINATOR, UserRole.HOD}:
        return getattr(user, "department_id", None)
    return None


def _require_lab_department(user: User) -> int:
    """Department-owned lab work must never silently fall back to all rooms."""
    department_id = _coordinator_department_id(user)
    if department_id is None:
        raise HTTPException(
            status_code=400,
            detail="Assign this lab coordinator to a department before managing lab rooms or schedules.",
        )
    return department_id


def _room_is_in_department_pool(db: Session, university_id: int, department_id: Optional[int], room_id: int) -> bool:
    """A department can use its own room or a room it deliberately selected."""
    room = db.query(Room).filter(Room.id == room_id, Room.university_id == university_id).first()
    if not room:
        return False
    if department_id is None:
        return True
    if room.department_id == department_id:
        return True
    return db.query(LabRoomAllocation.id).filter(
        LabRoomAllocation.university_id == university_id,
        LabRoomAllocation.department_id == department_id,
        LabRoomAllocation.room_id == room_id,
    ).first() is not None


def _is_descendant_of(db: Session, group_id: int, parent_group_id: int) -> bool:
    """Return True only when a lab subgroup belongs under the selected cohort."""
    current_id: Optional[int] = group_id
    for _ in range(10):
        if current_id is None:
            return False
        if current_id == parent_group_id:
            return True
        current = db.query(StudentGroup).filter(StudentGroup.id == current_id).first()
        current_id = current.parent_group_id if current else None
    return False


def _detect_conflicts(
    db: Session,
    university_id: int,
    room_id: Optional[int],
    group_id: int,
    day_of_week: int,
    start_time: time,
    end_time: time,
    timetable_id: Optional[int],
    exclude_session_id: Optional[int] = None,
    participant_group_ids: Optional[List[int]] = None,
) -> list:
    conflicts = []
    group_lineage_ids = _group_lineage_ids(db, group_id)
    for participant_id in participant_group_ids or []:
        group_lineage_ids.update(_group_lineage_ids(db, participant_id))

    # ── 1. Room conflict in TimetableSlot (lecture timetable) ────────────────
    if room_id and timetable_id:
        lecture_slots = (
            db.query(TimetableSlot)
            .filter(
                TimetableSlot.timetable_id == timetable_id,
                TimetableSlot.room_id == room_id,
                TimetableSlot.day_of_week == day_of_week,
            )
            .all()
        )
        for ls in lecture_slots:
            if _times_overlap(start_time, end_time, ls.start_time, ls.end_time):
                course = db.query(Course).filter(Course.id == ls.course_id).first()
                conflicts.append({
                    "type": "room_lecture_clash",
                    "slot_id": ls.id,
                    "description": (
                        f"Room already has a lecture "
                        f"({course.code if course else '?'}) "
                        f"{ls.start_time.strftime('%H:%M')}–{ls.end_time.strftime('%H:%M')}"
                    ),
                    "severity": "critical",
                })

    # ── 2. Group conflict in TimetableSlot (student busy during lecture) ────
    if timetable_id:
        grp_slots = (
            db.query(TimetableSlot)
            .filter(
                TimetableSlot.timetable_id == timetable_id,
                TimetableSlot.day_of_week == day_of_week,
            )
            .all()
        )
        for gs in grp_slots:
            slot_audience = {gs.group_id, *(gs.shared_group_ids or [])}
            if not slot_audience.intersection(group_lineage_ids):
                continue
            overlaps = _times_overlap(start_time, end_time, gs.start_time, gs.end_time)
            transit_clash = _has_transit_clash(
                start_time, end_time, room_id, gs.start_time, gs.end_time, gs.room_id,
            )
            if overlaps or transit_clash:
                course = db.query(Course).filter(Course.id == gs.course_id).first()
                conflicts.append({
                    "type": "group_lecture_clash" if overlaps else "group_lecture_transit",
                    "slot_id": gs.id,
                    "description": (
                        f"Group has a lecture "
                        f"({course.code if course else '?'}) "
                        f"{gs.start_time.strftime('%H:%M')}–{gs.end_time.strftime('%H:%M')}"
                        + (f"; at least {DEFAULT_TRANSIT_MINUTES} minutes are needed between different rooms" if transit_clash else "")
                    ),
                    "severity": "critical",
                })

    # ── 3. Room conflict within existing LabSession rows ─────────────────────
    if room_id:
        q = db.query(LabSession).filter(
            LabSession.university_id == university_id,
            LabSession.room_id == room_id,
            LabSession.day_of_week == day_of_week,
            LabSession.status != LabSessionStatus.CANCELLED,
        )
        if exclude_session_id:
            q = q.filter(LabSession.id != exclude_session_id)
        for ls in q.all():
            if _times_overlap(start_time, end_time, ls.start_time, ls.end_time):
                grp = db.query(StudentGroup).filter(StudentGroup.id == ls.group_id).first()
                conflicts.append({
                    "type": "room_lab_clash",
                    "session_id": ls.id,
                    "description": (
                        f"Room already has a lab for "
                        f"{grp.name if grp else '?'} "
                        f"{ls.start_time.strftime('%H:%M')}–{ls.end_time.strftime('%H:%M')}"
                    ),
                    "severity": "high",
                })

    # ── 4. Group already has a lab session at same time ───────────────────────
    q2 = db.query(LabSession).filter(
        LabSession.university_id == university_id,
        LabSession.day_of_week == day_of_week,
        LabSession.status != LabSessionStatus.CANCELLED,
    )
    if exclude_session_id:
        q2 = q2.filter(LabSession.id != exclude_session_id)
    for ls in q2.all():
        existing_audience_ids = {ls.group_id}
        for subgroup_ids in (ls.rotation_configuration or {}).values():
            existing_audience_ids.update(_dedupe_group_ids(subgroup_ids if isinstance(subgroup_ids, list) else []))
        existing_lineage_ids: set[int] = set()
        for audience_id in existing_audience_ids:
            existing_lineage_ids.update(_group_lineage_ids(db, audience_id))
        if not existing_lineage_ids.intersection(group_lineage_ids):
            continue
        overlaps = _times_overlap(start_time, end_time, ls.start_time, ls.end_time)
        transit_clash = _has_transit_clash(
            start_time, end_time, room_id, ls.start_time, ls.end_time, ls.room_id,
        )
        if overlaps or transit_clash:
            conflicts.append({
                "type": "group_lab_clash" if overlaps else "group_lab_transit",
                "session_id": ls.id,
                "description": (
                    f"Group already has a lab "
                    f"{ls.start_time.strftime('%H:%M')}–{ls.end_time.strftime('%H:%M')}"
                    + (f"; at least {DEFAULT_TRANSIT_MINUTES} minutes are needed between different rooms" if transit_clash else "")
                ),
                "severity": "high",
            })

    return conflicts


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/rooms")
async def get_lab_rooms(
    university_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    """Return the available lab rooms, marking this department's chosen pool."""
    uid = university_id or getattr(current_user, "university_id", None)
    q = db.query(Room).filter(
        Room.room_type.in_(["lab", "LAB", "computer_lab", "drawing_room"]),
        Room.is_blocked == False,
    )
    if uid:
        q = q.filter(Room.university_id == uid)
    dept_id = _coordinator_department_id(current_user)
    allocated_ids: set[int] = set()
    if dept_id is not None:
        allocated_ids = {
            room_id for (room_id,) in db.query(LabRoomAllocation.room_id).filter(
                LabRoomAllocation.university_id == uid,
                LabRoomAllocation.department_id == dept_id,
            ).all()
        }
    rooms = q.order_by(Room.name).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "building": r.building,
            "capacity": r.capacity,
            "room_type": r.room_type,
            "tags": r.tags,
            "department_id": r.department_id,
            "selected_for_department": r.id in allocated_ids,
            "owned_by_department": r.department_id == dept_id,
        }
        for r in rooms
    ]


@router.get("/room-allocations")
async def get_lab_room_allocations(
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    """Return the room IDs this department has selected for lab scheduling."""
    uid = getattr(current_user, "university_id", None)
    department_id = _require_lab_department(current_user)
    return {
        "department_id": department_id,
        "room_ids": [
            room_id for (room_id,) in db.query(LabRoomAllocation.room_id).filter(
                LabRoomAllocation.university_id == uid,
                LabRoomAllocation.department_id == department_id,
            ).order_by(LabRoomAllocation.room_id).all()
        ],
    }


@router.put("/room-allocations")
async def set_lab_room_allocations(
    payload: LabRoomAllocationUpdate,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    """Set the department's preferred lab-room pool.

    This is a planning selection, not an all-day exclusive reservation. Every
    generated session is still checked against university-wide room clashes.
    """
    uid = getattr(current_user, "university_id", None)
    department_id = _require_lab_department(current_user)
    room_ids = _dedupe_group_ids(payload.room_ids)
    valid_rooms = db.query(Room.id).filter(
        Room.university_id == uid,
        Room.id.in_(room_ids or [-1]),
        Room.room_type.in_(["lab", "LAB", "computer_lab", "drawing_room"]),
        Room.is_blocked == False,
    ).all()
    valid_ids = {room_id for (room_id,) in valid_rooms}
    unknown_ids = sorted(set(room_ids) - valid_ids)
    if unknown_ids:
        raise HTTPException(status_code=400, detail=f"Invalid or unavailable lab room IDs: {unknown_ids}")

    db.query(LabRoomAllocation).filter(
        LabRoomAllocation.university_id == uid,
        LabRoomAllocation.department_id == department_id,
    ).delete(synchronize_session=False)
    for room_id in room_ids:
        db.add(LabRoomAllocation(
            university_id=uid,
            department_id=department_id,
            room_id=room_id,
            created_by_id=current_user.id,
        ))
    db.commit()
    return {"department_id": department_id, "room_ids": room_ids}

@router.post("/rooms", status_code=status.HTTP_201_CREATED)
async def create_lab_room(
    room_data: LabRoomCreate,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    """Allow lab coordinators to create lab venues assigned to their department."""
    uid = getattr(current_user, "university_id", None)
    
    # Ensure name is unique
    if db.query(Room).filter(Room.university_id == uid, Room.name == room_data.name).first():
        raise HTTPException(status_code=400, detail="A venue with this name already exists.")

    new_room = Room(
        university_id=uid,
        school_id=getattr(current_user, "school_id", None),
        department_id=getattr(current_user, "department_id", None),
        name=room_data.name,
        capacity=room_data.capacity,
        building=room_data.building,
        room_type=room_data.room_type,
        is_blocked=False,
    )
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    # A room created by a department is immediately available to that
    # department's scheduler, without requiring a second configuration step.
    department_id = _coordinator_department_id(current_user)
    if department_id is not None:
        db.add(LabRoomAllocation(
            university_id=uid,
            department_id=department_id,
            room_id=new_room.id,
            created_by_id=current_user.id,
        ))
        db.commit()
    return {
        "id": new_room.id,
        "name": new_room.name,
        "capacity": new_room.capacity,
        "building": new_room.building,
    }

@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lab_room(
    room_id: int,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    """Delete a lab venue if it belongs to the coordinator's department, or if they are admin."""
    uid = getattr(current_user, "university_id", None)
    room = db.query(Room).filter(Room.id == room_id, Room.university_id == uid).first()
    if not room:
        raise HTTPException(status_code=404, detail="Lab venue not found.")
    
    department_id = _coordinator_department_id(current_user)
    if department_id is not None and room.department_id != department_id:
        raise HTTPException(status_code=403, detail="You can only delete venues managed by your department.")
             
    db.delete(room)
    db.commit()
    return None


@router.get("/groups")
async def get_lab_groups(
    parent_group_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    """Return lab subgroups (group_type = lab_group) scoped to the tenant. Filtered by department for Lab Coordinators."""
    uid = getattr(current_user, "university_id", None)
    q = db.query(StudentGroup).filter(
        StudentGroup.group_type.in_(["lab_group", "tutorial_group", "drawing_group"]),
    )
    if uid:
        q = q.filter(StudentGroup.university_id == uid)
    dept_id = _coordinator_department_id(current_user)
    if dept_id is not None:
        q = q.filter(StudentGroup.department_id == dept_id)
        
    if parent_group_id:
        q = q.filter(StudentGroup.parent_group_id == parent_group_id)
    groups = q.order_by(StudentGroup.name).all()
    return [
        {
            "id": g.id,
            "name": g.name,
            "size": g.size,
            "level": g.level,
            "display_code": g.display_code,
            "group_type": g.group_type,
            "parent_group_id": g.parent_group_id,
            "department_id": g.department_id,
        }
        for g in groups
    ]


@router.get("/courses")
async def get_lab_courses(
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    """Return only courses that actually have lab/practical work."""
    q = filter_course_query_for_user(db.query(Course), current_user).order_by(Course.code.asc())
    courses = [course for course in q.all() if _course_supports_lab(course)]
    return [
        {
            "id": course.id,
            "code": course.code,
            "name": course.name,
            "department_id": course.department_id,
            "level": course.level,
            "practical_hours": course.practical_hours,
            "lecture_hours": course.lecture_hours,
            "tutorial_hours": course.tutorial_hours,
            "activity_requirements": course.activity_requirements,
        }
        for course in courses
    ]


@router.get("/sessions")
async def list_lab_sessions(
    course_id: Optional[int] = None,
    group_id: Optional[int] = None,
    room_id: Optional[int] = None,
    day_of_week: Optional[int] = None,
    has_conflict: Optional[bool] = None,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    uid = getattr(current_user, "university_id", None)
    q = db.query(LabSession).filter(LabSession.university_id == uid)
    dept_id = _coordinator_department_id(current_user)
    if dept_id is not None:
        q = q.join(StudentGroup, StudentGroup.id == LabSession.group_id).filter(StudentGroup.department_id == dept_id)
    if course_id:
        q = q.filter(LabSession.course_id == course_id)
    if group_id:
        q = q.filter(LabSession.group_id == group_id)
    if room_id:
        q = q.filter(LabSession.room_id == room_id)
    if day_of_week is not None:
        q = q.filter(LabSession.day_of_week == day_of_week)
    if has_conflict is not None:
        q = q.filter(LabSession.has_conflict == has_conflict)
    sessions = q.order_by(LabSession.day_of_week, LabSession.start_time).all()

    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def _serialize(s: LabSession):
        group = db.query(StudentGroup).filter(StudentGroup.id == s.group_id).first()
        course = db.query(Course).filter(Course.id == s.course_id).first()
        room = db.query(Room).filter(Room.id == s.room_id).first() if s.room_id else None
        return {
            "id": s.id,
            "course_id": s.course_id,
            "course_code": course.code if course else None,
            "course_name": course.name if course else None,
            "group_id": s.group_id,
            "group_name": group.name if group else None,
            "group_size": group.size if group else None,
            "room_id": s.room_id,
            "room_name": room.name if room else None,
            "room_building": room.building if room else None,
            "day_of_week": s.day_of_week,
            "day_name": DAY_NAMES[s.day_of_week] if 0 <= s.day_of_week <= 6 else "?",
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
            "session_type": s.session_type,
            "status": s.status,
            "duration_minutes": s.duration_minutes,
            "frequency_weeks": s.frequency_weeks,
            "rotation_cycle_length": s.rotation_cycle_length,
            "rotation_configuration": s.rotation_configuration,
            "has_conflict": s.has_conflict,
            "conflict_detail": s.conflict_detail,
            "notes": s.notes,
            "timetable_id": s.timetable_id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }

    return [_serialize(s) for s in sessions]


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_lab_session(
    payload: LabSessionCreate,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    uid = getattr(current_user, "university_id", None) or 1
    parent_group_id = payload.parent_group_id or payload.group_id
    if not parent_group_id:
        raise HTTPException(status_code=400, detail="parent_group_id is required")

    st = _parse_time(payload.start_time, "start_time")
    et = _parse_time(payload.end_time, "end_time")
    if st >= et:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    # Validate FK references
    course = db.query(Course).filter(Course.id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if not _course_supports_lab(course):
        raise HTTPException(status_code=400, detail="Selected course does not have a lab/practical component")
    parent_group = db.query(StudentGroup).filter(StudentGroup.id == parent_group_id).first()
    if not parent_group:
        raise HTTPException(status_code=404, detail="Group not found")
    dept_id = _coordinator_department_id(current_user)
    if dept_id is not None and parent_group.department_id != dept_id:
        raise HTTPException(status_code=403, detail="You can only schedule lab sessions for your own department.")
    if payload.room_id and not _room_is_in_department_pool(db, uid, dept_id, payload.room_id):
        raise HTTPException(status_code=403, detail="Choose a lab room from your department's room pool.")

    rotation_group_ids = _resolve_rotation_group_ids(db, parent_group_id, payload.subgroup_ids)
    if any(not _is_descendant_of(db, group_id, parent_group_id) for group_id in rotation_group_ids):
        raise HTTPException(status_code=400, detail="Every rotating subgroup must belong to the selected parent group.")
    if payload.rotation_configuration:
        rotation_configuration = {
            str(key): _dedupe_group_ids(value if isinstance(value, list) else [])
            for key, value in payload.rotation_configuration.items()
            if _dedupe_group_ids(value if isinstance(value, list) else [])
        }
        rotation_cycle_length = max(len(rotation_configuration), 1)
    else:
        rotation_cycle_length, rotation_configuration = _build_rotation_configuration(
            rotation_group_ids,
            payload.rotation_cycle_length,
        )
        if rotation_configuration:
            rotation_cycle_length = len(rotation_configuration)

    # Determine active timetable for conflict checks
    timetable_id = payload.timetable_id
    if not timetable_id:
        department = db.query(Department).filter(Department.id == current_user.department_id).first() if current_user.department_id else None
        school_id = department.school_id if department else None
        
        active = (
            db.query(Timetable)
            .filter(
                Timetable.university_id == uid, 
                Timetable.is_active == True,
                or_(Timetable.school_id == school_id, Timetable.school_id == None) if school_id else True
            )
            .order_by(Timetable.school_id.isnot(None).desc(), Timetable.id.desc())
            .first()
        )
        timetable_id = active.id if active else None

    conflicts = _detect_conflicts(
        db, uid,
        payload.room_id,
        parent_group_id,
        payload.day_of_week,
        st, et,
        timetable_id,
        participant_group_ids=rotation_group_ids,
    )

    session = LabSession(
        university_id=uid,
        timetable_id=timetable_id,
        course_id=payload.course_id,
        group_id=parent_group_id,
        room_id=payload.room_id,
        day_of_week=payload.day_of_week,
        start_time=st,
        end_time=et,
        session_type=payload.session_type,
        duration_minutes=payload.duration_minutes,
        frequency_weeks=payload.frequency_weeks,
        rotation_cycle_length=rotation_cycle_length,
        rotation_configuration=rotation_configuration,
        notes=payload.notes,
        has_conflict=len(conflicts) > 0,
        conflict_detail=conflicts if conflicts else None,
        status=LabSessionStatus.DRAFT,
        created_by_id=current_user.id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "has_conflict": session.has_conflict, "conflicts": conflicts}


@router.patch("/sessions/{session_id}")
async def update_lab_session(
    session_id: int,
    payload: LabSessionUpdate,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    uid = getattr(current_user, "university_id", None) or 1
    session = (
        db.query(LabSession)
        .filter(LabSession.id == session_id, LabSession.university_id == uid)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Lab session not found")
    dept_id = _coordinator_department_id(current_user)
    if dept_id is not None:
        parent_group = db.query(StudentGroup).filter(StudentGroup.id == session.group_id).first()
        if not parent_group or parent_group.department_id != dept_id:
            raise HTTPException(status_code=403, detail="You can only update lab sessions for your own department.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        if key in ("start_time", "end_time") and val is not None:
            val = _parse_time(val, key)
        setattr(session, key, val)

    # Re-run conflict detection
    st = session.start_time
    et = session.end_time
    if st >= et:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    conflicts = _detect_conflicts(
        db, uid,
        session.room_id,
        session.group_id,
        session.day_of_week,
        st, et,
        session.timetable_id,
        exclude_session_id=session_id,
        participant_group_ids=[
            subgroup_id
            for subgroup_ids in (session.rotation_configuration or {}).values()
            for subgroup_id in _dedupe_group_ids(subgroup_ids if isinstance(subgroup_ids, list) else [])
        ],
    )
    session.has_conflict = len(conflicts) > 0
    session.conflict_detail = conflicts if conflicts else None

    db.commit()
    db.refresh(session)
    return {"id": session.id, "has_conflict": session.has_conflict, "conflicts": conflicts}


@router.post("/sessions/{session_id}/publish")
async def publish_lab_session(
    session_id: int,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    """Make a tested lab session visible to students and lecturers."""
    uid = getattr(current_user, "university_id", None) or 1
    session = db.query(LabSession).filter(
        LabSession.id == session_id,
        LabSession.university_id == uid,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Lab session not found")

    dept_id = _coordinator_department_id(current_user)
    parent_group = db.query(StudentGroup).filter(StudentGroup.id == session.group_id).first()
    if dept_id is not None and (not parent_group or parent_group.department_id != dept_id):
        raise HTTPException(status_code=403, detail="You can only publish lab sessions for your own department.")

    participant_group_ids = [
        subgroup_id
        for subgroup_ids in (session.rotation_configuration or {}).values()
        for subgroup_id in _dedupe_group_ids(subgroup_ids if isinstance(subgroup_ids, list) else [])
    ]
    conflicts = _detect_conflicts(
        db, uid, session.room_id, session.group_id, session.day_of_week,
        session.start_time, session.end_time, session.timetable_id,
        exclude_session_id=session.id,
        participant_group_ids=participant_group_ids,
    )
    session.has_conflict = bool(conflicts)
    session.conflict_detail = conflicts or None
    if conflicts:
        db.commit()
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Resolve every conflict before publishing this lab session.",
                "conflicts": conflicts,
            },
        )

    session.status = LabSessionStatus.PUBLISHED
    db.commit()
    return {"id": session.id, "status": LabSessionStatus.PUBLISHED.value, "published": True}


@router.post("/sessions/{session_id}/unpublish")
async def unpublish_lab_session(
    session_id: int,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    """Withdraw a published session back to a private coordinator draft."""
    uid = getattr(current_user, "university_id", None) or 1
    session = db.query(LabSession).filter(
        LabSession.id == session_id,
        LabSession.university_id == uid,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Lab session not found")

    dept_id = _coordinator_department_id(current_user)
    parent_group = db.query(StudentGroup).filter(StudentGroup.id == session.group_id).first()
    if dept_id is not None and (not parent_group or parent_group.department_id != dept_id):
        raise HTTPException(status_code=403, detail="You can only withdraw lab sessions for your own department.")

    session.status = LabSessionStatus.DRAFT
    db.commit()
    return {"id": session.id, "status": LabSessionStatus.DRAFT.value, "published": False}


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lab_session(
    session_id: int,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    uid = getattr(current_user, "university_id", None) or 1
    session = (
        db.query(LabSession)
        .filter(LabSession.id == session_id, LabSession.university_id == uid)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Lab session not found")
    dept_id = _coordinator_department_id(current_user)
    if dept_id is not None:
        parent_group = db.query(StudentGroup).filter(StudentGroup.id == session.group_id).first()
        if not parent_group or parent_group.department_id != dept_id:
            raise HTTPException(status_code=403, detail="You can only delete lab sessions for your own department.")
    db.delete(session)
    db.commit()
    return None


@router.post("/smart-schedule")
async def smart_schedule(
    payload: SmartScheduleRequest,
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    """
    Smart lab scheduling algorithm.

    Strategy
    ─────────
    1. Collect all existing lecture slots for the given groups (from timetable).
    2. For each group, find free windows on each day that don't clash with lectures.
    3. Assign groups to rooms in round-robin, splitting morning (07-13) vs
       afternoon (13-17) to maximise venue utilisation when venues are scarce.
    4. Create LabSession rows; return a proposal list (no side effects if
       dry_run=True in the future — for now always persists).
    """
    uid = getattr(current_user, "university_id", None) or 1
    course = db.query(Course).filter(Course.id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if not _course_supports_lab(course):
        raise HTTPException(status_code=400, detail="Selected course does not have a lab/practical component")

    department_id = _coordinator_department_id(current_user)
    parent_group = db.query(StudentGroup).filter(
        StudentGroup.id == payload.parent_group_id,
        StudentGroup.university_id == uid,
    ).first()
    if not parent_group:
        raise HTTPException(status_code=404, detail="Parent group not found")
    if department_id is not None and parent_group.department_id != department_id:
        raise HTTPException(status_code=403, detail="You can only schedule labs for your own department.")

    # Resolve timetable
    timetable_id = payload.timetable_id
    if not timetable_id:
        department = db.query(Department).filter(Department.id == current_user.department_id).first() if current_user.department_id else None
        school_id = department.school_id if department else None
        
        active = (
            db.query(Timetable)
            .filter(
                Timetable.university_id == uid, 
                Timetable.is_active == True,
                or_(Timetable.school_id == school_id, Timetable.school_id == None) if school_id else True
            )
            .order_by(Timetable.school_id.isnot(None).desc(), Timetable.id.desc())
            .first()
        )
        timetable_id = active.id if active else None

    rotation_group_ids = _dedupe_group_ids(payload.group_ids)
    if not rotation_group_ids:
        raise HTTPException(status_code=400, detail="group_ids must include at least one subgroup")
    if any(not _is_descendant_of(db, group_id, payload.parent_group_id) for group_id in rotation_group_ids):
        raise HTTPException(status_code=400, detail="Every rotating subgroup must belong to the selected parent group.")

    preferred_days = payload.preferred_days if payload.preferred_days is not None else list(range(5))
    if not preferred_days or any(day < 0 or day > 6 for day in preferred_days):
        raise HTTPException(status_code=400, detail="Choose one or more valid preferred days.")
    if payload.duration_minutes <= 0 or payload.start_hour < 0 or payload.end_hour > 24 or payload.start_hour >= payload.end_hour:
        raise HTTPException(status_code=400, detail="Provide a valid lab duration and operating-hours window.")
    duration_h = payload.duration_minutes / 60
    if duration_h > (payload.end_hour - payload.start_hour):
        raise HTTPException(status_code=400, detail="The lab duration does not fit inside the selected operating-hours window.")

    # Build busy windows per group from lecture timetable
    busy: list[tuple[int, time, time]] = []
    if timetable_id:
        slots = (
            db.query(TimetableSlot)
            .filter(
                TimetableSlot.timetable_id == timetable_id,
                TimetableSlot.group_id == payload.parent_group_id,
            )
            .all()
        )
        busy = [(s.day_of_week, s.start_time, s.end_time) for s in slots]

    # Candidate time slots to try (hour-based grid)
    def _candidate_slots(day: int) -> list[tuple[time, time]]:
        """Return (start, end) pairs that don't clash with the group's lectures."""
        candidates = []
        h = payload.start_hour
        while h + duration_h <= payload.end_hour:
            st = time(int(h), int((h % 1) * 60))
            end_h = h + duration_h
            et = time(int(end_h), int((end_h % 1) * 60))
            clash = any(
                d == day and _times_overlap(st, et, bs, be)
                for d, bs, be in busy
            )
            if not clash:
                candidates.append((st, et))
            h += duration_h  # step by duration so slots don't overlap
        return candidates

    cycle_length, rotation_config = _build_rotation_configuration(
        rotation_group_ids,
        payload.subgroups_per_session,
    )

    rooms = _dedupe_group_ids(payload.room_ids)
    if not rooms:
        raise HTTPException(status_code=400, detail="Select at least one room from your department's room pool.")
    disallowed_room_ids = [
        room_id for room_id in rooms
        if not _room_is_in_department_pool(db, uid, department_id, room_id)
    ]
    if disallowed_room_ids:
        raise HTTPException(
            status_code=403,
            detail="Select rooms from your department's room pool before scheduling: " + ", ".join(map(str, disallowed_room_ids)),
        )

    subgroup_sizes = {
        group.id: group.size
        for group in db.query(StudentGroup).filter(StudentGroup.id.in_(rotation_group_ids)).all()
    }
    batches = [
        rotation_group_ids[index:index + max(1, payload.subgroups_per_session)]
        for index in range(0, len(rotation_group_ids), max(1, payload.subgroups_per_session))
    ]
    largest_rotation_headcount = max((sum(subgroup_sizes.get(group_id, 0) for group_id in batch) for batch in batches), default=0)
    room_records = db.query(Room).filter(Room.id.in_(rooms), Room.university_id == uid).all()
    rooms = [room.id for room in room_records if room.capacity >= largest_rotation_headcount]
    if not rooms:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No selected room can hold the largest rotation batch ({largest_rotation_headcount} students). "
                "Choose a larger room or reduce subgroups per session."
            ),
        )
    created = []
    failed = []

    scheduled = False

    for day in preferred_days:
        if scheduled:
            break
        candidates = _candidate_slots(day)

        morning = [c for c in candidates if c[0].hour < 13]
        afternoon = [c for c in candidates if c[0].hour >= 13]
        ordered = morning + afternoon

        for st, et in ordered:
            if scheduled:
                break
                
            for room_id in rooms:
                # Check room not already taken by another lab session at this time
                conflicts = _detect_conflicts(
                    db, uid, room_id, payload.parent_group_id, day, st, et, timetable_id,
                    participant_group_ids=rotation_group_ids,
                )
                if conflicts:
                    # The smart scheduler never saves a known clash.  It can
                    # keep trying candidates, while manual entry remains a
                    # clearly flagged exceptional workflow.
                    continue

                session = LabSession(
                    university_id=uid,
                    timetable_id=timetable_id,
                    course_id=payload.course_id,
                    group_id=payload.parent_group_id,
                    room_id=room_id,
                    day_of_week=day,
                    start_time=st,
                    end_time=et,
                    session_type=payload.session_type,
                    duration_minutes=payload.duration_minutes,
                    frequency_weeks=payload.frequency_weeks,
                    rotation_cycle_length=cycle_length,
                    rotation_configuration=rotation_config,
                    has_conflict=len(conflicts) > 0,
                    conflict_detail=conflicts if conflicts else None,
                    status=LabSessionStatus.DRAFT,
                    created_by_id=current_user.id,
                )
                db.add(session)
                db.flush()
                group = db.query(StudentGroup).filter(StudentGroup.id == payload.parent_group_id).first()
                created.append({
                    "session_id": session.id,
                    "group_id": payload.parent_group_id,
                    "group_name": group.name if group else str(payload.parent_group_id),
                    "room_id": room_id,
                    "day_of_week": day,
                    "start_time": st.strftime("%H:%M"),
                    "end_time": et.strftime("%H:%M"),
                    "has_conflict": session.has_conflict,
                    "warnings": [c for c in conflicts if c.get("severity") != "critical"],
                })
                scheduled = True
                break

    if not scheduled:
        grp = db.query(StudentGroup).filter(StudentGroup.id == payload.parent_group_id).first()
        failed.append({
            "group_id": payload.parent_group_id,
            "group_name": grp.name if grp else str(payload.parent_group_id),
            "reason": "No conflict-free slot found on any preferred day",
        })

    db.commit()
    return {
        "scheduled": len(created),
        "failed": len(failed),
        "sessions": created,
        "unscheduled": failed,
    }


@router.get("/summary")
async def lab_summary(
    current_user: User = Depends(get_current_active_lab_coordinator_writer),
    db: Session = Depends(get_db),
):
    """Quick dashboard stats for the lab coordinator."""
    uid = getattr(current_user, "university_id", None) or 1

    dept_id = _coordinator_department_id(current_user)
    sessions_query = db.query(LabSession).filter(LabSession.university_id == uid)
    if dept_id is not None:
        sessions_query = sessions_query.join(StudentGroup, StudentGroup.id == LabSession.group_id).filter(
            StudentGroup.department_id == dept_id,
        )
    total = sessions_query.count()
    conflicted = sessions_query.filter(
        LabSession.university_id == uid,
        LabSession.has_conflict == True,
    ).count()
    lab_groups_query = (
        db.query(StudentGroup)
        .filter(
            StudentGroup.university_id == uid,
            StudentGroup.group_type.in_(["lab_group", "tutorial_group", "drawing_group"]),
        )
    )
    if dept_id is not None:
        lab_groups_query = lab_groups_query.filter(StudentGroup.department_id == dept_id)
    lab_groups = lab_groups_query.count()

    lab_rooms_query = (
        db.query(Room)
        .filter(
            Room.university_id == uid,
            Room.room_type.in_(["lab", "LAB", "computer_lab", "drawing_room"]),
            Room.is_blocked == False,
        )
    )
    if dept_id is not None:
        allocated_room_ids = db.query(LabRoomAllocation.room_id).filter(
            LabRoomAllocation.university_id == uid,
            LabRoomAllocation.department_id == dept_id,
        )
        lab_rooms_query = lab_rooms_query.filter(or_(
            Room.department_id == dept_id,
            Room.id.in_(allocated_room_ids),
        ))
    lab_rooms = lab_rooms_query.count()

    return {
        "total_sessions": total,
        "conflicted_sessions": conflicted,
        "lab_groups": lab_groups,
        "lab_rooms": lab_rooms,
        "conflict_rate": round(conflicted / total * 100, 1) if total else 0,
    }
