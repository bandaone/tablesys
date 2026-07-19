"""
Alerts Router — CRUD and on-demand trigger for PlatformAlert records.
All endpoints require SUPERADMIN role.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from ..database import get_db
from ..auth import get_current_superadmin
from ..models import PlatformAlert, User
from ..services.alert_engine import AlertEngine

router = APIRouter(prefix="/api/v1/superadmin/alerts", tags=["alerts"])


# ── Schemas ────────────────────────────────────────────────────────────────────
class AlertResponse(BaseModel):
    id: int
    severity: str
    category: str
    title: str
    detail: Optional[str]
    tenant_name: Optional[str]
    tenant_id: Optional[int]
    triggered_at: str
    resolved_at: Optional[str]
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[str]
    alert_key: str
    auto_resolve: bool

    class Config:
        from_attributes = True


def _serialize(alert: PlatformAlert) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        severity=alert.severity,
        category=alert.category,
        title=alert.title,
        detail=alert.detail,
        tenant_name=alert.tenant_name,
        tenant_id=alert.tenant_id,
        triggered_at=alert.triggered_at.isoformat(),
        resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        alert_key=alert.alert_key,
        auto_resolve=bool(alert.auto_resolve),
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.get("/", response_model=List[AlertResponse])
def get_active_alerts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """Return all unresolved platform alerts, ordered by severity then time."""
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts = (
        db.query(PlatformAlert)
        .filter(PlatformAlert.resolved_at.is_(None))
        .order_by(PlatformAlert.triggered_at.desc())
        .all()
    )
    alerts.sort(key=lambda a: (severity_order.get(a.severity, 9), a.triggered_at.isoformat()))
    return [_serialize(a) for a in alerts]


@router.get("/history", response_model=List[AlertResponse])
def get_alert_history(
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """Return resolved alerts, most recent first."""
    alerts = (
        db.query(PlatformAlert)
        .filter(PlatformAlert.resolved_at.isnot(None))
        .order_by(PlatformAlert.resolved_at.desc())
        .limit(min(limit, 500))
        .all()
    )
    return [_serialize(a) for a in alerts]


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Mark an alert as acknowledged. Does not resolve it."""
    alert = db.query(PlatformAlert).filter(PlatformAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    alert.acknowledged_by = current_user.email
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return _serialize(alert)


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """Manually resolve an alert (for non-auto-resolve alerts like security events)."""
    alert = db.query(PlatformAlert).filter(PlatformAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    alert.resolved_at = datetime.now(timezone.utc)
    if not alert.acknowledged_by:
        alert.acknowledged_by = current_user.email
        alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return _serialize(alert)


@router.post("/run-check", response_model=List[AlertResponse])
def trigger_alert_check(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superadmin),
):
    """Manually trigger the AlertEngine check cycle. Returns newly fired alerts."""
    engine = AlertEngine(db)
    fired = engine.run()
    return [_serialize(a) for a in fired]
