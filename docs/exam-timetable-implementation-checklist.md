# Exam Timetable Implementation Checklist

## Purpose

This checklist tracks the current coordinator exam timetable implementation state after the generator and review workspace upgrade.

It is meant to help future contributors quickly see:

- what is already implemented
- what diagnostics the current engine emits
- what still needs a second pass

## Current Build Scope

### Backend

- [x] Separate exam scheduling domain exists
- [x] Exam period, session window, seating profile, paper, slot, and slot-room models exist
- [x] Exam periods are scoped to the active university on list, detail, update, generate, publish, and delete flows
- [x] Effective room capacity is computed from seating profiles
- [x] Generator loads papers, rooms, groups, seating profiles, and session windows
- [x] Generator iterates across available day and session windows
- [x] Generator checks group conflicts and protected room bookings
- [x] Generator enforces minimum spacing between shared-group papers
- [x] Generator honors the same-day fallback setting as a real scheduling rule
- [x] Generator allocates one or more rooms per paper when needed
- [x] Generator prefers the smallest viable room bundle
- [x] Generator prioritizes large and constrained papers first
- [x] Generator balances session and day usage heuristically
- [x] Generator emits unscheduled-paper diagnostics
- [x] Generator emits scheduled-slot review flags
- [x] Publish is blocked when any paper in the period remains unscheduled
- [x] Published or locked periods are protected from deletion
- [x] Generic exam-period updates cannot directly toggle publish or lock state

### Frontend

- [x] Exam workspace page exists at `/exam-timetables`
- [x] Coordinators and HODs can both access the workspace according to their responsibilities
- [x] Coordinator can create periods, windows, seating profiles, and manual papers
- [x] HOD can sync manageable papers into an exam period
- [x] New periods start with deliberate paper selection instead of auto-selecting the full manageable catalogue
- [x] Generator response is surfaced as a draft review area
- [x] Review area now shows draft quality, flagged placements, and constraint diagnostics
- [x] Slot review table now surfaces placement notes instead of status alone
- [x] Publish control stays disabled while unscheduled papers remain

## Current Diagnostics

### Scheduled Placement Flags

The generator may flag draft slots with:

- `multi_room_allocation`
- `tight_capacity_fit`
- `same_day_pressure`
- `compressed_spacing`
- `peak_day_usage`

These are not hard failures. They are review cues for coordinators before publishing.

### Unscheduled Reasons

The generator aggregates unscheduled blockers such as:

- `window_too_short`
- `group_time_conflict`
- `same_day_not_allowed`
- `hard_daily_limit`
- `minimum_spacing`
- `rooms_unavailable`
- `capacity_insufficient`
- `too_many_rooms_required`
- `room_bundle_unavailable`

## Review Notes

### What is good enough for this iteration

- Coordinators can produce a realistic draft with room allocations
- The system explains why difficult papers failed or were placed tightly
- The review UI is calmer and more readable than a raw admin grid
- Draft lifecycle is now safer because publish and delete actions respect workflow state

### What should come next

- [ ] Optional manual drag/drop or reassignment workflow for draft exam slots
- [ ] Explicit student-level conflict support where cross-group exam membership exists
- [ ] More advanced fairness scoring across the full exam period
- [ ] Better edit flows for existing windows, papers, and seating profiles
- [ ] Export and publish views tailored for exam operations
- [ ] Scenario comparison or version history for multiple draft generations
- [ ] Bring back custom session-window overrides only after the override workflow and review controls are ready

## Verification Checklist

- [ ] Create an exam period with dates and spacing rules
- [ ] Add at least one active session window
- [ ] Add or confirm a seating profile
- [ ] Sync papers into the period
- [ ] Generate a draft
- [ ] Confirm room allocations appear
- [ ] Confirm flagged placements appear when capacity/spacing is tight
- [ ] Confirm unscheduled diagnostics appear when papers cannot fit
- [ ] Confirm publish is blocked when any paper remains unscheduled
- [ ] Publish only after reviewing draft quality
