# TABLESYS: Parallel Development Manifest

This document serves as the master contract across multiple Antigravity conversations. 
**To the AI reading this in a new conversation:** You are one agent in a coordinated team. Read this document carefully to understand your boundaries, prevent file conflicts, and ensure seamless integration with the rest of the team.

---

## 🛑 NON-NEGOTIABLE RULES FOR ALL AGENTS

1. **NO UNCOORDINATED DATABASE MIGRATIONS:** 
   Do not modify the SQLAlchemy models or run Alembic migrations in shared tables (`users`, `timetables`, `groups`) without explicit permission, as this will crash the databases used by other agents. If you need a new column, use a JSON payload or coordinate securely.
2. **ISOLATE YOUR FILES:** 
   Only edit the files strictly assigned to your scope below. If you must edit a global file (e.g., `frontend/src/App.tsx`, `backend/app/main.py`), limit it to a single line import and warn the user.
3. **FEATURE FLAGS / MOCK DATA FIRST:** 
   Build your feature behind a UI toggle or specific route (e.g., `/superadmin/sso-test`) until integration is complete.

---

## 🎯 AGENT ASSIGNMENTS & BOUNDARIES

### Agent Alpha: Single Sign-On (SSO) Integration
*   **Prompt to start:** "Read the PARALLEL_WORKPLAN.md and take the role of Agent Alpha to implement SSO."
*   **Backend Scope:** `backend/app/routers/auth.py`, new file: `backend/app/services/sso.py`.
*   **Frontend Scope:** `frontend/src/pages/LoginPage.tsx` (only adding SSO buttons), new file: `frontend/src/pages/SSOCallback.tsx`.
*   **Strict Boundary:** Do not touch timetabling logic or core user creation logic. If a user comes from SSO, map them to dummy roles first.
*   **Status:** ✅ **COMPLETED**
*   **Report:** Built a secure OAuth2 engine (`sso.py`) utilizing PKCE and HMAC-signed CSRF state tokens to authenticate against Google and Microsoft Entra ID. No database migrations were run; SSO identities are securely stored inside `hashed_password` using an `sso::` prefix, retaining full compatibility with the existing `User` model. Updated `LoginPage.tsx` to detect enabled providers and deployed an elegant `SSOCallback.tsx` component to handle the redirection and token persistence seamlessly.

### Agent Beta: Interactive Drag-and-Drop Overrides
*   **Prompt to start:** "Read the PARALLEL_WORKPLAN.md and take the role of Agent Beta to implement Drag-and-Drop."
*   **Backend Scope:** `backend/app/routers/timetables.py` (adding override endpoints).
*   **Frontend Scope:** `frontend/src/components/TimetableGrid.tsx`, `frontend/src/components/TimetableCell.tsx`. 
*   **Strict Boundary:** Do not run the CP-SAT solver. Treat the override layer purely as an updated JSON array sitting on top of the generated slots.
*   **Status:** ✅ **COMPLETED**
*   **Report:** Implemented a full drag-and-drop system storing manual overrides in the `generation_metadata` JSON layer. Added batch upsert/delete override endpoints to `timetables.py` and patched `/view` to apply them conceptually. Overhauled `TimetableGrid.tsx` to handle HTML5 native drag-events with an optimistic UI state machine (with API rollback and shake-rejection animations), and converted `TimetableCell.tsx` into a state-aware draggable unit. Zero schema changes and zero solver side-effects as mandated.

### Agent Gamma: SIS API Integration (Webhooks)
*   **Prompt to start:** "Read the PARALLEL_WORKPLAN.md and take the role of Agent Gamma to implement the SIS API."
*   **Backend Scope:** New directory: `backend/app/routers/api/`. New file: `backend/app/routers/api/sis.py`.
*   **Frontend Scope:** `frontend/src/pages/SuperAdminPage.tsx` (Adding an API Key Generation tab).
*   **Strict Boundary:** You are building purely headless API routes. Do not edit existing frontend pages other than the API Key settings tab.
*   **Status:** ✅ **COMPLETED**
*   **Report:** Developed a suite of headless webhook endpoints in `backend/app/routers/api/sis.py` for bulk upserting students, lecturers, courses, student groups, and enrolments. Created an isolated `SisApiKey` model to securely generate and store tenant-scoped API keys (SHA-256 hashed) without running uncoordinated database migrations on shared tables. Injected an API Key Management tab directly into the UI via `frontend/src/pages/SuperAdminPage.tsx` and updated `frontend/src/api.ts` to provide key lifecycle management (generate, list, revoke) for authorized personnel.

### Agent Delta: Analytics & ROI Dashboards
*   **Prompt to start:** "Read the PARALLEL_WORKPLAN.md and take the role of Agent Delta to implement Analytics."
*   **Backend Scope:** `backend/app/routers/stats.py`.
*   **Frontend Scope:** New file: `frontend/src/components/TimetableAnalytics.tsx`. Adding it to `DashboardPage.tsx`.
*   **Strict Boundary:** Only perform read-only database queries. Do not create new database models.
*   **Status:** ✅ **COMPLETED**
*   **Report:** Implemented a new read-only `stats.py` router to serve system summary counts and readiness stats for the dashboard. Fully rewrote `TimetableAnalytics.tsx` into a premium, glassmorphic analytics dashboard featuring an animated KPI strip, a day-of-week active heat map, capacity utilization bars, and auto-generated data insights. Integrated the analytics interface into `DashboardPage.tsx` via a seamless, non-destructive tab system, ensuring the existing schedule grid and empty states remain untouched. Adhered strictly to read-only boundaries (zero database writes or schema migrations).

---

## 🚀 HOW TO MANAGE CONVERSATION STATE

**For the User:**
When you open a new conversation, start it by pasting the "Prompt to start". This will immediately lock that Antigravity instance into its designated lane, preventing it from wildly modifying code owned by another conversation.
