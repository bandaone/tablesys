# School Hierarchy Onboarding Guide

## Tenant Admin Flow
After login, the tenant admin should:

1. Complete Institution Setup
2. Open the Schools page
3. Create one or more schools
4. Add shared university rooms if needed
5. Create `SCHOOL_COORDINATOR` accounts

## School Coordinator Flow
Inside a school, the school coordinator should:

1. Create departments
2. Create HOD and lab coordinator accounts
3. Upload school rooms
4. Upload lecturers
5. Upload courses
6. Upload student groups
7. Link groups to courses and assign lecturers
8. Create and generate school-scoped timetables

## Shared vs School Rooms
- Shared room: `school_id = NULL`
- School room: `school_id = <school>`

## Legacy Compatibility
- Older tenants can continue operating without schools
- Legacy coordinators continue working during rollout
- New school-scoped timetables can be introduced gradually
