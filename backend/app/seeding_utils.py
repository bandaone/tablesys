import logging
from datetime import datetime, timezone, time

from app.database import SessionLocal
from app.models import User, UserRole, PlanQuota, University, AcademicCalendar, ActivityType, School
from app.auth import get_password_hash
from app.config import settings
from app.services.institution_templates import build_policy, get_template_payload
from app.services.usage import create_quota_placeholders as create_tenant_quota_placeholders
from app.services.usage import emit_event

logger = logging.getLogger("app.seeding")

# ─── Plan Quota Defaults ──────────────────────────────────────────────────────
# These are the canonical quota values for this slice.
# Adjust here only — they propagate automatically via create_quota_placeholders().

PLAN_QUOTA_DEFAULTS = [
    # Starter (free)
    {"plan_tier": "starter",      "metric_key": "seats_active",          "limit_quantity": 1000,                "enforcement": "warn"},
    {"plan_tier": "starter",      "metric_key": "timetable_generations", "limit_quantity": 10,                  "enforcement": "block"},
    {"plan_tier": "starter",      "metric_key": "department_count",      "limit_quantity": 15,                  "enforcement": "warn"},
    {"plan_tier": "starter",      "metric_key": "course_count",          "limit_quantity": 150,                 "enforcement": "warn"},
    {"plan_tier": "starter",      "metric_key": "storage_bytes",         "limit_quantity": 5 * 1024 ** 3,      "enforcement": "warn"},
    # Professional (pro)
    {"plan_tier": "professional", "metric_key": "seats_active",          "limit_quantity": 5000,                "enforcement": "warn"},
    {"plan_tier": "professional", "metric_key": "timetable_generations", "limit_quantity": 30,                  "enforcement": "block"},
    {"plan_tier": "professional", "metric_key": "department_count",      "limit_quantity": 50,                  "enforcement": "warn"},
    {"plan_tier": "professional", "metric_key": "course_count",          "limit_quantity": 500,                 "enforcement": "warn"},
    {"plan_tier": "professional", "metric_key": "storage_bytes",         "limit_quantity": 25 * 1024 ** 3,     "enforcement": "warn"},
    # Enterprise
    {"plan_tier": "enterprise",   "metric_key": "seats_active",          "limit_quantity": 50000,               "enforcement": "warn"},
    {"plan_tier": "enterprise",   "metric_key": "timetable_generations", "limit_quantity": 100,                 "enforcement": "block"},
    {"plan_tier": "enterprise",   "metric_key": "department_count",      "limit_quantity": 200,                 "enforcement": "warn"},
    {"plan_tier": "enterprise",   "metric_key": "course_count",          "limit_quantity": 2000,                "enforcement": "warn"},
    {"plan_tier": "enterprise",   "metric_key": "storage_bytes",         "limit_quantity": 100 * 1024 ** 3,    "enforcement": "warn"},
]


# ─── Platform-Level Seed ──────────────────────────────────────────────────────

def seed_superadmin(db) -> None:
    """Seed the platform superadmin from environment variables. Idempotent."""
    if not (settings.SUPERADMIN_USERNAME and settings.SUPERADMIN_EMAIL and settings.SUPERADMIN_PASSWORD):
        return

    existing = db.query(User).filter(User.role == UserRole.SUPERADMIN).first()
    if existing:
        logger.info("[*] SUPERADMIN already exists — skipping seed.")
        return

    logger.info("[*] No SUPERADMIN found. Creating from environment variables...")
    superadmin = User(
        username=settings.SUPERADMIN_USERNAME,
        email=settings.SUPERADMIN_EMAIL,
        full_name="Platform Administrator",
        role=UserRole.SUPERADMIN,
        hashed_password=get_password_hash(settings.SUPERADMIN_PASSWORD),
        is_active=True,
        university_id=None,
    )
    db.add(superadmin)
    db.commit()
    logger.info("[+] SUPERADMIN created: %s", settings.SUPERADMIN_USERNAME)


def create_quota_placeholders(db, commit: bool = True) -> int:
    """
    Upsert canonical plan quota rows for starter, professional, and enterprise.
    Idempotent — skips rows that already exist.
    Returns the number of rows created.

    Parameters
    ----------
    commit : bool
        If True (default), commits the session after writing rows — use this
        for the platform-level startup seed.
        If False, only flushes — use this when called mid-transaction so the
        caller owns the commit boundary.
    """
    created = 0
    for quota_def in PLAN_QUOTA_DEFAULTS:
        existing = (
            db.query(PlanQuota)
            .filter(
                PlanQuota.plan_tier == quota_def["plan_tier"],
                PlanQuota.metric_key == quota_def["metric_key"],
            )
            .first()
        )
        if existing:
            continue
        db.add(PlanQuota(**quota_def))
        created += 1

    if created:
        if commit:
            db.commit()
        else:
            db.flush()
        logger.info("[+] Created %d quota placeholder rows.", created)
    else:
        logger.info("[*] Quota placeholders already present — skipping.")
    return created


def ensure_platform_quotas_seeded(db) -> None:
    """
    Pre-flight guard: ensure PlanQuota rows exist before per-tenant provisioning.

    This must be called BEFORE opening a per-tenant provisioning transaction.
    If quota rows are missing (e.g. fresh DB, test environment), this seeds them
    in a committed transaction so they are visible to subsequent queries.

    Raises RuntimeError if seeding fails, which causes provisioning to abort
    with a clear error before any tenant state is written.
    """
    missing = (
        db.query(PlanQuota)
        .filter(PlanQuota.plan_tier == "starter", PlanQuota.metric_key == "seats_active")
        .first()
    )
    if not missing:
        logger.warning("[!] Platform quotas not seeded — seeding now before provisioning.")
        try:
            create_quota_placeholders(db, commit=True)
        except Exception as exc:
            raise RuntimeError(f"Failed to seed platform quotas: {exc}") from exc
    else:
        logger.debug("[*] Platform quotas confirmed present.")


# ─── Tenant Bootstrap Helpers ─────────────────────────────────────────────────

def create_default_calendar(db, tenant_id: int) -> None:
    """
    Create the approved default calendar scaffold for a tenant.
    """
    existing_default = (
        db.query(AcademicCalendar)
        .filter(
            AcademicCalendar.university_id == tenant_id,
            AcademicCalendar.is_default == True,
        )
        .first()
    )
    if existing_default:
        logger.info("[*] Default calendar already exists for tenant %d", tenant_id)
        return

    db.add(
        AcademicCalendar(
            university_id=tenant_id,
            name="Standard Academic Calendar",
            days_of_week=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            start_time=time(7, 0),
            end_time=time(18, 0),
            slot_duration_minutes=60,
            is_default=True,
        )
    )
    db.flush()
    logger.info("[+] Default calendar created for tenant %d", tenant_id)


def apply_branding_defaults(db, tenant_id: int) -> None:
    """
    Apply default branding values (colors, logo) to a university record.
    Uses the approved defaults from the integration contract.
    """
    uni = db.query(University).filter(University.id == tenant_id).first()
    if not uni:
        logger.warning("[!] apply_branding_defaults: university %d not found", tenant_id)
        return

    if not getattr(uni, "primary_color", None):
        uni.primary_color = "#1976d2"

    if not getattr(uni, "secondary_color", None):
        uni.secondary_color = "#9c27b0"

    # Logo defaults to None — tenants upload their own logo post-onboarding.
    if not getattr(uni, "timezone", None):
        uni.timezone = "Africa/Lusaka"

    db.flush()
    logger.info("[+] Branding defaults applied for tenant %d", tenant_id)


def seed_default_activity_types(db, tenant_id: int, template_key: str = "custom") -> None:
    existing = (
        db.query(ActivityType)
        .filter(ActivityType.university_id == tenant_id)
        .count()
    )
    if existing:
        logger.info("[*] Activity types already exist for tenant %d", tenant_id)
        return

    template = get_template_payload(template_key)
    for item in template.get("activity_types", []):
        db.add(
            ActivityType(
                university_id=tenant_id,
                key=item["key"],
                display_name=item["display_name"],
                color=item.get("color", "#3B82F6"),
                default_duration_periods=item.get("default_duration_periods", 1),
                default_frequency_per_week=item.get("default_frequency_per_week", 1),
                requires_subgroups=item.get("requires_subgroups", False),
                resource_tags_required=item.get("resource_tags_required"),
                counts_toward_contact_hours=item.get("counts_toward_contact_hours", True),
                is_active=True,
            )
        )
    db.flush()
    logger.info("[+] Default activity types seeded for tenant %d", tenant_id)


def apply_scheduling_policy_defaults(db, tenant_id: int, template_key: str = "custom") -> None:
    uni = db.query(University).filter(University.id == tenant_id).first()
    if not uni:
        logger.warning("[!] apply_scheduling_policy_defaults: university %d not found", tenant_id)
        return

    if not uni.scheduling_policy:
        uni.scheduling_policy = build_policy(template_key)
    db.flush()
    logger.info("[+] Scheduling policy defaults applied for tenant %d", tenant_id)


def seed_default_school(db, tenant_id: int, template_key: str = "custom") -> None:
    template = get_template_payload(template_key)
    if not template.get("auto_seed_single_school"):
        return
    existing = db.query(School).filter(School.university_id == tenant_id).count()
    if existing:
        logger.info("[*] School rows already exist for tenant %d", tenant_id)
        return
    db.add(
        School(
            university_id=tenant_id,
            name=template.get("default_school_name") or "Main School",
            code=template.get("default_school_code") or "MAIN",
            description=f"Auto-seeded from {template.get('label', 'institution')} template",
            is_active=True,
        )
    )
    db.flush()
    logger.info("[+] Default school seeded for tenant %d", tenant_id)


def emit_onboarding_events(db, tenant_id: int, plan_tier: str) -> None:
    """
    Emit the Stage 5 onboarding usage events.
    Per the integration contract, these emit ONLY after earlier stages succeed.
    """
    event_metadata = {"plan_tier": plan_tier, "stage": "usage_baseline_recorded"}

    emit_event(
        db,
        tenant_id=tenant_id,
        metric_key="seats_active",
        quantity=1,
        source="provisioning",
        metadata=event_metadata,
    )
    emit_event(
        db,
        tenant_id=tenant_id,
        metric_key="department_count",
        quantity=0,
        source="provisioning",
        metadata=event_metadata,
    )
    emit_event(
        db,
        tenant_id=tenant_id,
        metric_key="course_count",
        quantity=0,
        source="provisioning",
        metadata=event_metadata,
    )
    emit_event(
        db,
        tenant_id=tenant_id,
        metric_key="storage_bytes",
        quantity=0,
        source="provisioning",
        metadata=event_metadata,
    )

    logger.info("[+] Onboarding usage events emitted for tenant %d (plan: %s)", tenant_id, plan_tier)


def seed_tenant_baseline(db, tenant_id: int, plan_tier: str, template_key: str = "custom") -> None:
    """
    Apply the minimum tenant bootstrap package (Stage 3).

    Assumes platform-level PlanQuota rows already exist (seeded at startup or
    via ensure_platform_quotas_seeded() before the provisioning transaction).
    Does NOT commit — the provisioning transaction owns the commit boundary.

    Stages applied:
    - Default calendar scaffold
    - Branding defaults
    - Scheduling policy + activity types (from template)
    - Default school (if template requires it)
    - Tenant-level UsageMonthlySummary placeholders (requires PlanQuota rows)
    """
    logger.info("[*] Applying tenant baseline seed for tenant %d (plan: %s)", tenant_id, plan_tier)
    create_default_calendar(db, tenant_id)
    apply_branding_defaults(db, tenant_id)
    apply_scheduling_policy_defaults(db, tenant_id, template_key=template_key)
    seed_default_activity_types(db, tenant_id, template_key=template_key)
    seed_default_school(db, tenant_id, template_key=template_key)
    create_tenant_quota_placeholders(db, tenant_id=tenant_id, plan_tier=plan_tier)
    logger.info("[+] Tenant baseline seed complete for tenant %d", tenant_id)


def backfill_universal_scheduling_defaults(
    db,
    template_key: str = "custom",
    seed_activity_types: bool = False,
) -> int:
    """
    Idempotently backfill universal scheduling defaults for pre-migration tenants.
    Returns the number of tenant records touched.
    """
    touched = 0
    universities = db.query(University).all()
    for university in universities:
        changed = False
        if not university.scheduling_policy:
            university.scheduling_policy = build_policy(template_key)
            changed = True
        if seed_activity_types:
            before = (
                db.query(ActivityType)
                .filter(ActivityType.university_id == university.id)
                .count()
            )
            if before == 0:
                seed_default_activity_types(db, university.id, template_key=template_key)
                changed = True
        if changed:
            touched += 1
    if touched:
        db.flush()
    logger.info("[+] Backfilled universal scheduling defaults for %d tenant(s)", touched)
    return touched


# ─── Startup Entry Point ──────────────────────────────────────────────────────

def run_schema_migrations(db):
    """Idempotent schema patches that run on every startup. Safe to re-run."""
    try:
        db.execute(
            "ALTER TABLE lecturers ADD COLUMN IF NOT EXISTS welcome_email_sent BOOLEAN DEFAULT FALSE;"
        )
        db.commit()
        logger.info("[+] Schema migration: lecturers.welcome_email_sent column ensured.")
    except Exception as e:
        logger.warning("Schema migration skipped or failed (may already exist): %s", e)
        db.rollback()


def seed_database_at_startup():
    db = SessionLocal()
    try:
        run_schema_migrations(db)
        seed_superadmin(db)
        create_quota_placeholders(db)
        logger.info("[+] Automatic seeding completed successfully.")
    except Exception as e:
        logger.error("[-] Error during automatic seeding: %s", e)
        db.rollback()
    finally:
        db.close()
