"""
Stats Router — Read-Only Analytics Summary Endpoint
====================================================
Agent Delta | PARALLEL_WORKPLAN.md — read-only scope only.

Provides lightweight aggregated counts consumed by:
  - DashboardPage.tsx  →  /api/v1/stats/summary
  - TimetableAnalytics.tsx  (indirectly via DashboardPage)

STRICT BOUNDARY: All methods here are GET (read) only.
No writes, no model changes, no migrations.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Any, Dict

from ..database import get_db
from ..auth import get_current_user
from ..models import User, Course, Department, StudentGroup, Lecturer, Room
from ..utils.school_scope import (
    filter_course_query_for_user,
    filter_department_query_for_user,
    filter_group_query_for_user,
    filter_lecturer_query_for_user,
    filter_room_query_for_user,
)


router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


def _scoped_counts(current_user: User, db: Session) -> Dict[str, int]:
    """Return counts using the same tenant/school filters as each resource API."""
    courses = filter_course_query_for_user(
        db.query(Course), current_user,
    ).with_entities(func.count(Course.id)).scalar() or 0
    departments = filter_department_query_for_user(
        db.query(Department), current_user,
    ).with_entities(func.count(Department.id)).scalar() or 0
    groups = filter_group_query_for_user(
        db.query(StudentGroup), current_user,
    ).with_entities(func.count(StudentGroup.id)).scalar() or 0
    lecturers = filter_lecturer_query_for_user(
        db.query(Lecturer), current_user,
    ).with_entities(func.count(Lecturer.id)).scalar() or 0
    rooms = filter_room_query_for_user(
        db.query(Room), current_user,
    ).with_entities(func.count(Room.id)).scalar() or 0

    return {
        "courses":     courses,
        "departments": departments,
        "groups":      groups,
        "lecturers":   lecturers,
        "rooms":       rooms,
    }


# ---------------------------------------------------------------------------
# /stats/summary
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=Dict[str, Any])
async def get_stats_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return aggregated entity counts scoped to the authenticated user's university.

    Response schema (matches SystemStats interface in DashboardPage.tsx):
    {
        "courses":     <int>,
        "departments": <int>,
        "groups":      <int>,
        "lecturers":   <int>,
        "rooms":       <int>
    }
    """
    return _scoped_counts(current_user, db)


# ---------------------------------------------------------------------------
# /stats/readiness  — convenience alias consumed by the setup-readiness strip
# ---------------------------------------------------------------------------

@router.get("/readiness", response_model=Dict[str, Any])
async def get_readiness_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns the same counts plus a boolean `ready` flag that the UI uses
    to render the coordinator setup-readiness progress strip.

    Thresholds mirror what DashboardPage EmptyTimetableLanding expects:
        courses     >= 10
        departments >=  3
        groups      >=  3
        lecturers   >=  5
        rooms       >=  3
    """
    counts = _scoped_counts(current_user, db)

    thresholds = {
        "courses":     10,
        "departments":  3,
        "groups":       3,
        "lecturers":    5,
        "rooms":        3,
    }

    readiness = {
        key: {
            "count":    counts[key],
            "required": thresholds[key],
            "ready":    counts[key] >= thresholds[key],
        }
        for key in counts
    }

    all_ready = all(v["ready"] for v in readiness.values())

    return {
        **counts,          # flat counts (backward-compatible with /summary)
        "readiness": readiness,
        "all_ready": all_ready,
    }
