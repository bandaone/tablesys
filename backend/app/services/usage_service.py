from datetime import datetime
import calendar
from typing import Iterable, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import UsageEvent, UsageMonthlySummary, PlanQuota, University


METRIC_KEYS = [
    "seats_active",
    "timetable_generations",
    "department_count",
    "course_count",
    "storage_bytes",
]

PLAN_TIER_ALIASES = {
    "free": "starter",
    "starter": "starter",
    "pro": "professional",
    "professional": "professional",
    "enterprise": "enterprise",
}


def resolve_period_bounds(period: Optional[str]) -> Tuple[datetime, datetime]:
    if period:
        year, month = map(int, period.split("-"))
    else:
        now = datetime.utcnow()
        year = now.year
        month = now.month

    start = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59)
    return start, end


class UsageService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_quota_placeholders(
        self,
        tenant_id: int,
        plan_tier: str,
        period: Optional[str] = None,
        commit: bool = False,
    ) -> int:
        normalized_tier = PLAN_TIER_ALIASES.get(plan_tier, plan_tier)
        period_start, period_end = resolve_period_bounds(period)
        created_count = 0

        for metric_key in METRIC_KEYS:
            quota = self.get_quota(normalized_tier, metric_key)
            if not quota:
                raise ValueError(
                    f"Missing plan quota for plan_tier='{normalized_tier}' metric_key='{metric_key}'"
                )

            summary = (
                self.db.query(UsageMonthlySummary)
                .filter(UsageMonthlySummary.tenant_id == tenant_id)
                .filter(UsageMonthlySummary.period_start == period_start)
                .filter(UsageMonthlySummary.metric_key == metric_key)
                .first()
            )
            if summary:
                summary.period_end = period_end
                continue

            self.db.add(
                UsageMonthlySummary(
                    tenant_id=tenant_id,
                    period_start=period_start,
                    period_end=period_end,
                    metric_key=metric_key,
                    total_quantity=0,
                )
            )
            created_count += 1

        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return created_count

    def aggregate_monthly(
        self,
        tenant_id: int,
        period: Optional[str] = None,
        metric_keys: Optional[Iterable[str]] = None,
    ) -> int:
        period_start, period_end = resolve_period_bounds(period)
        keys = list(metric_keys) if metric_keys else METRIC_KEYS
        updated_count = 0

        for metric_key in keys:
            total = self.db.query(func.coalesce(func.sum(UsageEvent.quantity), 0))\
                .filter(UsageEvent.tenant_id == tenant_id)\
                .filter(UsageEvent.metric_key == metric_key)\
                .filter(UsageEvent.occurred_at >= period_start)\
                .filter(UsageEvent.occurred_at <= period_end)\
                .scalar()

            summary = self.db.query(UsageMonthlySummary)\
                .filter(UsageMonthlySummary.tenant_id == tenant_id)\
                .filter(UsageMonthlySummary.period_start == period_start)\
                .filter(UsageMonthlySummary.metric_key == metric_key)\
                .first()

            if summary:
                summary.total_quantity = int(total or 0)
                summary.period_end = period_end
            else:
                summary = UsageMonthlySummary(
                    tenant_id=tenant_id,
                    period_start=period_start,
                    period_end=period_end,
                    metric_key=metric_key,
                    total_quantity=int(total or 0),
                )
                self.db.add(summary)

            updated_count += 1

        self.db.commit()
        return updated_count

    def resolve_plan_tier(self, tenant_id: int) -> str:
        plan_tier = "starter"
        university = self.db.query(University).filter(University.id == tenant_id).first()
        if university and university.plan_tier:
            plan_tier = PLAN_TIER_ALIASES.get(university.plan_tier, university.plan_tier)
        return plan_tier

    def get_quota(self, plan_tier: str, metric_key: str) -> Optional[PlanQuota]:
        return (
            self.db.query(PlanQuota)
            .filter(PlanQuota.plan_tier == plan_tier)
            .filter(PlanQuota.metric_key == metric_key)
            .first()
        )

    def get_usage_total(self, tenant_id: int, metric_key: str, period: Optional[str] = None) -> int:
        period_start, _ = resolve_period_bounds(period)
        summary = (
            self.db.query(UsageMonthlySummary)
            .filter(UsageMonthlySummary.tenant_id == tenant_id)
            .filter(UsageMonthlySummary.period_start == period_start)
            .filter(UsageMonthlySummary.metric_key == metric_key)
            .first()
        )
        if not summary:
            self.aggregate_monthly(tenant_id=tenant_id, period=period, metric_keys=[metric_key])
            summary = (
                self.db.query(UsageMonthlySummary)
                .filter(UsageMonthlySummary.tenant_id == tenant_id)
                .filter(UsageMonthlySummary.period_start == period_start)
                .filter(UsageMonthlySummary.metric_key == metric_key)
                .first()
            )
        return int(summary.total_quantity) if summary else 0

    def get_quota_status(self, tenant_id: int, metric_key: str, period: Optional[str] = None) -> Optional[dict]:
        plan_tier = self.resolve_plan_tier(tenant_id)
        quota = self.get_quota(plan_tier, metric_key)
        if not quota:
            return None

        total = self.get_usage_total(tenant_id, metric_key, period)
        limit_value = int(quota.limit_quantity)
        percent = round((total / limit_value) * 100, 2) if limit_value > 0 else 0

        status = "ok"
        if percent >= 100:
            status = "hard_warning"
        elif percent >= 80:
            status = "warning"

        return {
            "plan_tier": plan_tier,
            "metric_key": metric_key,
            "total": total,
            "limit": limit_value,
            "percent": percent,
            "status": status,
        }


# ─── Internal event emitter (no HTTP overhead) ───────────────────────────────
# Used by provisioning and background jobs to record usage events directly.

def emit_event(
    db: Session,
    tenant_id: int,
    metric_key: str,
    quantity: int = 1,
    source: str = "provisioning",
    metadata: Optional[dict] = None,
) -> UsageEvent:
    """
    Write a UsageEvent row directly to the database.

    This is the internal service contract specified by the integration document.
    Provisioning code and background tasks should call this instead of the
    HTTP /api/v1/usage/events endpoint to avoid circular request overhead.
    """
    from datetime import datetime, timezone

    event = UsageEvent(
        tenant_id=tenant_id,
        metric_key=metric_key,
        quantity=quantity,
        occurred_at=datetime.now(timezone.utc),
        source=source,
        metadata_json=metadata or {},
    )
    db.add(event)
    # Deliberately not committing here — caller owns the transaction.
    return event
