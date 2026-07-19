# Institution Setup Guide

## What This Setup Controls
Institution Setup configures the scheduling vocabulary for one tenant:
- teaching days and timetable window
- slot duration
- default weekly frequencies
- activity types
- room capability tags

## Choosing a Template
Templates are starting points only. Current options include:
- Engineering
- Medical / Health Sciences
- Nursing / Allied Health
- Education / Teaching
- Business / Commerce
- Trades / Technical
- Start from Scratch

Switching templates updates the seeded activity types and room tag catalog. Coordinators can edit them before saving.

## Calendar Configuration
The calendar settings are the most important setup inputs because they directly shape generation:
- `days_of_week`: which teaching days are schedulable
- `start_time` and `end_time`: the daily timetable window
- `slot_duration_minutes`: the size of one schedulable period
- `lunch_start` and `lunch_end`: the protected break window

If these values are wrong, the generator will build the wrong slot grid even if activities and rooms are configured correctly.

## Defining Activity Types
For each activity type, configure:
- internal key
- display name
- default duration in slot periods
- default weekly frequency
- whether subgroups are required
- required room tags

Examples:
- `clinical_skills`
- `ward_placement`
- `micro_teaching`
- `workshop`

Activity types omitted from a later save are soft-deactivated, not deleted. If the same key is reintroduced later, the system reactivates the existing row.

## Assigning Room Tags
Room tags describe suitability, not academic meaning. Examples:
- `lecture_hall`
- `clinical_skills_lab`
- `ward`
- `projector`
- `workshop`

Activities match rooms by tags first. A room must include all tags required by the activity.

## Course Activity Requirements
Courses can now define scheduling requirements as a list of activities instead of only legacy hour fields.

Example shape:
```json
[
  {
    "activity_type_key": "theory",
    "hours_per_session": 2,
    "frequency_per_week": 3
  },
  {
    "activity_type_key": "clinical_skills",
    "hours_per_session": 2,
    "frequency_per_week": 1
  }
]
```

## Subgroup-Required Activities
If an activity requires subgroups:
- use `StudentGroup.custom_subtype` for the institution-specific subtype
- legacy `group_type` still works for lab/tutorial/drawing flows

If no matching subgroup exists, generation falls back to the base teaching audience so the course remains schedulable.

## Operational Note
Institution Setup is where a generic template becomes institution-specific configuration. Provisioning only creates the safe starting state; coordinators are expected to confirm or replace the seeded vocabulary here before relying on advanced activity-driven scheduling.
