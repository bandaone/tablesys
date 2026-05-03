# AI Agent Collaboration & Anti-Collision Protocol

**Target Audience:** Antigravity, Copilot, Cursor (and any other autonomous agent working on this codebase).
**Objective:** Guarantee that multiple agents can work concurrently on the TABLESYS repository without race conditions, merge conflicts, overwritten files, or logic collisions.

---

## 1. The File Locking System (Mandatory)
Before you (the AI Agent) edit *any* file, you must exclusively lock it.

1. **Check Locks First:** Read `AGENT_STATUS.md`. Look at the `## Files Currently Locked` section. If a file you need is locked by another agent, **STOP**. Do not proceed. Report the collision to the user.
2. **Claim Your Lock:** Before making edits, add your lock to `AGENT_STATUS.md` in the following format:
   `[Date] <Your-Name> -> <file/path/1.py>, <file/path/2.tsx>`
3. **Release Your Lock:** Once your task is completely done, tested, and verified, you must delete your lock line from `AGENT_STATUS.md` so other agents can access those files.

## 2. Strict Domain Boundaries
Never touch code outside the immediate scope of your assigned task. If you spot a bug in another agent's domain, **do not fix it**. Instead, append a note to the `TEAM_WORKPLAN.md` or `AGENT_STATUS.md` Handoff section.

### Quick Reference Map:
* **Antigravity Focus:** Backend infrastructure, algorithms (`services/timetable_generator.py`), Docker, CI/CD, complex multi-step backend integrations, security analysis.
* **Cursor Focus:** Complex frontend React components, UI/UX flows, multi-file frontend state architecture.
* **Copilot Focus:** Repetitive boilerplate generation, API route CRUD generation (`routers/`), schema updates, backend test generation.

*Rule of Thumb:* If it is a frontend `.tsx` file, Antigravity shouldn't touch it unless it's an infrastructure/API linking task. If it's `timetable_generator.py`, Copilot and Cursor should not touch it.

## 3. Communication & State Synchronization
Agents cannot talk directly to each other. Your communication medium is the **Handoff Notes** in `AGENT_STATUS.md`.

* **Start of Session:** Always read `AGENT_STATUS.md` first.
* **End of Session:** Provide an indisputable output of your work in the `## Completed Work Log`.
* **Handoff Template:** If your task unblocks a different agent, append this to the `## Handoff Notes` in `AGENT_STATUS.md`:

```markdown
- [DATE] <Your Name> -> <Next Agent>: <Phase/Task> COMPLETE
- UNBLOCKS: <What they can do now>
- NOTES: 
   - <What exactly did you do>
   - <What is strictly required of the next agent>
```

## 4. The "No Global Database Wipes" Rule
When making modifications to the schema or test suites:
* **Never use `alembic downgrade base` or `drop_all`** on the main development database running in Docker, as other agents might be actively relying on that seeded data for frontend UI testing.
* **Isolate Tests:** Use pytest fixtures with transactional rollbacks or a dedicated `tablesys_test` database for any backend testing routines.

## 5. Sequential Schema Migrations
Database schemas are the biggest single point of failure for parallel agent workers. 
* Only **ONE agent** is allowed to generate an Alembic migration at a time. 
* If Copilot needs a new column for a router, and Antigravity needs a new column for a service, **do not generate migrations concurrently**. 
* The user must explicitly command one agent to finalize the migration, commit it, and update `AGENT_STATUS.md` before the other agent generates theirs. 

## Summary Checklist For Every Prompt You Execute
1. Read `TEAM_WORKPLAN.md` to see exactly what phase we are in.
2. Read `AGENT_STATUS.md` to ensure your target files are not locked.
3. Lock your files in `AGENT_STATUS.md`.
4. Perform your modifications and test locally.
5. Remove your lock, leave a Handoff Note in `AGENT_STATUS.md`, and yield back to the user.
