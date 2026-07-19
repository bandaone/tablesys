"""
Super Admin Router
Platform-level endpoints for managing universities (tenants).
ALL routes require the SUPERADMIN role — school coordinators cannot access these.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import os
import shutil
import time
import redis as redis_lib
from jose import JWTError, jwt
from ..database import get_db
from ..models import University, User, UserRole, AuditLog, Timetable, Room, Lecturer, ExamPeriod, PendingRegistration
from ..auth import get_current_superadmin, get_password_hash, create_access_token, oauth2_scheme
from ..config import settings
from ..utils.audit_logger import AuditLogger
from ..services.tenant_performance_service import TenantPerformanceService
from ..services.superadmin_business_metrics_service import SuperAdminBusinessMetricsService
from ..services.superadmin_operational_metrics_service import SuperAdminOperationalMetricsService
from ..schemas import Token

# Initialize router first before using it in decorators
router = APIRouter(prefix="/api/v1/superadmin", tags=["superadmin"])


@router.post("/backfill/universal-scheduling", status_code=200)
def backfill_universal_scheduling(
    seed_activity_types: bool = False,
    current_user=Depends(get_current_superadmin),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to idempotently backfill scheduling defaults for pre-migration tenants."""
    from ..seeding_utils import backfill_universal_scheduling_defaults

    touched = backfill_universal_scheduling_defaults(db, template_key="custom", seed_activity_types=seed_activity_types)
    return {"touched_universities": touched}


PROCESS_START_TS = time.time()

# 0 means unlimited tenant capacity.
UNLIMITED_MAX_USERS = 0


# ── Schemas ──────────────────────────────────────────────────────────────────

class UniversityCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    short_name: Optional[str] = Field(None, max_length=20)
    domain: str = Field(..., min_length=3, max_length=100)
    timezone: str = Field(default="Africa/Lusaka")
    plan_tier: str = Field(default="free")  # free | pro | enterprise
    max_users: int = Field(default=UNLIMITED_MAX_USERS, ge=0)  # 0 = unlimited
    primary_color: str = Field(default="#1976d2")
    secondary_color: str = Field(default="#9c27b0")
    tagline: Optional[str] = None
    scheduling_policy: Optional[dict] = None
    # Initial tenant admin account
    coordinator_username: str = Field(..., min_length=3, max_length=50)
    coordinator_email: EmailStr
    coordinator_password: str = Field(..., min_length=8)
    coordinator_full_name: str = Field(..., min_length=2)


class UniversityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    short_name: Optional[str] = Field(None, max_length=20)
    domain: Optional[str] = Field(None, min_length=3, max_length=100)
    timezone: Optional[str] = None
    plan_tier: Optional[str] = None
    max_users: Optional[int] = Field(None, ge=0)
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None
    scheduling_policy: Optional[dict] = None


class UniversityResponse(BaseModel):
    id: int
    name: str
    short_name: Optional[str]
    domain: str
    timezone: str
    is_active: bool
    registered_at: Optional[datetime]
    plan_tier: str
    max_users: int
    primary_color: str
    secondary_color: str
    tagline: Optional[str]
    logo_url: Optional[str]
    user_count: int = 0
    scheduling_policy: Optional[dict] = None
    onboarding_completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UniversityPaginatedResponse(BaseModel):
    items: List[UniversityResponse]
    total: int


class PendingRegistrationResponse(BaseModel):
    id: int
    token: str
    org_name: str
    subdomain: str
    admin_email: str
    admin_username: str
    admin_full_name: str
    status: str
    created_at: datetime
    expires_at: datetime
    
    class Config:
        from_attributes = True

class PendingRegistrationPaginatedResponse(BaseModel):
    items: List[PendingRegistrationResponse]
    total: int

class SuperAdminStats(BaseModel):
    total_universities: int
    active_universities: int
    suspended_universities: int
    total_users_all: int


class SuperAdminTelemetry(BaseModel):
    redis_status: str
    active_solver_jobs: int
    total_universities: int
    active_users: int
    system_uptime_hours: float
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    db_connection_status: str


class OrgUserCount(BaseModel):
    name: str
    user_count: int
    max_users: int
    plan_tier: str

class PlanDistribution(BaseModel):
    tier: str
    count: int

class RecentEvent(BaseModel):
    action: str
    entity_type: str
    user_email: Optional[str] = None
    timestamp: str

class SuperAdminAnalytics(BaseModel):
    users_per_org: List[OrgUserCount]
    plan_distribution: List[PlanDistribution]
    recent_events: List[RecentEvent]


class FailureEndpointSummary(BaseModel):
    endpoint: str
    count: int
    status_codes: Optional[List[int]] = None


class RecentGenerationRunSummary(BaseModel):
    timetable_id: int
    timetable_name: str
    status: str
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    saved_slot_count: int = 0
    fallback_used: bool = False
    error_message: Optional[str] = None


class TenantPerformanceRow(BaseModel):
    tenant_id: int
    tenant_name: str
    domain: str
    plan_tier: str
    requests: int
    server_errors: int
    client_errors: int
    error_rate_percent: float
    avg_response_ms: float
    sla_target_ms: int
    sla_breaches: int
    sla_compliance_percent: float
    generation_attempts: int
    generation_success_rate_percent: Optional[float] = None
    generation_avg_duration_ms: Optional[float] = None
    generation_failures: int
    generation_fallback_runs: int
    generation_timeout_runs: int
    generated_timetables: int
    draft_timetables: int
    health_status: str
    top_failure_endpoints: List[FailureEndpointSummary]
    recent_generation_runs: List[RecentGenerationRunSummary]


class TenantPerformanceSummary(BaseModel):
    tenant_count: int
    active_tenants: int
    tenants_meeting_sla: int
    platform_avg_response_ms: float
    platform_error_rate_percent: float
    platform_generation_success_rate_percent: float
    at_risk_tenants: int


class SuperAdminPerformanceResponse(BaseModel):
    window_days: int
    generated_at: str
    summary: TenantPerformanceSummary
    top_failure_endpoints: List[FailureEndpointSummary]
    tenants: List[TenantPerformanceRow]


class FeatureAdoptionTopTenant(BaseModel):
    tenant_name: str
    events: int


class FeatureAdoptionRow(BaseModel):
    feature_key: str
    feature_name: str
    tenant_count: int
    adoption_percent: float
    usage_events: int
    top_tenants: List[FeatureAdoptionTopTenant]


class TenantFeatureMatrixRow(BaseModel):
    tenant_id: int
    tenant_name: str
    plan_tier: str
    feature_count: int
    features_used: List[str]
    top_feature: Optional[str] = None
    total_feature_events: int


class EngagementMetricsRow(BaseModel):
    tenant_id: int
    tenant_name: str
    plan_tier: str
    login_count: int
    active_days: int
    avg_logins_per_week: float
    avg_session_duration_minutes: Optional[float] = None
    api_requests: int
    avg_api_requests_per_active_day: float
    peak_hour_utc: Optional[int] = None


class PlanCorrelationRow(BaseModel):
    plan_tier: str
    tenant_count: int
    avg_features_adopted: float
    avg_api_requests: float
    avg_generation_runs: float
    avg_login_count: float
    avg_session_duration_minutes: Optional[float] = None
    most_adopted_feature: Optional[str] = None


class BusinessMetricsSummary(BaseModel):
    tenant_count: int
    active_tenants: int
    adopted_feature_count: int
    avg_features_per_tenant: float
    avg_logins_per_tenant: float
    avg_session_duration_minutes: Optional[float] = None
    login_data_available: bool


class SuperAdminBusinessMetricsResponse(BaseModel):
    window_days: int
    generated_at: str
    summary: BusinessMetricsSummary
    feature_adoption: List[FeatureAdoptionRow]
    tenant_feature_matrix: List[TenantFeatureMatrixRow]
    engagement: List[EngagementMetricsRow]
    plan_correlation: List[PlanCorrelationRow]


class SolverReliabilityRow(BaseModel):
    tenant_id: int
    tenant_name: str
    domain: str
    plan_tier: str
    attempts: int
    successes: int
    failures: int
    fallback_runs: int
    timeout_runs: int
    fallback_rate_percent: Optional[float] = None
    timeout_rate_percent: Optional[float] = None


class ConflictResolutionRow(BaseModel):
    tenant_id: int
    tenant_name: str
    plan_tier: str
    evaluated_runs: int
    conflict_free_runs: int
    unresolved_runs: int
    conflict_free_rate_percent: Optional[float] = None
    total_conflicts: int
    top_conflict_type: Optional[str] = None


class StorageGrowthPoint(BaseModel):
    label: str
    total_bytes_added: int
    top_tenant_name: Optional[str] = None
    top_tenant_bytes: int = 0


class TenantStorageRow(BaseModel):
    tenant_id: int
    tenant_name: str
    plan_tier: str
    current_estimated_storage_bytes: int
    storage_added_bytes_window: int
    storage_added_bytes_previous_window: int
    growth_percent: Optional[float] = None


class RateLimitEndpointRow(BaseModel):
    endpoint: str
    count: int


class RateLimitHitRow(BaseModel):
    tenant_id: int
    tenant_name: str
    plan_tier: str
    hit_count: int
    distinct_user_count: int
    last_hit_at: Optional[str] = None
    top_endpoints: List[RateLimitEndpointRow]


class OperationalMetricsSummary(BaseModel):
    tenant_count: int
    active_tenants: int
    total_solver_runs: int
    avg_fallback_rate_percent: Optional[float] = None
    avg_timeout_rate_percent: Optional[float] = None
    conflict_free_rate_percent: Optional[float] = None
    storage_growth_bytes_window: int
    current_estimated_storage_bytes: int
    rate_limit_hits: int


class SuperAdminOperationalMetricsResponse(BaseModel):
    window_days: int
    generated_at: str
    summary: OperationalMetricsSummary
    solver_reliability: List[SolverReliabilityRow]
    conflict_resolution: List[ConflictResolutionRow]
    storage_growth: List[StorageGrowthPoint]
    tenant_storage: List[TenantStorageRow]
    rate_limits: List[RateLimitHitRow]


class SupportUserSnapshot(BaseModel):
    id: int
    email: str
    username: str
    full_name: str
    role: str
    department_id: Optional[int] = None
    is_active: bool


class SuperAdminImpersonationResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: SupportUserSnapshot


def _safe_len_map_entries(payload: Optional[dict]) -> int:
    """Return count of task entries from Celery inspect payloads safely."""
    if not payload:
        return 0
    return sum(len(items or []) for items in payload.values())


class RoleCount(BaseModel):
    role: str
    count: int

class TimetableStats(BaseModel):
    generated_count: int
    draft_count: int

class ResourceUtilization(BaseModel):
    total_rooms: int
    total_lecturers: int
    total_capacity: int

class TenantActivityLog(BaseModel):
    action: str
    entity_type: str
    user_email: Optional[str] = None
    timestamp: str

class TenantDashboardMetricsResponse(BaseModel):
    user_counts: List[RoleCount]
    timetable_stats: TimetableStats
    resource_utilization: ResourceUtilization
    recent_activity_logs: List[TenantActivityLog]


def _select_impersonation_target(db: Session, university_id: int) -> Optional[User]:
    """Select the best active tenant user to impersonate for support operations."""
    target = db.query(User).filter(
        User.university_id == university_id,
        User.role == UserRole.TENANT_ADMIN,
        User.is_active == True,
    ).order_by(User.id.asc()).first()
    if target:
        return target

    target = db.query(User).filter(
        User.university_id == university_id,
        User.role == UserRole.SCHOOL_COORDINATOR,
        User.is_active == True,
    ).order_by(User.id.asc()).first()
    if target:
        return target

    target = db.query(User).filter(
        User.university_id == university_id,
        User.role == UserRole.COORDINATOR,
        User.is_active == True,
    ).order_by(User.id.asc()).first()
    if target:
        return target

    return db.query(User).filter(
        User.university_id == university_id,
        User.role == UserRole.HOD,
        User.is_active == True,
    ).order_by(User.id.asc()).first()


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=SuperAdminStats)
def get_platform_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Platform-wide statistics for the super admin dashboard."""
    total_unis = db.query(University).count()
    active_unis = db.query(University).filter(University.is_active == True).count()
    total_users = db.query(User).filter(User.role != UserRole.SUPERADMIN).count()

    return SuperAdminStats(
        total_universities=total_unis,
        active_universities=active_unis,
        suspended_universities=total_unis - active_unis,
        total_users_all=total_users,
    )

@router.get("/analytics", response_model=SuperAdminAnalytics)
def get_platform_analytics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Aggregate real platform usage analytics for the dashboard."""
    
    # 1. Users per Org (Active orgs)
    orgs = db.query(University).filter(University.is_active == True).all()
    uni_ids = [o.id for o in orgs]
    
    org_counts = []
    if uni_ids:
        # Group non-superadmin users by uni
        counts = db.query(
            User.university_id, func.count(User.id)
        ).filter(
            User.university_id.in_(uni_ids),
            User.role != UserRole.SUPERADMIN
        ).group_by(User.university_id).all()
        counts_dict = {u_id: count for u_id, count in counts}
        
        for org in orgs:
            org_counts.append(OrgUserCount(
                name=org.name,
                user_count=counts_dict.get(org.id, 0),
                max_users=org.max_users,
                plan_tier=org.plan_tier
            ))
            
    # Sort dynamically: largest user counts first, up to top 6
    org_counts = sorted(org_counts, key=lambda x: x.user_count, reverse=True)[:6]

    # 2. Plan Distribution across ALL orgs
    all_orgs = db.query(University.plan_tier, func.count(University.id)).group_by(University.plan_tier).all()
    plan_distribution = [PlanDistribution(tier=tier, count=count) for tier, count in all_orgs]

    # 3. Recent Events (Audit Logs)
    recent_audit_logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(6).all()
    recent_events = [
        RecentEvent(
            action=log.action,
            entity_type=log.entity_type,
            user_email=log.user_email,
            timestamp=log.timestamp.isoformat()
        )
        for log in recent_audit_logs
    ]

    return SuperAdminAnalytics(
        users_per_org=org_counts,
        plan_distribution=plan_distribution,
        recent_events=recent_events
    )

@router.get("/telemetry", response_model=SuperAdminTelemetry)
def get_platform_telemetry(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Live platform telemetry for super admin dashboards (real data only)."""
    import psutil
    
    total_universities = db.query(func.count(University.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(
        User.role != UserRole.SUPERADMIN,
        User.is_active == True,
    ).scalar() or 0

    redis_status = "offline"
    active_solver_jobs = 0

    try:
        redis_client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        redis_client.ping()
        redis_status = "online"

        # Query live Celery worker task state: running + queued/scheduled.
        from ..celery_app import celery_app

        inspector = celery_app.control.inspect(timeout=1.0)
        if inspector is not None:
            active_solver_jobs = (
                _safe_len_map_entries(inspector.active())
                + _safe_len_map_entries(inspector.reserved())
                + _safe_len_map_entries(inspector.scheduled())
            )
    except Exception:
        # Telemetry should degrade gracefully if Redis/Celery is unavailable.
        redis_status = "offline"
        active_solver_jobs = 0

    uptime_hours = round((time.time() - PROCESS_START_TS) / 3600, 2)
    
    # System Hardware Metrics
    cpu_usage = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # DB Status (we are actively querying so it must be online)
    db_status = "online"

    return SuperAdminTelemetry(
        redis_status=redis_status,
        active_solver_jobs=active_solver_jobs,
        total_universities=total_universities,
        active_users=active_users,
        system_uptime_hours=uptime_hours,
        cpu_usage_percent=cpu_usage,
        memory_usage_percent=memory.percent,
        disk_usage_percent=disk.percent,
        db_connection_status=db_status
    )


@router.get("/performance", response_model=SuperAdminPerformanceResponse)
def get_platform_performance(
    window_days: int = 30,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Tenant performance, SLA, and generation health overview for platform owners."""
    if window_days < 1:
        window_days = 1
    if window_days > 90:
        window_days = 90

    service = TenantPerformanceService(db)
    return service.get_platform_performance_overview(window_days=window_days)


@router.get("/business-metrics", response_model=SuperAdminBusinessMetricsResponse)
def get_business_metrics(
    window_days: int = 30,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Business usage analytics for platform owners across tenant feature adoption and engagement."""
    if window_days < 1:
        window_days = 1
    if window_days > 90:
        window_days = 90

    service = SuperAdminBusinessMetricsService(db)
    return service.get_business_metrics_overview(window_days=window_days)


@router.get("/operational-metrics", response_model=SuperAdminOperationalMetricsResponse)
def get_operational_metrics(
    window_days: int = 30,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Operational health analytics for platform owners across solver reliability, storage, and rate-limit pressure."""
    if window_days < 1:
        window_days = 1
    if window_days > 90:
        window_days = 90

    service = SuperAdminOperationalMetricsService(db)
    return service.get_operational_metrics_overview(window_days=window_days)


@router.get("/universities", response_model=UniversityPaginatedResponse)
def list_universities(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """List registered universities with user counts, using pagination."""
    query = db.query(University)
    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            (func.lower(University.name).like(search_term)) |
            (func.lower(University.domain).like(search_term))
        )
    
    total_count = query.count()
    universities = query.order_by(University.registered_at.desc()).offset(skip).limit(limit).all()

    # Optimized user counts batch fetch
    uni_ids = [u.id for u in universities]
    user_counts = {}
    if uni_ids:
        counts = db.query(
            User.university_id, func.count(User.id)
        ).filter(
            User.university_id.in_(uni_ids),
            User.role != UserRole.SUPERADMIN
        ).group_by(User.university_id).all()
        user_counts = {u_id: count for u_id, count in counts}

    result = []
    for uni in universities:
        resp = UniversityResponse(
            id=uni.id,
            name=uni.name,
            short_name=uni.short_name,
            domain=uni.domain,
            timezone=uni.timezone,
            is_active=uni.is_active,
            registered_at=uni.registered_at,
            plan_tier=uni.plan_tier,
            max_users=uni.max_users,
            primary_color=uni.primary_color,
            secondary_color=uni.secondary_color,
            tagline=uni.tagline,
            logo_url=uni.logo_url,
            scheduling_policy=uni.scheduling_policy,
            onboarding_completed_at=getattr(uni, "onboarding_completed_at", None),
            user_count=user_counts.get(uni.id, 0),
        )
        result.append(resp)
        
    return UniversityPaginatedResponse(items=result, total=total_count)


@router.get("/pending-registrations", response_model=PendingRegistrationPaginatedResponse)
def list_pending_registrations(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """List pending registrations for super admin review."""
    query = db.query(PendingRegistration)
    if status_filter:
        query = query.filter(PendingRegistration.status == status_filter)
    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            (func.lower(PendingRegistration.org_name).like(search_term)) |
            (func.lower(PendingRegistration.subdomain).like(search_term)) |
            (func.lower(PendingRegistration.admin_email).like(search_term))
        )
    
    total_count = query.count()
    registrations = query.order_by(PendingRegistration.created_at.desc()).offset(skip).limit(limit).all()

    return PendingRegistrationPaginatedResponse(items=registrations, total=total_count)


@router.post("/pending-registrations/{registration_id}/retry", response_model=Token)
def retry_failed_registration(
    registration_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Manually retry a registration that failed provisioning."""
    from ..services.provisioning import provision_tenant, ProvisioningError

    pending = db.query(PendingRegistration).filter(PendingRegistration.id == registration_id).first()
    if not pending:
        raise HTTPException(status_code=404, detail="Pending registration not found.")
    
    if pending.status != "failed_provisioning":
        raise HTTPException(status_code=400, detail="Only failed registrations can be retried.")

    try:
        result = provision_tenant(db, pending)
        return Token(access_token=result.access_token, token_type=result.token_type)
    except ProvisioningError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Provisioning retry failed again: {str(exc)}"
        )


@router.post("/universities", response_model=UniversityResponse, status_code=status.HTTP_201_CREATED)
def register_university(
    request: UniversityCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Register a new university and create its first coordinator account."""
    # Domain uniqueness check (lowercase)
    normalized_domain = request.domain.lower()
    if db.query(University).filter(func.lower(University.domain) == normalized_domain).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A university with this domain is already registered.")
    if db.query(University).filter(University.name == request.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A university with this name is already registered.")

    # Email/username uniqueness
    if db.query(User).filter(User.email == request.coordinator_email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered on the platform.")
    if db.query(User).filter(User.username == request.coordinator_username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already taken on the platform.")

    # Create university
    normalized_max_users = request.max_users if request.max_users and request.max_users > 0 else UNLIMITED_MAX_USERS

    uni = University(
        name=request.name,
        short_name=request.short_name,
        domain=normalized_domain,
        timezone=request.timezone,
        is_active=True,
        registered_at=datetime.now(timezone.utc),
        plan_tier=request.plan_tier,
        max_users=normalized_max_users,
        primary_color=request.primary_color,
        secondary_color=request.secondary_color,
        tagline=request.tagline,
        scheduling_policy=request.scheduling_policy,
    )
    db.add(uni)
    try:
        db.commit()
        db.refresh(uni)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Concurrency conflict: A university with these details was just registered.")

    # Create tenant admin account
    coordinator = User(
        university_id=uni.id,
        username=request.coordinator_username,
        email=request.coordinator_email,
        hashed_password=get_password_hash(request.coordinator_password),
        full_name=request.coordinator_full_name,
        role=UserRole.TENANT_ADMIN,
        is_active=True,
    )
    db.add(coordinator)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Concurrency conflict: A user with this email or username was just registered.")

    return UniversityResponse(
        id=uni.id, name=uni.name, short_name=uni.short_name, domain=uni.domain,
        timezone=uni.timezone, is_active=uni.is_active, registered_at=uni.registered_at,
        plan_tier=uni.plan_tier, max_users=uni.max_users, primary_color=uni.primary_color,
        secondary_color=uni.secondary_color, tagline=uni.tagline, logo_url=uni.logo_url,
        scheduling_policy=uni.scheduling_policy, onboarding_completed_at=getattr(uni, "onboarding_completed_at", None),
        user_count=1,
    )


@router.patch("/universities/{university_id}", response_model=UniversityResponse)
def update_university(
    university_id: int,
    updates: UniversityUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Update a university's details, branding, or status."""
    uni = db.query(University).filter(University.id == university_id).first()
    if not uni:
        raise HTTPException(status_code=404, detail="University not found.")

    update_payload = updates.model_dump(exclude_unset=True)
    if "max_users" in update_payload:
        value = update_payload["max_users"]
        update_payload["max_users"] = value if value and value > 0 else UNLIMITED_MAX_USERS

    for field, value in update_payload.items():
        setattr(uni, field, value)

    db.commit()
    db.refresh(uni)

    user_count = db.query(User).filter(
        User.university_id == uni.id,
        User.role != UserRole.SUPERADMIN
    ).count()

    return UniversityResponse(
        id=uni.id, name=uni.name, short_name=uni.short_name, domain=uni.domain,
        timezone=uni.timezone, is_active=uni.is_active, registered_at=uni.registered_at,
        plan_tier=uni.plan_tier, max_users=uni.max_users, primary_color=uni.primary_color,
        secondary_color=uni.secondary_color, tagline=uni.tagline, logo_url=uni.logo_url,
        scheduling_policy=uni.scheduling_policy, onboarding_completed_at=getattr(uni, "onboarding_completed_at", None),
        user_count=user_count,
    )


@router.delete("/universities/{university_id}", status_code=status.HTTP_204_NO_CONTENT)
def suspend_university(
    university_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Soft-delete (suspend) a university by setting is_active=False."""
    uni = db.query(University).filter(University.id == university_id).first()
    if not uni:
        raise HTTPException(status_code=404, detail="University not found.")
    uni.is_active = False
    db.commit()

@router.delete("/universities/{university_id}/wipe", status_code=status.HTTP_204_NO_CONTENT)
def hard_delete_university(
    university_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Hard delete (wipe) a university completely."""
    uni = db.query(University).filter(University.id == university_id).first()
    if not uni:
        raise HTTPException(status_code=404, detail="University not found.")
    
    # Ideally should clear dependent records via cascade or manually,
    # For now simply deletes the tenant record. Be cautious with foreign keys if NO ACTION is set.
    db.delete(uni)
    db.commit()


@router.post("/universities/{university_id}/suspend", status_code=status.HTTP_200_OK)
def suspend_university_post(
    university_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Toggle suspend/activate for a university (POST alias used by the frontend)."""
    uni = db.query(University).filter(University.id == university_id).first()
    if not uni:
        raise HTTPException(status_code=404, detail="University not found.")
    uni.is_active = not uni.is_active
    db.commit()
    return {"id": university_id, "is_active": uni.is_active}


@router.post("/universities/{university_id}/logo", response_model=UniversityResponse)
async def upload_university_logo(
    university_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Upload or update a university's logo."""
    uni = db.query(University).filter(University.id == university_id).first()
    if not uni:
        raise HTTPException(status_code=404, detail="University not found.")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    # Create directory for this university's logo
    logo_dir = os.path.join("media", "logos", str(university_id))
    os.makedirs(logo_dir, exist_ok=True)
    
    # Save file always as logo.png for consistency on the frontend
    file_path = os.path.join(logo_dir, "logo.png")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Update DB record to signal it has a logo
    uni.logo_url = f"/media/logos/{university_id}/logo.png"
    db.commit()
    db.refresh(uni)

    user_count = db.query(User).filter(
        User.university_id == uni.id,
        User.role != UserRole.SUPERADMIN
    ).count()

    return UniversityResponse(
        id=uni.id, name=uni.name, short_name=uni.short_name, domain=uni.domain,
        timezone=uni.timezone, is_active=uni.is_active, registered_at=uni.registered_at,
        plan_tier=uni.plan_tier, max_users=uni.max_users, primary_color=uni.primary_color,
        secondary_color=uni.secondary_color, tagline=uni.tagline, logo_url=uni.logo_url,
        scheduling_policy=uni.scheduling_policy, onboarding_completed_at=getattr(uni, "onboarding_completed_at", None),
        user_count=user_count,
    )


@router.post("/universities/{university_id}/impersonate", response_model=SuperAdminImpersonationResponse)
def impersonate_tenant_user(
    university_id: int,
    request: Request,
    db: Session = Depends(get_db),
    superadmin: User = Depends(get_current_superadmin),
):
    """Issue a short-lived tenant token for superadmin troubleshooting."""
    uni = db.query(University).filter(University.id == university_id).first()
    if not uni:
        raise HTTPException(status_code=404, detail="University not found.")
    if not uni.is_active:
        raise HTTPException(status_code=400, detail="University is suspended. Reactivate it before impersonation.")

    target_user = _select_impersonation_target(db, university_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="No active coordinator or HOD found for this university.")

    expiry_minutes = min(max(settings.ACCESS_TOKEN_EXPIRE_MINUTES, 5), 15)
    access_token = create_access_token(
        data={
            "sub": target_user.username,
            "impersonation": True,
            "impersonated_by": superadmin.username,
            "impersonated_by_id": superadmin.id,
            "impersonated_university_id": university_id,
        },
        expires_delta=timedelta(minutes=expiry_minutes),
    )

    AuditLogger.log_event(
        event_type="SUPERADMIN_IMPERSONATION_STARTED",
        request=request,
        user_id=superadmin.id,
        username=superadmin.username,
        resource=f"/api/v1/superadmin/universities/{university_id}/impersonate",
        action="POST",
        details={
            "target_user_id": target_user.id,
            "target_username": target_user.username,
            "target_role": target_user.role.value,
            "target_university_id": target_user.university_id,
            "token_ttl_minutes": expiry_minutes,
        },
        success=True,
    )

    return SuperAdminImpersonationResponse(
        access_token=access_token,
        user={
            "id": target_user.id,
            "email": target_user.email,
            "username": target_user.username,
            "full_name": target_user.full_name,
            "role": target_user.role.value,
            "department_id": target_user.department_id,
            "is_active": target_user.is_active,
        },
    )

@router.post("/revert-impersonation", response_model=Token)
def revert_impersonation(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Secure endpoint to swap an impersonation token back to the superadmin token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if not payload.get("impersonation"):
            raise HTTPException(status_code=400, detail="Token is not an impersonation token.")
        
        superadmin_username = payload.get("impersonated_by")
        superadmin = db.query(User).filter(User.username == superadmin_username).first()
        
        if not superadmin or superadmin.role != UserRole.SUPERADMIN or not superadmin.is_active:
            raise HTTPException(status_code=403, detail="Invalid or suspended superadmin impersonator.")
        
        # Issue new standard superadmin token
        access_token = create_access_token(
            data={"sub": superadmin.username},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return Token(access_token=access_token, token_type="bearer")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/universities/{university_id}/dashboard-metrics", response_model=TenantDashboardMetricsResponse)
def get_tenant_dashboard_metrics(
    university_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin)
):
    """Aggregate per-tenant dashboard metrics: users by role, timetable stats, resources, and recent logs."""
    uni = db.query(University).filter(University.id == university_id).first()
    if not uni:
        raise HTTPException(status_code=404, detail="University not found.")

    # 1. User counts by role
    role_counts_query = db.query(User.role, func.count(User.id)).filter(
        User.university_id == university_id,
        User.role != UserRole.SUPERADMIN
    ).group_by(User.role).all()
    user_counts = [RoleCount(role=role.value, count=count) for role, count in role_counts_query]

    # 2. Timetable stats
    # Lecture timetables
    lecture_active = db.query(Timetable).filter(Timetable.university_id == university_id, Timetable.is_active == True).count()
    lecture_draft = db.query(Timetable).filter(Timetable.university_id == university_id, Timetable.is_active == False).count()
    # Exam periods
    exam_active = db.query(ExamPeriod).filter(ExamPeriod.university_id == university_id, ExamPeriod.is_published == True).count()
    exam_draft = db.query(ExamPeriod).filter(ExamPeriod.university_id == university_id, ExamPeriod.is_published == False).count()
    
    timetable_stats = TimetableStats(
        generated_count=lecture_active + exam_active,
        draft_count=lecture_draft + exam_draft
    )

    # 3. Resource utilization
    total_rooms = db.query(Room).filter(Room.university_id == university_id).count()
    # Calculate sum of room capacities safely
    capacity_result = db.query(func.sum(Room.capacity)).filter(Room.university_id == university_id).scalar()
    total_capacity = int(capacity_result) if capacity_result else 0
    
    # Lecturers belong to a department, and a department belongs to a university.
    # We can join Lecturer -> Department to filter by university_id.
    from ..models import Department
    total_lecturers = db.query(Lecturer).join(Department).filter(Department.university_id == university_id).count()

    resource_utilization = ResourceUtilization(
        total_rooms=total_rooms,
        total_lecturers=total_lecturers,
        total_capacity=total_capacity
    )

    # 4. Recent activity logs
    # Join with User to capture logs by tenant users, or fallback to university-level entity logs
    logs = db.query(AuditLog).outerjoin(User, AuditLog.user_id == User.id).filter(
        (User.university_id == university_id) | 
        ((AuditLog.entity_type == "university") & (AuditLog.entity_id == university_id))
    ).order_by(AuditLog.timestamp.desc()).limit(10).all()

    recent_logs = [
        TenantActivityLog(
            action=log.action,
            entity_type=log.entity_type,
            user_email=log.user_email,
            timestamp=log.timestamp.isoformat()
        )
        for log in logs
    ]

    return TenantDashboardMetricsResponse(
        user_counts=user_counts,
        timetable_stats=timetable_stats,
        resource_utilization=resource_utilization,
        recent_activity_logs=recent_logs
    )
