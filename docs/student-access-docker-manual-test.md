# Student Access Docker Manual Test

This guide is for end-to-end manual testing of the student access layer in the existing Docker environment.

Use it when you want to prototype the full system, not just the frontend in isolation.

## What This Covers

- main management web app for timetable setup and generation
- student access portal at `/student`
- Docker-based demo student bootstrap
- manual checks for login, dashboard, search, offline behavior, and exports

## Product Boundary

Keep the split clear while testing:

- HODs, coordinators, admins, and superadmins use the main web platform
- students use the separate access layer at `/student`

This is mobile-first, but it should also test well in a desktop browser.

## Before You Start

1. Copy `.env.example` to `.env` if needed.
2. Fill the required secrets in `.env`.
3. Make sure Docker Desktop or Docker Engine is running.

## Start the Full Stack

From the repository root:

```bash
docker compose up -d --build
```

Main URLs:

- frontend: `http://localhost:3002`
- student portal: `http://localhost:3002/student`
- backend API: `http://localhost:8000`

## Prepare Real Timetable Data

The student access layer only becomes meaningful when a timetable already exists and has slots linked to student groups.

Use the management web app first to make sure the system has:

- departments
- rooms
- lecturers
- student groups
- courses
- a generated or imported timetable with assigned slots

If there is no timetable with grouped slots yet, the student portal will not have useful data to show.

## Create a Predictable Demo Student

Once timetable data exists, create a reusable student test account:

```bash
docker compose exec backend python scripts/bootstrap_student_access_demo.py
```

Default demo credentials created by the script:

- student number: `STUDENT-DEMO-001`
- password: `StudentDemo123!`

The script automatically attaches the student to the first available timetable-linked group it finds.

If you want custom credentials:

```bash
docker compose exec backend python scripts/bootstrap_student_access_demo.py \
  --student-number 20260001 \
  --password StrongStudent123! \
  --full-name "Manual Test Student" \
  --email manual.student@tablesys.local
```

## Manual Test Flow

### 1. Login

Open:

- `http://localhost:3002/student`

Sign in with the demo student account.

Expected result:

- login succeeds
- student lands in the student portal, not the admin dashboard
- the portal opens on the `Home` tab

### 2. Home / Dashboard

Check that the home screen shows:

- `Now`
- `Next`
- `Today`
- quick actions
- last synced state

Expected result:

- the student sees only their own timetable context
- no giant admin-style timetable grid appears first

### 3. Today

Open the `Today` tab.

Check:

- today sessions load
- session-type chips work
- empty-state messaging is sensible if there are no classes today

### 4. Week

Open the `Week` tab.

Check:

- sessions are grouped by day
- week filter chips work
- room, lecturer, and course details look correct

### 5. Search

Open the `Search` tab.

Check:

- lecturer lookup
- room lookup
- course lookup
- group lookup
- free rooms panel loads

### 6. More

Open the `More` tab.

Check:

- course list
- JSON export
- ICS export
- reminder toggle

### 7. Refresh / Cache Behavior

While online:

- refresh the page
- use the refresh button in the app bar

Expected result:

- portal reloads without losing the student session
- cache-source messaging is visible after refresh

### 8. Offline Reopen

After a successful online load:

1. open browser dev tools
2. simulate offline mode
3. refresh the student portal

Expected result:

- last synced timetable snapshot still loads
- offline banner appears

## Useful Docker Commands

View service state:

```bash
docker compose ps
```

Watch backend logs:

```bash
docker compose logs -f backend
```

Watch frontend logs:

```bash
docker compose logs -f frontend
```

Recreate the demo student:

```bash
docker compose exec backend python scripts/bootstrap_student_access_demo.py
```

Stop the stack:

```bash
docker compose down
```

## When Manual Testing Is Considered Ready

The student access layer is ready for broader manual testing when:

- Docker stack starts cleanly
- a demo student can be created predictably
- `/student` login works
- `Home`, `Today`, `Week`, `Search`, and `More` all load
- offline reopen works after an initial sync
- exports work

## Follow-On Work After This

After student manual testing is stable, the next steps remain:

- continue slimming `StudentPortal.tsx`
- move mobile reads toward published snapshot backing
- add the lecturer access layer as a sibling surface
