"""Shared, physical-transition rules for scheduled events.

An event ending at the precise time another event starts is only practical when
the attendee remains in the same room.  These helpers deliberately keep room
availability separate: rooms may be used back-to-back, while people may not be
asked to move between venues without enough time to do so.
"""

from __future__ import annotations

from datetime import time
from typing import Optional


# This is intentionally conservative and works with the common 30/60 minute
# timetable grids.  Institutions can later expose it as a policy setting
# without changing any of the scheduling rules below.
DEFAULT_TRANSIT_MINUTES = 10


def minutes_between(start: time, end: time) -> int:
    """Return the number of minutes from ``start`` to ``end`` on one day."""
    return ((end.hour * 60 + end.minute) - (start.hour * 60 + start.minute))


def times_overlap(start_a: time, end_a: time, start_b: time, end_b: time) -> bool:
    """Return whether two intervals overlap (touching boundaries are allowed)."""
    return start_a < end_b and start_b < end_a


def insufficient_transit_time(
    start_a: time,
    end_a: time,
    room_a_id: Optional[int],
    start_b: time,
    end_b: time,
    room_b_id: Optional[int],
    minimum_minutes: int = DEFAULT_TRANSIT_MINUTES,
) -> bool:
    """Whether two non-overlapping events leave an attendee too little travel time.

    A shared, known room is the sole exception.  A missing room is treated as a
    different location so incomplete data cannot silently create an impossible
    timetable.
    """
    if times_overlap(start_a, end_a, start_b, end_b):
        return False
    if room_a_id is not None and room_a_id == room_b_id:
        return False

    if end_a <= start_b:
        return minutes_between(end_a, start_b) < minimum_minutes
    if end_b <= start_a:
        return minutes_between(end_b, start_a) < minimum_minutes
    return False

