# TABLESYS — Backup and Disaster Recovery Policy

**Document owner:** Antigravity (technical author)  
**Approval required from:** Team Leader (Dennis Banda) before publishing to clients  
**Version:** 1.0 — 2026-05-05  
**Classification:** Internal — Engineering + Legal

**Last verified restore test:** [DATE] — [PASS/FAIL]  
**Performed by:** [NAME]

> Update these two fields every time a monthly restore test is completed (Section 8.2).
> When a university procurement officer asks "when did you last test your backups?", the answer is here.

---

## 1. Purpose

This document describes exactly what TABLESYS backs up, how often it backs it up, how long those backups are kept, how to restore from them, and what to do when something goes seriously wrong. It exists for three reasons:

1. **Operational survival** — so the engineering team knows what to do at 2 AM when a database crashes.
2. **Client trust** — so universities know their timetable data is safe and recoverable.
3. **Commercial readiness** — institutional procurement teams (procurement officers, IT directors, legal reviewers) will ask for a written policy. This is that policy.

---

## 2. What Data TABLESYS Stores

Understanding what we store is the foundation of any backup policy. TABLESYS holds data in three places:

### 2.1 PostgreSQL Database (Primary — most critical)

This is where everything lives. The database is a single PostgreSQL instance accessed via the `DATABASE_URL` environment variable.

The database contains **14 categories of data** across the following tables:

| Category | Tables | Why It Matters |
|---|---|---|
| **Tenants** | `universities`, `pending_registrations` | Identity and billing context for every client |
| **User accounts** | `users` | Login credentials (hashed), roles, contact emails |
| **Academic structure** | `departments`, `courses`, `rooms`, `student_groups` | The core configuration each university sets up |
| **Staff** | `lecturers`, `lecturer_assignments`, `lecturer_unavailability` | Scheduling inputs — often hard to recreate |
| **Timetables** | `timetables`, `timetable_slots`, `course_group_links` | The generated output — the primary deliverable |
| **Exams** | `exam_periods`, `exam_papers`, `exam_slots`, `exam_slot_rooms`, `exam_session_windows`, `exam_seating_profiles` | Exam scheduling data |
| **Communication** | `notifications`, `course_announcements` | Lecturer-to-student messages |
| **Billing & metering** | `usage_events`, `usage_monthly_summaries`, `plan_quotas` | Usage records needed for billing |
| **Audit trail** | `audit_logs` (flat file: `logs/audit.log`) | Security and compliance evidence |
| **Branding** | `universities.logo_url`, `universities.primary_color` | Cosmetic but client-visible |
| **Schema history** | `alembic_version` | Which migrations have been applied |

**Estimated production size:** Approximately 50–200 MB per active tenant depending on timetable complexity. A 50-tenant platform should stay well under 10 GB for the foreseeable future.

### 2.2 Redis (Cache — secondary)

Redis is used exclusively as a **Celery task queue and short-lived cache**. It does NOT store persistent business data.

- **Contents:** Pending background job metadata (verification emails, monthly usage aggregation jobs).
- **Loss impact:** If Redis is lost, pending jobs that haven't been picked up yet will be lost. No historical data is lost. Background tasks will simply need to be re-triggered manually.
- **Backup requirement:** Low. Redis persistence (AOF or RDB) should be enabled as a convenience, but Redis loss is not a disaster.

### 2.3 Filesystem — Log Files (Audit trail)

The application writes three rotating log files to `logs/` inside the backend container:

| File | Content | Retention configured |
|---|---|---|
| `logs/app.log` | General application events | 30 × 10 MB files (~300 MB) |
| `logs/audit.log` | Security events (login, data export, purge) | 90 × 10 MB files (~900 MB) |
| `logs/error.log` | Python exceptions and stack traces | 30 × 10 MB files (~300 MB) |

These files are managed by Python's `RotatingFileHandler`. They are **not** automatically backed up to external storage. See Section 4 for the recommendation.

### 2.4 Media Files

The application mounts a `media/` directory for uploaded files (logos, branding assets). These are served at `/api/v1/media/*` and `/media/*`. This directory should be backed up alongside the database.

---

## 3. Recovery Objectives

Before describing backup procedures, we define the targets that the backup system must meet:

| Metric | Definition | TABLESYS Target |
|---|---|---|
| **RPO** (Recovery Point Objective) | Maximum acceptable data loss. "How old can our most recent backup be?" | **24 hours** for database. **7 days** for logs. |
| **RTO** (Recovery Time Objective) | Maximum acceptable downtime. "How fast must we be back online?" | **4 hours** for full database restore. **30 minutes** for application restart. |

**Plain language:**
- If the database server fails at 3 PM on Tuesday, we can lose at most the changes made since 3 PM on Monday (the previous day's backup). We should be back online by 7 PM.
- If the application crashes, a restart with `docker compose up` or equivalent should take under 30 minutes.

These are conservative targets for a pre-Series-A SaaS. They can be tightened to RPO = 1 hour / RTO = 1 hour when we add continuous WAL shipping (PostgreSQL's built-in streaming replication). That upgrade is noted in Section 7.

---

## 4. Backup Procedures

### 4.1 PostgreSQL Database — Daily Full Backup

**Method:** `pg_dump` — PostgreSQL's native dump utility. Produces a portable, human-readable SQL file that can be restored to any PostgreSQL instance.

**What to run (on the database server or a backup server with access):**

```bash
#!/bin/bash
# tablesys_backup.sh
# Run daily via cron or a task scheduler.

set -euo pipefail

BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +"%Y-%m-%d_%H%M%S")
DB_NAME="tablesys"         # Replace with your actual database name
DB_USER="tablesys_user"    # Replace with your actual database user
BACKUP_FILE="${BACKUP_DIR}/tablesys_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup: $BACKUP_FILE"

# Dump and compress in one step (no intermediate uncompressed file)
PGPASSWORD="$DB_PASSWORD" pg_dump \
    -h "$DB_HOST" \
    -p "${DB_PORT:-5432}" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=plain \
    --no-owner \
    --no-acl \
    | gzip > "$BACKUP_FILE"

echo "[$(date)] Backup complete: $BACKUP_FILE ($(du -sh "$BACKUP_FILE" | cut -f1))"

# Delete backups older than RETENTION_DAYS
find "$BACKUP_DIR" -name "tablesys_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete
echo "[$(date)] Cleanup complete. Keeping last ${RETENTION_DAYS} days."
```

**Environment variables required:**
```bash
DB_HOST=<your-postgres-host>
DB_PORT=5432
DB_USER=<your-db-username>
DB_PASSWORD=<your-db-password>   # Never hardcode this
DB_NAME=tablesys
```

**Schedule:** Daily at 02:00 UTC (low-traffic window).

```
# Add to crontab (crontab -e)
0 2 * * * /opt/scripts/tablesys_backup.sh >> /var/log/tablesys_backup.log 2>&1
```

**Storage target:** The compressed backup file should be uploaded to an off-site location immediately after creation. Acceptable options:
- AWS S3 / Backblaze B2 / Wasabi (append `aws s3 cp "$BACKUP_FILE" s3://your-bucket/postgres/` to the script)
- A separate VPS in a different data centre
- A local NAS (acceptable as secondary copy only — not primary)

**Retention:** 30 days of daily backups. This covers the case where data corruption is discovered weeks after it happened.

### 4.2 Media Files — Daily Rsync

```bash
#!/bin/bash
# Sync the media directory to backup storage
rsync -avz --delete \
    /path/to/tablesys/backend/media/ \
    backup-server:/backups/media/
```

Schedule alongside the database backup.

### 4.3 Audit Logs — Weekly Archive

Audit logs rotate automatically within the container. To preserve them beyond the in-container retention window:

```bash
#!/bin/bash
# Weekly: tar and upload the current audit log
WEEK=$(date +"%Y-W%V")
tar -czf "/backups/logs/audit_${WEEK}.tar.gz" /path/to/logs/audit.log
# Upload to S3 or equivalent
```

### 4.4 Redis — Persistence Config (not a backup, but critical)

In your `redis.conf` or Docker Compose Redis config, enable AOF persistence:

```
appendonly yes
appendfsync everysec
```

This ensures Redis can recover its queue state after a crash without data loss greater than 1 second.

---

## 5. Restore Procedures

### 5.1 Full Database Restore (worst case — server destroyed)

**Scenario:** The database server is unrecoverable. We need to restore from a backup file.

**Step 1 — Provision a new PostgreSQL instance.**

This can be a managed cloud database (e.g. Supabase, AWS RDS, DigitalOcean Managed Postgres) or a self-hosted PostgreSQL 14+ instance.

**Step 2 — Download the most recent backup.**

```bash
# From S3 example:
aws s3 cp s3://your-bucket/postgres/tablesys_2026-05-05_020000.sql.gz ./restore.sql.gz

# Decompress
gunzip restore.sql.gz
```

**Step 3 — Create the database and user.**

```sql
-- Run as PostgreSQL superuser (psql)
CREATE USER tablesys_user WITH PASSWORD 'your-password';
CREATE DATABASE tablesys OWNER tablesys_user;
GRANT ALL PRIVILEGES ON DATABASE tablesys TO tablesys_user;
```

**Step 4 — Restore the dump.**

```bash
PGPASSWORD="your-password" psql \
    -h new-db-host \
    -U tablesys_user \
    -d tablesys \
    < restore.sql
```

**Step 5 — Verify schema version matches application.**

```bash
# Inside the backend container or virtualenv
cd backend
alembic current
```

The revision shown should match the head of `backend/alembic/versions/`. If the backup is from a slightly older schema version, run:

```bash
alembic upgrade head
```

**Step 6 — Update DATABASE_URL in .env and restart the application.**

```bash
# .env
DATABASE_URL=postgresql://tablesys_user:password@new-db-host:5432/tablesys

# Restart
docker compose down && docker compose up -d
```

**Step 7 — Smoke test.**

- Hit `/health` — expect `{"status": "healthy"}`.
- Log in as Superadmin.
- Confirm at least one tenant is visible.
- Confirm timetable data is present for that tenant.

**Estimated time for steps 1–7:** 2–3 hours (dominated by database provisioning and download time).

### 5.2 Partial Restore — Single Tenant Data

**Scenario:** A coordinator accidentally deletes their department structure. They want it back without restoring the entire platform.

> [!IMPORTANT]
> This procedure requires temporary downtime for the affected tenant OR a read-only query against a separate restored instance. Do NOT run destructive SQL against production without isolating the tenant first.

**Approach:**

1. Restore the backup SQL file into a **temporary** PostgreSQL database (local or staging):
   ```bash
   createdb tablesys_restore
   psql tablesys_restore < restore.sql
   ```

2. Extract the affected tenant's rows using their `university_id`:
   ```sql
   -- Example: extract departments for university_id = 7
   \COPY (SELECT * FROM departments WHERE university_id = 7) TO '/tmp/departments_uni7.csv' CSV HEADER;
   ```

3. Re-import into production after coordinator confirmation.

### 5.3 Application-Only Crash (database intact)

**Scenario:** The backend container crashes or the server reboots. The database is fine.

```bash
# Restart the application
docker compose up -d backend
# or
systemctl restart tablesys-backend

# Check health
curl http://localhost:8000/health
```

Expected recovery time: **under 5 minutes**.

---

## 6. What Is NOT Backed Up (and Why)

| What | Why not backed up |
|---|---|
| In-memory rate limiter state | Intentionally ephemeral. On restart, all IPs start with a clean counter. This is acceptable — a restarted server is less risky than a crashed one. |
| JWT tokens | Stateless by design. They expire on their own. There is no token store to back up. |
| Redis job queue (if AOF disabled) | If AOF is not enabled, pending Celery jobs since the last RDB snapshot will be lost. Mitigation: enable AOF (see Section 4.4). |
| Alembic migration scripts | These are in source control (Git), not the database. They are protected by your Git backup policy, not this one. |
| `.env` secrets | These must be stored in a **secrets manager** (Vault, AWS Secrets Manager, or at minimum a password manager like Bitwarden) independently of the backup system. If `.env` is lost and not separately stored, the `SECRET_KEY` is gone and all JWTs are invalidated — all users must log in again. |

> [!CAUTION]
> The `SECRET_KEY` in `.env` is the most critical non-database secret. If it changes or is lost, every active login session across every tenant is immediately invalidated. Store it separately from the application server.

---

## 7. Encryption at Rest — Verification Checklist

Encryption at rest means that if someone physically steals the storage disk, they cannot read the data without the decryption key.

### 7.1 Database Layer

| Platform | How to verify encryption |
|---|---|
| **AWS RDS / Aurora** | In the RDS console → Your DB instance → Configuration → `Storage encrypted: Yes`. Also visible via `aws rds describe-db-instances --query 'DBInstances[].StorageEncrypted'`. |
| **Supabase** | Supabase encrypts all databases at rest by default using AES-256. No action needed. Visible under Settings → Infrastructure. |
| **DigitalOcean Managed Postgres** | All managed databases are encrypted at rest. Visible in the database cluster settings page. |
| **Self-hosted PostgreSQL** | PostgreSQL does NOT encrypt data files by default. Encryption must come from the **filesystem or volume level** (e.g. LUKS on Linux, encrypted EBS volume on AWS). Verify with `lsblk --output NAME,FSTYPE,MOUNTPOINT,UUID` and confirm the volume is a LUKS device. |

> [!WARNING]
> If TABLESYS is running on a self-hosted PostgreSQL without OS-level disk encryption, tenant data is unencrypted on disk. This must be remediated before commercial launch. Use an encrypted volume or migrate to a managed cloud database.

### 7.2 Backup Files

Backup files (the `.sql.gz` files produced by Section 4.1) are compressed but **not encrypted** by default.

**To encrypt backup files before uploading:**

```bash
# Encrypt with AES-256 using GPG (recommended)
gpg --symmetric --cipher-algo AES256 --output "${BACKUP_FILE}.gpg" "$BACKUP_FILE"
rm "$BACKUP_FILE"  # Delete the unencrypted copy

# Store the passphrase in your secrets manager, not in the script
```

Or use server-side encryption at the storage layer (e.g. `aws s3 cp --sse AES256`).

### 7.3 Log Files

Log files at `logs/audit.log` contain security-sensitive events (login attempts, data exports, purge operations). These should be stored on an encrypted volume alongside the application.

### 7.4 Media Files

The `media/` directory contains uploaded branding assets (logos, images). These are not personally identifiable and encryption at this layer is lower priority, but should still reside on an encrypted volume in production.

---

## 8. Backup Monitoring

A backup that runs silently and fails is worse than no backup policy at all.

### 8.1 Minimum monitoring requirement

After every backup run, the script should emit a result to a monitoring channel:

```bash
# Add to the end of tablesys_backup.sh

BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
STATUS="SUCCESS"

# Check the backup is non-empty (>1KB means something was written)
if [ ! -s "$BACKUP_FILE" ] || [ $(stat -c%s "$BACKUP_FILE") -lt 1024 ]; then
    STATUS="FAILED"
fi

# Option A: POST to a Slack/Discord webhook
curl -s -X POST "$BACKUP_ALERT_WEBHOOK" \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"TABLESYS Backup [${STATUS}] — ${TIMESTAMP} — ${BACKUP_SIZE}\"}"

# Option B: Send an email (if mailx is available)
echo "TABLESYS backup ${STATUS} at ${TIMESTAMP}. Size: ${BACKUP_SIZE}" \
    | mail -s "TABLESYS Backup ${STATUS}" ops@yourcompany.com
```

### 8.2 Monthly restore test

**Once per month**, a team member should complete the following steps in order. The test is only a PASS if **every step succeeds**.

**Step 1 — Download and restore the most recent backup.**

```bash
# Download
aws s3 cp s3://your-bucket/postgres/$(aws s3 ls s3://your-bucket/postgres/ | sort | tail -1 | awk '{print $4}') ./restore.sql.gz

# Decompress
gunzip restore.sql.gz

# Create a temporary restore database (do NOT use the production DB)
createdb tablesys_restore

# Restore
psql tablesys_restore < restore.sql
```

**Step 2 — Run the automated sanity check.**

A successful `pg_restore` exit code is not enough — the backup could be structurally valid but empty. Run this query immediately after restore:

```bash
psql -h localhost -U tablesys_user -d tablesys_restore -c "
SELECT 'universities'    AS table_name, COUNT(*) AS row_count FROM universities
UNION ALL
SELECT 'users',                         COUNT(*)               FROM users
UNION ALL
SELECT 'timetable_slots',               COUNT(*)               FROM timetable_slots;
"
```

**Pass/fail rules:**

| Condition | Result |
|---|---|
| `universities` row_count = 0 | **FAIL** — backup is empty or corrupted. Do not use this backup for disaster recovery. Investigate immediately. |
| `users` row_count = 0 | **FAIL** — user accounts missing. The restore is unusable. |
| `timetable_slots` row_count = 0 | **WARN** — acceptable only if the platform has no published timetables yet. If active tenants exist, this is a **FAIL**. |
| All three return > 0 | **PASS** |

**Step 3 — Confirm schema version.**

```bash
# Check that alembic head matches what's running in production
psql -h localhost -U tablesys_user -d tablesys_restore \
    -c "SELECT version_num FROM alembic_version;"
```

This should match the output of `alembic current` in the production backend.

**Step 4 — Tear down the test database.**

```bash
dropdb tablesys_restore
```

**Step 5 — Update the document header.**

After completing the test, update the `Last verified restore test` and `Performed by` fields at the top of this document with today's date, your name, and the result (PASS or FAIL).

A backup policy that has never been tested is a false sense of security.


---

## 9. Tenant-Level Data Recovery

Beyond platform-level disaster recovery, TABLESYS provides two tenant-facing tools:

### 9.1 Data Export (self-service)

Coordinators can download all their university's data at any time via:

```
GET /api/v1/export/tenant-data
Authorization: Bearer <coordinator-token>
```

This returns a JSON file containing all departments, rooms, courses, groups, timetables, exam data, and usage summaries. This is the tenant's own copy of their data and is their primary GDPR/POPIA data portability mechanism.

### 9.2 Tenant Offboarding (Superadmin-controlled)

When a tenant churns (cancels their subscription), the following process applies:

1. **Deactivate** (`POST /api/v1/superadmin/offboard/{id}/deactivate`): Blocks all logins immediately. Reversible. Data is retained.
2. **Retention window:** 30 days from deactivation. The tenant may request data export or reactivation during this window.
3. **Purge** (`POST /api/v1/superadmin/offboard/{id}/purge`): Irreversible deletion of all tenant rows. Requires the university domain as a confirmation token. Full audit log entry written before deletion. Executed by Superadmin only.

This two-phase process ensures we never accidentally destroy a paying customer's data.

---

## 10. Incident Response — Runbook

This section gives a clear decision tree for what to do when something goes wrong.

### Incident Level 1 — Application crash (database intact)

**Symptoms:** The backend returns 502/503. `/health` is unreachable.

**Response:**
1. Check container/process logs: `docker compose logs backend --tail=100`
2. Restart: `docker compose restart backend`
3. If still down: check database connectivity (`psql -h DB_HOST -U DB_USER -d tablesys -c "SELECT 1"`)
4. If database is unreachable: escalate to Level 2.

**Target resolution time:** 30 minutes.

### Incident Level 2 — Database unreachable

**Symptoms:** Application starts but all API calls return 500. Database connection errors in logs.

**Response:**
1. Check if the database service is running: `docker compose ps db` or check your managed DB console.
2. If the database is running but unreachable, check network/firewall rules.
3. If the database service has crashed, attempt restart: `docker compose restart db`
4. If the data volume is corrupted: escalate to Level 3.

**Target resolution time:** 1–2 hours.

### Incident Level 3 — Data corruption or catastrophic failure

**Symptoms:** Database cannot start, data files are corrupt, or a mass deletion was performed accidentally.

**Response:**
1. **Do not attempt to repair the corrupted database.** Take a snapshot of the broken state for forensics.
2. Provision a new PostgreSQL instance.
3. Follow Section 5.1 — Full Database Restore.
4. Update `DATABASE_URL` and restart the application.
5. Notify all tenant coordinators via email once service is restored.
6. Write a post-mortem document within 48 hours.

**Target resolution time:** 4 hours.

### Incident Level 4 — Security breach (suspected data exfiltration)

**Symptoms:** Unusual access patterns in audit logs, a coordinator reports unauthorized data access.

**Response:**
1. **Immediately** rotate the `SECRET_KEY` in `.env` — this invalidates all active JWT sessions and forces all users to log back in.
2. Review `logs/audit.log` for the time window in question.
3. Identify the affected tenant(s) using tenant_id from the audit trail.
4. Notify affected tenants within 72 hours (GDPR requirement).
5. File an incident report.
6. Engage a security consultant if exfiltration is confirmed.

---

## 11. Roles and Responsibilities

| Who | Responsibility |
|---|---|
| **Team Leader (Dennis)** | Approve this policy. Approve retention periods. Own legal notifications to tenants in case of breach. Decide when to execute tenant purge. |
| **Antigravity / Engineering** | Implement and maintain backup scripts. Test restores monthly. Respond to Level 1–3 incidents. |
| **Superadmin account** | Execute tenant deactivation and purge operations. Monitor the Superadmin notification panel for new tenant registrations and unusual activity. |
| **Coordinators (tenants)** | Responsible for their own data exports if they need a local copy. Not responsible for platform-level backups. |

---

## 12. Open Items (Require Team Leader Decision)

> [!IMPORTANT]
> The following decisions cannot be made by engineering and require Team Leader approval before this policy is final.

| Decision | Options | Impact |
|---|---|---|
| **Off-site backup storage provider** | AWS S3, Backblaze B2, Wasabi | Determines where the backup script uploads. Low cost (~$5/month for small deployments). |
| **Tenant data retention window post-churn** | 7 days / 30 days / 90 days | How long we keep a deactivated tenant's data before purging. Longer = more storage cost, more legal exposure. |
| **Breach notification SLA** | 24h / 48h / 72h | GDPR requires 72h to supervisory authority. Tenant notification is separate — how fast? |
| **Self-hosted vs managed database** | Self-hosted PostgreSQL / Supabase / AWS RDS | Determines encryption-at-rest strategy and operational overhead. |
| **Backup encryption passphrase management** | GPG key in Bitwarden / AWS KMS / HashiCorp Vault | Required before backup files contain encrypted data. |

---

## 13. Summary — What We Have Today vs What We Need

| Item | Status | Gap |
|---|---|---|
| Daily database backup script | 📋 Written in this doc — needs deployment | Deploy and schedule cron |
| Off-site backup storage | ❌ Not configured | Team Leader to select provider |
| Media file backup | 📋 Written in this doc — needs deployment | Deploy rsync script |
| Audit log archiving | 📋 Written in this doc — needs deployment | Deploy weekly archive |
| Redis persistence (AOF) | ❌ Not verified | Add `appendonly yes` to Redis config |
| Database encryption at rest | ❓ Depends on hosting choice | Verify per Section 7.1 |
| Backup file encryption | ❌ Not implemented | Add GPG step to backup script |
| Monthly restore test process | 📋 Defined in Section 8.2 — needs calendar entry | Team Leader to assign owner |
| Tenant data export endpoint | ✅ Implemented | None — live and tested |
| Tenant offboarding pipeline | ✅ Implemented | None — live and tested |

---

*End of document. Version 1.0 — 2026-05-05. Requires Team Leader sign-off before client distribution.*
