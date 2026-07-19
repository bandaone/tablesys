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
from sqlalchemy import or_

from ..database import get_db
from ..models import (
    ActivityType,
    Course,
    Department,
    Lecturer,
    Room,
    School,
    StudentGroup,
    Timetable,
    TimetableSlot,
    University,
    CourseAnnouncement,
    LabSession,
    LabSessionStatus,
)
from ..utils.sanitization import sanitize_input

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


def _resolve_public_university_id(
    db: Session,
    request: Optional[Request],
    university_id: Optional[int],
) -> int:
    header_val = None
    if request is not None:
        header_val = request.headers.get("X-University-ID")

    resolved_id: Optional[int] = None
    if university_id is not None:
        resolved_id = university_id
    elif header_val:
        try:
            resolved_id = int(header_val)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid university context header.",
            )

    if resolved_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="University context is required.",
        )

    uni = db.query(University).filter(
        University.id == resolved_id,
        University.is_active == True,
    ).first()
    if not uni:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="University not found or inactive.",
        )
    return uni.id


# ── Helpers ─────────────────────────────────────────────────────────────────


def _format_time(value: Optional[time]) -> str:
    if value is None:
        return ""
    return value.strftime("%H:%M")


def _activity_type_map(db: Session, university_id: Optional[int]) -> Dict[str, Dict[str, str]]:
    if not university_id:
        return {}
    rows = (
        db.query(ActivityType)
        .filter(
            ActivityType.university_id == university_id,
            ActivityType.is_active == True,
        )
        .all()
    )
    return {
        str(row.key).strip().lower(): {
            "display_name": row.display_name,
            "color": row.color or "#3B82F6",
        }
        for row in rows
    }


def _get_effective_group_ids(
    db: Session, group_id: int, *, include_descendants: bool = False
) -> set[int]:
    """
    Return the groups whose normal teaching slots belong to a selected group.

    A selection inherits its parents (cohort and stream teaching), but it does
    not automatically inherit every child lab/tutorial group.  That previously
    made a student selecting a parent cohort see every parallel lab.  Child
    groups are added only when the student selects them in the lab selector.
    Callers that genuinely need the full hierarchy, such as exam allocation,
    can explicitly request descendants.
    """
    effective_ids: set[int] = set()
    
    # 1. Walk UP the chain (ancestors)
    current_id: Optional[int] = group_id
    max_depth = 10
    while current_id and max_depth > 0:
        effective_ids.add(current_id)
        group = db.query(StudentGroup).filter(StudentGroup.id == current_id).first()
        if not group or not group.parent_group_id:
            break
        current_id = group.parent_group_id
        max_depth -= 1

    if not include_descendants:
        return effective_ids

    # 2. Walk DOWN the chain (descendants) for aggregate use cases only.
    from collections import deque
    queue = deque([group_id])
    while queue:
        curr = queue.popleft()
        effective_ids.add(curr)
        children = db.query(StudentGroup.id).filter(StudentGroup.parent_group_id == curr).all()
        for (child_id,) in children:
            if child_id not in effective_ids:
                queue.append(child_id)

    return effective_ids


def _validate_selected_subgroups(
    db: Session,
    group_id: int,
    selected_subgroup_ids: List[int],
    university_id: int,
) -> set[int]:
    """Keep optional lab/tutorial selections within the selected group tree."""
    if not selected_subgroup_ids:
        return set()

    # Lab groups may be attached directly to the selected stream or to its
    # parent cohort (legacy data and rotating master labs).  They are optional
    # viewer choices, never a login identity, so make both locations available.
    permitted: set[int] = set()
    for ancestor_id in _get_effective_group_ids(db, group_id):
        permitted.update(_get_effective_group_ids(db, ancestor_id, include_descendants=True))
    selected = {int(value) for value in selected_subgroup_ids}
    if not selected.issubset(permitted):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected lab or tutorial groups must belong to the selected programme group.",
        )

    valid_count = (
        db.query(StudentGroup.id)
        .filter(
            StudentGroup.id.in_(selected),
            StudentGroup.university_id == university_id,
        )
        .count()
    )
    if valid_count != len(selected):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid subgroup selection.")
    return selected


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


def _resolve_group(db: Session, group_id: int, university_id: Optional[int] = None) -> StudentGroup:
    """Load and validate the requested group."""
    group = db.query(StudentGroup).filter(StudentGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found. Please select a valid group.",
        )
    if university_id is not None and group.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Group does not belong to this institution.",
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
    department = db.query(Department).filter(Department.id == group.department_id).first() if group else None
    school_id = department.school_id if department else None

    timetables = (
        db.query(Timetable)
        .filter(
            Timetable.university_id == group.university_id,
            Timetable.is_active == True,
            or_(Timetable.school_id == school_id, Timetable.school_id == None) if school_id else True
        )
        .options(
            joinedload(Timetable.slots).joinedload(TimetableSlot.course),
            joinedload(Timetable.slots).joinedload(TimetableSlot.lecturer),
            joinedload(Timetable.slots).joinedload(TimetableSlot.room),
            joinedload(Timetable.slots).joinedload(TimetableSlot.group),
        )
        .order_by(Timetable.id.desc())
        .all()
    )

    matching: List[Timetable] = []
    for tt in timetables:
        if any(_slot_matches_effective_groups(slot, effective_ids) for slot in tt.slots):
            matching.append(tt)
    return matching


def _resolve_public_context(
    db: Session, 
    group_id: int, 
    university_id: int,
    academic_week: Optional[int] = None,
    lab_subgroup_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    group = _resolve_group(db, group_id, university_id)
    effective_ids = _get_effective_group_ids(db, group_id)
    selected_subgroups = _validate_selected_subgroups(
        db, group_id, lab_subgroup_ids or [], university_id
    )

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

    # Labs/tutorials are separate events.  Show only the selected subgroup(s)
    # plus any session intentionally attached to the selected parent group,
    # and only when they belong to the currently published timetable.
    lab_group_ids = effective_ids | selected_subgroups
    lab_sessions = (
        db.query(LabSession)
        .filter(
            LabSession.university_id == university_id,
            LabSession.timetable_id == timetable.id,
            LabSession.group_id.in_(lab_group_ids),
            LabSession.status.in_([LabSessionStatus.PUBLISHED, LabSessionStatus.SCHEDULED]),
        )
        .options(
            joinedload(LabSession.course),
            joinedload(LabSession.room)
        )
        .all()
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
        "lab_sessions": lab_sessions,
        "effective_group_ids": effective_ids,
        "group_breadcrumb": breadcrumb,
        "academic_week": academic_week,
        "lab_subgroup_ids": list(selected_subgroups),
    }


def _serialize_slot(
    slot: TimetableSlot,
    activity_types_by_key: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Serialize a slot — lecturer email is intentionally omitted."""
    course = slot.course
    lecturer = slot.lecturer
    room = slot.room
    group = slot.group
    activity_key = str(slot.session_type or "").strip().lower()
    activity_meta = (activity_types_by_key or {}).get(activity_key, {})

    return {
        "id": slot.id,
        "day_of_week": _day_name(slot.day_of_week),
        "start_time": _format_time(slot.start_time),
        "end_time": _format_time(slot.end_time),
        "session_type": slot.session_type,
        "activity_type_key": activity_key or None,
        "activity_display_name": activity_meta.get("display_name"),
        "activity_color": activity_meta.get("color"),
        "course_id": slot.course_id,
        "course_code": course.code if course else "N/A",
        "course_name": course.name if course else "N/A",
        "lecturer_name": lecturer.full_name if lecturer else "Unassigned",
        "room_name": room.name if room else "TBA",
        "room_number": room.name if room else "TBA",
        "building": room.building if room else "TBA",
        "group_name": group.name if group else "N/A",
    }


def _serialize_lab_session(
    ls: LabSession,
    activity_types_by_key: Optional[Dict[str, Dict[str, str]]] = None,
    active_subgroup_ids: Optional[List[int]] = None,
    subgroup_label: str = "Lab Group",
) -> Dict[str, Any]:
    course = ls.course
    room = ls.room
    activity_key = str(ls.session_type or "lab").strip().lower()
    activity_meta = (activity_types_by_key or {}).get(activity_key, {})

    return {
        "id": f"lab_{ls.id}",
        "day_of_week": _day_name(ls.day_of_week),
        "start_time": _format_time(ls.start_time),
        "end_time": _format_time(ls.end_time),
        "session_type": ls.session_type,
        "activity_type_key": activity_key or None,
        "activity_display_name": activity_meta.get("display_name", "Lab Session"),
        "activity_color": activity_meta.get("color", "#7C3AED"),
        "course_id": ls.course_id,
        "course_code": course.code if course else "N/A",
        "course_name": course.name if course else "N/A",
        "lecturer_name": "Unassigned",
        "room_name": room.name if room else "TBA",
        "room_number": room.name if room else "TBA",
        "building": room.building if room else "TBA",
        "group_name": subgroup_label,
        "is_lab_session": True,
        "lab_session_id": ls.id,
        "rotation_cycle_length": ls.rotation_cycle_length,
        "rotation_configuration": ls.rotation_configuration,
        "active_subgroup_ids": active_subgroup_ids,
    }


def _get_all_serialized_sessions(db: Session, context: Dict[str, Any], activity_types_by_key: Dict[str, Any]) -> List[Dict[str, Any]]:
    sessions = [_serialize_slot(s, activity_types_by_key) for s in context["slots"]]
    academic_week = context.get("academic_week")
    lab_subgroup_ids = context.get("lab_subgroup_ids", [])
    effective_ids = context["effective_group_ids"]

    for ls in context.get("lab_sessions", []):
        active_subgroup_ids = None
        subgroup_label = "Lab Group"
        
        if ls.rotation_configuration and academic_week is not None:
            cycle_pos = str(((academic_week - 1) % ls.rotation_cycle_length) + 1)
            active_subgroup_ids = ls.rotation_configuration.get(cycle_pos, [])
            
            # If the student selected specific lab subgroups, verify if their subgroup is active
            if lab_subgroup_ids:
                has_active = any(sg in active_subgroup_ids for sg in lab_subgroup_ids)
                if not has_active:
                    continue  # The student's chosen subgroup is not scheduled this week
            
            sub_names = []
            for sg_id in active_subgroup_ids:
                sg = db.query(StudentGroup).filter(StudentGroup.id == int(sg_id)).first()
                if sg:
                    sub_names.append(sg.name)
            subgroup_label = ", ".join(sub_names) if sub_names else "No subgroups this week"

        # A rotating master slot may be attached to a parent group.  Do not
        # show it to a self-selected subgroup unless that subgroup is active.
        if lab_subgroup_ids and active_subgroup_ids is None and ls.group_id not in lab_subgroup_ids:
            continue
        
        sessions.append(_serialize_lab_session(ls, activity_types_by_key, active_subgroup_ids, subgroup_label))
        
    return sessions


def _build_lab_subgroup_catalog(db: Session, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    catalog: Dict[int, Dict[str, Any]] = {}
    academic_week = context.get("academic_week")

    for ls in context.get("lab_sessions", []):
        if not ls.rotation_configuration:
            continue

        course = ls.course
        active_subgroup_ids: List[int] = []
        if academic_week is not None:
            cycle_pos = str(((academic_week - 1) % max(ls.rotation_cycle_length, 1)) + 1)
            active_subgroup_ids = [
                int(group_id)
                for group_id in ls.rotation_configuration.get(cycle_pos, [])
                if str(group_id).isdigit()
            ]

        for week_key, subgroup_ids in ls.rotation_configuration.items():
            for subgroup_id_raw in subgroup_ids or []:
                if not str(subgroup_id_raw).isdigit():
                    continue
                subgroup_id = int(subgroup_id_raw)
                subgroup = db.query(StudentGroup).filter(StudentGroup.id == subgroup_id).first()
                if not subgroup:
                    continue

                entry = catalog.setdefault(
                    subgroup_id,
                    {
                        "id": subgroup.id,
                        "name": subgroup.name,
                        "display_code": subgroup.display_code,
                        "group_type": getattr(subgroup.group_type, "value", str(subgroup.group_type)) if subgroup.group_type else None,
                        "parent_group_id": subgroup.parent_group_id,
                        "course_codes": [],
                        "course_names": [],
                        "rotation_weeks": [],
                        "active_this_week": False,
                    },
                )

                if course and course.code not in entry["course_codes"]:
                    entry["course_codes"].append(course.code)
                if course and course.name not in entry["course_names"]:
                    entry["course_names"].append(course.name)
                if week_key not in entry["rotation_weeks"]:
                    entry["rotation_weeks"].append(week_key)
                if subgroup_id in active_subgroup_ids:
                    entry["active_this_week"] = True

    # Also support individually scheduled lab/tutorial groups.  Older imports
    # and manual schedules may create one LabSession per child group rather
    # than one rotating master session on the parent group.
    descendant_ids: set[int] = set()
    for ancestor_id in context["effective_group_ids"]:
        descendant_ids.update(_get_effective_group_ids(db, ancestor_id, include_descendants=True))
    descendant_ids.difference_update(context["effective_group_ids"])
    if descendant_ids:
        direct_sessions = (
            db.query(LabSession)
            .filter(
                LabSession.timetable_id == context["timetable"].id,
                LabSession.group_id.in_(descendant_ids),
                LabSession.status.in_([LabSessionStatus.PUBLISHED, LabSessionStatus.SCHEDULED]),
            )
            .options(joinedload(LabSession.course))
            .all()
        )
        for ls in direct_sessions:
            subgroup = db.query(StudentGroup).filter(StudentGroup.id == ls.group_id).first()
            if not subgroup:
                continue
            entry = catalog.setdefault(
                subgroup.id,
                {
                    "id": subgroup.id,
                    "name": subgroup.name,
                    "display_code": subgroup.display_code,
                    "group_type": getattr(subgroup.group_type, "value", str(subgroup.group_type)) if subgroup.group_type else None,
                    "parent_group_id": subgroup.parent_group_id,
                    "course_codes": [],
                    "course_names": [],
                    "rotation_weeks": [],
                    "active_this_week": True,
                },
            )
            if ls.course and ls.course.code not in entry["course_codes"]:
                entry["course_codes"].append(ls.course.code)
            if ls.course and ls.course.name not in entry["course_names"]:
                entry["course_names"].append(ls.course.name)
            if "Every week" not in entry["rotation_weeks"]:
                entry["rotation_weeks"].append("Every week")

    return sorted(catalog.values(), key=lambda item: (item["name"] or "", item["id"]))


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
    request: Request,
    university_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Return all available groups structured for the onboarding wizard.

    Response shape::

        {
          "schools": [
            {
              "id": 1, "name": "School of Engineering", "departments": [...]
            },
            ...
          ]
        }

    Only departments and levels that actually have groups are returned,
    so the frontend dropdown never shows an empty selection.
    """
    resolved_university_id = _resolve_public_university_id(db, request, university_id)

    query = db.query(StudentGroup).filter(
        StudentGroup.university_id == resolved_university_id
    )

    all_groups = query.order_by(
        StudentGroup.department_id.asc(),
        StudentGroup.level.asc(),
        StudentGroup.name.asc(),
    ).all()

    if not all_groups:
        return {"schools": [], "departments": []}

    # ── Login identity: stream or unsplit cohort only ────────────────────────
    # Lab/tutorial/drawing groups are delivery detail.  They must never replace
    # EMP/ET (or an unsplit cohort) in the student's initial selection.
    #
    # A stream remains selectable even when it has lab children.  A root cohort
    # is selectable only if it has no elective streams; this keeps a simple
    # cohort usable while preventing duplicate parent + stream choices.
    child_stream_parent_ids = {
        g.parent_group_id
        for g in all_groups
        if g.parent_group_id and str(getattr(g.group_type, "value", g.group_type)) == "stream"
    }
    selectable_groups = [
        g
        for g in all_groups
        if (
            str(getattr(g.group_type, "value", g.group_type)) == "stream"
            or (
                g.parent_group_id is None
                and str(getattr(g.group_type, "value", g.group_type)) in {"general", "department", "None"}
                and g.id not in child_stream_parent_ids
            )
        )
    ]

    # ── Collect departments ───────────────────────────────────────────────────
    dept_ids = {g.department_id for g in selectable_groups}
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
        dept_leaves = [g for g in selectable_groups if g.department_id == dept.id]
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

    # The public selector is intentionally school-first.  A department must
    # belong to an active school before its students can self-identify; this
    # prevents a timetable from one school appearing in another school's path.
    # List every active school in this tenant first.  A school must not vanish
    # from the public identity path merely because one of its departments has
    # not yet had groups or a timetable loaded.
    schools_by_id = {
        school.id: school
        for school in db.query(School).filter(
            School.university_id == resolved_university_id,
            School.is_active == True,
        ).all()
    }
    school_buckets: Dict[int, Dict[str, Any]] = {
        school.id: {
            "id": school.id,
            "name": school.name,
            "code": school.code,
            "departments": [],
        }
        for school in schools_by_id.values()
    }
    for department_entry, department_model in zip(result, departments):
        school = schools_by_id.get(department_model.school_id)
        if not school:
            continue
        school_id = school.id
        bucket = school_buckets[school_id]
        bucket["departments"].append(department_entry)

    schools = sorted(
        school_buckets.values(),
        key=lambda item: item["name"].lower(),
    )
    for school in schools:
        school["departments"].sort(key=lambda item: item["name"].lower())
    # Keep departments during the transition so cached/mobile clients built on
    # earlier versions do not fail. New clients use the school hierarchy only.
    return {"schools": schools, "departments": result}


@router.get("/lab-subgroups")
async def get_public_lab_subgroups(
    group_id: int = Query(..., description="Student group ID"),
    academic_week: Optional[int] = Query(None, description="Academic week for lab rotation"),
    university_id: Optional[int] = None,
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Return the rotating lab subgroups available to a student group."""
    resolved_university_id = _resolve_public_university_id(db, request, university_id)
    context = _resolve_public_context(db, group_id, resolved_university_id, academic_week)
    return {
        "group_id": group_id,
        "academic_week": academic_week,
        "lab_subgroups": _build_lab_subgroup_catalog(db, context),
    }


# ── Dashboard ───────────────────────────────────────────────────────────────


@router.get("/dashboard")
async def get_public_dashboard(
    group_id: int = Query(..., description="Student group ID"),
    academic_week: Optional[int] = Query(None, description="Academic week for lab rotation"),
    lab_subgroup_ids: Optional[str] = Query(None, description="Comma-separated list of selected lab subgroups"),
    university_id: Optional[int] = None,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    resolved_university_id = _resolve_public_university_id(db, request, university_id)
    subgroups = [int(i) for i in lab_subgroup_ids.split(",")] if lab_subgroup_ids else []
    context = _resolve_public_context(db, group_id, resolved_university_id, academic_week, subgroups)
    activity_types_by_key = _activity_type_map(db, context["group"].university_id)
    serialized = _get_all_serialized_sessions(db, context, activity_types_by_key)

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
    academic_week: Optional[int] = Query(None, description="Academic week for lab rotation"),
    lab_subgroup_ids: Optional[str] = Query(None, description="Comma-separated list of selected lab subgroups"),
    university_id: Optional[int] = None,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    resolved_university_id = _resolve_public_university_id(db, request, university_id)
    subgroups = [int(i) for i in lab_subgroup_ids.split(",")] if lab_subgroup_ids else []
    context = _resolve_public_context(db, group_id, resolved_university_id, academic_week, subgroups)
    activity_types_by_key = _activity_type_map(db, context["group"].university_id)
    serialized = _get_all_serialized_sessions(db, context, activity_types_by_key)

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
    academic_week: Optional[int] = Query(None, description="Academic week for lab rotation"),
    lab_subgroup_ids: Optional[str] = Query(None, description="Comma-separated list of selected lab subgroups"),
    university_id: Optional[int] = None,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    resolved_university_id = _resolve_public_university_id(db, request, university_id)
    subgroups = [int(i) for i in lab_subgroup_ids.split(",")] if lab_subgroup_ids else []
    context = _resolve_public_context(db, group_id, resolved_university_id, academic_week, subgroups)
    activity_types_by_key = _activity_type_map(db, context["group"].university_id)
    local_now = _get_local_now(db, context["group"])
    today_name = local_now.strftime("%A")
    all_sessions = _get_all_serialized_sessions(db, context, activity_types_by_key)
    sessions = [s for s in all_sessions if s["day_of_week"] == today_name]

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
    academic_week: Optional[int] = Query(None, description="Academic week for lab rotation"),
    lab_subgroup_ids: Optional[str] = Query(None, description="Comma-separated list of selected lab subgroups"),
    university_id: Optional[int] = None,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    resolved_university_id = _resolve_public_university_id(db, request, university_id)
    subgroups = [int(i) for i in lab_subgroup_ids.split(",")] if lab_subgroup_ids else []
    context = _resolve_public_context(db, group_id, resolved_university_id, academic_week, subgroups)
    activity_types_by_key = _activity_type_map(db, context["group"].university_id)
    sessions = _get_all_serialized_sessions(db, context, activity_types_by_key)

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
    university_id: Optional[int] = None,
    db: Session = Depends(get_db),
    request: Request = None,
):
    resolved_university_id = _resolve_public_university_id(db, request, university_id)
    context = _resolve_public_context(db, group_id, resolved_university_id)
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
    request: Request = None,
    university_id: Optional[int] = None,
):
    resolved_university_id = _resolve_public_university_id(db, request, university_id)
    query = sanitize_input(q, max_length=100).strip()
    if len(query) < 2:
        return {"results": []}

    group = _resolve_group(db, group_id, resolved_university_id)
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
    department = db.query(Department).filter(Department.id == group.department_id).first() if group else None
    school_id = department.school_id if department else None

    query = (
        db.query(Timetable)
        .filter(
            Timetable.university_id == group.university_id,
            Timetable.is_active == True,
            or_(Timetable.school_id == school_id, Timetable.school_id == None) if school_id else True
        )
        .options(
            joinedload(Timetable.slots).joinedload(TimetableSlot.course),
            joinedload(Timetable.slots).joinedload(TimetableSlot.lecturer),
            joinedload(Timetable.slots).joinedload(TimetableSlot.room),
            joinedload(Timetable.slots).joinedload(TimetableSlot.group),
        )
        .order_by(Timetable.id.desc())
    )
    return query.first()


@router.get("/lookup/{entity_type}/{entity_id}")
async def public_lookup_detail(
    entity_type: str,
    entity_id: int,
    group_id: int = Query(..., description="Student group ID"),
    db: Session = Depends(get_db),
    request: Request = None,
    university_id: Optional[int] = None,
):
    resolved_university_id = _resolve_public_university_id(db, request, university_id)
    group = _resolve_group(db, group_id, resolved_university_id)
    timetable = _resolve_reference_timetable(db, group)
    if not timetable:
        raise HTTPException(status_code=404, detail="No timetable available for lookup.")

    entity_type = sanitize_input(entity_type, max_length=50).strip().lower()

    activity_types_by_key = _activity_type_map(db, group.university_id)
    serialized = [_serialize_slot(s, activity_types_by_key) for s in timetable.slots]

    if entity_type == "lecturer":
        entity_obj = db.query(Lecturer).filter(
            Lecturer.id == entity_id,
            Lecturer.department_id == group.department_id,
        ).first()
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
        entity_obj = db.query(Room).filter(
            Room.id == entity_id,
            Room.university_id == group.university_id,
        ).first()
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
        entity_obj = db.query(StudentGroup).filter(
            StudentGroup.id == entity_id,
            StudentGroup.university_id == group.university_id,
        ).first()
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
        entity_obj = db.query(Course).filter(
            Course.id == entity_id,
            Course.department_id == group.department_id,
        ).first()
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
    university_id: Optional[int] = None,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    resolved_university_id = _resolve_public_university_id(db, request, university_id)
    group = _resolve_group(db, group_id, resolved_university_id)
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
        safe_building = sanitize_input(building, max_length=100).strip()
        rooms_query = rooms_query.filter(
            Room.building.ilike(f"%{safe_building}%")
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
    university_id: Optional[int] = None,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    resolved_university_id = _resolve_public_university_id(db, request, university_id)
    context = _resolve_public_context(db, group_id, resolved_university_id)
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

# ── Exam Timetables ─────────────────────────────────────────────────────────

@router.get("/exam-timetable")
async def get_public_exam_timetable(
    group_id: int = Query(..., description="Student group ID"),
    university_id: Optional[int] = None,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    resolved_university_id = _resolve_public_university_id(db, request, university_id)
    group = _resolve_group(db, group_id, resolved_university_id)
    effective_ids = _get_effective_group_ids(db, group_id, include_descendants=True)

    from ..models import ExamPeriod, ExamSlot, ExamSlotRoom, ExamPaper, Lecturer, Course, Room

    # Get active published exam period
    period = (
        db.query(ExamPeriod)
        .filter(
            ExamPeriod.university_id == resolved_university_id,
            ExamPeriod.is_published == True
        )
        .order_by(ExamPeriod.start_date.desc())
        .first()
    )

    if not period:
        return {"period": None, "slots": []}

    # Find all slots where this group is allocated
    slots = (
        db.query(ExamSlot)
        .join(ExamPaper, ExamSlot.exam_paper_id == ExamPaper.id)
        .filter(ExamSlot.exam_period_id == period.id)
        .options(
            joinedload(ExamSlot.paper).joinedload(ExamPaper.course),
            joinedload(ExamSlot.chief_invigilator),
            joinedload(ExamSlot.room_allocations).joinedload(ExamSlotRoom.room),
        )
        .all()
    )

    # Build the full set of courses this student should see.
    # Start with direct group-to-course links (GroupAssignment + CourseGroupLink).
    from ..routers.groups import _effective_course_ids_for_group
    student_course_ids: set[int] = _effective_course_ids_for_group(db, group)

    # Also pull courses from the active lecture timetable — shared courses
    # (e.g. EEE courses taken by GEN) have lecture slots assigned directly to
    # the GEN group, so this captures cross-department courses that the
    # GroupAssignment / CourseGroupLink tables might not reflect.
    from ..models import Timetable as TimetableModel
    department = db.query(Department).filter(Department.id == group.department_id).first() if group else None
    school_id = department.school_id if department else None

    active_tt = (
        db.query(TimetableModel)
        .filter(
            TimetableModel.university_id == resolved_university_id,
            TimetableModel.is_active == True,
            or_(TimetableModel.school_id == school_id, TimetableModel.school_id == None) if school_id else True
        )
        .first()
    )
    if active_tt:
        lecture_slots = (
            db.query(TimetableSlot)
            .filter(TimetableSlot.timetable_id == active_tt.id)
            .all()
        )
        for ls in lecture_slots:
            if _slot_matches_effective_groups(ls, effective_ids):
                student_course_ids.add(ls.course_id)

    relevant_slots = []
    for slot in slots:
        paper_group_ids = slot.paper.group_ids or []

        if slot.paper.course_id is not None:
            # Course-based exam paper: show it if the student takes this course.
            # This handles shared / cross-department courses correctly — the
            # paper's group_ids may point to the owning department's group, but
            # the student still needs to sit the exam.
            is_relevant = slot.paper.course_id in student_course_ids
        else:
            # Non-course (custom) paper: fall back to group hierarchy match.
            is_relevant = any(gid in effective_ids for gid in paper_group_ids)

        if is_relevant:
            # Find exact room allocation
            allocated_rooms = []
            for alloc in slot.room_allocations:
                alloc_group_ids = alloc.allocated_group_ids or paper_group_ids
                if any(gid in effective_ids for gid in alloc_group_ids):
                    allocated_rooms.append(alloc.room.name if alloc.room else "TBA")
            
            # If no specific room matched, but paper did, just show all rooms
            if not allocated_rooms:
                allocated_rooms = [a.room.name for a in slot.room_allocations if a.room]

            relevant_slots.append({
                "id": slot.id,
                "exam_date": slot.exam_date.isoformat(),
                "day_of_week": slot.exam_date.strftime("%A"),
                "start_time": _format_time(slot.start_time),
                "end_time": _format_time(slot.end_time),
                "paper_code": slot.paper.paper_code,
                "paper_name": slot.paper.paper_name,
                "course_name": slot.paper.course.name if slot.paper.course else None,
                "chief_invigilator": slot.chief_invigilator.full_name if slot.chief_invigilator else "TBA",
                "rooms": allocated_rooms or ["TBA"],
                "duration_minutes": slot.paper.duration_minutes
            })

    # Sort slots by date and time
    relevant_slots.sort(key=lambda s: (s["exam_date"], s["start_time"]))

    return {
        "period": {
            "id": period.id,
            "name": period.name,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
        },
        "slots": relevant_slots
    }
