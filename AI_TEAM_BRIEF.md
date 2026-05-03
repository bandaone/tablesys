# TABLESYS — AI Team Briefing

## What This Is
A university timetable management system for UNZA (University of Zambia).
Handles scheduling of lectures, rooms, lecturers, and student groups.

## Stack
- Backend: Python, Flask, SQLAlchemy, Alembic (migrations), OR-Tools (scheduling solver)
- Frontend: React, TypeScript, Vite, Playwright (E2E tests)
- Database: SQLite (dev), PostgreSQL (prod)
- Containerization: Docker, docker-compose

## Project Structure
- backend/app/        → main Flask application
- backend/tests/      → pytest test suite
- backend/alembic/    → database migrations
- backend/scripts/    → utility scripts
- frontend/src/       → React TypeScript source
- frontend/tests/     → Playwright E2E tests

## Critical Rules For AI Agents
1. NEVER modify alembic migration files — ask Dennis first
2. NEVER drop or reset the database without explicit instruction
3. Always run existing tests before and after making changes
4. The timetable solver is in backend/app — treat it as sensitive logic
5. Frontend uses Vite — use npm run dev to test, never modify vite.config.ts
6. Check requirements.txt before adding new Python packages
7. All API endpoints must maintain existing auth patterns

## How To Run
- Backend: cd backend && source venv/bin/activate && flask run
- Frontend: cd frontend && npm run dev
- Full stack: docker-compose up

## Current Focus
Active development — ask Dennis what the current task is before starting.
