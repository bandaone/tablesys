# Universal Scheduling Migration Guide

## Schema Additions
- `universities.scheduling_policy`
- `universities.onboarding_completed_at`
- `activity_types`
- `courses.activity_requirements`
- `rooms.tags`
- `student_groups.custom_subtype`

## Tenant-Scoped Uniqueness
The following uniqueness rules are now tenant-safe:
- departments: `(university_id, name)` and `(university_id, code)`
- rooms: `(university_id, name)`
- student groups: `(university_id, name)`
- courses: `(department_id, code)`

## Backward Compatibility
Existing tenants continue to work because:
- legacy course hour fields are still read
- legacy room type preferences are still honored when no tag requirements exist
- legacy group enums remain intact
- legacy session labels still flow into `TimetableSlot.session_type`

## Rollout Sequence
1. Run Alembic migrations with `alembic upgrade head`.
2. New provisioned tenants receive a neutral `custom` scheduling policy unless provisioning already knows the target institution template.
3. Coordinators open `Institution Setup` and switch to the correct template or custom configuration.
4. New courses may start using `activity_requirements`.
5. Legacy courses can be migrated gradually without breaking generation.

## Existing Tenants (Pre-Migration)
- Existing tenants may have `NULL` `scheduling_policy` and no `ActivityType` rows immediately after the schema migration.
- That is safe: generation still falls back to legacy course hours and legacy room matching.
- The recommended next step is to open Institution Setup and choose either:
  - a template such as Nursing, Medical, or Trades
  - or `custom` to build the vocabulary from scratch
- Admin backfill may safely set a neutral `custom` scheduling policy for old tenants without forcing engineering assumptions.

## Recommended Migration for Existing Tenants
1. Leave legacy courses untouched initially.
2. Configure room tags for institution spaces.
3. Add custom activity types only where the old `lecture/tutorial/practical` model is insufficient.
4. Migrate courses department-by-department into `activity_requirements`.
5. Add `custom_subtype` to groups only when non-legacy subgroup behavior is required.

## Fallback Behavior
- If an activity has no tag requirements, the system falls back to legacy room matching.
- If a course has no `activity_requirements`, the generator derives activities from legacy hours.
- If a subgroup-required activity finds no matching subgroup type, the generator falls back to the base audience.
- If a tenant has no saved scheduling policy yet, the runtime fallback is the neutral `custom` template rather than an engineering preset.
