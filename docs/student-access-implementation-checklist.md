# Student Access Implementation Checklist

## Purpose

This checklist is for anyone continuing work on the student access layer.

It answers three questions quickly:

1. What already exists?
2. What should not be redone?
3. What should be built next?

Use this document before changing the student portal.

## Working Environment

This workspace has been using Docker for the backend and frontend flow so far.

Prefer Docker-based verification when checking end-to-end behavior:

1. start services with `docker compose up -d --build`
2. verify the backend and frontend inside the running containers
3. use the Docker manual test guide for access-layer flows

## Product Boundary

This work is for the student access layer only.

Do not treat it as a rewrite of the whole platform.

The split remains:

- management platform
  - HODs
  - coordinators
  - admins
  - superadmins
- access layer
  - students now
  - lecturers next

The student access layer is mobile-first, but not mobile-only.
It should work well on phones, tablets, laptops, and normal desktop browsers.

## Primary Reference Docs

Read these first:

- [access-layer-architecture.md](/home/on3/DENNIS/TABLESYS/docs/access-layer-architecture.md:1)
- [student-access-docker-manual-test.md](/home/on3/DENNIS/TABLESYS/docs/student-access-docker-manual-test.md:1)
- [mobile-timetable-blueprint.md](/home/on3/DENNIS/TABLESYS/docs/mobile-timetable-blueprint.md:1)
- [mobile-implementation-roadmap.md](/home/on3/DENNIS/TABLESYS/docs/mobile-implementation-roadmap.md:1)
- [0001-mobile-delivery-architecture.md](/home/on3/DENNIS/TABLESYS/docs/adr/0001-mobile-delivery-architecture.md:1)

## Current Starting Point

### Frontend files already in use

- [frontend/src/pages/StudentPortal.tsx](/home/on3/DENNIS/TABLESYS/frontend/src/pages/StudentPortal.tsx:1)
- [frontend/src/studentPortalApi.ts](/home/on3/DENNIS/TABLESYS/frontend/src/studentPortalApi.ts:1)
- [frontend/src/main.tsx](/home/on3/DENNIS/TABLESYS/frontend/src/main.tsx:1)
- [frontend/src/pwa.ts](/home/on3/DENNIS/TABLESYS/frontend/src/pwa.ts:1)
- [frontend/public/sw.js](/home/on3/DENNIS/TABLESYS/frontend/public/sw.js:1)
- [frontend/public/manifest.webmanifest](/home/on3/DENNIS/TABLESYS/frontend/public/manifest.webmanifest:1)
- [frontend/index.html](/home/on3/DENNIS/TABLESYS/frontend/index.html:1)

### Backend files already supporting the student layer

- [backend/app/routers/student_portal.py](/home/on3/DENNIS/TABLESYS/backend/app/routers/student_portal.py:1)
- [backend/app/routers/mobile_portal.py](/home/on3/DENNIS/TABLESYS/backend/app/routers/mobile_portal.py:1)

### Backend files already supporting lecturer access

- [backend/app/routers/lecturer_portal.py](/home/on3/DENNIS/TABLESYS/backend/app/routers/lecturer_portal.py:1)

### Frontend files already supporting lecturer access

- [frontend/src/pages/LecturerLogin.tsx](/home/on3/DENNIS/TABLESYS/frontend/src/pages/LecturerLogin.tsx:1)
- [frontend/src/pages/LecturerPortal.tsx](/home/on3/DENNIS/TABLESYS/frontend/src/pages/LecturerPortal.tsx:1)

## What Is Already Done

Do not rebuild these from scratch unless there is a clear reason.

### Student route and separation

- dedicated student route exists at `/student`
- student portal is separate from admin dashboard routes
- student access uses a separate client file instead of sharing admin request logic

### Student API client

- separate student access client exists in `frontend/src/studentPortalApi.ts`
- student login is isolated from admin login flow
- student token handling is separate from admin token handling

### Student mobile/PWA foundation

- service worker registration exists
- manifest is linked
- install prompt handling exists
- offline cache support exists
- last synced personal data can be restored from local storage

### Student home experience already implemented

- Now card
- Next card
- Today at a glance summary
- bottom tab navigation:
  - Home
  - Today
  - Week
  - Search
  - More

### Student access features already implemented

- today view
- week view
- universal search for:
  - lecturer
  - room
  - course
  - group
- offline JSON export
- client-side ICS calendar export
- lightweight reminder toggle using browser notifications
- session-type filtering on Today and Week
- direct browser tab state via `?tab=...`

## What Must Not Be Redone

Avoid these mistakes:

1. Do not merge student auth back into the admin API interceptor.
2. Do not move student access into dashboard/admin routes.
3. Do not redesign the student portal as a squeezed admin table/grid.
4. Do not assume this is phone-only.
5. Do not remove the current offline/PWA path unless replacing it with something clearly better.
6. Do not invent fake backend features in the UI if the backend does not support them yet.

## Current Gaps

These are the most important incomplete areas.

### Backend gaps

- no true published snapshot engine yet
- initial `GET /api/v1/mobile/me/now` endpoint is now implemented (non-snapshot-backed)
- initial `GET /api/v1/mobile/rooms/free-now` endpoint is now implemented (non-snapshot-backed)
- centralized access-policy guard path is now in place for staff role checks and student active-account checks
- no published personal export endpoints yet
- baseline ETag support now exists on core mobile read endpoints (`/mobile/me/dashboard`, `/mobile/me/now`, `/mobile/me/today`, `/mobile/me/week`, `/mobile/rooms/free-now`), but full incremental client refresh strategy is still pending
- no notification/reminder persistence model yet
- lecturer access is now scaffolded, but shared read endpoints and richer lecturer metrics still need refinement

### Frontend gaps

- `StudentPortal.tsx` has started being split into smaller components, but it is still too large overall and needs further slimming
- reminder handling is lightweight and only practical while the portal is active
- free-room quick action now has baseline backend support via `/api/v1/mobile/rooms/free-now`; further UX polish is still needed
- [done 2026-04-27] responsive desktop/tablet portal layout pass completed (desktop tab navigation, adaptive panel grids, mobile-only dock)
- offline search is limited to what has already been cached
- full stale-while-revalidate/offline-first strategy is still pending, but conditional ETag refresh is now wired in the student API client for core mobile endpoints
- lecturer portal is currently minimal and should be expanded to match the student access quality bar for timetable viewing and metrics

### Verification gap

- frontend build/typecheck was verified in this environment on 2026-04-26 after installing Node/npm
- someone continuing this work should verify the frontend build in a Node-enabled shell before major new changes
- when practical, use Docker-based verification rather than bypassing the containerized setup

## Recommended Next Build Order

Work in this order unless there is a strong reason not to.

### Lecturer Access Starter Path

- confirm the lecturer login flow in Docker first
- expand lecturer dashboard metrics after basic timetable viewing is stable
- keep lecturer access read-mostly and timetable-focused, not SIS-like

### Phase 1: Harden What Exists

- [done 2026-04-26] run frontend build and typecheck in a proper Node environment
- [done 2026-04-26] add Docker-based manual test guide for the student access layer
- [done 2026-04-26] add demo student bootstrap script for repeatable `/student` testing in Docker
- [done 2026-04-26] verify Docker stack startup for student access prototyping (`/student`, student login, `/api/v1/mobile/me/dashboard`)
- test login, refresh, logout, offline reopen, install prompt, and tab query behavior
- fix any compile or runtime issues before adding more features

### Phase 2: Refactor Student Portal Structure

- [done 2026-04-26] extract initial student portal panels from `StudentPortal.tsx` into `frontend/src/components/student/StudentPortalPanels.tsx`
- [done 2026-04-26] move shared student access types into `frontend/src/components/student/types.ts`
- continue slimming `StudentPortal.tsx` into smaller components and hooks where useful
- suggested candidates:
  - `StudentHomePanel`
  - `StudentTodayPanel`
  - `StudentWeekPanel`
  - `StudentSearchPanel`
  - `StudentMorePanel`
  - `StudentSessionCard`
  - `StudentQuickActions`
- keep behavior unchanged while refactoring

### Phase 3: Add Real Access-Layer Backend Support

- [done 2026-04-26] add a real `GET /api/v1/mobile/me/now`
- [done 2026-04-26] add a real room-availability or free-room endpoint (`GET /api/v1/mobile/rooms/free-now`)
- [done 2026-04-26] add baseline ETag cache validation on core mobile read endpoints
- move toward published snapshot-backed access responses
- keep payloads compact and role-shaped

### Phase 4: Upgrade Student Utility Features

- proper free-room screen
- richer course detail cards
- better search result detail depth
- clearer stale/offline states
- [done 2026-04-27] stronger tablet/desktop responsive layout

### Phase 5: Strengthen Offline and Export

- [done 2026-04-26] wire frontend conditional requests (`If-None-Match`) for core mobile reads (`/mobile/me/dashboard`, `/mobile/me/now`, `/mobile/me/week`, `/mobile/rooms/free-now`)
- [done 2026-04-26] show cache-source status in student UI (live refresh vs cached 304 reuse)
- better cached search indexes
- explicit offline metadata and sync status
- server-backed calendar/PDF export if needed
- safer refresh/version behavior

### Phase 6: Lecturer Access Layer

- [done 2026-04-27] lecturer login endpoint and portal scaffold
- [done 2026-04-27] lecturer timetable endpoint scaffold
- [done 2026-04-27] lecturer courses endpoint scaffold
- [done 2026-04-27] lecturer dashboard metrics scaffold
- [done 2026-04-27] lecturer workload cards for now teaching, next-session countdown, daily load, weekly load vs max hours, and course breakdown
- next: align lecturer UX with student quality bar while keeping the access model simple and secure

## Exact “Start Here” Task List

If you are picking this up fresh, start here:

1. Read the reference docs listed above.
2. Read:
   - `frontend/src/pages/StudentPortal.tsx`
   - `frontend/src/studentPortalApi.ts`
   - `backend/app/routers/mobile_portal.py`
3. Run frontend verification in a Node-enabled shell.
4. If testing end-to-end in Docker:
   - start the stack with `docker compose up -d --build`
   - create the demo student with `docker compose exec backend python scripts/bootstrap_student_access_demo.py`
   - use [student-access-docker-manual-test.md](/home/on3/DENNIS/TABLESYS/docs/student-access-docker-manual-test.md:1)
5. Confirm these flows manually:
   - student login
   - home/dashboard
   - today filter chips
   - week filter chips
   - search and lookup detail
   - offline reopen
   - install prompt
   - JSON export
   - ICS export
6. Only after verification, choose one of:
   - refactor the student portal into smaller components
   - build true backend availability/free-room support
   - improve offline/sync behavior
  - extend the lecturer access layer with richer timetable metrics and summaries

## “Done vs Next” Quick Summary

### Done

- separate student route
- separate student API client
- student token separation
- PWA registration and service worker
- install prompt support
- offline cache restore
- Now / Next / Today shape
- Today and Week screens
- search for lecturer/room/course/group
- JSON export
- ICS export
- reminder toggle
- session filters
- URL tab sync
- build/typecheck verification in Node-enabled environment
- real backend `GET /api/v1/mobile/me/now`
- real backend `GET /api/v1/mobile/rooms/free-now`
- baseline ETag cache validation on core mobile read endpoints
- frontend conditional ETag requests wired for core mobile reads
- student UI now surfaces cache-source status after refresh
- student free-room panel wired to backend endpoint
- initial `StudentPortal.tsx` panel extraction completed
- shared student access types extracted into a dedicated module
- lecturer access layer scaffolded with login, timetable, courses, and dashboard metrics endpoints
- Docker manual-test guide for the student access layer
- centralized access-policy helper module now backs core staff-role and student account-state authorization checks
- Docker demo-student bootstrap script for `/student`
- Docker stack manually verified for core student-access startup and API login flow

### Next

- continue slimming the remaining large student portal file
- move toward published snapshot backend
- implement full incremental client refresh strategy on top of ETag responses
- improve desktop/tablet polish
- improve offline sync model

## If You Are About To Add Lecturer Access

Do not add lecturer code directly into the student portal.

Instead:

- create a dedicated lecturer route
- create a dedicated lecturer API client
- reuse patterns from the student access layer where appropriate
- keep lecturer and student access as sibling surfaces

## Definition of Success for the Student Layer

The student access layer is in a good state when:

- students can open `/student` and immediately understand `Now`, `Next`, and `Today`
- the view works well on phone and browser
- the last synced timetable is still useful offline
- lookup is fast and useful
- exports are practical
- future contributors can extend it without untangling admin code
