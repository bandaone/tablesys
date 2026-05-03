"""
Public Mobile Portal — Anonymous Student Access Layer

No authentication is required.  Students select their group once;
the frontend stores the group_id in localStorage and passes it as a
query parameter on every request.

All endpoints live under  /api/v1/mobile/public/*

Security notes
--------------
* Lecturer emails are stripped from every payload.
* Responses are ETag-cached so thousands of students hitting the same
  group_id result in a single DB query + cache revalidation.
* Rate limiting should be applied at the reverse-proxy / Cloudflare level.
"""

import hashlib
import json
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import (
    Course,
    Department,
    Lecturer,
    Room,
    StudentGroup,
    Timetable,
    TimetableSlot,
    University,
    CourseAnnouncement,
)

router = APIRouter(prefix="/api/v1/mobile/public", tags=["mobile-public"])

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


# ── Helpers ─────────────────────────────────────────────────────────────────


def _format_time(value: Optional[time]) -> str:
    if value is None:
        return ""
    return value.strftime("%H:%M")


def _get_effective_group_ids(db: Session, group_id: int) -> set[int]:
    """Walk up the parent_group_id chain and return all ancestor group IDs.

    If the student is in *Lab Group A* (tier 3), this returns the IDs for
    Lab Group A, its parent Stream group, and its grandparent Department
    group.  Slots assigned to any of these groups should be shown.
    """
    effective_ids: set[int] = set()
    current_id: Optional[int] = group_id
    max_depth = 10  # safety valve against circular references

    while current_id and max_depth > 0:
        effective_ids.add(current_id)
        group = db.query(StudentGroup).filter(StudentGroup.id == current_id).first()
        if not group or not group.parent_group_id:
            break
        current_id = group.parent_group_id
        max_depth -= 1

    return effective_ids


def _slot_matches_effective_groups(
    slot: TimetableSlot, effective_group_ids: set[int]
) -> bool:
    """Return True if *slot* is relevant for any of the student's groups."""
    if slot.group_id in effective_group_ids:
        return True
    shared_ids = slot.shared_group_ids or []
    return any(gid in effective_group_ids for gid in shared_ids)


def _sort_slots(slots: List[TimetableSlot]) -> List[TimetableSlot]:
    return sorted(
        slots,
        key=lambda s: (
            DAY_ORDER.get(_day_name(s.day_of_week), 999),
            _format_time(s.start_time),
            _format_time(s.end_time),
            s.id,
        ),
    )


def _resolve_group(db: Session, group_id: int) -> StudentGroup:
    """Load and validate the requested group."""
    group = db.query(StudentGroup).filter(StudentGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found. Please select a valid group.",
        )
    return group


def _get_local_now(db: Session, group: StudentGroup) -> datetime:
    """Return the current datetime in the university's configured timezone.

    Falls back to Africa/Harare (CAT / UTC+2) when no timezone is set.
    """
    tz_name = "Africa/Harare"  # Safe default
    if group.university_id:
        uni = db.query(University).filter(University.id == group.university_id).first()
        if uni and uni.timezone:
            tz_name = uni.timezone
    try:
        tz = ZoneInfo(tz_name)
    except (KeyError, Exception):
        tz = ZoneInfo("Africa/Harare")
    return datetime.now(tz)


def _find_candidate_timetables(
    db: Session, group: StudentGroup, effective_ids: set[int]
) -> List[Timetable]:
    timetables = (
        db.query(Timetable)
        .filter(Timetable.university_id == group.university_id)
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
    for tt in timetables:
        if any(_slot_matches_effective_groups(slot, effective_ids) for slot in tt.slots):
            matching.append(tt)
    return matching


def _resolve_public_context(db: Session, group_id: int) -> Dict[str, Any]:
    group = _resolve_group(db, group_id)
    effective_ids = _get_effective_group_ids(db, group_id)

    candidates = _find_candidate_timetables(db, group, effective_ids)
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No timetable is available for this group yet.",
        )

    timetable = candidates[0]
    relevant_slots = _sort_slots(
        [s for s in timetable.slots if _slot_matches_effective_groups(s, effective_ids)]
    )

    department = (
        db.query(Department).filter(Department.id == group.department_id).first()
    )

    # Build group breadcrumb (e.g. ["Engineering Year 1", "Stream B", "Lab A"])
    breadcrumb: List[str] = []
    current_id: Optional[int] = group_id
    max_depth = 10
    while current_id and max_depth > 0:
        g = db.query(StudentGroup).filter(StudentGroup.id == current_id).first()
        if not g:
            break
        breadcrumb.insert(0, g.name)
        current_id = g.parent_group_id
        max_depth -= 1

    return {
        "group": group,
        "department": department,
        "timetable": timetable,
        "slots": relevant_slots,
        "effective_group_ids": effective_ids,
        "group_breadcrumb": breadcrumb,
    }


def _serialize_slot(slot: TimetableSlot) -> Dict[str, Any]:
    """Serialize a slot — lecturer email is intentionally omitted."""
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
        "lecturer_name": lecturer.full_name if lecturer else "Unassigned",
        "room_name": room.name if room else "TBA",
        "room_number": room.name if room else "TBA",
        "building": room.building if room else "TBA",
        "group_name": group.name if group else "N/A",
    }


def _compute_etag(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f'"{digest}"'


def _if_none_match_matches(header: str, etag: str) -> bool:
    if not header:
        return False
    tokens = [t.strip() for t in header.split(",") if t.strip()]
    return "*" in tokens or etag in tokens


def _with_conditional_etag(
    payload: Dict[str, Any],
    request: Request,
    response: Response,
    max_age_seconds: int = 60,
) -> Response | Dict[str, Any]:
    etag = _compute_etag(payload)
    cache_control = f"public, max-age={max_age_seconds}"

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = cache_control

    if _if_none_match_matches(
        request.headers.get("if-none-match", ""), etag
    ):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"ETag": etag, "Cache-Control": cache_control},
        )

    return payload


def _build_profile_payload(context: Dict[str, Any]) -> Dict[str, Any]:
    group = context["group"]
    department = context["department"]

    return {
        "group_id": group.id,
        "group_name": group.name,
        "group_breadcrumb": context.get("group_breadcrumb", [group.name]),
        "level": group.level,
        "department": department.name if department else None,
    }


def _build_timetable_payload(context: Dict[str, Any]) -> Dict[str, Any]:
    tt = context["timetable"]
    return {
        "id": tt.id,
        "name": tt.name,
        "semester": tt.semester,
        "year": tt.year,
        "academic_half": tt.academic_half,
        "is_active": tt.is_active,
    }


def _find_current_session(
    sessions: List[Dict[str, Any]], today_name: str, now_minutes: int
) -> Optional[Dict[str, Any]]:
    return next(
        (
            s
            for s in sessions
            if (
                s["day_of_week"] == today_name
                and int(s["start_time"][:2]) * 60 + int(s["start_time"][3:])
                <= now_minutes
                < int(s["end_time"][:2]) * 60 + int(s["end_time"][3:])
            )
        ),
        None,
    )


def _find_next_session(
    sessions: List[Dict[str, Any]], today_name: str, now_minutes: int
) -> Optional[Dict[str, Any]]:
    return next(
        (
            s
            for s in sessions
            if (
                DAY_ORDER.get(s["day_of_week"], 999)
                > DAY_ORDER.get(today_name, 999)
                or (
                    s["day_of_week"] == today_name
                    and (int(s["start_time"][:2]) * 60 + int(s["start_time"][3:]))
                    > now_minutes
                )
            )
        ),
        None,
    )


# ── Onboarding ──────────────────────────────────────────────────────────────


@router.get("/onboarding-groups")
async def get_onboarding_groups(
    university_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Return all available groups structured for the onboarding wizard.

    Response shape::

        {
          "departments": [
            {
              "id": 1,
              "name": "Engineering",
              "levels": [
                {
                  "level": 1,
                  "groups": [
                    { "id": 5, "name": "GEN Year 1", "display_code": "GEN1", "size": 120 },
                    ...
                  ]
                },
                ...
              ]
            },
            ...
          ]
        }

    Only departments and levels that actually have groups are returned,
    so the frontend dropdown never shows an empty selection.
    """
    query = db.query(StudentGroup)
    if university_id:
        query = query.filter(StudentGroup.university_id == university_id)

    all_groups = query.order_by(
        StudentGroup.department_id.asc(),
        StudentGroup.level.asc(),
        StudentGroup.name.asc(),
    ).all()

    if not all_groups:
        return {"departments": []}

    # ── Only expose leaf groups (no children) ────────────────────────────────
    # Parent/cohort groups (Year 5 cohort) are infrastructure — students should
    # only select the specific stream or single-group they actually belong to.
    # A leaf group is one whose id does not appear as any group's parent_group_id.
    all_parent_ids = {g.parent_group_id for g in all_groups if g.parent_group_id}
    leaf_groups = [g for g in all_groups if g.id not in all_parent_ids]

    # ── Collect departments ───────────────────────────────────────────────────
    dept_ids = {g.department_id for g in leaf_groups}
    departments = (
        db.query(Department)
        .filter(Department.id.in_(dept_ids))
        .order_by(Department.name.asc())
        .all()
    )

    def _normalize_level(raw_level) -> int:
        """Map 100-scale levels (100, 200 … 700) to 1-7, pass normal values through."""
        if raw_level is None:
            return 0
        v = int(raw_level)
        if v >= 100 and v % 100 == 0:
            return v // 100
        return v

    result: List[Dict[str, Any]] = []
    for dept in departments:
        dept_leaves = [g for g in leaf_groups if g.department_id == dept.id]
        level_map: Dict[int, List[Dict[str, Any]]] = {}
        for g in dept_leaves:
            norm_level = _normalize_level(g.level)
            entry = {
                "id": g.id,
                "name": g.name,
                "display_code": g.display_code,
                "size": g.size,
                "group_type": getattr(g.group_type, "value", str(g.group_type)) if g.group_type else None,
                "parent_group_id": g.parent_group_id,
            }
            level_map.setdefault(norm_level, []).append(entry)

        levels = [
            {"level": lvl, "groups": sorted(grps, key=lambda x: x["name"])}
            for lvl, grps in sorted(level_map.items())
        ]
        result.append({"id": dept.id, "name": dept.name, "code": dept.code, "levels": levels})

    return {"departments": result}


# ── Dashboard ───────────────────────────────────────────────────────────────


@router.get("/dashboard")
async def get_public_dashboard(
    group_id: int = Query(..., description="Student group ID"),
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    context = _resolve_public_context(db, group_id)
    serialized = [_serialize_slot(s) for s in context["slots"]]

    local_now = _get_local_now(db, context["group"])
    today_name = local_now.strftime("%A")
    now_minutes = local_now.hour * 60 + local_now.minute

    today_sessions = [s for s in serialized if s["day_of_week"] == today_name]
    current_session = _find_current_session(today_sessions, today_name, now_minutes)
    next_session = _find_next_session(serialized, today_name, now_minutes)

    payload = {
        "profile": _build_profile_payload(context),
        "timetable": _build_timetable_payload(context),
        "today_name": today_name,
        "generated_at": datetime.utcnow().isoformat(),
        "stats": {
            "today_total_sessions": len(today_sessions),
            "week_total_sessions": len(serialized),
        },
        "current_session": current_session,
        "next_session": next_session,
        "today_sessions": today_sessions,
    }

    return _with_conditional_etag(payload, request, response)


# ── Now ─────────────────────────────────────────────────────────────────────


@router.get("/now")
async def get_public_now(
    group_id: int = Query(..., description="Student group ID"),
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    context = _resolve_public_context(db, group_id)
    serialized = [_serialize_slot(s) for s in context["slots"]]

    local_now = _get_local_now(db, context["group"])
    today_name = local_now.strftime("%A")
    now_minutes = local_now.hour * 60 + local_now.minute

    today_sessions = [s for s in serialized if s["day_of_week"] == today_name]
    current_session = _find_current_session(today_sessions, today_name, now_minutes)
    next_session = _find_next_session(serialized, today_name, now_minutes)

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


# ── Today ───────────────────────────────────────────────────────────────────


@router.get("/today")
async def get_public_today(
    group_id: int = Query(..., description="Student group ID"),
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    context = _resolve_public_context(db, group_id)
    local_now = _get_local_now(db, context["group"])
    today_name = local_now.strftime("%A")
    sessions = [
        _serialize_slot(s)
        for s in context["slots"]
        if s.day_of_week == today_name
    ]

    payload = {
        "profile": _build_profile_payload(context),
        "timetable": _build_timetable_payload(context),
        "day": today_name,
        "sessions": sessions,
    }

    return _with_conditional_etag(payload, request, response)


# ── Week ────────────────────────────────────────────────────────────────────


@router.get("/week")
async def get_public_week(
    group_id: int = Query(..., description="Student group ID"),
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    context = _resolve_public_context(db, group_id)
    sessions = [_serialize_slot(s) for s in context["slots"]]

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


# ── Courses ─────────────────────────────────────────────────────────────────


@router.get("/courses")
async def get_public_courses(
    group_id: int = Query(..., description="Student group ID"),
    db: Session = Depends(get_db),
):
    context = _resolve_public_context(db, group_id)
    slots = context["slots"]

    seen: set[int] = set()
    courses: List[Dict[str, Any]] = []
    for slot in slots:
        course = slot.course
        if not course or course.id in seen:
            continue
        seen.add(course.id)
        courses.append(
            {
                "id": course.id,
                "code": course.code,
                "name": course.name,
                "credit_hours": course.credits,
                "course_type": getattr(course.course_type, "value", str(course.course_type)),
                "lecturer": {"name": slot.lecturer.full_name}
                if slot.lecturer
                else None,
            }
        )

    return courses


# ── Lookup ──────────────────────────────────────────────────────────────────


@router.get("/lookup")
async def public_lookup(
    q: str,
    group_id: int = Query(..., description="Student group ID"),
    db: Session = Depends(get_db),
):
    query = q.strip()
    if len(query) < 2:
        return {"results": []}

    group = _resolve_group(db, group_id)
    university_id = group.university_id

    lecturer_q = db.query(Lecturer).filter(Lecturer.department_id == group.department_id)
    room_q = db.query(Room).filter(Room.university_id == university_id)
    group_q = (
        db.query(StudentGroup)
        .filter(StudentGroup.university_id == university_id)
        .filter(StudentGroup.department_id == group.department_id)
    )
    course_q = db.query(Course).filter(Course.department_id == group.department_id)

    lecturers = (
        lecturer_q.filter(
            (Lecturer.full_name.ilike(f"%{query}%"))
            | (Lecturer.staff_number.ilike(f"%{query}%"))
        )
        .order_by(Lecturer.full_name.asc())
        .limit(5)
        .all()
    )
    rooms = (
        room_q.filter(
            (Room.name.ilike(f"%{query}%")) | (Room.building.ilike(f"%{query}%"))
        )
        .order_by(Room.name.asc())
        .limit(5)
        .all()
    )
    groups = (
        group_q.filter(StudentGroup.name.ilike(f"%{query}%"))
        .order_by(StudentGroup.name.asc())
        .limit(5)
        .all()
    )
    courses = (
        course_q.filter(
            (Course.code.ilike(f"%{query}%")) | (Course.name.ilike(f"%{query}%"))
        )
        .order_by(Course.code.asc())
        .limit(5)
        .all()
    )

    results: List[Dict[str, Any]] = []
    for lec in lecturers:
        results.append(
            {
                "type": "lecturer",
                "id": lec.id,
                "title": lec.full_name,
                "subtitle": lec.staff_number,
                # email intentionally omitted
            }
        )
    for room in rooms:
        results.append(
            {
                "type": "room",
                "id": room.id,
                "title": room.name,
                "subtitle": room.building,
                "meta": f"Capacity {room.capacity}",
            }
        )
    for grp in groups:
        results.append(
            {
                "type": "group",
                "id": grp.id,
                "title": grp.name,
                "subtitle": f"Level {grp.level}",
                "meta": f"{grp.size} students",
            }
        )
    for c in courses:
        results.append(
            {
                "type": "course",
                "id": c.id,
                "title": c.code,
                "subtitle": c.name,
                "meta": f"Level {c.level}",
            }
        )

    return {"results": results}


# ── Lookup Detail ───────────────────────────────────────────────────────────


def _build_availability_payload(sessions: List[Dict[str, Any]], local_now: datetime = None) -> Dict[str, Any]:
    if local_now is None:
        local_now = datetime.now()
    today_name = local_now.strftime("%A")
    now_minutes = local_now.hour * 60 + local_now.minute

    ordered = sorted(
        sessions,
        key=lambda s: (
            DAY_ORDER.get(s["day_of_week"], 999),
            s["start_time"],
            s["end_time"],
        ),
    )

    current_session = _find_current_session(ordered, today_name, now_minutes)
    next_session = _find_next_session(ordered, today_name, now_minutes)

    return {
        "today_name": today_name,
        "is_busy_now": current_session is not None,
        "current_session": current_session,
        "next_session": next_session,
        "today_sessions": [s for s in ordered if s["day_of_week"] == today_name],
    }


def _resolve_reference_timetable(db: Session, group: StudentGroup) -> Optional[Timetable]:
    query = (
        db.query(Timetable)
        .filter(Timetable.university_id == group.university_id)
        .options(
            joinedload(Timetable.slots).joinedload(TimetableSlot.course),
            joinedload(Timetable.slots).joinedload(TimetableSlot.lecturer),
            joinedload(Timetable.slots).joinedload(TimetableSlot.room),
            joinedload(Timetable.slots).joinedload(TimetableSlot.group),
        )
        .order_by(Timetable.is_active.desc(), Timetable.id.desc())
    )
    return query.first()


@router.get("/lookup/{entity_type}/{entity_id}")
async def public_lookup_detail(
    entity_type: str,
    entity_id: int,
    group_id: int = Query(..., description="Student group ID"),
    db: Session = Depends(get_db),
):
    group = _resolve_group(db, group_id)
    timetable = _resolve_reference_timetable(db, group)
    if not timetable:
        raise HTTPException(status_code=404, detail="No timetable available for lookup.")

    serialized = [_serialize_slot(s) for s in timetable.slots]

    if entity_type == "lecturer":
        entity_obj = db.query(Lecturer).filter(Lecturer.id == entity_id).first()
        if not entity_obj:
            raise HTTPException(status_code=404, detail="Lecturer not found")
        sessions = [s for s in serialized if s["lecturer_name"] == entity_obj.full_name]
        entity = {
            "type": "lecturer",
            "id": entity_obj.id,
            "title": entity_obj.full_name,
            "subtitle": entity_obj.staff_number,
        }
    elif entity_type == "room":
        entity_obj = db.query(Room).filter(Room.id == entity_id).first()
        if not entity_obj:
            raise HTTPException(status_code=404, detail="Room not found")
        sessions = [s for s in serialized if s["room_name"] == entity_obj.name]
        entity = {
            "type": "room",
            "id": entity_obj.id,
            "title": entity_obj.name,
            "subtitle": entity_obj.building,
            "meta": f"Capacity {entity_obj.capacity}",
        }
    elif entity_type == "group":
        entity_obj = db.query(StudentGroup).filter(StudentGroup.id == entity_id).first()
        if not entity_obj:
            raise HTTPException(status_code=404, detail="Group not found")
        sessions = [s for s in serialized if s["group_name"] == entity_obj.name]
        entity = {
            "type": "group",
            "id": entity_obj.id,
            "title": entity_obj.name,
            "subtitle": f"Level {entity_obj.level}",
            "meta": f"{entity_obj.size} students",
        }
    elif entity_type == "course":
        entity_obj = db.query(Course).filter(Course.id == entity_id).first()
        if not entity_obj:
            raise HTTPException(status_code=404, detail="Course not found")
        sessions = [s for s in serialized if s["course_id"] == entity_obj.id]
        entity = {
            "type": "course",
            "id": entity_obj.id,
            "title": entity_obj.code,
            "subtitle": entity_obj.name,
            "meta": f"Level {entity_obj.level}",
        }
    else:
        raise HTTPException(status_code=400, detail="Unsupported lookup type")

    return {
        "entity": entity,
        "availability": _build_availability_payload(sessions, _get_local_now(db, group)),
        "sessions": sorted(
            sessions,
            key=lambda s: (
                DAY_ORDER.get(s["day_of_week"], 999),
                s["start_time"],
                s["end_time"],
            ),
        ),
    }


# ── Free Rooms ──────────────────────────────────────────────────────────────


@router.get("/rooms/free-now")
async def get_public_free_rooms_now(
    group_id: int = Query(..., description="Student group ID"),
    building: Optional[str] = None,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    group = _resolve_group(db, group_id)
    university_id = group.university_id

    timetable = _resolve_reference_timetable(db, group)
    if not timetable:
        raise HTTPException(
            status_code=404, detail="No timetable available for room availability."
        )

    local_now = _get_local_now(db, group)
    today_name = local_now.strftime("%A")
    now_minutes = local_now.hour * 60 + local_now.minute

    occupied_room_ids = {
        slot.room_id
        for slot in timetable.slots
        if slot.room_id
        and slot.day_of_week == today_name
        and slot.start_time
        and slot.end_time
        and (slot.start_time.hour * 60 + slot.start_time.minute)
        <= now_minutes
        < (slot.end_time.hour * 60 + slot.end_time.minute)
    }

    rooms_query = db.query(Room).filter(Room.university_id == university_id)
    if building:
        rooms_query = rooms_query.filter(
            Room.building.ilike(f"%{building.strip()}%")
        )

    rooms = rooms_query.order_by(Room.building.asc(), Room.name.asc()).all()
    free_rooms = [
        r for r in rooms if r.id not in occupied_room_ids and not r.is_blocked
    ]

    payload = {
        "today_name": today_name,
        "checked_at": datetime.utcnow().isoformat(),
        "total_rooms": len(rooms),
        "occupied_rooms": len(occupied_room_ids),
        "free_rooms": [
            {
                "id": r.id,
                "name": r.name,
                "building": r.building,
                "capacity": r.capacity,
                "room_type": r.room_type,
            }
            for r in free_rooms
        ],
    }

    return _with_conditional_etag(payload, request, response)


# ── Announcements ───────────────────────────────────────────────────────────

@router.get("/announcements")
async def get_public_announcements(
    group_id: int = Query(..., description="Student group ID"),
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    context = _resolve_public_context(db, group_id)
    slots = context["slots"]

    course_ids = list({s.course_id for s in slots if s.course_id})
    if not course_ids:
        return _with_conditional_etag({"announcements": []}, request, response)

    announcements = db.query(CourseAnnouncement).filter(
        CourseAnnouncement.course_id.in_(course_ids)
    ).order_by(CourseAnnouncement.created_at.desc()).all()

    payload = {
        "announcements": [
            {
                "id": a.id,
                "course_id": a.course_id,
                "title": a.title,
                "message": a.message,
                "type": a.announcement_type,
                "target_date": a.target_date.isoformat() if a.target_date else None,
                "venue": a.venue,
                "created_at": a.created_at.isoformat(),
                "lecturer_name": a.lecturer.full_name if a.lecturer else "Lecturer",
                "course_code": a.course.code if a.course else ""
            }
            for a in announcements
        ]
    }

    return _with_conditional_etag(payload, request, response)
