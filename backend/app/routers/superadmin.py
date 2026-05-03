"""
Super Admin Router
Platform-level endpoints for managing universities (tenants).
ALL routes require the SUPERADMIN role — school coordinators cannot access these.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import os
import shutil
import time
import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import University, User, UserRole, AuditLog
from ..auth import get_current_superadmin, get_password_hash, create_access_token, oauth2_scheme
from ..config import settings
from ..utils.audit_logger import AuditLogger
from jose import JWTError, jwt
from ..schemas import Token


PROCESS_START_TS = time.time()

router = APIRouter(prefix="/api/v1/superadmin", tags=["superadmin"])

# 0 means unlimited tenant capacity.
UNLIMITED_MAX_USERS = 0


# ── Schemas ──────────────────────────────────────────────────────────────────

class UniversityCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    short_name: Optional[str] = Field(None, max_length=20)
    domain: str = Field(..., min_length=3, max_length=100)
    timezone: str = Field(default="Africa/Harare")
    plan_tier: str = Field(default="free")  # free | pro | enterprise
    max_users: int = Field(default=UNLIMITED_MAX_USERS, ge=0)  # 0 = unlimited
    primary_color: str = Field(default="#1976d2")
    secondary_color: str = Field(default="#9c27b0")
    tagline: Optional[str] = None
    # Initial coordinator account
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

    class Config:
        from_attributes = True

class UniversityPaginatedResponse(BaseModel):
    items: List[UniversityResponse]
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


def _select_impersonation_target(db: Session, university_id: int) -> Optional[User]:
    """Select the best active tenant user to impersonate for support operations."""
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
            user_count=user_counts.get(uni.id, 0),
        )
        result.append(resp)
        
    return UniversityPaginatedResponse(items=result, total=total_count)


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
        raise HTTPException(status_code=400, detail="A university with this domain is already registered.")
    if db.query(University).filter(University.name == request.name).first():
        raise HTTPException(status_code=400, detail="A university with this name is already registered.")

    # Email/username uniqueness
    if db.query(User).filter(User.email == request.coordinator_email).first():
        raise HTTPException(status_code=400, detail="Email is already registered on the platform.")
    if db.query(User).filter(User.username == request.coordinator_username).first():
        raise HTTPException(status_code=400, detail="Username is already taken on the platform.")

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
    )
    db.add(uni)
    db.commit()
    db.refresh(uni)

    # Create coordinator account
    coordinator = User(
        university_id=uni.id,
        username=request.coordinator_username,
        email=request.coordinator_email,
        hashed_password=get_password_hash(request.coordinator_password),
        full_name=request.coordinator_full_name,
        role=UserRole.COORDINATOR,
        is_active=True,
    )
    db.add(coordinator)
    db.commit()

    return UniversityResponse(
        id=uni.id, name=uni.name, short_name=uni.short_name, domain=uni.domain,
        timezone=uni.timezone, is_active=uni.is_active, registered_at=uni.registered_at,
        plan_tier=uni.plan_tier, max_users=uni.max_users, primary_color=uni.primary_color,
        secondary_color=uni.secondary_color, tagline=uni.tagline, logo_url=uni.logo_url,
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
