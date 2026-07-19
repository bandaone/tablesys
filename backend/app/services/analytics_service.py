"""
Analytics Service

Provides analytics and statistics for timetables including:
- Room utilization rates
- Lecturer workload distribution
- Course distribution by department
- Time slot utilization
"""

from __future__ import annotations

from collections import defaultdict
from datetime import time
from typing import Any, Dict, List

from sqlalchemy import false, func
from sqlalchemy.orm import Session

from ..models import (
    Course,
    Department,
    Lecturer,
    Room,
    StudentGroup,
    Timetable,
    TimetableSlot,
    User,
)
from ..auth import is_tenant_admin


class AnalyticsService:
    """Generates analytics and statistics for timetables."""
    
    def __init__(self, db: Session, current_user: User | None = None):
        self.db = db
        self.current_user = current_user

    def _timetable_query(self):
        """Keep analytics inside the caller's tenant and school boundary."""
        query = self.db.query(Timetable)
        if not self.current_user:
            return query

        university_id = getattr(self.current_user, "university_id", None)
        if university_id is not None:
            query = query.filter(Timetable.university_id == university_id)
        if not is_tenant_admin(self.current_user):
            school_id = getattr(self.current_user, "school_id", None)
            # A staff account without a school assignment must not fall back to
            # tenant-wide analytics.
            query = query.filter(Timetable.school_id == school_id) if school_id is not None else query.filter(false())
        return query
    
    def get_timetable_analytics(self, timetable_id: int) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a timetable.
        
        Returns:
            Dictionary containing room utilization, lecturer workload,
            and other timetable statistics.
        """
        # Check if timetable exists
        timetable = self._timetable_query().filter(Timetable.id == timetable_id).first()
        if not timetable:
            raise ValueError(f"Timetable {timetable_id} not found")
        
        slots = (
            self.db.query(TimetableSlot)
            .filter(TimetableSlot.timetable_id == timetable_id)
            .all()
        )
        effective_slots = self._build_effective_slots(timetable, slots)
        
        return {
            "timetable_id": timetable_id,
            "timetable_name": timetable.name,
            "room_utilization": self._calculate_room_utilization(timetable, slots),
            "lecturer_workload": self._calculate_lecturer_workload(timetable, slots),
            "course_distribution": self._calculate_course_distribution(slots),
            "time_slot_utilization": self._calculate_time_slot_utilization(effective_slots),
            "day_distribution": self._calculate_day_distribution(effective_slots),
            "summary": self._generate_summary(slots),
            "warnings": self._calculate_warning_summary(slots),
        }
    
    def get_active_timetable_analytics(self) -> Dict[str, Any]:
        """Get analytics for the currently active timetable."""
        timetable = (
            self._timetable_query()
            .filter(Timetable.is_active == True)
            .order_by(Timetable.id.desc())
            .first()
        )
        
        if not timetable:
            raise ValueError("No active timetable found")
        
        return self.get_timetable_analytics(timetable.id)
    
    def _calculate_room_utilization(self, timetable: Timetable, slots: List[TimetableSlot]) -> List[Dict[str, Any]]:
        """Calculate utilization rate for each room."""
        # Count slots per room
        room_usage: Dict[int, int] = defaultdict(int)
        
        for slot in slots:
            if slot.room_id:
                room_usage[slot.room_id] += 1
        
        # Get all rooms
        rooms = (
            self.db.query(Room)
            .filter(
                Room.university_id == timetable.university_id,
                Room.school_id == timetable.school_id,
            )
            .all()
        )
        
        # Calculate total possible slots per week (5 days, ~10 hours/day)
        TOTAL_POSSIBLE_SLOTS_PER_WEEK = 50  # Approximate
        
        utilization_data = []
        for room in rooms:
            usage_count = room_usage.get(room.id, 0)
            utilization_rate = (usage_count / TOTAL_POSSIBLE_SLOTS_PER_WEEK) * 100
            
            utilization_data.append({
                "room_id": room.id,
                "room_name": room.name,
                "building": room.building,
                "capacity": room.capacity,
                "room_type": room.room_type,
                "slots_used": usage_count,
                "utilization_rate": round(utilization_rate, 1),
                "status": self._get_utilization_status(utilization_rate),
            })
        
        # Sort by utilization rate descending
        utilization_data.sort(key=lambda x: x["utilization_rate"], reverse=True)
        
        return utilization_data
    
    def _calculate_lecturer_workload(self, timetable: Timetable, slots: List[TimetableSlot]) -> List[Dict[str, Any]]:
        """Calculate workload hours for each lecturer."""
        # Count hours per lecturer
        lecturer_hours: Dict[int, float] = defaultdict(float)
        
        for slot in slots:
            if slot.lecturer_id:
                # Calculate duration in hours
                duration = (slot.end_time.hour + slot.end_time.minute / 60) - \
                          (slot.start_time.hour + slot.start_time.minute / 60)
                lecturer_hours[slot.lecturer_id] += duration
        
        # Get all lecturers
        lecturers = (
            self.db.query(Lecturer)
            .join(Department, Lecturer.department_id == Department.id)
            .filter(
                Department.university_id == timetable.university_id,
                Department.school_id == timetable.school_id,
            )
            .all()
        )
        
        workload_data = []
        for lecturer in lecturers:
            hours = lecturer_hours.get(lecturer.id, 0)
            max_hours = lecturer.max_hours_per_week or 20
            workload_percentage = (hours / max_hours) * 100
            
            workload_data.append({
                "lecturer_id": lecturer.id,
                "lecturer_name": lecturer.full_name,
                "department": lecturer.department.name if lecturer.department else "N/A",
                "total_hours": round(hours, 1),
                "max_hours": max_hours,
                "workload_percentage": round(workload_percentage, 1),
                "status": self._get_workload_status(workload_percentage),
            })
        
        # Sort by total hours descending
        workload_data.sort(key=lambda x: x["total_hours"], reverse=True)
        
        return workload_data
    
    def _calculate_course_distribution(self, slots: List[TimetableSlot]) -> List[Dict[str, Any]]:
        """Calculate course distribution by department."""
        # Count courses per department
        dept_course_count: Dict[str, int] = defaultdict(int)
        dept_hours: Dict[str, float] = defaultdict(float)
        
        for slot in slots:
            course = self.db.query(Course).get(slot.course_id)
            if course and course.department:
                dept_name = course.department.name
                dept_course_count[dept_name] += 1
                
                # Calculate duration
                duration = (slot.end_time.hour + slot.end_time.minute / 60) - \
                          (slot.start_time.hour + slot.start_time.minute / 60)
                dept_hours[dept_name] += duration
        
        distribution_data = []
        total_slots = len(slots)
        
        for dept_name, course_count in dept_course_count.items():
            percentage = (course_count / total_slots) * 100 if total_slots > 0 else 0
            
            distribution_data.append({
                "department": dept_name,
                "course_count": course_count,
                "total_hours": round(dept_hours[dept_name], 1),
                "percentage": round(percentage, 1),
            })
        
        # Sort by course count descending
        distribution_data.sort(key=lambda x: x["course_count"], reverse=True)
        
        return distribution_data
    
    def _calculate_time_slot_utilization(self, slots: List[Any]) -> Dict[str, Any]:
        """Calculate utilization by time of day."""
        # Time slots: Morning (7-12), Afternoon (12-17), Evening (17-20)
        morning_count = 0
        afternoon_count = 0
        evening_count = 0
        
        for slot in slots:
            start_time = self._slot_value(slot, "start_time")
            if start_time is None:
                continue
            hour = start_time.hour
            if 7 <= hour < 12:
                morning_count += 1
            elif 12 <= hour < 17:
                afternoon_count += 1
            else:
                evening_count += 1
        
        total = len(slots)
        
        return {
            "morning": {
                "count": morning_count,
                "percentage": round((morning_count / total) * 100, 1) if total > 0 else 0,
                "time_range": "07:00 - 12:00",
            },
            "afternoon": {
                "count": afternoon_count,
                "percentage": round((afternoon_count / total) * 100, 1) if total > 0 else 0,
                "time_range": "12:00 - 17:00",
            },
            "evening": {
                "count": evening_count,
                "percentage": round((evening_count / total) * 100, 1) if total > 0 else 0,
                "time_range": "17:00 - 20:00",
            },
        }

    def _calculate_day_distribution(self, slots: List[Any]) -> List[Dict[str, Any]]:
        """Calculate actual slot load by weekday."""
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        day_counts: Dict[int, int] = defaultdict(int)

        for slot in slots:
            day_index = self._normalize_day_index(self._slot_value(slot, "day_of_week"), day_names)
            if day_index is not None:
                day_counts[day_index] += 1

        total = len(slots)
        distribution = []
        for day_index, day_name in enumerate(day_names):
            count = day_counts.get(day_index, 0)
            distribution.append({
                "day_index": day_index,
                "day_name": day_name,
                "short_label": day_name[:3],
                "count": count,
                "percentage": round((count / total) * 100, 1) if total > 0 else 0,
            })

        return distribution

    @staticmethod
    def _slot_value(slot: Any, field_name: str) -> Any:
        if isinstance(slot, dict):
            return slot.get(field_name)
        return getattr(slot, field_name, None)

    def _build_effective_slots(self, timetable: Timetable, slots: List[TimetableSlot]) -> List[Dict[str, Any]]:
        """Apply coordinator overrides so analytics reflect the visible timetable state."""
        raw_overrides = (timetable.generation_metadata or {}).get("overrides", {})
        override_map = raw_overrides if isinstance(raw_overrides, dict) else {}

        effective_slots: List[Dict[str, Any]] = []
        for slot in slots:
            effective = {
                "id": slot.id,
                "day_of_week": slot.day_of_week,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
            }

            override = override_map.get(str(slot.id)) or override_map.get(slot.id)
            if isinstance(override, dict):
                override_day = override.get("day")
                if override_day is not None:
                    effective["day_of_week"] = override_day

                parsed_start_time = self._parse_time_value(override.get("start_time"))
                if parsed_start_time is not None:
                    effective["start_time"] = parsed_start_time

                parsed_end_time = self._parse_time_value(override.get("end_time"))
                if parsed_end_time is not None:
                    effective["end_time"] = parsed_end_time

            effective_slots.append(effective)

        return effective_slots

    @staticmethod
    def _parse_time_value(value: Any) -> time | None:
        if isinstance(value, time):
            return value
        if not isinstance(value, str):
            return None

        text = value.strip()
        if not text:
            return None

        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                parts = text.split(":")
                if fmt == "%H:%M" and len(parts) != 2:
                    continue
                if fmt == "%H:%M:%S" and len(parts) != 3:
                    continue
                hour, minute, *seconds = [int(part) for part in parts]
                return time(hour=hour, minute=minute, second=seconds[0] if seconds else 0)
            except ValueError:
                continue

        return None

    @staticmethod
    def _normalize_day_index(day_value: Any, day_names: List[str]) -> int | None:
        """Normalize supported weekday formats to a zero-based Monday-Friday index."""
        if day_value is None:
            return None

        if isinstance(day_value, str):
            text = day_value.strip()
            if not text:
                return None
            if text.isdigit():
                day_value = int(text)
            else:
                lowered = text.lower()
                for index, day_name in enumerate(day_names):
                    if lowered in {day_name.lower(), day_name[:3].lower()}:
                        return index
                return None

        if isinstance(day_value, (int, float)):
            day_int = int(day_value)
            if 0 <= day_int < len(day_names):
                return day_int
            if 1 <= day_int <= len(day_names):
                return day_int - 1

        return None
    
    def _generate_summary(self, slots: List[TimetableSlot]) -> Dict[str, Any]:
        """Generate overall summary statistics."""
        unique_courses = len(set(slot.course_id for slot in slots))
        unique_rooms = len(set(slot.room_id for slot in slots if slot.room_id))
        unique_lecturers = len(set(slot.lecturer_id for slot in slots if slot.lecturer_id))
        unique_groups = len(set(slot.group_id for slot in slots if slot.group_id))
        
        # Calculate total contact hours
        total_hours = 0
        for slot in slots:
            duration = (slot.end_time.hour + slot.end_time.minute / 60) - \
                      (slot.start_time.hour + slot.start_time.minute / 60)
            total_hours += duration
        
        return {
            "total_slots": len(slots),
            "unique_courses": unique_courses,
            "unique_rooms": unique_rooms,
            "unique_lecturers": unique_lecturers,
            "unique_groups": unique_groups,
            "total_contact_hours": round(total_hours, 1),
        }

    def _calculate_warning_summary(self, slots: List[TimetableSlot]) -> Dict[str, Any]:
        """Summarize operational warnings worth surfacing in analytics."""
        capacity_fallbacks: List[Dict[str, Any]] = []

        for slot in slots:
            room = self.db.query(Room).get(slot.room_id) if slot.room_id else None
            course = self.db.query(Course).get(slot.course_id) if slot.course_id else None
            primary_group = self.db.query(StudentGroup).get(slot.group_id) if slot.group_id else None

            shared_group_ids = slot.shared_group_ids or []
            shared_groups = []
            if shared_group_ids:
                shared_groups = (
                    self.db.query(StudentGroup)
                    .filter(StudentGroup.id.in_(shared_group_ids))
                    .all()
                )

            audience_groups = [group for group in [primary_group, *shared_groups] if group]
            required_size = (
                slot.combined_size
                or sum((group.size or 0) for group in audience_groups)
                or (primary_group.size if primary_group else 0)
            )
            room_capacity = room.capacity if room and room.capacity is not None else 0

            if room and required_size > room_capacity:
                overflow = required_size - room_capacity
                capacity_fallbacks.append({
                    "slot_id": slot.id,
                    "course_code": course.code if course else "Unknown",
                    "course_name": course.name if course else "Unknown",
                    "room_name": room.name,
                    "room_capacity": room_capacity,
                    "required_size": required_size,
                    "overflow": overflow,
                    "day_of_week": slot.day_of_week,
                    "start_time": slot.start_time.strftime("%H:%M"),
                    "end_time": slot.end_time.strftime("%H:%M"),
                    "session_type": slot.session_type,
                    "group_names": [group.name for group in audience_groups],
                    "group_count": len(audience_groups),
                })

        capacity_fallbacks.sort(key=lambda item: (item["overflow"], item["required_size"]), reverse=True)

        return {
            "total": len(capacity_fallbacks),
            "capacity_fallbacks": capacity_fallbacks[:12],
            "largest_overflow": capacity_fallbacks[0]["overflow"] if capacity_fallbacks else 0,
        }
    
    @staticmethod
    def _get_utilization_status(rate: float) -> str:
        """Get status label for utilization rate."""
        if rate >= 80:
            return "High"
        elif rate >= 50:
            return "Moderate"
        elif rate >= 20:
            return "Low"
        else:
            return "Minimal"
    
    @staticmethod
    def _get_workload_status(percentage: float) -> str:
        """Get status label for workload percentage."""
        if percentage >= 100:
            return "Overloaded"
        elif percentage >= 80:
            return "High"
        elif percentage >= 50:
            return "Moderate"
        else:
            return "Light"
