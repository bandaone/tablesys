# Tenant Onboarding Integration Contract

Owner: Codex
Date: 2026-05-05
Status: Ready for implementation handoff

## Purpose

Translate the current registration code and the new SaaS workstreams into one implementation-ready contract so Copilot and Antigravity can work without crossing responsibilities or editing the same files.

## Why This Slice Exists

The original Codex task card pointed at implementation files that are now partially covered by Antigravity's observability work. Codex is taking the cross-cutting integration role instead: define the shared lifecycle, expose the current gaps, and specify handoff boundaries.

## Current Code Reality

### Public registration already exists

`backend/app/routers/public.py` currently implements:
- `POST /api/v1/public/register`
- `POST /api/v1/public/verify`
- `POST /api/v1/public/resend`

Current behavior:
- `register` writes a `PendingRegistration` row and sends a verification email asynchronously.
- `verify` provisions the `University`, provisions the first coordinator user, marks the pending record as verified, creates superadmin notifications, then returns an auth token.

### Provisioning is still inline

The actual tenant creation work is embedded inside `verify_tenant()` in `backend/app/routers/public.py`.

Implications:
- There is no staged provisioning pipeline yet.
- There is no explicit rollback boundary beyond the current database transaction.
- There is no reusable service contract for future self-service onboarding.

### Seeding support is incomplete for SaaS onboarding

`backend/app/seeding_utils.py` currently seeds only the platform superadmin from environment variables.

Implications:
- No tenant bootstrap package exists yet for a newly created university.
- Department, calendar, branding defaults, quota defaults, and onboarding state are not formalized.

### Metering has started

Copilot added a `UsageEvent` model and `POST /api/v1/usage/events` ingestion endpoint.

Implications:
- The platform now has a normalized place to record onboarding and generation-related usage events.
- The onboarding lifecycle should emit events through this model once the provisioning flow is extracted.

### Tenant context is still request-header driven

`backend/app/middleware/tenant.py` still depends on `X-University-ID`.

Implications:
- Background jobs and public verification flow cannot rely on middleware tenant context alone.
- Provisioning code should pass tenant identity explicitly until tenant-context hardening is expanded.

## Approved Provisioning Inputs And Defaults

The following inputs are approved for provisioning and must be resolved before `provisioning_complete` is set:

| Field | Required | Default if missing |
| --- | --- | --- |
| University name | Yes | none |
| Subdomain | Yes | none |
| Plan tier | Yes | `free` |
| Coordinator email | Yes | none |
| Coordinator name | Yes | none |
| Timezone | No | `Africa/Lusaka` |
| Branding (logo, colors) | No | platform defaults |
| Academic calendar | No | January-December standard |

These defaults are now locked for this slice. Antigravity should hardcode them in the provisioning baseline rather than introducing database-driven defaults.

## Recommended End-To-End Lifecycle

### Stage 1: Registration intake

Owner: existing public router, with Copilot support only if request schema changes

Flow:
1. Accept `TenantRegistrationRequest`.
2. Validate uniqueness for subdomain, username, and email.
3. Write `PendingRegistration` with opaque token and expiry.
4. Dispatch verification email task.

Required outputs:
- `PendingRegistration.id`
- opaque verification token
- normalized onboarding payload for later provisioning

### Stage 2: Verification and provisioning kickoff

Owner: Antigravity implementation, guided by current router behavior

Flow:
1. Validate token and expiry.
2. Move provisioning work out of the router into a dedicated service or orchestration function.
3. Create a provisioning sequence with explicit stage markers.

Recommended stages:
1. `tenant_record_created`
2. `admin_account_created`
3. `baseline_seed_applied`
4. `notifications_written`
5. `usage_baseline_recorded`
6. `provisioning_complete`

Stage 3 clarification:
- `baseline_seed_applied` must include quota row creation.
- Quotas are bootstrap data, not a separate post-provisioning job.
- `provisioning_complete` must not be set unless quota placeholders exist for the tenant.

### Stage 3: Baseline tenant seed

Owner: Antigravity for implementation, Codex contract here, Copilot only if schemas change

Minimum bootstrap package:
- University row with active status and initial plan tier
- first coordinator user
- default academic calendar scaffold
- tenant-safe branding defaults
- default quota placeholders

Optional later bootstrap:
- sample departments
- onboarding checklist state
- default support/help links

Required split for `backend/app/seeding_utils.py` after Antigravity's implementation:
- `seed_superadmin()`
- `seed_tenant_baseline()`
- `create_default_calendar()`
- `apply_branding_defaults()`
- `create_quota_placeholders()`
- `emit_onboarding_events()`
- `seed_onboarding_checklist()` as optional and deferred

Ownership note:
- Antigravity owns the timing and orchestration of `seed_tenant_baseline()`.
- Copilot owns the quota schema contract that powers `create_quota_placeholders(tenant_id, plan_tier)`.

### Stage 4: Rollback policy

Owner: Antigravity

Rollback rule:
- If provisioning fails before `provisioning_complete`, the system must not leave a partially active tenant that appears usable.

Recommended behavior:
- If failure occurs before commit: rollback transaction.
- If failure occurs after tenant row exists but before completion: mark tenant inactive and record provisioning status for manual retry or cleanup.
- Mark `PendingRegistration` with a terminal failure state instead of leaving it ambiguous.

Non-goal for this slice:
- Do not build automated retry logic yet.
- Manual retry by a Superadmin from a terminal failure state is acceptable for now.

## Metering And Event Alignment

Owner: Copilot for event shape and summaries, Antigravity for emit points

Implementation directive:
- Antigravity should not call the usage HTTP endpoint internally during provisioning.
- Copilot should expose an internal service API instead, for example `backend/app/services/usage.py`.

Suggested interface:

```python
async def emit_event(
    tenant_id: int,
    metric_key: str,
    quantity: int,
    source: str = "provisioning",
    metadata: dict | None = None,
):
    ...
```

This keeps the event contract in Copilot's codebase while avoiding HTTP overhead during provisioning.

The onboarding lifecycle should emit these events through `UsageEvent` once wiring is added:

1. `seats_active`
- Quantity: `1`
- Trigger: first coordinator account created
- Source: `job` or `admin`

2. `storage_bytes`
- Quantity: estimated bootstrap storage footprint if tracked early, otherwise defer
- Trigger: seed package writes tenant-owned assets

3. `department_count`
- Quantity: seeded count if baseline departments are created

4. `api_calls`
- Not needed for registration itself in the first pass unless public API billing includes onboarding traffic

Event timing rule:
- Onboarding events should emit only at Stage 5, `usage_baseline_recorded`, after the earlier provisioning stages succeed.
- Do not emit usage events during earlier partial stages.

Non-billing metric decision:
- Do not add `tenant_registrations` to the metering system in this slice.
- Registration volume belongs in product analytics tooling such as Plausible or PostHog, not billing metering.

## File Ownership Boundaries

### Antigravity owns next implementation work in:
- `backend/app/routers/public.py`
- `backend/app/tasks/registration_tasks.py`
- `backend/app/seeding_utils.py`
- `backend/app/services/provisioning.py`
- any related provisioning task module

Reason:
- Provisioning, rollback, and lifecycle orchestration are infrastructure-sensitive backend work.
- Router extraction is mandatory: the public router should validate and call `provision_tenant(pending_registration)`.

### Copilot owns follow-on work in:
- `backend/app/schemas.py`
- `backend/app/routers/usage.py`
- `backend/app/services/usage.py`
- reporting or quota endpoints
- quota placeholder contract consumed by provisioning

Reason:
- Metering schemas, ingestion contracts, and reporting surfaces remain in Copilot's lane.
- Internal usage-event emission and quota creation APIs should live in Copilot-owned service code, even when Antigravity invokes them.

### Codex owns cross-cutting review and integration checks

Codex should re-enter when:
- a new provisioning service needs coordination with usage events
- tenant context strategy affects both API and background jobs
- rollback semantics touch multiple subsystems

## Immediate Next Steps

1. Antigravity should extract inline provisioning logic from `verify_tenant()` into a dedicated provisioning flow with stage markers.
2. Antigravity should extend `seeding_utils.py` from "superadmin only" to "platform seed plus tenant bootstrap helpers", including quota creation in Stage 3.
3. Copilot should create an internal `emit_event()` service and a stable `create_quota_placeholders(tenant_id, plan_tier)` contract for Antigravity to call.
4. Codex should review the extracted flow once Antigravity's first implementation lands, especially for rollback semantics and event timing.

## Risks To Watch

1. Provisioning currently happens inside a request handler, which will become harder to manage as onboarding expands.
2. Tenant identification is inconsistent across public routes, authenticated routes, and background jobs.
3. Usage events can be added too early unless the tenant creation lifecycle exposes stable completion checkpoints.
4. Seeding defaults can drift from real onboarding data unless the approved defaults above are treated as authoritative during implementation.

## Approved Risk Directives

| Risk | Directive |
| --- | --- |
| Provisioning inside request handler | Must extract into `backend/app/services/provisioning.py` with `provision_tenant(pending_registration)`. Router validates and delegates only. |
| Tenant identification inconsistency | Acceptable for now. Public routes use token, authenticated routes use JWT, and background jobs pass `tenant_id` explicitly. Revisit in a later architecture review. |
| Usage events too early | Emit onboarding events only at Stage 5 after earlier stages succeed. |
| Seeding defaults drifting | Use the approved defaults in this document. No database-driven defaults in this slice. |
