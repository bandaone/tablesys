from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..services.usage_service import UsageService


BLOCK_ONLY_METRICS = {"timetable_generations"}


def enforce_generation_quota(
    db: Session,
    tenant_id: Optional[int],
    period: Optional[str] = None,
) -> Optional[dict]:
    if tenant_id is None:
        return None

    service = UsageService(db)
    status_info = service.get_quota_status(
        tenant_id=tenant_id,
        metric_key="timetable_generations",
        period=period,
    )
    if not status_info:
        return None

    total = status_info["total"]
    limit_value = status_info["limit"]
    if limit_value > 0 and total > limit_value and status_info["metric_key"] in BLOCK_ONLY_METRICS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Generation quota exceeded",
                "metric_key": status_info["metric_key"],
                "total": total,
                "limit": limit_value,
                "status": "blocked",
                "percent": status_info["percent"],
            },
        )

    return status_info
