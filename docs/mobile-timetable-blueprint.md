# Mobile Timetable Blueprint

## Purpose

This document defines the mobile-first timetable experience that sits on top of the existing TABLESYS scheduling platform. The goal is daily adoption, not just feature completeness.

This experience should be understood as an access layer, not a replacement for the main timetable management platform.

The mobile product should answer four questions faster than any existing page:

1. What is happening now?
2. What is next?
3. Where do I need to be?
4. Am I free right now?

## Product Goal

Deliver a professional, installable, low-bandwidth timetable access experience for students and lecturers without making timetable generation or administration more fragile.

## Product Shape

The product is split into three layers:

1. Published timetable engine
   - Snapshot-based and read-optimized
   - Separated from the generator and admin editing workflows
   - One canonical source for student, lecturer, room, and group mobile views
2. Access portal
   - Mobile-first, responsive, and installable
   - Opens to `Now`, `Next`, and `Today`, not a giant desktop grid
   - Personalizes automatically to the logged-in user
3. Offline companion capabilities
   - Cached personal timetable
   - Exportable PDF and calendar copy
   - Reminders and install-to-home-screen behavior

## Current Codebase Baseline

TABLESYS already has a strong base for this work:

- Backend: FastAPI, SQLAlchemy, PostgreSQL, Redis, notifications, reporting
- Frontend: React 18, TypeScript, Vite, MUI, existing routing and auth contexts
- Existing student portal: `/student` with login, timetable, and course access
- Existing timetable domain: `Timetable`, `TimetableSlot`, `TimetableVersion`

The missing piece is a dedicated published/mobile access layer with snapshot-friendly APIs and offline behavior.

## Product Boundary

The access layer is for timetable consumers:

- students
- lecturers

The main web platform remains for timetable operators:

- HODs
- coordinators
- admins
- superadmins

This split is intentional and should remain clear in both architecture and UI decisions.

## Recommended Architecture

### 1. Keep the generator and mobile delivery separate

The timetable generator remains the source of draft and admin-facing schedules.

The mobile experience reads from a published representation only. This avoids:

- exposing draft or incomplete data to students
- tying mobile performance to admin pages
- breaking the mobile app when generator logic changes

### 2. Introduce a published snapshot domain

Add a publish workflow that materializes a read-optimized snapshot from the active timetable.

This snapshot should support:

- student personal view
- lecturer personal view
- room occupancy lookup
- group lookup
- course lookup
- `now`, `today`, and `week` derived responses

### 3. Ship the access layer as a PWA-capable web experience first

Recommended delivery model:

- React + Vite PWA frontend
- installable to home screen
- service worker cache for published data
- responsive UI with app-like navigation

Why this is the right first step:

- works across Android and iPhone
- still works in normal desktop and laptop browsers
- faster to ship than native apps
- supports offline caching and notifications
- preserves one shared frontend codebase

## Primary User Journeys

### Student Journey

1. Open app
2. Land on Home
3. See `Now`, `Next`, and `Today`
4. Tap a class card for room, lecturer, and countdown details
5. Open Week to swipe through other days
6. Search for lecturer, room, course, or group
7. Download offline copy or export to calendar

### Lecturer Journey

1. Open app
2. Land on Home
3. See current status: teaching now or free
4. See next teaching slot with audience group and room
5. Review today's teaching timeline
6. Check free windows
7. Search room or group occupancy when needed

### Availability Lookup Journey

1. Open Search
2. Search `Dr. Banda`, `LT2`, `MEC 3001`, or a group code
3. Open availability panel
4. See busy/free now and next visible booking

## Mobile Information Architecture

Use five primary tabs:

1. Home
   - now
   - next
   - reminders
   - last updated
2. Today
   - vertical timeline cards
   - filters by session type
3. Week
   - swipeable day view on mobile
   - denser layout on tablet/desktop
4. Search
   - universal lookup
   - lecturer, room, course, group
5. More
   - offline copy
   - PDF export
   - calendar export
   - reminders
   - accessibility and display settings

## Screen Requirements

### Home

Student:

- current class card or free-state card
- next class card with countdown
- today's classes preview
- quick actions:
  - Full Timetable
  - This Week
  - Free Rooms
  - Search Lecturer
  - Download Offline Copy

Lecturer:

- teaching now or free-state card
- next teaching card
- today's teaching list
- quick actions:
  - My Timetable
  - My Free Time
  - Room Lookup
  - Group Lookup

### Today

- chronological vertical list
- clearly labeled course, room, audience, lecturer
- strong empty states when no sessions exist
- status chips:
  - Live now
  - Starts soon
  - Completed

### Week

- mobile-first day pager instead of a tiny full-grid
- desktop can still support broader grid layouts later
- compact cards with start/end times

### Search

Search types:

- lecturer
- room
- course
- group

Search result requirements:

- current status
- next session
- today overview
- room/building details where allowed

### More

- offline sync status
- last published update time
- export actions
- notification preferences
- font size and contrast options

## Role Model

### Student / Common User

Can see:

- own timetable
- public lecturer availability view
- public room availability view
- public course and group published timetable views

Should not see:

- draft timetables
- admin editing tools
- sensitive lecturer/internal metadata

### Lecturer

Can see:

- own teaching timetable
- free/busy now
- next teaching slot
- group and room lookup where policy allows

### Coordinator / HOD

Can see:

- full published lookup capabilities
- broader room and lecturer inspection
- publish status and snapshot health

## Backend Design

### New Domain Boundary

Add a published-read layer rather than stretching admin endpoints.

Suggested backend modules:

- `backend/app/routers/mobile_portal.py`
- `backend/app/services/published_timetable_service.py`
- `backend/app/services/mobile_snapshot_service.py`
- `backend/app/services/availability_service.py`

### Core API Surface

Use compact endpoints optimized for frequent phone access.

#### Personal endpoints

- `GET /api/v1/mobile/me`
- `GET /api/v1/mobile/me/now`
- `GET /api/v1/mobile/me/today`
- `GET /api/v1/mobile/me/week?start=YYYY-MM-DD`
- `GET /api/v1/mobile/me/reminders`
- `POST /api/v1/mobile/me/reminders`

#### Lookup endpoints

- `GET /api/v1/mobile/lookup?q=...`
- `GET /api/v1/mobile/lecturers/{id}`
- `GET /api/v1/mobile/lecturers/{id}/availability`
- `GET /api/v1/mobile/rooms/{id}`
- `GET /api/v1/mobile/rooms/{id}/availability`
- `GET /api/v1/mobile/groups/{id}`
- `GET /api/v1/mobile/courses/{id}`

#### Export endpoints

- `GET /api/v1/mobile/me/export/pdf`
- `GET /api/v1/mobile/me/export/ics`
- `GET /api/v1/mobile/me/offline-bundle`

#### Metadata endpoints

- `GET /api/v1/mobile/bootstrap`
- `GET /api/v1/mobile/sync-status`

### Response Design Principles

- small JSON payloads
- do not send the full timetable grid to render Home
- include normalized date/time fields and precomputed labels
- include `last_updated` and `published_at` on every personal response
- support `ETag` and conditional requests for cheap refreshes

### Suggested Personal Response Shape

```json
{
  "audience": {
    "type": "student",
    "id": 42,
    "display_name": "2020123456",
    "group_name": "MEC-3001"
  },
  "published_at": "2026-04-26T06:00:00Z",
  "last_updated": "2026-04-26T07:10:00Z",
  "timezone": "Africa/Lusaka",
  "now": {
    "status": "live",
    "session_id": "slot-1902",
    "title": "MEC 3001 Thermodynamics",
    "room": "LT2",
    "building": "Engineering Block",
    "starts_at": "2026-04-26T08:00:00+02:00",
    "ends_at": "2026-04-26T10:00:00+02:00"
  },
  "next": {
    "status": "upcoming",
    "starts_in_minutes": 50
  }
}
```

## Snapshot Model

### Publish Pipeline

Recommended flow:

1. Coordinator finalizes timetable
2. System creates a publishable version from the active timetable
3. Snapshot materialization job creates read-optimized records
4. Mobile caches are invalidated by version key
5. Users receive the new published data on next sync

### Snapshot Granularity

Use one canonical published timetable version per academic period, then derive audience-specific responses.

Derived indexes should support:

- by student group
- by lecturer
- by room
- by course
- by day/date

### Storage Recommendation

Start with database-backed published snapshot tables plus Redis cache for hot mobile responses.

Why:

- stable persistence
- easy auditability
- straightforward invalidation
- lower risk than storing the whole product state only in Redis

## Offline and Sync Model

The offline goal is practical resilience, not full offline administration.

### Cache offline

- `Home`
- `Today`
- current week
- user profile basics
- recent search entities already visited
- exported PDF or ICS file if downloaded

### Keep online-only

- live publish events
- institution-wide uncached search
- analytics refresh
- admin operations

### Offline rules

- app should always show last sync timestamp
- stale data should remain readable
- actions that require live validation should clearly warn when offline

## Reminder Strategy

### Phase 1

- in-app reminder preferences
- browser/device notifications where supported
- reminder offsets: 10 min, 30 min, 1 hour

### Phase 2

- ICS export with alarms
- calendar import guidance

### Phase 3

- push notifications for published change alerts
- room-change alerts
- cancellation alerts

## Calendar and Export Strategy

Support three save modes:

1. Offline app cache
2. PDF export
3. ICS calendar export

Calendar export is high-value because users already trust Google Calendar and Apple Calendar for reminders.

## Analytics Principles

Keep analytics practical and personal.

Student metrics:

- today's contact hours
- weekly contact hours
- free gaps today
- first and last class

Lecturer metrics:

- teaching hours this week
- next teaching slot
- busiest day
- longest free window

## Frontend Implementation Direction

### Recommended frontend additions

- dedicated mobile route tree under the existing React app
- a PWA setup with manifest, service worker, install prompt handling
- shared design tokens for mobile cards, chips, status colors, spacing
- API client layer for mobile-specific endpoints

### Suggested frontend modules

- `frontend/src/pages/mobile/MobileHomePage.tsx`
- `frontend/src/pages/mobile/MobileTodayPage.tsx`
- `frontend/src/pages/mobile/MobileWeekPage.tsx`
- `frontend/src/pages/mobile/MobileSearchPage.tsx`
- `frontend/src/pages/mobile/MobileMorePage.tsx`
- `frontend/src/components/mobile/*`
- `frontend/src/hooks/mobile/*`

### UX quality bar

The experience should feel institution-grade:

- large tap targets
- low-clutter screens
- strong typography hierarchy
- clear room/building emphasis
- excellent empty states
- visible loading and stale-data states

## Non-Functional Requirements

- Home screen loads in under 2 seconds on average campus connectivity
- `Now` endpoint remains cheap under high request volume
- offline screens remain readable after cold reconnect failure
- publish operation does not block timetable generation
- mobile APIs are versioned and backward-compatible during rollout

## Release Strategy

### Phase 1

- student mobile Home, Today, Week
- personal published endpoints
- offline cache for current user
- installable PWA shell

### Phase 2

- lecturer mobile experience
- universal search
- room and lecturer availability checker
- PDF and ICS export

### Phase 3

- reminders
- push notifications
- publish change alerts
- richer analytics cards

## Definition of Success

The mobile initiative is successful when:

- users open the timetable on their phone daily without friction
- students can answer `what do I have now/next?` in seconds
- lecturers can check teaching status and next location instantly
- the institution can publish timetable changes without breaking mobile clients
- the experience looks and behaves like a professional campus product
