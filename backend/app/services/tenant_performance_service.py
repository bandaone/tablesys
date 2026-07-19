from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models import Timetable, University, UsageEvent


API_METRIC_KEYS = {
    "requests": "api_requests_total",
    "server_errors": "api_server_errors_total",
    "client_errors": "api_client_errors_total",
    "response_time_ms": "api_response_time_ms",
    "sla_breaches": "api_sla_breaches_total",
}

GENERATION_METRIC_KEYS = {
    "attempts": "timetable_generation_attempts",
    "successes": "timetable_generation_successes",
    "failures": "timetable_generation_failures",
    "duration_ms": "timetable_generation_duration_ms",
    "fallback_runs": "timetable_generation_fallback_runs",
    "timeout_runs": "timetable_generation_timeout_runs",
}

SLA_TARGETS_MS = {
    "free": 2500,
    "starter": 2500,
    "pro": 1800,
    "professional": 1800,
    "enterprise": 1200,
}


class TenantPerformanceService:
    def __init__(self, db: Session):
        self.db = db

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _start_for_window(self, window_days: int) -> datetime:
        return self._now() - timedelta(days=window_days)

    def _plan_sla_ms(self, plan_tier: str) -> int:
        return SLA_TARGETS_MS.get((plan_tier or "free").lower(), 2500)

    def _health_status(
        self,
        *,
        requests: int,
        avg_response_ms: float,
        sla_target_ms: int,
        error_rate_percent: float,
        generation_success_rate_percent: float | None,
    ) -> str:
        if requests == 0:
            return "quiet"
        if error_rate_percent > 8 or avg_response_ms > (sla_target_ms * 1.35):
            return "critical"
        if (
            error_rate_percent > 3
            or avg_response_ms > sla_target_ms
            or (generation_success_rate_percent is not None and generation_success_rate_percent < 75)
        ):
            return "warning"
        return "healthy"

    def get_platform_performance_overview(self, window_days: int = 30) -> dict[str, Any]:
        window_start = self._start_for_window(window_days)
        universities = self.db.query(University).order_by(University.name.asc()).all()
        university_map = {uni.id: uni for uni in universities}

        all_metric_keys = list(API_METRIC_KEYS.values()) + list(GENERATION_METRIC_KEYS.values())
        usage_events = (
            self.db.query(UsageEvent)
            .filter(UsageEvent.tenant_id.in_(list(university_map.keys()) or [-1]))
            .filter(UsageEvent.occurred_at >= window_start)
            .filter(UsageEvent.metric_key.in_(all_metric_keys))
            .all()
        )

        totals_by_tenant: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        failure_patterns_by_tenant: dict[int, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {"count": 0, "statuses": set()}))

        for event in usage_events:
            totals_by_tenant[event.tenant_id][event.metric_key] += int(event.quantity or 0)
            if event.metric_key in {API_METRIC_KEYS["server_errors"], API_METRIC_KEYS["client_errors"]}:
                metadata = event.metadata_json or {}
                endpoint = metadata.get("endpoint_route") or "unknown"
                failure_patterns_by_tenant[event.tenant_id][endpoint]["count"] += int(event.quantity or 0)
                if metadata.get("status_code") is not None:
                    failure_patterns_by_tenant[event.tenant_id][endpoint]["statuses"].add(int(metadata["status_code"]))

        timetables = self.db.query(Timetable).filter(Timetable.university_id.in_(list(university_map.keys()) or [-1])).all()
        recent_runs_by_tenant: dict[int, list[dict[str, Any]]] = defaultdict(list)
        timetable_status_by_tenant: dict[int, dict[str, int]] = defaultdict(lambda: {"generated": 0, "draft": 0})

        for timetable in timetables:
            meta = dict(timetable.generation_metadata or {})
            if meta.get("generated"):
                timetable_status_by_tenant[timetable.university_id]["generated"] += 1
            else:
                timetable_status_by_tenant[timetable.university_id]["draft"] += 1

            status = meta.get("generation_status")
            if not status:
                continue

            recent_runs_by_tenant[timetable.university_id].append(
                {
                    "timetable_id": timetable.id,
                    "timetable_name": timetable.name,
                    "status": status,
                    "completed_at": meta.get("last_generation_completed_at"),
                    "duration_ms": meta.get("last_generation_duration_ms"),
                    "saved_slot_count": int(meta.get("last_generation_saved_slot_count") or 0),
                    "fallback_used": bool(meta.get("last_generation_fallback_used")),
                    "error_message": meta.get("last_generation_error_message"),
                }
            )

        tenants: list[dict[str, Any]] = []
        total_requests = 0
        total_errors = 0
        total_duration_ms = 0
        tenants_meeting_sla = 0

        for tenant_id, uni in university_map.items():
            tenant_totals = totals_by_tenant.get(tenant_id, {})
            plan_tier = uni.plan_tier or "free"
            sla_target_ms = self._plan_sla_ms(plan_tier)
            requests = int(tenant_totals.get(API_METRIC_KEYS["requests"], 0))
            server_errors = int(tenant_totals.get(API_METRIC_KEYS["server_errors"], 0))
            client_errors = int(tenant_totals.get(API_METRIC_KEYS["client_errors"], 0))
            total_error_count = server_errors + client_errors
            response_time_ms_total = int(tenant_totals.get(API_METRIC_KEYS["response_time_ms"], 0))
            sla_breaches = int(tenant_totals.get(API_METRIC_KEYS["sla_breaches"], 0))

            attempts = int(tenant_totals.get(GENERATION_METRIC_KEYS["attempts"], 0))
            successes = int(tenant_totals.get(GENERATION_METRIC_KEYS["successes"], 0))
            failures = int(tenant_totals.get(GENERATION_METRIC_KEYS["failures"], 0))
            generation_duration_ms = int(tenant_totals.get(GENERATION_METRIC_KEYS["duration_ms"], 0))
            fallback_runs = int(tenant_totals.get(GENERATION_METRIC_KEYS["fallback_runs"], 0))
            timeout_runs = int(tenant_totals.get(GENERATION_METRIC_KEYS["timeout_runs"], 0))

            avg_response_ms = round(response_time_ms_total / requests, 2) if requests else 0.0
            error_rate_percent = round((total_error_count / requests) * 100, 2) if requests else 0.0
            sla_compliance_percent = round(((requests - sla_breaches) / requests) * 100, 2) if requests else 100.0
            generation_success_rate_percent = round((successes / attempts) * 100, 2) if attempts else None
            generation_avg_duration_ms = round(generation_duration_ms / attempts, 2) if attempts else None
            health_status = self._health_status(
                requests=requests,
                avg_response_ms=avg_response_ms,
                sla_target_ms=sla_target_ms,
                error_rate_percent=error_rate_percent,
                generation_success_rate_percent=generation_success_rate_percent,
            )

            endpoint_patterns = failure_patterns_by_tenant.get(tenant_id, {})
            top_failure_endpoints = [
                {
                    "endpoint": endpoint,
                    "count": payload["count"],
                    "status_codes": sorted(payload["statuses"]),
                }
                for endpoint, payload in sorted(
                    endpoint_patterns.items(),
                    key=lambda item: item[1]["count"],
                    reverse=True,
                )[:5]
            ]

            recent_runs = sorted(
                recent_runs_by_tenant.get(tenant_id, []),
                key=lambda run: run.get("completed_at") or "",
                reverse=True,
            )[:3]

            if requests > 0 and avg_response_ms <= sla_target_ms and error_rate_percent <= 3:
                tenants_meeting_sla += 1

            total_requests += requests
            total_errors += total_error_count
            total_duration_ms += response_time_ms_total

            tenants.append(
                {
                    "tenant_id": tenant_id,
                    "tenant_name": uni.name,
                    "domain": uni.domain,
                    "plan_tier": plan_tier,
                    "requests": requests,
                    "server_errors": server_errors,
                    "client_errors": client_errors,
                    "error_rate_percent": error_rate_percent,
                    "avg_response_ms": avg_response_ms,
                    "sla_target_ms": sla_target_ms,
                    "sla_breaches": sla_breaches,
                    "sla_compliance_percent": sla_compliance_percent,
                    "generation_attempts": attempts,
                    "generation_success_rate_percent": generation_success_rate_percent,
                    "generation_avg_duration_ms": generation_avg_duration_ms,
                    "generation_failures": failures,
                    "generation_fallback_runs": fallback_runs,
                    "generation_timeout_runs": timeout_runs,
                    "generated_timetables": timetable_status_by_tenant[tenant_id]["generated"],
                    "draft_timetables": timetable_status_by_tenant[tenant_id]["draft"],
                    "health_status": health_status,
                    "top_failure_endpoints": top_failure_endpoints,
                    "recent_generation_runs": recent_runs,
                }
            )

        tenants.sort(
            key=lambda tenant: (
                {"critical": 0, "warning": 1, "healthy": 2, "quiet": 3}.get(tenant["health_status"], 4),
                tenant["error_rate_percent"] * -1,
                tenant["avg_response_ms"] * -1,
            )
        )

        top_failure_endpoints_platform: dict[str, int] = defaultdict(int)
        for tenant in tenants:
            for endpoint in tenant["top_failure_endpoints"]:
                top_failure_endpoints_platform[endpoint["endpoint"]] += int(endpoint["count"])

        return {
            "window_days": window_days,
            "generated_at": self._now().isoformat(),
            "summary": {
                "tenant_count": len(universities),
                "active_tenants": len([tenant for tenant in tenants if tenant["requests"] > 0 or tenant["generation_attempts"] > 0]),
                "tenants_meeting_sla": tenants_meeting_sla,
                "platform_avg_response_ms": round(total_duration_ms / total_requests, 2) if total_requests else 0.0,
                "platform_error_rate_percent": round((total_errors / total_requests) * 100, 2) if total_requests else 0.0,
                "platform_generation_success_rate_percent": round(
                    (
                        sum((tenant["generation_success_rate_percent"] or 0) * tenant["generation_attempts"] for tenant in tenants)
                        / max(sum(tenant["generation_attempts"] for tenant in tenants), 1)
                    ),
                    2,
                ) if any(tenant["generation_attempts"] for tenant in tenants) else 0.0,
                "at_risk_tenants": len([tenant for tenant in tenants if tenant["health_status"] in {"critical", "warning"}]),
            },
            "top_failure_endpoints": [
                {"endpoint": endpoint, "count": count}
                for endpoint, count in sorted(top_failure_endpoints_platform.items(), key=lambda item: item[1], reverse=True)[:8]
            ],
            "tenants": tenants,
        }
