# Metering and Usage API Blueprint

Owner: Copilot
Date: 2026-05-05
Status: Approved

## Purpose

Define the API surface and data contract for usage metering, monthly summaries, and plan enforcement for TABLESYS SaaS. This is a blueprint for implementation and review.

## Assumptions (Confirmed)

1. Billing is per-tenant (university) with plan tiers and quotas.
2. Billable metrics are limited to four core buckets:
  - Active students (seats)
  - Timetable generations per month
  - Department and course count (complexity proxy)
  - Storage consumed (uploads + audit logs)
3. Monthly billing cycle per tenant (calendar month).
4. API call volume metering is deferred until a public API exists.
5. Enforcement uses warning thresholds and blocking rules (see below).

## Definitions

- Tenant: A university account identified by university_id.
- Usage event: A normalized record describing a metered action.
- Monthly summary: Aggregated usage totals for a tenant per month.
- Plan tier: free | pro | enterprise (names can be changed).

## Data Model (Logical)

1. UsageEvent
   - id
   - tenant_id
  - metric_key (seats_active, timetable_generations, department_count, course_count, storage_bytes)
   - quantity (integer)
   - occurred_at (UTC timestamp)
   - source (api, job, admin)
   - metadata (JSON)

2. UsageMonthlySummary
   - id
   - tenant_id
   - period_start (YYYY-MM-01 00:00:00 UTC)
   - period_end (YYYY-MM-last 23:59:59 UTC)
   - metric_key
   - total_quantity
   - updated_at

3. PlanQuota
   - id
   - plan_tier
   - metric_key
   - limit_quantity
   - enforcement (warn | block | throttle)

## Collection Points (Where Events Are Emitted)

- Student activation/deactivation -> seats_active delta
- Timetable generation start/end -> timetable_generations +1
- Department/course create/delete -> department_count/course_count recalculated or delta
- Public API requests -> deferred until public API exists
- File uploads and audit log writes -> storage_bytes +delta

## API Endpoints (Blueprint)

### 1) Ingest Usage Event (Internal)

POST /api/v1/usage/events

Request:
{
  "tenant_id": 123,
  "metric_key": "timetable_generations",
  "quantity": 1,
  "occurred_at": "2026-05-05T12:30:00Z",
  "source": "job",
  "metadata": {
    "timetable_id": 44,
    "duration_ms": 9123
  }
}

Response:
{
  "status": "accepted",
  "event_id": 9912
}

Notes:
- This endpoint should be protected for internal use only.
- Optionally bypass HTTP and write directly via service layer for performance.

### 2) Get Monthly Usage Summary (Tenant)

GET /api/v1/usage/summary?period=2026-05

Response:
{
  "tenant_id": 123,
  "period": "2026-05",
  "metrics": [
    {"metric_key": "seats_active", "total": 840, "limit": 1000, "status": "ok"},
    {"metric_key": "timetable_generations", "total": 12, "limit": 20, "status": "warn"},
    {"metric_key": "department_count", "total": 9, "limit": 20, "status": "ok"},
    {"metric_key": "course_count", "total": 210, "limit": 300, "status": "ok"},
    {"metric_key": "api_calls", "total": 12000, "limit": 20000, "status": "ok"},
    {"metric_key": "storage_bytes", "total": 2147483648, "limit": 5368709120, "status": "ok"}
  ]
}

### 3) Admin Usage Summary (Superadmin)

GET /api/v1/superadmin/usage/summary?tenant_id=123&period=2026-05

Response:
{
  "tenant_id": 123,
  "tenant_name": "University X",
  "period": "2026-05",
  "metrics": [ ... ]
}

### 4) Plan Quota Definitions (Superadmin)

GET /api/v1/superadmin/plans

Response:
{
  "plans": [
    {
      "plan_tier": "free",
      "quotas": [
        {"metric_key": "seats_active", "limit": 200, "enforcement": "warn"},
        {"metric_key": "timetable_generations", "limit": 5, "enforcement": "warn"}
      ]
    }
  ]
}

### 5) Update Plan Quotas (Superadmin)

PUT /api/v1/superadmin/plans/{plan_tier}

Request:
{
  "quotas": [
    {"metric_key": "seats_active", "limit": 500, "enforcement": "warn"},
    {"metric_key": "storage_bytes", "limit": 1073741824, "enforcement": "block"}
  ]
}

Response:
{
  "status": "success"
}

### 6) Usage Export (Tenant)

GET /api/v1/usage/export?period=2026-05&format=csv

Response:
- CSV file download

## Enforcement Hooks (Blueprint)

- 80%: Warning (yellow indicator + one email/month)
- 100%: Hard warning (red indicator + one email/month)
- >100%: Block for generations; warn-only for seats and storage

## Reporting (Monthly SLA/Usage)

- Monthly usage summary endpoint can be used by SLA reporting service.
- If SLA requires availability metrics, those remain in observability workstream.

## Plan Quotas (Confirmed)

Metric | Starter | Professional | Enterprise
--- | --- | --- | ---
Seats | 1,000 | 5,000 | 50,000
Generations (per month) | 10 | 30 | 100
Departments | 15 | 50 | 200
Courses | 150 | 500 | 2,000
Storage | 5 GB | 25 GB | 100 GB

## Implementation Order (Approved)

1. UsageEvent table + ingestion
2. Monthly summary aggregation job
3. PlanQuota seed data
4. Quota check middleware
5. Tenant usage summary endpoint
6. Superadmin endpoints (later)
