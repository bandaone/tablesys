import time as time_mod
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple, Any

from ortools.sat.python import cp_model
from sqlalchemy.orm import Session, selectinload

from ..models import (
    ExamPaper,
    ExamPeriod,
    ExamSeatingProfile,
    ExamSessionWindow,
    ExamSlot,
    ExamSlotRoom,
    LecturerAssignment,
    Room,
    RoomBooking,
    StudentGroup,
)
from ..utils.transit import insufficient_transit_time
from .exam_seating_service import ExamSeatingService


class ExamTimetableGenerator:
    """CP-SAT powered exam scheduler optimizing for fair student spacing."""

    def __init__(self, db: Session, exam_period_id: int):
        self.db = db
        self.exam_period_id = exam_period_id
        self.seating = ExamSeatingService()
        self.generation_diagnostics = []

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

    def _get_chief_invigilator(self, course_id: Optional[int]) -> Optional[int]:
        if not course_id:
            return None
        assignment = (
            self.db.query(LecturerAssignment)
            .filter(
                LecturerAssignment.course_id == course_id,
                LecturerAssignment.expertise_level == "primary",
            )
            .first()
        )
        return assignment.lecturer_id if assignment else None

    def generate(self, *, replace_existing: bool = True) -> Dict:
        start_time_ts = time_mod.time()
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

        all_rooms = (
            self.db.query(Room)
            .filter(
                Room.university_id == period.university_id,
                Room.is_blocked.is_(False),
            )
            .all()
        )
        profiles = self.db.query(ExamSeatingProfile).filter(ExamSeatingProfile.university_id == period.university_id).all()
        default_profile = next((p for p in profiles if p.is_default), None)
        profiles_by_id = {p.id: p for p in profiles}
        
        # Pre-compute effective capacities
        effective_caps = {}
        for room in all_rooms:
            for prof in profiles + [None]:
                prof_id = prof.id if prof else 0
                effective_caps[(room.id, prof_id)] = self.seating.effective_capacity(room, prof)

        # Setup Dates
        all_dates = []
        for w in windows:
            for d in self._date_candidates(period, w):
                if d not in all_dates:
                    all_dates.append(d)
        all_dates.sort()
        date_indices = {d: i for i, d in enumerate(all_dates)}

        model = cp_model.CpModel()
        
        # Variables: X[paper_id][window_id][date_idx] = boolean
        X = {}
        # Room placement: R[paper_id][room_id] = boolean
        R = {}
        
        unscheduled = []
        scheduled_slots_data = []

        papers_to_schedule = list(period.papers)
        
        for p in papers_to_schedule:
            for w in windows:
                for d in all_dates:
                    X[(p.id, w.id, date_indices[d])] = model.NewBoolVar(f'x_p{p.id}_w{w.id}_d{date_indices[d]}')
            for r in all_rooms:
                R[(p.id, r.id)] = model.NewBoolVar(f'r_p{p.id}_r{r.id}')

        # Constraint 1: Every paper scheduled exactly once
        for p in papers_to_schedule:
            model.AddExactlyOne(X[(p.id, w.id, date_indices[d])] for w in windows for d in all_dates)

        # Constraint 2: Room Capacity
        for p in papers_to_schedule:
            prof = profiles_by_id.get(p.preferred_seating_profile_id, default_profile)
            prof_id = prof.id if prof else 0
            req_cap = self._resolved_candidate_count(p, groups_by_id)
            model.Add(sum(R[(p.id, r.id)] * effective_caps[(r.id, prof_id)] for r in all_rooms) >= req_cap)
            
            # Max Rooms constraint
            max_rooms = p.max_rooms or 100
            model.Add(sum(R[(p.id, r.id)] for r in all_rooms) <= max_rooms)

        # Constraint 3: Room Time Overlaps
        for w in windows:
            for d in all_dates:
                for r in all_rooms:
                    papers_in_slot = []
                    for p in papers_to_schedule:
                        # If paper is in this slot AND in this room
                        p_in_slot = model.NewBoolVar(f'in_slot_p{p.id}_w{w.id}_d{date_indices[d]}_r{r.id}')
                        model.AddMultiplicationEquality(p_in_slot, [X[(p.id, w.id, date_indices[d])], R[(p.id, r.id)]])
                        papers_in_slot.append(p_in_slot)
                    model.AddAtMostOne(papers_in_slot)

        # Constraint 4: Student Group Overlaps & Same Day Limits
        for g_id in groups_by_id.keys():
            g_papers = [p for p in papers_to_schedule if p.group_ids and g_id in p.group_ids]
            if not g_papers:
                continue
            
            # Prevent same group taking two exams in same window/date
            for w in windows:
                for d in all_dates:
                    model.AddAtMostOne(X[(p.id, w.id, date_indices[d])] for p in g_papers)
            
            # Daily limit (Max 2 papers per day per group)
            for d in all_dates:
                model.Add(sum(X[(p.id, w.id, date_indices[d])] for p in g_papers for w in windows) <= 2)

            # A paper can use several rooms, so the generator cannot promise a
            # particular candidate will remain in the same room.  Treat close
            # consecutive windows as incompatible for the group; a manually
            # assigned one-room exam can still use the same-room exception in
            # ExamValidationService.
            for d in all_dates:
                for first_index, first_paper in enumerate(g_papers):
                    for second_paper in g_papers[first_index + 1:]:
                        for first_window in windows:
                            for second_window in windows:
                                if insufficient_transit_time(
                                    first_window.start_time, first_window.end_time, None,
                                    second_window.start_time, second_window.end_time, None,
                                ):
                                    model.Add(
                                        X[(first_paper.id, first_window.id, date_indices[d])]
                                        + X[(second_paper.id, second_window.id, date_indices[d])]
                                        <= 1
                                    )

        # Optimization: Maximize Spacing (Minimize consecutive days)
        penalties = []
        for g_id in groups_by_id.keys():
            g_papers = [p for p in papers_to_schedule if p.group_ids and g_id in p.group_ids]
            if len(g_papers) < 2:
                continue
                
            for d_idx in range(len(all_dates) - 1):
                day_active = model.NewBoolVar(f'g{g_id}_d{d_idx}_active')
                next_day_active = model.NewBoolVar(f'g{g_id}_d{d_idx+1}_active')
                
                # Link day_active to whether any paper is scheduled on that day for this group
                model.AddMaxEquality(day_active, [X[(p.id, w.id, d_idx)] for p in g_papers for w in windows])
                model.AddMaxEquality(next_day_active, [X[(p.id, w.id, d_idx+1)] for p in g_papers for w in windows])
                
                consecutive = model.NewBoolVar(f'g{g_id}_d{d_idx}_consec')
                model.AddMultiplicationEquality(consecutive, [day_active, next_day_active])
                penalties.append(consecutive * 100) # Heavy penalty for back-to-back days

        model.Minimize(sum(penalties))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 15.0
        status = solver.Solve(model)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            for p in papers_to_schedule:
                prof = profiles_by_id.get(p.preferred_seating_profile_id, default_profile)
                prof_id = prof.id if prof else 0
                
                selected_w = None
                selected_d = None
                for w in windows:
                    for d in all_dates:
                        if solver.Value(X[(p.id, w.id, date_indices[d])]):
                            selected_w = w
                            selected_d = d
                            break
                    if selected_w:
                        break
                
                selected_rooms = []
                for r in all_rooms:
                    if solver.Value(R[(p.id, r.id)]):
                        selected_rooms.append(r)
                
                # Create Slot
                chief_invigilator_id = self._get_chief_invigilator(p.course_id)
                
                slot = ExamSlot(
                    exam_period_id=period.id,
                    exam_paper_id=p.id,
                    session_window_id=selected_w.id,
                    seating_profile_id=prof_id if prof_id else None,
                    chief_invigilator_id=chief_invigilator_id,
                    exam_date=selected_d,
                    start_time=selected_w.start_time,
                    end_time=selected_w.end_time,
                    status="draft",
                    total_allocated_capacity=sum(effective_caps[(r.id, prof_id)] for r in selected_rooms),
                    generated_score=int(solver.ObjectiveValue()),
                    notes="Optimized via CP-SAT for fair spacing."
                )
                
                slot.paper = p
                allocations = []
                remaining_candidates = self._resolved_candidate_count(p, groups_by_id)
                for seq, r in enumerate(selected_rooms):
                    alloc_cap = min(remaining_candidates, effective_caps[(r.id, prof_id)])
                    remaining_candidates -= alloc_cap
                    allocations.append(ExamSlotRoom(
                        room_id=r.id,
                        seating_profile_id=prof_id if prof_id else None,
                        allocated_capacity=alloc_cap,
                        allocated_group_ids=p.group_ids,
                        sequence_no=seq
                    ))
                slot.room_allocations = allocations
                self.db.add(slot)
                scheduled_slots_data.append(slot)
            
            self.db.flush()
        else:
            # If CP-SAT fails completely due to impossible constraints
            unscheduled = [{"paper_id": p.id, "paper_code": p.paper_code, "paper_name": p.paper_name, "reason": "No feasible global schedule possible with current constraints."} for p in papers_to_schedule]

        period.generation_metadata = {
            "generated_at": datetime.utcnow().isoformat(),
            "scheduled_count": len(scheduled_slots_data),
            "unscheduled_count": len(unscheduled),
            "unscheduled_papers": unscheduled,
            "scheduled_flags": [],
            "diagnostics_summary": {
                "strategy": "CP-SAT Global Spacing Optimization",
                "solver_status": solver.StatusName(status),
                "objective_value": int(solver.ObjectiveValue()) if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else 0
            }
        }
        self.db.commit()
        self.db.refresh(period)

        return {
            "scheduled_count": len(scheduled_slots_data),
            "unscheduled_count": len(unscheduled),
            "unscheduled_papers": unscheduled,
            "scheduled_flags": [],
            "diagnostics_summary": period.generation_metadata["diagnostics_summary"],
        }
