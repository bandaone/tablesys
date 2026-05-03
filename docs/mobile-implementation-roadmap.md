# Mobile Timetable Implementation Roadmap

## Objective

Build a mobile-first but browser-flexible timetable access layer for students and lecturers by adding a published read layer, role-aware APIs, and a dedicated PWA-capable user experience.

## Chosen Technology Direction

Use the existing stack and extend it cleanly:

- Backend: FastAPI + SQLAlchemy + PostgreSQL + Redis
- Frontend: React 18 + TypeScript + Vite + MUI
- Access delivery: Progressive Web App inside the current frontend
- Background work: existing Redis/Celery capability for snapshot materialization and reminder jobs

This avoids introducing a second frontend framework or a native app codebase before the access-layer product-market fit is proven.

## Product Boundary

This roadmap does not convert the full TABLESYS platform into a mobile app.

Instead, it adds a separate access layer for:

- students
- lecturers

The main timetable management workflows for HODs, coordinators, admins, and superadmins remain in the existing web platform.

## Delivery Principles

- access layer reads published data only
- fast paths first: `now`, `next`, `today`
- no giant timetable payloads for phone screens
- offline support must degrade gracefully
- desktop browser usage must still be supported
- every phase should leave the product demonstrably better

## Workstreams

### Workstream A: Published Snapshot Backbone

Deliverables:

- publish lifecycle for timetables
- snapshot materialization service
- read-optimized lookup strategy
- cache invalidation plan

Tasks:

1. define published timetable entities and version keys
2. add publish action and snapshot generation service
3. build derived indexes for group, lecturer, room, and course
4. add Redis caching for hot mobile endpoints
5. return `published_at`, `version`, and `last_updated` in responses

Acceptance criteria:

- a published timetable can be materialized without touching draft data
- mobile APIs can serve personal views without scanning full raw slot sets repeatedly

### Workstream B: Mobile API Layer

Deliverables:

- new `/api/v1/mobile/*` endpoints
- compact response contracts
- authorization rules per audience

Tasks:

1. add mobile router
2. implement `/me`, `/me/now`, `/me/today`, `/me/week`
3. implement search and availability endpoints
4. add export endpoints for PDF and ICS
5. add ETag support for cheap refresh

Acceptance criteria:

- Home can render from 1 to 2 lightweight requests
- Today and Week endpoints return mobile-shaped data without frontend over-processing

### Workstream C: Mobile Frontend Experience

Deliverables:

- app-like route structure
- bottom navigation
- now/next/today dashboard
- swipe-friendly week view

Tasks:

1. create dedicated mobile page components
2. add responsive app shell and bottom tabs
3. build Home cards for current, next, and free-state scenarios
4. build Today timeline cards
5. build Week day-switcher
6. build Search and More screens

Acceptance criteria:

- the mobile experience does not feel like a squeezed admin page
- the first screen is immediately useful on a phone

### Workstream D: PWA and Offline

Deliverables:

- web app manifest
- service worker caching
- install prompt
- offline fallback states

Tasks:

1. add manifest and icons
2. register service worker
3. cache bootstrap, me, now, today, and week responses
4. store last successful sync metadata
5. show stale/offline status in UI

Acceptance criteria:

- users can reopen the app and see their latest synced timetable without internet
- install-to-home-screen works on supported devices

### Workstream E: Notifications and Reminders

Deliverables:

- reminder preferences
- scheduled notification jobs
- calendar-friendly export

Tasks:

1. add reminder preference model or settings payload
2. implement in-app/browser reminder scheduling path
3. generate ICS exports with alarm support
4. plan push notification support after stable PWA rollout

Acceptance criteria:

- users can opt into simple pre-class reminders
- calendar export works as a practical fallback

## Recommended Build Order

### Phase 0: Foundation and Design Prep

Scope:

- approve architecture
- define response contracts
- agree publish vocabulary
- create mobile design tokens and status semantics

Output:

- this documentation set
- implementation tickets
- low-risk development sequence

### Phase 1: Student Mobile MVP

Scope:

- published personal snapshot service
- `/mobile/me/now`
- `/mobile/me/today`
- `/mobile/me/week`
- mobile Home/Today/Week screens
- installable PWA shell
- offline cache for student personal data

Output:

- student timetable access on the go and in-browser

### Phase 2: Lecturer Mobile MVP

Scope:

- lecturer personal snapshot resolution
- lecturer Home/Today/Week views
- free/busy status
- next teaching slot
- lecturer-focused route and API client

Output:

- lecturer daily-use access experience

### Phase 3: Universal Lookup

Scope:

- room lookup
- lecturer lookup
- course lookup
- group lookup
- public availability rules

Output:

- strong campus utility beyond personal timetable access

### Phase 4: Export and Reminder Layer

Scope:

- PDF export
- ICS export
- reminder preferences
- browser/device notifications

Output:

- better retention and fewer missed classes

### Phase 5: Publish Alerts and Refinement

Scope:

- change alerts
- room-change notifications
- performance hardening
- analytics polish

Output:

- production-grade adoption layer

## API Contract Priorities

Implement these first:

1. `GET /api/v1/mobile/bootstrap`
2. `GET /api/v1/mobile/me`
3. `GET /api/v1/mobile/me/now`
4. `GET /api/v1/mobile/me/today`
5. `GET /api/v1/mobile/me/week`

Implement next:

1. `GET /api/v1/mobile/lookup`
2. `GET /api/v1/mobile/rooms/{id}/availability`
3. `GET /api/v1/mobile/lecturers/{id}/availability`
4. `GET /api/v1/mobile/me/export/pdf`
5. `GET /api/v1/mobile/me/export/ics`

## Data Model Preparation

Recommended additions:

- published timetable version marker
- published snapshot tables or durable JSON snapshots
- reminder preferences storage
- optional device registration table for later push support

Do not overload `generation_metadata` as the permanent mobile data store. It is useful for generation context but should not become the entire published mobile domain.

## Security and Privacy Notes

- students should see public availability, not unrestricted internal staff data
- room occupancy visibility should follow institutional policy
- published endpoints must never return draft overrides unless published
- exports should respect the authenticated audience

## Performance Notes

- precompute current-day slices during publish
- use Redis for `now` and `today`
- include entity display labels directly in payloads
- prefer incremental refresh with `ETag`

## Suggested First Tickets

1. Create `docs/` architecture artifacts and align naming
2. Add `mobile_portal` router scaffold
3. Create `published_timetable_service` scaffold
4. Define response schemas for `bootstrap`, `me`, `now`, `today`, `week`
5. Build student `now` endpoint from current timetable data as an interim implementation
6. Add mobile route group and basic PWA shell in the frontend
7. Replace current `StudentPortal` landing experience with the new mobile Home once the new stack is ready

## Milestone Definition

### Milestone 1

Student can install the app, open it on a weak connection, and immediately see `Now`, `Next`, and `Today`.

### Milestone 2

Lecturer can do the same and also see free/busy teaching status.

### Milestone 3

Any authorized user can check room or lecturer availability in seconds.
