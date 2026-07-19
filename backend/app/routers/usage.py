from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from ..auth import get_current_user, is_tenant_admin
from ..database import get_db
from ..models import Timetable, UsageEvent, User, UserRole
from ..schemas import UsageEventCreate, UsageEventResponse, UsageSummaryResponse, UsageSummaryMetric
from ..services.usage_service import UsageService, METRIC_KEYS, resolve_period_bounds


router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


OBSERVABILITY_EVENT_KEYS = [
    "timetable_generation_attempts",
    "timetable_generation_successes",
    "timetable_generation_failures",
    "timetable_generation_duration_ms",
    "timetable_generation_fallback_runs",
    "timetable_generation_timeout_runs",
    "api_requests_total",
    "api_response_time_ms",
    "api_server_errors_total",
    "api_client_errors_total",
    "api_sla_breaches_total",
]


class TimetableRunSnapshot(BaseModel):
    timetable_id: int
    timetable_name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    saved_slot_count: int = 0
    fallback_used: bool = False
    solver_status_by_level: dict[str, str] = {}
    error_message: Optional[str] = None


class TenantGenerationObservability(BaseModel):
    attempts: int
    successes: int
    failures: int
    success_rate_percent: float
    average_duration_ms: Optional[float] = None
    total_duration_ms: int
    fallback_runs: int
    timeout_runs: int
    generated_timetables: int
    draft_timetables: int
    last_completed_at: Optional[str] = None
    recent_runs: list[TimetableRunSnapshot]


class TenantApiObservability(BaseModel):
    requests: int
    avg_response_ms: Optional[float] = None
    server_errors: int
    client_errors: int
    total_errors: int
    error_rate_percent: float
    sla_target_ms: int
    sla_breaches: int
    sla_compliance_percent: float
    top_failure_endpoints: list[dict[str, object]]


class TenantObservabilityResponse(BaseModel):
    tenant_id: int
    period: str
    generation: TenantGenerationObservability
    api: TenantApiObservability


def resolve_tenant_id(payload: UsageEventCreate, current_user: User) -> int:
    if current_user.role == UserRole.SUPERADMIN:
        if payload.tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tenant_id is required for superadmin usage events",
            )
        return payload.tenant_id

    if current_user.university_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context is missing for this account",
        )

    if payload.tenant_id is not None and payload.tenant_id != current_user.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="tenant_id does not match authenticated tenant",
        )

    return current_user.university_id


@router.post("/events", response_model=UsageEventResponse, status_code=status.HTTP_201_CREATED)
def create_usage_event(
    payload: UsageEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsageEventResponse:
    tenant_id = resolve_tenant_id(payload, current_user)
    occurred_at = payload.occurred_at or datetime.utcnow()

    event = UsageEvent(
        tenant_id=tenant_id,
        metric_key=payload.metric_key.value,
        quantity=payload.quantity,
        occurred_at=occurred_at,
        source=payload.source,
        metadata_json=payload.metadata,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return UsageEventResponse(
        id=event.id,
        tenant_id=event.tenant_id,
        metric_key=payload.metric_key,
        quantity=event.quantity,
        occurred_at=event.occurred_at,
        source=event.source,
        metadata=event.metadata_json,
    )


@router.get("/summary", response_model=UsageSummaryResponse)
def get_usage_summary(
    period: str = None,
    tenant_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsageSummaryResponse:
    if current_user.role == UserRole.SUPERADMIN:
        if tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tenant_id is required for superadmin usage summary",
            )
        resolved_tenant_id = tenant_id
    else:
        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant context is missing for this account",
            )
        if tenant_id is not None and tenant_id != current_user.university_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="tenant_id does not match authenticated tenant",
            )
        resolved_tenant_id = current_user.university_id

    from ..models import Department, Course, Timetable, Lecturer

    usage_service = UsageService(db)
    
    # --- Live Metric Calculations ---
    live_totals = {}
    
    # seats_active = Administrative Users + Lecturers
    user_count = db.query(User).filter(
        User.university_id == resolved_tenant_id,
        User.is_active == True,
        User.role != UserRole.SUPERADMIN
    ).count()
    
    lecturer_count = db.query(Lecturer).join(Department).filter(
        Department.university_id == resolved_tenant_id
    ).count()
    
    live_totals["seats_active"] = user_count + lecturer_count
    
    # department_count
    live_totals["department_count"] = db.query(Department).filter(
        Department.university_id == resolved_tenant_id
    ).count()
    
    # course_count
    live_totals["course_count"] = db.query(Course).join(Department).filter(
        Department.university_id == resolved_tenant_id
    ).count()
    
    # timetable_generations
    live_totals["timetable_generations"] = db.query(Timetable).filter(
        Timetable.university_id == resolved_tenant_id
    ).count()
    
    live_totals["storage_bytes"] = 0

    metrics: list[UsageSummaryMetric] = []
    for key in METRIC_KEYS:
        # Use live calculated total for accuracy over event-sourced summary
        actual_total = live_totals.get(key, 0)
        
        status_info = usage_service.get_quota_status(resolved_tenant_id, key, period)
        if status_info:
            # Overwrite the event-based total with our live database count
            status_info["total"] = actual_total
            if status_info["limit"] > 0:
                percent = round((actual_total / status_info["limit"]) * 100, 2)
                status_info["percent"] = percent
                status_val = "ok"
                if percent >= 100:
                    status_val = "exceeded"
                elif percent >= 80:
                    status_val = "warning"
                status_info["status"] = status_val
            else:
                status_info["percent"] = 0
                status_info["status"] = "ok"

            metrics.append(
                UsageSummaryMetric(
                    metric_key=key,
                    total=status_info["total"],
                    limit=status_info["limit"],
                    percent=status_info["percent"],
                    status=status_info["status"],
                )
            )
        else:
            metrics.append(
                UsageSummaryMetric(
                    metric_key=key,
                    total=actual_total,
                    limit=None,
                    percent=None,
                    status="unknown",
                )
            )

    period_label = period or datetime.utcnow().strftime("%Y-%m")
    return UsageSummaryResponse(
        tenant_id=resolved_tenant_id,
        period=period_label,
        metrics=metrics,
    )


@router.get("/observability", response_model=TenantObservabilityResponse)
def get_tenant_observability(
    period: str = None,
    tenant_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantObservabilityResponse:
    if current_user.role == UserRole.SUPERADMIN:
        if tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tenant_id is required for superadmin observability summary",
            )
        resolved_tenant_id = tenant_id
    else:
        # Usage events are tenant-level and carry no school identifier.  They
        # therefore cannot be safely segmented for a school coordinator.
        if not is_tenant_admin(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System health analytics are available to tenant administrators only.",
            )
        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant context is missing for this account",
            )
        if tenant_id is not None and tenant_id != current_user.university_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="tenant_id does not match authenticated tenant",
            )
        resolved_tenant_id = current_user.university_id

    period_start, period_end = resolve_period_bounds(period)
    period_label = period or datetime.utcnow().strftime("%Y-%m")

    totals = {
        metric_key: int(total or 0)
        for metric_key, total in (
            db.query(
                UsageEvent.metric_key,
                func.coalesce(func.sum(UsageEvent.quantity), 0),
            )
            .filter(UsageEvent.tenant_id == resolved_tenant_id)
            .filter(UsageEvent.metric_key.in_(OBSERVABILITY_EVENT_KEYS))
            .filter(UsageEvent.occurred_at >= period_start)
            .filter(UsageEvent.occurred_at <= period_end)
            .group_by(UsageEvent.metric_key)
            .all()
        )
    }

    api_requests = totals.get("api_requests_total", 0)
    api_response_total_ms = totals.get("api_response_time_ms", 0)
    api_server_errors = totals.get("api_server_errors_total", 0)
    api_client_errors = totals.get("api_client_errors_total", 0)
    api_total_errors = api_server_errors + api_client_errors
    api_sla_breaches = totals.get("api_sla_breaches_total", 0)

    attempts = totals.get("timetable_generation_attempts", 0)
    successes = totals.get("timetable_generation_successes", 0)
    failures = totals.get("timetable_generation_failures", 0)
    total_duration_ms = totals.get("timetable_generation_duration_ms", 0)
    fallback_runs = totals.get("timetable_generation_fallback_runs", 0)
    timeout_runs = totals.get("timetable_generation_timeout_runs", 0)
    avg_duration_ms = round(total_duration_ms / attempts, 2) if attempts else None
    success_rate = round((successes / attempts) * 100, 2) if attempts else 0.0

    tenant_timetables = (
        db.query(Timetable)
        .filter(Timetable.university_id == resolved_tenant_id)
        .all()
    )

    recent_runs: list[TimetableRunSnapshot] = []
    generated_timetables = 0
    draft_timetables = 0
    latest_completed_at: Optional[str] = None
    failure_endpoint_map: dict[str, dict[str, object]] = {}

    api_error_events = (
        db.query(UsageEvent)
        .filter(UsageEvent.tenant_id == resolved_tenant_id)
        .filter(UsageEvent.metric_key.in_(["api_server_errors_total", "api_client_errors_total"]))
        .filter(UsageEvent.occurred_at >= period_start)
        .filter(UsageEvent.occurred_at <= period_end)
        .all()
    )

    for event in api_error_events:
        metadata = event.metadata_json or {}
        endpoint = str(metadata.get("endpoint_route") or "unknown")
        status_codes = failure_endpoint_map.setdefault(endpoint, {"count": 0, "status_codes": set()})
        status_codes["count"] = int(status_codes["count"]) + int(event.quantity or 0)
        if metadata.get("status_code") is not None:
            casted_codes = status_codes["status_codes"]
            if isinstance(casted_codes, set):
                casted_codes.add(int(metadata["status_code"]))

    for timetable in tenant_timetables:
        meta = dict(timetable.generation_metadata or {})
        if meta.get("generated"):
            generated_timetables += 1
        else:
            draft_timetables += 1

        completed_at = meta.get("last_generation_completed_at")
        if completed_at and (latest_completed_at is None or completed_at > latest_completed_at):
            latest_completed_at = completed_at

        status = meta.get("generation_status")
        if not status:
            continue

        recent_runs.append(
            TimetableRunSnapshot(
                timetable_id=timetable.id,
                timetable_name=timetable.name,
                status=status,
                started_at=meta.get("last_generation_started_at"),
                completed_at=completed_at,
                duration_ms=meta.get("last_generation_duration_ms"),
                saved_slot_count=int(meta.get("last_generation_saved_slot_count") or 0),
                fallback_used=bool(meta.get("last_generation_fallback_used")),
                solver_status_by_level=meta.get("last_generation_solver_status_by_level") or {},
                error_message=meta.get("last_generation_error_message"),
            )
        )

    recent_runs.sort(
        key=lambda run: run.completed_at or run.started_at or "",
        reverse=True,
    )

    avg_response_ms = round(api_response_total_ms / api_requests, 2) if api_requests else None
    error_rate_percent = round((api_total_errors / api_requests) * 100, 2) if api_requests else 0.0
    sla_compliance_percent = round(((api_requests - api_sla_breaches) / api_requests) * 100, 2) if api_requests else 100.0

    plan_tier = "free"
    if current_user.role == UserRole.SUPERADMIN or current_user.university_id is not None:
        from ..models import University

        university = db.query(University).filter(University.id == resolved_tenant_id).first()
        if university and university.plan_tier:
            plan_tier = university.plan_tier

    sla_target_ms = {
        "free": 2500,
        "starter": 2500,
        "pro": 1800,
        "professional": 1800,
        "enterprise": 1200,
    }.get((plan_tier or "free").lower(), 2500)

    top_failure_endpoints = [
        {
            "endpoint": endpoint,
            "count": int(payload["count"]),
            "status_codes": sorted(payload["status_codes"]) if isinstance(payload["status_codes"], set) else [],
        }
        for endpoint, payload in sorted(
            failure_endpoint_map.items(),
            key=lambda item: int(item[1]["count"]),
            reverse=True,
        )[:5]
    ]

    return TenantObservabilityResponse(
        tenant_id=resolved_tenant_id,
        period=period_label,
        generation=TenantGenerationObservability(
            attempts=attempts,
            successes=successes,
            failures=failures,
            success_rate_percent=success_rate,
            average_duration_ms=avg_duration_ms,
            total_duration_ms=total_duration_ms,
            fallback_runs=fallback_runs,
            timeout_runs=timeout_runs,
            generated_timetables=generated_timetables,
            draft_timetables=draft_timetables,
            last_completed_at=latest_completed_at,
            recent_runs=recent_runs[:5],
        ),
        api=TenantApiObservability(
            requests=api_requests,
            avg_response_ms=avg_response_ms,
            server_errors=api_server_errors,
            client_errors=api_client_errors,
            total_errors=api_total_errors,
            error_rate_percent=error_rate_percent,
            sla_target_ms=sla_target_ms,
            sla_breaches=api_sla_breaches,
            sla_compliance_percent=sla_compliance_percent,
            top_failure_endpoints=top_failure_endpoints,
        ),
    )
