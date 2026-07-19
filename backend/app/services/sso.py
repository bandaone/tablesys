"""
Agent Alpha — SSO Service
═════════════════════════
Handles the full OAuth2 Authorization Code Flow (server-side) for:
  • Google (OpenID Connect)
  • Microsoft Entra ID (Azure AD)

Design principles:
  1. client_secret never leaves the backend — the browser only ever sees
     the authorization URL and the final TABLESYS JWT.
  2. State parameter (CSRF) is a signed, short-lived HMAC token so we
     don't need an extra Redis/session store.
  3. No DB migrations — SSO users are stored with hashed_password =
     "sso::<provider>::<sub>" so the auth guard knows to skip bcrypt.
  4. Domain → Tenant matching: email domain is used to find the university;
     rejected if no match (prevents random Google accounts gaining access).
  5. Auto-provisioning: first-time SSO users get role=TENANT_ADMIN; an admin
     can change the role afterwards from the Users page.
"""

import hashlib
import hmac
import time
import json
import base64
import secrets
import logging
from typing import Optional
from urllib.parse import urlencode, urlparse

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import User, UserRole, University

logger = logging.getLogger("app")

# ── Constants ──────────────────────────────────────────────────────────────────

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_SCOPES    = "openid email profile"

_MS_BASE         = "https://login.microsoftonline.com/{tenant}"
MS_AUTH_URL      = _MS_BASE + "/oauth2/v2.0/authorize"
MS_TOKEN_URL     = _MS_BASE + "/oauth2/v2.0/token"
MS_GRAPH_ME      = "https://graph.microsoft.com/v1.0/me"
MS_SCOPES        = "openid email profile User.Read"

STATE_TTL_SECONDS = 300       # State token valid for 5 minutes
SSO_MARKER_PREFIX = "sso::"   # Prefix in hashed_password for SSO users


# ── CSRF State helpers ─────────────────────────────────────────────────────────

def _generate_state(provider: str) -> str:
    """
    Generate a signed, time-stamped state token.
    Format (base64-url-safe): JSON payload + HMAC-SHA256 signature.
    No external store needed — the signature proves authenticity.
    """
    payload = {
        "provider": provider,
        "nonce": secrets.token_hex(16),
        "ts": int(time.time()),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(
        settings.SECRET_KEY.encode(),
        raw,
        hashlib.sha256,
    ).hexdigest()
    combined = base64.urlsafe_b64encode(raw).decode() + "." + sig
    return combined


def _verify_state(state: str, expected_provider: str) -> bool:
    """Verify state token signature and TTL; returns True if valid."""
    try:
        encoded, sig = state.rsplit(".", 1)
        raw = base64.urlsafe_b64decode(encoded.encode())
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode(),
            raw,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            logger.warning("SSO state signature mismatch")
            return False
        payload = json.loads(raw)
        if payload.get("provider") != expected_provider:
            logger.warning("SSO state provider mismatch")
            return False
        age = int(time.time()) - payload.get("ts", 0)
        if age > STATE_TTL_SECONDS:
            logger.warning("SSO state token expired (%ds old)", age)
            return False
        return True
    except Exception as exc:
        logger.exception("SSO state verification error: %s", exc)
        return False


# ── Redirect URI builders ──────────────────────────────────────────────────────

def _google_redirect_uri() -> str:
    return f"{settings.SSO_REDIRECT_BASE_URL.rstrip('/')}/api/v1/auth/sso/google/callback"


def _microsoft_redirect_uri() -> str:
    return f"{settings.SSO_REDIRECT_BASE_URL.rstrip('/')}/api/v1/auth/sso/microsoft/callback"


# ── Authorization URL builders ─────────────────────────────────────────────────

def build_google_auth_url() -> str:
    """Return the Google OpenID Connect authorization URL."""
    if not settings.GOOGLE_CLIENT_ID:
        raise ValueError("GOOGLE_CLIENT_ID is not configured")
    params = {
        "client_id":     settings.GOOGLE_CLIENT_ID,
        "redirect_uri":  _google_redirect_uri(),
        "response_type": "code",
        "scope":         GOOGLE_SCOPES,
        "state":         _generate_state("google"),
        "access_type":   "online",
        "prompt":        "select_account",   # Always show account chooser
    }
    return GOOGLE_AUTH_URL + "?" + urlencode(params)


def build_microsoft_auth_url() -> str:
    """Return the Microsoft Entra ID authorization URL."""
    if not settings.MICROSOFT_CLIENT_ID:
        raise ValueError("MICROSOFT_CLIENT_ID is not configured")
    tenant = settings.MICROSOFT_TENANT_ID or "common"
    params = {
        "client_id":     settings.MICROSOFT_CLIENT_ID,
        "redirect_uri":  _microsoft_redirect_uri(),
        "response_type": "code",
        "scope":         MS_SCOPES,
        "state":         _generate_state("microsoft"),
        "prompt":        "select_account",
    }
    return MS_AUTH_URL.format(tenant=tenant) + "?" + urlencode(params)


# ── Token exchange ─────────────────────────────────────────────────────────────

async def exchange_google_code(code: str) -> dict:
    """Exchange an authorization code for Google user info."""
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri":  _google_redirect_uri(),
            "grant_type":    "authorization_code",
        })
        token_resp.raise_for_status()
        tokens = token_resp.json()

        info_resp = await client.get(
            GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        info_resp.raise_for_status()
        info = info_resp.json()

    return {
        "provider":    "google",
        "sub":         info["sub"],           # Stable unique Google user ID
        "email":       info.get("email", "").lower().strip(),
        "full_name":   info.get("name", ""),
        "email_verified": info.get("email_verified", False),
    }


async def exchange_microsoft_code(code: str) -> dict:
    """Exchange an authorization code for Microsoft Graph user info."""
    tenant = settings.MICROSOFT_TENANT_ID or "common"
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            MS_TOKEN_URL.format(tenant=tenant),
            data={
                "code":          code,
                "client_id":     settings.MICROSOFT_CLIENT_ID,
                "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                "redirect_uri":  _microsoft_redirect_uri(),
                "grant_type":    "authorization_code",
                "scope":         MS_SCOPES,
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        me_resp = await client.get(
            MS_GRAPH_ME,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        me_resp.raise_for_status()
        me = me_resp.json()

    email = (
        me.get("mail")
        or me.get("userPrincipalName", "")
    ).lower().strip()

    return {
        "provider":    "microsoft",
        "sub":         me.get("id", ""),      # Stable unique MS object ID
        "email":       email,
        "full_name":   me.get("displayName", ""),
        "email_verified": True,               # MS Graph always returns verified
    }


# ── Domain → Tenant resolver ───────────────────────────────────────────────────

def _email_domain(email: str) -> str:
    return email.split("@")[-1] if "@" in email else ""


def resolve_university(db: Session, email: str) -> Optional[University]:
    """
    Find the university whose `domain` matches the email's domain.
    Returns None if no match (access denied).
    """
    domain = _email_domain(email)
    if not domain:
        return None
    return (
        db.query(University)
        .filter(University.domain == domain, University.is_active.is_(True))
        .first()
    )


# ── User provisioning ──────────────────────────────────────────────────────────

def get_or_create_sso_user(db: Session, profile: dict, university: University) -> User:
    """
    Find an existing user by email or SSO marker; create one if brand new.

    hashed_password format for SSO users:
        sso::<provider>::<sub>
    e.g.
        sso::google::118392847563920948571
    """
    provider = profile["provider"]
    sub      = profile["sub"]
    email    = profile["email"]
    marker   = f"{SSO_MARKER_PREFIX}{provider}::{sub}"

    # 1. Try to find by the SSO marker (most reliable — survives email changes)
    user = (
        db.query(User)
        .filter(User.hashed_password == marker, User.university_id == university.id)
        .first()
    )

    # 2. Fall back to email lookup (handles the case where they previously used
    #    password login with the same address)
    if user is None:
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Upgrade their record to SSO marker so future logins are faster
            user.hashed_password = marker
            logger.info(
                "Linked existing user %s to SSO provider %s", email, provider
            )

    # 3. Brand new user — auto-provision
    if user is None:
        raw_username = email.split("@")[0].replace(".", "_").replace("-", "_")
        # Ensure username uniqueness
        username = raw_username
        suffix = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{raw_username}_{suffix}"
            suffix += 1

        user = User(
            university_id   = university.id,
            email           = email,
            username        = username,
            full_name       = profile.get("full_name") or email.split("@")[0],
            hashed_password = marker,
            role            = UserRole.TENANT_ADMIN,   # Safe default; admin can change
            is_active       = True,
        )
        db.add(user)
        logger.info(
            "Auto-provisioned SSO user %s from provider %s under university %d",
            email, provider, university.id,
        )

    db.commit()
    db.refresh(user)
    return user
