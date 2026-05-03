# Lecturer Access Implementation Checklist

## Purpose

This checklist is for anyone continuing work on the lecturer access layer.

It answers three questions quickly:

1. What already exists?
2. What should not be redone?
3. What should be built next?

Use this document before changing the lecturer portal.

## Product Boundary

This work is for the lecturer access layer only.

It is considered a "sibling" to the student access layer. It shares many of the same design patterns (e.g., simplified authentication, mobile-friendly layouts, read-mostly access) but serves lecturers.

- It is strictly separated from the admin/coordinator management dashboard.
- It uses the `staff_number` for login (no passwords, trusting the SIS import).
- Lecturers see all their assigned courses, timetables, and group rosters.
- Like the student portal, it must be responsive (phone, tablet, desktop).

## Primary Reference Docs

Read these first:

- [LECTURER_ACCESS_LAYER_DESIGN.md](../LECTURER_ACCESS_LAYER_DESIGN.md)
- [access-layer-architecture.md](access-layer-architecture.md)
- [student-access-implementation-checklist.md](student-access-implementation-checklist.md) (for parallel reference)

## Current Starting Point

This module is currently **unstarted**. It is a greenfield implementation following established patterns from the student access layer.

### What Is Already Done

- The `Lecturer` and `TimetableSlot` models exist in the database schema.
- The conceptual API and Frontend plans are fully defined in `LECTURER_ACCESS_LAYER_DESIGN.md`.
- Shared UI components from the student portal might be extracted, but the specific lecturer routes and clients do not exist yet.

## What Must Not Be Redone / Avoided

1. **Do not mix student and lecturer APIs:** They must have separate routers (e.g., `/api/v1/lecturer/...`).
2. **Do not build a password flow:** The MVP relies strictly on `staff_number` presence in the database.
3. **Do not use admin credentials:** The lecturer token is a standard JWT with a specific `type: "lecturer"` payload.
4. **Do not grant global access:** Queries must always be scoped by the `current_lecturer.id`.

## Recommended Next Build Order

Work in this order unless there is a strong reason not to.

### Phase 1: Core Authentication & Security Foundation
- [ ] Implement `get_current_lecturer` FastAPI dependency.
- [ ] Create `backend/app/routers/lecturer_portal.py`.
- [ ] Implement `POST /api/v1/lecturer/login` (generates JWT based on `staff_number`).
- [ ] Implement `GET /api/v1/lecturer/me`.
- [ ] Register router in `backend/app/main.py` under `api/v1`.

### Phase 2: Core Timetable & Frontend Scaffold
- [ ] Create `frontend/src/lecturerPortalApi.ts` (clone/adapt from `studentPortalApi.ts`).
- [ ] Set up frontend routing for `/lecturer/login` and `/lecturer/timetable`.
- [ ] Implement `GET /api/v1/lecturer/timetable` mapped securely to the `lecturer_id`.
- [ ] Build the Lecturer Timetable View (reusing the unified PortalLayout and Timeline components where possible).
- [ ] Update `frontend/src/pwa.ts` and `frontend/public/sw.js` if separate caching rules are needed, or ensure they share the same base cache strategy.

### Phase 3: Courses & Groups View
- [ ] Implement `GET /api/v1/lecturer/courses` and group endpoints to show assigned classes.
- [ ] Create `/lecturer/courses` frontend view.
- [ ] Display enrolled students per course/group via `/api/v1/lecturer/courses/{id}/groups`.

### Phase 4: Unavailability Management & Dashboard
- [ ] Implement `GET/POST/DELETE /api/v1/lecturer/unavailability`.
- [ ] Build Unavailability UI for lecturers to block out times.
- [ ] Build Dashboard summary cards.

### Phase 5: Test Venue Lookup & Booking
- [ ] Add a lecturer-facing venue search that filters by date, time, and room capacity.
- [ ] Default a scheduled test to the course's normal lecture venue when the lecturer does not choose another room.
- [ ] Persist test scheduling as a room booking so the selected venue becomes unavailable to later overlapping bookings.
- [ ] Reuse the existing room conflict rules so test bookings do not interfere with scheduled lectures, and lecture clashes still fail validation.
- [ ] Keep the lecturer and coordinator access layers on the same availability logic so both surfaces show the same room state.

## Exact "Start Here" Task List

If you are picking this up fresh, start here:

1. Read `LECTURER_ACCESS_LAYER_DESIGN.md`.
2. Look at how backend auth works for students (`backend/app/routers/student_portal.py` or `/api/v1/mobile_portal`).
3. Create `backend/app/routers/lecturer_portal.py` as your first piece of code.
4. Add the `POST /api/v1/lecturer/login` and `GET /api/v1/lecturer/me` endpoints.
5. Create a manual testing script or use `curl`/Thunder Client to verify the token is issued correctly before starting the frontend work.

## "Done vs Next" Quick Summary

### Done
- Architecture and Design finalized
- Reference Docs created

### Next
- Backend Auth (`get_current_lecturer` and `/login`)
- Frontend Layout and Client API
- Timetable Endpoint

## Definition of Success for the Lecturer Layer

The lecturer access layer is in a good state when:
- A lecturer can login instantly using only their SIS `staff_number`.
- They can view their timetable across all groups they teach, without seeing other lecturers' entries.
- The UI feels perfectly snappy, native, and responsive across their phone and desktop, directly matching the quality of the student layer.
- The code is siloed properly to avoid breaking admin functionalities.
- Lecturers can schedule a test in a venue, leave venue blank to inherit the normal lecture room, or search alternative rooms by time/date/capacity before booking.
- A booked test blocks later overlapping room bookings, but never displaces an existing scheduled lecture.
