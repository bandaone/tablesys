# ADR 0001: Mobile Delivery Architecture

## Status

Accepted

## Date

2026-04-26

## Context

TABLESYS currently provides timetable generation and administration through a React frontend and FastAPI backend. A basic student portal exists, but it is not yet the lightweight, installable, low-bandwidth timetable experience needed for daily student and lecturer adoption.

The team needs a mobile delivery strategy that:

- works on Android and iPhone
- is fast to ship
- supports offline timetable access
- does not destabilize timetable generation
- can evolve into a richer mobile product over time

The team also needs clarity that this work is an access layer for timetable consumers, not a replacement for the full management platform.

## Decision

We will deliver the first mobile timetable experience as a Progressive Web App built within the existing React/Vite frontend and powered by a published timetable snapshot layer in the FastAPI backend.

This PWA is a separate access layer for students and lecturers. It does not replace the main web platform used by HODs, coordinators, admins, and superadmins.

## Rationale

### Why a PWA first

- one codebase for web and mobile delivery
- lower delivery risk than starting native apps
- supports install-to-home-screen behavior
- supports offline caching and notification patterns
- aligns with the existing frontend stack
- still works as a browser experience beyond phones

### Why published snapshots

- separates student and lecturer access from draft/admin timetable state
- keeps read traffic away from generator-heavy workflows
- makes `now`, `today`, and `week` cheap to serve
- provides a stable contract for offline sync and caching

### Why not reuse admin endpoints directly

- payloads are too heavy
- semantics are shaped for coordination and management, not daily mobile use
- mixing draft/admin state with end-user mobile views increases risk

## Consequences

### Positive

- fast path to a professional mobile product
- clear separation of concerns
- easier offline strategy
- better long-term scaling for high-frequency phone access

### Negative

- requires introducing a new published-read layer
- adds another API surface to maintain
- requires careful publish/invalidation design

## Implementation Notes

- mobile endpoints live under `/api/v1/mobile`
- mobile payloads must be compact and versioned
- the first screen must be `Now / Next / Today`
- service worker caching should target personal published data only
- calendar export and reminders are part of the mobile adoption strategy, not optional extras

## Follow-Up

Immediate follow-up work:

1. add mobile router and service scaffolding
2. define published snapshot entities
3. build student mobile MVP before broader lookup and alert features
