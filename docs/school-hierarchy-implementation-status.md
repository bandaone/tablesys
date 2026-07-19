# School Hierarchy Implementation Status

## Completed Subsystems
- **School-Scoped Context Utilities (`school_scope.py`)**: Complete filtering wrappers for querying datasets based on `TENANT_ADMIN` vs `SCHOOL_COORDINATOR` rules.
- **Backend Migrations**: Replaced the flat-era `require_admin` dependency injections with strictly scoped operators (`is_tenant_admin`, `is_school_operator`) across core operational routers (`courses.py`, `groups.py`, `dashboard.py`, `reports.py`, `exam_timetables.py`).
- **SuperAdmin Provisioning Path Alignment (`superadmin.py`)**: Ensures self-serve onboarding accurately delegates the `TENANT_ADMIN` root role rather than defaulting to unstructured legacy coordinates.
- **Docker-Native Test Hierarchy (`docker-compose.test.yml`)**: Formalized an isolated ephemeral postgres setup to validate safe cross-tenant logic updates safely.

## Remaining Gaps / Action Items
- **5 Test Failures Remaining**: The integration test suite ran successfully in Docker but highlights localized feature failures that need specific assertion updates post-migration:
  - `test_scheduler.py::test_lecturer_unavailability_blocks_overlapping_windows`
  - `test_scheduler.py::test_find_general_department_accepts_gen_code`
  - `test_institution_setup.py::test_course_update_accepts_valid_activity_requirements`
  - `test_exam_timetables.py::test_exam_generation_supports_multi_room_allocations`
  - `test_exam_timetables.py::test_exam_publish_locks_period`
- Needs to be reviewed to determine if the baseline tests need their setup payloads adjusted for the new `school_id` requirements or if there is genuine model drift in scheduling calculations.

## Test Evidence
The integration system test is verifiable against `test_output.txt`.

### Environment
- Validated via isolated Postgres test container using `tablesys_test` database boundary.
- Executed DB schema setup and teardown cleanly. 

### Executed Strategy
```bash
docker compose -f docker-compose.test.yml up --build
```
Result summary (from ephemeral DB testing environment):
```
5 failed, 55 passed, 3 skipped, 39 warnings in 38.51s
```
