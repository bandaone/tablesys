"""
Enhanced Validation Service

Provides comprehensive validation for timetable constraints:
- Room capacity vs group size validation
- Lecturer availability checking
- Break time enforcement
- Prerequisites validation
- Concurrent booking detection
"""

from __future__ import annotations

from typing import List, Dict, Optional, Tuple
from datetime import time, datetime
from sqlalchemy.orm import Session
from ..models import (
    Course,
    Lecturer,
    Room,
    RoomType,
    StudentGroup,
    TimetableSlot,
    Timetable
)
from ..utils.room_matching import room_match_rank, room_type_matches
from ..utils.transit import DEFAULT_TRANSIT_MINUTES, insufficient_transit_time


class ValidationError:
    """Represents a validation error with severity level."""
    
    def __init__(
        self,
        entity_type: str,
        entity_id: int,
        field: str,
        message: str,
        severity: str = "error"  # error, warning, info
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.field = field
        self.message = message
        self.severity = severity
    
    def to_dict(self) -> Dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "field": self.field,
            "message": self.message,
            "severity": self.severity
        }


class ValidationService:
    """Provides validation services for timetable system."""

    OVERSIZED_ROOM_MIN_ATTENDANCE_RATIO = 0.50
    
    def __init__(self, db: Session):
        self.db = db
        self.errors: List[ValidationError] = []

    @staticmethod
    def _group_label(group: Optional[StudentGroup]) -> str:
        if not group:
            return "Unknown"
        return getattr(group, "name", None) or getattr(group, "group_name", None) or f"Group #{group.id}"

    @staticmethod
    def _day_name(day_value: Optional[int | str]) -> Optional[str]:
        if day_value is None:
            return None
        if isinstance(day_value, int):
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            return days[day_value] if 0 <= day_value < len(days) else None

        text = str(day_value).strip()
        if not text:
            return None
        if text.isdigit():
            return ValidationService._day_name(int(text))
        return text

    def _resolve_slot_day(self, slot_data: Dict) -> Optional[str]:
        day_name = self._day_name(slot_data.get("day"))
        if day_name:
            return day_name
        return self._day_name(slot_data.get("day_of_week"))

    @staticmethod
    def _day_index(day_value: Optional[int | str]) -> Optional[int]:
        if isinstance(day_value, int):
            return day_value if 0 <= day_value <= 6 else None
        day_name = ValidationService._day_name(day_value)
        if not day_name:
            return None
        names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        try:
            return names.index(day_name.lower())
        except ValueError:
            return None

    @classmethod
    def _minimum_acceptable_fallback_capacity(cls, required_size: int) -> int:
        if required_size <= 0:
            return 0
        return max(1, int(required_size * cls.OVERSIZED_ROOM_MIN_ATTENDANCE_RATIO))

    @classmethod
    def _room_meets_fallback_capacity(cls, required_size: int, room_capacity: Optional[int]) -> bool:
        if not room_capacity:
            return True
        return room_capacity >= cls._minimum_acceptable_fallback_capacity(required_size)

    def _audience_groups_for_slot(self, slot_data: Dict) -> List[StudentGroup]:
        group_ids: List[int] = []
        primary_group_id = slot_data.get("group_id")
        if primary_group_id:
            group_ids.append(int(primary_group_id))

        for raw_group_id in slot_data.get("shared_group_ids") or []:
            try:
                group_id = int(raw_group_id)
            except (TypeError, ValueError):
                continue
            if group_id not in group_ids:
                group_ids.append(group_id)

        if not group_ids:
            return []

        groups = self.db.query(StudentGroup).filter(StudentGroup.id.in_(group_ids)).all()
        group_by_id = {group.id: group for group in groups}
        return [group_by_id[group_id] for group_id in group_ids if group_id in group_by_id]

    def _largest_compatible_room_capacity(
        self,
        *,
        university_id: Optional[int],
        course: Optional[Course],
        session_type: Optional[str],
        group_size: Optional[int] = None,
        enforce_fallback_threshold: bool = False,
    ) -> int:
        if not university_id:
            return 0

        rooms = (
            self.db.query(Room)
            .filter(
                Room.university_id == university_id,
                Room.is_blocked.is_(False),
            )
            .all()
        )

        compatible_rooms = rooms
        if course:
            compatible_rooms = [
                room for room in rooms
                if room_type_matches(
                    course.preferred_room_type,
                    session_type,
                    room.room_type,
                    group_size=group_size,
                )
            ]

        if enforce_fallback_threshold and group_size:
            compatible_rooms = [
                room for room in compatible_rooms
                if self._room_meets_fallback_capacity(group_size, room.capacity)
            ]

        capacities = [room.capacity or 0 for room in compatible_rooms]
        return max(capacities) if capacities else 0

    def validate_room_assignment(
        self,
        room_id: int,
        *,
        course_id: Optional[int] = None,
        primary_group_id: Optional[int] = None,
        shared_group_ids: Optional[List[int]] = None,
        combined_size: Optional[int] = None,
        session_type: Optional[str] = None,
    ) -> bool:
        """Validate that the chosen room is suitable for the full slot audience."""
        room = self.db.query(Room).get(room_id)
        if not room:
            return False

        audience_groups = self._audience_groups_for_slot(
            {
                "group_id": primary_group_id,
                "shared_group_ids": shared_group_ids or [],
            }
        )
        if primary_group_id and not audience_groups:
            return False

        required_size = combined_size
        if required_size is None:
            required_size = sum(group.size or 0 for group in audience_groups)
        if required_size is None or required_size <= 0:
            required_size = audience_groups[0].size if audience_groups else 0

        if getattr(room, "is_blocked", False):
            self.errors.append(ValidationError(
                entity_type="room_assignment",
                entity_id=room_id,
                field="room_id",
                message=f"Room {room.name} is blocked and cannot host classes",
                severity="error"
            ))
            return False

        course = None
        if course_id:
            course = self.db.query(Course).get(course_id)
            assigned_match_rank = None
            if course:
                assigned_match_rank = room_match_rank(
                    course.preferred_room_type,
                    session_type,
                    room.room_type,
                    group_size=required_size,
                )
            if course and assigned_match_rank is None:
                preferred_type = str(course.preferred_room_type or RoomType.ANY.value)
                self.errors.append(ValidationError(
                    entity_type="room_assignment",
                    entity_id=room_id,
                    field="room_type",
                    message=(
                        f"Room {room.name} ({room.room_type}) does not match the required "
                        f"room type for this {session_type or 'session'} ({preferred_type})"
                    ),
                    severity="error"
                ))
                return False
            if course and assigned_match_rank is not None:
                candidate_rooms = (
                    self.db.query(Room)
                    .filter(
                        Room.university_id == getattr(room, "university_id", None),
                        Room.is_blocked.is_(False),
                    )
                    .all()
                )
                ranked_candidates = []
                for candidate_room in candidate_rooms:
                    candidate_rank = room_match_rank(
                        course.preferred_room_type,
                        session_type,
                        candidate_room.room_type,
                        group_size=required_size,
                    )
                    if candidate_rank is None:
                        continue
                    ranked_candidates.append((candidate_room, candidate_rank))

                capacity_candidates = [
                    (candidate_room, candidate_rank)
                    for candidate_room, candidate_rank in ranked_candidates
                    if self._room_meets_fallback_capacity(required_size, candidate_room.capacity)
                ]
                best_rank_pool = capacity_candidates or ranked_candidates
                best_available_rank = min((candidate_rank for _, candidate_rank in best_rank_pool), default=assigned_match_rank)

                if assigned_match_rank > best_available_rank:
                    self.errors.append(ValidationError(
                        entity_type="room_assignment",
                        entity_id=room_id,
                        field="room_type",
                        message=(
                            f"Room {room.name} is only a fallback match for this {session_type or 'session'}; "
                            "a better-matched room type is available"
                        ),
                        severity="error"
                    ))
                    return False

                if assigned_match_rank > 0:
                    self.errors.append(ValidationError(
                        entity_type="room_assignment",
                        entity_id=room_id,
                        field="room_type_fallback",
                        message=(
                            f"Room {room.name} is being used as a fallback for this {session_type or 'session'} "
                            "because no better-matched room type is currently available"
                        ),
                        severity="warning"
                    ))

        if required_size > room.capacity:
            audience_label = ", ".join(self._group_label(group) for group in audience_groups) or "selected audience"
            minimum_fallback_capacity = self._minimum_acceptable_fallback_capacity(required_size)
            room_meets_threshold = self._room_meets_fallback_capacity(required_size, room.capacity)
            largest_compatible_capacity = self._largest_compatible_room_capacity(
                university_id=getattr(room, "university_id", None),
                course=course,
                session_type=session_type,
                group_size=required_size,
                enforce_fallback_threshold=True,
            )
            if not room_meets_threshold:
                self.errors.append(ValidationError(
                    entity_type="room_assignment",
                    entity_id=room_id,
                    field="capacity_threshold",
                    message=(
                        f"Room {room.name} (capacity {room.capacity}) is too small for "
                        f"{audience_label} (size {required_size}); oversized fallback rooms must seat at least "
                        f"{minimum_fallback_capacity} students"
                    ),
                    severity="error"
                ))
                return False

            if largest_compatible_capacity and (room.capacity or 0) >= largest_compatible_capacity:
                self.errors.append(ValidationError(
                    entity_type="room_assignment",
                    entity_id=room_id,
                    field="capacity_overflow",
                    message=(
                        f"Room {room.name} is the largest compatible fallback room available "
                        f"({room.capacity} seats) but still cannot fully accommodate "
                        f"{audience_label} (size {required_size})"
                    ),
                    severity="warning"
                ))
            else:
                self.errors.append(ValidationError(
                    entity_type="room_assignment",
                    entity_id=room_id,
                    field="capacity",
                    message=(
                        f"Room {room.name} (capacity {room.capacity}) cannot accommodate "
                        f"{audience_label} (size {required_size}); use the largest compatible fallback room available "
                        f"({largest_compatible_capacity} seats)"
                    ),
                    severity="error"
                ))
                return False

        if room.capacity and required_size:
            utilization = (required_size / room.capacity) * 100
            if utilization < 50:
                audience_label = ", ".join(self._group_label(group) for group in audience_groups) or "selected audience"
                self.errors.append(ValidationError(
                    entity_type="room_assignment",
                    entity_id=room_id,
                    field="utilization",
                    message=f"Low room utilization: {utilization:.1f}% for {room.name} with {audience_label}",
                    severity="warning"
                ))

        return True

    def _timetable_lunch_window(self, timetable_id: int) -> Tuple[time, time]:
        timetable = self.db.query(Timetable).get(timetable_id)
        grid_config = getattr(timetable, "generation_metadata", None) or {}
        if isinstance(grid_config, dict):
            grid_config = grid_config.get("grid_config") or {}
        else:
            grid_config = {}

        lunch_start_raw = str(grid_config.get("lunch_start", "13:00"))
        lunch_end_raw = str(grid_config.get("lunch_end", "14:00"))

        try:
            lunch_start = datetime.strptime(lunch_start_raw, "%H:%M").time()
            lunch_end = datetime.strptime(lunch_end_raw, "%H:%M").time()
        except ValueError:
            return time(13, 0), time(14, 0)

        if lunch_start >= lunch_end:
            return time(13, 0), time(14, 0)
        return lunch_start, lunch_end
    
    def validate_room_capacity(self, room_id: int, group_id: int) -> bool:
        """
        Validate that room capacity can accommodate student group.
        Returns True if valid, False otherwise.
        """
        return self.validate_room_assignment(room_id, primary_group_id=group_id)
    
    def validate_lecturer_availability(
        self,
        lecturer_id: int,
        day: str,
        start_time: time,
        end_time: time
    ) -> bool:
        """
        Validate lecturer is available at specified time.
        Checks teaching preferences and existing assignments.
        """
        lecturer = self.db.query(Lecturer).get(lecturer_id)
        if not lecturer:
            return False
        
        # Check teaching preferences
        if lecturer.teaching_preferences:
            prefs = lecturer.teaching_preferences
            
            # Check early morning preference (before 08:30)
            if prefs.get("avoid_early_morning", False):
                if start_time < time(8, 30):
                    self.errors.append(ValidationError(
                        entity_type="lecturer_assignment",
                        entity_id=lecturer_id,
                        field="time_preference",
                        message=f"Lecturer {lecturer.full_name} prefers to avoid early morning classes",
                        severity="warning"
                    ))
            
            # Check late afternoon preference (after 17:00)
            if prefs.get("avoid_late_afternoon", False):
                if start_time >= time(17, 0):
                    self.errors.append(ValidationError(
                        entity_type="lecturer_assignment",
                        entity_id=lecturer_id,
                        field="time_preference",
                        message=f"Lecturer {lecturer.full_name} prefers to avoid late afternoon classes",
                        severity="warning"
                    ))
        
        return True
    
    def validate_break_time(
        self,
        timetable_id: int,
        day: str,
        start_time: time,
        end_time: time,
        lecturer_id: Optional[int] = None,
        group_id: Optional[int] = None,
        room_id: Optional[int] = None,
        exclude_slot_id: Optional[int] = None,
    ) -> bool:
        """
        Validate that entities have adequate break time between consecutive classes.
        Minimum break: 10 minutes between classes.
        Lunch break: Should have at least 30 minutes during the configured lunch window.
        """
        valid = True
        
        day_index = self._day_index(day)
        if day_index is None:
            return valid

        # A transition is only required if the person changes rooms.  This
        # allows a class to continue in the same venue at the exact boundary.
        if lecturer_id:
            adjacent_slots = (
                self.db.query(TimetableSlot)
                .filter(
                    TimetableSlot.timetable_id == timetable_id,
                    TimetableSlot.day_of_week == day_index,
                    TimetableSlot.lecturer_id == lecturer_id
                )
                .all()
            )
            for slot in adjacent_slots:
                if exclude_slot_id and slot.id == exclude_slot_id:
                    continue
                if insufficient_transit_time(start_time, end_time, room_id, slot.start_time, slot.end_time, slot.room_id):
                    lecturer = self.db.query(Lecturer).get(lecturer_id)
                    self.errors.append(ValidationError(
                        entity_type="time_slot",
                        entity_id=0,
                        field="transit_time",
                        message=(f"Lecturer {lecturer.full_name if lecturer else 'Unknown'} needs at least "
                                 f"{DEFAULT_TRANSIT_MINUTES} minutes between classes in different rooms on {day}"),
                        severity="error"
                    ))
                    valid = False
        
        # Check for back-to-back classes for student group
        if group_id:
            adjacent_slots = (
                self.db.query(TimetableSlot)
                .filter(
                    TimetableSlot.timetable_id == timetable_id,
                    TimetableSlot.day_of_week == day_index,
                    TimetableSlot.group_id == group_id
                )
                .all()
            )
            
            for slot in adjacent_slots:
                if exclude_slot_id and slot.id == exclude_slot_id:
                    continue
                if insufficient_transit_time(start_time, end_time, room_id, slot.start_time, slot.end_time, slot.room_id):
                    group = self.db.query(StudentGroup).get(group_id)
                    self.errors.append(ValidationError(
                        entity_type="time_slot",
                        entity_id=0,
                        field="transit_time",
                        message=(f"Group {self._group_label(group)} needs at least {DEFAULT_TRANSIT_MINUTES} "
                                 f"minutes between classes in different rooms on {day}"),
                        severity="error"
                    ))
                    valid = False
        
        lunch_start, lunch_end = self._timetable_lunch_window(timetable_id)
        
        # If class spans lunch time, ensure reasonable duration
        if start_time < lunch_start and end_time > lunch_end:
            self.errors.append(ValidationError(
                entity_type="time_slot",
                entity_id=0,
                field="lunch_break",
                message=f"Class spans entire lunch period ({start_time}-{end_time})",
                severity="warning"
            ))
        
        return valid
    
    def validate_lecturer_workload(self, lecturer_id: int, timetable_id: int) -> bool:
        """
        Validate lecturer's total workload doesn't exceed maximum hours.
        """
        lecturer = self.db.query(Lecturer).get(lecturer_id)
        if not lecturer:
            return False
        
        # Calculate total assigned hours
        slots = (
            self.db.query(TimetableSlot)
            .filter(
                TimetableSlot.timetable_id == timetable_id,
                TimetableSlot.lecturer_id == lecturer_id
            )
            .all()
        )
        
        total_hours = 0
        for slot in slots:
            duration = (slot.end_time.hour + slot.end_time.minute / 60) - \
                      (slot.start_time.hour + slot.start_time.minute / 60)
            total_hours += duration
        
        max_hours = lecturer.max_hours_per_week or 20
        
        if total_hours > max_hours:
            self.errors.append(ValidationError(
                entity_type="lecturer",
                entity_id=lecturer_id,
                field="workload",
                message=f"Lecturer {lecturer.full_name} is overloaded: {total_hours:.1f}h / {max_hours}h",
                severity="error"
            ))
            return False
        
        # Warning if approaching limit (> 90%)
        if total_hours > max_hours * 0.9:
            self.errors.append(ValidationError(
                entity_type="lecturer",
                entity_id=lecturer_id,
                field="workload",
                message=f"Lecturer {lecturer.full_name} is near capacity: {total_hours:.1f}h / {max_hours}h",
                severity="warning"
            ))
        
        return True
    
    def validate_room_double_booking(
        self,
        room_id: int,
        timetable_id: int,
        day: str,
        start_time: time,
        end_time: time,
        exclude_slot_id: Optional[int] = None
    ) -> bool:
        """
        Validate room is not double-booked at the specified time.
        """
        day_index = self._day_index(day)
        if day_index is None:
            return False
        query = (
            self.db.query(TimetableSlot)
            .filter(
                TimetableSlot.timetable_id == timetable_id,
                TimetableSlot.room_id == room_id,
                TimetableSlot.day_of_week == day_index
            )
        )
        
        if exclude_slot_id:
            query = query.filter(TimetableSlot.id != exclude_slot_id)
        
        existing_slots = query.all()
        
        for slot in existing_slots:
            # Check for time overlap
            if not (end_time <= slot.start_time or start_time >= slot.end_time):
                room = self.db.query(Room).get(room_id)
                self.errors.append(ValidationError(
                    entity_type="room",
                    entity_id=room_id,
                    field="double_booking",
                    message=f"Room {room.name if room else 'Unknown'} is already booked on {day} {start_time}-{end_time}",
                    severity="error"
                ))
                return False
        
        return True
    
    def validate_course_prerequisites(self, course_id: int, group_level: int) -> bool:
        """
        Validate that course is appropriate for student group level.
        """
        course = self.db.query(Course).get(course_id)
        if not course:
            return False
        
        # Check if course level matches group level
        if course.level != group_level:
            self.errors.append(ValidationError(
                entity_type="course",
                entity_id=course_id,
                field="level_mismatch",
                message=f"Course {course.code} (Level {course.level}) assigned to Level {group_level} group",
                severity="warning"
            ))
            return False
        
        return True
    
    def validate_timetable_slot(
        self,
        slot_data: Dict,
        timetable_id: int,
        exclude_slot_id: Optional[int] = None
    ) -> Tuple[bool, List[Dict]]:
        """
        Comprehensive validation for a timetable slot.
        Returns (is_valid, list_of_errors).
        """
        self.errors = []  # Reset errors
        
        valid = True
        session_type = str(slot_data.get("session_type") or "").strip().lower()
        requires_room = session_type not in {"practical", "lab"}

        # Validate room capacity
        if "room_id" in slot_data and "group_id" in slot_data:
            if slot_data["room_id"] and slot_data["group_id"]:
                valid &= self.validate_room_assignment(
                    slot_data["room_id"],
                    course_id=slot_data.get("course_id"),
                    primary_group_id=slot_data.get("group_id"),
                    shared_group_ids=slot_data.get("shared_group_ids"),
                    combined_size=slot_data.get("combined_size"),
                    session_type=slot_data.get("session_type"),
                )
            elif requires_room:
                self.errors.append(ValidationError(
                    entity_type="room_assignment",
                    entity_id=0,
                    field="room_id",
                    message=f"A room is required for this {session_type or 'session'} slot",
                    severity="error"
                ))
                valid = False
            else:
                self.errors.append(ValidationError(
                    entity_type="room_assignment",
                    entity_id=0,
                    field="room_id",
                    message="Practical session recorded without a room as requested",
                    severity="info"
                ))

        day_name = self._resolve_slot_day(slot_data)
        if not day_name:
            self.errors.append(ValidationError(
                entity_type="time_slot",
                entity_id=0,
                field="day",
                message="Slot day is required",
                severity="error"
            ))
            return False, [error.to_dict() for error in self.errors]
        
        # Validate lecturer availability
        if "lecturer_id" in slot_data:
            if slot_data["lecturer_id"]:
                valid &= self.validate_lecturer_availability(
                    slot_data["lecturer_id"],
                    day_name,
                    slot_data["start_time"],
                    slot_data["end_time"]
                )
        
        # Validate break time
        valid &= self.validate_break_time(
            timetable_id,
            day_name,
            slot_data["start_time"],
            slot_data["end_time"],
            slot_data.get("lecturer_id"),
            slot_data.get("group_id"),
            slot_data.get("room_id"),
            exclude_slot_id,
        )
        
        # Validate room double booking
        if "room_id" in slot_data:
            if slot_data["room_id"]:
                valid &= self.validate_room_double_booking(
                    slot_data["room_id"],
                    timetable_id,
                    day_name,
                    slot_data["start_time"],
                    slot_data["end_time"],
                    exclude_slot_id
                )
        
        # Validate course prerequisites
        if "course_id" in slot_data and "group_id" in slot_data:
            if slot_data["course_id"] and slot_data["group_id"]:
                group = self.db.query(StudentGroup).get(slot_data["group_id"])
                if group:
                    valid &= self.validate_course_prerequisites(slot_data["course_id"], group.level)
        
        return valid, [error.to_dict() for error in self.errors]
    
    def validate_entire_timetable(self, timetable_id: int) -> Dict:
        """
        Validate entire timetable and return comprehensive report.
        """
        self.errors = []
        
        timetable = self.db.query(Timetable).get(timetable_id)
        if not timetable:
            return {"valid": False, "errors": [{"message": "Timetable not found"}]}
        
        slots = (
            self.db.query(TimetableSlot)
            .filter(TimetableSlot.timetable_id == timetable_id)
            .all()
        )
        
        # Validate each slot
        for slot in slots:
            slot_data = {
                "day_of_week": slot.day_of_week,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "course_id": slot.course_id,
                "room_id": slot.room_id,
                "lecturer_id": slot.lecturer_id,
                "group_id": slot.group_id,
                "session_type": slot.session_type,
            }
            
            self.validate_timetable_slot(slot_data, timetable_id, exclude_slot_id=slot.id)
        
        # Validate lecturer workloads
        lecturer_ids = set(slot.lecturer_id for slot in slots if slot.lecturer_id)
        for lecturer_id in lecturer_ids:
            self.validate_lecturer_workload(lecturer_id, timetable_id)
        
        # Categorize errors by severity
        errors_by_severity = {
            "error": [],
            "warning": [],
            "info": []
        }
        
        for error in self.errors:
            errors_by_severity[error.severity].append(error.to_dict())
        
        return {
            "valid": len(errors_by_severity["error"]) == 0,
            "total_issues": len(self.errors),
            "errors": errors_by_severity["error"],
            "warnings": errors_by_severity["warning"],
            "info": errors_by_severity["info"]
        }
