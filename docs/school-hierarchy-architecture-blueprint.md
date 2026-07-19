# TABLESYS School Hierarchy Architecture Blueprint

## Summary
TABLESYS now supports a hierarchical institutional model:

- `University -> School -> Department`
- `TENANT_ADMIN` owns university-wide setup and can act across schools
- `SCHOOL_COORDINATOR` owns school-scoped academic operations
- legacy `COORDINATOR` remains a compatibility alias during rollout

## Core Rules
- `school_id = NULL` preserves legacy flat behavior for existing tenants.
- `Room.school_id = NULL` means the room is shared university-wide.
- `Timetable.school_id = NULL` means legacy whole-university generation.
- `Timetable.school_id = <id>` means generation is restricted to that school.

## Access Model
- `SUPERADMIN`: platform-wide
- `TENANT_ADMIN`: all schools in one university
- `SCHOOL_COORDINATOR` / legacy `COORDINATOR`: one school plus shared rooms
- `HOD`: one department within one school

## Generation Scope
When a timetable has `school_id`:

1. Courses are restricted to departments in that school.
2. Student groups are restricted to departments in that school.
3. Lecturer assignments are resolved only for those courses.
4. Room pool includes:
   - rooms with matching `school_id`
   - shared rooms where `school_id IS NULL`

If `school_id` is null, the generator keeps the existing flat tenant-wide behavior.

## Provisioning
- New self-serve tenant signup provisions a `TENANT_ADMIN`
- Single-school templates may auto-seed one default school
- Institution setup remains university-wide and is tenant-admin-only
- School creation and school coordinator assignment happen after institution setup
