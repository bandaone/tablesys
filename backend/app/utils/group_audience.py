from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from ..models import CourseGroupLink, GroupAssignment, GroupType, StudentGroup, TimetableSlot


def group_display_label(group: Optional[StudentGroup]) -> str:
    if not group:
        return "Unknown Group"
    return group.display_code or group.name


def resolve_slot_audience_groups(
    db: Session,
    slot: TimetableSlot,
    *,
    group_cache: Optional[Dict[int, StudentGroup]] = None,
    stream_children_cache: Optional[Dict[int, List[StudentGroup]]] = None,
) -> List[StudentGroup]:
    """
    Resolve the real visible audience for a saved slot.

    Rules:
    - explicit shared_group_ids win and are used literally
    - otherwise, parent-group lectures prefer actual stream course mappings
      before falling back to legacy "show all streams" expansion
    - otherwise, the primary group alone is shown
    """
    cache = group_cache if group_cache is not None else {}
    children_cache = stream_children_cache if stream_children_cache is not None else {}

    def _get_group(group_id: Optional[int]) -> Optional[StudentGroup]:
        if not group_id:
            return None
        if group_id not in cache:
            cache[group_id] = (
                db.query(StudentGroup)
                .filter(StudentGroup.id == group_id)
                .first()
            )
        return cache[group_id]

    primary_group = _get_group(slot.group_id)
    if not primary_group:
        return []

    explicit_group_ids = [slot.group_id] + list(slot.shared_group_ids or [])
    if len(explicit_group_ids) > 1:
        resolved: List[StudentGroup] = []
        seen_ids = set()
        for group_id in explicit_group_ids:
            if group_id in seen_ids:
                continue
            seen_ids.add(group_id)
            group = _get_group(group_id)
            if group:
                resolved.append(group)
        return resolved

    if primary_group.parent_group_id is None:
        if primary_group.id not in children_cache:
            children_cache[primary_group.id] = (
                db.query(StudentGroup)
                .filter(
                    StudentGroup.parent_group_id == primary_group.id,
                    StudentGroup.group_type == GroupType.STREAM,
                )
                .order_by(StudentGroup.name.asc())
                .all()
            )
        stream_children = children_cache[primary_group.id]
        if stream_children:
            session_type = str(getattr(slot, "session_type", "") or "").strip().lower()
            course_id = getattr(slot, "course_id", None)
            stream_child_ids = [group.id for group in stream_children]

            if course_id and session_type == "lecture":
                linked_streams = (
                    db.query(StudentGroup)
                    .join(CourseGroupLink, CourseGroupLink.group_id == StudentGroup.id)
                    .filter(
                        CourseGroupLink.course_id == course_id,
                        CourseGroupLink.session_type == "lecture",
                        StudentGroup.id.in_(stream_child_ids),
                    )
                    .order_by(StudentGroup.name.asc())
                    .all()
                )
                if linked_streams:
                    return linked_streams

                assigned_streams = (
                    db.query(StudentGroup)
                    .join(GroupAssignment, GroupAssignment.group_id == StudentGroup.id)
                    .filter(
                        GroupAssignment.course_id == course_id,
                        StudentGroup.id.in_(stream_child_ids),
                    )
                    .order_by(StudentGroup.name.asc())
                    .all()
                )
                if assigned_streams:
                    return assigned_streams

            return stream_children

    return [primary_group]


def resolve_slot_audience_labels(
    db: Session,
    slot: TimetableSlot,
    *,
    group_cache: Optional[Dict[int, StudentGroup]] = None,
    stream_children_cache: Optional[Dict[int, List[StudentGroup]]] = None,
) -> List[str]:
    return [
        group_display_label(group)
        for group in resolve_slot_audience_groups(
            db,
            slot,
            group_cache=group_cache,
            stream_children_cache=stream_children_cache,
        )
    ]
