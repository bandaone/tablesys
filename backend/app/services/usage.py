from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..models import UsageEvent
from .usage_service import UsageService


def emit_event(
    db: Session,
    tenant_id: int,
    metric_key: str,
    quantity: int,
    source: str = "provisioning",
    metadata: Optional[dict] = None,
    occurred_at: Optional[datetime] = None,
    commit: bool = False,
) -> UsageEvent:
    event = UsageEvent(
        tenant_id=tenant_id,
        metric_key=metric_key,
        quantity=quantity,
        occurred_at=occurred_at or datetime.utcnow(),
        source=source,
        metadata_json=metadata,
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    else:
        db.flush()
    return event


def create_quota_placeholders(
    db: Session,
    tenant_id: int,
    plan_tier: str,
    period: Optional[str] = None,
    commit: bool = False,
) -> int:
    service = UsageService(db)
    return service.ensure_quota_placeholders(
        tenant_id=tenant_id,
        plan_tier=plan_tier,
        period=period,
        commit=commit,
    )
