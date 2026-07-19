from __future__ import annotations

import re
from typing import Any, Optional


COURSE_PROFILE_STATUS_COMPLETE = "profile_complete"
COURSE_PROFILE_STATUS_SEEDED = "profile_seeded"


def normalize_course_level(value: Any) -> int:
    """Normalize year-style values to the stored hundred-level format."""
    if value is None:
        raise ValueError("Course level is required")

    if isinstance(value, str):
        match = re.search(r"(\d+)", value)
        if match:
            value = int(match.group(1))

    try:
        level = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Course level must be numeric") from exc

    if 1 <= level <= 7:
        return level * 100
    if level in {100, 200, 300, 400, 500, 600, 700}:
        return level
    raise ValueError("Level must be a year (1-7) or hundred level (100-700)")


def has_complete_course_profile(
    credits: Optional[int],
    lecture_hours: Optional[int],
    tutorial_hours: Optional[int],
    practical_hours: Optional[int],
) -> bool:
    return all(value is not None for value in (credits, lecture_hours, tutorial_hours, practical_hours))


def derive_course_profile_status(
    credits: Optional[int],
    lecture_hours: Optional[int],
    tutorial_hours: Optional[int],
    practical_hours: Optional[int],
) -> str:
    if has_complete_course_profile(credits, lecture_hours, tutorial_hours, practical_hours):
        return COURSE_PROFILE_STATUS_COMPLETE
    return COURSE_PROFILE_STATUS_SEEDED

