# Course-to-Group Mapping Scope

## Purpose

This document records how course-to-group mapping currently works in TABLESYS after the recent ownership, visibility, and scheduling updates.

The goal is to keep one accurate picture of:

- where enrolment is written
- where delivery is written or derived
- who controls cross-department enrolment
- how the timetable generator interprets shared audiences

## Implemented Foundation

The following foundation is now implemented:

- a unified course-side enrolment API for main groups:
  - `GET /api/v1/courses/{course_id}/enrollment-map`
  - `PUT /api/v1/courses/{course_id}/enrollment-map`
- a backend `CourseMappingService` that:
  - resolves eligible main groups by owner/shared departments and level
  - saves main-group enrolment in `GroupAssignment`
  - rebuilds lecture delivery in `CourseGroupLink`
  - clears stream lecture remnants under a parent when that parent is explicitly enrolled from the course page
- a backend `GroupCourseMappingService` that:
  - resolves same-level visible courses for one group
  - auto-seeds baseline course visibility from own department, `GEN`, and explicitly shared external courses
  - marks outside-owned courses as read-only on the group side
- the Courses page now uses one owner-side course dialog for pulling same-level groups into one specific course
- the Groups page now uses one group-side curriculum dialog that:
  - allows editing department-owned courses
  - shows shared-in outside-owned courses as read-only
  - keeps stream-specific refinement on streams only
- explicit old mapping routes have been removed:
  - old course push endpoints
  - old standalone `course_group_links` router
- tutorials and practicals now follow the enrolled lecture audience automatically during generation unless custom explicit mapping is added later
- audit coverage exists for:
  - `CourseGroupLink` mutations
  - manual slot assignment
  - manual slot creation
- `GEN` course visibility is now owner-based rather than tied to whether `GEN` has a local cohort at that level
- oversized audience fallback is now explicit in the generator:
  - if no room fully fits, prefer the biggest available room as the institutional best-effort compromise

## Executive Summary

The current system uses two mapping layers and one ownership rule:

- `GroupAssignment`
  - enrolment truth
  - answers: which groups take this course at all?
- `CourseGroupLink`
  - delivery truth for lecture and explicit session audiences
  - answers: how is this course delivered to the enrolled groups?
- ownership rule
  - the course owner controls cross-department enrolment for that course
  - receiving departments can see the result on their group view, but do not control it there

That means:

- group-side editing controls local department curriculum choices
- course-side editing controls shared-course pull-in for one specific course
- lecture delivery is rebuilt from enrolment into `CourseGroupLink`
- the generator uses shared audiences as one occupied teaching audience for conflicts and room sizing

## Core Domain Model

### Student group hierarchy

File: `backend/app/models/__init__.py`

- `StudentGroup`
  - main groups: `parent_group_id is null`
  - streams: `group_type = stream`
  - session subgroups: `lab_group`, `tutorial_group`, `drawing_group`
- `display_code`
  - shorthand label used in timetable/export displays
- `parent_group_id`
  - defines stream and subgroup hierarchy

### Course sharing semantics

Files:

- `backend/app/models/__init__.py`
- `backend/app/routers/courses.py`
- `backend/app/utils/department_utils.py`

Relevant fields:

- `department_id`
- `course_type`
- `shared_with_department_ids`

Meaning:

- own-department course: normal departmental ownership
- general course: often owned by the General Engineering department
- shared course: visible to other departments through `shared_with_department_ids`
- `GEN` ownership does not imply universal consumption
- a `GEN` course may be:
  - universal
  - targeted to only specific departments
- `GEN` can control higher-level service courses even if `GEN` itself has no local cohort at that level

### Mapping tables

File: `backend/app/models/__init__.py`

#### `GroupAssignment`

Role today:

- enrolment truth
- records that a group takes a course
- still used by generator fallback logic

Limitations:

- no session type
- no shared batching
- no distinction between lecture/tutorial/practical delivery

#### `CourseGroupLink`

Role today:

- lecture delivery truth
- explicit per-session mapping when needed
- supports `session_type`
- supports `is_shared`
- supports `shared_batch_id`

Strength:

- can represent real teaching audience for lecture/tutorial/practical sessions
- shared lecture batches live here

### Timetable slot audience storage

Files:

- `backend/app/models/__init__.py`
- `backend/app/services/timetable_generator.py`
- `backend/app/utils/group_audience.py`

Relevant fields on `TimetableSlot`:

- `group_id`
- `shared_group_ids`
- `combined_size`
- `shared_batch_id`

Meaning:

- `group_id` is the primary/representative group
- `shared_group_ids` holds the rest of the audience
- `combined_size` is the total headcount used for room sizing

This is runtime output, not the source of truth for enrolment edits.

## Current Write Paths

## 1. Group-side curriculum editing

Frontend:

- `frontend/src/pages/GroupsPage.tsx`
- `frontend/src/components/GroupCourseManager.tsx`
- `frontend/src/api.ts`

Backend:

- `backend/app/routers/groups.py`

Flow:

`GroupsPage -> GroupCourseManager -> POST /api/v1/groups/{group_id}/courses`

What it does:

- loads one group-side course map
- groups same-level courses into:
  - department-controlled courses
  - shared-in outside-owned courses
- auto-seeds a fresh group's baseline choices from recommended same-level courses
- writes selected department-controlled `course_ids` into `GroupAssignment`
- for stream groups, calls `_synchronize_stream_lecture_links()`

Important behavior:

- outside-owned courses remain visible but read-only here
- receiving departments can see external/shared-in courses, but cannot remove them from the group side
- stream groups inherit parent baseline courses when still unconfigured
- if the same course stays on multiple sibling streams, lecture links become shared
- if a course remains on only one stream, it becomes stream-specific

Important limitation:

- only lecture `CourseGroupLink` rows are synchronized automatically here
- tutorial/practical delivery is not explicitly managed here

## 2. Course-side owner enrolment

Frontend:

- `frontend/src/pages/CoursesPage.tsx`
- `frontend/src/components/CourseGroupAssigner.tsx`

Backend:

- `backend/app/routers/courses.py`

Flow:

`CoursesPage -> CourseGroupAssigner -> GET/PUT /api/v1/courses/{course_id}/enrollment-map`

What it does:

- lets the owning department HOD or coordinator pull same-level main groups into one specific course
- resolves eligible main groups by:
  - course level
  - owner department
  - `shared_with_department_ids`
- writes `GroupAssignment`
- rebuilds lecture `CourseGroupLink`

Important behavior:

- this is the controlling UI for cross-department enrolment
- receiving departments consume the result but do not control it from their side
- `GEN` can manage its owned service courses here even if `GEN` has no local cohort at that level

Important limitation:

- the current dialog still manages lecture delivery only
- tutorial/practical delivery remains derived

## 3. Group creation and stream subdivision

Frontend:

- `frontend/src/pages/GroupsPage.tsx`

Backend:

- `backend/app/routers/groups.py`

What happens on create/update/subdivide:

- `_inherit_parent_courses_to_stream()`
  - copies parent baseline course assignments into a new stream if the stream is still empty
- `_synchronize_stream_lecture_links()`
  - rebuilds lecture `CourseGroupLink` rows for sibling streams

Why this matters:

- stream creation mutates mapping state
- stream creation is not just structure creation; it also creates inherited enrolment and shared lecture behavior

## 4. Timetable slot reassignment

Frontend:

- `frontend/src/pages/TimetableViewPage.tsx`
- `frontend/src/components/TimetableAssignmentPanel.tsx`

Backend:

- `backend/app/routers/timetables.py`

Flow:

`TimetableViewPage -> TimetableAssignmentPanel -> POST /api/v1/timetables/slots/{slot_id}/assign`

What it does:

- can overwrite `slot.group_id`
- can overwrite `slot.lecturer_id`
- validates timetable conflicts after update

Important limitation:

- this changes a saved slot, not the underlying mapping source
- this can make a timetable look different from the source rules that generated it

## 5. Manual slot creation

Frontend:

- `frontend/src/components/CreateManualSlotModal.tsx`

Backend:

- `backend/app/routers/timetables.py`

Flow:

`CreateManualSlotModal -> POST /api/v1/timetables/{timetable_id}/slots/manual`

What it does:

- creates a fixed timetable slot with direct `course_id`, `group_id`, `lecturer_id`, `room_id`

Important limitation:

- bypasses mapping source tables entirely
- useful operationally, but should be treated as an exception layer

## Current Read and Consumer Paths

## 1. Effective group course view

Backend:

- `backend/app/routers/groups.py`

Endpoints:

- `GET /api/v1/groups/{group_id}/courses`
- `GET /api/v1/groups/{group_id}/course-map`

Behavior:

- returns effective group courses
- includes direct `GroupAssignment` courses
- also includes `CourseGroupLink` courses
- for streams with no direct selection, falls back to parent courses
- group-side map distinguishes:
  - locally editable courses
  - outside-owned read-only courses

## 2. Timetable generation

Backend:

- `backend/app/services/timetable_generator.py`

Current generator rule order:

### Lecture

1. if explicit `CourseGroupLink` rows exist for lecture, use them literally
2. otherwise fall back to `GroupAssignment`
3. if a course is assigned directly to streams, treat it as stream-specific/shared depending on sibling selection
4. if a course is assigned only to the parent group, keep the parent combined

### Tutorial

1. explicit tutorial `CourseGroupLink` if present
2. else tutorial subgroups under lecture audience
3. else lecture audience itself

### Practical

1. explicit practical `CourseGroupLink` if present
2. else lab/drawing subgroups under lecture audience
3. if multiple practical subgroups exist, create a rotating slot

Important current behavior:

- when a lecture is shared, the generator uses one combined audience
- all groups inside `covered_group_ids` are treated as occupied for conflict checking
- room sizing uses the combined audience size
- if no room fully fits, the generator now explicitly prefers the biggest available room

## 3. Timetable display and exports

Files:

- `backend/app/routers/timetables.py`
- `backend/app/services/export_service.py`
- `backend/app/routers/print_views.py`
- `backend/app/utils/group_audience.py`

Behavior:

- timetable view reads saved slots
- audience is resolved from `shared_group_ids`
- if a slot is saved on a parent group with no explicit `shared_group_ids`, the audience resolver can expand that parent to stream labels for display

## 4. Dashboard readiness

Backend:

- `backend/app/services/dashboard_service.py`

Current status:

- this area has been improved, but still needs validation against the current owner/group split so enrolment coverage and delivery coverage stay aligned in reporting

## Logging and Notification Coverage

Covered today:

- group create/update/delete
- group course update
- course enrolment updates
- `CourseGroupLink` mutations
- timetable generation
- manual slot assignment
- manual slot creation

Still worth validating:

- that all current owner-side and group-side mapping mutations surface the right audit and notification detail after the UI split

## UI Surfaces in Scope

### Courses page

File: `frontend/src/pages/CoursesPage.tsx`

Contains:

- course CRUD
- `CourseGroupAssigner`
  - owner-side group enrolment for one specific course
  - cross-department pull-in for that course

### Groups page

File: `frontend/src/pages/GroupsPage.tsx`

Contains:

- group CRUD
- stream/subgroup creation
- `GroupCourseManager`
  - group-side curriculum view
  - local editing of department-owned courses
  - read-only visibility of shared-in outside-owned courses

### Timetable page

Owns:

- generated timetable output
- timetable exceptions

Should not own:

- persistent course-group truth

## Current Risks and Contradictions

## 1. Two-layer complexity remains

The system now uses the right separation more deliberately, but it still depends on everyone respecting:

- `GroupAssignment` for enrolment truth
- `CourseGroupLink` for delivery truth

## 2. Ownership must stay explicit

The current policy is:

- course owner controls cross-department enrolment
- receiving departments see read-only on the group side

That is correct, but the UI must keep making that obvious.

## 3. Session delivery is still only partly exposed

Tutorial/practical delivery is mostly derived rather than explicitly configured in the main UI.

## 4. Timetable slot editing can drift from mapping truth

Manual slot reassignment and manual slot creation are still operational exception tools, not mapping tools.

## 5. Oversized room allocation is a compromise

The explicit policy is now:

- if no room fully fits, prefer the biggest available room

That is the institutionally preferred fallback, but it is still a compromise and not a true fit.

## Recommended Target Logic

## Recommendation: keep two layers, but make them explicit

### Layer 1: Enrollment mapping

Question answered:

Which groups take this course at all?

Source:

- `GroupAssignment`

### Layer 2: Session delivery mapping

Question answered:

How is each session type delivered to the enrolled groups?

Source:

- `CourseGroupLink`

### Layer 3: Timetable exception layer

Question answered:

What manual timetable changes exist for an already generated timetable?

Source:

- saved slot override/manual slot mechanisms

## Current Ownership Rule

- course owner controls cross-department enrolment for that course
- group-side editing controls local department curriculum
- receiving departments see shared-in courses as read-only

## Recommended UI Direction

Keep the user mental model simple:

- Groups page:
  - "What does this group take?"
- Courses page:
  - "Who else should take this course?"
- Timetable page:
  - "What exceptions did we make?"

## Proposed Implementation Plan

## Phase 1: Stabilize semantics

- keep comments and UI labels aligned with the owner/group split
- keep audit and notifications complete for both edit surfaces

## Phase 2: Centralize reconciliation

- extract stream sync and default delivery derivation into one service
- keep group-side and course-side writes aligned to the same reconciliation path

## Phase 3: Finish reporting and cleanup

- validate dashboard readiness against enrolment and delivery separately
- fix any remaining cleanup paths that still rely on old assumptions

## Phase 4: Expand explicit session UI only if needed

- keep tutorial/practical derived by default
- only add explicit UI if a real operational need appears

## Phase 5: Protect against drift

- keep timetable slot edits exception-only
- optionally surface oversized-room fallback more clearly in diagnostics and UI

## Test Coverage We Already Have

Files:

- `backend/tests/test_scheduler.py`
- `backend/tests/test_group_audience.py`
- `backend/tests/test_course_mapping_service.py`
- `backend/tests/test_group_course_mapping_service.py`
- `backend/tests/test_course_visibility.py`

Current coverage includes:

- parent-assigned common stream course stays combined
- course present on multiple sibling streams becomes shared
- course present on only one stream stays separate
- parent-group timetable slots can display stream audience labels correctly
- course owner eligibility across owner/shared departments
- group-side recommendation and read model basics
- `GEN` owner visibility for owned courses even without local cohorts at that level

## Tests We Still Need

- end-to-end group-side read-only visibility for outside-owned courses
- dashboard readiness reflects both enrollment and delivery correctly
- explicit tutorial/practical custom mapping works end-to-end if we expose it later
- oversized-room fallback surfacing in diagnostics/reporting

## Key Decisions Still Worth Keeping Explicit

1. Keep `GroupAssignment` as enrollment truth, or retire it later?
2. Keep current ownership rule:
   - course owner controls cross-department enrolment
   - receiving departments see read-only?
3. Keep tutorial/practical mapping mostly derived, or expose it explicitly?
4. Keep manual timetable group changes as auditable exceptions only?
5. Surface oversized-room fallback more visibly in diagnostics/UI?

## Working Recommendation

1. Keep `GroupAssignment` as enrollment truth for now.
2. Treat `CourseGroupLink` as delivery truth.
3. Keep the ownership split:
   - group side for local department curriculum control
   - course side for owner-controlled cross-department pull-in
4. Add one reconciliation service so all write paths stay aligned.
5. Keep timetable slot edits as exceptions, not mapping truth.
6. Keep the explicit “biggest room for oversized audience” fallback as the institutional compromise.

That path gives us the cleanest improvement with the least dangerous migration.
