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
from .database import engine, Base
from .models import *  # Import all models so SQLAlchemy knows about them
from .routers import auth, courses, lecturers, rooms, groups, departments, timetables, exam_timetables, export, import_timetable, users, print_views, notifications, search, dashboard, reports, student_portal, mobile_portal, mobile_public, audit, scheduler, lecturer_portal
from .routers import superadmin, branding, public
from .routers import stats  # Agent Delta: read-only analytics stats router
from .routers.api import sis as sis_router  # Agent Gamma: SIS webhooks
from .middleware import SecurityHeadersMiddleware, ErrorHandlerMiddleware, TenantMiddleware
from .utils import RequestContextFilter
from .config import settings
import os
import logging
import logging.handlers
from pathlib import Path
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

# Create database tables
Base.metadata.create_all(bind=engine)

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

# 1.5 Tenant Isolation
app.add_middleware(TenantMiddleware)

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
    allow_origin_regex=r"^http(s)?://(.*?\.)?(localhost:5173|localhost:3000|localhost:3002|tablesys\.com|yourdomain\.com)$",
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
app.include_router(timetables.router)
app.include_router(exam_timetables.router)
app.include_router(export.router, prefix="/api/v1")
app.include_router(import_timetable.router)
app.include_router(print_views.router)
app.include_router(notifications.router)
app.include_router(search.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
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
# Agent Gamma — SIS Integration (headless webhooks + API key management)
app.include_router(sis_router.router)

# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
