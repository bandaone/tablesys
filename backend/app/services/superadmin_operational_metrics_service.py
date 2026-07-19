from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from ..models import ExamPeriod, Timetable, TimetableVersion, University, UsageEvent, UsageMonthlySummary, User
from ..utils.conflict_detector import ConflictDetector


SOLVER_METRIC_KEYS = {
    "attempts": "timetable_generation_attempts",
    "successes": "timetable_generation_successes",
    "failures": "timetable_generation_failures",
    "fallback_runs": "timetable_generation_fallback_runs",
    "timeout_runs": "timetable_generation_timeout_runs",
}


class SuperAdminOperationalMetricsService:
    def __init__(self, db: Session):
        self.db = db
        self.conflict_detector = ConflictDetector(db)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _window_start(self, window_days: int) -> datetime:
        return self._now() - timedelta(days=window_days)

    def _parse_timestamp(self, raw_value: str | None) -> datetime | None:
        if not raw_value:
            return None
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _normalize_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _serialize_size(self, payload: Any) -> int:
        if payload is None:
            return 0
        try:
            return len(json.dumps(payload, default=str, sort_keys=True))
        except (TypeError, ValueError):
            return len(str(payload))

    def _estimate_timetable_storage(self, timetable: Timetable) -> int:
        return (
            len(timetable.name or "")
            + len(timetable.semester or "")
            + len(timetable.academic_half or "")
            + self._serialize_size(timetable.generation_metadata)
        )

    def _estimate_version_storage(self, version: TimetableVersion) -> int:
        return len(version.description or "") + self._serialize_size(version.snapshot_data)

    def _estimate_usage_event_storage(self, event: UsageEvent) -> int:
        return (
            len(event.metric_key or "")
            + len(event.source or "")
            + self._serialize_size(event.metadata_json)
            + 16
        )

    def _estimate_usage_summary_storage(self, summary: UsageMonthlySummary) -> int:
        return len(summary.metric_key or "") + 24

    def _estimate_exam_period_storage(self, period: ExamPeriod) -> int:
        return (
            len(period.name or "")
            + len(period.semester or "")
            + self._serialize_size(period.constraint_settings)
            + self._serialize_size(period.generation_metadata)
        )

    def _audit_log_paths(self) -> list[Path]:
        candidates = [
            Path("logs/audit.log"),
            Path(__file__).resolve().parents[2] / "logs" / "audit.log",
            Path(__file__).resolve().parents[3] / "logs" / "audit.log",
        ]
        unique_paths: list[Path] = []
        seen: set[str] = set()
        for path in candidates:
            key = str(path)
            if key not in seen:
                seen.add(key)
                unique_paths.append(path)
        return unique_paths

    def _read_rate_limit_events(
        self,
        *,
        window_start: datetime,
        username_tenant_map: dict[str, int],
    ) -> dict[int, dict[str, Any]]:
        rate_limit_by_tenant: dict[int, dict[str, Any]] = defaultdict(
            lambda: {
                "hit_count": 0,
                "last_hit_at": None,
                "usernames": set(),
                "endpoint_counts": defaultdict(int),
            }
        )

        for path in self._audit_log_paths():
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            payload = json.loads(line.strip())
                        except json.JSONDecodeError:
                            continue

                        if str(payload.get("event_type") or "") != "RATE_LIMIT_BLOCK":
                            continue

                        timestamp = self._parse_timestamp(payload.get("timestamp"))
                        if not timestamp or timestamp < window_start:
                            continue

                        username = str(payload.get("username") or "").strip().lower()
                        if not username:
                            continue

                        tenant_id = username_tenant_map.get(username)
                        if tenant_id is None:
                            continue

                        resource = str(payload.get("resource") or "unknown")
                        details = rate_limit_by_tenant[tenant_id]
                        details["hit_count"] += 1
                        details["usernames"].add(username)
                        details["endpoint_counts"][resource] += 1
                        if details["last_hit_at"] is None or timestamp > details["last_hit_at"]:
                            details["last_hit_at"] = timestamp
            except OSError:
                continue

        return rate_limit_by_tenant

    def _build_storage_buckets(
        self,
        *,
        now: datetime,
        window_days: int,
    ) -> tuple[list[dict[str, Any]], list[datetime]]:
        bucket_count = 6
        bucket_span_days = max(1, window_days // bucket_count)
        bucket_span = timedelta(days=bucket_span_days)
        start = now - bucket_span * bucket_count

        buckets: list[dict[str, Any]] = []
        edges: list[datetime] = []
        cursor = start
        for _ in range(bucket_count):
            edges.append(cursor)
            bucket_end = cursor + bucket_span
            buckets.append(
                {
                    "label": f"{cursor.strftime('%b %d')} - {(bucket_end - timedelta(days=1)).strftime('%b %d')}",
                    "start": cursor,
                    "end": bucket_end,
                }
            )
            cursor = bucket_end
        edges.append(cursor)
        return buckets, edges

    def _bucket_index_for(self, timestamp: datetime | None, edges: list[datetime]) -> int | None:
        ts = self._normalize_datetime(timestamp)
        if ts is None:
            return None
        for idx in range(len(edges) - 1):
            if edges[idx] <= ts < edges[idx + 1]:
                return idx
        if ts == edges[-1]:
            return len(edges) - 2
        return None

    def get_operational_metrics_overview(self, window_days: int = 30) -> dict[str, Any]:
        now = self._now()
        window_start = self._window_start(window_days)
        previous_window_start = now - timedelta(days=window_days * 2)

        universities = self.db.query(University).order_by(University.name.asc()).all()
        university_map = {tenant.id: tenant for tenant in universities}

        users = self.db.query(User.username, User.university_id).filter(User.university_id.isnot(None)).all()
        username_tenant_map = {
            str(username).lower(): tenant_id
            for username, tenant_id in users
            if username and tenant_id is not None
        }

        solver_events = (
            self.db.query(UsageEvent)
            .filter(UsageEvent.tenant_id.in_(list(university_map.keys()) or [-1]))
            .filter(UsageEvent.occurred_at >= window_start)
            .filter(UsageEvent.metric_key.in_(list(SOLVER_METRIC_KEYS.values())))
            .all()
        )

        solver_totals_by_tenant: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for event in solver_events:
            solver_totals_by_tenant[event.tenant_id][event.metric_key] += int(event.quantity or 0)

        rate_limit_by_tenant = self._read_rate_limit_events(
            window_start=window_start,
            username_tenant_map=username_tenant_map,
        )

        timetables = self.db.query(Timetable).filter(Timetable.university_id.in_(list(university_map.keys()) or [-1])).all()

        conflict_rows: list[dict[str, Any]] = []
        conflict_summary_counts = {
            "evaluated": 0,
            "conflict_free": 0,
            "total_conflicts": 0,
        }

        for tenant in universities:
            tenant_timetables = [item for item in timetables if item.university_id == tenant.id]
            evaluated_runs = 0
            conflict_free_runs = 0
            unresolved_runs = 0
            total_conflicts = 0
            top_conflict_type = None
            top_conflict_count = 0

            for timetable in tenant_timetables:
                meta = dict(timetable.generation_metadata or {})
                if str(meta.get("generation_status") or "").lower() != "success":
                    continue
                completed_at = self._parse_timestamp(meta.get("last_generation_completed_at"))
                if not completed_at or completed_at < window_start:
                    continue

                summary = self.conflict_detector.get_conflict_summary(timetable.id)
                evaluated_runs += 1
                total_conflicts += int(summary.get("total_conflicts") or 0)
                if int(summary.get("total_conflicts") or 0) == 0:
                    conflict_free_runs += 1
                else:
                    unresolved_runs += 1

                by_type = summary.get("by_type") or {}
                for conflict_type, count in by_type.items():
                    if int(count or 0) > top_conflict_count:
                        top_conflict_type = conflict_type
                        top_conflict_count = int(count or 0)

            conflict_summary_counts["evaluated"] += evaluated_runs
            conflict_summary_counts["conflict_free"] += conflict_free_runs
            conflict_summary_counts["total_conflicts"] += total_conflicts

            conflict_rows.append(
                {
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "plan_tier": tenant.plan_tier or "free",
                    "evaluated_runs": evaluated_runs,
                    "conflict_free_runs": conflict_free_runs,
                    "unresolved_runs": unresolved_runs,
                    "conflict_free_rate_percent": round((conflict_free_runs / evaluated_runs) * 100, 2) if evaluated_runs else None,
                    "total_conflicts": total_conflicts,
                    "top_conflict_type": top_conflict_type,
                }
            )

        conflict_rows.sort(
            key=lambda item: (
                item["conflict_free_rate_percent"] if item["conflict_free_rate_percent"] is not None else -1,
                -item["evaluated_runs"],
                item["tenant_name"],
            ),
            reverse=True,
        )

        version_rows = self.db.query(TimetableVersion).all()
        exam_periods = self.db.query(ExamPeriod).filter(ExamPeriod.university_id.in_(list(university_map.keys()) or [-1])).all()
        usage_events_for_storage = self.db.query(UsageEvent).filter(UsageEvent.tenant_id.in_(list(university_map.keys()) or [-1])).all()
        usage_summaries = self.db.query(UsageMonthlySummary).filter(UsageMonthlySummary.tenant_id.in_(list(university_map.keys()) or [-1])).all()

        current_storage_by_tenant: dict[int, int] = defaultdict(int)
        storage_added_window_by_tenant: dict[int, int] = defaultdict(int)
        storage_added_previous_window_by_tenant: dict[int, int] = defaultdict(int)

        buckets, bucket_edges = self._build_storage_buckets(now=now, window_days=window_days)
        bucket_rows = [
            {
                "label": bucket["label"],
                "total_bytes_added": 0,
                "top_tenant_name": None,
                "top_tenant_bytes": 0,
            }
            for bucket in buckets
        ]
        bucket_tenant_totals: list[dict[int, int]] = [defaultdict(int) for _ in buckets]

        for timetable in timetables:
            size = self._estimate_timetable_storage(timetable)
            current_storage_by_tenant[timetable.university_id] += size

            completed_at = self._parse_timestamp((timetable.generation_metadata or {}).get("last_generation_completed_at"))
            if completed_at and completed_at >= window_start:
                storage_added_window_by_tenant[timetable.university_id] += size
            elif completed_at and previous_window_start <= completed_at < window_start:
                storage_added_previous_window_by_tenant[timetable.university_id] += size

            bucket_index = self._bucket_index_for(completed_at, bucket_edges)
            if bucket_index is not None:
                bucket_rows[bucket_index]["total_bytes_added"] += size
                bucket_tenant_totals[bucket_index][timetable.university_id] += size

        for version in version_rows:
            timetable = next((item for item in timetables if item.id == version.timetable_id), None)
            if timetable is None:
                continue
            size = self._estimate_version_storage(version)
            tenant_id = timetable.university_id
            current_storage_by_tenant[tenant_id] += size

            created_at = self._normalize_datetime(version.created_at)
            if created_at and created_at >= window_start:
                storage_added_window_by_tenant[tenant_id] += size
            elif created_at and previous_window_start <= created_at < window_start:
                storage_added_previous_window_by_tenant[tenant_id] += size

            bucket_index = self._bucket_index_for(created_at, bucket_edges)
            if bucket_index is not None:
                bucket_rows[bucket_index]["total_bytes_added"] += size
                bucket_tenant_totals[bucket_index][tenant_id] += size

        for period in exam_periods:
            size = self._estimate_exam_period_storage(period)
            current_storage_by_tenant[period.university_id] += size

            created_at = self._normalize_datetime(period.created_at)
            if created_at and created_at >= window_start:
                storage_added_window_by_tenant[period.university_id] += size
            elif created_at and previous_window_start <= created_at < window_start:
                storage_added_previous_window_by_tenant[period.university_id] += size

            bucket_index = self._bucket_index_for(created_at, bucket_edges)
            if bucket_index is not None:
                bucket_rows[bucket_index]["total_bytes_added"] += size
                bucket_tenant_totals[bucket_index][period.university_id] += size

        for event in usage_events_for_storage:
            size = self._estimate_usage_event_storage(event)
            current_storage_by_tenant[event.tenant_id] += size

            occurred_at = self._normalize_datetime(event.occurred_at)
            if occurred_at and occurred_at >= window_start:
                storage_added_window_by_tenant[event.tenant_id] += size
            elif occurred_at and previous_window_start <= occurred_at < window_start:
                storage_added_previous_window_by_tenant[event.tenant_id] += size

            bucket_index = self._bucket_index_for(occurred_at, bucket_edges)
            if bucket_index is not None:
                bucket_rows[bucket_index]["total_bytes_added"] += size
                bucket_tenant_totals[bucket_index][event.tenant_id] += size

        for summary in usage_summaries:
            size = self._estimate_usage_summary_storage(summary)
            current_storage_by_tenant[summary.tenant_id] += size

            updated_at = self._normalize_datetime(summary.updated_at)
            if updated_at and updated_at >= window_start:
                storage_added_window_by_tenant[summary.tenant_id] += size
            elif updated_at and previous_window_start <= updated_at < window_start:
                storage_added_previous_window_by_tenant[summary.tenant_id] += size

            bucket_index = self._bucket_index_for(updated_at, bucket_edges)
            if bucket_index is not None:
                bucket_rows[bucket_index]["total_bytes_added"] += size
                bucket_tenant_totals[bucket_index][summary.tenant_id] += size

        for idx, tenant_totals in enumerate(bucket_tenant_totals):
            if not tenant_totals:
                continue
            top_tenant_id, top_tenant_bytes = max(tenant_totals.items(), key=lambda item: item[1])
            bucket_rows[idx]["top_tenant_name"] = university_map.get(top_tenant_id).name if top_tenant_id in university_map else None
            bucket_rows[idx]["top_tenant_bytes"] = top_tenant_bytes

        storage_rows: list[dict[str, Any]] = []
        for tenant in universities:
            current_storage = int(current_storage_by_tenant.get(tenant.id, 0))
            current_growth = int(storage_added_window_by_tenant.get(tenant.id, 0))
            previous_growth = int(storage_added_previous_window_by_tenant.get(tenant.id, 0))
            growth_percent = None
            if previous_growth > 0:
                growth_percent = round(((current_growth - previous_growth) / previous_growth) * 100, 2)

            storage_rows.append(
                {
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "plan_tier": tenant.plan_tier or "free",
                    "current_estimated_storage_bytes": current_storage,
                    "storage_added_bytes_window": current_growth,
                    "storage_added_bytes_previous_window": previous_growth,
                    "growth_percent": growth_percent,
                }
            )

        storage_rows.sort(
            key=lambda item: (
                -item["storage_added_bytes_window"],
                -item["current_estimated_storage_bytes"],
                item["tenant_name"],
            )
        )

        solver_rows: list[dict[str, Any]] = []
        total_attempts = 0
        total_fallbacks = 0
        total_timeouts = 0

        for tenant in universities:
            totals = solver_totals_by_tenant.get(tenant.id, {})
            attempts = int(totals.get(SOLVER_METRIC_KEYS["attempts"], 0))
            fallbacks = int(totals.get(SOLVER_METRIC_KEYS["fallback_runs"], 0))
            timeouts = int(totals.get(SOLVER_METRIC_KEYS["timeout_runs"], 0))
            successes = int(totals.get(SOLVER_METRIC_KEYS["successes"], 0))
            failures = int(totals.get(SOLVER_METRIC_KEYS["failures"], 0))

            total_attempts += attempts
            total_fallbacks += fallbacks
            total_timeouts += timeouts

            solver_rows.append(
                {
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "domain": tenant.domain,
                    "plan_tier": tenant.plan_tier or "free",
                    "attempts": attempts,
                    "successes": successes,
                    "failures": failures,
                    "fallback_runs": fallbacks,
                    "timeout_runs": timeouts,
                    "fallback_rate_percent": round((fallbacks / attempts) * 100, 2) if attempts else None,
                    "timeout_rate_percent": round((timeouts / attempts) * 100, 2) if attempts else None,
                }
            )

        solver_rows.sort(
            key=lambda item: (
                -item["attempts"],
                -(item["fallback_rate_percent"] or 0),
                -(item["timeout_rate_percent"] or 0),
                item["tenant_name"],
            )
        )

        rate_limit_rows: list[dict[str, Any]] = []
        total_rate_limit_hits = 0
        for tenant in universities:
            details = rate_limit_by_tenant.get(tenant.id, {})
            hit_count = int(details.get("hit_count", 0))
            total_rate_limit_hits += hit_count
            endpoint_counts = details.get("endpoint_counts") or {}
            top_endpoints = [
                {"endpoint": endpoint, "count": count}
                for endpoint, count in sorted(endpoint_counts.items(), key=lambda item: item[1], reverse=True)[:3]
            ]

            last_hit_at = details.get("last_hit_at")
            rate_limit_rows.append(
                {
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "plan_tier": tenant.plan_tier or "free",
                    "hit_count": hit_count,
                    "distinct_user_count": len(details.get("usernames") or []),
                    "last_hit_at": last_hit_at.isoformat() if isinstance(last_hit_at, datetime) else None,
                    "top_endpoints": top_endpoints,
                }
            )

        rate_limit_rows.sort(key=lambda item: (-item["hit_count"], item["tenant_name"]))

        total_storage_growth = sum(row["storage_added_bytes_window"] for row in storage_rows)
        total_storage_current = sum(row["current_estimated_storage_bytes"] for row in storage_rows)
        conflict_free_rate = (
            round((conflict_summary_counts["conflict_free"] / conflict_summary_counts["evaluated"]) * 100, 2)
            if conflict_summary_counts["evaluated"]
            else None
        )

        active_tenants = len(
            [
                tenant
                for tenant in universities
                if any(
                    [
                        next((row for row in solver_rows if row["tenant_id"] == tenant.id and row["attempts"] > 0), None),
                        next((row for row in conflict_rows if row["tenant_id"] == tenant.id and row["evaluated_runs"] > 0), None),
                        next((row for row in storage_rows if row["tenant_id"] == tenant.id and row["storage_added_bytes_window"] > 0), None),
                        next((row for row in rate_limit_rows if row["tenant_id"] == tenant.id and row["hit_count"] > 0), None),
                    ]
                )
            ]
        )

        return {
            "window_days": window_days,
            "generated_at": now.isoformat(),
            "summary": {
                "tenant_count": len(universities),
                "active_tenants": active_tenants,
                "total_solver_runs": total_attempts,
                "avg_fallback_rate_percent": round((total_fallbacks / total_attempts) * 100, 2) if total_attempts else None,
                "avg_timeout_rate_percent": round((total_timeouts / total_attempts) * 100, 2) if total_attempts else None,
                "conflict_free_rate_percent": conflict_free_rate,
                "storage_growth_bytes_window": total_storage_growth,
                "current_estimated_storage_bytes": total_storage_current,
                "rate_limit_hits": total_rate_limit_hits,
            },
            "solver_reliability": solver_rows,
            "conflict_resolution": conflict_rows,
            "storage_growth": bucket_rows,
            "tenant_storage": storage_rows,
            "rate_limits": rate_limit_rows,
        }
