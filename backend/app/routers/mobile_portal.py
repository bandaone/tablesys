import hashlib
import json
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Course, Department, Lecturer, Room, Student, StudentGroup, Timetable, TimetableSlot, University
from .student_portal import get_current_student
from ..utils.display_formatting import (
    format_department_name,
    format_group_label,
    format_person_name,
    format_room_name,
)

router = APIRouter(prefix="/api/v1/mobile", tags=["mobile-portal"])

DAY_ORDER = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def _day_name(val: Any) -> str:
    if isinstance(val, int) and 0 <= val <= 6:
        return DAY_NAMES[val]
    if isinstance(val, str) and val.isdigit():
        idx = int(val)
        if 0 <= idx <= 6:
            return DAY_NAMES[idx]
    return str(val) if val is not None else ""


def _format_time(value: Optional[time]) -> str:
    if value is None:
        return ""
    return value.strftime("%H:%M")


def _slot_matches_group(slot: TimetableSlot, group_id: int) -> bool:
    if slot.group_id == group_id:
        return True

    shared_group_ids = slot.shared_group_ids or []
    return group_id in shared_group_ids


def _sort_slots(slots: List[TimetableSlot]) -> List[TimetableSlot]:
    return sorted(
        slots,
        key=lambda slot: (
            DAY_ORDER.get(_day_name(slot.day_of_week), 999),
            _format_time(slot.start_time),
            _format_time(slot.end_time),
            slot.id,
        ),
    )


def _find_candidate_timetables(db: Session, student: Student) -> List[Timetable]:
    group_id = student.group_id
    if not group_id:
        return []

    timetables = (
        db.query(Timetable)
        .options(
            joinedload(Timetable.slots).joinedload(TimetableSlot.course),
            joinedload(Timetable.slots).joinedload(TimetableSlot.lecturer),
            joinedload(Timetable.slots).joinedload(TimetableSlot.room),
            joinedload(Timetable.slots).joinedload(TimetableSlot.group),
        )
        .order_by(Timetable.is_active.desc(), Timetable.id.desc())
        .all()
    )

    matching: List[Timetable] = []
    for timetable in timetables:
        if any(_slot_matches_group(slot, group_id) for slot in timetable.slots):
            matching.append(timetable)
    return matching


def _resolve_mobile_context(db: Session, student: Student) -> Dict[str, Any]:
    if not student.group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student is not assigned to a group. Please contact your department.",
        )

    group = db.query(StudentGroup).filter(StudentGroup.id == student.group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student group not found")

    candidate_timetables = _find_candidate_timetables(db, student)
    if not candidate_timetables:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No timetable is available for this student yet.",
        )

    timetable = candidate_timetables[0]
    relevant_slots = _sort_slots(
        [slot for slot in timetable.slots if _slot_matches_group(slot, student.group_id)]
    )

    department = db.query(Department).filter(Department.id == student.department_id).first()

    return {
        "student": student,
        "group": group,
        "department": department,
        "timetable": timetable,
        "slots": relevant_slots,
    }


def _get_local_now(db: Session, student: Student) -> datetime:
    """Return the current datetime in the university's configured timezone."""
    tz_name = "Africa/Harare"  # Safe default
    dept = db.query(Department).filter(Department.id == student.department_id).first()
    if dept and dept.university_id:
        uni = db.query(University).filter(University.id == dept.university_id).first()
        if uni and uni.timezone:
            tz_name = uni.timezone
    try:
        tz = ZoneInfo(tz_name)
    except (KeyError, Exception):
        tz = ZoneInfo("Africa/Harare")
    return datetime.now(tz)


def _resolve_reference_timetable(db: Session, student: Student) -> Optional[Timetable]:
    department = db.query(Department).filter(Department.id == student.department_id).first()

    query = (
        db.query(Timetable)
        .options(
            joinedload(Timetable.slots).joinedload(TimetableSlot.course),
            joinedload(Timetable.slots).joinedload(TimetableSlot.lecturer),
            joinedload(Timetable.slots).joinedload(TimetableSlot.room),
            joinedload(Timetable.slots).joinedload(TimetableSlot.group),
        )
        .order_by(Timetable.is_active.desc(), Timetable.id.desc())
    )

    if department and department.university_id:
        query = query.filter(Timetable.university_id == department.university_id)

    return query.first()


def _serialize_slot(slot: TimetableSlot) -> Dict[str, Any]:
    course = slot.course
    lecturer = slot.lecturer
    room = slot.room
    group = slot.group

    return {
        "id": slot.id,
        "day_of_week": _day_name(slot.day_of_week),
        "start_time": _format_time(slot.start_time),
        "end_time": _format_time(slot.end_time),
        "session_type": slot.session_type,
        "course_id": slot.course_id,
        "course_code": course.code if course else "N/A",
        "course_name": course.name if course else "N/A",
        "lecturer_name": format_person_name(lecturer.full_name) if lecturer else "Unassigned",
        "room_name": format_room_name(room.name) if room else "TBA",
        "room_number": format_room_name(room.name) if room else "TBA",
        "building": room.building if room else "TBA",
        "group_name": format_group_label(group) if group else "N/A",
    }


def _slot_minutes(slot_data: Dict[str, Any]) -> tuple[int, int]:
    start_minutes = int(slot_data["start_time"][:2]) * 60 + int(slot_data["start_time"][3:])
    end_minutes = int(slot_data["end_time"][:2]) * 60 + int(slot_data["end_time"][3:])
    return start_minutes, end_minutes


def _build_availability_payload(sessions: List[Dict[str, Any]], local_now: datetime = None) -> Dict[str, Any]:
    if local_now is None:
        local_now = datetime.now()
    today_name = local_now.strftime("%A")
    now_minutes = local_now.hour * 60 + local_now.minute

    ordered_sessions = sorted(
        sessions,
        key=lambda session: (
            DAY_ORDER.get(session["day_of_week"], 999),
            session["start_time"],
            session["end_time"],
        ),
    )

    current_session = None
    next_session = None

    for session in ordered_sessions:
        start_minutes, end_minutes = _slot_minutes(session)
        day_index = DAY_ORDER.get(session["day_of_week"], 999)
        today_index = DAY_ORDER.get(today_name, 999)

        if session["day_of_week"] == today_name and start_minutes <= now_minutes < end_minutes:
            current_session = session
            continue

        if day_index > today_index or (day_index == today_index and start_minutes > now_minutes):
            next_session = session
            break

    return {
        "today_name": today_name,
        "is_busy_now": current_session is not None,
        "current_session": current_session,
        "next_session": next_session,
        "today_sessions": [session for session in ordered_sessions if session["day_of_week"] == today_name],
    }


def _build_profile_payload(context: Dict[str, Any]) -> Dict[str, Any]:
    student = context["student"]
    group = context["group"]
    department = context["department"]

    return {
        "student_number": student.student_number,
        "full_name": format_person_name(student.full_name),
        "program": student.program,
        "year_level": student.year_level,
        "group_name": format_group_label(group),
        "department": format_department_name(department.name) if department else None,
    }


def _build_timetable_payload(context: Dict[str, Any]) -> Dict[str, Any]:
    timetable = context["timetable"]
    return {
        "id": timetable.id,
        "name": timetable.name,
        "semester": timetable.semester,
        "year": timetable.year,
        "academic_half": timetable.academic_half,
        "is_active": timetable.is_active,
    }


def _compute_etag(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f'"{digest}"'


def _if_none_match_matches(if_none_match_header: str, etag: str) -> bool:
    if not if_none_match_header:
        return False

    tokens = [token.strip() for token in if_none_match_header.split(",") if token.strip()]
    return "*" in tokens or etag in tokens


def _with_conditional_etag(
    payload: Dict[str, Any], request: Request, response: Response, max_age_seconds: int = 30
) -> Response | Dict[str, Any]:
    etag = _compute_etag(payload)
    cache_control = f"private, max-age={max_age_seconds}"

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = cache_control

    if _if_none_match_matches(request.headers.get("if-none-match", ""), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag, "Cache-Control": cache_control})

    return payload


def _find_current_session(sessions: List[Dict[str, Any]], today_name: str, now_minutes: int) -> Optional[Dict[str, Any]]:
    return next(
        (
            session
            for session in sessions
            if (
                session["day_of_week"] == today_name
                and int(session["start_time"][:2]) * 60 + int(session["start_time"][3:]) <= now_minutes
                < int(session["end_time"][:2]) * 60 + int(session["end_time"][3:])
            )
        ),
        None,
    )


def _find_next_session(sessions: List[Dict[str, Any]], today_name: str, now_minutes: int) -> Optional[Dict[str, Any]]:
    return next(
        (
            session
            for session in sessions
            if (
                DAY_ORDER.get(session["day_of_week"], 999) > DAY_ORDER.get(today_name, 999)
                or (
                    session["day_of_week"] == today_name
                    and (int(session["start_time"][:2]) * 60 + int(session["start_time"][3:])) > now_minutes
                )
            )
        ),
        None,
    )


@router.get("/me")
async def get_mobile_me(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    context = _resolve_mobile_context(db, current_student)
    return {
        "profile": _build_profile_payload(context),
        "timetable": _build_timetable_payload(context),
    }


@router.get("/me/dashboard")
async def get_mobile_dashboard(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    context = _resolve_mobile_context(db, current_student)
    serialized_slots = [_serialize_slot(slot) for slot in context["slots"]]

    local_now = _get_local_now(db, current_student)
    today_name = local_now.strftime("%A")
    now_minutes = local_now.hour * 60 + local_now.minute

    today_sessions = [slot for slot in serialized_slots if slot["day_of_week"] == today_name]

    current_session = _find_current_session(today_sessions, today_name, now_minutes)
    next_session = _find_next_session(serialized_slots, today_name, now_minutes)

    payload = {
        "profile": _build_profile_payload(context),
        "timetable": _build_timetable_payload(context),
        "today_name": today_name,
        "generated_at": datetime.utcnow().isoformat(),
        "stats": {
            "today_total_sessions": len(today_sessions),
            "week_total_sessions": len(serialized_slots),
        },
        "current_session": current_session,
        "next_session": next_session,
        "today_sessions": today_sessions,
    }

    return _with_conditional_etag(payload, request, response)


@router.get("/me/now")
async def get_mobile_now(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    context = _resolve_mobile_context(db, current_student)
    serialized_slots = [_serialize_slot(slot) for slot in context["slots"]]

    local_now = _get_local_now(db, current_student)
    today_name = local_now.strftime("%A")
    now_minutes = local_now.hour * 60 + local_now.minute

    today_sessions = [slot for slot in serialized_slots if slot["day_of_week"] == today_name]
    current_session = _find_current_session(today_sessions, today_name, now_minutes)
    next_session = _find_next_session(serialized_slots, today_name, now_minutes)

    payload = {
        "profile": _build_profile_payload(context),
        "timetable": _build_timetable_payload(context),
        "today_name": today_name,
        "generated_at": datetime.utcnow().isoformat(),
        "is_busy_now": current_session is not None,
        "current_session": current_session,
        "next_session": next_session,
        "today_sessions": today_sessions,
    }

    return _with_conditional_etag(payload, request, response)


@router.get("/me/today")
async def get_mobile_today(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    context = _resolve_mobile_context(db, current_student)
    local_now = _get_local_now(db, current_student)
    today_name = local_now.strftime("%A")
    sessions = [_serialize_slot(slot) for slot in context["slots"] if slot.day_of_week == today_name]

    payload = {
        "profile": _build_profile_payload(context),
        "timetable": _build_timetable_payload(context),
        "day": today_name,
        "sessions": sessions,
    }

    return _with_conditional_etag(payload, request, response)


@router.get("/me/week")
async def get_mobile_week(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    context = _resolve_mobile_context(db, current_student)
    sessions = [_serialize_slot(slot) for slot in context["slots"]]

    sessions_by_day: Dict[str, List[Dict[str, Any]]] = {}
    for session in sessions:
        sessions_by_day.setdefault(session["day_of_week"], []).append(session)

    payload = {
        "profile": _build_profile_payload(context),
        "timetable": _build_timetable_payload(context),
        "sessions": sessions,
        "sessions_by_day": sessions_by_day,
    }

    return _with_conditional_etag(payload, request, response)


@router.get("/me/courses")
async def get_mobile_courses(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    context = _resolve_mobile_context(db, current_student)
    slots = context["slots"]

    seen_course_ids: set[int] = set()
    course_payload: List[Dict[str, Any]] = []
    for slot in slots:
        course = slot.course
        if not course or course.id in seen_course_ids:
            continue

        seen_course_ids.add(course.id)
        course_payload.append(
            {
                "id": course.id,
                "code": course.code,
                "name": course.name,
                "credit_hours": course.credits,
                "course_type": getattr(course.course_type, "value", str(course.course_type)),
                "lecturer": {
                    "name": format_person_name(slot.lecturer.full_name),
                    "email": slot.lecturer.email,
                }
                if slot.lecturer
                else None,
            }
        )

    return course_payload


@router.get("/lookup")
async def mobile_lookup(
    q: str,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    query = q.strip()
    if len(query) < 2:
        return {"results": []}

    department = db.query(Department).filter(Department.id == current_student.department_id).first()
    university_id = department.university_id if department else None

    lecturer_query = db.query(Lecturer)
    room_query = db.query(Room)
    group_query = db.query(StudentGroup)
    course_query = db.query(Course)

    if current_student.department_id:
        lecturer_query = lecturer_query.filter(Lecturer.department_id == current_student.department_id)
        group_query = group_query.filter(StudentGroup.department_id == current_student.department_id)
        course_query = course_query.filter(Course.department_id == current_student.department_id)

    if university_id:
        room_query = room_query.filter(Room.university_id == university_id)
        group_query = group_query.filter(StudentGroup.university_id == university_id)

    lecturers = (
        lecturer_query.filter(
            (Lecturer.full_name.ilike(f"%{query}%")) | (Lecturer.staff_number.ilike(f"%{query}%"))
        )
        .order_by(Lecturer.full_name.asc())
        .limit(5)
        .all()
    )
    rooms = (
        room_query.filter((Room.name.ilike(f"%{query}%")) | (Room.building.ilike(f"%{query}%")))
        .order_by(Room.name.asc())
        .limit(5)
        .all()
    )
    groups = (
        group_query.filter(StudentGroup.name.ilike(f"%{query}%"))
        .order_by(StudentGroup.name.asc())
        .limit(5)
        .all()
    )
    courses = (
        course_query.filter((Course.code.ilike(f"%{query}%")) | (Course.name.ilike(f"%{query}%")))
        .order_by(Course.code.asc())
        .limit(5)
        .all()
    )

    results: List[Dict[str, Any]] = []
    for lecturer in lecturers:
        results.append(
            {
                "type": "lecturer",
                "id": lecturer.id,
                "title": format_person_name(lecturer.full_name),
                "subtitle": lecturer.staff_number,
                "meta": lecturer.email,
            }
        )
    for room in rooms:
        results.append(
            {
                "type": "room",
                "id": room.id,
                "title": format_room_name(room.name),
                "subtitle": room.building,
                "meta": f"Capacity {room.capacity}",
            }
        )
    for group in groups:
        results.append(
            {
                "type": "group",
                "id": group.id,
                "title": format_group_label(group),
                "subtitle": f"Level {group.level}",
                "meta": f"{group.size} students",
            }
        )
    for course in courses:
        results.append(
            {
                "type": "course",
                "id": course.id,
                "title": course.code,
                "subtitle": course.name,
                "meta": f"Level {course.level}",
            }
        )

    return {"results": results}


@router.get("/lookup/{entity_type}/{entity_id}")
async def mobile_lookup_detail(
    entity_type: str,
    entity_id: int,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    timetable = _resolve_reference_timetable(db, current_student)
    if not timetable:
        raise HTTPException(status_code=404, detail="No timetable available for lookup.")

    serialized_slots = [_serialize_slot(slot) for slot in timetable.slots]

    if entity_type == "lecturer":
        lecturer = db.query(Lecturer).filter(Lecturer.id == entity_id).first()
        if not lecturer:
            raise HTTPException(status_code=404, detail="Lecturer not found")
        lecturer_name = format_person_name(lecturer.full_name)
        sessions = [slot for slot in serialized_slots if slot["lecturer_name"] == lecturer_name]
        entity = {
            "type": "lecturer",
            "id": lecturer.id,
            "title": lecturer_name,
            "subtitle": lecturer.staff_number,
            "meta": lecturer.email,
        }
    elif entity_type == "room":
        room = db.query(Room).filter(Room.id == entity_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        room_name = format_room_name(room.name)
        sessions = [slot for slot in serialized_slots if slot["room_name"] == room_name]
        entity = {
            "type": "room",
            "id": room.id,
            "title": room_name,
            "subtitle": room.building,
            "meta": f"Capacity {room.capacity}",
        }
    elif entity_type == "group":
        group = db.query(StudentGroup).filter(StudentGroup.id == entity_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        group_name = format_group_label(group)
        sessions = [slot for slot in serialized_slots if slot["group_name"] == group_name]
        entity = {
            "type": "group",
            "id": group.id,
            "title": group_name,
            "subtitle": f"Level {group.level}",
            "meta": f"{group.size} students",
        }
    elif entity_type == "course":
        course = db.query(Course).filter(Course.id == entity_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        sessions = [slot for slot in serialized_slots if slot["course_id"] == course.id]
        entity = {
            "type": "course",
            "id": course.id,
            "title": course.code,
            "subtitle": course.name,
            "meta": f"Level {course.level}",
        }
    else:
        raise HTTPException(status_code=400, detail="Unsupported lookup type")

    return {
        "entity": entity,
        "availability": _build_availability_payload(sessions, _get_local_now(db, current_student)),
        "sessions": sorted(
            sessions,
            key=lambda session: (
                DAY_ORDER.get(session["day_of_week"], 999),
                session["start_time"],
                session["end_time"],
            ),
        ),
    }


@router.get("/rooms/free-now")
async def get_mobile_free_rooms_now(
    building: Optional[str] = None,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    department = db.query(Department).filter(Department.id == current_student.department_id).first()
    university_id = department.university_id if department else None

    reference_timetable = _resolve_reference_timetable(db, current_student)
    if not reference_timetable:
        raise HTTPException(status_code=404, detail="No timetable available for room availability.")

    local_now = _get_local_now(db, current_student)
    today_name = local_now.strftime("%A")
    now_minutes = local_now.hour * 60 + local_now.minute

    occupied_room_ids = {
        slot.room_id
        for slot in reference_timetable.slots
        if slot.room_id
        and slot.day_of_week == today_name
        and slot.start_time
        and slot.end_time
        and (slot.start_time.hour * 60 + slot.start_time.minute) <= now_minutes
        < (slot.end_time.hour * 60 + slot.end_time.minute)
    }

    rooms_query = db.query(Room)
    if university_id:
        rooms_query = rooms_query.filter(Room.university_id == university_id)
    if building:
        rooms_query = rooms_query.filter(Room.building.ilike(f"%{building.strip()}%"))

    rooms = rooms_query.order_by(Room.building.asc(), Room.name.asc()).all()
    free_rooms = [room for room in rooms if room.id not in occupied_room_ids and not room.is_blocked]

    payload = {
        "today_name": today_name,
        "checked_at": datetime.utcnow().isoformat(),
        "total_rooms": len(rooms),
        "occupied_rooms": len(occupied_room_ids),
        "free_rooms": [
            {
                "id": room.id,
                "name": format_room_name(room.name),
                "building": room.building,
                "capacity": room.capacity,
                "room_type": room.room_type,
            }
            for room in free_rooms
        ],
    }

    return _with_conditional_etag(payload, request, response)
