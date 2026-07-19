from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from ..models import University, UsageEvent, User


FEATURE_DEFINITIONS = [
    {"key": "course_management", "label": "Course Management", "prefixes": ["/api/v1/courses"]},
    {"key": "lecturer_management", "label": "Lecturer Management", "prefixes": ["/api/v1/lecturers"]},
    {"key": "room_management", "label": "Room Management", "prefixes": ["/api/v1/rooms"]},
    {"key": "group_management", "label": "Group Management", "prefixes": ["/api/v1/groups"]},
    {"key": "timetable_builder", "label": "Timetable Builder", "prefixes": ["/api/v1/timetables", "/api/v1/templates", "/api/v1/import-timetable"]},
    {"key": "exam_timetables", "label": "Exam Timetables", "prefixes": ["/api/v1/exam-timetables"]},
    {"key": "reports_analytics", "label": "Reports & Analytics", "prefixes": ["/api/v1/reports", "/api/v1/stats", "/api/v1/dashboard", "/api/v1/print-views", "/api/v1/export", "/api/v1/data-export"]},
    {"key": "sis_integration", "label": "SIS Integration", "prefixes": ["/api/v1/sis"]},
    {"key": "billing_usage", "label": "Billing & Usage", "prefixes": ["/api/v1/usage", "/api/v1/offboarding"]},
]

GENERATION_FEATURE_KEY = "automated_generation"
GENERATION_FEATURE_LABEL = "Automated Timetable Generation"
MAX_SESSION_DURATION_MINUTES = 12 * 60


class SuperAdminBusinessMetricsService:
    def __init__(self, db: Session):
        self.db = db

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

    def _resolve_feature(self, event: UsageEvent) -> tuple[str, str] | None:
        if event.metric_key == "timetable_generation_attempts":
            return GENERATION_FEATURE_KEY, GENERATION_FEATURE_LABEL

        metadata = event.metadata_json or {}
        route = str(metadata.get("endpoint_route") or "").strip()
        if not route:
            return None

        for feature in FEATURE_DEFINITIONS:
            if any(route.startswith(prefix) for prefix in feature["prefixes"]):
                return feature["key"], feature["label"]
        return None

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

    def _read_login_events(
        self,
        *,
        window_start: datetime,
        user_tenant_map: dict[int, int],
        username_tenant_map: dict[str, int],
    ) -> tuple[dict[int, list[dict[str, Any]]], bool]:
        events_by_tenant: dict[int, list[dict[str, Any]]] = defaultdict(list)
        has_login_data = False

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

                        event_type = str(payload.get("event_type") or "")
                        if event_type not in {"LOGIN_SUCCESS", "LOGOUT"}:
                            continue

                        timestamp = self._parse_timestamp(payload.get("timestamp"))
                        if not timestamp or timestamp < window_start:
                            continue

                        details = payload.get("details") or {}
                        user_id = details.get("user_id")
                        username = payload.get("username")
                        tenant_id = user_tenant_map.get(user_id) if user_id is not None else None
                        if tenant_id is None and username:
                            tenant_id = username_tenant_map.get(str(username).lower())
                        if tenant_id is None:
                            continue

                        has_login_data = True
                        events_by_tenant[tenant_id].append(
                            {
                                "timestamp": timestamp,
                                "event_type": event_type,
                                "user_id": user_id,
                                "username": username,
                            }
                        )
            except OSError:
                continue

            if has_login_data:
                break

        return events_by_tenant, has_login_data

    def get_business_metrics_overview(self, window_days: int = 30) -> dict[str, Any]:
        window_start = self._window_start(window_days)
        universities = self.db.query(University).order_by(University.name.asc()).all()
        university_map = {tenant.id: tenant for tenant in universities}

        users = self.db.query(User.id, User.username, User.university_id).filter(User.university_id.isnot(None)).all()
        user_tenant_map = {user_id: tenant_id for user_id, _, tenant_id in users if tenant_id is not None}
        username_tenant_map = {str(username).lower(): tenant_id for _, username, tenant_id in users if username and tenant_id is not None}

        relevant_metric_keys = ["api_requests_total", "timetable_generation_attempts"]
        usage_events = (
            self.db.query(UsageEvent)
            .filter(UsageEvent.tenant_id.in_(list(university_map.keys()) or [-1]))
            .filter(UsageEvent.occurred_at >= window_start)
            .filter(UsageEvent.metric_key.in_(relevant_metric_keys))
            .all()
        )

        feature_usage_by_tenant: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
        api_requests_by_tenant: dict[int, int] = defaultdict(int)
        generation_runs_by_tenant: dict[int, int] = defaultdict(int)
        active_days_by_tenant: dict[int, set[str]] = defaultdict(set)
        peak_hours_by_tenant: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))

        for event in usage_events:
            tenant_id = event.tenant_id
            timestamp = event.occurred_at
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:
                timestamp = timestamp.astimezone(timezone.utc)

            if event.metric_key == "api_requests_total":
                api_requests_by_tenant[tenant_id] += int(event.quantity or 0)
                active_days_by_tenant[tenant_id].add(timestamp.date().isoformat())
                peak_hours_by_tenant[tenant_id][timestamp.hour] += int(event.quantity or 0)
            elif event.metric_key == "timetable_generation_attempts":
                generation_runs_by_tenant[tenant_id] += int(event.quantity or 0)

            feature = self._resolve_feature(event)
            if not feature:
                continue

            feature_key, feature_label = feature
            current = feature_usage_by_tenant[tenant_id].get(feature_key)
            if not current:
                current = {"feature_key": feature_key, "feature_name": feature_label, "events": 0}
                feature_usage_by_tenant[tenant_id][feature_key] = current
            current["events"] += int(event.quantity or 0)

        login_events_by_tenant, has_login_data = self._read_login_events(
            window_start=window_start,
            user_tenant_map=user_tenant_map,
            username_tenant_map=username_tenant_map,
        )

        login_summary_by_tenant: dict[int, dict[str, Any]] = defaultdict(
            lambda: {
                "login_count": 0,
                "login_days": set(),
                "session_durations_minutes": [],
            }
        )

        for tenant_id, events in login_events_by_tenant.items():
            by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for event in events:
                user_key = str(event.get("user_id") or event.get("username") or "unknown")
                by_user[user_key].append(event)
                if event["event_type"] == "LOGIN_SUCCESS":
                    login_summary_by_tenant[tenant_id]["login_count"] += 1
                    login_summary_by_tenant[tenant_id]["login_days"].add(event["timestamp"].date().isoformat())

            for user_events in by_user.values():
                ordered = sorted(user_events, key=lambda item: item["timestamp"])
                open_login: datetime | None = None
                for event in ordered:
                    if event["event_type"] == "LOGIN_SUCCESS":
                        if open_login is not None:
                            delta_minutes = (event["timestamp"] - open_login).total_seconds() / 60
                            if 0 < delta_minutes <= MAX_SESSION_DURATION_MINUTES:
                                login_summary_by_tenant[tenant_id]["session_durations_minutes"].append(delta_minutes)
                        open_login = event["timestamp"]
                    elif event["event_type"] == "LOGOUT" and open_login is not None:
                        delta_minutes = (event["timestamp"] - open_login).total_seconds() / 60
                        if 0 < delta_minutes <= MAX_SESSION_DURATION_MINUTES:
                            login_summary_by_tenant[tenant_id]["session_durations_minutes"].append(delta_minutes)
                        open_login = None

        feature_catalog: dict[str, dict[str, Any]] = {}
        tenant_feature_rows: list[dict[str, Any]] = []
        engagement_rows: list[dict[str, Any]] = []
        plan_rollups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "tenant_count": 0,
                "feature_counts": [],
                "api_requests": [],
                "generation_runs": [],
                "login_counts": [],
                "session_durations": [],
                "feature_adoption_counts": defaultdict(int),
            }
        )

        avg_session_values: list[float] = []

        for tenant in universities:
            tenant_id = tenant.id
            features = sorted(
                feature_usage_by_tenant.get(tenant_id, {}).values(),
                key=lambda item: (-item["events"], item["feature_name"]),
            )
            feature_names = [item["feature_name"] for item in features]
            for item in features:
                feature_stats = feature_catalog.setdefault(
                    item["feature_key"],
                    {
                        "feature_key": item["feature_key"],
                        "feature_name": item["feature_name"],
                        "tenant_ids": set(),
                        "usage_events": 0,
                        "top_tenants": [],
                    },
                )
                feature_stats["tenant_ids"].add(tenant_id)
                feature_stats["usage_events"] += item["events"]
                feature_stats["top_tenants"].append({"tenant_name": tenant.name, "events": item["events"]})

            login_summary = login_summary_by_tenant[tenant_id]
            active_days = active_days_by_tenant.get(tenant_id, set()) | login_summary["login_days"]
            session_durations = login_summary["session_durations_minutes"]
            avg_session_minutes = round(mean(session_durations), 2) if session_durations else None
            if avg_session_minutes is not None:
                avg_session_values.append(avg_session_minutes)

            peak_hour_map = peak_hours_by_tenant.get(tenant_id, {})
            peak_hour = max(peak_hour_map.items(), key=lambda item: item[1])[0] if peak_hour_map else None
            api_requests = int(api_requests_by_tenant.get(tenant_id, 0))
            login_count = int(login_summary["login_count"])
            generation_runs = int(generation_runs_by_tenant.get(tenant_id, 0))

            tenant_feature_rows.append(
                {
                    "tenant_id": tenant_id,
                    "tenant_name": tenant.name,
                    "plan_tier": tenant.plan_tier or "free",
                    "feature_count": len(features),
                    "features_used": feature_names,
                    "top_feature": feature_names[0] if feature_names else None,
                    "total_feature_events": sum(item["events"] for item in features),
                }
            )

            engagement_rows.append(
                {
                    "tenant_id": tenant_id,
                    "tenant_name": tenant.name,
                    "plan_tier": tenant.plan_tier or "free",
                    "login_count": login_count,
                    "active_days": len(active_days),
                    "avg_logins_per_week": round(login_count / max(window_days / 7, 1), 2),
                    "avg_session_duration_minutes": avg_session_minutes,
                    "api_requests": api_requests,
                    "avg_api_requests_per_active_day": round(api_requests / len(active_days), 2) if active_days else 0.0,
                    "peak_hour_utc": peak_hour,
                }
            )

            plan_rollup = plan_rollups[tenant.plan_tier or "free"]
            plan_rollup["tenant_count"] += 1
            plan_rollup["feature_counts"].append(len(features))
            plan_rollup["api_requests"].append(api_requests)
            plan_rollup["generation_runs"].append(generation_runs)
            plan_rollup["login_counts"].append(login_count)
            if avg_session_minutes is not None:
                plan_rollup["session_durations"].append(avg_session_minutes)
            for feature_name in feature_names:
                plan_rollup["feature_adoption_counts"][feature_name] += 1

        feature_adoption_rows = []
        for feature_stats in feature_catalog.values():
            feature_stats["top_tenants"] = sorted(
                feature_stats["top_tenants"],
                key=lambda item: (-item["events"], item["tenant_name"]),
            )[:3]
            tenant_count = len(feature_stats["tenant_ids"])
            feature_adoption_rows.append(
                {
                    "feature_key": feature_stats["feature_key"],
                    "feature_name": feature_stats["feature_name"],
                    "tenant_count": tenant_count,
                    "adoption_percent": round((tenant_count / max(len(universities), 1)) * 100, 2),
                    "usage_events": feature_stats["usage_events"],
                    "top_tenants": feature_stats["top_tenants"],
                }
            )

        feature_adoption_rows.sort(key=lambda item: (-item["tenant_count"], -item["usage_events"], item["feature_name"]))
        tenant_feature_rows.sort(key=lambda item: (-item["feature_count"], -item["total_feature_events"], item["tenant_name"]))
        engagement_rows.sort(key=lambda item: (-item["login_count"], -item["active_days"], -item["api_requests"], item["tenant_name"]))

        plan_correlation_rows = []
        for plan_tier, rollup in sorted(plan_rollups.items(), key=lambda item: item[0]):
            adoption_counts = rollup["feature_adoption_counts"]
            most_adopted_feature = None
            if adoption_counts:
                most_adopted_feature = sorted(adoption_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

            plan_correlation_rows.append(
                {
                    "plan_tier": plan_tier,
                    "tenant_count": rollup["tenant_count"],
                    "avg_features_adopted": round(mean(rollup["feature_counts"]), 2) if rollup["feature_counts"] else 0.0,
                    "avg_api_requests": round(mean(rollup["api_requests"]), 2) if rollup["api_requests"] else 0.0,
                    "avg_generation_runs": round(mean(rollup["generation_runs"]), 2) if rollup["generation_runs"] else 0.0,
                    "avg_login_count": round(mean(rollup["login_counts"]), 2) if rollup["login_counts"] else 0.0,
                    "avg_session_duration_minutes": round(mean(rollup["session_durations"]), 2) if rollup["session_durations"] else None,
                    "most_adopted_feature": most_adopted_feature,
                }
            )

        active_tenants = len(
            [
                tenant
                for tenant in engagement_rows
                if tenant["api_requests"] > 0 or tenant["login_count"] > 0 or tenant["active_days"] > 0
            ]
        )

        return {
            "window_days": window_days,
            "generated_at": self._now().isoformat(),
            "summary": {
                "tenant_count": len(universities),
                "active_tenants": active_tenants,
                "adopted_feature_count": len(feature_adoption_rows),
                "avg_features_per_tenant": round(mean([row["feature_count"] for row in tenant_feature_rows]), 2) if tenant_feature_rows else 0.0,
                "avg_logins_per_tenant": round(mean([row["login_count"] for row in engagement_rows]), 2) if engagement_rows else 0.0,
                "avg_session_duration_minutes": round(mean(avg_session_values), 2) if avg_session_values else None,
                "login_data_available": has_login_data,
            },
            "feature_adoption": feature_adoption_rows,
            "tenant_feature_matrix": tenant_feature_rows,
            "engagement": engagement_rows,
            "plan_correlation": plan_correlation_rows,
        }
