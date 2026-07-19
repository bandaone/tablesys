"""
Conflict Detection Utility

Detects scheduling conflicts in timetables:
- Lecturer double-booked (same lecturer, overlapping time slots)
- Room double-booked (same room, overlapping time slots)
- Group double-booked (same student group, overlapping time slots)

Provides structured conflict data for API responses and UI warnings.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import time
from typing import Any, Dict, List, Set, Tuple

from sqlalchemy.orm import Session

from ..models import (
    Course,
    ExamPeriod,
    ExamSlot,
    ExamSlotRoom,
    Lecturer,
    Room,
    StudentGroup,
    TimetableSlot,
    RoomBooking,
    Timetable
)
from .transit import DEFAULT_TRANSIT_MINUTES, insufficient_transit_time, times_overlap


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ConflictType = str  # "lecturer" | "room" | "group"

class Conflict:
    """Represents a scheduling conflict."""
    
    def __init__(
        self,
        conflict_type: ConflictType,
        slot_ids: List[int],
        resource_id: int,
        resource_name: str,
        day: int,
        time_range: Tuple[time, time],
    ):
        self.conflict_type = conflict_type
        self.slot_ids = slot_ids
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.day = day
        self.time_range = time_range
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.conflict_type,
            "severity": "high" if len(self.slot_ids) > 2 else "medium",
            "slot_ids": self.slot_ids,
            "resource": {
                "id": self.resource_id,
                "name": self.resource_name,
                "type": self.conflict_type,
            },
            "day_of_week": self.day,
            "start_time": self.time_range[0].strftime("%H:%M"),
            "end_time": self.time_range[1].strftime("%H:%M"),
            "description": self._generate_description(),
        }
    
    def _generate_description(self) -> str:
        """Generate human-readable conflict description."""
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_name = days[self.day] if 0 <= self.day < len(days) else f"Day {self.day}"
        
        start = self.time_range[0].strftime("%H:%M")
        end = self.time_range[1].strftime("%H:%M")
        
        if self.conflict_type.endswith("_transit"):
            resource_type = self.conflict_type.removesuffix("_transit").capitalize()
            return (
                f"{resource_type} '{self.resource_name}' has less than {DEFAULT_TRANSIT_MINUTES} minutes "
                f"to move between different rooms on {day_name} ({start}-{end})"
            )

        resource_type = self.conflict_type.capitalize()
        
        return (
            f"{resource_type} '{self.resource_name}' is double-booked on "
            f"{day_name} at {start}-{end} ({len(self.slot_ids)} conflicting slots)"
        )


# ---------------------------------------------------------------------------
# Conflict Detector
# ---------------------------------------------------------------------------

class ConflictDetector:
    """Detects scheduling conflicts in a timetable."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def detect_all_conflicts(self, timetable_id: int) -> List[Conflict]:
        """
        Detect all conflicts in a timetable.
        
        Returns:
            List of Conflict objects representing all detected scheduling conflicts.
        """
        slots = (
            self.db.query(TimetableSlot)
            .filter(TimetableSlot.timetable_id == timetable_id)
            .all()
        )
        
        conflicts = []
        conflicts.extend(self._detect_lecturer_conflicts(slots))
        conflicts.extend(self._detect_room_conflicts(slots))
        conflicts.extend(self._detect_group_conflicts(slots))
        
        return conflicts

    @staticmethod
    def _slot_group_ids(slot: TimetableSlot) -> Set[int]:
        """Return every group explicitly covered by a shared timetable slot."""
        return {slot.group_id, *(slot.shared_group_ids or [])}

    def _group_lineage_ids(self, group_id: int) -> Set[int]:
        """Include parents so a stream cannot be sent to another class mid-cohort."""
        ids: Set[int] = set()
        current_id = group_id
        for _ in range(10):
            if current_id is None or current_id in ids:
                break
            ids.add(current_id)
            group = self.db.get(StudentGroup, current_id)
            current_id = group.parent_group_id if group else None
        return ids

    def _slots_share_audience(self, first: TimetableSlot, second: TimetableSlot) -> bool:
        first_lineage: Set[int] = set()
        second_lineage: Set[int] = set()
        for group_id in self._slot_group_ids(first):
            first_lineage.update(self._group_lineage_ids(group_id))
        for group_id in self._slot_group_ids(second):
            second_lineage.update(self._group_lineage_ids(group_id))
        return bool(first_lineage.intersection(second_lineage))
    
    def _detect_lecturer_conflicts(self, slots: List[TimetableSlot]) -> List[Conflict]:
        """Detect overlapping or impossible cross-room lecturer movements."""
        conflicts = []
        by_lecturer: Dict[Tuple[int, int], List[TimetableSlot]] = defaultdict(list)
        for slot in slots:
            if slot.lecturer_id is not None:
                by_lecturer[(slot.lecturer_id, slot.day_of_week)].append(slot)
        for (lecturer_id, day), schedule in by_lecturer.items():
            lecturer = self.db.get(Lecturer, lecturer_id)
            lecturer_name = lecturer.full_name if lecturer else f"Lecturer #{lecturer_id}"
            for index, first in enumerate(schedule):
                for second in schedule[index + 1:]:
                    if times_overlap(first.start_time, first.end_time, second.start_time, second.end_time):
                        conflict_type, time_range = "lecturer", (max(first.start_time, second.start_time), min(first.end_time, second.end_time))
                    elif insufficient_transit_time(first.start_time, first.end_time, first.room_id, second.start_time, second.end_time, second.room_id):
                        conflict_type, time_range = "lecturer_transit", (min(first.start_time, second.start_time), max(first.end_time, second.end_time))
                    else:
                        continue
                    conflicts.append(Conflict(conflict_type, [first.id, second.id], lecturer_id, lecturer_name, day, time_range))
        
        return conflicts
    
    def _detect_room_conflicts(self, slots: List[TimetableSlot]) -> List[Conflict]:
        """Detect room double-booking. Back-to-back use of one room is allowed."""
        conflicts = []
        by_room: Dict[Tuple[int, int], List[TimetableSlot]] = defaultdict(list)
        for slot in slots:
            if slot.room_id is not None:
                by_room[(slot.room_id, slot.day_of_week)].append(slot)
        for (room_id, day), schedule in by_room.items():
            room = self.db.get(Room, room_id)
            room_name = room.name if room else f"Room #{room_id}"
            for index, first in enumerate(schedule):
                for second in schedule[index + 1:]:
                    if times_overlap(first.start_time, first.end_time, second.start_time, second.end_time):
                        conflicts.append(Conflict("room", [first.id, second.id], room_id, room_name, day,
                                                  (max(first.start_time, second.start_time), min(first.end_time, second.end_time))))
        
        return conflicts
    
    def _detect_group_conflicts(self, slots: List[TimetableSlot]) -> List[Conflict]:
        """Detect student clashes and too-short movements between different rooms."""
        conflicts = []
        by_day: Dict[int, List[TimetableSlot]] = defaultdict(list)
        for slot in slots:
            by_day[slot.day_of_week].append(slot)
        for day, schedule in by_day.items():
            for index, first in enumerate(schedule):
                for second in schedule[index + 1:]:
                    if not self._slots_share_audience(first, second):
                        continue
                    primary_group = self.db.get(StudentGroup, first.group_id)
                    group_name = primary_group.name if primary_group else f"Group #{first.group_id}"
                    if times_overlap(first.start_time, first.end_time, second.start_time, second.end_time):
                        conflict_type, time_range = "group", (max(first.start_time, second.start_time), min(first.end_time, second.end_time))
                    elif insufficient_transit_time(first.start_time, first.end_time, first.room_id, second.start_time, second.end_time, second.room_id):
                        conflict_type, time_range = "group_transit", (min(first.start_time, second.start_time), max(first.end_time, second.end_time))
                    else:
                        continue
                    conflicts.append(Conflict(conflict_type, [first.id, second.id], first.group_id, group_name, day, time_range))
        
        return conflicts
    
    def get_conflict_summary(self, timetable_id: int) -> Dict[str, Any]:
        """
        Get a summary of conflicts for a timetable.
        
        Returns:
            Dictionary with conflict counts by type and severity.
        """
        conflicts = self.detect_all_conflicts(timetable_id)
        
        summary = {
            "total_conflicts": len(conflicts),
            "by_type": {
                "lecturer": 0,
                "room": 0,
                "group": 0,
                "lecturer_transit": 0,
                "group_transit": 0,
            },
            "by_severity": {
                "high": 0,  # 3+ overlapping slots
                "medium": 0,  # 2 overlapping slots
            },
            "conflicts": [c.to_dict() for c in conflicts],
        }
        
        for conflict in conflicts:
            summary["by_type"][conflict.conflict_type] += 1
            
            if len(conflict.slot_ids) > 2:
                summary["by_severity"]["high"] += 1
            else:
                summary["by_severity"]["medium"] += 1
        
        return summary

    def get_available_rooms(
        self,
        target_date,
        start_time: time,
        end_time: time,
        min_capacity: int = 0,
        exclude_course_id: int = None
    ) -> List[Room]:
        """
        Finds rooms available for a specific date and time span.
        Checks both recurring TimetableSlots and one-off RoomBookings.
        """
        day_of_week = target_date.weekday()
        exam_period = self.db.query(ExamPeriod).filter(
            ExamPeriod.is_published.is_(True),
            ExamPeriod.start_date <= target_date,
            ExamPeriod.end_date >= target_date,
        ).first()

        all_rooms = self.db.query(Room).filter(
            Room.capacity >= min_capacity,
            Room.is_blocked == False
        ).all()

        colliding_room_ids = set()

        if exam_period:
            exam_allocations = (
                self.db.query(ExamSlotRoom)
                .join(ExamSlot, ExamSlotRoom.exam_slot_id == ExamSlot.id)
                .filter(
                    ExamSlot.exam_period_id == exam_period.id,
                    ExamSlot.exam_date == target_date,
                    ExamSlot.start_time < end_time,
                    ExamSlot.end_time > start_time,
                )
                .all()
            )
            for allocation in exam_allocations:
                colliding_room_ids.add(allocation.room_id)
        else:
            # Check recurring lecture slots only outside exam mode.
            active_timetable = self.db.query(Timetable).filter(Timetable.is_active == True).first()
            if active_timetable:
                query = self.db.query(TimetableSlot).filter(
                    TimetableSlot.timetable_id == active_timetable.id,
                    TimetableSlot.day_of_week == day_of_week,
                    TimetableSlot.start_time < end_time,
                    TimetableSlot.end_time > start_time
                )
                if exclude_course_id is not None:
                    query = query.filter(TimetableSlot.course_id != exclude_course_id)
                    
                slots = query.all()
                for s in slots:
                    if s.room_id:
                        colliding_room_ids.add(s.room_id)

        # Check one-off bookings
        query = self.db.query(RoomBooking).filter(
            RoomBooking.booking_date == target_date,
            RoomBooking.start_time < end_time,
            RoomBooking.end_time > start_time
        )
        if exclude_course_id is not None:
            query = query.filter(RoomBooking.course_id != exclude_course_id)
            
        bookings = query.all()
        for b in bookings:
            colliding_room_ids.add(b.room_id)

        return [r for r in all_rooms if r.id not in colliding_room_ids]
