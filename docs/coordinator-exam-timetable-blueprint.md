# Coordinator Exam Timetable Blueprint

## Purpose

This document defines the coordinator-managed exam timetable feature for TABLESYS.

The goal is to schedule exam periods realistically, with the right constraints, without reusing the lecture timetable rules blindly.

This is a management-platform feature, not an access-layer feature.

## Current Implementation Snapshot

As of the current build, the system already includes:

- a separate exam scheduling router and service layer
- exam periods, session windows, seating profiles, papers, and draft slots
- effective-capacity room handling for exam seating profiles
- multi-room paper allocation
- heuristic generation with constrained-paper prioritization
- diagnostic flags for tight placements and unscheduled papers
- a coordinator review workspace for generating, reviewing, and publishing drafts

See [exam-timetable-implementation-checklist.md](/home/on3/DENNIS/TABLESYS/docs/exam-timetable-implementation-checklist.md) for the working checklist and current follow-up items.

## Why This Needs Its Own Engine

Exams behave differently from lectures:

- they happen inside a fixed date range
- rooms are used only for exam activity during the exam period
- papers must fit venue seating arrangements, not just raw room capacity
- the same paper should not be split across separate sessions
- students in the same group should rarely write multiple papers on the same day
- spacing between papers matters more than in weekly lecture scheduling
- session windows are usually fixed, such as morning and afternoon

Because of that, the exam planner should be a separate scheduling engine, even if it reuses some shared validation and room-availability helpers.

## Primary References

Read these first:

- [access-layer-architecture.md](access-layer-architecture.md)
- [lecturer-access-implementation-checklist.md](lecturer-access-implementation-checklist.md)
- [mobile-timetable-blueprint.md](mobile-timetable-blueprint.md)
- [backend/app/services/timetable_generator.py](/home/on3/DENNIS/TABLESYS/backend/app/services/timetable_generator.py)
- [backend/app/services/validation_service.py](/home/on3/DENNIS/TABLESYS/backend/app/services/validation_service.py)
- [backend/app/routers/rooms.py](/home/on3/DENNIS/TABLESYS/backend/app/routers/rooms.py)
- [backend/app/models/__init__.py](/home/on3/DENNIS/TABLESYS/backend/app/models/__init__.py)

## Product Boundary

This work belongs to the coordinator and timetable management side of the system.

It should not be mixed into the lecturer/student access layer.

The coordinator workflow should:

- define the exam period
- define exam sessions and room rules
- import or build the exam paper list
- generate a conflict-free exam timetable
- review exceptions and overrides
- publish the final exam timetable

## Core Rules

### Hard Rules

These should fail validation if broken:

- Every exam must fall inside the configured exam period.
- No two exams may overlap in the same room.
- No group may be assigned to two exams at the same time.
- The same paper must stay in one session and can be in in different rooms arrangement depending on the numbr people seating for that exam.
- A session must respect the venue seating capacity for the chosen arrangement.
- If a room is committed to an exam booking, later overlapping exam bookings must be rejected.
- Existing committed lecture bookings must still be treated as protected constraints if the institution allows any overlap between teaching and exam administration data.

### Soft Rules

These should be optimized, not merely checked:

- avoid multiple papers for the same group on the same day
- maximize spacing between papers for the same group
- spread difficult or high-volume papers across the period
- prefer balanced use of morning and afternoon sessions
- minimize unnecessary room changes for related papers

## Existing Building Blocks to Reuse

The current codebase already has useful pieces we should build on:

- `TimetableSlot` and room assignment history in [backend/app/models/__init__.py](/home/on3/DENNIS/TABLESYS/backend/app/models/__init__.py)
- room availability and capacity fields in [backend/app/routers/rooms.py](/home/on3/DENNIS/TABLESYS/backend/app/routers/rooms.py)
- overlap and conflict validation in [backend/app/services/validation_service.py](/home/on3/DENNIS/TABLESYS/backend/app/services/validation_service.py)
- the existing timetable generation and resource conflict logic in [backend/app/services/timetable_generator.py](/home/on3/DENNIS/TABLESYS/backend/app/services/timetable_generator.py)

The important point is not to copy lecture logic as-is, but to reuse the same ideas for overlap detection, room blocking, and resource validation.

## Recommended Data Model

A separate exam engine will likely need its own domain objects.

Suggested entities:

- `ExamPeriod`
  - start date, end date, academic year, semester/term, published state
- `ExamPaper`
  - course, group(s), paper duration, paper code, expected candidate count
- `ExamSessionWindow`
  - morning, afternoon, or custom windows such as `08:00-12:00` and `14:00-17:00`
- `ExamSeatingProfile`
  - venue seating arrangement rules and effective capacity factor
- `ExamSlot`
  - date, session window, room, paper, audience, invigilator metadata if needed
- `ExamConstraintRuleSet`
  - spacing rules, max papers per day, capacity thresholds, override flags
- `ExamTimetableVersion`
  - published snapshots and rollback history

Minimal-change fallback:

- if the team wants the smallest possible schema change, exam bookings could reuse a timetable-slot-like table with an `exam` session type
- that is only acceptable if the planning logic stays separate from lecture generation
- the safer long-term path is a distinct exam engine with its own tables and a shared availability layer

## Seating Arrangement Plan

This is one of the most important pieces.

Coordinators should be able to define how students sit in a venue for exams.

Examples:

- standard one-student-per-desk
- spaced seating with empty seats between candidates
- alternate-row seating
- lab/computer-based seating
- special-needs arrangement with wider spacing

The seating arrangement should reduce the room's effective capacity automatically.

Suggested rule:

- physical room capacity is the raw maximum
- exam arrangement applies a factor or seat map that produces effective capacity
- the scheduler uses effective capacity, not raw lecture capacity, when placing a paper

This means a room that can hold 120 students for lectures might only hold 80 or 60 in an exam arrangement.

## Session Window Plan

Exams should be scheduled in fixed windows instead of free-form lecture-style slots.

Default example windows:

- Morning: `08:00-12:00`
- Afternoon: `14:00-17:00`

The coordinator should be able to configure:

- exact start and end times
- break windows between sessions
- whether weekends are allowed
- whether any evening sessions exist
- whether special papers can use custom windows

A paper's duration must fit completely inside one allowed session window.

## Group Spacing Plan

The scheduler should be aware of group-level paper load.

Recommended spacing rules:

- the same group should ideally not write two papers on the same day
- if that is unavoidable, enforce a minimum gap between papers
- keep a larger gap for high-enrolment or high-difficulty papers
- allow controlled exceptions with coordinator override

Suggested constraints to start with:

- preferred: one paper per group per day
- hard cap: no more than two papers per group per day unless explicitly overridden
- minimum gap: configurable by institution, for example 24 hours or one full session block

## Scheduling Workflow

### Step 1: Define the exam period

The coordinator creates the exam window, for example:

- start date
- end date
- term or semester
- active year level(s)
- lock/publish state

### Step 2: Load the paper list

The engine should accept papers from existing course and group mappings.

It should use the current academic structure to determine:

- which groups sit which paper
- whether a paper is shared across groups
- the number of candidates per paper
- the duration of each paper

### Step 3: Calculate effective room capacity

For each room and seating profile:

- read physical room capacity
- apply seating arrangement factor or seat map
- subtract unusable seats if needed
- produce the effective exam capacity

### Step 4: Generate candidate placements

The engine should test:

- date
- session window
- room
- paper
- group audience
- capacity fit
- spacing fit
- already-committed room bookings

### Step 5: Solve and rank options

The engine should either:

- use a separate solver service, or
- use a shared solver core with different exam objective weights

Recommended objective priorities:

1. satisfy all hard constraints
2. keep same-paper audiences together
3. reduce same-group day collisions
4. maximize spacing between papers
5. prefer better room-capacity fit
6. balance morning vs afternoon usage

### Step 6: Review exceptions

The coordinator should be able to inspect:

- papers that could not be placed
- papers that only fit in one room type
- papers with spacing conflicts
- groups with overloaded exam days
- rooms that are underused or overused

### Step 7: Publish and lock

Once the coordinator publishes the exam timetable:

- the exam room bookings become active
- overlapping bookings are blocked
- the timetable is frozen until an explicit edit or republish action
- audit history should record the publish event

## UI Plan for Coordinators

A practical coordinator workflow should include:

- exam period setup screen
- seating arrangement profile editor
- paper import or paper selection screen
- session window editor
- generation preview with conflicts and warnings
- room-capacity fit view
- manual override panel
- publish/lock control
- printable or exportable timetable output

## Suggested Backend Structure

Recommended service split:

- `backend/app/services/exam_timetable_generator.py`
- `backend/app/services/exam_validation_service.py`
- `backend/app/services/exam_seating_service.py`
- `backend/app/routers/exam_timetables.py`
- `backend/app/routers/exam_rooms.py` or shared room search helpers

The engine should reuse shared conflict helpers where possible, but keep exam rules isolated from lecture generation.

## Implementation Phases

### Phase 1: Domain and Schema
- define exam period and exam slot models
- define seating arrangement profiles
- define session windows
- define paper/group audience mapping

### Phase 2: Capacity and Seating Logic
- calculate effective room capacity by seating arrangement
- add room arrangement metadata
- validate room fit before scheduling

### Phase 3: Scheduling Engine
- build a separate exam solver or planning service
- apply hard and soft constraints
- generate the first complete exam timetable

### Phase 4: Coordinator UI
- build screens for period setup, paper review, and generation
- show warnings, conflicts, and room fit
- support overrides and republishing

### Phase 5: Publishing and Locking
- publish final exam timetable
- lock room bookings for the period
- keep audit history and rollback support

### Phase 6: Testing and Hardening
- add deterministic test cases for spacing rules
- test same-group same-day collision prevention
- test seating arrangement capacity math
- test publish/lock behavior
- test room conflict rejection across exam bookings

## Open Questions

These should be decided before implementation begins:

- Should exam bookings use separate tables or a shared timetable-slot table with an `exam` type?
- Should seating arrangement be room-level, exam-level, or both?
- Should the engine allow one paper to span multiple rooms only when the seating profile requires it?
- How should invigilation be modeled if it is added later?
- Should make-up exams and re-sits share the same engine and period rules?
- What is the minimum acceptable gap between papers for the same group?
- Are any papers allowed in custom windows outside the default morning and afternoon sessions?
- Should the final published exam timetable completely freeze lecture edits in the same rooms during that date range?

## Success Criteria

The feature is successful when:

- coordinators can define a realistic exam period
- papers are scheduled inside the allowed window only
- room capacity is calculated from exam seating, not lecture seating
- same-paper audiences stay together in one session
- same-group same-day collisions are rare and controlled
- room bookings become exclusive during the exam period
- the final timetable can be published, audited, and reviewed safely

## Next Step

If we implement this, the next work item should be a concrete schema and API design for the exam period, exam slot, and seating arrangement models.
