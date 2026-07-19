from datetime import datetime
from typing import Optional

from celery import shared_task

from ..database import SessionLocal
from ..models import University
from ..services.usage_service import UsageService


@shared_task(bind=True)
def aggregate_usage_monthly_task(self, tenant_id: Optional[int] = None, period: Optional[str] = None):
    db = SessionLocal()
    try:
        service = UsageService(db)
        if tenant_id is not None:
            updated = service.aggregate_monthly(tenant_id=tenant_id, period=period)
            return {"status": "success", "tenant_id": tenant_id, "updated": updated}

        tenant_ids = [row[0] for row in db.query(University.id).all()]
        total_updated = 0
        for tid in tenant_ids:
            total_updated += service.aggregate_monthly(tenant_id=tid, period=period)

        return {"status": "success", "tenant_count": len(tenant_ids), "updated": total_updated}
    except Exception as exc:
        db.rollback()
        return {"status": "error", "message": str(exc)}
    finally:
        db.close()
