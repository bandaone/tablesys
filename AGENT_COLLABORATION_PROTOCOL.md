# TABLESYS — Agent Collaboration Protocol

Audience: Codex, Copilot, Antigravity
Effective date: 2026-05-05
Purpose: Prevent collisions while executing the SaaS expansion plan.

---

## 1) Single Source Of Truth

Always read these in order before starting work:
1. TEAM_WORKPLAN.md
2. AGENT_STATUS.md
3. This protocol

If instructions conflict, use this precedence:
1. User instruction in current session
2. TEAM_WORKPLAN.md
3. AGENT_STATUS.md
4. This protocol

---

## 2) Mandatory Lock Workflow

Before any edit:
1. Check AGENT_STATUS.md -> Files Currently Locked.
2. If target file is locked by another agent, stop and add a blocker note.
3. If free, add your lock entry first.

Lock format:
- `<workstream>: <agent> -> <file1>, <file2>, ...`

After finishing:
1. Validate your changes.
2. Add Completed Work Log entry.
3. Add Handoff Note if another agent is unblocked.
4. Remove your lock entry.

---

## 3) Domain Ownership

Codex:
- Cross-cutting architecture and integration slices.
- Complex multi-step changes that span subsystems.
- Deep debugging and dependency/risk analysis.

Copilot:
- API routes, schemas, validation, boilerplate-heavy backend work.
- Reporting endpoints, docs scaffolding, repetitive test generation.

Antigravity:
- Infrastructure, security hardening, observability, reliability.
- Provisioning, orchestration, and backend performance-sensitive paths.

Rule:
- Do not edit outside your slice unless a handoff explicitly authorizes it.

---

## 4) Migration And Data Safety

1. Only one migration owner at a time.
2. No destructive shared-db operations (`drop_all`, full downgrades) in collaborative flow.
3. Use isolated test DB or transactional tests for validation.
4. Any change to deletion/export/compliance paths must include audit trail checks.

---

## 5) Handoff Contract

Use this exact format in AGENT_STATUS.md -> Handoff Notes:

- `[DATE] <From Agent> -> <To Agent>: <Task> COMPLETE`
- `UNBLOCKS: <next executable work>`
- `NOTES:`
- `  - Files changed`
- `  - Validation performed`
- `  - Risks or constraints`

Handoffs must be actionable. Avoid vague notes.

---

## 6) Definition Of Done (Per Slice)

A slice is done only when all are true:
1. Changes are validated with the narrowest relevant check.
2. Completed Work Log entry exists.
3. Handoff entry exists if needed.
4. Lock entry is removed.

---

## 7) Blocker Handling

If blocked by lock, missing decision, or vendor/legal dependency:
1. Do not continue speculative edits.
2. Add blocker note in AGENT_STATUS.md.
3. State exact unblock requirement and owner.

---

## 8) Operating Goal

All collaboration in this repo should move one of these outcomes forward:
1. Tenant lifecycle automation
2. Billing and metering
3. Observability and SLA reporting
4. Self-service documentation
5. Security/compliance/commercial readiness

---

## 9) Team Communication Model

Treat the agents like a dev team that reports through one shared board:
- The Team Leader (Dennis) assigns work in AGENT_STATUS.md.
- Each agent reads AGENT_STATUS.md first, then claims locks and executes.
- All progress and blockers are recorded in AGENT_STATUS.md.

This prevents side conversations and keeps all status in one place.

---

## 10) How To Assign Work (Task Cards)

Create one task card per agent in AGENT_STATUS.md under a new section called "Active Task Cards".
Use this exact template so each agent knows what to do:

Task Card Template:
- `[DATE] <Agent> | <Task Name>`
- `GOAL: <one sentence outcome>`
- `FILES: <exact file list or module scope>`
- `DEPENDENCIES: <decisions, locks, or prerequisites>`
- `VALIDATION: <command or check>`
- `HANDOFF: <who is unblocked>`

Rules:
- One active task card per agent at a time.
- If the task changes, update the card instead of creating a second one.
- If blocked, move it to Decision Blockers and note the owner.

---

## 11) Daily Briefing Loop (3 Lines Per Agent)

Each agent posts a short daily update in AGENT_STATUS.md under "Daily Briefing":
- `DONE: <what completed>`
- `NEXT: <what will be done next>`
- `BLOCKED: <what is stuck and why>`

This keeps leadership aware of current state without long logs.