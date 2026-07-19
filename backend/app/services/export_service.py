"""
Export Service

Prepares structured grid data from the database that can be consumed by
DocxGenerator, ExcelGenerator, or returned directly as JSON.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Course, Lecturer, Room, StudentGroup, Timetable, TimetableSlot, University
from ..utils.display_formatting import format_group_label, format_group_name, format_person_name, format_room_name
from ..utils.group_audience import resolve_slot_audience_labels


class ExportService:
    """Builds the timetable grid dict used by all export generators."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_traditional_export_data(self, timetable_id: int, university_id=None) -> Dict[str, Any]:
        timetable: Optional[Timetable] = (
            self.db.query(Timetable)
            .filter(Timetable.id == timetable_id)
            .first()
        )
        if timetable is None:
            raise ValueError(f"Timetable {timetable_id} not found.")

        # Ownership check - reject cross-tenant access
        if university_id is not None and timetable.university_id != university_id:
            raise PermissionError("You do not have access to this timetable.")

        slots = (
            self.db.query(TimetableSlot)
            .filter(TimetableSlot.timetable_id == timetable_id)
            .all()
        )
        return self._build_grid(timetable, slots)

    def get_active_timetable_export_data(self, university_id=None) -> Dict[str, Any]:
        query = self.db.query(Timetable).filter(Timetable.is_active == True)
        if university_id is not None:
            query = query.filter(Timetable.university_id == university_id)
        timetable: Optional[Timetable] = query.first()
        if timetable is None:
            raise ValueError("No active timetable found. Activate a timetable first.")

        slots = (
            self.db.query(TimetableSlot)
            .filter(TimetableSlot.timetable_id == timetable.id)
            .all()
        )
        return self._build_grid(timetable, slots)

    def _get_university_id(self) -> Optional[int]:
        """Attempt to resolve a university id from context — returns None if not scoped."""
        return None  # No tenant filtering for direct ID lookups

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_grid(
        self, timetable: Timetable, slots: list[TimetableSlot]
    ) -> Dict[str, Any]:
        _DAY_NAMES = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]

        grid: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        group_cache: Dict[int, StudentGroup] = {}
        stream_children_cache: Dict[int, list[StudentGroup]] = {}

        for slot in slots:
            course: Optional[Course] = (
                self.db.query(Course).filter(Course.id == slot.course_id).first()
            )
            room: Optional[Room] = (
                self.db.query(Room).filter(Room.id == slot.room_id).first() if slot.room_id else None
            )
            group: Optional[StudentGroup] = (
                self.db.query(StudentGroup).filter(StudentGroup.id == slot.group_id).first()
            )
            lecturer: Optional[Lecturer] = (
                self.db.query(Lecturer).filter(Lecturer.id == slot.lecturer_id).first()
                if slot.lecturer_id else None
            )

            # Course and group are mandatory; room and lecturer can be TBD
            if not course or not group:
                continue

            col_key = self._determine_column_key(group, course)
            day_name = _DAY_NAMES[slot.day_of_week]
            start_hour = slot.start_time.strftime("%H:%M")
            audience_names = resolve_slot_audience_labels(
                self.db,
                slot,
                group_cache=group_cache,
                stream_children_cache=stream_children_cache,
            ) or [format_group_label(group, prefer_code=True)]
            audience_names = [format_group_name(name) for name in audience_names if name]

            grid[day_name][start_hour][col_key].append(
                {
                    "course_code": course.code,
                    "room_name": format_room_name(room.name) if room else "TBA",
                    "group_name": " + ".join(audience_names),
                    "lecturer_name": format_person_name(lecturer.full_name) if lecturer else "TBA",
                    "session_type": slot.session_type,
                }
            )

        return {
            "timetable_name": timetable.name,
            "semester": timetable.semester,
            "year": timetable.year,
            "academic_half": getattr(timetable, "academic_half", "first_half"),
            "university_name": self._resolve_university_name(timetable),
            "university_short_name": self._resolve_university_short_name(timetable),
            "grid_data": grid,
        }

    def _resolve_university_name(self, timetable: Timetable) -> str:
        if getattr(timetable, "university_id", None):
            university = (
                self.db.query(University)
                .filter(University.id == timetable.university_id)
                .first()
            )
            if university and university.name:
                return university.name
        return settings.UNIVERSITY_NAME

    def _resolve_university_short_name(self, timetable: Timetable) -> str:
        if getattr(timetable, "university_id", None):
            university = (
                self.db.query(University)
                .filter(University.id == timetable.university_id)
                .first()
            )
            if university and university.short_name:
                return university.short_name
            if university and university.name:
                return university.name
        return settings.UNIVERSITY_SHORT_NAME

    def _determine_column_key(self, group: StudentGroup, course: Course) -> str:
        """Map a student group to its column key in the traditional grid."""
        if group.level == 2:
            if "LG1" in group.name or "GEN1" in group.name:
                return "GEN LG1"
            return "GEN LG2"

        dept_code = group.department.code if group.department else "UNK"
        return f"{group.level}-{dept_code}"

