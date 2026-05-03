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
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from ..models import University, User, UserRole, PendingRegistration, Notification
from ..schemas import TenantRegistrationRequest, TenantVerificationRequest, Token
from ..auth import get_password_hash, create_access_token
from ..config import settings
from ..tasks.registration_tasks import send_verification_email_task

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
    uni = db.query(University).filter(
        University.domain == domain,
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

    # ── Uniqueness checks (generic error to prevent enumeration) ──────────
    domain_taken = db.query(University).filter(University.domain == request.subdomain).first()
    username_taken = db.query(User).filter(User.username == request.admin_username).first()
    email_taken = db.query(User).filter(User.email == request.admin_email).first()

    # Also check pending registrations that haven't expired
    now = datetime.now(timezone.utc)
    pending_email = db.query(PendingRegistration).filter(
        PendingRegistration.admin_email == request.admin_email,
        PendingRegistration.status == "pending",
        PendingRegistration.expires_at > now,
    ).first()

    if domain_taken or username_taken or email_taken or pending_email:
        # Log the specific reason server-side for debugging
        reason = "domain" if domain_taken else "username" if username_taken else "email" if email_taken else "pending"
        logger.warning(
            "Registration rejected (reason=%s) subdomain=%s email=%s ip=%s",
            reason, request.subdomain, request.admin_email, client_ip
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
        org_name=request.organization_name,
        subdomain=request.subdomain,
        admin_email=request.admin_email,
        admin_username=request.admin_username,
        admin_full_name=request.admin_full_name,
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

    logger.info("Registration pending: subdomain=%s email=%s", request.subdomain, request.admin_email)

    try:
        send_verification_email_task.delay(
            recipient=request.admin_email,
            organization_name=request.organization_name,
            verification_link=verify_url,
        )
    except Exception:
        logger.warning("Could not dispatch verification email via task queue — will retry on resend.")

    return {"message": "Verification email sent. Please check your inbox.", "status": "pending"}


@router.post("/verify", response_model=Token)
def verify_tenant(request: TenantVerificationRequest, db: Session = Depends(get_db)):
    """
    Step 2: Look up the PendingRegistration by opaque token, validate it,
    provision the tenant + admin, and return an access token.
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

    # ── Provision University ──────────────────────────────────────────────
    uni = University(
        name=pending.org_name,
        domain=pending.subdomain,
        is_active=True,
        registered_at=now,
        plan_tier="pro",
        max_users=0,  # Unlimited
    )
    db.add(uni)
    db.flush()  # Get uni.id before creating admin

    # ── Provision Admin User ──────────────────────────────────────────────
    admin_user = User(
        university_id=uni.id,
        username=pending.admin_username,
        email=pending.admin_email,
        full_name=pending.admin_full_name,
        hashed_password=pending.hashed_password,
        role=UserRole.COORDINATOR,
        is_active=True,
    )
    db.add(admin_user)

    # ── Mark pending registration as consumed ─────────────────────────────
    pending.status = "verified"

    # ── Notify all SuperAdmins ────────────────────────────────────────────
    superadmins = db.query(User).filter(User.role == UserRole.SUPERADMIN).all()
    for sa in superadmins:
        notification = Notification(
            user_id=sa.id,
            title="New Tenant Registered",
            message=f"{pending.org_name} ({pending.subdomain}) has been verified and provisioned. Admin: {pending.admin_email}",
            type="info",
            is_read=False,
            created_at=now,
            action_link="/superadmin",
        )
        db.add(notification)

    db.commit()

    logger.info(
        "Tenant provisioned: university_id=%d domain=%s admin=%s",
        uni.id, uni.domain, admin_user.email
    )

    # ── Generate access token for auto-login ──────────────────────────────
    access_token = create_access_token(
        data={"sub": admin_user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {"access_token": access_token, "token_type": "bearer"}


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

    now = datetime.now(timezone.utc)
    pending = db.query(PendingRegistration).filter(
        PendingRegistration.admin_email == request.email,
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

    try:
        send_verification_email_task.delay(
            recipient=pending.admin_email,
            organization_name=pending.org_name,
            verification_link=verify_url,
        )
    except Exception:
        logger.warning("Could not dispatch resend email via task queue.")

    return {"message": "If a pending registration exists for this email, a verification link has been sent."}
