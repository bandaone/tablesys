# TABLESYS: Enterprise & Go-To-Market Roadmap

This document outlines the critical technical features required to move TABLESYS from a mathematically sound, beautiful tool into a commercially viable, enterprise-grade SaaS product that can survive brutal university procurement processes.

## 1. Single Sign-On (SSO) Integration
**Priority: CRITICAL (Blocker for Enterprise Sales)**
Universities will not mandate 20,000 students and staff to create new passwords. IT departments require centralized identity management for security and off-boarding.
*   **Requirements:**
    *   OAuth2 / OpenID Connect support.
    *   Integration with **Microsoft Entra ID (Azure AD)** and **Google Workspace**.
    *   SAML 2.0 support for legacy university identity providers (Shibboleth).
    *   Auto-provisioning of accounts when a user successfully authenticates via their university email domain.

## 2. Interactive Drag-and-Drop Override System
**Priority: HIGH (Blocker for Coordinators)**
While the CP-SAT engine generates mathematically optimal schedules, human edge-cases always exist (e.g., "Dr. Smith gets Tuesday mornings off for research"). Coordinators will reject the system if they cannot easily manually tweak the AI's output.
*   **Requirements:**
    *   Interactive Drag-and-Drop UI in the `Live Master Timetable` view.
    *   Real-time conflict validation (if a block is dropped into a slot that causes a lecturer/room/student group clash, the UI must flash red and show the specific conflict).
    *   Ability to "pin" a block, locking it in place before re-running the solver to optimize around the manual changes.

## 3. Student Information System (SIS) API Integration
**Priority: HIGH (Blocker for IT & Data Migration)**
Manual Excel uploads are acceptable for pilots and small colleges, but massive universities automate this. They need direct pipes from their source of truth.
*   **Requirements:**
    *   Secure REST API endpoints with API key authentication for automated data syncing.
    *   Data mapping templates or webhooks to ingest raw data from systems like **Ellucian Banner**, **Oracle PeopleSoft**, or LMS platforms like **Moodle/Canvas**.
    *   Nightly sync capabilities to update student group sizes and lecturer lists automatically.

## 4. Resource Utilization & ROI Dashboards
**Priority: MEDIUM (Required for Executive Buy-in / Sales)**
To sell to University Chancellors or CFOs, the system must justify its own cost by demonstrating savings in facility overhead.
*   **Requirements:**
    *   Analytics dashboards tracking "Room Utilization %" (e.g., "Lecture Hall A is only used 40% of the week").
    *   Metrics showing the reduction in student-class conflicts compared to previous semesters.
    *   Exportable Excel/PDF reports that Registrars can take to board meetings to prove the software is saving the university money.

## 5. Staging & Draft Timetable Environments
**Priority: MEDIUM**
Schedulers need a sandbox to test "what-if" scenarios without affecting the live student portal.
*   **Requirements:**
    *   Ability to have multiple versions of a timetable (e.g., "Draft A", "Draft B").
    *   A staging viewer where staff can log in and review Draft A before the SuperAdmin hits the "Publish to Live" button.
