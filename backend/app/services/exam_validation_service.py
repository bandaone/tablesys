from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time
from typing import Dict, List, Optional

from sqlalchemy.orm import Session, selectinload

from ..models import (
    ExamPaper,
    ExamPeriod,
    ExamSeatingProfile,
    ExamSessionWindow,
    ExamSlot,
    ExamSlotRoom,
    Room,
    RoomBooking,
    StudentGroup,
)
from .exam_seating_service import ExamSeatingService


class ExamValidationService:
    """Validation helpers for the coordinator-managed exam engine."""

    def __init__(self, db: Session):
        self.db = db
        self.seating = ExamSeatingService()

    @staticmethod
    def _overlaps(start_a: time, end_a: time, start_b: time, end_b: time) -> bool:
        return start_a < end_b and end_a > start_b

    @staticmethod
    def _combine(dt: date, tm: time) -> datetime:
        return datetime.combine(dt, tm)

    def validate_period(self, period: ExamPeriod) -> List[Dict]:
        errors: List[Dict] = []
        if period.start_date > period.end_date:
            errors.append({"field": "date_range", "message": "start_date must be on or before end_date", "severity": "error"})
        return errors

    def validate_session_window(self, session_window: ExamSessionWindow) -> List[Dict]:
        errors: List[Dict] = []
        if session_window.start_time >= session_window.end_time:
            errors.append({"field": "time_window", "message": "Session window start_time must be earlier than end_time", "severity": "error"})
        return errors

    def validate_paper(self, period: ExamPeriod, paper: ExamPaper) -> List[Dict]:
        errors: List[Dict] = []
        group_ids = [int(group_id) for group_id in (paper.group_ids or [])]
        if not group_ids:
            errors.append({"field": "group_ids", "message": "Exam paper must target at least one student group", "severity": "error"})
            return errors

        groups = self.db.query(StudentGroup).filter(StudentGroup.id.in_(group_ids)).all()
        found_ids = {group.id for group in groups}
        missing = [group_id for group_id in group_ids if group_id not in found_ids]
        if missing:
            errors.append({"field": "group_ids", "message": f"Unknown student group ids: {missing}", "severity": "error"})

        if paper.duration_minutes <= 0:
            errors.append({"field": "duration_minutes", "message": "Exam duration must be greater than zero", "severity": "error"})

        candidate_count = paper.candidate_count or sum(int(group.size or 0) for group in groups)
        if candidate_count <= 0:
            errors.append({"field": "candidate_count", "message": "Exam paper must have a positive candidate count", "severity": "error"})

        preferred_profile_id = getattr(paper, "preferred_seating_profile_id", None)
        if preferred_profile_id:
            profile = self.db.query(ExamSeatingProfile).filter(ExamSeatingProfile.id == preferred_profile_id).first()
            if not profile or profile.university_id != period.university_id:
                errors.append({"field": "preferred_seating_profile_id", "message": "Preferred seating profile is invalid for this university", "severity": "error"})

        return errors

    def validate_slot(
        self,
        *,
        period: ExamPeriod,
        paper: ExamPaper,
        exam_date: date,
        start_time: time,
        end_time: time,
        room_allocations: List[Dict],
        slot_id: Optional[int] = None,
    ) -> List[Dict]:
        errors: List[Dict] = []

        if exam_date < period.start_date or exam_date > period.end_date:
            errors.append({"field": "exam_date", "message": "Exam date falls outside the configured exam period", "severity": "error"})
            return errors

        group_ids = [int(group_id) for group_id in (paper.group_ids or [])]
        settings = dict(period.constraint_settings or {})
        min_gap_hours = int(settings.get("min_gap_hours", 24) or 24)
        hard_max_papers_per_day = int(settings.get("hard_max_papers_per_day", 2) or 2)

        existing_slots = (
            self.db.query(ExamSlot)
            .options(
                selectinload(ExamSlot.paper),
                selectinload(ExamSlot.room_allocations),
            )
            .filter(ExamSlot.exam_period_id == period.id)
            .all()
        )

        existing_rooms_by_slot = {
            slot.id: {allocation.room_id for allocation in slot.room_allocations}
            for slot in existing_slots
        }

        requested_room_ids = {int(item["room_id"]) for item in room_allocations}

        for slot in existing_slots:
            if slot_id and slot.id == slot_id:
                continue
            if slot.exam_date != exam_date:
                continue
            if not self._overlaps(start_time, end_time, slot.start_time, slot.end_time):
                continue

            overlapping_group_ids = set(group_ids).intersection(set(slot.paper.group_ids or []))
            if overlapping_group_ids:
                errors.append({"field": "group_conflict", "message": f"Groups {sorted(overlapping_group_ids)} already have an overlapping exam", "severity": "error"})

            overlapping_rooms = requested_room_ids.intersection(existing_rooms_by_slot.get(slot.id, set()))
            if overlapping_rooms:
                errors.append({"field": "room_conflict", "message": f"Rooms {sorted(overlapping_rooms)} already have an overlapping exam booking", "severity": "error"})

        if requested_room_ids:
            bookings = (
                self.db.query(RoomBooking)
                .filter(
                    RoomBooking.room_id.in_(requested_room_ids),
                    RoomBooking.booking_date == exam_date,
                )
                .all()
            )
            for booking in bookings:
                if self._overlaps(start_time, end_time, booking.start_time, booking.end_time):
                    errors.append({"field": "room_booking_conflict", "message": f"Room {booking.room_id} already has a protected booking during this time", "severity": "error"})

        group_daily_counts: Dict[int, int] = defaultdict(int)
        for slot in existing_slots:
            if slot_id and slot.id == slot_id:
                continue
            slot_groups = [int(group_id) for group_id in (slot.paper.group_ids or [])]
            if slot.exam_date == exam_date:
                for group_id in set(group_ids).intersection(slot_groups):
                    group_daily_counts[group_id] += 1

            if not set(group_ids).intersection(slot_groups):
                continue

            gap_hours = abs(
                (self._combine(exam_date, start_time) - self._combine(slot.exam_date, slot.start_time)).total_seconds()
            ) / 3600
            if gap_hours < min_gap_hours:
                errors.append({"field": "spacing", "message": f"Minimum gap of {min_gap_hours} hours is violated for one or more groups", "severity": "error"})

        for group_id, existing_count in group_daily_counts.items():
            if existing_count + 1 > hard_max_papers_per_day:
                errors.append({"field": "daily_load", "message": f"Group {group_id} exceeds the hard cap of {hard_max_papers_per_day} papers in one day", "severity": "error"})

        total_capacity = 0
        rooms = self.db.query(Room).filter(Room.id.in_(requested_room_ids)).all() if requested_room_ids else []
        room_map = {room.id: room for room in rooms}
        for allocation in room_allocations:
            room = room_map.get(int(allocation["room_id"]))
            if not room:
                errors.append({"field": "room_id", "message": f"Room {allocation['room_id']} not found", "severity": "error"})
                continue
            profile = None
            profile_id = allocation.get("seating_profile_id")
            if profile_id:
                profile = self.db.query(ExamSeatingProfile).filter(ExamSeatingProfile.id == profile_id).first()
            if not self.seating.room_supports_profile(room, profile):
                errors.append({"field": "room_profile", "message": f"Room {room.name} cannot support the selected seating profile", "severity": "error"})
                continue
            effective_capacity = self.seating.effective_capacity(room, profile)
            if int(allocation["allocated_capacity"]) > effective_capacity:
                errors.append({"field": "allocated_capacity", "message": f"Room {room.name} exceeds its effective exam capacity", "severity": "error"})
                continue
            total_capacity += int(allocation["allocated_capacity"])

        if total_capacity < (paper.candidate_count or 0):
            errors.append({"field": "capacity", "message": "Combined room allocations do not cover the candidate count", "severity": "error"})

        return errors
