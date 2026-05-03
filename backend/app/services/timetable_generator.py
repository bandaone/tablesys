import json
from collections import defaultdict
from ortools.sat.python import cp_model
from sqlalchemy.orm import Session
from typing import Dict, Callable, List, Optional, Any, Tuple, Set
from datetime import time
from ..models import (
    Timetable, TimetableSlot, Room, Course, Lecturer,
    StudentGroup, GroupAssignment, LecturerAssignment,
    RoomType, UserRole, CourseType, CourseGroupLink
)
from ..utils.department_utils import is_general_department
from ..utils.room_matching import room_match_rank, room_type_matches


class TimetableGenerator:
    def __init__(self, db: Session, timetable_id: int, progress_callback: Callable = None, components: list = None):
        self.db = db
        self.timetable_id = timetable_id
        self.progress_callback = progress_callback
        self.requested_components = list(components) if components else None
        self.components = list(components) if components else None

        # Load grid configuration from timetable record.
        # The current API stores this under generation_metadata.grid_config.
        timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
        metadata = (getattr(timetable, 'generation_metadata', None) or {}) if timetable else {}
        metadata_grid = metadata.get('grid_config') if isinstance(metadata, dict) else None
        model_grid = getattr(timetable, 'grid_config', None) if timetable else None

        grid_config: Dict[str, Any] = {}
        if isinstance(metadata_grid, dict):
            grid_config.update(metadata_grid)
        if isinstance(model_grid, dict):
            # Prefer explicit model values when present, but keep metadata fallback.
            grid_config.update(model_grid)

        active_days = grid_config.get('active_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
        if not isinstance(active_days, list) or not active_days:
            active_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

        start_raw = grid_config.get('start_time', '07:00')
        end_raw = grid_config.get('end_time', '17:00')

        def _extract_hour(value: Any, default: int) -> int:
            if value is None:
                return default
            if hasattr(value, 'hour'):
                try:
                    return int(value.hour)
                except Exception:
                    return default
            text = str(value).strip()
            if ':' in text:
                text = text.split(':', 1)[0]
            try:
                return int(text)
            except Exception:
                return default

        self.start_hour = _extract_hour(start_raw, 7)
        end_hour = _extract_hour(end_raw, 17)
        self.lunch_start_hour = _extract_hour(grid_config.get('lunch_start', '13:00'), 13)
        self.lunch_end_hour = _extract_hour(grid_config.get('lunch_end', '14:00'), 14)
        if end_hour <= self.start_hour:
            end_hour = self.start_hour + 1
        if self.lunch_end_hour <= self.lunch_start_hour:
            self.lunch_start_hour = 13
            self.lunch_end_hour = 14
        self.days = active_days

        num_slots = end_hour - self.start_hour
        self.time_slots = [
            (time(self.start_hour + i, 0), time(self.start_hour + i + 1, 0))
            for i in range(num_slots)
        ]
        self.num_slots = num_slots

        self.all_slots: List[Dict] = []
        self.existing_slots: List[Dict] = []
        self.generation_diagnostics: List[Dict] = []
        self.solver_status_by_level: Dict[str, str] = {}
        self.fallback_levels: List[str] = []
        self.saved_slot_annotations: List[Dict[str, Any]] = []
        self.cleared_slot_counts: Dict[str, Any] = {}
        # Institutional fallback policy: if no room can fully fit a class,
        # prefer the biggest acceptable room instead of pretending a much
        # smaller room is a better compromise.
        self.prefer_largest_room_for_oversized = True
        # Fallback rooms must still be large enough to host a realistic
        # portion of the class. This blocks absurd assignments such as
        # placing 650 students into a 50-seat room.
        self.oversized_room_min_attendance_ratio = 0.50

    @staticmethod
    def _session_requires_room(session_type: Optional[str]) -> bool:
        return str(session_type or "").strip().lower() not in {"practical", "lab"}

    def _capacity_penalty(self, required_size: int, room_capacity: Optional[int]) -> int:
        capacity = room_capacity or 0
        if capacity >= required_size:
            return capacity - required_size
        return (required_size - capacity) * 1000

    def _minimum_acceptable_fallback_capacity(self, required_size: int) -> int:
        if required_size <= 0:
            return 0
        return max(1, int(required_size * self.oversized_room_min_attendance_ratio))

    def _room_meets_fallback_capacity(self, required_size: int, room_capacity: Optional[int]) -> bool:
        if not room_capacity:
            return True
        return room_capacity >= self._minimum_acceptable_fallback_capacity(required_size)

    def _rank_rooms_for_requirement(
        self,
        rooms: List[Room],
        required_size: int,
        *,
        room_load_hours: Optional[Dict[int, int]] = None,
        oversized_only: bool = False,
        match_rank_lookup: Optional[Dict[int, int]] = None,
    ) -> List[Room]:
        load_lookup = room_load_hours or {}
        rank_lookup = match_rank_lookup or {}

        if oversized_only and self.prefer_largest_room_for_oversized:
            return sorted(
                rooms,
                key=lambda room: (
                    rank_lookup.get(room.id, 99),
                    -(room.capacity or 0),
                    load_lookup.get(room.id, 0),
                    -(getattr(room, 'priority_level', 5) or 5),
                ),
            )

        return sorted(
            rooms,
            key=lambda room: (
                rank_lookup.get(room.id, 99),
                load_lookup.get(room.id, 0),
                self._capacity_penalty(required_size, room.capacity),
                -(getattr(room, 'priority_level', 5) or 5),
                -(room.capacity or 0),
            ),
        )

    def _lunch_window_indices(self) -> Optional[Tuple[int, int]]:
        lunch_start_idx = self.lunch_start_hour - self.start_hour
        lunch_end_idx = self.lunch_end_hour - self.start_hour
        if lunch_end_idx <= lunch_start_idx:
            return None
        if lunch_end_idx <= 0 or lunch_start_idx >= self.num_slots:
            return None
        return max(0, lunch_start_idx), min(self.num_slots, lunch_end_idx)

    def _overlaps_lunch(self, start_idx: int, duration: int) -> bool:
        lunch_window = self._lunch_window_indices()
        if not lunch_window:
            return False
        lunch_start_idx, lunch_end_idx = lunch_window
        session_end_idx = start_idx + duration
        return start_idx < lunch_end_idx and session_end_idx > lunch_start_idx

    def _component_sequence(self) -> List[str]:
        """Return generation layers in the order they should be scheduled."""
        selected = self.requested_components or ['lecture', 'practical', 'tutorial']
        normalized = []
        for component in selected:
            name = str(component).strip().lower()
            if name in {'lecture', 'practical', 'tutorial'} and name not in normalized:
                normalized.append(name)
        return normalized or ['lecture', 'practical', 'tutorial']

    def _active_component_name(self) -> str:
        selected = self._selected_components()
        if selected and len(selected) == 1:
            return next(iter(selected))
        return 'all'

    def _scope_key(self, level: int) -> str:
        return f"{level}:{self._active_component_name()}"

    def _selected_components(self) -> Optional[Set[str]]:
        """Normalize optional component selection into a lowercase set."""
        if not self.components:
            return None
        return {str(component).strip().lower() for component in self.components if str(component).strip()}

    def _session_frequency(self, config: Dict[str, Any], session_type: str, default: int) -> int:
        """Read weekly frequency from config with a clear operational default."""
        key = f"{session_type}_sessions"
        try:
            frequency = int(config.get(key, default))
        except (TypeError, ValueError):
            frequency = default
        return max(frequency, 0)

    def _normalize_shared_group_ids(self, value: Any) -> List[int]:
        """Return shared group ids as a plain list regardless of legacy storage shape."""
        if not value:
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [int(v) for v in parsed]
            except Exception:
                return []
        return []

    def _slots_overlap(self, day_idx: int, start_hour: int, end_hour: int, slot: Dict) -> bool:
        """Check whether a candidate placement overlaps an existing booking."""
        if slot['day_of_week'] != day_idx:
            return False
        slot_start = self._time_to_idx(slot['start_time'])
        slot_end = self._time_to_idx(slot['end_time'])
        return start_hour < slot_end and end_hour > slot_start

    def _resource_blocked(self, resource_kind: str, resource_id: int, day_idx: int,
                          start_hour: int, end_hour: int) -> bool:
        """Check whether a room, lecturer, or group is already blocked by prior placements."""
        if resource_id is None:
            return False

        for slot in self.all_slots + self.existing_slots:
            if not self._slots_overlap(day_idx, start_hour, end_hour, slot):
                continue

            if resource_kind == 'room' and slot.get('room_id') == resource_id:
                return True
            if resource_kind == 'lecturer' and slot.get('lecturer_id') == resource_id:
                return True
            if resource_kind == 'group':
                if slot.get('group_id') == resource_id:
                    return True
                if resource_id in self._normalize_shared_group_ids(slot.get('shared_group_ids')):
                    return True
                if resource_id in self._normalize_shared_group_ids(slot.get('rotation_group_ids')):
                    return True
        return False

    def _diagnose_zero_candidate_session(
        self,
        level: int,
        course: Course,
        session_type: str,
        duration: int,
        primary_group_id: int,
        covered_group_ids: List[int],
        group_size_required: int,
        all_rooms: List[Room],
        lecturer_ids: List[Optional[int]],
    ) -> Dict[str, Any]:
        """
        Explain why a session instance produced zero legal variables under hard constraints.
        """
        diagnostic: Dict[str, Any] = {
            'level': level,
            'course_id': course.id,
            'course_code': course.code,
            'session_type': session_type,
            'duration_hours': duration,
            'primary_group_id': primary_group_id,
            'covered_group_ids': list(covered_group_ids),
            'group_size_required': group_size_required,
            'reason_code': 'no_candidates',
            'reason': 'No legal placements found under current hard constraints.',
        }

        if duration > self.num_slots:
            diagnostic['reason_code'] = 'duration_exceeds_day'
            diagnostic['reason'] = 'Session duration exceeds the configured timetable day length.'
            return diagnostic

        if not all_rooms:
            diagnostic['reason_code'] = 'no_rooms_defined'
            diagnostic['reason'] = 'No rooms are available in the dataset.'
            return diagnostic

        compatible_room_count = 0
        candidate_windows = 0
        room_filter_blocked = 0
        room_booking_blocked = 0
        lecturer_booking_blocked = 0
        group_booking_blocked = 0

        for day_idx in range(len(self.days)):
            for start_t in range(self.num_slots - duration + 1):
                if self._overlaps_lunch(start_t, duration):
                    continue

                start_hour = self.start_hour + start_t
                end_hour = start_hour + duration
                compat_rooms = self._get_compatible_rooms(
                    course, session_type, group_size_required, all_rooms, day_idx, start_hour, end_hour
                )

                if compat_rooms:
                    compatible_room_count += len(compat_rooms)
                else:
                    room_filter_blocked += 1
                    continue

                if any(self._resource_blocked('group', gid, day_idx, start_t, start_t + duration)
                       for gid in covered_group_ids):
                    group_booking_blocked += 1
                    continue

                window_has_candidate = False
                room_free_found = False
                lecturer_free_found = False

                for room_entry in compat_rooms:
                    room = room_entry['room']
                    if self._resource_blocked('room', room.id, day_idx, start_t, start_t + duration):
                        continue
                    room_free_found = True

                    for lecturer_id in lecturer_ids:
                        if lecturer_id is not None and self._resource_blocked(
                            'lecturer', lecturer_id, day_idx, start_t, start_t + duration
                        ):
                            continue
                        lecturer_free_found = True
                        window_has_candidate = True
                        break

                    if window_has_candidate:
                        break

                if window_has_candidate:
                    candidate_windows += 1
                elif not room_free_found:
                    room_booking_blocked += 1
                elif not lecturer_free_found:
                    lecturer_booking_blocked += 1

        if candidate_windows > 0:
            diagnostic['reason_code'] = 'solver_global_conflict'
            diagnostic['reason'] = (
                'Local placement windows exist, but the full model became infeasible after combining all hard constraints.'
            )
        elif room_filter_blocked > 0 and compatible_room_count == 0:
            diagnostic['reason_code'] = 'no_compatible_room'
            diagnostic['reason'] = 'No room satisfies the required type, capacity, and room-level availability.'
        elif group_booking_blocked > 0:
            diagnostic['reason_code'] = 'group_blocked_by_existing_slots'
            diagnostic['reason'] = 'The target group is already fully blocked by existing or previously placed sessions.'
        elif room_booking_blocked > 0:
            diagnostic['reason_code'] = 'rooms_blocked_by_existing_slots'
            diagnostic['reason'] = 'Compatible rooms exist, but all are blocked by existing or previously placed sessions.'
        elif lecturer_booking_blocked > 0:
            diagnostic['reason_code'] = 'lecturers_blocked_by_existing_slots'
            diagnostic['reason'] = 'Available lecturer assignments exist, but all are blocked by existing or previously placed sessions.'

        diagnostic['window_summary'] = {
            'candidate_windows': candidate_windows,
            'room_filter_blocked_windows': room_filter_blocked,
            'group_blocked_windows': group_booking_blocked,
            'room_blocked_windows': room_booking_blocked,
            'lecturer_blocked_windows': lecturer_booking_blocked,
        }
        return diagnostic

    def _record_level_diagnostic(self, level: int, solver_status: Optional[str] = None,
                                 unschedulable_sessions: Optional[List[Dict[str, Any]]] = None,
                                 placed_slots: Optional[int] = None,
                                 attempted_slots: Optional[int] = None):
        """Store per-level feasibility information for later inspection or UI surfacing."""
        if unschedulable_sessions is None:
            unschedulable_sessions = []

        level_values = self._level_values(level)
        level_courses = self.db.query(Course).filter(Course.level.in_(level_values)).all()
        level_groups = self.db.query(StudentGroup).filter(StudentGroup.level.in_(level_values)).all()
        group_weekly_load = {g.id: 0 for g in level_groups}
        course_breakdown = []

        for course in level_courses:
            sessions = self._parse_course_sessions(course)
            total_course_hours = sum(s['duration'] for s in sessions)
            course_breakdown.append({
                'course_id': course.id,
                'course_code': course.code,
                'session_count': len(sessions),
                'weekly_hours': total_course_hours,
            })
            ga_rows = self.db.query(GroupAssignment).filter(GroupAssignment.course_id == course.id).all()
            for ga in ga_rows:
                if ga.group_id in group_weekly_load:
                    group_weekly_load[ga.group_id] += total_course_hours

        level_report = {
            'level': level,
            'component': self._active_component_name(),
            'scope_key': self._scope_key(level),
            'solver_status': solver_status or self.solver_status_by_level.get(self._scope_key(level)),
            'daily_hard_cap_hours': 10,
            'placed_slots': placed_slots,
            'attempted_slots': attempted_slots,
            'weekly_group_load_hours': [
                {
                    'group_id': g.id,
                    'group_name': g.name,
                    'weekly_hours': group_weekly_load.get(g.id, 0),
                }
                for g in level_groups
            ],
            'courses': course_breakdown,
            'unschedulable_sessions': unschedulable_sessions,
        }

        self.generation_diagnostics = [
            d for d in self.generation_diagnostics
            if not (d.get('level') == level and d.get('component') == self._active_component_name())
        ]
        self.generation_diagnostics.append(level_report)

    def send_progress(self, level: int, status: str, percentage: float, message: str):
        """Send progress update via callback"""
        if self.progress_callback:
            self.progress_callback({
                'level': level,
                'status': status,
                'percentage': min(max(round(float(percentage), 1), 0.0), 100.0),
                'message': message
            })

    def generate_timetable(self) -> bool:
        """Generate timetable level-by-level and component-by-component."""
        level_rows = self.db.query(Course.level).distinct().all()
        levels = sorted({r[0] for r in level_rows if r[0]}, reverse=True)
        if not levels:
            self.send_progress(0, 'success', 100, 'No scheduled courses found. Nothing to process.')
            return True
        component_layers = self._component_sequence()

        existing_db_slots = self.db.query(TimetableSlot).filter(
            TimetableSlot.timetable_id == self.timetable_id
        ).all()

        replacement_components = set(component_layers) if self.requested_components else None
        preserved_slots: List[TimetableSlot] = []
        cleared_count = 0
        for slot in existing_db_slots:
            should_replace = (
                replacement_components is None or
                slot.session_type in replacement_components
            )
            if should_replace:
                self.db.delete(slot)
                cleared_count += 1
                continue
            preserved_slots.append(slot)

        self.db.flush()
        self.cleared_slot_counts = {
            'mode': 'partial' if replacement_components is not None else 'full',
            'cleared_slots': cleared_count,
            'preserved_slots': len(preserved_slots),
        }

        for slot in preserved_slots:
            self.existing_slots.append({
                'course_id': slot.course_id,
                'lecturer_id': slot.lecturer_id,
                'room_id': slot.room_id,
                'group_id': slot.group_id,
                'day_of_week': slot.day_of_week,
                'start_time': slot.start_time,
                'end_time': slot.end_time,
                'session_type': slot.session_type,
                'shared_group_ids': slot.shared_group_ids,
                'combined_size': slot.combined_size,
                'shared_batch_id': slot.shared_batch_id,
            })

        total_units = max(len(levels) * len(component_layers), 1)
        unit_idx = 0
        for level in levels:
            for component in component_layers:
                self.components = [component]
                unit_pct_start = (unit_idx / total_units) * 100
                unit_pct_end = ((unit_idx + 1) / total_units) * 100

                self.send_progress(level, 'starting', unit_pct_start,
                                   f'Processing Year {level} {component}s...')

                success = self.generate_level_timetable(level, unit_pct_start, unit_pct_end)

                if not success:
                    self.fallback_levels.append(self._scope_key(level))
                    self.send_progress(level, 'retrying', unit_pct_start,
                                       f'Year {level} {component}s: Applying extended scheduling strategy...')
                    success = self.generate_level_timetable_greedy(level)

                if not success:
                    self.send_progress(level, 'failed', unit_pct_start,
                                       f'Year {level} {component}s: Unable to produce a valid schedule.')
                    return False

                self.send_progress(level, 'completed', unit_pct_end,
                                   f'Year {level} {component}s ready.')
                unit_idx += 1

        self.send_progress(0, 'finalizing', 95, 'Finalising and saving timetable...')
        self.save_timetable()
        self.send_progress(0, 'success', 100, 'Timetable generated successfully!')
        return True

    def _parse_course_sessions(self, course: Course) -> List[Dict]:
        """
        Interpret lecture/tutorial/practical hours as the duration of ONE session.

        Operational defaults reflect the manual timetable process:
        - lecture:   2 sessions/week
        - tutorial:  1 session/week
        - practical: 1 session/week

        session_configuration may override weekly frequency explicitly.
        """
        sessions = []
        config = course.session_configuration or {}
        selected_components = self._selected_components()

        # --- Lectures ---
        duration = course.lecture_hours or 0
        if duration > 0 and (selected_components is None or 'lecture' in selected_components):
            frequency = self._session_frequency(config, 'lecture', 2)
            for _ in range(frequency):
                sessions.append({
                    'type': 'lecture',
                    'duration': duration,
                    'course_id': course.id,
                    's_id': len(sessions)
                })

        # --- Tutorials ---
        tut_hours = course.tutorial_hours or 0
        if tut_hours > 0 and (selected_components is None or 'tutorial' in selected_components):
            tut_freq = self._session_frequency(config, 'tutorial', 1)
            for _ in range(tut_freq):
                sessions.append({
                    'type': 'tutorial',
                    'duration': tut_hours,
                    'course_id': course.id,
                    's_id': len(sessions)
                })

        # --- Practicals ---
        prac_hours = course.practical_hours or 0
        if prac_hours > 0 and (selected_components is None or 'practical' in selected_components):
            prac_freq = self._session_frequency(config, 'practical', 1)
            for _ in range(prac_freq):
                sessions.append({
                    'type': 'practical',
                    'duration': prac_hours,
                    'course_id': course.id,
                    's_id': len(sessions)
                })

        return sessions

    def _build_level_group_context(self, level: int) -> Dict[str, Any]:
        """Load all groups for a level and index them by parent/type."""
        level_groups = (
            self.db.query(StudentGroup)
            .filter(StudentGroup.level.in_(self._level_values(level)))
            .all()
        )
        groups_by_id = {g.id: g for g in level_groups}
        children_by_parent: Dict[int, List[StudentGroup]] = defaultdict(list)
        children_by_parent_type: Dict[Tuple[int, str], List[StudentGroup]] = defaultdict(list)

        for group in level_groups:
            if group.parent_group_id is None:
                continue
            children_by_parent[group.parent_group_id].append(group)
            children_by_parent_type[(group.parent_group_id, self._group_type_value(group))].append(group)

        descendants_by_group: Dict[int, Set[int]] = defaultdict(set)
        ancestors_by_group: Dict[int, Set[int]] = defaultdict(set)
        
        for group in level_groups:
            current_group = group
            while current_group and current_group.parent_group_id:
                parent_id = current_group.parent_group_id
                ancestors_by_group[group.id].add(parent_id)
                descendants_by_group[parent_id].add(group.id)
                current_group = groups_by_id.get(parent_id)

        return {
            'all_groups': level_groups,
            'main_groups': [g for g in level_groups if g.parent_group_id is None],
            'groups_by_id': groups_by_id,
            'children_by_parent': children_by_parent,
            'children_by_parent_type': children_by_parent_type,
            'group_size_map': {g.id: (g.size or 30) for g in level_groups},
            'descendants_by_group': descendants_by_group,
            'ancestors_by_group': ancestors_by_group,
        }

    def _lecturer_ids_for_session(self, course_id: int, session_type: str) -> List[Optional[int]]:
        """Prefer session-specific lecturer assignments, then generic ones."""
        assignments = self.db.query(LecturerAssignment).filter(
            LecturerAssignment.course_id == course_id
        ).all()
        exact = [a.lecturer_id for a in assignments if (a.session_type or '').strip().lower() == session_type]
        generic = [a.lecturer_id for a in assignments if not a.session_type]

        ordered: List[Optional[int]] = []
        for lecturer_id in exact + generic:
            if lecturer_id not in ordered:
                ordered.append(lecturer_id)
        return ordered or [None]

    def _build_explicit_session_units(
        self,
        course: Course,
        session_type: str,
        groups_by_id: Dict[int, StudentGroup],
        group_size_map: Dict[int, int],
    ) -> List[Dict[str, Any]]:
        """Use explicit CourseGroupLink rows literally for lecture only."""
        if session_type != 'lecture':
            return []

        links = self.db.query(CourseGroupLink).filter(
            CourseGroupLink.course_id == course.id,
            CourseGroupLink.session_type == session_type
        ).all()
        if not links:
            return []

        batch_map: Dict[Any, List[int]] = defaultdict(list)
        for link in links:
            if link.group_id in groups_by_id:
                key = link.shared_batch_id if link.is_shared else f'_solo_{link.group_id}'
                batch_map[key].append(link.group_id)

        units = []
        for batch_key, group_ids in batch_map.items():
            if not group_ids:
                continue
            is_shared = len(group_ids) > 1 and not str(batch_key).startswith('_solo_')
            units.append({
                'primary_group_id': group_ids[0],
                'covered_group_ids': list(group_ids),
                'group_size_required': (
                    sum(group_size_map.get(gid, 30) for gid in group_ids)
                    if is_shared else group_size_map.get(group_ids[0], 30)
                ),
                'grouping_mode': 'shared' if is_shared else 'single',
                'shared_batch_id': batch_key if is_shared else None,
                'rotation_group_ids': None,
                'rotation_cycle_weeks': None,
            })
        return units

    def _resolve_default_lecture_units(
        self,
        course: Course,
        group_ctx: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Resolve lecture audience from explicit group assignments.

        Rule:
        - If the course is assigned directly to stream groups, treat it as
          stream-specific/elective and schedule each stream explicitly.
        - Otherwise, keep the parent/main group combined. This makes common
          courses stay together even when streams exist under the cohort.
        """
        group_size_map = group_ctx['group_size_map']
        groups_by_id = group_ctx['groups_by_id']

        ga_rows = self.db.query(GroupAssignment).filter(GroupAssignment.course_id == course.id).all()
        assigned_groups = []
        stream_assigned_parent_ids: Set[int] = set()
        for ga in ga_rows:
            group = groups_by_id.get(ga.group_id)
            if not group:
                continue
            assigned_groups.append(group)
            if self._group_type_value(group) == 'stream' and group.parent_group_id:
                stream_assigned_parent_ids.add(group.parent_group_id)

        seen = set()
        stream_groups_by_parent: Dict[int, List[StudentGroup]] = defaultdict(list)
        non_stream_groups: List[StudentGroup] = []

        for group in assigned_groups:
            if group.id in seen:
                continue
            seen.add(group.id)

            if self._group_type_value(group) == 'stream' and group.parent_group_id:
                stream_groups_by_parent[group.parent_group_id].append(group)
                continue

            # Once stream-specific assignments exist for a parent cohort, the
            # parent assignment becomes informational and should not create an
            # extra duplicate lecture slot.
            if group.id in stream_assigned_parent_ids:
                continue

            non_stream_groups.append(group)

        units = []
        for group in non_stream_groups:
            units.append({
                'primary_group_id': group.id,
                'covered_group_ids': [group.id],
                'group_size_required': group_size_map.get(group.id, 30),
                'grouping_mode': 'single',
                'shared_batch_id': None,
                'rotation_group_ids': None,
                'rotation_cycle_weeks': None,
            })

        for parent_group_id, stream_groups in stream_groups_by_parent.items():
            covered_group_ids = [group.id for group in stream_groups]
            if len(covered_group_ids) > 1:
                units.append({
                    'primary_group_id': covered_group_ids[0],
                    'covered_group_ids': covered_group_ids,
                    'group_size_required': sum(group_size_map.get(group_id, 30) for group_id in covered_group_ids),
                    'grouping_mode': 'shared',
                    'shared_batch_id': None,
                    'rotation_group_ids': None,
                    'rotation_cycle_weeks': None,
                })
            else:
                group = stream_groups[0]
                units.append({
                    'primary_group_id': group.id,
                    'covered_group_ids': [group.id],
                    'group_size_required': group_size_map.get(group.id, 30),
                    'grouping_mode': 'single',
                    'shared_batch_id': None,
                    'rotation_group_ids': None,
                    'rotation_cycle_weeks': None,
                })
        if self._should_auto_share_lecture(course, units):
            covered_group_ids: List[int] = []
            combined_size = 0
            for unit in units:
                for covered_group_id in unit.get('covered_group_ids', [unit['primary_group_id']]):
                    if covered_group_id not in covered_group_ids:
                        covered_group_ids.append(covered_group_id)
                        combined_size += group_size_map.get(covered_group_id, 30)

            if len(covered_group_ids) > 1:
                return [{
                    'primary_group_id': covered_group_ids[0],
                    'covered_group_ids': covered_group_ids,
                    'group_size_required': combined_size,
                    'grouping_mode': 'shared',
                    'shared_batch_id': None,
                    'rotation_group_ids': None,
                    'rotation_cycle_weeks': None,
                }]

        return units

    def _should_auto_share_lecture(self, course: Course, units: List[Dict[str, Any]]) -> bool:
        """
        Infer a shared lecture when course metadata says the audience spans
        multiple departments/groups and no explicit shared links were configured.
        """
        if len(units) <= 1:
            return False

        if is_general_department(getattr(course, 'department', None)):
            return True

        if course.course_type in {CourseType.GENERAL, CourseType.MULTI_DEPARTMENT}:
            return True

        return bool(course.shared_with_department_ids)

    def _resolve_session_units(
        self,
        course: Course,
        session_type: str,
        group_ctx: Dict[str, Any],
        lecture_units: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Resolve the real teaching audience for one session layer.

        Lecture:
        - explicit lecture links if present
        - otherwise assigned main groups, split into streams where streams exist

        Tutorial:
        - explicit tutorial links if present
        - otherwise tutorial subgroups under the lecture audience
        - otherwise the lecture audience itself

        Practical:
        - explicit practical links if present
        - otherwise lab/drawing subgroups under the lecture audience
        - if multiple lab groups exist for the same audience, create one rotating slot
        """
        groups_by_id = group_ctx['groups_by_id']
        group_size_map = group_ctx['group_size_map']
        children_by_parent_type = group_ctx['children_by_parent_type']

        explicit_units = self._build_explicit_session_units(course, session_type, groups_by_id, group_size_map)
        if explicit_units:
            return explicit_units

        if session_type == 'lecture':
            return self._resolve_default_lecture_units(course, group_ctx)

        lecture_units = lecture_units or self._resolve_session_units(course, 'lecture', group_ctx, [])
        base_group_ids: List[int] = []
        for unit in lecture_units:
            for group_id in unit.get('covered_group_ids', [unit['primary_group_id']]):
                if group_id not in base_group_ids:
                    base_group_ids.append(group_id)

        resolved_units: List[Dict[str, Any]] = []
        for base_group_id in base_group_ids:
            if session_type == 'tutorial':
                subgroup_candidates = children_by_parent_type.get((base_group_id, 'tutorial_group'), [])
                if subgroup_candidates:
                    for subgroup in subgroup_candidates:
                        resolved_units.append({
                            'primary_group_id': subgroup.id,
                            'covered_group_ids': [subgroup.id],
                            'group_size_required': group_size_map.get(subgroup.id, 30),
                            'grouping_mode': 'single',
                            'shared_batch_id': None,
                            'rotation_group_ids': None,
                            'rotation_cycle_weeks': None,
                        })
                else:
                    resolved_units.append({
                        'primary_group_id': base_group_id,
                        'covered_group_ids': [base_group_id],
                        'group_size_required': group_size_map.get(base_group_id, 30),
                        'grouping_mode': 'single',
                        'shared_batch_id': None,
                        'rotation_group_ids': None,
                        'rotation_cycle_weeks': None,
                    })
                continue

            practical_subgroups = (
                children_by_parent_type.get((base_group_id, 'lab_group'), []) +
                children_by_parent_type.get((base_group_id, 'drawing_group'), [])
            )
            if len(practical_subgroups) > 1:
                subgroup_ids = [g.id for g in practical_subgroups]
                resolved_units.append({
                    'primary_group_id': subgroup_ids[0],
                    'covered_group_ids': list(subgroup_ids),
                    'group_size_required': max(group_size_map.get(gid, 30) for gid in subgroup_ids),
                    'grouping_mode': 'rotating',
                    'shared_batch_id': None,
                    'rotation_group_ids': subgroup_ids,
                    'rotation_cycle_weeks': len(subgroup_ids),
                })
            elif len(practical_subgroups) == 1:
                subgroup = practical_subgroups[0]
                resolved_units.append({
                    'primary_group_id': subgroup.id,
                    'covered_group_ids': [subgroup.id],
                    'group_size_required': group_size_map.get(subgroup.id, 30),
                    'grouping_mode': 'single',
                    'shared_batch_id': None,
                    'rotation_group_ids': None,
                    'rotation_cycle_weeks': None,
                })
            else:
                resolved_units.append({
                    'primary_group_id': base_group_id,
                    'covered_group_ids': [base_group_id],
                    'group_size_required': group_size_map.get(base_group_id, 30),
                    'grouping_mode': 'single',
                    'shared_batch_id': None,
                    'rotation_group_ids': None,
                    'rotation_cycle_weeks': None,
                })
        return resolved_units

    def _get_compatible_rooms(self, course: Course, session_type: str,
                              group_size: int, all_rooms: List[Room],
                              day_idx: int, start_hour: int, end_hour: int) -> List[Dict]:
        """
        Filter rooms by type, capacity, and availability window.
        Returns list of dicts: {'room': Room, 'capacity_penalty': int}
        so the penalty is captured at query time, not mutated onto the ORM object.
        """
        # Fix #3: Accept day+time to check room availability blocks
        compatible = []
        for room in all_rooms:
            # Type match
            match_rank = room_match_rank(
                course.preferred_room_type,
                session_type,
                room.room_type,
                group_size=group_size,
            )
            if match_rank is None:
                continue

            # Oversized fallback still needs a realistic lower bound.
            if not self._room_meets_fallback_capacity(group_size, room.capacity):
                continue
            
            # Room availability_blocks: list of {day, start, end} dicts where room is UNAVAILABLE
            if room.availability_blocks:
                day_name = self.days[day_idx]
                blocked = False
                for block in room.availability_blocks:
                    if block.get('day') == day_name:
                        b_start = int(str(block.get('start', '00:00')).split(':')[0])
                        b_end = int(str(block.get('end', '00:00')).split(':')[0])
                        # Session overlaps block?
                        if start_hour < b_end and end_hour > b_start:
                            blocked = True
                            break
                if blocked:
                    continue

            capacity = room.capacity or 0
            penalty = self._capacity_penalty(group_size, capacity)
            compatible.append({'room': room, 'capacity_penalty': penalty, 'match_rank': match_rank})
        return sorted(
            compatible,
            key=lambda entry: (
                entry['match_rank'],
                entry['capacity_penalty'],
                -(entry['room'].capacity or 0),
                -(getattr(entry['room'], 'priority_level', 5) or 5),
            ),
        )

    def _is_lecturer_available(self, lecturer: Lecturer, day_idx: int,
                                start_hour: int, end_hour: int) -> bool:
        """
        Check lecturer hard availability.
        The Lecturer model stores unavailability as a relationship (not a column).
        teaching_preferences handles soft preferences via the objective.
        Hard day/time blocking via unavailability rows is handled by the
        external slot checks in C3. This method always returns True — 
        the solver's double-booking constraints (C3) already prevent conflicts.
        """
        return lecturer is not None

    def generate_level_timetable(self, level: int, progress_start: float, progress_end: float) -> bool:
        """Generate timetable for a specific level using CP-SAT solver"""
        range_span = progress_end - progress_start

        courses = self.db.query(Course).filter(Course.level.in_(self._level_values(level))).all()
        if not courses:
            return True

        group_ctx = self._build_level_group_context(level)
        if not group_ctx['all_groups']:
            return True
        all_rooms = self.db.query(Room).all()
        group_size_map = group_ctx['group_size_map']

        self.send_progress(level, 'building', progress_start + range_span * 0.1,
                           f'Year {level} {self._active_component_name()}s: Analysing course and resource data...')

        model = cp_model.CpModel()
        vars_store = {}
        var_meta: Dict[Tuple[int, int, int, int, int, int, Optional[int]], Dict[str, Any]] = {}
        # Used for C4 to know which variables conflict
        var_group_map: Dict[str, List[int]] = {}
        course_sessions: Dict[int, List[Dict]] = {}
        unschedulable_sessions: List[Dict[str, Any]] = []
        room_candidate_vars: Dict[int, List[Any]] = {}
        lecturer_candidate_vars: Dict[int, List[Any]] = {}

        # ── 1. Create Variables ─────────────────────────────────────────────
        for course in courses:
            sessions = self._parse_course_sessions(course)
            course_sessions[course.id] = sessions
            lecture_units = self._resolve_session_units(course, 'lecture', group_ctx)

            for session in sessions:
                duration = session['duration']
                s_id = session['s_id']
                session_type = session['type']
                lecturer_ids = self._lecturer_ids_for_session(course.id, session_type)
                session_units = self._resolve_session_units(course, session_type, group_ctx, lecture_units)

                if not session_units:
                    continue

                for unit in session_units:
                    group_id = unit['primary_group_id']
                    covered_group_ids = list(unit['covered_group_ids'])
                    group_size_required = unit['group_size_required']
                    candidate_count = 0

                    for day_idx in range(len(self.days)):
                        for start_t in range(self.num_slots - duration + 1):
                            # Hard lunch break: do not allow any session to overlap the configured lunch window.
                            if self._overlaps_lunch(start_t, duration):
                                continue

                            start_hour = self.start_hour + start_t
                            end_hour = start_hour + duration

                            if self._session_requires_room(session_type):
                                room_entries = self._get_compatible_rooms(
                                    course, session_type, group_size_required, all_rooms,
                                    day_idx, start_hour, end_hour
                                )
                                if not room_entries:
                                    fallback_rooms = [
                                        room for room in all_rooms
                                        if room_match_rank(
                                            course.preferred_room_type,
                                            session_type,
                                            room.room_type,
                                            group_size=group_size_required,
                                        ) is not None
                                    ]
                                    fallback_rank_lookup = {
                                        room.id: room_match_rank(
                                            course.preferred_room_type,
                                            session_type,
                                            room.room_type,
                                            group_size=group_size_required,
                                        ) or 99
                                        for room in fallback_rooms
                                    }
                                    oversized_fallback_rooms = self._rank_rooms_for_requirement(
                                        fallback_rooms,
                                        group_size_required,
                                        oversized_only=True,
                                        match_rank_lookup=fallback_rank_lookup,
                                    )
                                    room_entries = [
                                        {
                                            'room': r,
                                            'capacity_penalty': self._capacity_penalty(group_size_required, r.capacity),
                                            'match_rank': fallback_rank_lookup.get(r.id, 99),
                                        }
                                        for r in oversized_fallback_rooms
                                    ]
                            else:
                                room_entries = [{'room': None, 'capacity_penalty': 0, 'match_rank': 0}]

                            for room_entry in room_entries:
                                room = room_entry['room']
                                for lec_id in lecturer_ids:
                                    var_name = (
                                        f'c{course.id}_g{group_id}_s{s_id}'
                                        f'_d{day_idx}_t{start_t}_r{room.id if room else "none"}_l{lec_id}'
                                    )
                                    var = model.NewBoolVar(var_name)
                                    key = (course.id, group_id, s_id, day_idx, start_t, room.id if room else None, lec_id)
                                    vars_store[key] = var
                                    var_meta[key] = {
                                        'covered_group_ids': list(covered_group_ids),
                                        'required_group_size': group_size_required,
                                        'combined_size': (
                                            group_size_required if unit['grouping_mode'] == 'shared' else None
                                        ),
                                        'shared_batch_id': unit.get('shared_batch_id'),
                                        'grouping_mode': unit['grouping_mode'],
                                        'rotation_group_ids': list(unit.get('rotation_group_ids') or []),
                                        'rotation_cycle_weeks': unit.get('rotation_cycle_weeks'),
                                    }
                                    expanded_groups = set(covered_group_ids)
                                    for gid in covered_group_ids:
                                        expanded_groups.update(group_ctx['descendants_by_group'].get(gid, set()))
                                    var_group_map[var_name] = list(expanded_groups)
                                    if room is not None:
                                        room_candidate_vars.setdefault(room.id, []).append(var)
                                    if lec_id is not None:
                                        lecturer_candidate_vars.setdefault(lec_id, []).append(var)
                                    candidate_count += 1

                    if candidate_count == 0:
                        diagnostic = self._diagnose_zero_candidate_session(
                            level=level,
                            course=course,
                            session_type=session_type,
                            duration=duration,
                            primary_group_id=group_id,
                            covered_group_ids=list(covered_group_ids),
                            group_size_required=group_size_required,
                            all_rooms=all_rooms,
                            lecturer_ids=lecturer_ids,
                        )
                        diagnostic['grouping_mode'] = unit['grouping_mode']
                        diagnostic['rotation_group_ids'] = list(unit.get('rotation_group_ids') or [])
                        diagnostic['rotation_cycle_weeks'] = unit.get('rotation_cycle_weeks')
                        unschedulable_sessions.append(diagnostic)

        if unschedulable_sessions:
            self.solver_status_by_level[self._scope_key(level)] = 'ZERO_CANDIDATE_PRECHECK'
            self._record_level_diagnostic(level, 'ZERO_CANDIDATE_PRECHECK', unschedulable_sessions)
            return False

        if not vars_store:
            return True  # Nothing to schedule at this level

        self.send_progress(level, 'constraining', progress_start + range_span * 0.3,
                           f'Year {level} {self._active_component_name()}s: Validating scheduling constraints...')

        # ── C1. Each session scheduled exactly once ──────────────────────────
        # Fix #4: C1 must mirror variable-creation group logic for ALL session types.
        # Build a map: course_id -> {s_id -> [group_ids that must schedule it]}
        c1_targets: Dict[int, Dict[int, List[int]]] = {}
        for k in vars_store:
            c_id, g_id, s_id = k[0], k[1], k[2]
            c1_targets.setdefault(c_id, {}).setdefault(s_id, [])
            if g_id not in c1_targets[c_id][s_id]:
                c1_targets[c_id][s_id].append(g_id)

        for c_id, session_map in c1_targets.items():
            for s_id, g_ids in session_map.items():
                for g_id in g_ids:
                    session_vars = [
                        v for k, v in vars_store.items()
                        if k[0] == c_id and k[1] == g_id and k[2] == s_id
                    ]
                    if session_vars:
                        model.Add(sum(session_vars) == 1)

        # ── C2/C3/C4. Time-slot resource conflicts ───────────────────────────
        # Compute these once — they don't change per t_idx iteration
        unique_lecturers = {k[6] for k in vars_store if k[6] is not None}
        all_covered_groups: set = set()
        for glist in var_group_map.values():
            all_covered_groups.update(glist)

        for day_idx in range(len(self.days)):
            for t_idx in range(self.num_slots):

                # C2: Room no double-booking
                for room in all_rooms:
                    active_room_vars = []
                    for k, var in vars_store.items():
                        if k[3] == day_idx and k[5] == room.id:
                            s_t = k[4]
                            dur = course_sessions[k[0]][k[2]]['duration']
                            if s_t <= t_idx < s_t + dur:
                                active_room_vars.append(var)
                    blocked = any(
                        slot['day_of_week'] == day_idx and slot['room_id'] == room.id and
                        self._time_to_idx(slot['start_time']) <= t_idx < self._time_to_idx(slot['end_time'])
                        for slot in self.all_slots + self.existing_slots
                    )
                    if blocked:
                        if active_room_vars:
                            model.Add(sum(active_room_vars) == 0)
                    elif active_room_vars:
                        model.Add(sum(active_room_vars) <= 1)

                # C3: Lecturer no double-booking (skip None = ghost)
                for lecturer_id in unique_lecturers:
                    active_lec_vars = []
                    for k, var in vars_store.items():
                        if k[3] == day_idx and k[6] == lecturer_id:
                            s_t = k[4]
                            dur = course_sessions[k[0]][k[2]]['duration']
                            if s_t <= t_idx < s_t + dur:
                                active_lec_vars.append(var)
                    blocked = any(
                        slot['day_of_week'] == day_idx and slot.get('lecturer_id') == lecturer_id and
                        self._time_to_idx(slot['start_time']) <= t_idx < self._time_to_idx(slot['end_time'])
                        for slot in self.all_slots + self.existing_slots
                    )
                    if blocked:
                        if active_lec_vars:
                            model.Add(sum(active_lec_vars) == 0)
                    elif active_lec_vars:
                        model.Add(sum(active_lec_vars) <= 1)

                # C4: Group conflict — uses var_group_map so shared batches are covered
                for group_id in all_covered_groups:
                    active_group_vars = []
                    for k, var in vars_store.items():
                        var_name = (f'c{k[0]}_g{k[1]}_s{k[2]}'
                                    f'_d{k[3]}_t{k[4]}_r{k[5] if k[5] is not None else "none"}_l{k[6]}')
                        if k[3] == day_idx and group_id in var_group_map.get(var_name, [k[1]]):
                            s_t = k[4]
                            dur = course_sessions[k[0]][k[2]]['duration']
                            if s_t <= t_idx < s_t + dur:
                                active_group_vars.append(var)
                    blocked = False
                    for slot in self.all_slots + self.existing_slots:
                        if slot['day_of_week'] == day_idx and self._time_to_idx(slot['start_time']) <= t_idx < self._time_to_idx(slot['end_time']):
                            slot_groups = [slot['group_id']]
                            if slot.get('shared_group_ids'):
                                slot_groups.extend(self._normalize_shared_group_ids(slot['shared_group_ids']))
                            if slot.get('rotation_group_ids'):
                                slot_groups.extend(self._normalize_shared_group_ids(slot['rotation_group_ids']))
                            
                            if any(sg == group_id or sg in group_ctx['ancestors_by_group'].get(group_id, set()) or sg in group_ctx['descendants_by_group'].get(group_id, set()) for sg in slot_groups):
                                blocked = True
                                break
                        if blocked:
                            break

                    if blocked:
                        if active_group_vars:
                            model.Add(sum(active_group_vars) == 0)
                    elif active_group_vars:
                        model.Add(sum(active_group_vars) <= 1)

        objective_terms = []
        objective_penalties = []

        # ── C5. Daily load cap (outside day loop — manages its own iteration) ─
        all_active_groups = set()
        for glist in var_group_map.values():
            all_active_groups.update(glist)

        for group_id in all_active_groups:
            # We explicitly track hourly Boolean occupancy for C5 and C6
            group_hourly_occupancy_vars = {
                d: {t: [] for t in range(self.num_slots)} for d in range(len(self.days))
            }
            
            # Map session vars into the hours they occupy
            for k, var in vars_store.items():
                var_name = f'c{k[0]}_g{k[1]}_s{k[2]}_d{k[3]}_t{k[4]}_r{k[5]}_l{k[6]}'
                if group_id in var_group_map.get(var_name, [k[1]]):
                    d, s_t = k[3], k[4]
                    dur = course_sessions[k[0]][k[2]]['duration']
                    for t in range(s_t, s_t + dur):
                        group_hourly_occupancy_vars[d][t].append(var)

            for d_idx in range(len(self.days)):
                hourly_load = []
                for t_idx in range(self.num_slots):
                    # For each hour, create a boolean 0 or 1 variable representing "group active"
                    h_var = model.NewBoolVar(f'g{group_id}_d{d_idx}_t{t_idx}_active')
                    # Tie h_var directly to the sum of overlapping session variables
                    # Since C4 already prevents double booking, sum is at most 1
                    model.Add(h_var == sum(group_hourly_occupancy_vars[d_idx][t_idx]))
                    hourly_load.append(h_var)
                
                # C5: Elastic Daily Load Cap (Ideally max 8 hours)
                daily_load = sum(hourly_load)
                # Hard limit set to 10 to entirely prevent insane days, but 9 and 10 are heavily penalized.
                model.Add(daily_load <= 10)
                
                # Using dummy variables to trick CP-SAT into max(0, daily_load - 8)
                overload_var = model.NewIntVar(0, self.num_slots, f'g{group_id}_d{d_idx}_overload')
                daily_diff = model.NewIntVar(-self.num_slots, self.num_slots, f'g{group_id}_d{d_idx}_diff')
                model.Add(daily_diff == daily_load - 8)
                model.AddMaxEquality(overload_var, [0, daily_diff])
                objective_penalties.append(overload_var * 1000)

                # C6: Elastic Sliding Window Fatigue (Ideally max 4 continuous hours)
                for start_w in range(self.num_slots - 4):
                    window = hourly_load[start_w : start_w + 5]
                    b_fatigue = model.NewBoolVar(f'fatigue_g{group_id}_d{d_idx}_w{start_w}')
                    # If sum(window) is 5, it exceeds 4, so b_fatigue MUST be 1.
                    model.Add(sum(window) <= 4 + b_fatigue)
                    objective_penalties.append(b_fatigue * 500)

        # C7a: Hard lecture spread rule.
        # Standard timetable practice expects a course's two weekly lectures
        # to land on different days for the same group whenever lectures exist.
        for course in courses:
            lecture_s_ids = [idx for idx, s in enumerate(course_sessions[course.id]) if s['type'] == 'lecture']
            if len(lecture_s_ids) <= 1:
                continue
            for group_id in all_active_groups:
                for day_idx in range(len(self.days)):
                    lecture_day_vars = []
                    for k, var in vars_store.items():
                        if k[0] == course.id and k[2] in lecture_s_ids and k[3] == day_idx:
                            var_name = f'c{k[0]}_g{k[1]}_s{k[2]}_d{k[3]}_t{k[4]}_r{k[5]}_l{k[6]}'
                            if group_id in var_group_map.get(var_name, [k[1]]):
                                lecture_day_vars.append(var)
                    if len(lecture_day_vars) > 1:
                        model.Add(sum(lecture_day_vars) <= 1)

        # C7b: Soft distribution for any repeated session type on the same day.
        for course in courses:
            c_sessions = course_sessions[course.id]
            for stype in {'lecture', 'practical', 'tutorial'}:
                # get all session IDs belonging to this course & type
                s_ids = [idx for idx, s in enumerate(c_sessions) if s['type'] == stype]
                if len(s_ids) <= 1:
                    continue  # Only one session exists, naturally can't recur today
                for group_id in all_active_groups:
                    for day_idx in range(len(self.days)):
                        day_vars = []
                        for k, var in vars_store.items():
                            if k[0] == course.id and k[2] in s_ids and k[3] == day_idx:
                                var_name = f'c{k[0]}_g{k[1]}_s{k[2]}_d{k[3]}_t{k[4]}_r{k[5]}_l{k[6]}'
                                if group_id in var_group_map.get(var_name, [k[1]]):
                                    day_vars.append(var)
                        if len(day_vars) > 1:
                            excess_sessions = model.NewIntVar(0, len(day_vars), f'excess_c{course.id}_st{stype}_d{day_idx}_g{group_id}')
                            model.Add(sum(day_vars) - 1 <= excess_sessions)
                            objective_penalties.append(excess_sessions * 800)

        # C8: Resource activation bonus.
        # Encourage the solver to use more of the assigned lecturers and
        # available rooms instead of collapsing everything onto a tiny subset.
        for room_id, candidate_vars in room_candidate_vars.items():
            if not candidate_vars:
                continue
            room_used = model.NewBoolVar(f'room_{room_id}_used')
            model.Add(sum(candidate_vars) >= room_used)
            model.Add(sum(candidate_vars) <= len(candidate_vars) * room_used)
            objective_terms.append(room_used * 12)

        for lecturer_id, candidate_vars in lecturer_candidate_vars.items():
            if not candidate_vars:
                continue
            lecturer_used = model.NewBoolVar(f'lecturer_{lecturer_id}_used')
            model.Add(sum(candidate_vars) >= lecturer_used)
            model.Add(sum(candidate_vars) <= len(candidate_vars) * lecturer_used)
            objective_terms.append(lecturer_used * 40)


        self.send_progress(level, 'optimizing', progress_start + range_span * 0.5,
                           f'Year {level} {self._active_component_name()}s: Optimising schedule quality...')

        # ── Soft objectives ──────────────────────────────────────────────────
        # Fix #5: deterministic capacity penalty per room (no stale ORM attribute)
        room_cap_lookup: Dict[int, int] = {r.id: (r.capacity or 0) for r in all_rooms}

        for k, var in vars_store.items():
            course_id, group_id, s_id, day_idx, start_t, room_id, lecturer_id = k
            dur = course_sessions[course_id][s_id]['duration']
            meta = var_meta.get(k, {})

            # Golden hours bonus (09:00-12:00)
            golden_start = 9 - self.start_hour
            if golden_start <= start_t <= golden_start + 2:
                objective_terms.append(var * 200)

            # Fatigue zone penalty (starts at 16:00)
            fatigue_start = 16 - self.start_hour
            if start_t >= fatigue_start:
                objective_penalties.append(var * 300)

            # Capacity overflow and wasted space penalty
            g_size = meta.get('required_group_size') or group_size_map.get(group_id, 30)
            room_cap = room_cap_lookup.get(room_id, 0) if room_id is not None else 0
            
            if room_id is not None:
                wasted_space = max(0, room_cap - g_size)
                if wasted_space > 0:
                    # Slight penalty for wasting a big room on a small class
                    objective_penalties.append(var * wasted_space)
                
                overflow = max(0, g_size - room_cap)
                if overflow > 0:
                    # Heavy penalty for putting a big class in a small room
                    objective_penalties.append(var * overflow * 10)

            # Lecturer preferences
            if lecturer_id is not None:
                lecturer = self.db.query(Lecturer).get(lecturer_id)
                if lecturer and lecturer.teaching_preferences:
                    prefs = lecturer.teaching_preferences
                    if isinstance(prefs, dict):
                        if prefs.get('avoid_early_morning') and start_t == 0:
                            objective_penalties.append(var * 500)
                        if prefs.get('avoid_late_afternoon') and start_t + dur > (16 - self.start_hour):
                            objective_penalties.append(var * 500)

        model.Minimize(sum(objective_penalties) - sum(objective_terms))

        self.send_progress(level, 'solving', progress_start + range_span * 0.6,
                           f'Year {level} {self._active_component_name()}s: Generating schedule...')

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 120.0
        solver.parameters.num_search_workers = 4
        solver.parameters.log_search_progress = True
        solver.parameters.cp_model_presolve = True
        solver.parameters.linearization_level = 2

        status = solver.Solve(model)
        self.solver_status_by_level[self._scope_key(level)] = solver.StatusName(status)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            self.send_progress(level, 'extracting', progress_start + range_span * 0.9,
                               f'Year {level} {self._active_component_name()}s: Preparing results...')
            for k, var in vars_store.items():
                if solver.Value(var) == 1:
                    course_id, group_id, s_id, day_idx, start_t, room_id, lecturer_id = k
                    session_meta = course_sessions[course_id][s_id]
                    duration = session_meta['duration']
                    meta = var_meta.get(k, {})
                    covered_group_ids = list(meta.get('covered_group_ids') or [group_id])
                    shared_group_ids = (
                        [gid for gid in covered_group_ids if gid != group_id]
                        if meta.get('grouping_mode') == 'shared' else None
                    )
                    self.all_slots.append({
                        'course_id': course_id,
                        'lecturer_id': lecturer_id,
                        'room_id': room_id,
                        'group_id': group_id,
                        'day': self.days[day_idx],
                        'day_of_week': day_idx,
                        'start_time': self.time_slots[start_t][0],
                        'end_time': self.time_slots[start_t + duration - 1][1],
                        'session_type': session_meta['type'],
                        'shared_group_ids': shared_group_ids,
                        'combined_size': meta.get('combined_size'),
                        'shared_batch_id': meta.get('shared_batch_id'),
                        'grouping_mode': meta.get('grouping_mode'),
                        'rotation_group_ids': meta.get('rotation_group_ids'),
                        'rotation_cycle_weeks': meta.get('rotation_cycle_weeks'),
                    })
            self._record_level_diagnostic(level, self.solver_status_by_level[self._scope_key(level)], [])
            return True
        else:
            self._record_level_diagnostic(level, self.solver_status_by_level[self._scope_key(level)], [])
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # GREEDY FALLBACK SCHEDULER
    # ─────────────────────────────────────────────────────────────────────────
    def generate_level_timetable_greedy(self, level: int) -> bool:
        """
        Greedy fallback used when CP-SAT returns INFEASIBLE.

        Maintains in-memory booking grids for rooms, groups, and lecturers.
        Iterates sessions (longest-duration first) and places each into the
        first conflict-free (day, start_time, room) slot found.

        This approach ALWAYS produces a schedule - it cannot return INFEASIBLE.
        Sessions that genuinely cannot be placed are logged but non-fatal.
        """
        courses = self.db.query(Course).filter(Course.level.in_(self._level_values(level))).all()
        if not courses:
            return True
        group_ctx = self._build_level_group_context(level)
        if not group_ctx['all_groups']:
            return True
        all_rooms = self.db.query(Room).all()
        if not all_rooms:
            return False

        group_size_map = group_ctx['group_size_map']

        # In-memory booking grids: entity_id -> day_idx -> t_idx -> bool
        room_grid:     Dict[int, Any] = {}
        group_grid:    Dict[int, Any] = {}
        lecturer_grid: Dict[int, Any] = {}
        room_load_hours: Dict[int, int] = defaultdict(int)
        lecturer_load_hours: Dict[int, int] = defaultdict(int)

        def _init(grid: dict, eid: int):
            if eid not in grid:
                grid[eid] = {d: {t: False for t in range(self.num_slots)}
                             for d in range(len(self.days))}

        def _free(grid: dict, eid: int, day: int, s: int, dur: int) -> bool:
            _init(grid, eid)
            return all(not grid[eid][day].get(t, False) for t in range(s, s + dur))

        def _book(grid: dict, eid: int, day: int, s: int, dur: int):
            _init(grid, eid)
            for t in range(s, s + dur):
                grid[eid][day][t] = True

        def _book_group_hierarchy(grid: dict, base_gid: int, day: int, s: int, dur: int):
            group_ids = {base_gid}
            group_ids.update(group_ctx['ancestors_by_group'].get(base_gid, set()))
            group_ids.update(group_ctx['descendants_by_group'].get(base_gid, set()))
            for gid in group_ids:
                _book(grid, gid, day, s, dur)

        # Pre-fill grids from already-placed slots
        daily_course_tracker: Dict[int, Dict[int, Dict[str, set]]] = {}
        def _track_course_dist(gid, cid, stype, d):
            daily_course_tracker.setdefault(gid, {}).setdefault(cid, {}).setdefault(stype, set()).add(d)

        for slot in self.all_slots + self.existing_slots:
            d = slot['day_of_week']
            s_t = self._time_to_idx(slot['start_time'])
            e_t = self._time_to_idx(slot['end_time'])
            dur = e_t - s_t
            if dur <= 0:
                continue
            if slot.get('room_id'):
                _book(room_grid, slot['room_id'], d, s_t, dur)
                room_load_hours[slot['room_id']] += dur
            if slot.get('group_id'):
                _book_group_hierarchy(group_grid, slot['group_id'], d, s_t, dur)
                _track_course_dist(slot['group_id'], slot['course_id'], slot['session_type'], d)
            if slot.get('lecturer_id'):
                _book(lecturer_grid, slot['lecturer_id'], d, s_t, dur)
                lecturer_load_hours[slot['lecturer_id']] += dur
            if slot.get('shared_group_ids'):
                try:
                    for sgid in self._normalize_shared_group_ids(slot['shared_group_ids']):
                        _book_group_hierarchy(group_grid, sgid, d, s_t, dur)
                        _track_course_dist(sgid, slot['course_id'], slot['session_type'], d)
                except:
                    pass
            if slot.get('rotation_group_ids'):
                try:
                    for rgid in self._normalize_shared_group_ids(slot['rotation_group_ids']):
                        _book_group_hierarchy(group_grid, rgid, d, s_t, dur)
                        _track_course_dist(rgid, slot['course_id'], slot['session_type'], d)
                except:
                    pass

        # Rule of greedy checking
        def _will_exceed_fatigue(grid: dict, eid: int, day: int, s: int, dur: int) -> bool:
            """Check if placing a dur block at s would create a 5-hour contiguous block."""
            if eid not in grid: return False
            # Check all sliding 5-hour windows that overlap with this placement
            test_grid = grid[eid][day].copy()
            for i in range(dur):
                test_grid[s+i] = True
            
            for start_w in range(max(0, s - 4), min(self.num_slots - 4, s + dur)):
                w_sum = sum(1 for hw in range(start_w, start_w + 5) if test_grid.get(hw, False))
                if w_sum > 4:
                    return True
            return False

        # Slot ordering: golden hours first (09-12), then morning, then afternoon
        golden = max(0, 9 - self.start_hour)
        slot_order = (
            list(range(golden, min(golden + 3, self.num_slots))) +
            list(range(0, golden)) +
            list(range(golden + 3, self.num_slots))
        )

        # Build work list
        work: List[Dict] = []
        for course in courses:
            sessions = self._parse_course_sessions(course)
            lecture_units = self._resolve_session_units(course, 'lecture', group_ctx)
            for session in sessions:
                stype = session['type']
                lec_ids = self._lecturer_ids_for_session(course.id, stype)
                session_units = self._resolve_session_units(course, stype, group_ctx, lecture_units)

                for unit in session_units:
                    work.append({
                        'course': course,
                        'session': session,
                        'gid': unit['primary_group_id'],
                        'covered': list(unit['covered_group_ids']),
                        'lec_ids': lec_ids,
                        'stype': stype,
                        'group_size': unit['group_size_required'],
                        'shared_batch_id': unit.get('shared_batch_id'),
                        'grouping_mode': unit['grouping_mode'],
                        'rotation_group_ids': list(unit.get('rotation_group_ids') or []),
                        'rotation_cycle_weeks': unit.get('rotation_cycle_weeks'),
                    })

        # Longest blocks first — harder to place, should be scheduled early
        work.sort(key=lambda w: w['session']['duration'], reverse=True)

        starting_slot_count = len(self.all_slots)
        for item in work:
            course   = item['course']
            session  = item['session']
            dur      = session['duration']
            gid      = item['gid']
            covered  = item['covered']
            lec_ids  = item['lec_ids']
            stype    = item['stype']

            requires_room = self._session_requires_room(stype)
            if requires_room:
                compat = [
                    r for r in all_rooms
                    if self._room_type_matches(course.preferred_room_type, stype, r, item['group_size'])
                ]
                match_rank_lookup = {
                    room.id: room_match_rank(
                        course.preferred_room_type,
                        stype,
                        room.room_type,
                        group_size=item['group_size'],
                    ) or 99
                    for room in compat
                }
                # Reject unrealistic fallbacks even when no room can fully fit.
                compat = [
                    r for r in compat
                    if self._room_meets_fallback_capacity(item['group_size'], getattr(r, 'capacity', None))
                ]
                if compat:
                    compat = self._rank_rooms_for_requirement(
                        compat,
                        item['group_size'],
                        room_load_hours=room_load_hours,
                        match_rank_lookup=match_rank_lookup,
                    )
                else:
                    compat = [
                        r for r in all_rooms
                        if self._room_type_matches(course.preferred_room_type, stype, r, item['group_size'])
                    ]
                    match_rank_lookup = {
                        room.id: room_match_rank(
                            course.preferred_room_type,
                            stype,
                            room.room_type,
                            group_size=item['group_size'],
                        ) or 99
                        for room in compat
                    }
                    compat = [
                        r for r in compat
                        if self._room_meets_fallback_capacity(item['group_size'], getattr(r, 'capacity', None))
                    ]
                    if compat:
                        compat = self._rank_rooms_for_requirement(
                            compat,
                            item['group_size'],
                            room_load_hours=room_load_hours,
                            oversized_only=True,
                            match_rank_lookup=match_rank_lookup,
                        )
            else:
                compat = []

            ordered_lec_ids = sorted(
                lec_ids,
                key=lambda lid: (1, 0) if lid is None else (0, lecturer_load_hours.get(lid, 0), lid)
            )

            placed = False
            for day in range(len(self.days)):
                if placed:
                    break
                for s in slot_order:
                    if s + dur > self.num_slots:
                        continue

                    # 1. Lunch break collision
                    if self._overlaps_lunch(s, dur):
                        continue

                    # 2. Availability (no overlap)
                    if not all(_free(group_grid, g, day, s, dur) for g in covered):
                        continue

                    # 3. Fatigue Rule (C6): verify it doesn't break back-to-back limits
                    fatigue_broken = any(_will_exceed_fatigue(group_grid, g, day, s, dur) for g in covered)
                    if fatigue_broken:
                        continue
                    
                    # 4. Distribution Rule (C7): max 1 session per course type per day
                    dist_broken = any(
                        day in daily_course_tracker.get(g, {}).get(course.id, {}).get(stype, set())
                        for g in covered
                    )
                    if dist_broken:
                        continue

                    room = None
                    if requires_room:
                        room = next((r for r in compat if _free(room_grid, r.id, day, s, dur)), None)
                        if not room:
                            continue

                    chosen_lid: Optional[int] = None
                    found_lec = False
                    for lid in ordered_lec_ids:
                        if lid is None or _free(lecturer_grid, lid, day, s, dur):
                            chosen_lid = lid
                            found_lec = True
                            break
                    if not found_lec and None not in lec_ids:
                        continue

                    # Book all resources
                    for g in covered:
                        _book_group_hierarchy(group_grid, g, day, s, dur)
                        _track_course_dist(g, course.id, stype, day)
                    if room is not None:
                        _book(room_grid, room.id, day, s, dur)
                        room_load_hours[room.id] += dur
                    if chosen_lid is not None:
                        _book(lecturer_grid, chosen_lid, day, s, dur)
                        lecturer_load_hours[chosen_lid] += dur

                    # Map into single sequential DB block
                    start_t = self._idx_to_time(s)
                    end_t   = self._idx_to_time(s + dur)
                    self.all_slots.append({
                        'course_id':  course.id,
                        'lecturer_id': chosen_lid,
                        'room_id':    room.id if room is not None else None,
                        'group_id':   gid,
                        'day':        self.days[day],
                        'day_of_week': day,
                        'start_time': start_t,
                        'end_time':   end_t,
                        'session_type': stype,
                        'shared_group_ids': (
                            [g for g in item['covered'] if g != gid]
                            if item.get('grouping_mode') == 'shared' else None
                        ),
                        'combined_size': item['group_size'] if item.get('grouping_mode') == 'shared' else None,
                        'shared_batch_id':  item['shared_batch_id'],
                        'grouping_mode': item.get('grouping_mode'),
                        'rotation_group_ids': item.get('rotation_group_ids'),
                        'rotation_cycle_weeks': item.get('rotation_cycle_weeks'),
                        'oversized_room_fallback': (
                            bool(room and room.capacity and room.capacity < item['group_size'])
                            if self.prefer_largest_room_for_oversized else False
                        ),
                    })
                    placed = True
                    break

        placed_slots = len(self.all_slots) - starting_slot_count
        attempted_slots = len(work)
        fallback_status = f'GREEDY_FALLBACK_AFTER_{self.solver_status_by_level.get(self._scope_key(level), "UNKNOWN")}'
        if attempted_slots > 0 and placed_slots == 0:
            self._record_level_diagnostic(
                level,
                f'{fallback_status}_NO_PLACEMENTS',
                [],
                placed_slots=placed_slots,
                attempted_slots=attempted_slots,
            )
            return False

        self._record_level_diagnostic(
            level,
            fallback_status,
            [],
            placed_slots=placed_slots,
            attempted_slots=attempted_slots,
        )
        return True

    def _room_type_matches(self, pref: RoomType, session_type: str, room: Room, group_size: Optional[int] = None) -> bool:
        """Quick room-type check used by the greedy scheduler."""
        return room_type_matches(pref, session_type, room.room_type, group_size=group_size)

    def _time_to_idx(self, t: time) -> int:
        """Convert time object to index based on dynamic start_hour"""
        return t.hour - self.start_hour

    def _idx_to_time(self, idx: int) -> time:
        """Convert a slot index back to a time object (inverse of _time_to_idx)"""
        hour = self.start_hour + idx
        return time(hour=min(hour, 23), minute=0)

    def save_timetable(self):
        """Save all generated slots to the database"""
        self.saved_slot_annotations = []
        for slot_data in self.all_slots:
            slot = TimetableSlot(
                course_id=slot_data['course_id'],
                lecturer_id=slot_data['lecturer_id'],
                room_id=slot_data['room_id'],
                group_id=slot_data['group_id'],
                day_of_week=slot_data['day_of_week'],
                start_time=slot_data['start_time'],
                end_time=slot_data['end_time'],
                session_type=slot_data['session_type'],
                timetable_id=self.timetable_id,
                shared_group_ids=slot_data.get('shared_group_ids'),
                combined_size=slot_data.get('combined_size'),
                shared_batch_id=slot_data.get('shared_batch_id'),
            )
            self.db.add(slot)
            self.db.flush()

            if slot_data.get('grouping_mode') in {'shared', 'rotating'}:
                self.saved_slot_annotations.append({
                    'slot_id': slot.id,
                    'course_id': slot.course_id,
                    'group_id': slot.group_id,
                    'session_type': slot.session_type,
                    'grouping_mode': slot_data.get('grouping_mode'),
                    'shared_group_ids': slot_data.get('shared_group_ids'),
                    'rotation_group_ids': slot_data.get('rotation_group_ids'),
                    'rotation_cycle_weeks': slot_data.get('rotation_cycle_weeks'),
                    'oversized_room_fallback': slot_data.get('oversized_room_fallback', False),
                })
        self.db.commit()
    @staticmethod
    def _level_values(level: int) -> List[int]:
        """Treat year notation (5) and hundred-level notation (500) as equivalent."""
        if 1 <= level <= 7:
            alternate = level * 100
        elif level % 100 == 0 and 100 <= level <= 700:
            alternate = level // 100
        else:
            alternate = level

        values: List[int] = []
        for candidate in (level, alternate):
            if candidate not in values:
                values.append(candidate)
        return values

    @staticmethod
    def _group_type_value(group: StudentGroup) -> Optional[str]:
        """Normalize enum-backed group types to their raw string values."""
        raw_value = getattr(group, 'group_type', None)
        if raw_value is None:
            return None
        return getattr(raw_value, 'value', raw_value)
