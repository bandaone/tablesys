"""
TABLESYS - University Timetable Management System

Main application entry point with:
- Logging configuration (app, audit, error logs)
- Error handling middleware
- Security headers middleware
- CORS configuration
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import SessionLocal
from .models import *  # Import all models so SQLAlchemy knows about them
from .routers import auth, courses, lecturers, rooms, groups, departments, timetables, exam_timetables, export, import_timetable, users, print_views, notifications, search, dashboard, reports, student_portal, mobile_portal, mobile_public, audit, scheduler, lecturer_portal, usage, activity_types, institution_setup, schools
from .routers import superadmin, branding, public
from .routers import stats  # Agent Delta: read-only analytics stats router
from .routers.api import sis as sis_router  # Agent Gamma: SIS webhooks
from .routers import data_export, offboarding  # Antigravity: security & compliance
from .routers import alerts as alerts_router  # Platform alerting system
from .middleware import SecurityHeadersMiddleware, ErrorHandlerMiddleware, TenantMiddleware
from .utils import RequestContextFilter
from .config import settings
import os
import logging
import logging.handlers
from pathlib import Path
import sentry_sdk
from datetime import datetime, timezone

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from jose import JWTError, jwt
from .models import University, ViewerActivity
from .observability import api_request_duration_histogram, api_request_count_counter
from .middleware.rate_limiter import PublicRouteRateLimiter
from .services.usage import emit_event
from .utils.ip_utils import get_client_ip
import hashlib

# ── Public endpoint rate limiter (unauthenticated routes) ─────────────────────
# 60 requests / 60 seconds per IP. Sustained violators get a 2-minute block.
_public_rate_limiter = PublicRouteRateLimiter(
    max_requests=60,
    window_seconds=60,
    block_duration_seconds=120,
)

_PUBLIC_RATE_LIMITED_PREFIXES = (
    "/api/v1/mobile/public",
    "/api/v1/public",
)


class PublicRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Apply sliding-window rate limiting to all unauthenticated public routes.
    Authenticated routes are unaffected.
    """
    async def dispatch(self, request, call_next):
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _PUBLIC_RATE_LIMITED_PREFIXES):
            ip = get_client_ip(request)
            allowed, retry_after = _public_rate_limiter.is_allowed(ip)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down."},
                    headers={"Retry-After": str(retry_after)},
                )
        return await call_next(request)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    _IGNORED_PATH_PREFIXES = (
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
        "/media",
        "/api/v1/media",
    )

    def _decode_request_token(self, request):
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        elif request.query_params.get("token"):
            token = request.query_params.get("token")

        if not token:
            return None

        try:
            return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except (JWTError, ValueError, TypeError):
            return None

    def _resolve_tenant_context(self, request, token_payload=None):
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is not None:
            return tenant_id

        payload = token_payload or self._decode_request_token(request)
        if not payload:
            return None

        try:
            decoded_tenant_id = payload.get("university_id")
            if decoded_tenant_id is not None:
                request.state.tenant_id = int(decoded_tenant_id)
                return int(decoded_tenant_id)
        except (ValueError, TypeError):
            return None

        return None

    def _should_capture_request(self, path: str, tenant_id: int | None) -> bool:
        if tenant_id is None:
            return False
        if any(path.startswith(prefix) for prefix in self._IGNORED_PATH_PREFIXES):
            return False
        return path.startswith("/api/")

    def _resolve_viewer_context(self, request, token_payload=None):
        path = request.url.path
        query_params = request.query_params

        if path.startswith("/api/v1/mobile/public/"):
            raw_viewer_id = request.headers.get("X-Viewer-ID", "").strip()
            if not raw_viewer_id:
                fallback_seed = f"{get_client_ip(request)}|{request.headers.get('User-Agent', '')}"
                raw_viewer_id = hashlib.sha256(fallback_seed.encode("utf-8")).hexdigest()[:32]
            try:
                group_id = int(query_params.get("group_id")) if query_params.get("group_id") else None
            except ValueError:
                group_id = None
            return {
                "audience": "student_public",
                "viewer_id": raw_viewer_id[:128],
                "lecturer_id": None,
                "group_id": group_id,
            }

        if path.startswith("/api/v1/lecturer/"):
            payload = token_payload or self._decode_request_token(request) or {}
            lecturer_id = payload.get("lecturer_id")
            if lecturer_id is None:
                return None
            try:
                lecturer_id = int(lecturer_id)
            except (TypeError, ValueError):
                return None
            return {
                "audience": "lecturer_portal",
                "viewer_id": f"lecturer:{lecturer_id}",
                "lecturer_id": lecturer_id,
                "group_id": None,
            }

        return None

    async def dispatch(self, request, call_next):
        start_time = time.time()
        token_payload = self._decode_request_token(request)
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise e
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            tenant_id = self._resolve_tenant_context(request, token_payload=token_payload)
            plan_tier = "free"
            
            if tenant_id:
                db = None
                try:
                    db = SessionLocal()
                    uni = db.query(University).filter(University.id == tenant_id).first()
                    if uni and uni.plan_tier:
                        plan_tier = uni.plan_tier

                    if self._should_capture_request(request.url.path, tenant_id):
                        rounded_duration_ms = max(1, int(duration_ms))
                        normalized_plan = (plan_tier or "free").lower()
                        sla_target_ms = {
                            "free": 2500,
                            "starter": 2500,
                            "pro": 1800,
                            "professional": 1800,
                            "enterprise": 1200,
                        }.get(normalized_plan, 2500)
                        event_metadata = {
                            "endpoint_route": request.url.path,
                            "method": request.method,
                            "status_code": status_code,
                            "plan_tier": plan_tier,
                        }

                        emit_event(
                            db,
                            tenant_id=tenant_id,
                            metric_key="api_requests_total",
                            quantity=1,
                            source="api",
                            metadata=event_metadata,
                        )
                        emit_event(
                            db,
                            tenant_id=tenant_id,
                            metric_key="api_response_time_ms",
                            quantity=rounded_duration_ms,
                            source="api",
                            metadata={**event_metadata, "duration_ms": rounded_duration_ms},
                        )

                        if status_code >= 500:
                            emit_event(
                                db,
                                tenant_id=tenant_id,
                                metric_key="api_server_errors_total",
                                quantity=1,
                                source="api",
                                metadata=event_metadata,
                            )
                        elif status_code >= 400:
                            emit_event(
                                db,
                                tenant_id=tenant_id,
                                metric_key="api_client_errors_total",
                                quantity=1,
                                source="api",
                                metadata=event_metadata,
                            )

                        if rounded_duration_ms > sla_target_ms:
                            emit_event(
                                db,
                                tenant_id=tenant_id,
                                metric_key="api_sla_breaches_total",
                                quantity=1,
                                source="api",
                                metadata={**event_metadata, "duration_ms": rounded_duration_ms, "sla_target_ms": sla_target_ms},
                            )

                        viewer_context = self._resolve_viewer_context(request, token_payload=token_payload)
                        if viewer_context:
                            db.add(
                                ViewerActivity(
                                    tenant_id=tenant_id,
                                    audience=viewer_context["audience"],
                                    viewer_id=viewer_context["viewer_id"],
                                    lecturer_id=viewer_context["lecturer_id"],
                                    group_id=viewer_context["group_id"],
                                    route_key=request.url.path,
                                    method=request.method,
                                    status_code=status_code,
                                    response_time_ms=rounded_duration_ms,
                                    occurred_at=datetime.now(timezone.utc),
                                )
                            )

                        db.commit()
                except Exception:
                    if db:
                        db.rollback()
                finally:
                    if db:
                        db.close()
            
            request.state.plan_tier = plan_tier
            
            span = trace.get_current_span()
            if span and span.is_recording():
                span.set_attribute("tablesys.tenant_id", str(tenant_id) if tenant_id else "none")
                span.set_attribute("tablesys.plan_tier", plan_tier)
                
            attributes = {
                "tenant_id": str(tenant_id) if tenant_id else "none",
                "plan_tier": plan_tier,
                "status_code": status_code,
                "endpoint_route": request.url.path
            }
            
            api_request_duration_histogram.record(duration_ms, attributes)
            api_request_count_counter.add(1, attributes)
            
        return response

# Initialize Sentry SDK early in the process
sentry_dsn = os.getenv("SENTRY_DSN", "")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        environment=settings.ENVIRONMENT,
    )
import sentry_sdk

# Initialize Sentry SDK early in the process
sentry_dsn = os.getenv("SENTRY_DSN", "")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        environment=settings.ENVIRONMENT,
    )

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging():
    """
    Configure application, audit, and error logging with rotation.
    
    Creates three log files:
    - logs/app.log: General application logs (INFO+)
    - logs/audit.log: Security audit logs (90-day retention)
    - logs/error.log: Error logs only (ERROR+)
    
    All logs rotate at 10 MB with appropriate backup counts.
    """
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Root logger configuration
    logging.basicConfig(
        level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Add request context filter to all loggers
    request_filter = RequestContextFilter()
    
    # Application logger (general logs)
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG)
    app_handler = logging.handlers.RotatingFileHandler(
        "logs/app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=30,  # Keep 30 files (~300 MB total)
        encoding="utf-8"
    )
    app_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    app_handler.addFilter(request_filter)
    app_logger.addHandler(app_handler)
    
    # Audit logger (security events)
    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(logging.INFO)
    audit_handler = logging.handlers.RotatingFileHandler(
        "logs/audit.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=90,  # Keep 90 files (~900 MB total, 3 months)
        encoding="utf-8"
    )
    audit_handler.setFormatter(logging.Formatter(
        "%(message)s"  # Audit logs are already JSON formatted
    ))
    audit_logger.addHandler(audit_handler)
    
    # Error logger (errors only)
    error_logger = logging.getLogger("error")
    error_logger.setLevel(logging.ERROR)
    error_handler = logging.handlers.RotatingFileHandler(
        "logs/error.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=30,  # Keep 30 files (~300 MB total)
        encoding="utf-8"
    )
    error_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s\n%(exc_info)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    error_handler.addFilter(request_filter)
    error_logger.addHandler(error_handler)
    
    logging.info("Logging configured successfully")
    logging.info(f"Environment: {settings.ENVIRONMENT}")
    logging.info(f"Log directory: {logs_dir.absolute()}")

# Configure logging at startup
setup_logging()

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

from .lifecycle import lifespan

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

# Disable interactive API docs in production (major security best practice)
docs_url = "/docs" if settings.ENVIRONMENT == "development" else None
redoc_url = "/redoc" if settings.ENVIRONMENT == "development" else None

app = FastAPI(
    title=settings.APP_TITLE,
    description="Timetable management system",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
)

# ============================================================================
# MIDDLEWARE CONFIGURATION (Order matters!)
# ============================================================================

# 1. Error Handler FIRST (catches all errors)
app.add_middleware(ErrorHandlerMiddleware)

# 1.4 Public route rate limiting (must run before TenantMiddleware to block abuse early)
app.add_middleware(PublicRateLimitMiddleware)

# 1.5 Tenant Isolation
app.add_middleware(TenantMiddleware)

# 1.6 Observability
app.add_middleware(ObservabilityMiddleware)

# 2. Security Headers (adds security headers to all responses)
app.add_middleware(SecurityHeadersMiddleware)

# 3. CORS (allows cross-origin requests)
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:3002",
]

# Add production origin from settings (FRONTEND_URL env var)
if settings.FRONTEND_URL:
    allowed_origins.append(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^http(s)?://((.*?\.)?(localhost:5173|localhost:3000|localhost:3002|tablesys\.com|yourdomain\.com|nip\.io)|(\d{1,3}\.){3}\d{1,3}(:\d+)?)$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# ============================================================================
# TENANT ISOLATION INITIALIZATION
# ============================================================================

from .database import setup_tenant_isolation
setup_tenant_isolation()

# ============================================================================
# STATIC FILES (MEDIA)
# ============================================================================

import os
media_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "media")
os.makedirs(media_dir, exist_ok=True)
app.mount("/api/v1/media", StaticFiles(directory=media_dir), name="media")
app.mount("/media", StaticFiles(directory=media_dir), name="media_root")

# ============================================================================
# PROMETHEUS METRICS
# ============================================================================
from prometheus_fastapi_instrumentator import Instrumentator

@app.on_event("startup")
async def startup_prometheus():
    Instrumentator().instrument(app).expose(app)

# ============================================================================
# PROMETHEUS METRICS
# ============================================================================
from prometheus_fastapi_instrumentator import Instrumentator

@app.on_event("startup")
async def startup_prometheus():
    Instrumentator().instrument(app).expose(app)

# ============================================================================
# ROUTER REGISTRATION
# ============================================================================

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(departments.router)
app.include_router(courses.router)
app.include_router(lecturers.router)
app.include_router(rooms.router)
app.include_router(groups.router)
app.include_router(activity_types.router)
app.include_router(institution_setup.router)
app.include_router(schools.router)
app.include_router(timetables.router)
app.include_router(exam_timetables.router)
app.include_router(export.router, prefix="/api/v1")
app.include_router(import_timetable.router)
app.include_router(print_views.router)
app.include_router(notifications.router)
app.include_router(search.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(usage.router)
app.include_router(student_portal.router)
app.include_router(mobile_portal.router)
app.include_router(mobile_public.router)  # Anonymous student access (no auth)
app.include_router(audit.router)
app.include_router(scheduler.router)
app.include_router(lecturer_portal.router)
# Phase 11: Super Admin + Branding routers
app.include_router(superadmin.router)
app.include_router(branding.router)
app.include_router(public.router)
app.include_router(stats.router)   # Agent Delta: GET /api/v1/stats/summary (read-only)

# Lab Coordinator router
from .routers import lab_coordinator
app.include_router(lab_coordinator.router)

# Agent Gamma — SIS Integration (headless webhooks + API key management)
app.include_router(sis_router.router)
app.include_router(data_export.router)   # GDPR/POPIA data export
app.include_router(offboarding.router)   # Tenant deactivation + purge
app.include_router(alerts_router.router)  # Platform alert engine

# ============================================================================
# OPENTELEMETRY FASTAPI INSTRUMENTATION
# ============================================================================
FastAPIInstrumentor.instrument_app(app)

# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
