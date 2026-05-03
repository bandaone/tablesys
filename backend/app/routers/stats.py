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
from typing import Any, Dict

from ..database import get_db
from ..auth import get_current_user
from ..models import User, Course, Department, StudentGroup, Lecturer, Room

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


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

    Tenant scoping is enforced by the TenantMiddleware at the SQLAlchemy
    session level — no additional filtering needed here.
    """
    courses     = db.query(Course).count()
    departments = db.query(Department).count()
    groups      = db.query(StudentGroup).count()
    lecturers   = db.query(Lecturer).count()
    rooms       = db.query(Room).count()

    return {
        "courses":     courses,
        "departments": departments,
        "groups":      groups,
        "lecturers":   lecturers,
        "rooms":       rooms,
    }


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
        courses     ≥ 10
        departments ≥  3
        groups      ≥  3
        lecturers   ≥  5
        rooms       ≥  3
    """
    counts = {
        "courses":     db.query(Course).count(),
        "departments": db.query(Department).count(),
        "groups":      db.query(StudentGroup).count(),
        "lecturers":   db.query(Lecturer).count(),
        "rooms":       db.query(Room).count(),
    }

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
