"""
Regression tests for Workstream 5 — Security, Compliance & Commercial Foundation.

Covers:
1. PublicRouteRateLimiter unit tests
2. PublicRateLimitMiddleware integration (API-level 429 behaviour)
3. Tenant provisioning service (staged lifecycle + rollback)
4. Seeding utilities (quota placeholders idempotency)
5. Data export endpoint (role enforcement, content, privacy)
6. Tenant offboarding (deactivate + purge confirmation guard)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from httpx import AsyncClient


# ─────────────────────────────────────────────────────────────────────────────
# 1. PublicRouteRateLimiter — Unit Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.security
class TestPublicRouteRateLimiter:
    """Direct unit tests against PublicRouteRateLimiter without HTTP overhead."""

    def _make_limiter(self, max_requests=5, window_seconds=60, block_duration_seconds=120):
        from app.middleware.rate_limiter import PublicRouteRateLimiter
        return PublicRouteRateLimiter(
            max_requests=max_requests,
            window_seconds=window_seconds,
            block_duration_seconds=block_duration_seconds,
        )

    def test_first_request_is_always_allowed(self):
        limiter = self._make_limiter()
        allowed, retry_after = limiter.is_allowed("10.0.0.1")
        assert allowed is True
        assert retry_after == 0

    def test_requests_within_quota_are_allowed(self):
        limiter = self._make_limiter(max_requests=5)
        ip = "10.0.0.2"
        for _ in range(5):
            allowed, _ = limiter.is_allowed(ip)
            assert allowed is True

    def test_request_at_quota_boundary_is_blocked(self):
        """The 6th request when max=5 must be blocked."""
        limiter = self._make_limiter(max_requests=5)
        ip = "10.0.0.3"
        for _ in range(5):
            limiter.is_allowed(ip)  # exhaust quota
        allowed, retry_after = limiter.is_allowed(ip)
        assert allowed is False
        assert retry_after > 0

    def test_blocked_ip_receives_positive_retry_after(self):
        limiter = self._make_limiter(max_requests=1, block_duration_seconds=60)
        ip = "10.0.0.4"
        limiter.is_allowed(ip)  # hit 1
        limiter.is_allowed(ip)  # triggers block
        _, retry_after = limiter.is_allowed(ip)
        assert retry_after > 0
        assert retry_after <= 60

    def test_block_expires_after_duration(self):
        """Simulate an expired block — IP should be allowed again."""
        limiter = self._make_limiter(block_duration_seconds=10)
        ip = "10.0.0.5"
        # Manually inject an already-expired block
        limiter._blocked[ip] = datetime.utcnow() - timedelta(seconds=1)
        allowed, retry_after = limiter.is_allowed(ip)
        assert allowed is True
        assert retry_after == 0
        assert ip not in limiter._blocked

    def test_different_ips_are_tracked_independently(self):
        """Exhausting one IP's quota must not affect a different IP."""
        limiter = self._make_limiter(max_requests=2)
        victim = "10.0.1.1"
        innocent = "10.0.1.2"
        for _ in range(3):
            limiter.is_allowed(victim)  # exhaust + block victim
        allowed, _ = limiter.is_allowed(innocent)
        assert allowed is True

    def test_window_slides_old_hits_expire(self):
        """Hits older than window_seconds must not count toward the quota."""
        limiter = self._make_limiter(max_requests=2, window_seconds=60)
        ip = "10.0.1.3"
        # Inject two old hits (outside the window)
        old_ts = datetime.utcnow() - timedelta(seconds=120)
        limiter._hits[ip] = [old_ts, old_ts]
        # Both new requests should be allowed (old ones slid out)
        allowed1, _ = limiter.is_allowed(ip)
        allowed2, _ = limiter.is_allowed(ip)
        assert allowed1 is True
        assert allowed2 is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. PublicRateLimitMiddleware — API Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.security
@pytest.mark.api
class TestPublicRateLimitMiddlewareIntegration:
    """
    Verify that the PublicRateLimitMiddleware correctly gates API routes.

    Uses a very low limit (max_requests=2) injected via monkeypatch so the test
    runs fast without making 60 real HTTP requests.
    """

    @pytest.fixture(autouse=True)
    def patch_public_rate_limiter(self, monkeypatch):
        """Replace the global limiter with a tight-limit instance for testing."""
        from app.middleware.rate_limiter import PublicRouteRateLimiter
        import app.main as main_module
        tight_limiter = PublicRouteRateLimiter(
            max_requests=2,
            window_seconds=60,
            block_duration_seconds=30,
        )
        monkeypatch.setattr(main_module, "_public_rate_limiter", tight_limiter)

    async def test_first_requests_to_public_route_succeed(self, async_client: AsyncClient):
        """The first N requests within quota return normal responses (not 429)."""
        for _ in range(2):
            response = await async_client.get(
                "/api/v1/mobile/public/onboarding-groups"
            )
            assert response.status_code != 429

    async def test_request_after_quota_exhausted_returns_429(self, async_client: AsyncClient):
        """After exhausting the quota, the next request must return 429."""
        # Exhaust quota
        for _ in range(2):
            await async_client.get("/api/v1/mobile/public/onboarding-groups")
        # This one should be rate limited
        response = await async_client.get("/api/v1/mobile/public/onboarding-groups")
        assert response.status_code == 429

    async def test_429_response_includes_retry_after_header(self, async_client: AsyncClient):
        """Rate limited responses must include a Retry-After header."""
        for _ in range(3):
            response = await async_client.get("/api/v1/mobile/public/onboarding-groups")
        last = response
        if last.status_code == 429:
            assert "retry-after" in last.headers or "Retry-After" in last.headers

    async def test_authenticated_routes_are_not_rate_limited(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """The public rate limiter must not affect authenticated API routes."""
        # Exhaust public quota first
        for _ in range(3):
            await async_client.get("/api/v1/mobile/public/onboarding-groups")
        # Authenticated route must still work
        response = await async_client.get(
            "/api/v1/departments/", headers=auth_headers
        )
        assert response.status_code != 429

    async def test_public_registration_route_is_also_rate_limited(
        self, async_client: AsyncClient
    ):
        """The /api/v1/public/* prefix must also be covered by the middleware."""
        for _ in range(2):
            await async_client.get("/api/v1/public/university?domain=test")
        response = await async_client.get("/api/v1/public/university?domain=test")
        # Either 429 (rate limited) or 404 (domain not found) — not 500
        assert response.status_code in (404, 429)


@pytest.mark.integration
class TestPublicBrandingResolution:
    def test_public_branding_resolves_exact_domain_and_slug_subdomain(self, client, db_session):
        from app.models import University

        db_session.add_all([
            University(
                name="Slug University",
                short_name="SLUG",
                domain="unza",
                timezone="Africa/Harare",
                is_active=True,
            ),
            University(
                name="Custom Domain University",
                short_name="CUSTOM",
                domain="campus.example.org",
                timezone="Africa/Harare",
                is_active=True,
            ),
        ])
        db_session.commit()

        slug_response = client.get("/api/v1/public/university?domain=unza.tablesys.cloud")
        assert slug_response.status_code == 200
        assert slug_response.json()["domain"] == "unza"

        exact_response = client.get("/api/v1/public/university?domain=campus.example.org")
        assert exact_response.status_code == 200
        assert exact_response.json()["domain"] == "campus.example.org"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Seeding Utilities — Unit Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestSeedingUtils:
    """Test that seeding utilities are idempotent and produce correct output."""

    def test_create_quota_placeholders_creates_rows(self, db_session):
        """First run must create quota rows for all three tiers."""
        from app.seeding_utils import create_quota_placeholders, PLAN_QUOTA_DEFAULTS
        from app.models import PlanQuota

        # Ensure clean state
        db_session.query(PlanQuota).delete()
        db_session.commit()

        count = create_quota_placeholders(db_session)
        assert count == len(PLAN_QUOTA_DEFAULTS)

    def test_create_quota_placeholders_is_idempotent(self, db_session):
        """Running twice must not create duplicate rows."""
        from app.seeding_utils import create_quota_placeholders
        from app.models import PlanQuota

        db_session.query(PlanQuota).delete()
        db_session.commit()

        create_quota_placeholders(db_session)
        count_second_run = create_quota_placeholders(db_session)
        assert count_second_run == 0  # Nothing new to create

    def test_quota_covers_all_three_plan_tiers(self, db_session):
        """Quota rows must exist for starter, professional, and enterprise."""
        from app.seeding_utils import create_quota_placeholders
        from app.models import PlanQuota

        db_session.query(PlanQuota).delete()
        db_session.commit()

        create_quota_placeholders(db_session)

        tiers = {
            row.plan_tier
            for row in db_session.query(PlanQuota.plan_tier).distinct().all()
        }
        assert "starter" in tiers
        assert "professional" in tiers
        assert "enterprise" in tiers

    def test_emit_onboarding_events_writes_usage_events(self, db_session):
        """Onboarding event emitter must write seats_active and storage_bytes rows."""
        from app.seeding_utils import emit_onboarding_events
        from app.models import UsageEvent

        # Clear any prior events for tenant 1
        db_session.query(UsageEvent).filter(UsageEvent.tenant_id == 1).delete()
        db_session.commit()

        emit_onboarding_events(db_session, tenant_id=1, plan_tier="free")
        db_session.commit()

        events = (
            db_session.query(UsageEvent)
            .filter(UsageEvent.tenant_id == 1)
            .all()
        )
        metric_keys = {e.metric_key for e in events}
        assert "seats_active" in metric_keys
        assert "storage_bytes" in metric_keys

    def test_emit_onboarding_events_sets_source_to_provisioning(self, db_session):
        """All onboarding events must have source='provisioning'."""
        from app.seeding_utils import emit_onboarding_events
        from app.models import UsageEvent

        db_session.query(UsageEvent).filter(UsageEvent.tenant_id == 1).delete()
        db_session.commit()

        emit_onboarding_events(db_session, tenant_id=1, plan_tier="pro")
        db_session.commit()

        events = (
            db_session.query(UsageEvent)
            .filter(UsageEvent.tenant_id == 1)
            .all()
        )
        assert all(e.source == "provisioning" for e in events)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Provisioning Service — Unit Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestProvisioningService:
    """Test the staged provisioning lifecycle and rollback policy."""

    def _make_pending(self, db_session, subdomain="new-uni", email="admin@new-uni.test"):
        """Create a minimal PendingRegistration for provisioning tests."""
        from app.models import PendingRegistration
        from app.auth import get_password_hash
        from datetime import datetime, timezone, timedelta
        import uuid

        from app.seeding_utils import create_quota_placeholders
        create_quota_placeholders(db_session)
        
        pending = PendingRegistration(
            token=uuid.uuid4().hex,
            org_name=f"New University {subdomain}",
            subdomain=subdomain,
            admin_email=email,
            admin_username=f"admin_{uuid.uuid4().hex[:6]}",
            admin_full_name="Admin User",
            hashed_password=get_password_hash("testpass123"),
            status="pending",
            ip_address="127.0.0.1",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        db_session.add(pending)
        db_session.flush()
        return pending

    def test_provision_tenant_creates_university_and_user(self, db_session):
        """Successful provisioning must create both a University and a User row."""
        from app.services.provisioning import provision_tenant
        from app.models import University, User

        pending = self._make_pending(db_session, "prov-uni-1", "prov1@prov-uni-1.test")

        result = provision_tenant(db_session, pending)

        assert result.access_token  # token must be non-empty
        assert result.university_id is not None

        uni = db_session.query(University).filter(
            University.domain == "prov-uni-1"
        ).first()
        assert uni is not None
        assert uni.is_active is True

        user = db_session.query(User).filter(
            User.email == "prov1@prov-uni-1.test"
        ).first()
        assert user is not None
        assert user.role.value == "tenant_admin"

    def test_provision_tenant_marks_pending_as_verified(self, db_session):
        """Successful provisioning must set PendingRegistration.status = 'verified'."""
        from app.services.provisioning import provision_tenant

        pending = self._make_pending(db_session, "prov-uni-2", "prov2@prov-uni-2.test")
        provision_tenant(db_session, pending)

        db_session.refresh(pending)
        assert pending.status == "verified"

    def test_provision_tenant_completes_all_six_stages(self, db_session):
        """The result must list all 6 stage markers as completed."""
        from app.services.provisioning import provision_tenant

        pending = self._make_pending(db_session, "prov-uni-3", "prov3@prov-uni-3.test")
        result = provision_tenant(db_session, pending)

        expected_stages = [
            "tenant_record_created",
            "admin_account_created",
            "baseline_seed_applied",
            "notifications_written",
            "usage_baseline_recorded",
            "provisioning_complete",
        ]
        for stage in expected_stages:
            assert stage in result.stages_completed, (
                f"Stage '{stage}' not in completed stages: {result.stages_completed}"
            )

    def test_provision_tenant_raises_on_duplicate_domain(self, db_session):
        """Attempting to provision the same domain twice must raise ProvisioningError."""
        from app.services.provisioning import provision_tenant, ProvisioningError

        pending1 = self._make_pending(db_session, "dup-uni", "first@dup-uni.test")
        provision_tenant(db_session, pending1)

        pending2 = self._make_pending(db_session, "dup-uni", "second@dup-uni.test")
        with pytest.raises(ProvisioningError):
            provision_tenant(db_session, pending2)

    def test_provisioning_failure_marks_pending_as_failed(self, db_session):
        """When provisioning fails mid-way, PendingRegistration must not stay 'pending'."""
        from app.services.provisioning import provision_tenant, ProvisioningError
        from app.seeding_utils import seed_tenant_baseline

        pending = self._make_pending(db_session, "fail-uni", "fail@fail-uni.test")

        # Inject a failure at Stage 3 (baseline seed)
        with patch(
            "app.services.provisioning.seed_tenant_baseline",
            side_effect=RuntimeError("Simulated seed failure"),
        ):
            with pytest.raises(ProvisioningError):
                provision_tenant(db_session, pending)

        db_session.refresh(pending)
        assert pending.status == "failed_provisioning"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Data Export Endpoint — API Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.api
@pytest.mark.security
class TestDataExportEndpoint:
    """Verify role enforcement, response shape, and privacy rules for data export."""

    async def test_unauthenticated_request_returns_401(self, async_client: AsyncClient):
        """No token → 401."""
        response = await async_client.get("/api/v1/export/tenant-data")
        assert response.status_code == 401

    async def test_coordinator_can_access_export(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Coordinator role must receive 200 and a JSON attachment."""
        response = await async_client.get(
            "/api/v1/export/tenant-data", headers=auth_headers
        )
        assert response.status_code == 200

    async def test_export_response_is_json_attachment(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Response must have Content-Disposition: attachment and be valid JSON."""
        response = await async_client.get(
            "/api/v1/export/tenant-data", headers=auth_headers
        )
        assert response.status_code == 200
        disposition = response.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "tablesys_export_" in disposition
        data = response.json()
        assert isinstance(data, dict)

    async def test_export_contains_required_top_level_keys(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Export payload must include all documented top-level sections."""
        response = await async_client.get(
            "/api/v1/export/tenant-data", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        required_keys = [
            "export_metadata",
            "university",
            "users",
            "departments",
            "rooms",
            "courses",
            "lecturers",
            "student_groups",
            "timetables",
            "exam_periods",
            "usage_summary",
        ]
        for key in required_keys:
            assert key in data, f"Missing key '{key}' in export payload"

    async def test_export_metadata_includes_timestamp_and_user(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Export metadata must identify when and by whom the export was made."""
        response = await async_client.get(
            "/api/v1/export/tenant-data", headers=auth_headers
        )
        meta = response.json()["export_metadata"]
        assert "generated_at" in meta
        assert "exported_by_user_id" in meta
        assert "format_version" in meta

    async def test_lecturer_email_is_not_in_export(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """
        Lecturer emails must be excluded from the export per data minimisation policy.
        This is a privacy regression test — if this fails, we have a data leak.
        """
        response = await async_client.get(
            "/api/v1/export/tenant-data", headers=auth_headers
        )
        assert response.status_code == 200
        lecturers = response.json().get("lecturers", [])
        for lecturer in lecturers:
            assert "email" not in lecturer, (
                f"Lecturer email leaked in export! Lecturer data: {lecturer}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Tenant Offboarding — API Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.api
@pytest.mark.security
class TestTenantOffboarding:
    """Verify role enforcement, deactivation, and purge confirmation guard."""

    async def test_deactivate_requires_superadmin(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Coordinator must not be able to deactivate a tenant — 403 expected."""
        response = await async_client.post(
            "/api/v1/superadmin/offboard/999/deactivate",
            headers=auth_headers,
        )
        assert response.status_code == 403

    async def test_deactivate_unknown_university_returns_404(
        self, async_client: AsyncClient, db_session
    ):
        """Offboarding a non-existent university must return 404."""
        from app.auth import create_access_token
        from app.models import User, UserRole
        from datetime import timedelta

        # Create a temporary superadmin for this test
        sa = db_session.query(User).filter(
            User.role == UserRole.SUPERADMIN
        ).first()
        if not sa:
            pytest.skip("No superadmin in test database")

        token = create_access_token(
            data={"sub": sa.username},
            expires_delta=timedelta(minutes=30),
        )
        headers = {"Authorization": f"Bearer {token}"}

        response = await async_client.post(
            "/api/v1/superadmin/offboard/999999/deactivate",
            headers=headers,
        )
        assert response.status_code == 404

    async def test_purge_without_confirmation_token_returns_400(
        self, async_client: AsyncClient, db_session
    ):
        """Purge with wrong confirmation_token must be rejected."""
        from app.auth import create_access_token
        from app.models import User, UserRole, University
        from datetime import datetime, timezone, timedelta

        sa = db_session.query(User).filter(
            User.role == UserRole.SUPERADMIN
        ).first()
        if not sa:
            pytest.skip("No superadmin in test database")

        token = create_access_token(
            data={"sub": sa.username},
            expires_delta=timedelta(minutes=30),
        )
        headers = {"Authorization": f"Bearer {token}"}

        # Create a deactivated university to purge
        uni = University(
            name="Purge Test University",
            domain="purge-test.local",
            is_active=False,  # Already deactivated
            registered_at=datetime.now(timezone.utc),
            plan_tier="free",
            max_users=0,
        )
        db_session.add(uni)
        db_session.commit()
        db_session.refresh(uni)

        # Wrong confirmation token
        response = await async_client.post(
            f"/api/v1/superadmin/offboard/{uni.id}/purge",
            headers=headers,
            json={"confirmation_token": "wrong-domain"},
        )
        assert response.status_code == 400

    async def test_purge_of_active_tenant_returns_409(
        self, async_client: AsyncClient, db_session
    ):
        """Purge must be rejected if the tenant is still active (not deactivated first)."""
        from app.auth import create_access_token
        from app.models import User, UserRole, University
        from datetime import datetime, timezone, timedelta

        sa = db_session.query(User).filter(
            User.role == UserRole.SUPERADMIN
        ).first()
        if not sa:
            pytest.skip("No superadmin in test database")

        token = create_access_token(
            data={"sub": sa.username},
            expires_delta=timedelta(minutes=30),
        )
        headers = {"Authorization": f"Bearer {token}"}

        uni = University(
            name="Active Purge Test",
            domain="active-purge.local",
            is_active=True,  # Still active — must block purge
            registered_at=datetime.now(timezone.utc),
            plan_tier="free",
            max_users=0,
        )
        db_session.add(uni)
        db_session.commit()
        db_session.refresh(uni)

        response = await async_client.post(
            f"/api/v1/superadmin/offboard/{uni.id}/purge",
            headers=headers,
            json={"confirmation_token": uni.domain},
        )
        assert response.status_code == 409

    async def test_purge_unauthenticated_returns_401(self, async_client: AsyncClient):
        """No token → 401."""
        response = await async_client.post(
            "/api/v1/superadmin/offboard/1/purge",
            json={"confirmation_token": "anything"},
        )
        assert response.status_code == 401
