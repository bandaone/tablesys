# School Hierarchy Migration Guide

## Apply the Migration
Run:

```bash
alembic upgrade head
```

## What Changes
- Adds `schools` table
- Adds nullable `school_id` to:
  - `departments`
  - `rooms`
  - `timetables`
  - `users`
- Expands user roles with:
  - `tenant_admin`
  - `school_coordinator`
  - `lecturer`
  - `student`

## Backward Compatibility
- Existing tenants continue to work with `school_id = NULL`
- Existing `COORDINATOR` users remain valid and are treated as school-capable operators
- Existing flat timetables still generate university-wide

## New Tenant Behavior
- New provisioning creates `TENANT_ADMIN`
- Some templates auto-seed a single school so small colleges can start quickly

## Recommended Migration Path for Existing Tenants
1. Upgrade schema
2. Keep operating in flat mode initially
3. Create one or more schools
4. Assign departments and rooms to schools
5. Assign users to schools
6. Start creating new school-scoped timetables

## Shared Rooms
- `Room.school_id = NULL` means the room is shared across the university
- school-scoped timetable generation may use both school-owned and shared rooms
