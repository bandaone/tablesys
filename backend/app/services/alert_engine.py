"""
AlertEngine — evaluates all platform monitoring thresholds and persists
PlatformAlert records. Designed to be called by a Celery beat task and
also on-demand via the alerts API endpoint.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import redis as redis_lib
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuditLog, PlatformAlert, University, User

# ── Threshold constants ────────────────────────────────────────────────────────
CPU_CRITICAL = 85.0
MEM_CRITICAL = 85.0
DISK_CRITICAL = 92.0
PLATFORM_ERROR_RATE_WARN = 3.0
PLATFORM_ERROR_RATE_CRIT = 8.0
PLATFORM_AVG_RESP_WARN = 2000   # ms
GEN_SUCCESS_RATE_CRIT = 70.0    # %
SLA_COMPLIANCE_CRIT = 90.0      # %
AUTH_FAIL_THRESHOLD = 5         # failures from same IP in 10 min
DELETE_SPIKE_THRESHOLD = 10     # deletes in 5 min


class AlertEngine:
    def __init__(self, db: Session):
        self.db = db
        self._now = datetime.now(timezone.utc)
        try:
            self._redis = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            self._redis = None

    # ── Public entry point ─────────────────────────────────────────────────────
    def run(self) -> list[PlatformAlert]:
        """Evaluate all alert rules. Returns list of newly fired alerts."""
        candidates = []

        try:
            telemetry = self._get_telemetry()
            candidates += self._check_infra(telemetry)
        except Exception:
            pass

        try:
            candidates += self._check_tenant_health()
        except Exception:
            pass

        try:
            candidates += self._check_security_audit()
        except Exception:
            pass

        fired = self._persist_and_dedup(candidates)
        self._auto_resolve(candidates)
        if fired and self._redis:
            self._broadcast(fired)
        return fired

    # ── Telemetry (mirrors SystemMonitorPage logic) ────────────────────────────
    def _get_telemetry(self) -> dict[str, Any]:
        import psutil
        import redis as redis_lib
        redis_status = "offline"
        try:
            r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            r.ping()
            redis_status = "online"
        except Exception:
            pass

        try:
            db_status = "online"
            self.db.execute(__import__("sqlalchemy").text("SELECT 1"))
        except Exception:
            db_status = "offline"

        return {
            "cpu": psutil.cpu_percent(interval=0.5),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage("/").percent,
            "redis": redis_status,
            "db": db_status,
        }

    def _check_infra(self, t: dict) -> list[dict]:
        alerts = []
        if t["redis"] != "online":
            alerts.append(self._make("critical", "infra", "Redis Offline",
                "The Redis broker is unreachable. Background jobs and real-time features are degraded.",
                "infra:redis_offline", auto_resolve=True))
        if t["db"] != "online":
            alerts.append(self._make("critical", "infra", "Database Offline",
                "PostgreSQL is unreachable. All data operations will fail.",
                "infra:db_offline", auto_resolve=True))
        if t["cpu"] > CPU_CRITICAL:
            alerts.append(self._make("critical", "infra", f"CPU Critical ({t['cpu']:.0f}%)",
                f"Host CPU usage exceeded {CPU_CRITICAL}%. Solver and API performance may degrade.",
                "infra:cpu_high", auto_resolve=True))
        if t["memory"] > MEM_CRITICAL:
            alerts.append(self._make("critical", "infra", f"Memory Critical ({t['memory']:.0f}%)",
                f"Host memory usage exceeded {MEM_CRITICAL}%.",
                "infra:memory_high", auto_resolve=True))
        if t["disk"] > DISK_CRITICAL:
            alerts.append(self._make("critical", "infra", f"Disk Critical ({t['disk']:.0f}%)",
                f"Disk usage exceeded {DISK_CRITICAL}%. Uploads and artifact storage may fail.",
                "infra:disk_high", auto_resolve=True))
        return alerts

    def _check_tenant_health(self) -> list[dict]:
        from ..services.tenant_performance_service import TenantPerformanceService
        alerts = []
        svc = TenantPerformanceService(self.db)
        overview = svc.get_platform_performance_overview(window_days=1)

        summary = overview.get("summary", {})
        if summary.get("platform_error_rate_percent", 0) > PLATFORM_ERROR_RATE_CRIT:
            alerts.append(self._make("critical", "tenant",
                f"Platform Error Rate Critical ({summary['platform_error_rate_percent']:.1f}%)",
                f"Platform-wide API error rate exceeded {PLATFORM_ERROR_RATE_CRIT}%.",
                "tenant:platform_error_rate_critical", auto_resolve=True))
        elif summary.get("platform_error_rate_percent", 0) > PLATFORM_ERROR_RATE_WARN:
            alerts.append(self._make("warning", "tenant",
                f"Platform Error Rate Elevated ({summary['platform_error_rate_percent']:.1f}%)",
                f"Platform-wide API error rate is above {PLATFORM_ERROR_RATE_WARN}%.",
                "tenant:platform_error_rate_warning", auto_resolve=True))

        if summary.get("platform_avg_response_ms", 0) > PLATFORM_AVG_RESP_WARN:
            alerts.append(self._make("warning", "tenant",
                f"High Average Response Time ({summary['platform_avg_response_ms']:.0f}ms)",
                "Platform average API response time is above 2000ms.",
                "tenant:avg_response_high", auto_resolve=True))

        for tenant in overview.get("tenants", []):
            key_prefix = f"tenant:{tenant['tenant_id']}"
            if tenant.get("health_status") == "critical":
                alerts.append(self._make("critical", "tenant",
                    f"{tenant['tenant_name']} — Health Critical",
                    f"Error rate: {tenant['error_rate_percent']:.1f}%, Avg resp: {tenant['avg_response_ms']:.0f}ms",
                    f"{key_prefix}:health_critical",
                    tenant_id=tenant["tenant_id"], tenant_name=tenant["tenant_name"],
                    auto_resolve=True))
            elif tenant.get("health_status") == "warning":
                alerts.append(self._make("warning", "tenant",
                    f"{tenant['tenant_name']} — Health Warning",
                    f"Error rate: {tenant['error_rate_percent']:.1f}%, SLA compliance: {tenant['sla_compliance_percent']:.1f}%",
                    f"{key_prefix}:health_warning",
                    tenant_id=tenant["tenant_id"], tenant_name=tenant["tenant_name"],
                    auto_resolve=True))

            gen_rate = tenant.get("generation_success_rate_percent")
            gen_attempts = tenant.get("generation_attempts", 0)
            if gen_rate is not None and gen_rate < GEN_SUCCESS_RATE_CRIT and gen_attempts >= 3:
                alerts.append(self._make("critical", "tenant",
                    f"{tenant['tenant_name']} — Timetable Generation Failing ({gen_rate:.0f}%)",
                    f"Only {gen_rate:.0f}% of {gen_attempts} generation attempts succeeded.",
                    f"{key_prefix}:gen_failure",
                    tenant_id=tenant["tenant_id"], tenant_name=tenant["tenant_name"],
                    auto_resolve=True))

        return alerts

    def _check_security_audit(self) -> list[dict]:
        alerts = []
        window_10m = self._now - timedelta(minutes=10)
        window_5m = self._now - timedelta(minutes=5)

        # Auth failure spike per IP
        recent_logins = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.action == "LOGIN",
                AuditLog.status == "failure",
                AuditLog.timestamp >= window_10m,
            )
            .all()
        )
        ip_failures: dict[str, int] = defaultdict(int)
        for log in recent_logins:
            if log.ip_address:
                ip_failures[log.ip_address] += 1
        for ip, count in ip_failures.items():
            if count >= AUTH_FAIL_THRESHOLD:
                alerts.append(self._make("warning", "security",
                    f"Auth Brute-Force Detected — {ip}",
                    f"{count} failed login attempts from {ip} in the last 10 minutes.",
                    f"security:auth_bruteforce:{ip}", auto_resolve=False))

        # DELETE spike
        recent_deletes = (
            self.db.query(AuditLog)
            .filter(AuditLog.action == "DELETE", AuditLog.timestamp >= window_5m)
            .count()
        )
        if recent_deletes >= DELETE_SPIKE_THRESHOLD:
            alerts.append(self._make("warning", "security",
                f"Unusual DELETE Spike ({recent_deletes} in 5 min)",
                "A high volume of DELETE operations was detected in the last 5 minutes.",
                "security:delete_spike", auto_resolve=True))

        # Impersonation events
        recent_impersonate = (
            self.db.query(AuditLog)
            .filter(AuditLog.action == "IMPERSONATE", AuditLog.timestamp >= window_10m)
            .count()
        )
        if recent_impersonate > 0:
            alerts.append(self._make("info", "security",
                f"Superadmin Impersonation ({recent_impersonate} event(s))",
                "A superadmin performed tenant impersonation in the last 10 minutes.",
                "security:impersonation", auto_resolve=True))

        return alerts

    # ── Persistence & deduplication ────────────────────────────────────────────
    def _make(
        self,
        severity: str,
        category: str,
        title: str,
        detail: str,
        alert_key: str,
        tenant_id: int | None = None,
        tenant_name: str | None = None,
        auto_resolve: bool = True,
    ) -> dict:
        return dict(severity=severity, category=category, title=title, detail=detail,
                    alert_key=alert_key, tenant_id=tenant_id, tenant_name=tenant_name,
                    auto_resolve=auto_resolve)

    def _persist_and_dedup(self, candidates: list[dict]) -> list[PlatformAlert]:
        """Persist new alerts; skip if an unresolved alert with same key already exists."""
        fired: list[PlatformAlert] = []
        candidate_keys = {c["alert_key"] for c in candidates}

        existing = {
            row.alert_key: row
            for row in self.db.query(PlatformAlert)
            .filter(PlatformAlert.resolved_at.is_(None))
            .filter(PlatformAlert.alert_key.in_(list(candidate_keys) or ["__none__"]))
            .all()
        }

        for c in candidates:
            if c["alert_key"] in existing:
                continue  # Already active — skip
            alert = PlatformAlert(
                severity=c["severity"],
                category=c["category"],
                title=c["title"],
                detail=c["detail"],
                alert_key=c["alert_key"],
                tenant_id=c.get("tenant_id"),
                tenant_name=c.get("tenant_name"),
                triggered_at=self._now,
                auto_resolve=c.get("auto_resolve", True),
            )
            self.db.add(alert)
            fired.append(alert)

        if fired:
            self.db.commit()
            for a in fired:
                self.db.refresh(a)
        return fired

    def _auto_resolve(self, active_candidates: list[dict]) -> None:
        """Resolve alerts whose conditions have cleared."""
        active_keys = {c["alert_key"] for c in active_candidates}
        stale = (
            self.db.query(PlatformAlert)
            .filter(
                PlatformAlert.resolved_at.is_(None),
                PlatformAlert.auto_resolve.is_(True),
                PlatformAlert.alert_key.notin_(list(active_keys) or ["__none__"]),
            )
            .all()
        )
        for alert in stale:
            alert.resolved_at = self._now
        if stale:
            self.db.commit()

    def _broadcast(self, alerts: list[PlatformAlert]) -> None:
        """Push new alerts to the existing Redis audit_stream channel."""
        if not self._redis:
            return
        for alert in alerts:
            payload = {
                "type": "platform_alert",
                "id": alert.id,
                "severity": alert.severity,
                "category": alert.category,
                "title": alert.title,
                "detail": alert.detail,
                "tenant_name": alert.tenant_name,
                "triggered_at": alert.triggered_at.isoformat(),
            }
            try:
                self._redis.publish("audit_stream", json.dumps(payload))
            except Exception:
                pass
