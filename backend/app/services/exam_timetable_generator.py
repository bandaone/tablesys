from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

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


@dataclass
class CandidatePlacement:
    exam_date: date
    session_window: ExamSessionWindow
    seating_profile: Optional[ExamSeatingProfile]
    rooms: List[Tuple[Room, int, List[int]]]
    score: int
    flags: List[str]
    capacity_margin: int
    total_available_capacity: int
    observed_min_gap_hours: Optional[float]
    same_day_group_count: int


@dataclass
class CandidateSearchOutcome:
    best: Optional[CandidatePlacement]
    feasible_count: int
    rejection_summary: Dict[str, int]
    priority_score: int


class ExamTimetableGenerator:
    """Heuristic exam scheduler with richer diagnostics and fair-distribution scoring."""

    def __init__(self, db: Session, exam_period_id: int):
        self.db = db
        self.exam_period_id = exam_period_id
        self.seating = ExamSeatingService()

    @staticmethod
    def _combine(dt: date, tm: time) -> datetime:
        return datetime.combine(dt, tm)

    @staticmethod
    def _window_duration_minutes(window: ExamSessionWindow) -> int:
        return int(
            (
                datetime.combine(date.today(), window.end_time)
                - datetime.combine(date.today(), window.start_time)
            ).total_seconds()
            / 60
        )

    @staticmethod
    def _profile_key(profile: Optional[ExamSeatingProfile]) -> int:
        return int(profile.id) if profile and getattr(profile, "id", None) else 0

    @staticmethod
    def _room_type_key(preferred_room_type: Optional[str]) -> str:
        return str(preferred_room_type or "").strip().lower()

    @staticmethod
    def _room_priority(room: Room) -> int:
        return int(getattr(room, "priority_level", 5) or 5)

    def _load_period(self) -> ExamPeriod:
        period = (
            self.db.query(ExamPeriod)
            .options(
                selectinload(ExamPeriod.session_windows),
                selectinload(ExamPeriod.papers),
                selectinload(ExamPeriod.slots).selectinload(ExamSlot.room_allocations),
                selectinload(ExamPeriod.slots).selectinload(ExamSlot.paper),
            )
            .filter(ExamPeriod.id == self.exam_period_id)
            .first()
        )
        if not period:
            raise ValueError("Exam period not found")
        return period

    def _date_candidates(self, period: ExamPeriod, window: ExamSessionWindow) -> List[date]:
        days: List[date] = []
        current = period.start_date
        while current <= period.end_date:
            if window.allow_weekends or current.weekday() < 5:
                days.append(current)
            current += timedelta(days=1)
        return days

    def _resolved_candidate_count(self, paper: ExamPaper, groups_by_id: Dict[int, StudentGroup]) -> int:
        if paper.candidate_count:
            return int(paper.candidate_count)
        return sum(
            int(groups_by_id[group_id].size or 0)
            for group_id in paper.group_ids or []
            if group_id in groups_by_id
        )

    def _load_room_pool(
        self,
        *,
        rooms: List[Room],
        profile: Optional[ExamSeatingProfile],
        preferred_room_type: Optional[str],
    ) -> List[Room]:
        filtered: List[Room] = []
        preferred_type = self._room_type_key(preferred_room_type)
        for room in rooms:
            if preferred_type and str(getattr(room, "room_type", "")).strip().lower() != preferred_type:
                continue
            if not self.seating.room_supports_profile(room, profile):
                continue
            filtered.append(room)
        return filtered

    def _room_conflicts(
        self,
        scheduled_slots: List[ExamSlot],
        protected_bookings: List[RoomBooking],
        *,
        exam_date: date,
        start_time: time,
        end_time: time,
        room_id: int,
    ) -> bool:
        for slot in scheduled_slots:
            if slot.exam_date != exam_date:
                continue
            if not (start_time < slot.end_time and end_time > slot.start_time):
                continue
            if any(allocation.room_id == room_id for allocation in slot.room_allocations):
                return True
        for booking in protected_bookings:
            if booking.room_id != room_id or booking.booking_date != exam_date:
                continue
            if start_time < booking.end_time and end_time > booking.start_time:
                return True
        return False

    def _group_exam_stats(
        self,
        scheduled_slots: List[ExamSlot],
        group_ids: List[int],
        candidate_date: date,
        candidate_start: time,
        candidate_end: time,
    ) -> Tuple[Dict[int, int], bool]:
        daily_counts: Dict[int, int] = defaultdict(int)
        same_time_conflict = False

        target_groups = set(group_ids)
        for slot in scheduled_slots:
            overlap = target_groups.intersection(set(slot.paper.group_ids or []))
            if not overlap:
                continue
            if slot.exam_date == candidate_date:
                for group_id in overlap:
                    daily_counts[group_id] += 1
                if candidate_start < slot.end_time and slot.start_time < candidate_end:
                    same_time_conflict = True

        return daily_counts, same_time_conflict

    def _spacing_penalty(
        self,
        scheduled_slots: List[ExamSlot],
        *,
        group_ids: List[int],
        exam_date: date,
        start_time: time,
        min_gap_hours: int,
    ) -> Tuple[Optional[int], Optional[float]]:
        penalty = 0
        minimum_gap_seen: Optional[float] = None
        target_dt = self._combine(exam_date, start_time)
        target_groups = set(group_ids)

        for slot in scheduled_slots:
            overlap = target_groups.intersection(set(slot.paper.group_ids or []))
            if not overlap:
                continue
            gap_hours = abs((target_dt - self._combine(slot.exam_date, slot.start_time)).total_seconds()) / 3600
            minimum_gap_seen = gap_hours if minimum_gap_seen is None else min(minimum_gap_seen, gap_hours)
            if gap_hours < min_gap_hours:
                return None, minimum_gap_seen
            if gap_hours < min_gap_hours * 2:
                penalty += int((min_gap_hours * 2 - gap_hours) * 25)
        return penalty, minimum_gap_seen

    def _effective_capacity(
        self,
        room: Room,
        seating_profile: Optional[ExamSeatingProfile],
        capacity_cache: Dict[Tuple[int, int], int],
    ) -> int:
        key = (room.id, self._profile_key(seating_profile))
        if key not in capacity_cache:
            capacity_cache[key] = self.seating.effective_capacity(room, seating_profile)
        return capacity_cache[key]

    @staticmethod
    def _minimum_rooms_required(capacities: List[int], required_capacity: int) -> Optional[int]:
        total = 0
        for index, capacity in enumerate(sorted(capacities, reverse=True), start=1):
            total += capacity
            if total >= required_capacity:
                return index
        return None

    def _room_bundle_pressure(
        self,
        rooms: List[Room],
        required_capacity: int,
        *,
        max_rooms: Optional[int],
        seating_profile: Optional[ExamSeatingProfile],
        capacity_cache: Dict[Tuple[int, int], int],
    ) -> Dict[str, Optional[int]]:
        capacities = [
            self._effective_capacity(room, seating_profile, capacity_cache)
            for room in rooms
        ]
        capacities = [capacity for capacity in capacities if capacity > 0]
        if not capacities:
            return {"max_capacity": 0, "min_rooms_needed": None}
        return {
            "max_capacity": sum(capacities),
            "min_rooms_needed": self._minimum_rooms_required(capacities, required_capacity),
            "max_rooms_allowed": max_rooms,
        }

    def _build_room_bundle(
        self,
        rooms: List[Room],
        required_capacity: int,
        *,
        max_rooms: Optional[int],
        seating_profile: Optional[ExamSeatingProfile],
        groups: List[StudentGroup],
        capacity_cache: Dict[Tuple[int, int], int],
    ) -> Optional[List[Tuple[Room, int, List[int]]]]:
        capacities = [
            (room, self._effective_capacity(room, seating_profile, capacity_cache))
            for room in rooms
        ]
        capacities = [(room, capacity) for room, capacity in capacities if capacity > 0]
        if not capacities:
            return None

        single_room_options = [
            (room, capacity)
            for room, capacity in capacities
            if capacity >= required_capacity
        ]
        if single_room_options:
            room, _capacity = min(
                single_room_options,
                key=lambda item: (
                    item[1] - required_capacity,
                    -self._room_priority(item[0]),
                    item[0].name,
                ),
            )
            return [(room, required_capacity, [group.id for group in groups])]

        capacities.sort(
            key=lambda item: (
                -self._room_priority(item[0]),
                -item[1],
                item[0].name,
            )
        )
        chosen: List[Tuple[Room, int]] = []
        total = 0
        for room, capacity in capacities:
            chosen.append((room, capacity))
            total += capacity
            if total >= required_capacity:
                break

        if total < required_capacity:
            return None
        if max_rooms and len(chosen) > max_rooms:
            return None

        remaining_by_group = {group.id: int(group.size or 0) for group in groups}
        allocations: List[Tuple[Room, int, List[int]]] = []
        remaining_total = required_capacity

        for room, room_capacity in chosen:
            allocation_capacity = min(room_capacity, remaining_total)
            remaining_total -= allocation_capacity
            assigned_groups: List[int] = []
            remaining_capacity = allocation_capacity

            for group in groups:
                outstanding = remaining_by_group.get(group.id, 0)
                if outstanding <= 0:
                    continue
                assigned_groups.append(group.id)
                used = min(outstanding, remaining_capacity)
                remaining_by_group[group.id] = outstanding - used
                remaining_capacity -= used
                if remaining_capacity <= 0:
                    break

            if remaining_capacity > 0 and groups:
                assigned_groups.append(groups[-1].id)

            allocations.append((room, allocation_capacity, assigned_groups))

        return allocations

    def _paper_priority_score(
        self,
        *,
        paper: ExamPaper,
        groups_by_id: Dict[int, StudentGroup],
        room_pool: List[Room],
        seating_profile: Optional[ExamSeatingProfile],
        capacity_cache: Dict[Tuple[int, int], int],
    ) -> int:
        candidate_count = self._resolved_candidate_count(paper, groups_by_id)
        group_count = len(paper.group_ids or [])
        duration = int(paper.duration_minutes or 0)
        pressure = self._room_bundle_pressure(
            room_pool,
            candidate_count,
            max_rooms=paper.max_rooms,
            seating_profile=seating_profile,
            capacity_cache=capacity_cache,
        )

        min_rooms_needed = pressure.get("min_rooms_needed") or len(room_pool) or 1
        limited_room_pool_penalty = max(0, 6 - len(room_pool)) * 110
        max_rooms_penalty = max(0, min_rooms_needed - 1) * 180
        preferred_room_type_penalty = 180 if self._room_type_key(paper.preferred_room_type) else 0

        return (
            candidate_count * 4
            + group_count * 220
            + duration * 2
            + limited_room_pool_penalty
            + max_rooms_penalty
            + preferred_room_type_penalty
        )

    @staticmethod
    def _unscheduled_reason(rejection_summary: Dict[str, int]) -> str:
        if not rejection_summary:
            return "No feasible placement found under the current exam constraints"

        dominant = max(rejection_summary.items(), key=lambda item: item[1])[0]
        messages = {
            "window_too_short": "No session window is long enough for the paper duration",
            "group_time_conflict": "Student groups already have overlapping papers in the available sessions",
            "hard_daily_limit": "Daily paper limits for one or more groups block every candidate slot",
            "minimum_spacing": "Minimum spacing between exams blocks every candidate slot",
            "rooms_unavailable": "Rooms are occupied or protected during the feasible sessions",
            "capacity_insufficient": "Effective venue capacity is not sufficient for the paper audience",
            "too_many_rooms_required": "The paper would need more rooms than the configured maximum",
            "room_bundle_unavailable": "No valid room bundle satisfies the placement constraints",
        }
        return messages.get(dominant, "No feasible placement found under the current exam constraints")

    def _find_best_candidate(
        self,
        *,
        paper: ExamPaper,
        period: ExamPeriod,
        windows: List[ExamSessionWindow],
        rooms: List[Room],
        seating_profile: Optional[ExamSeatingProfile],
        scheduled_slots: List[ExamSlot],
        groups_by_id: Dict[int, StudentGroup],
        session_usage: Dict[int, int],
        day_usage: Dict[str, int],
        protected_bookings: List[RoomBooking],
        capacity_cache: Dict[Tuple[int, int], int],
    ) -> CandidateSearchOutcome:
        settings = dict(period.constraint_settings or {})
        preferred_max_papers_per_day = int(settings.get("preferred_max_papers_per_day", 1) or 1)
        hard_max_papers_per_day = int(settings.get("hard_max_papers_per_day", 2) or 2)
        min_gap_hours = int(settings.get("min_gap_hours", 24) or 24)

        paper_group_ids = [int(group_id) for group_id in (paper.group_ids or []) if group_id in groups_by_id]
        groups = sorted(
            [groups_by_id[group_id] for group_id in paper_group_ids],
            key=lambda item: int(item.size or 0),
            reverse=True,
        )
        candidate_count = self._resolved_candidate_count(paper, groups_by_id)
        priority_score = self._paper_priority_score(
            paper=paper,
            groups_by_id=groups_by_id,
            room_pool=rooms,
            seating_profile=seating_profile,
            capacity_cache=capacity_cache,
        )

        best: Optional[CandidatePlacement] = None
        feasible_count = 0
        rejection_summary: Dict[str, int] = defaultdict(int)

        for window in windows:
            if self._window_duration_minutes(window) < int(paper.duration_minutes or 0):
                rejection_summary["window_too_short"] += 1
                continue

            for exam_date in self._date_candidates(period, window):
                daily_counts, same_time_conflict = self._group_exam_stats(
                    scheduled_slots,
                    paper_group_ids,
                    exam_date,
                    window.start_time,
                    window.end_time,
                )
                if same_time_conflict:
                    rejection_summary["group_time_conflict"] += 1
                    continue
                if any(count >= hard_max_papers_per_day for count in daily_counts.values()):
                    rejection_summary["hard_daily_limit"] += 1
                    continue

                spacing_penalty, observed_min_gap_hours = self._spacing_penalty(
                    scheduled_slots,
                    group_ids=paper_group_ids,
                    exam_date=exam_date,
                    start_time=window.start_time,
                    min_gap_hours=min_gap_hours,
                )
                if spacing_penalty is None:
                    rejection_summary["minimum_spacing"] += 1
                    continue

                free_rooms = [
                    room
                    for room in rooms
                    if not self._room_conflicts(
                        scheduled_slots,
                        protected_bookings,
                        exam_date=exam_date,
                        start_time=window.start_time,
                        end_time=window.end_time,
                        room_id=room.id,
                    )
                ]
                if not free_rooms:
                    rejection_summary["rooms_unavailable"] += 1
                    continue

                bundle = self._build_room_bundle(
                    free_rooms,
                    candidate_count,
                    max_rooms=paper.max_rooms,
                    seating_profile=seating_profile,
                    groups=groups,
                    capacity_cache=capacity_cache,
                )
                if not bundle:
                    pressure = self._room_bundle_pressure(
                        free_rooms,
                        candidate_count,
                        max_rooms=paper.max_rooms,
                        seating_profile=seating_profile,
                        capacity_cache=capacity_cache,
                    )
                    if (pressure.get("max_capacity") or 0) < candidate_count:
                        rejection_summary["capacity_insufficient"] += 1
                    elif paper.max_rooms and (pressure.get("min_rooms_needed") or 0) > paper.max_rooms:
                        rejection_summary["too_many_rooms_required"] += 1
                    else:
                        rejection_summary["room_bundle_unavailable"] += 1
                    continue

                feasible_count += 1
                total_capacity = sum(item[1] for item in bundle)
                total_available_capacity = sum(
                    self._effective_capacity(room, seating_profile, capacity_cache)
                    for room, _allocated_capacity, _group_ids in bundle
                )
                capacity_margin = max(0, total_available_capacity - candidate_count)
                room_penalty = len(bundle) * 32
                unused_capacity_penalty = max(0, capacity_margin)
                same_day_penalty = sum(
                    max(0, count - preferred_max_papers_per_day + 1) * 480
                    for count in daily_counts.values()
                )
                existing_same_day_penalty = sum(daily_counts.values()) * 140
                session_balance_penalty = session_usage.get(window.id, 0) * 22
                day_balance_penalty = day_usage.get(exam_date.isoformat(), 0) * 18

                score = (
                    spacing_penalty
                    + room_penalty
                    + unused_capacity_penalty
                    + same_day_penalty
                    + existing_same_day_penalty
                    + session_balance_penalty
                    + day_balance_penalty
                )

                flags: List[str] = []
                if len(bundle) > 1:
                    flags.append("multi_room_allocation")
                if capacity_margin <= max(15, int(candidate_count * 0.05)):
                    flags.append("tight_capacity_fit")
                if sum(daily_counts.values()) > 0:
                    flags.append("same_day_pressure")
                if observed_min_gap_hours is not None and observed_min_gap_hours < max(min_gap_hours * 1.5, min_gap_hours + 6):
                    flags.append("compressed_spacing")
                if day_usage.get(exam_date.isoformat(), 0) >= max(1, len(windows)):
                    flags.append("peak_day_usage")

                candidate = CandidatePlacement(
                    exam_date=exam_date,
                    session_window=window,
                    seating_profile=seating_profile,
                    rooms=bundle,
                    score=score,
                    flags=flags,
                    capacity_margin=capacity_margin,
                    total_available_capacity=total_available_capacity,
                    observed_min_gap_hours=observed_min_gap_hours,
                    same_day_group_count=sum(1 for count in daily_counts.values() if count > 0),
                )
                if not best or candidate.score < best.score:
                    best = candidate

        return CandidateSearchOutcome(
            best=best,
            feasible_count=feasible_count,
            rejection_summary=dict(rejection_summary),
            priority_score=priority_score,
        )

    def generate(self, *, replace_existing: bool = True) -> Dict:
        period = self._load_period()
        if period.is_locked:
            raise ValueError("Exam period is locked and cannot be regenerated")

        windows = [window for window in period.session_windows if window.is_active]
        if not windows:
            raise ValueError("At least one active exam session window is required")

        group_ids = sorted({int(group_id) for paper in period.papers for group_id in (paper.group_ids or [])})
        groups = self.db.query(StudentGroup).filter(StudentGroup.id.in_(group_ids)).all() if group_ids else []
        groups_by_id = {group.id: group for group in groups}

        if replace_existing and period.slots:
            for slot in list(period.slots):
                self.db.delete(slot)
            self.db.flush()
            period.slots = []

        profiles = (
            self.db.query(ExamSeatingProfile)
            .filter(ExamSeatingProfile.university_id == period.university_id)
            .all()
        )
        profiles_by_id = {profile.id: profile for profile in profiles}
        default_profile = next((profile for profile in profiles if profile.is_default), None)
        protected_bookings = (
            self.db.query(RoomBooking)
            .filter(
                RoomBooking.booking_date >= period.start_date,
                RoomBooking.booking_date <= period.end_date,
            )
            .all()
        )
        all_rooms = (
            self.db.query(Room)
            .filter(
                Room.university_id == period.university_id,
                Room.is_blocked.is_(False),
            )
            .all()
        )

        room_pool_cache: Dict[Tuple[int, str], List[Room]] = {}
        capacity_cache: Dict[Tuple[int, int], int] = {}

        scheduled_slots: List[ExamSlot] = list(period.slots or [])
        session_usage: Dict[int, int] = defaultdict(int)
        day_usage: Dict[str, int] = defaultdict(int)
        for slot in scheduled_slots:
            session_usage[int(slot.session_window_id)] += 1
            day_usage[slot.exam_date.isoformat()] += 1

        unscheduled: List[Dict] = []
        scheduled_flags: List[Dict] = []

        remaining_papers = list(period.papers)
        while remaining_papers:
            evaluated: List[Tuple[ExamPaper, CandidateSearchOutcome, Optional[ExamSeatingProfile]]] = []
            for paper in remaining_papers:
                seating_profile = (
                    profiles_by_id.get(paper.preferred_seating_profile_id)
                    if paper.preferred_seating_profile_id
                    else default_profile
                )
                room_cache_key = (self._profile_key(seating_profile), self._room_type_key(paper.preferred_room_type))
                if room_cache_key not in room_pool_cache:
                    room_pool_cache[room_cache_key] = self._load_room_pool(
                        rooms=all_rooms,
                        profile=seating_profile,
                        preferred_room_type=paper.preferred_room_type,
                    )
                room_pool = room_pool_cache[room_cache_key]

                outcome = self._find_best_candidate(
                    paper=paper,
                    period=period,
                    windows=windows,
                    rooms=room_pool,
                    seating_profile=seating_profile,
                    scheduled_slots=scheduled_slots,
                    groups_by_id=groups_by_id,
                    session_usage=session_usage,
                    day_usage=day_usage,
                    protected_bookings=protected_bookings,
                    capacity_cache=capacity_cache,
                )
                evaluated.append((paper, outcome, seating_profile))

            evaluated.sort(
                key=lambda item: (
                    0 if item[1].best is not None else 1,
                    item[1].feasible_count if item[1].feasible_count > 0 else 10**9,
                    -item[1].priority_score,
                    item[1].best.score if item[1].best else 10**9,
                    -(self._resolved_candidate_count(item[0], groups_by_id)),
                )
            )

            paper, outcome, seating_profile = evaluated[0]
            remaining_papers = [item for item in remaining_papers if item.id != paper.id]

            if not outcome.best:
                unscheduled.append(
                    {
                        "paper_id": paper.id,
                        "paper_code": paper.paper_code,
                        "paper_name": paper.paper_name,
                        "reason": self._unscheduled_reason(outcome.rejection_summary),
                        "feasible_options": outcome.feasible_count,
                        "priority_score": outcome.priority_score,
                        "candidate_count": self._resolved_candidate_count(paper, groups_by_id),
                        "diagnostics": outcome.rejection_summary,
                    }
                )
                continue

            candidate = outcome.best
            note_parts: List[str] = []
            if "multi_room_allocation" in candidate.flags:
                note_parts.append(f"Split across {len(candidate.rooms)} rooms")
            if "tight_capacity_fit" in candidate.flags:
                note_parts.append(f"Tight fit with {candidate.capacity_margin} spare seats")
            if "same_day_pressure" in candidate.flags:
                note_parts.append("Shared groups already have another paper on the same day")
            if "compressed_spacing" in candidate.flags and candidate.observed_min_gap_hours is not None:
                note_parts.append(f"Nearest shared-group gap is {candidate.observed_min_gap_hours:.1f} hours")
            if "peak_day_usage" in candidate.flags:
                note_parts.append("Placed on an already busy exam day")

            slot = ExamSlot(
                exam_period_id=period.id,
                exam_paper_id=paper.id,
                session_window_id=candidate.session_window.id,
                seating_profile_id=candidate.seating_profile.id if candidate.seating_profile else None,
                exam_date=candidate.exam_date,
                start_time=candidate.session_window.start_time,
                end_time=candidate.session_window.end_time,
                status="draft",
                total_allocated_capacity=sum(item[1] for item in candidate.rooms),
                generated_score=candidate.score,
                notes=" | ".join(note_parts) if note_parts else None,
            )
            slot.paper = paper
            slot.room_allocations = [
                ExamSlotRoom(
                    room_id=room.id,
                    seating_profile_id=seating_profile.id if seating_profile else None,
                    allocated_capacity=capacity,
                    allocated_group_ids=assigned_group_ids,
                    sequence_no=index,
                )
                for index, (room, capacity, assigned_group_ids) in enumerate(candidate.rooms)
            ]
            self.db.add(slot)
            self.db.flush()
            scheduled_slots.append(slot)
            session_usage[candidate.session_window.id] += 1
            day_usage[candidate.exam_date.isoformat()] += 1

            if candidate.flags:
                severity = "warning" if any(
                    flag in {"tight_capacity_fit", "same_day_pressure", "compressed_spacing"}
                    for flag in candidate.flags
                ) else "info"
                scheduled_flags.append(
                    {
                        "slot_id": slot.id,
                        "paper_id": paper.id,
                        "paper_code": paper.paper_code,
                        "paper_name": paper.paper_name,
                        "severity": severity,
                        "flags": candidate.flags,
                        "summary": slot.notes or "Placement created with minor diagnostics",
                        "room_count": len(candidate.rooms),
                        "capacity_margin": candidate.capacity_margin,
                        "available_capacity": candidate.total_available_capacity,
                        "same_day_group_count": candidate.same_day_group_count,
                    }
                )

        flag_counts: Dict[str, int] = defaultdict(int)
        for item in scheduled_flags:
            for flag in item.get("flags", []):
                flag_counts[flag] += 1

        unscheduled_reason_counts: Dict[str, int] = defaultdict(int)
        for item in unscheduled:
            for reason, count in (item.get("diagnostics") or {}).items():
                unscheduled_reason_counts[reason] += count

        period.generation_metadata = {
            "generated_at": datetime.utcnow().isoformat(),
            "scheduled_count": len(scheduled_slots),
            "unscheduled_count": len(unscheduled),
            "unscheduled_papers": unscheduled,
            "scheduled_flags": scheduled_flags,
            "diagnostics_summary": {
                "scheduled_with_flags": len(scheduled_flags),
                "multi_room_allocations": flag_counts.get("multi_room_allocation", 0),
                "tight_capacity_fits": flag_counts.get("tight_capacity_fit", 0),
                "same_day_pressure_cases": flag_counts.get("same_day_pressure", 0),
                "compressed_spacing_cases": flag_counts.get("compressed_spacing", 0),
                "peak_day_usage_cases": flag_counts.get("peak_day_usage", 0),
                "unscheduled_reasons": dict(unscheduled_reason_counts),
                "average_rooms_per_slot": round(
                    sum(len(slot.room_allocations or []) for slot in scheduled_slots) / len(scheduled_slots),
                    2,
                ) if scheduled_slots else 0,
            },
            "strategy": "constraint-prioritized heuristic with flexible-paper ordering, room-bundle minimization, and fairness diagnostics",
        }
        self.db.commit()
        self.db.refresh(period)

        return {
            "scheduled_count": len(scheduled_slots),
            "unscheduled_count": len(unscheduled),
            "unscheduled_papers": unscheduled,
            "scheduled_flags": scheduled_flags,
            "diagnostics_summary": period.generation_metadata["diagnostics_summary"],
        }
