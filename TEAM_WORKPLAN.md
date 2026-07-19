# TABLESYS — SaaS Team Coordination Plan
> **Version:** 4.2 (Current Operating Plan) · **Date:** 2026-05-05
> **Project:** TABLESYS — University SaaS Expansion
> **Owner:** Dennis Banda · **Team:** codex · Copilot · Antigravity

---

## Purpose

This is the active team plan for the SaaS expansion. It replaces older task matrices and keeps one current operating model for the three roles.

---

## Team Roles

### Team Leader

Owns product direction, non-coding execution, and final approvals.

Responsibilities:
- Define pricing, tiers, and quota policy.
- Own legal and commercial documents.
- Choose vendors for billing, observability, and support tooling.
- Approve release gates and rollout timing.
- Handle all non-coding work and external coordination.

Deliverables:
- Pricing model and quota policy.
- DPA, SLA, MSA, and Terms of Service drafts.
- Business registration progress.
- Vendor shortlist and procurement decisions.
- Support and knowledge-base approvals.

### Codex

Owns cross-cutting architecture, integration slices, and resolving systemic conflicts.

Responsibilities:
- Bridge gaps between Copilot's APIs and Antigravity's infrastructure.
- Model wide-reaching database relations (e.g., Tenant onboarding flows).
- Validate runtime behavior across boundaries.

Deliverables:
- Integration contracts (e.g., Onboarding Integration).
- Systemic schema reconciliation and merge strategies.
- End-to-end flow validation.

### Copilot

Owns patterned backend/API work, schemas, reporting surfaces, and documentation scaffolding.

Responsibilities:
- Add and maintain API routes.
- Build request/response schemas and validation.
- Add billing and metering endpoints.
- Build reporting endpoints for usage and SLA summaries.
- Generate router-level tests and docs stubs.

Deliverables:
- Usage and quota API surface.
- Monthly reporting endpoints.
- Admin-ready reporting helpers.
- Router tests and validation coverage.

### Antigravity

Owns backend infrastructure, automation, security, observability, and lifecycle orchestration.

Responsibilities:
- Build tenant lifecycle automation.
- Wire seeding, provisioning, and rollback flows.
- Add telemetry and health instrumentation.
- Enforce security, rate limits, and data protection flows.
- Add backup, restore, and disaster-recovery support.

Deliverables:
- Tenant creation pipeline.
- Observability and SLA data capture.
- Security and retention controls.
- Backup/restore procedures.
- Backend regression tests.

---

## Coordination Rules

1. One owner per file. Only one agent writes to a file during a slice.
2. One migration at a time. No parallel schema changes.
3. Lock before edit. Claim the file in `AGENT_STATUS.md` before changing it.
4. Handoff before overlap. Release the lock and write the handoff note before another agent starts the next slice.
5. Non-coding work stays with the Team Leader.
6. If a change touches another owner’s area, stop and hand off rather than crossing boundaries.

---

## Workstreams

### 1. Tenant Lifecycle Automation

Owner: Antigravity

Goal: Make every new university self-provisioning instead of manually onboarded.

Deliverables:
- Tenant creation API.
- Automated database seeding.
- DNS or provisioning hook integration.
- Welcome sequence and onboarding completion flow.
- Rollback handling for failed provisioning.

Acceptance criteria:
- A tenant can be created from one controlled request.
- A seeded environment is created consistently.
- Failures roll back safely.

Dependencies:
- Final tenant data contract.
- Team Leader approval of onboarding fields.

### 2. Billing and Metering Infrastructure

Owner: Copilot

Goal: Measure usage so the product can enforce plans and charge correctly.

Deliverables:
- Metering for active students per tenant.
- Metering for timetable generations per month.
- Metering for departments and courses as complexity proxies.
- API call volume capture if public APIs are exposed.
- Storage usage tracking for uploads and audit logs.
- Monthly usage summary endpoints.

Acceptance criteria:
- Usage is captured per tenant.
- Quota and tier checks can be performed from the API layer.
- Monthly reports can be generated on demand.

Dependencies:
- Stable tenant identity on every request.
- Team Leader approval of plan quotas and billable metrics.

### 3. Observability and SLA Monitoring

Owner: Antigravity

Goal: Prove uptime, performance, and reliability to institutional buyers.

Deliverables:
- API response-time metrics by endpoint.
- Timetable generation success rate and duration.
- Database connection pool saturation metrics.
- Solver timeout and fallback-to-greedy tracking.
- Tenant-specific error rates.
- Monitoring stack recommendation and integration plan.

Acceptance criteria:
- Health and performance metrics are visible per tenant.
- SLA reporting data can be produced monthly.
- Alerting can be connected to an external monitoring vendor.

Dependencies:
- Consistent telemetry naming.
- Team Leader vendor selection.

### 4. Self-Service and Documentation

Owner: Copilot, with Team Leader approval for public-facing copy

Goal: Reduce support load by making setup and troubleshooting self-service.

Deliverables:
- CSV template downloads with validation rules.
- Step-by-step generation walkthroughs.
- Common error and fix articles.
- API documentation if public endpoints exist.
- Video tutorial outline and support script.

Acceptance criteria:
- Coordinators can discover upload rules without support.
- Common errors are documented with fixes.
- Documentation matches the current API and UI.

Dependencies:
- Final upload format.
- Team Leader approval for customer-facing wording.

### 5. Security, Compliance, and Commercial Foundation

Owner: Team Leader for policy; Antigravity for technical enforcement

Goal: Make TABLESYS ready for institutional procurement.

Deliverables:
- DPA template.
- Pen-test procurement and report filing.
- Backup and disaster-recovery policy.
- Encryption-at-rest verification.
- Rate limiting on public endpoints.
- Data export and deletion capability.
- Terms of Service, SLA, and MSA drafts.
- Business entity registration progress.

Acceptance criteria:
- Technical safeguards are implemented and documented.
- Legal documents exist in draft form.
- Monthly SLA reporting can be attached to tenant accounts.

Dependencies:
- Observability and billing foundations.
- Team Leader ownership of legal/commercial approvals.

---

## Delivery Order

### Stage 1: Decisions (Completed)

- [x] 1. Team Leader confirms plan tiers, quotas, SLA target, and legal owners.
- [x] 2. Team Leader selects monitoring and billing vendors.
- [x] 3. Team Leader confirms support content priorities.

### Stage 2: Core Platform (Completed)

- [x] 1. Antigravity builds tenant lifecycle automation.
- [x] 2. Copilot builds metering and reporting endpoints.
- [x] 3. Antigravity adds observability and security controls.
- [x] 4. Codex resolves integration contracts and runtime verification.

### Stage 3: Customer Readiness (Completed)

- [x] 1. Copilot publishes self-service documentation.
- [x] 2. Team Leader finalizes legal and commercial artifacts.
- [x] 3. Antigravity validates backup, restore, export, and deletion paths.

### Stage 4: Commercial Launch (Pending)

- [ ] 1. Team Leader signs off pricing and contract package.
- [ ] 2. Copilot & Codex confirm end-to-end billing and reporting flows.
- [ ] 3. Antigravity confirms production monitoring and operational readiness.

---

## Working Agreement

- Any task touching tenant lifecycle, billing, observability, security, or compliance is written here before implementation starts.
- Keep non-coding work out of code files.
- Every finished slice ends with a lock release and a handoff note in `AGENT_STATUS.md`.
- Use the Team Leader as the decision point whenever a task needs legal, commercial, vendor, or policy approval.

---

## Immediate Next Actions

1. **Copilot**: Begin Workstream 4. Draft self-service documentation scaffolding (CSV templates, API docs, generation walkthroughs).
2. **Team Leader**: Provide copy approval for support articles and finalize compliance document drafting.
3. **Codex**: Stand by to support Copilot with API documentation structures, or unblock Antigravity with export/deletion technical contracts.
4. **Antigravity**: Stand by for production monitoring integration or deployment execution. All security, compliance, observability, and tenant lifecycle foundations are complete.

---

## Notes

This is the active coordination plan. Older phase tables and strength matrices were removed so the team has one current operating model.