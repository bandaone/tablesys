from __future__ import annotations

from datetime import date, time
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import ExamPeriod, ExamSlot, ExamSlotRoom


class ExamModeService:
    """Shared helpers for enforcing institution-wide exam mode behavior."""

    def __init__(self, db: Session):
        self.db = db

    def get_published_period_for_date(
        self,
        target_date: date,
        *,
        university_id: Optional[int] = None,
    ) -> Optional[ExamPeriod]:
        query = self.db.query(ExamPeriod).filter(
            ExamPeriod.is_published.is_(True),
            ExamPeriod.start_date <= target_date,
            ExamPeriod.end_date >= target_date,
        )
        if university_id is not None:
            query = query.filter(ExamPeriod.university_id == university_id)
        return query.order_by(ExamPeriod.start_date.asc(), ExamPeriod.id.asc()).first()

    def room_reserved_for_exam(
        self,
        *,
        room_id: int,
        target_date: date,
        start_time: time,
        end_time: time,
    ) -> bool:
        return (
            self.db.query(ExamSlotRoom)
            .join(ExamSlot, ExamSlotRoom.exam_slot_id == ExamSlot.id)
            .join(ExamPeriod, ExamSlot.exam_period_id == ExamPeriod.id)
            .filter(
                ExamSlotRoom.room_id == room_id,
                ExamSlot.exam_date == target_date,
                ExamSlot.start_time < end_time,
                ExamSlot.end_time > start_time,
                ExamPeriod.is_published.is_(True),
            )
            .first()
            is not None
        )

    def ensure_non_exam_activity_allowed(
        self,
        *,
        target_date: date,
        university_id: Optional[int] = None,
        activity_label: str = "This activity",
    ) -> None:
        period = self.get_published_period_for_date(target_date, university_id=university_id)
        if not period:
            return
        raise HTTPException(
            status_code=409,
            detail=(
                f"{activity_label} is blocked while exam mode is active for "
                f"'{period.name}' ({period.start_date} to {period.end_date})."
            ),
        )
