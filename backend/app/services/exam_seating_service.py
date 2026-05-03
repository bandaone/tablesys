from __future__ import annotations

from typing import Optional

from ..models import ExamSeatingProfile, Room


class ExamSeatingService:
    """Calculates effective exam capacity after seating rules are applied."""

    @staticmethod
    def effective_capacity(room: Room, profile: Optional[ExamSeatingProfile]) -> int:
        raw_capacity = int(getattr(room, "capacity", 0) or 0)
        if raw_capacity <= 0:
            return 0

        if not profile:
            return raw_capacity

        fixed_capacity = getattr(profile, "fixed_capacity", None)
        if fixed_capacity is not None:
            return max(0, min(raw_capacity, int(fixed_capacity)))

        factor = int(getattr(profile, "capacity_factor", 100) or 100)
        factor = max(1, min(factor, 100))
        return max(1, int(raw_capacity * factor / 100))

    @staticmethod
    def room_supports_profile(room: Room, profile: Optional[ExamSeatingProfile]) -> bool:
        if not profile:
            return True
        if getattr(profile, "requires_computers", False):
            return str(getattr(room, "room_type", "")).lower() == "lab"
        return True
