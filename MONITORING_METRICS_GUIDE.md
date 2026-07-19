# TABLESYS Monitoring Metrics Guide

This guide explains all monitored metrics across the TABLESYS platform and what they mean for system health, tenant performance, and business operations.

---

## Table of Contents

1. [System Infrastructure Metrics](#system-infrastructure-metrics)
2. [Tenant Usage Metrics](#tenant-usage-metrics)
3. [Tenant Performance & SLA Metrics](#tenant-performance--sla-metrics)
4. [Live Audit & Event Stream](#live-audit--event-stream)

---

## System Infrastructure Metrics

**Location:** System Monitor → Host / Infrastructure Health tab

These are platform-level metrics that indicate whether the TABLESYS server itself is healthy and responsive. All tenants share this infrastructure.

### CPU Usage

**What it measures:** Percentage of available CPU being consumed by the TABLESYS application and background workers.

**Health thresholds:**
- **Healthy:** < 65%
- **Watch:** 65–80%
- **Critical:** > 80%

**Why it matters:**
- Shows whether the application has headroom for concurrent timetable generation requests
- High CPU indicates the solver is under load or many background jobs are running
- Critical CPU usage can cause generation timeouts and slow API responses

**Action needed:**
- Watch (65–80%): Monitor trends; consider scheduling heavy generations during off-peak hours
- Critical (>80%): Investigate active jobs, pause non-urgent background tasks, or scale infrastructure

---

### Memory Usage

**What it measures:** Percentage of available RAM being consumed by the TABLESYS application stack (FastAPI, Celery workers, Python processes).

**Health thresholds:**
- **Healthy:** < 65%
- **Watch:** 65–80%
- **Critical:** > 80%

**Why it matters:**
- Memory pressure impacts the speed of timetable solver algorithms
- Out-of-memory conditions cause processes to crash or swap, severely degrading performance
- Each background worker (Celery) consumes memory proportional to the number of solver jobs queued

**Action needed:**
- Watch: Monitor; consider increasing memory or reducing concurrent solver jobs
- Critical: Stop accepting new generation jobs immediately; identify memory leaks; restart Celery workers if needed

---

### Disk Usage

**What it measures:** Percentage of disk space used on the storage partition where TABLESYS stores uploads, generated artifacts, and audit logs.

**Health thresholds:**
- **Healthy:** < 75%
- **Watch:** 75–90%
- **Critical:** > 90%

**Why it matters:**
- If disk fills to 100%, the database and file uploads fail
- Audit logs and timetable artifacts are stored on disk; full disk = lost operational data
- Generated PDFs and Excel files consume significant space during peak usage

**Action needed:**
- Watch (75–90%): Archive old uploads; compress logs; plan storage expansion
- Critical (>90%): Immediately archive or delete old timetables and audit logs; add storage

---

### PostgreSQL

**What it measures:** Connection status of the PostgreSQL database (online/offline).

**Values:**
- **Online:** Database is reachable and accepting connections
- **Offline:** Database is unreachable (network issue, process crashed, or maintenance mode)

**Why it matters:**
- If PostgreSQL goes offline, the entire platform becomes unavailable
- All tenant data (users, courses, timetables, audit logs) lives in PostgreSQL
- A single database serves all tenants; its unavailability affects everyone

**Action needed:**
- If Offline: Check database process, network connectivity, authentication credentials
- If it remains offline for >2 minutes, alert ops team immediately

---

### Redis & Celery

**What it measures:** Status of Redis (online/offline) and the count of active background solver jobs.

**Values:**
- **Redis Status:** Online/Offline
- **Active Jobs:** Number (e.g., "online • 5 jobs")

**Why it matters:**
- Redis is the task broker for background timetable generation jobs
- If Redis goes offline, no new generations can be queued
- Active jobs count shows current load on the solver system
  - 0–2: Light load
  - 3–5: Moderate load
  - 6+: Heavy load; users may experience delays

**Action needed:**
- Redis Offline: Check Redis process; ensure network access; restart if necessary
- Jobs > 8: Notify tenants of delays; monitor solver timeout rates

---

### System Uptime

**What it measures:** How many hours the TABLESYS platform has been continuously running without a restart.

**Health:**
- **Healthy:** ≥ 1 hour (freshly started is OK)
- **Watch:** Any uptime is acceptable unless it indicates frequent crashes

**Why it matters:**
- Shows whether the application is stable
- Frequent restarts (< 1 hour uptime regularly) indicate crashes, memory leaks, or unstable code
- Long uptime (weeks+) is normal and healthy

**Action needed:**
- If uptime resets frequently: Check error logs for crash patterns; investigate for memory leaks or infinite loops

---

## Tenant Usage Metrics

**Location:** Organizations tab → Tenant list or Billing & Usage tab (per-tenant)

These metrics measure how much each tenant is using the platform. They feed into billing, quota enforcement, and plan tier validation.

### Seats Active

**What it measures:** Number of unique students currently active or enrolled in a tenant's system.

**Why it matters:**
- Pro and Enterprise plans charge per seat
- Free tier has a seat limit; exceeding it blocks new enrollments
- Shows tenant size and complexity

**Quota enforcement:**
- Free: Default limit (e.g., 100 seats)
- Pro: Metered pricing (pay per seat over base)
- Enterprise: Custom negotiated limit

**Data source:** SIS webhooks or manual upload

---

### Timetable Generations

**What it measures:** Count of timetable generation runs (successful + failed) per month.

**Why it matters:**
- Each generation run consumes CPU and memory
- Pro/Enterprise plans have soft limits; excessive generations degrade shared infrastructure
- Tracks solver workload trends

**Quota enforcement:**
- Free: 5 generations/month (soft limit; warning at 80%)
- Pro: 50 generations/month
- Enterprise: Unlimited or negotiated

**Data source:** Tracked in audit logs when `GENERATE_TIMETABLE` event is logged

---

### Department Count

**What it measures:** Number of academic departments configured in the tenant's instance.

**Why it matters:**
- Proxy for scheduling complexity
- More departments = more timetable complexity
- Used for support SLA classification

**Typical ranges:**
- Small tenant: 1–3 departments
- Medium tenant: 4–8 departments
- Large tenant: 9+ departments

**Data source:** Counted from the `departments` table scoped to tenant

---

### Course Count

**What it measures:** Total courses across all departments in a tenant.

**Why it matters:**
- Complexity proxy (more courses = larger search space for solver)
- Billing determinant in some plan tiers
- Shows tenant scale

**Typical ranges:**
- Small: 50–150 courses
- Medium: 150–500 courses
- Large: 500+ courses

**Data source:** Counted from the `courses` table scoped to tenant

---

### Storage Bytes

**What it measures:** Total disk space used by a tenant's uploads, generated PDFs, Excel files, and logs.

**Why it matters:**
- Storage is a limited resource
- Free tier has a storage quota; Pro/Enterprise have higher limits
- Tracks upload volume and artifact generation

**Quota enforcement:**
- Free: 1 GB
- Pro: 10 GB
- Enterprise: 100+ GB or unlimited

**Data source:** Calculated from file sizes in the uploads folder and audit log retention

---

## Tenant Performance & SLA Metrics

**Location:** Super Admin → Tenant Performance tab

These metrics measure how well each tenant's instance is performing and whether it meets SLA commitments.

### API Response Time (Average)

**What it measures:** Average round-trip time (in milliseconds) for HTTP requests to tenant-specific endpoints.

**Example:** `245 ms` means the average API call takes ~245 milliseconds from request to response.

**Health targets (varies by plan):**
- **Free:** SLA target ≤ 500 ms (best effort)
- **Pro:** SLA target ≤ 300 ms
- **Enterprise:** SLA target ≤ 150 ms (or negotiated)

**Why it matters:**
- Slow APIs frustrate users and indicate infrastructure overload or code inefficiency
- Response time SLA is a major contract commitment to institutional buyers

**Factors that increase response time:**
- High CPU usage (solver processes consuming cycles)
- High database query load
- Network latency
- Large response payloads (e.g., exporting 5000-slot timetables)

**Action needed:**
- If consistently > SLA target: Profile database queries, check for N+1 queries, optimize solver I/O

---

### Error Rate

**What it measures:** Percentage of HTTP requests that result in an error (4xx or 5xx status codes).

**Example:** `2.45%` means ~2.45 out of every 100 requests fail.

**Health targets:**
- **Healthy:** < 0.5%
- **Watch:** 0.5–2%
- **Critical:** > 2%

**Why it matters:**
- High error rates indicate bugs, misconfiguration, or resource exhaustion
- Affects user experience and SLA compliance
- Helps identify systematic issues (e.g., a bad deployment)

**Common causes:**
- Out-of-memory errors (500)
- Validation failures (400)
- Quota exceeded errors (429)
- Database deadlocks (503)

**Action needed:**
- Watch (0.5–2%): Monitor; investigate specific error endpoints
- Critical (>2%): Check application logs immediately; consider rollback if recent deployment

---

### SLA Compliance

**What it measures:** Percentage of requests that met the response-time SLA for the tenant's plan tier.

**Example:** `98.5% SLA compliance` means 98.5% of requests finished within the target time.

**SLA targets (typical):**
- Free: No SLA guarantee (best effort)
- Pro: 95% compliance
- Enterprise: 99% compliance

**Why it matters:**
- Legal/commercial commitment to the tenant
- Determines whether credits or penalties apply under the contract
- Shows whether infrastructure can reliably serve the tenant

**Action needed:**
- Below contract target: Identify bottlenecks; scale if needed; may trigger automatic credits
- Consistently below 90%: Escalate to ops; review architecture

---

### Generation Success Rate

**What it measures:** Percentage of timetable generation runs that completed successfully (vs. timeouts or errors).

**Example:** `94.2% success rate` means 94.2% of generation attempts produced a valid timetable.

**Health targets:**
- **Healthy:** > 95%
- **Watch:** 90–95%
- **Critical:** < 90%

**Why it matters:**
- Users rely on generation to work; failures block their workflow
- Low success rates indicate solver crashes, timeouts, or constraint violations
- High success rates show good algorithm reliability

**Common causes of failures:**
- Timetable too constrained (impossible to schedule all courses)
- Solver timeout (CPU overloaded)
- Out-of-memory during solver execution
- Greedy fallback activated (no optimal solution found)

**Action needed:**
- Watch (90–95%): Analyze failed generations; check if constraints are too tight
- Critical (<90%): Alert solver team; may need constraint relaxation or solver tuning

---

### Generation Average Duration

**What it measures:** Average time (in seconds) it takes to generate one timetable.

**Example:** `12.3 sec` means typical generations take about 12 seconds.

**Factors affecting duration:**
- **Size:** Larger timetables (more courses, students, rooms) take longer
- **Complexity:** More constraints = longer solver time
- **Infrastructure:** CPU-bound; faster CPUs = faster generations
- **Algorithm quality:** Greedy fallback is faster but lower quality

**Health targets:**
- Small timetable (<100 courses): 2–5 sec
- Medium timetable (100–500 courses): 5–20 sec
- Large timetable (500+ courses): 20–60 sec

**Why it matters:**
- Users wait for generations; long durations frustrate
- Indicates algorithm efficiency and infrastructure capacity
- Combined with success rate, shows solver health

**Action needed:**
- If consistently > 60 sec: Check if solver is timing out; consider increasing CPU or relaxing constraints

---

### Generation Fallback Runs

**What it measures:** Count of generation attempts that fell back to a simpler greedy algorithm instead of using the full solver.

**Why it matters:**
- Fallbacks produce lower-quality schedules (more conflicts, worse utilization)
- Indicate that optimal solutions couldn't be found in time
- Show solver is struggling with timetable complexity

**When fallbacks occur:**
- Solver reaches timeout (default: 30 seconds)
- Memory pressure or CPU saturation
- Constraints are over-specified or conflicting

**Action needed:**
- If fallbacks > 20% of generations: Review constraint tightness; consider splitting timetable generation

---

### Health Status

**What it measures:** Overall classification of a tenant's operational status: healthy, warning, or critical.

**Status meanings:**
- **Healthy:** All metrics within SLA targets; no issues detected
- **Warning:** One or more metrics trending toward SLA breach; minor issues
- **Critical:** One or more metrics breached SLA; immediate action needed

**How it's calculated:**
- Red flags: Error rate > 2%, SLA compliance < threshold, generation success < 90%
- Orange flags: Response time trending up, fallback runs increasing
- Green: All metrics normal

**Action needed:**
- Warning: Investigate root cause; no immediate action required
- Critical: Page on-call team; may need infrastructure scaling or code rollback

---

## Live Audit & Event Stream

**Location:** System Monitor tab → Live event widgets

These show real-time activity across the platform. Useful for debugging, security audits, and understanding user behavior.

### Authentication & Security

**Events captured:**
- `LOGIN_SUCCESS` / `LOGIN_FAILURE` — User login attempts
- `LOGOUT` — User logout
- `ROLE_CHANGE` — Permission/role changes
- Rate-limit blocks and suspicious activity

**Why it matters:**
- Detects unauthorized access attempts
- Identifies compromised accounts (multiple failed logins)
- Tracks permission changes for compliance

**Filter for:**
- Multiple failed logins from same IP (brute force attempt)
- Unexpected role elevations
- Off-hours admin actions

---

### Data Changes (CRUD)

**Events captured:**
- `CREATE_*` — New entity created (course, lecturer, room, etc.)
- `UPDATE_*` — Entity modified
- `DELETE_*` — Entity deleted

**Examples:**
- `CREATE_COURSE` — New course added
- `UPDATE_TIMETABLE` — Timetable edited
- `DELETE_USER` — User account removed

**Why it matters:**
- Audit trail for compliance (who changed what and when)
- Helps diagnose bulk import issues
- Shows data editing patterns

---

### Bulk Uploads & Imports

**Events captured:**
- `BULK_UPLOAD_COURSES` — CSV upload of courses
- `BULK_UPLOAD_STUDENTS` — Student roster import
- `BULK_UPLOAD_LECTURERS` — Lecturer data import
- `IMPORT_TIMETABLE` — Timetable import from Excel

**Includes:**
- Number of records processed
- Errors and validation failures
- Success/failure status

**Why it matters:**
- SIS integrations rely on bulk uploads
- Upload failures block data sync
- Tracks data quality issues (e.g., duplicate students)

---

### Timetable Generation

**Events captured:**
- `GENERATE_TIMETABLE` — Timetable generation run initiated
- Includes: success/failure, duration, slot count, fallback flag

**Example event:**
```
GENERATE_TIMETABLE
User: coordinator@acme.edu
Status: success
Duration: 14.2 sec
Slots: 347
Fallback: no
```

**Why it matters:**
- Shows generation load over time
- Identifies users running excessive generations
- Detects solver failures or timeout patterns

---

### Errors & Anomalies

**Events captured:**
- `SYSTEM_ERROR` — Unhandled exceptions
- Failed operations with error messages
- Rate limit blocks
- Validation failures

**Examples:**
- Out-of-memory during generation
- Database deadlock
- Invalid CSV format in upload
- Quota exceeded

**Why it matters:**
- Detects systematic issues
- Helps debugging user-reported problems
- Shows when infrastructure is under stress

**Action needed:**
- Spike in errors: Check application logs
- Specific error recurring: May indicate code bug or misconfiguration

---

## How These Metrics Work Together

```
┌─────────────────────────────────────────────────────────────────┐
│ SYSTEM INFRASTRUCTURE (All Tenants)                             │
│ CPU, Memory, Disk, DB, Redis, Uptime                           │
│ ↓ (If ANY critical → Platform is at risk)                      │
├─────────────────────────────────────────────────────────────────┤
│ TENANT USAGE (Per Tenant)                                       │
│ Seats, Generations, Courses, Storage                            │
│ ↓ (Feeds billing, quota enforcement, SLA classification)       │
├─────────────────────────────────────────────────────────────────┤
│ TENANT PERFORMANCE (Per Tenant)                                 │
│ API latency, Error rate, SLA compliance, Generation health      │
│ ↓ (Determines whether SLA credits/penalties apply)             │
├─────────────────────────────────────────────────────────────────┤
│ LIVE AUDIT STREAM (Real-time, All Actions)                      │
│ Security, CRUD, Uploads, Generations, Errors                   │
│ ↓ (Used for troubleshooting, compliance, debugging)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference: When to Investigate

| Metric | Warning Level | Action |
|--------|---------------|--------|
| CPU > 80% | Critical | Stop non-urgent jobs; scale |
| Memory > 80% | Critical | Check memory leaks; restart workers |
| Disk > 90% | Critical | Archive logs/uploads immediately |
| PostgreSQL Offline | Critical | Check DB process; page ops |
| Redis Offline | Critical | Restart Redis; queue jobs blocked |
| API response time > SLA | Warning | Check slow queries; profile code |
| Error rate > 2% | Warning | Check error logs; may need rollback |
| Generation success < 90% | Warning | Analyze constraint violations; tune solver |
| SLA compliance below contract | Critical | Scale infrastructure or negotiate |
| Frequent fallback runs | Warning | Review scheduling complexity; split TTG |

---

## Access & Permissions

- **System Monitor:** Superadmin only
- **Tenant Performance:** Superadmin only
- **Audit Logs:** Admin (coordinator) or Superadmin
- **Billing & Usage:** Coordinator (their own tenant) or Superadmin
