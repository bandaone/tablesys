"""
Tenant Provisioning Service

Extracts and encapsulates the tenant onboarding lifecycle from the public router
into a staged, rollback-safe service as specified by the integration contract.

Stages
------
1. tenant_record_created      — University row created and flushed.
2. admin_account_created      — Coordinator user created and flushed.
3. baseline_seed_applied      — Default calendar, branding, and quota placeholders seeded.
4. notifications_written      — SuperAdmin notifications queued.
5. usage_baseline_recorded    — Onboarding UsageEvent rows queued.
6. provisioning_complete      — PendingRegistration marked verified, transaction committed,
                                access token generated.

Rollback Policy
---------------
- All stages execute within a single database transaction.
- If any stage raises an exception:
  - The in-flight transaction is rolled back so partial tenant rows do not survive.
  - PendingRegistration is marked with status="failed_provisioning" in a follow-up commit.
  - The exception is re-raised as ProvisioningError.
- Automated retry is out of scope for this slice. Manual Superadmin retry is acceptable.
"""

import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from ..models import University, User, UserRole, PendingRegistration, Notification
from ..auth import create_access_token
from ..config import settings
from ..seeding_utils import seed_tenant_baseline, emit_onboarding_events, ensure_platform_quotas_seeded

logger = logging.getLogger("app.provisioning")


class ProvisioningError(Exception):
    """Raised when tenant provisioning fails at any stage."""
    pass


@dataclass
class ProvisioningResult:
    access_token: str
    token_type: str = "bearer"
    university_id: Optional[int] = None
    stages_completed: list = field(default_factory=list)


def provision_tenant(db: Session, pending: PendingRegistration) -> ProvisioningResult:
    """
    Execute the full 6-stage tenant provisioning lifecycle.

    Parameters
    ----------
    db : Session
        The active database session. The caller should NOT commit before this
        function returns — provisioning owns the transaction.
    pending : PendingRegistration
        A validated PendingRegistration row (token checked, not expired, not yet verified).

    Returns
    -------
    ProvisioningResult with a ready-to-return access token.

    Raises
    ------
    ProvisioningError on any stage failure after partial state has been written.
    """
    now = datetime.now(timezone.utc)
    uni: Optional[University] = None
    stages_completed = []

    # ── Pre-flight: guarantee platform quota rows exist ───────────────────────
    # This runs OUTSIDE the tenant transaction so quota rows are committed and
    # visible to subsequent queries inside the transaction. On a warm production
    # DB this is a cheap read (rows already exist); on a fresh/test DB it seeds
    # them automatically without breaking atomicity.
    try:
        ensure_platform_quotas_seeded(db)
    except Exception as exc:
        raise ProvisioningError(
            f"Platform quota pre-flight failed: {exc}"
        ) from exc

    try:
        # ── Stage 1: tenant_record_created ───────────────────────────────────
        plan_tier = getattr(pending, "plan_tier", None) or "free"
        uni = University(
            name=pending.org_name,
            domain=pending.subdomain,
            timezone="Africa/Lusaka",
            is_active=True,
            registered_at=now,
            plan_tier=plan_tier,
            max_users=0,  # Unlimited (enforced by quota layer instead)
        )
        db.add(uni)
        db.flush()  # Obtain uni.id before dependent rows

        stages_completed.append("tenant_record_created")
        logger.info(
            "[Stage 1] tenant_record_created: university_id=%d domain=%s",
            uni.id, uni.domain,
        )

        # ── Stage 2: admin_account_created ───────────────────────────────────
        admin_user = User(
            university_id=uni.id,
            username=pending.admin_username,
            email=pending.admin_email,
            full_name=pending.admin_full_name,
            hashed_password=pending.hashed_password,
            role=UserRole.TENANT_ADMIN,
            is_active=True,
        )
        db.add(admin_user)
        db.flush()

        stages_completed.append("admin_account_created")
        logger.info(
            "[Stage 2] admin_account_created: user=%s university_id=%d",
            admin_user.email, uni.id,
        )

        # ── Stage 3: baseline_seed_applied ───────────────────────────────────
        template_key = getattr(pending, "institution_template_key", None) or "custom"
        seed_tenant_baseline(db, tenant_id=uni.id, plan_tier=plan_tier, template_key=template_key)
        stages_completed.append("baseline_seed_applied")
        logger.info("[Stage 3] baseline_seed_applied: university_id=%d", uni.id)

        # ── Stage 4: notifications_written ───────────────────────────────────
        superadmins = db.query(User).filter(User.role == UserRole.SUPERADMIN).all()
        for sa in superadmins:
            notification = Notification(
                user_id=sa.id,
                title="New Tenant Registered",
                message=(
                    f"{pending.org_name} ({pending.subdomain}) has been verified and provisioned. "
                    f"Admin: {pending.admin_email} | Plan: {plan_tier}"
                ),
                type="info",
                is_read=False,
                created_at=now,
                action_link="/superadmin",
            )
            db.add(notification)

        stages_completed.append("notifications_written")
        logger.info(
            "[Stage 4] notifications_written: notified %d superadmin(s)", len(superadmins)
        )

        # ── Stage 5: usage_baseline_recorded ─────────────────────────────────
        emit_onboarding_events(db, tenant_id=uni.id, plan_tier=plan_tier)
        stages_completed.append("usage_baseline_recorded")
        logger.info("[Stage 5] usage_baseline_recorded: university_id=%d", uni.id)

        # ── Stage 6: provisioning_complete ───────────────────────────────────
        # Generate access token before committing so token creation failure
        # can still trigger rollback and keep provisioning atomic.
        access_token = create_access_token(
            data={"sub": admin_user.username},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        pending.status = "verified"
        db.commit()

        stages_completed.append("provisioning_complete")
        logger.info(
            "[Stage 6] provisioning_complete: university_id=%d domain=%s",
            uni.id, uni.domain,
        )

        return ProvisioningResult(
            access_token=access_token,
            university_id=uni.id,
            stages_completed=stages_completed,
        )

    except Exception as exc:
        _handle_provisioning_failure(db, pending, stages_completed, exc)


def _handle_provisioning_failure(
    db: Session,
    pending: PendingRegistration,
    stages_completed: list,
    exc: Exception,
) -> None:
    """
    Apply rollback policy:
    - Roll back the in-flight transaction so partial tenant rows do not persist.
    - Persist PendingRegistration as failed_provisioning for manual retry.
    - Re-raise as ProvisioningError.
    """
    failed_at_stage = len(stages_completed)
    logger.error(
        "[!] Provisioning failed after stage %d (%s): %s",
        failed_at_stage,
        stages_completed[-1] if stages_completed else "none",
        exc,
        exc_info=True,
    )

    try:
        db.rollback()
    except Exception:
        pass

    try:
        # Persist the terminal failure state so a Superadmin can retry manually.
        pending.status = "failed_provisioning"
        db.add(pending)
        db.commit()
    except Exception:
        db.rollback()

    # ── Alert all SuperAdmins so the failure is visible in the dashboard ──────
    # This runs in a fresh transaction AFTER the rollback so it always persists.
    try:
        superadmins = db.query(User).filter(User.role == UserRole.SUPERADMIN).all()
        for sa in superadmins:
            db.add(Notification(
                user_id=sa.id,
                title="⚠️ Tenant Provisioning Failed",
                message=(
                    f"Registration for '{pending.org_name}' ({pending.subdomain}) failed "
                    f"at stage {failed_at_stage} "
                    f"({'→'.join(stages_completed) if stages_completed else 'pre-provisioning'}). "
                    f"Cause: {exc}. "
                    f"Admin email: {pending.admin_email}. "
                    f"Use the Pending Registrations panel to retry."
                ),
                type="error",
                is_read=False,
                created_at=datetime.now(timezone.utc),
                action_link="/superadmin?tab=registrations",
            ))
        db.commit()
        logger.info(
            "[!] Failure alert notification sent to %d superadmin(s).", len(superadmins)
        )
    except Exception as notify_exc:
        logger.warning("Could not write failure notification: %s", notify_exc)
        try:
            db.rollback()
        except Exception:
            pass

    raise ProvisioningError(
        f"Tenant provisioning failed at stage {failed_at_stage}. "
        f"Completed: {stages_completed}. Cause: {exc}"
    ) from exc
