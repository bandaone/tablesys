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
    
    def _detect_lecturer_conflicts(self, slots: List[TimetableSlot]) -> List[Conflict]:
        """Detect lecturer double-booking conflicts."""
        # Group slots by (lecturer_id, day, time) to find overlaps
        lecturer_schedule: Dict[Tuple[int, int, time, time], List[TimetableSlot]] = defaultdict(list)
        
        for slot in slots:
            if slot.lecturer_id is None:
                continue
            
            key = (slot.lecturer_id, slot.day_of_week, slot.start_time, slot.end_time)
            lecturer_schedule[key].append(slot)
        
        # Find conflicts (multiple slots with same lecturer at same time)
        conflicts = []
        for (lecturer_id, day, start, end), conflicting_slots in lecturer_schedule.items():
            if len(conflicting_slots) > 1:
                # Get lecturer name
                lecturer = self.db.query(Lecturer).get(lecturer_id)
                lecturer_name = lecturer.full_name if lecturer else f"Lecturer #{lecturer_id}"
                
                conflict = Conflict(
                    conflict_type="lecturer",
                    slot_ids=[s.id for s in conflicting_slots],
                    resource_id=lecturer_id,
                    resource_name=lecturer_name,
                    day=day,
                    time_range=(start, end),
                )
                conflicts.append(conflict)
        
        return conflicts
    
    def _detect_room_conflicts(self, slots: List[TimetableSlot]) -> List[Conflict]:
        """Detect room double-booking conflicts."""
        room_schedule: Dict[Tuple[int, int, time, time], List[TimetableSlot]] = defaultdict(list)
        
        for slot in slots:
            if slot.room_id is None:
                continue
            
            key = (slot.room_id, slot.day_of_week, slot.start_time, slot.end_time)
            room_schedule[key].append(slot)
        
        conflicts = []
        for (room_id, day, start, end), conflicting_slots in room_schedule.items():
            if len(conflicting_slots) > 1:
                room = self.db.query(Room).get(room_id)
                room_name = room.name if room else f"Room #{room_id}"
                
                conflict = Conflict(
                    conflict_type="room",
                    slot_ids=[s.id for s in conflicting_slots],
                    resource_id=room_id,
                    resource_name=room_name,
                    day=day,
                    time_range=(start, end),
                )
                conflicts.append(conflict)
        
        return conflicts
    
    def _detect_group_conflicts(self, slots: List[TimetableSlot]) -> List[Conflict]:
        """Detect student group double-booking conflicts."""
        group_schedule: Dict[Tuple[int, int, time, time], List[TimetableSlot]] = defaultdict(list)
        
        for slot in slots:
            if slot.group_id is None:
                continue
            
            key = (slot.group_id, slot.day_of_week, slot.start_time, slot.end_time)
            group_schedule[key].append(slot)
        
        conflicts = []
        for (group_id, day, start, end), conflicting_slots in group_schedule.items():
            if len(conflicting_slots) > 1:
                group = self.db.query(StudentGroup).get(group_id)
                group_name = group.name if group else f"Group #{group_id}"
                
                conflict = Conflict(
                    conflict_type="group",
                    slot_ids=[s.id for s in conflicting_slots],
                    resource_id=group_id,
                    resource_name=group_name,
                    day=day,
                    time_range=(start, end),
                )
                conflicts.append(conflict)
        
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
