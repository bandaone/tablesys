"""
Public Router — no auth required.

Endpoints:
  GET  /api/v1/public/university   — Pre-load branding on login page
  POST /api/v1/public/register     — Step 1: Create pending registration + send email
  POST /api/v1/public/verify       — Step 2: Verify token, provision tenant + admin
  POST /api/v1/public/resend       — Resend verification email for a pending registration
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from ..models import University, User, UserRole, PendingRegistration, Notification
from ..schemas import TenantRegistrationRequest, TenantVerificationRequest, Token
from ..auth import get_password_hash, create_access_token
from ..config import settings
from ..utils.sanitization import sanitize_input
from ..tasks.registration_tasks import send_verification_email_task
from ..services.provisioning import provision_tenant, ProvisioningError

logger = logging.getLogger("app.registration")

router = APIRouter(prefix="/api/v1/public", tags=["public"])


# ─── Registration Rate Limiter ────────────────────────────────────────────────
# Max 3 registration attempts per IP per hour.
# This is separate from the login rate limiter.

_reg_attempts: dict[str, list[datetime]] = defaultdict(list)
_reg_lock = Lock()
_REG_MAX_ATTEMPTS = 3
_REG_WINDOW_SECONDS = 3600  # 1 hour


def _check_registration_rate_limit(ip: str) -> bool:
    """Return True if allowed, False if rate-limited."""
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=_REG_WINDOW_SECONDS)
    with _reg_lock:
        _reg_attempts[ip] = [t for t in _reg_attempts[ip] if t > cutoff]
        if len(_reg_attempts[ip]) >= _REG_MAX_ATTEMPTS:
            return False
        _reg_attempts[ip].append(now)
        return True


# ─── Response Models ──────────────────────────────────────────────────────────

class PublicBrandingResponse(BaseModel):
    id: int
    name: str
    short_name: Optional[str]
    domain: str
    logo_url: Optional[str]
    primary_color: str
    secondary_color: str
    tagline: Optional[str]

    class Config:
        from_attributes = True


class ResendRequest(BaseModel):
    email: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/university", response_model=PublicBrandingResponse)
def get_university_public_branding(domain: str, db: Session = Depends(get_db)):
    """
    Returns non-sensitive branding info for a university by domain.
    Used by the login page to pre-load school-specific colours/logo
    before authentication.
    """
    normalized_domain = domain.strip().lower()
    uni = db.query(University).filter(
        University.domain == normalized_domain,
        University.is_active == True
    ).first()

    if not uni and "." in normalized_domain:
        subdomain = normalized_domain.split(".", 1)[0]
        if subdomain and subdomain != normalized_domain:
            uni = db.query(University).filter(
                (University.domain == subdomain) | 
                (University.domain == f"{subdomain}.tablesys.cloud"),
                University.is_active == True
            ).first()

    if not uni:
        raise HTTPException(status_code=404, detail="University not found or inactive.")

    return uni


@router.post("/register", status_code=202)
def register_tenant(request: TenantRegistrationRequest, req: Request, db: Session = Depends(get_db)):
    """
    Step 1: Validate inputs, create a PendingRegistration, and dispatch
    a verification email with an opaque token (no credentials in the URL).
    """
    # ── Rate limiting ─────────────────────────────────────────────────────
    client_ip = req.client.host if req.client else "unknown"
    if not _check_registration_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many registration attempts. Please try again later."
        )

    # ── Normalize + sanitize inputs ──────────────────────────────────────
    organization_name = sanitize_input(request.organization_name, max_length=200)
    subdomain = sanitize_input(request.subdomain, max_length=100).lower()
    admin_email = sanitize_input(request.admin_email, max_length=200).lower()
    admin_username = sanitize_input(request.admin_username, max_length=50)
    admin_full_name = sanitize_input(request.admin_full_name, max_length=200)

    # ── Uniqueness checks (generic error to prevent enumeration) ──────────
    domain_taken = db.query(University).filter(University.domain == subdomain).first()
    username_taken = db.query(User).filter(User.username == admin_username).first()
    email_taken = db.query(User).filter(User.email == admin_email).first()

    # Also check pending registrations that haven't expired
    now = datetime.now(timezone.utc)
    pending_email = db.query(PendingRegistration).filter(
        PendingRegistration.admin_email == admin_email,
        PendingRegistration.status == "pending",
        PendingRegistration.expires_at > now,
    ).first()

    if domain_taken or username_taken or email_taken or pending_email:
        # Log the specific reason server-side for debugging
        reason = "domain" if domain_taken else "username" if username_taken else "email" if email_taken else "pending"
        logger.warning(
            "Registration rejected (reason=%s) subdomain=%s email=%s ip=%s",
            reason, subdomain, admin_email, client_ip
        )
        raise HTTPException(
            status_code=400,
            detail="Registration could not be completed. The domain, username, or email may already be in use."
        )

    # ── Create pending registration ───────────────────────────────────────
    opaque_token = uuid.uuid4().hex
    expires_at = now + timedelta(hours=2)  # 2-hour verification window

    pending = PendingRegistration(
        token=opaque_token,
        org_name=organization_name,
        subdomain=subdomain,
        admin_email=admin_email,
        admin_username=admin_username,
        admin_full_name=admin_full_name,
        hashed_password=get_password_hash(request.admin_password),
        status="pending",
        ip_address=client_ip,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(pending)
    db.commit()

    # ── Dispatch verification email ───────────────────────────────────────
    frontend_url = settings.FRONTEND_URL or "http://localhost:3002"
    verify_url = f"{frontend_url}/verify?token={opaque_token}"

    logger.info("Registration pending: subdomain=%s email=%s", subdomain, admin_email)
    
    email_enabled = getattr(settings, "EMAIL_ENABLED", False)
    if not email_enabled:
        logger.warning(
            "⚠️ EMAIL_ENABLED is False or SMTP is not configured. Email will be skipped.\n"
            "⚠️ MANUAL VERIFICATION LINK: %s", verify_url
        )

    try:
        send_verification_email_task.delay(
            recipient=admin_email,
            organization_name=organization_name,
            verification_link=verify_url,
        )
    except Exception:
        logger.warning("Could not dispatch verification email via task queue — will retry on resend.")

    return {"message": "Verification email sent. Please check your inbox.", "status": "pending"}


@router.post("/verify", response_model=Token)
def verify_tenant(request: TenantVerificationRequest, db: Session = Depends(get_db)):
    """
    Step 2: Validate the opaque verification token, then delegate all tenant
    provisioning to the provisioning service.

    The router is responsible only for:
    - Finding and validating the PendingRegistration
    - Uniqueness re-checks (domain/email could have been taken during window)
    - Translating ProvisioningError into an HTTP 500

    All provisioning logic (University, User, seeding, notifications, usage events)
    lives in backend/app/services/provisioning.py.
    """
    now = datetime.now(timezone.utc)

    # ── Find pending registration ─────────────────────────────────────────
    pending = db.query(PendingRegistration).filter(
        PendingRegistration.token == request.token,
    ).first()

    if not pending:
        raise HTTPException(status_code=400, detail="Invalid verification token.")

    if pending.status == "verified":
        raise HTTPException(status_code=400, detail="This link has already been used. Please sign in.")

    if pending.status == "failed_provisioning":
        raise HTTPException(
            status_code=409,
            detail="Provisioning previously failed for this registration. Please contact support for manual retry.",
        )

    if pending.status == "expired" or pending.expires_at < now:
        pending.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Verification link has expired. Please register again.")

    # ── Re-check uniqueness (may have been taken during verification window)
    if db.query(University).filter(University.domain == pending.subdomain).first():
        pending.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="This workspace domain was taken. Please register again.")

    if db.query(User).filter(User.email == pending.admin_email).first():
        pending.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="This email is now associated with another account.")

    # ── Delegate provisioning ─────────────────────────────────────────────
    try:
        result = provision_tenant(db, pending)
    except ProvisioningError as exc:
        logger.error("Tenant provisioning failed for pending_id=%s: %s", pending.id, exc)
        raise HTTPException(
            status_code=500,
            detail="Tenant provisioning encountered an error. Our team has been notified. Please contact support.",
        )

    return {"access_token": result.access_token, "token_type": result.token_type}


@router.post("/resend", status_code=200)
def resend_verification(request: ResendRequest, req: Request, db: Session = Depends(get_db)):
    """
    Resend a verification email for a pending registration.
    Uses the same rate limiter as registration.
    """
    client_ip = req.client.host if req.client else "unknown"
    if not _check_registration_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please try again later."
        )

    sanitized_email = sanitize_input(request.email, max_length=200).lower()
    now = datetime.now(timezone.utc)
    pending = db.query(PendingRegistration).filter(
        PendingRegistration.admin_email == sanitized_email,
        PendingRegistration.status == "pending",
        PendingRegistration.expires_at > now,
    ).first()

    # Always return success (don't reveal if email exists)
    if not pending:
        return {"message": "If a pending registration exists for this email, a verification link has been sent."}

    # Generate a fresh token and extend expiry
    pending.token = uuid.uuid4().hex
    pending.expires_at = now + timedelta(hours=2)
    db.commit()

    frontend_url = settings.FRONTEND_URL or "http://localhost:3002"
    verify_url = f"{frontend_url}/verify?token={pending.token}"

    email_enabled = getattr(settings, "EMAIL_ENABLED", False)
    if not email_enabled:
        logger.warning(
            "⚠️ EMAIL_ENABLED is False or SMTP is not configured. Email will be skipped.\n"
            "⚠️ MANUAL VERIFICATION LINK: %s", verify_url
        )

    try:
        send_verification_email_task.delay(
            recipient=pending.admin_email,
            organization_name=pending.org_name,
            verification_link=verify_url,
        )
    except Exception:
        logger.warning("Could not dispatch resend email via task queue.")

    return {"message": "If a pending registration exists for this email, a verification link has been sent."}


@router.get("/legacy-access")
def get_legacy_access(token: str, db: Session = Depends(get_db)):
    """
    Validate a single-use legacy access token and return the associated university_id.
    Supports admin-issued onboarding links for tenants without DNS configured.
    """
    if not token:
        raise HTTPException(status_code=400, detail="token is required")

    row = db.execute(
        text(
            """
        SELECT id, university_id, expires_at, used_at
        FROM tenant_access_links
        WHERE token = :token
        FOR UPDATE
        """
        ),
        {"token": token},
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Invalid or expired token.")

    link_id, university_id, expires_at, used_at = row

    now = datetime.now(timezone.utc)
    if used_at is not None:
        raise HTTPException(status_code=410, detail="Token already used.")
    if expires_at is not None and expires_at < now:
        raise HTTPException(status_code=410, detail="Token expired.")

    db.execute(text("UPDATE tenant_access_links SET used_at = now() WHERE id = :id"), {"id": link_id})
    db.commit()

    return {"university_id": university_id}
