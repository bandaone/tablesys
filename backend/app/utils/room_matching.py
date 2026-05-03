from __future__ import annotations

from typing import Optional

from ..models import RoomType

SMALL_GROUP_THRESHOLD = 60


def _normalized_room_type(room_type: Optional[str]) -> str:
    return str(room_type or "").strip().lower()


def _room_family(room_type: Optional[str]) -> str:
    room = _normalized_room_type(room_type)

    if "lab" in room:
        return "lab"
    if "drawing" in room:
        return "drawing"
    if "survey" in room:
        return "surveying"
    if "conference" in room:
        return "conference"
    if "seminar" in room:
        return "seminar"
    if "tutorial" in room:
        return "tutorial"
    if "auditorium" in room:
        return "auditorium"
    if "lecture" in room:
        return "lecture"
    if "class" in room:
        return "classroom"
    return "other"


def _preferred_room_key(preferred_room_type: Optional[RoomType | str], session_type: Optional[str]) -> str:
    raw_pref = getattr(preferred_room_type, "value", preferred_room_type)
    pref = str(raw_pref or RoomType.ANY.value).strip().lower()
    session = str(session_type or "").strip().lower()

    if pref != RoomType.ANY.value:
        return pref

    if session == "lecture":
        return RoomType.LECTURE_HALL.value
    if session == "tutorial":
        return RoomType.TUTORIAL_ROOM.value
    if session == "seminar":
        return RoomType.SEMINAR_ROOM.value
    if session == "practical":
        return RoomType.LAB.value
    return RoomType.ANY.value


def room_match_rank(
    preferred_room_type: Optional[RoomType | str],
    session_type: Optional[str],
    room_type: Optional[str],
    *,
    group_size: Optional[int] = None,
) -> Optional[int]:
    """
    Return a soft compatibility rank.

    Lower is better:
    - 0 ideal match
    - 1 strong compromise
    - 2 acceptable fallback
    - 3 weak fallback
    - None incompatible
    """
    room_family = _room_family(room_type)
    target = _preferred_room_key(preferred_room_type, session_type)
    size = group_size or 0
    small_group = size <= SMALL_GROUP_THRESHOLD if size else False

    if target == RoomType.LECTURE_HALL.value:
        if room_family in {"lecture", "auditorium", "classroom"}:
            return 0
        if room_family in {"seminar", "tutorial", "conference"} and small_group:
            return 1
        if room_family in {"seminar", "tutorial", "conference"}:
            return 2
        return None

    if target == RoomType.TUTORIAL_ROOM.value:
        if room_family == "tutorial":
            return 0
        if room_family in {"seminar", "classroom"}:
            return 1
        if room_family in {"conference", "lecture", "auditorium"}:
            return 2
        return None

    if target == RoomType.SEMINAR_ROOM.value:
        if room_family in {"seminar", "conference"}:
            return 0
        if room_family in {"tutorial", "classroom"}:
            return 1
        if room_family in {"lecture", "auditorium"}:
            return 2
        return None

    if target == RoomType.LAB.value:
        if room_family in {"lab", "drawing", "surveying"}:
            return 0
        if room_family in {"tutorial", "seminar", "classroom"}:
            return 2
        if room_family in {"lecture", "auditorium", "conference"}:
            return 3
        return None

    if target == RoomType.DRAWING_ROOM.value:
        if room_family == "drawing":
            return 0
        if room_family in {"lab", "surveying"}:
            return 1
        if room_family in {"tutorial", "seminar", "classroom"}:
            return 2
        return None

    if target == RoomType.SURVEYING_ROOM.value:
        if room_family == "surveying":
            return 0
        if room_family in {"drawing", "lab"}:
            return 1
        if room_family in {"tutorial", "seminar", "classroom"}:
            return 2
        return None

    if target == RoomType.AUDITORIUM.value:
        if room_family == "auditorium":
            return 0
        if room_family == "lecture":
            return 1
        if room_family == "classroom":
            return 2
        return None

    if target == RoomType.ANY.value:
        if str(session_type or "").strip().lower() == "lecture":
            if room_family in {"lecture", "auditorium", "classroom"}:
                return 0
            if room_family in {"seminar", "tutorial", "conference"} and small_group:
                return 1
            if room_family in {"seminar", "tutorial", "conference"}:
                return 2
            return None
        if room_family in {"tutorial", "seminar", "classroom", "conference", "lecture", "auditorium"}:
            return 1
        return None

    return None


def room_type_matches(
    preferred_room_type: Optional[RoomType | str],
    session_type: Optional[str],
    room_type: Optional[str],
    *,
    group_size: Optional[int] = None,
) -> bool:
    return room_match_rank(
        preferred_room_type,
        session_type,
        room_type,
        group_size=group_size,
    ) is not None
