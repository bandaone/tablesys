# Lecturer Access Layer - Design Document

**Purpose:** Enable lecturers to securely view and manage their own timetables, courses, and related information without needing admin intervention.

**Design Principle:** Keep it simple, secure, and separate from SIS—focus on timetable access only.

**Implementation Status:** The workspace now includes the lecturer login flow, lecturer portal shell, timetable endpoint, courses endpoint, and dashboard metrics endpoint.

**Current Lecturer Metrics:**
- now teaching
- next session countdown
- daily teaching load
- weekly load vs max hours
- course-by-course workload breakdown

**Verification Path:** Continue using Docker for end-to-end verification in this repository unless a local shell is specifically needed.

---

## 1. Lecturer Identification & Authentication

### Identity Source
- **Existing DB:** `Lecturer` table (staff_number, full_name, email, department_id)
- **Assumption:** Lecturers are pre-imported via SIS webhook (`POST /api/v1/sis/lecturers`)
- **No SIS password integration:** Like students, lecturers authenticate with staff_number only (no credential validation against external systems)

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Lecturer accesses /student portal (or dedicated /lecturer)   │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Clicks "I'm a Lecturer" or navigates to /lecturer/login     │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Enters staff_number (e.g., "ENG-2024-001")                  │
│ System finds matching Lecturer record in DB                 │
│ No password required (trust SIS pre-import)                 │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Backend: POST /api/v1/lecturer/login                        │
│ Request: { "staff_number": "ENG-2024-001" }                │
│ Response: { "access_token": "<JWT>", "token_type": "bearer" }
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Frontend stores token in localStorage (like student flow)   │
│ On each request, adds: Authorization: Bearer <token>        │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Lecturer portal loads and fetches:                          │
│ - Their assigned courses                                    │
│ - Their timetable (all sessions for those courses)         │
│ - Groups/students in each course                           │
│ - Room assignments                                          │
└─────────────────────────────────────────────────────────────┘
```

### JWT Token Structure (Lecturer)

```json
{
  "sub": "ENG-2024-001",              // staff_number (unique identifier)
  "type": "lecturer",                  // token type marker
  "lecturer_id": 42,                   // database record ID
  "full_name": "Dr. Jane Smith",       // display name
  "department_id": 5,                  // department scoping
  "email": "jane.smith@university.edu",
  "exp": 1735689600                    // 7 days expiry (like student)
}
```

---

## 2. Authorization & Data Scoping

### Principle: Department-Scoped Access

**Who can view what:**
- **Lecturer can see:**
  - Own timetable (all TimetableSlots where lecturer_id = their id)
  - Own courses (all Courses linked via LecturerAssignment)
  - Groups enrolled in those courses (via CourseGroupLink)
  - Students in those groups (Student records)
  - Room assignments (from TimetableSlot.room_id)
  - Unavailability records (own LecturerUnavailability entries)

- **Lecturer CANNOT see:**
  - Other lecturers' timetables or assignments
  - Courses not assigned to them
  - Students outside their groups
  - Admin/coordinator data (users, permissions, audit logs)

### Authorization Checks

```python
# Example: Lecturer views their timetable
GET /api/v1/lecturer/timetable

# Backend logic:
current_lecturer = get_current_lecturer()  # From JWT
sessions = db.query(TimetableSlot).filter(
    TimetableSlot.lecturer_id == current_lecturer.id
).all()

# No need for department checks—lecturers are already scoped by their assignments
```

---

## 3. Data Model: What Lecturer Information Exists

### Existing Data Lecturer Can Access

**Direct from Lecturer table:**
```
- staff_number (unique ID)
- full_name
- email
- department_id (scopes them to a department)
- max_hours_per_week (optional constraint)
- teaching_preferences (JSON—e.g., preferred time slots, room types)
```

**Through LecturerAssignment:**
```
- Assigned courses (code, name, credits)
- Session types (lecture, tutorial, lab)
- Room preferences
- Expertise level (e.g., subject matter expert)
```

**Through TimetableSlot:**
```
- Scheduled sessions (date, time, room, group, course)
- Conflict detection (if slot time overlaps with another)
```

**Through LecturerUnavailability:**
```
- Blocked time slots (day_of_week, start_time, end_time)
- Reason (optional—e.g., "Department meeting", "Leave")
```

---

## 4. API Endpoints for Lecturer Access

### Authentication

```
POST /api/v1/lecturer/login
Request:  { "staff_number": "ENG-2024-001" }
Response: { "access_token": "<JWT>", "token_type": "bearer" }

GET /api/v1/lecturer/me
Headers:  Authorization: Bearer <token>
Response: {
  "lecturer_id": 42,
  "staff_number": "ENG-2024-001",
  "full_name": "Dr. Jane Smith",
  "email": "jane.smith@university.edu",
  "department_id": 5,
  "department_name": "Engineering"
}
```

### Timetable & Sessions

```
GET /api/v1/lecturer/timetable
Response: {
  "profile": { "lecturer_id": 42, "staff_number": "ENG-2024-001", ... },
  "timetable": { "id": 1, "name": "Academic Year 2025/26", "year": 2026 },
  "sessions": [
    {
      "id": 101,
      "course_code": "ENG101",
      "course_name": "Introduction to Engineering",
      "group_name": "Engineering Y1 A",
      "session_type": "Lecture",
      "day_of_week": "Monday",
      "start_time": "09:00",
      "end_time": "10:30",
      "room_number": "Hall A",
      "building": "Science Block",
      "capacity": 200,
      "student_count": 150
    },
    ...
  ]
}

GET /api/v1/lecturer/timetable?filter=week    // Current week only
GET /api/v1/lecturer/timetable?filter=day     // Today only
```

### Courses & Assignments

```
GET /api/v1/lecturer/courses
Response: [
  {
    "id": 1,
    "code": "ENG101",
    "name": "Introduction to Engineering",
    "credits": 3,
    "level": 1,
    "department": "Engineering",
    "groups": [
      { "id": 10, "name": "Engineering Y1 A", "size": 150 },
      { "id": 11, "name": "Engineering Y1 B", "size": 140 }
    ],
    "assignment": {
      "session_types": ["Lecture", "Tutorial"],
      "room_preference": "Hall with projector",
      "expertise_level": "Subject Matter Expert"
    }
  },
  ...
]

GET /api/v1/lecturer/courses/{course_id}
Response: { ...full course detail + enrollment }
```

### Groups & Students

```
GET /api/v1/lecturer/courses/{course_id}/groups
Response: [
  {
    "id": 10,
    "name": "Engineering Y1 A",
    "level": 1,
    "size": 150,
    "students_count": 145,  // Actual enrollment
    "type": "STREAM"
  }
]

GET /api/v1/lecturer/courses/{course_id}/groups/{group_id}/students
Response: [
  {
    "id": 1001,
    "student_number": "STU-2024-001",
    "full_name": "John Doe",
    "email": "john.doe@university.edu",
    "program": "B.Eng",
    "year_level": 1
  },
  ...
]
```

### Unavailability & Constraints

```
GET /api/v1/lecturer/unavailability
Response: [
  {
    "id": 1,
    "day_of_week": "Wednesday",
    "start_time": "14:00",
    "end_time": "16:00",
    "reason": "Department Meeting"
  }
]

POST /api/v1/lecturer/unavailability
Request: {
  "day_of_week": "Friday",
  "start_time": "15:00",
  "end_time": "17:00",
  "reason": "Research Time"
}
Response: { "id": 2, ... }

DELETE /api/v1/lecturer/unavailability/{id}
Response: { "success": true }
```

### Dashboard / Summary

```
GET /api/v1/lecturer/dashboard
Response: {
  "profile": { ... },
  "summary": {
    "total_courses": 3,
    "total_sessions_this_week": 12,
    "total_hours_this_week": 18,
    "upcoming_session": {
      "course": "ENG101",
      "group": "Engineering Y1 A",
      "room": "Hall A",
      "day": "Monday",
      "start_time": "09:00",
      "time_until_start": "2 hours"
    }
  },
  "this_week_sessions": [ ... ]
}
```

### Lecturer Metrics Included Today

The lecturer dashboard currently exposes the following access-layer metrics:

- `now_teaching` / current session card - shows the session currently in progress, if any
- `next_session` - the next teaching session plus countdown metadata
- `daily_teaching_hours` - total scheduled teaching hours for the current day
- `daily_session_count` - number of sessions scheduled today
- `weekly_load_hours` - total teaching hours scheduled for the current week
- `max_hours_per_week` - lecturer workload cap from the lecturer profile
- `weekly_load_percent` - weekly load as a percentage of the workload cap
- `course_workload` - course-by-course session count and hours breakdown

---

## 5. Frontend: Lecturer Portal Structure

### Pages

1. **Login Page** (`/lecturer/login`)
   - Input: staff_number
   - No password
   - "I'm a Lecturer" button on main login page or separate route

2. **Timetable View** (`/lecturer/timetable`)
   - Week view (default)
   - Day/week/month filters
   - Search by course or group
   - Color-coded by course

3. **Courses Page** (`/lecturer/courses`)
   - List of assigned courses
   - Enrollment numbers by group
   - Filter by department/level

4. **Group Details** (`/lecturer/courses/:courseId/groups/:groupId`)
   - Student roster
   - Enrollment status
   - Session schedule for that group

5. **Unavailability Management** (`/lecturer/unavailability`)
   - View blocked times
   - Add/edit/delete unavailability
   - Optional: bulk import (e.g., "Block all Mondays 2-4pm for the semester")

6. **Dashboard** (`/lecturer`)
   - Summary cards (courses, sessions this week, hours)
   - Upcoming session notification
   - Quick links to timetable, courses, messages

---

## 6. Security & Best Practices

### Authentication Security

- ✅ **JWT tokens** (same HS256 as staff): Time-limited (7 days), signed
- ✅ **Staff number validation:** Check against Lecturer table before issuing token
- ✅ **Token refresh:** (Optional) Support refresh tokens for extended sessions
- ✅ **Logout:** Clear localStorage on client side (stateless backend)

### Data Authorization

- ✅ **Lecturer isolation:** Lecturer can ONLY see their own assignments (via lecturer_id check)
- ✅ **Department scoping:** (Optional) Lecturers can't access courses outside their department
- ✅ **Read-only by default:** Lecturers view timetables but can't modify them (Coordinator owns generation)
- ✅ **Unavailability ownership:** Lecturers can only CRUD their own unavailability records

### SIS Assumptions

- ✅ **Pre-import trust:** Staff numbers come from SIS; we trust they're correct
- ✅ **No password sync:** We don't validate against external SIS credentials (keeps system simple)
- ✅ **Upsert on refresh:** If SIS re-imports lecturer data, update existing records (don't create duplicates)

### Current Workspace Notes

- `backend/app/routers/lecturer_portal.py` handles lecturer login, `me`, timetable, courses, and dashboard endpoints.
- `frontend/src/pages/LecturerLogin.tsx` provides the staff-number login screen.
- `frontend/src/pages/LecturerPortal.tsx` provides the timetable-first dashboard with metrics, courses, and sessions.
- `backend/app/main.py` already registers the lecturer router.
- The lecturer flow is intentionally read-mostly and timetable-focused, so it stays simple for institutions that already have a SIS.

---

## 7. Phased Implementation Plan

### Phase 1: Core Lecturer Authentication & Timetable View
- [x] `POST /api/v1/lecturer/login` endpoint
- [x] `GET /api/v1/lecturer/me` endpoint
- [x] `GET /api/v1/lecturer/timetable` endpoint
- [x] JWT dependency: `get_current_lecturer()`
- [x] Frontend: `/lecturer/login` form + `/lecturer/timetable` page

### Phase 2: Courses & Groups View
- [x] `GET /api/v1/lecturer/courses` endpoint
- [ ] `GET /api/v1/lecturer/courses/{id}/groups` endpoint
- [ ] `GET /api/v1/lecturer/courses/{id}/groups/{id}/students` endpoint
- [ ] Frontend: `/lecturer/courses` page + course details modal

### Phase 3: Unavailability Management (Optional)
- [ ] `GET/POST/DELETE /api/v1/lecturer/unavailability` endpoints
- [ ] Frontend: `/lecturer/unavailability` page

### Phase 4: Dashboard & Notifications (Optional)
- [x] `GET /api/v1/lecturer/dashboard` endpoint
- [x] Frontend: `/lecturer` dashboard page
- [ ] (Future) Email/browser notifications for upcoming sessions

---

## 8. Example: Flow from Login to Timetable View

**Step 1: Lecturer navigates to system**
```
Browser: GET /lecturer
Redirect to: /lecturer/login (if not authenticated)
```

**Step 2: Lecturer enters staff number**
```
Form input: "ENG-2024-001"
Click: "Sign In"
```

**Step 3: Backend authenticates**
```
POST /api/v1/lecturer/login
Body: { "staff_number": "ENG-2024-001" }

Backend:
  - Query: Lecturer.query.filter(staff_number == "ENG-2024-001").first()
  - If exists: Issue JWT with lecturer_id, staff_number, full_name, etc.
  - If not exists: Return 404 with "Staff number not recognized. Contact coordinator."

Response: { "access_token": "eyJ...", "token_type": "bearer" }
```

**Step 4: Frontend stores token**
```javascript
localStorage.setItem('lecturer_token', accessToken);
// Or: localStorage.setItem('auth_token', accessToken); // reuse student flow
// Redirect to: /lecturer/timetable
```

**Step 5: Frontend fetches timetable**
```
GET /api/v1/lecturer/timetable
Headers: { "Authorization": "Bearer eyJ..." }

Backend:
  - Decode JWT, extract lecturer_id = 42
  - Query TimetableSlot.filter(lecturer_id == 42)
  - Return slots with course, group, room, times

Response: { 
  "profile": { "staff_number": "ENG-2024-001", ... },
  "sessions": [ { "course_code": "ENG101", "day": "Monday", ... }, ... ]
}
```

**Step 6: Frontend renders timetable**
```
Display week grid with lecturer's sessions color-coded by course
```

---

## 9. Differences from Student Access

| Aspect | Student | Lecturer |
|--------|---------|----------|
| **Identifier** | student_number | staff_number |
| **JWT token** | 7 days | 7 days |
| **Password** | None (SIS pre-import) | None (SIS pre-import) |
| **What they see** | Their personal timetable (1 group) | All their course sessions (N groups, multiple days) |
| **Modification rights** | Read-only | Read-only (+ optional: own unavailability) |
| **Department scoping** | No (only see own group) | Yes (only see own courses) |
| **API prefix** | `/api/v1/student` | `/api/v1/lecturer` |
| **Frontend path** | `/student` | `/lecturer` |

---

## 10. Keep-It-Simple Checklist

✅ **Single identifier:** staff_number (no need for multiple login methods)
✅ **No password:** Trust pre-import from SIS
✅ **No registration:** Lecturers are pre-created by coordinators via SIS import
✅ **Minimal endpoints:** Core 4 endpoints (login, me, timetable, courses) + optional 2 (groups, unavailability)
✅ **No complex workflows:** No approval chains, no course bidding, no shift swapping
✅ **Department-scoped by default:** Lecturers can't see other departments
✅ **Read-mostly access:** Lecturers view data; coordinators control timetable generation
✅ **Reuse existing patterns:** JWT, role-based deps, query scoping from student/coordinator flows
