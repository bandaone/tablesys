from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta
from ..database import get_db
from ..schemas import Token, User, LoginRequest
from ..auth import create_access_token, get_current_user, authenticate_user
from ..config import settings
from ..models import User as UserModel
from ..middleware.rate_limiter import RateLimiter
from ..utils.ip_utils import get_client_ip
from ..utils.audit_logger import AuditLogger

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

# Create rate limiter instance with configurable settings
rate_limiter = RateLimiter(
    max_attempts=settings.RATE_LIMIT_MAX_ATTEMPTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    block_duration=settings.RATE_LIMIT_BLOCK_DURATION
)

@router.post("/login", response_model=Token)
def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """Secure password-based authentication with rate limiting"""
    
    # Get client IP (handles proxies correctly)
    client_ip = get_client_ip(request)
    
    # Check rate limit
    is_allowed, error_message = rate_limiter.check_rate_limit(client_ip)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_message
        )
    
    # Authenticate user with username and password
    user = authenticate_user(db, login_data.username, login_data.password)
    
    if not user:
        # Log failed login attempt
        AuditLogger.log_login_attempt(
            request=request,
            username=login_data.username,
            success=False,
            details={"reason": "Invalid credentials"}
        )
        
        # Record failed attempt for rate limiting
        rate_limiter.record_attempt(client_ip, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check Tenant Scope: User must belong to the tenant they are trying to log into.
    # SUPERADMIN can login anywhere.
    user_role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    if user_role_str != "SUPERADMIN" and login_data.university_id is not None:
        if user.university_id != login_data.university_id:
            AuditLogger.log_login_attempt(
                request=request,
                username=login_data.username,
                success=False,
                details={"reason": "Workspace mismatch", "user_id": user.id, "target_tenant": login_data.university_id}
            )
            rate_limiter.record_attempt(client_ip, success=False)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials for this workspace",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    if not user.is_active:
        # Log failed login attempt (inactive account)
        AuditLogger.log_login_attempt(
            request=request,
            username=login_data.username,
            success=False,
            details={"reason": "Account inactive", "user_id": user.id}
        )
        
        # Record failed attempt (inactive account)
        rate_limiter.record_attempt(client_ip, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )
    
    # Log successful login
    AuditLogger.log_login_attempt(
        request=request,
        username=user.username,
        success=True,
        details={
            "user_id": user.id,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "department_id": user.department_id
        }
    )
    
    # Update last login timestamp
    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    # Record successful attempt (clears failed attempts)
    rate_limiter.record_attempt(client_ip, success=True)
    
    # Create access token with embedded tenant context
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "university_id": user.university_id,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role)
        }, 
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: UserModel = Depends(get_current_user)
):
    """Get current user information"""
    return current_user


# ══════════════════════════════════════════════════════════════════════════════
# SSO — Single Sign-On endpoints (Agent Alpha)
# All four endpoints live here so we stay in Alpha's allowed file scope.
# ══════════════════════════════════════════════════════════════════════════════

from fastapi.responses import RedirectResponse, JSONResponse
from ..services.sso import (
    build_google_auth_url,
    build_microsoft_auth_url,
    exchange_google_code,
    exchange_microsoft_code,
    resolve_university,
    get_or_create_sso_user,
    _verify_state,
)
from ..utils.audit_logger import AuditLogger


def _sso_disabled_guard():
    """Raise 503 if SSO is not enabled in config."""
    if not settings.SSO_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO is not enabled on this platform.",
        )


def _issue_sso_token(user: UserModel) -> str:
    """Issue the same JWT format used by password login."""
    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token(
        data={
            "sub": user.username,
            "university_id": user.university_id,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        },
        expires_delta=expires,
    )


# ── Provider info endpoint (consumed by the frontend to decide what to render) ─

@router.get("/sso/providers")
def sso_providers():
    """
    Returns which SSO providers are available.
    The frontend checks this once on mount to show/hide SSO buttons.
    """
    return {
        "sso_enabled": settings.SSO_ENABLED,
        "google":      bool(settings.SSO_ENABLED and settings.GOOGLE_CLIENT_ID),
        "microsoft":   bool(settings.SSO_ENABLED and settings.MICROSOFT_CLIENT_ID),
    }


# ── Google ─────────────────────────────────────────────────────────────────────

@router.get("/sso/google/authorize")
def google_authorize():
    """
    Step 1: Redirect the browser to Google's consent screen.
    The frontend just navigates to this URL — no body / JSON involved.
    """
    _sso_disabled_guard()
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Google SSO is not configured.")
    url = build_google_auth_url()
    return RedirectResponse(url, status_code=302)


@router.get("/sso/google/callback")
async def google_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    """
    Step 2: Google redirects here with ?code=&state=
    We exchange the code, provision/find the user, issue our JWT,
    then redirect to the frontend callback page with the token.
    """
    _sso_disabled_guard()

    frontend_cb = settings.SSO_FRONTEND_CALLBACK

    if error:
        AuditLogger.log_login_attempt(
            request=request, username="sso:google",
            success=False, details={"error": error},
        )
        return RedirectResponse(f"{frontend_cb}?error={error}", status_code=302)

    if not code:
        return RedirectResponse(f"{frontend_cb}?error=no_code", status_code=302)

    if not _verify_state(state, "google"):
        return RedirectResponse(f"{frontend_cb}?error=invalid_state", status_code=302)

    try:
        profile = await exchange_google_code(code)
    except Exception as exc:
        logger.error("Google token exchange failed: %s", exc)
        return RedirectResponse(f"{frontend_cb}?error=token_exchange_failed", status_code=302)

    if not profile.get("email_verified"):
        return RedirectResponse(f"{frontend_cb}?error=email_not_verified", status_code=302)

    university = resolve_university(db, profile["email"])
    if university is None:
        return RedirectResponse(f"{frontend_cb}?error=institution_not_found", status_code=302)

    user = get_or_create_sso_user(db, profile, university)
    if not user.is_active:
        return RedirectResponse(f"{frontend_cb}?error=account_inactive", status_code=302)

    token = _issue_sso_token(user)

    AuditLogger.log_login_attempt(
        request=request, username=user.username,
        success=True, details={"provider": "google", "user_id": user.id},
    )

    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(f"{frontend_cb}?token={token}", status_code=302)


# ── Microsoft ──────────────────────────────────────────────────────────────────

@router.get("/sso/microsoft/authorize")
def microsoft_authorize():
    """Redirect to Microsoft Entra ID consent screen."""
    _sso_disabled_guard()
    if not settings.MICROSOFT_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Microsoft SSO is not configured.")
    url = build_microsoft_auth_url()
    return RedirectResponse(url, status_code=302)


@router.get("/sso/microsoft/callback")
async def microsoft_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    """
    Microsoft redirects here after consent.
    Same flow as Google callback.
    """
    _sso_disabled_guard()

    frontend_cb = settings.SSO_FRONTEND_CALLBACK

    if error:
        AuditLogger.log_login_attempt(
            request=request, username="sso:microsoft",
            success=False, details={"error": error},
        )
        return RedirectResponse(f"{frontend_cb}?error={error}", status_code=302)

    if not code:
        return RedirectResponse(f"{frontend_cb}?error=no_code", status_code=302)

    if not _verify_state(state, "microsoft"):
        return RedirectResponse(f"{frontend_cb}?error=invalid_state", status_code=302)

    try:
        profile = await exchange_microsoft_code(code)
    except Exception as exc:
        logger.error("Microsoft token exchange failed: %s", exc)
        return RedirectResponse(f"{frontend_cb}?error=token_exchange_failed", status_code=302)

    university = resolve_university(db, profile["email"])
    if university is None:
        return RedirectResponse(f"{frontend_cb}?error=institution_not_found", status_code=302)

    user = get_or_create_sso_user(db, profile, university)
    if not user.is_active:
        return RedirectResponse(f"{frontend_cb}?error=account_inactive", status_code=302)

    token = _issue_sso_token(user)

    AuditLogger.log_login_attempt(
        request=request, username=user.username,
        success=True, details={"provider": "microsoft", "user_id": user.id},
    )

    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(f"{frontend_cb}?token={token}", status_code=302)

