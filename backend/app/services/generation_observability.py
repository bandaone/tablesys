from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import Timetable
from .usage import emit_event


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_utc(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def mark_generation_started(
    timetable: Timetable,
    *,
    mode: str,
    started_at: Optional[datetime] = None,
    components: Optional[list[str]] = None,
    job_id: Optional[str] = None,
) -> datetime:
    started_at = started_at or utc_now()
    meta = dict(timetable.generation_metadata or {})
    meta.update(
        {
            "generation_status": "running",
            "last_generation_mode": mode,
            "last_generation_started_at": isoformat_utc(started_at),
            "last_generation_components": components or [],
            "last_generation_job_id": job_id,
        }
    )
    timetable.generation_metadata = meta
    return started_at


def finalize_generation_run(
    db: Session,
    timetable: Timetable,
    *,
    tenant_id: int,
    success: bool,
    started_at: datetime,
    mode: str,
    components: Optional[list[str]] = None,
    job_id: Optional[str] = None,
    saved_slot_count: int = 0,
    error_message: Optional[str] = None,
    solver_status_by_level: Optional[dict[str, str]] = None,
    fallback_levels: Optional[list[Any]] = None,
    diagnostics: Optional[list[dict[str, Any]]] = None,
    status_override: Optional[str] = None,
) -> dict[str, Any]:
    completed_at = utc_now()
    duration_ms = max(1, int((completed_at - started_at).total_seconds() * 1000))
    statuses = solver_status_by_level or {}
    fallback_levels = fallback_levels or []
    diagnostics = diagnostics or []
    timeout_like = any(
        "UNKNOWN" in str(status).upper() or "TIMEOUT" in str(status).upper()
        for status in statuses.values()
    )

    final_status = status_override if status_override else ("success" if success else "failure")
    run_summary = {
        "timetable_id": timetable.id,
        "timetable_name": timetable.name,
        "status": final_status,
        "mode": mode,
        "job_id": job_id,
        "components": components or [],
        "started_at": isoformat_utc(started_at),
        "completed_at": isoformat_utc(completed_at),
        "duration_ms": duration_ms,
        "saved_slot_count": saved_slot_count,
        "fallback_used": bool(fallback_levels),
        "fallback_levels": fallback_levels,
        "solver_status_by_level": statuses,
        "error_message": error_message,
    }

    meta = dict(timetable.generation_metadata or {})
    history = list(meta.get("generation_run_history") or [])
    history.insert(0, run_summary)
    meta.update(
        {
            "generation_status": final_status,
            "last_generation_mode": mode,
            "last_generation_started_at": isoformat_utc(started_at),
            "last_generation_completed_at": isoformat_utc(completed_at),
            "last_generation_duration_ms": duration_ms,
            "last_generation_success": success,
            "last_generation_error_message": error_message,
            "last_generation_components": components or [],
            "last_generation_job_id": job_id,
            "last_generation_saved_slot_count": saved_slot_count,
            "last_generation_fallback_used": bool(fallback_levels),
            "last_generation_fallback_levels": fallback_levels,
            "last_generation_solver_status_by_level": statuses,
            "last_generation_diagnostics": diagnostics,
            "generation_run_history": history[:10],
        }
    )
    timetable.generation_metadata = meta

    emit_event(
        db,
        tenant_id=tenant_id,
        metric_key="timetable_generation_attempts",
        quantity=1,
        source="job" if mode == "async" else "api",
        metadata={"timetable_id": timetable.id, "mode": mode, "job_id": job_id},
    )
    emit_event(
        db,
        tenant_id=tenant_id,
        metric_key="timetable_generation_successes" if success else "timetable_generation_failures",
        quantity=1,
        source="job" if mode == "async" else "api",
        metadata={
            "timetable_id": timetable.id,
            "mode": mode,
            "job_id": job_id,
            "duration_ms": duration_ms,
            "saved_slot_count": saved_slot_count,
        },
    )
    emit_event(
        db,
        tenant_id=tenant_id,
        metric_key="timetable_generation_duration_ms",
        quantity=duration_ms,
        source="job" if mode == "async" else "api",
        metadata={
            "timetable_id": timetable.id,
            "mode": mode,
            "job_id": job_id,
            "success": success,
        },
    )

    if fallback_levels:
        emit_event(
            db,
            tenant_id=tenant_id,
            metric_key="timetable_generation_fallback_runs",
            quantity=1,
            source="job" if mode == "async" else "api",
            metadata={
                "timetable_id": timetable.id,
                "mode": mode,
                "job_id": job_id,
                "fallback_levels": fallback_levels,
            },
        )

    if timeout_like:
        emit_event(
            db,
            tenant_id=tenant_id,
            metric_key="timetable_generation_timeout_runs",
            quantity=1,
            source="job" if mode == "async" else "api",
            metadata={
                "timetable_id": timetable.id,
                "mode": mode,
                "job_id": job_id,
                "solver_status_by_level": statuses,
            },
        )

    return run_summary
