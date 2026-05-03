# Access Layer Architecture

## Purpose

This document explains how timetable access for end users should evolve in TABLESYS.

It is written for future contributors so they can quickly understand:

- what the access layer is
- what it is not
- how it relates to the main timetable management platform
- where the current student work fits
- how the lecturer access layer should be added next

## Plain-English Summary

TABLESYS has two different product surfaces:

1. Management platform
   - Used by HODs, coordinators, admins, and timetable operators
   - Responsible for generation, editing, publishing, reporting, and control
   - Remains primarily a full web application
2. Access layer
   - Used by students and lecturers to consume published timetables
   - Optimized for speed, clarity, low friction, and repeat daily use
   - Must work well on phones, but is not limited to phones

This means we are not converting the whole platform into a mobile app.

We are building a flexible timetable access layer on top of the existing platform.

## Core Product Decision

The access layer is:

- mobile-first
- responsive
- installable as a PWA where useful
- still usable in a normal browser on desktop or laptop

The management layer is:

- web-first
- richer and more operational
- intentionally separate from end-user daily timetable consumption

## Why This Split Matters

Students and lecturers need fast answers:

- What is happening now?
- What is next?
- Where is my next class?
- Am I free right now?

Coordinators and HODs need control tools:

- create and generate timetables
- inspect conflicts
- manage rooms, groups, lecturers, and courses
- publish changes safely
- run reports and audits

These are different jobs, so they should not be forced into one UI shape.

## Access Layer Principles

All future access-layer work should follow these rules:

1. Published data only
   - Students and lecturers should read a published timetable view, not draft or in-progress generator state.
2. Mobile-first, not mobile-only
   - Design for phones first, but keep the experience responsive and useful on desktop browsers too.
3. Separate auth and API handling where appropriate
   - End-user access should stay isolated from admin auth and admin API assumptions.
4. Fast common views first
   - `now`, `next`, `today`, and `week` matter more than giant master grids.
5. Graceful offline behavior
   - The last synced personal timetable should still be visible if connectivity drops.
6. Keep the admin platform stable
   - Access-layer work must not quietly break HOD/coordinator/admin workflows.

## Current Architecture Direction

### Management Platform

- Main web app routes remain the operational platform
- Used by HODs, coordinators, admins, and superadmins
- Continues to own generation and administration flows
- Coordinator exam timetable planning should follow [coordinator-exam-timetable-blueprint.md](coordinator-exam-timetable-blueprint.md)

### Access Layer

- Dedicated user-facing route(s) inside the same frontend codebase
- Dedicated API surface for access-layer use cases
- PWA support for installability and offline reuse
- Read-optimized payloads shaped around personal timetable consumption

## Current Implementation Status

### Student Access Layer

The first active access-layer surface is the student portal.

Current implementation includes:

- dedicated student route: `/student`
- separate student API client in `frontend/src/studentPortalApi.ts`
- student-specific session token handling
- mobile-first student timetable UI
- PWA registration and service worker support
- local cached snapshot behavior for last synced personal timetable data

This is the beginning of the access layer, not the final architecture.

### Lecturer Access Layer

Lecturers need the same style of access surface, but with lecturer-focused information.

Minimum lecturer daily-use needs:

- teaching now / free now
- next class
- today timeline
- week view
- room and group context
- fast lookup where permitted

Recommended delivery:

- separate lecturer route
- separate lecturer-oriented page shell and cards
- access-layer API endpoints that resolve the authenticated lecturer's published view

## Recommended Route Strategy

Keep routes explicit and role-oriented.

Suggested shape:

- `/student`
- `/lecturer`

Do not overload the admin dashboard routes for these daily-use access experiences.

## Recommended Frontend Structure

As the access layer grows, keep it organized separately from admin pages.

Suggested direction:

- `frontend/src/pages/StudentPortal.tsx`
- `frontend/src/pages/LecturerPortal.tsx`
- `frontend/src/studentPortalApi.ts`
- `frontend/src/lecturerPortalApi.ts`
- `frontend/src/components/mobile/*` or `frontend/src/components/access/*`

The exact folder names can evolve, but the access-layer code should stay visibly separated from admin dashboard code.

## Recommended Backend Structure

The access layer should eventually read from a published snapshot or published-read service rather than raw admin-style queries.

Suggested direction:

- personal student published view
- personal lecturer published view
- lookup for room, group, lecturer, and course
- lightweight endpoints under `/api/v1/mobile/*` or another clearly scoped access-layer namespace

## Contributor Guidance

If you work on this area next:

1. Do not treat this as a full-platform mobile conversion.
2. Do not merge student and admin auth logic unless there is a very strong reason.
3. Keep lecturer access as the next sibling surface to student access.
4. Prefer access-layer APIs that are compact and role-aware.
5. Keep desktop browser usability even when designing for phones first.
6. Document any new route, token, cache key, or service worker behavior when you add it.

## Lecturer Test Venue Rule

Lecturer test scheduling should reuse the same room availability and conflict rules used by the published timetable views.

Design intent:

- If a lecturer does not select a venue, the test should default to the course's normal lecture room.
- If the lecturer searches for another venue, the search should filter by date, time, and capacity, then return only rooms that are actually free.
- When a test is scheduled, it should be stored as a booking on the room timeline so later overlapping room bookings are blocked.
- That booking must not interfere with already scheduled lectures; lecture conflicts remain hard validation failures.
- Lecturer and coordinator surfaces should use the same availability source so the room state stays consistent.

## Next Recommended Steps

1. Finish hardening the student access layer.
2. Add a lecturer access layer with its own route and API client.
3. Move toward published snapshot-backed access responses.
4. Expand offline/export/reminder support after the two personal access flows are stable.

## Decision Boundary

If the question is:

- "Who generates, edits, publishes, or manages timetables?"
  - use the management platform
- "Who needs to quickly view a published timetable or availability?"
  - use the access layer

That distinction should remain clear in both code and product design.
