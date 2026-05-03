import pytest
from datetime import datetime, timezone
from httpx import AsyncClient

from app.auth import create_access_token, get_password_hash
from app.models import University, User, UserRole


@pytest.mark.security
@pytest.mark.asyncio
class TestSuperadminImpersonation:
    async def test_superadmin_can_impersonate_active_tenant_user(self, async_client: AsyncClient, db_session):
        uni = db_session.query(University).filter(University.domain == "ops-tenant.test.local").first()
        if not uni:
            uni = University(
                name="Ops Tenant University",
                short_name="OTU",
                domain="ops-tenant.test.local",
                timezone="Africa/Harare",
                is_active=True,
                registered_at=datetime.now(timezone.utc),
                plan_tier="free",
                max_users=100,
            )
            db_session.add(uni)
            db_session.commit()
            db_session.refresh(uni)

        coordinator = db_session.query(User).filter(User.username == "ops_coordinator").first()
        if not coordinator:
            coordinator = User(
                username="ops_coordinator",
                email="ops_coordinator@ops-tenant.test.local",
                full_name="Ops Coordinator",
                role=UserRole.COORDINATOR,
                hashed_password=get_password_hash("pass"),
                is_active=True,
                university_id=uni.id,
            )
            db_session.add(coordinator)
            db_session.commit()
            db_session.refresh(coordinator)

        superadmin = db_session.query(User).filter(User.username == "root_superadmin").first()
        if not superadmin:
            superadmin = User(
                username="root_superadmin",
                email="root_superadmin@platform.local",
                full_name="Platform Superadmin",
                role=UserRole.SUPERADMIN,
                hashed_password=get_password_hash("pass"),
                is_active=True,
                university_id=None,
            )
            db_session.add(superadmin)
            db_session.commit()
            db_session.refresh(superadmin)

        sa_token = create_access_token({"sub": superadmin.username})
        response = await async_client.post(
            f"/api/v1/superadmin/universities/{uni.id}/impersonate",
            headers={"Authorization": f"Bearer {sa_token}"},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["token_type"] == "bearer"
        assert payload["user"]["username"] == coordinator.username
        assert payload["user"]["role"] == UserRole.COORDINATOR.value

        me_response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        )
        assert me_response.status_code == 200, me_response.text
        assert me_response.json()["username"] == coordinator.username

    async def test_non_superadmin_cannot_impersonate(self, async_client: AsyncClient, db_session):
        uni = db_session.query(University).filter(University.domain == "ops-tenant-2.test.local").first()
        if not uni:
            uni = University(
                name="Ops Tenant University 2",
                short_name="OTU2",
                domain="ops-tenant-2.test.local",
                timezone="Africa/Harare",
                is_active=True,
                registered_at=datetime.now(timezone.utc),
                plan_tier="free",
                max_users=100,
            )
            db_session.add(uni)
            db_session.commit()
            db_session.refresh(uni)

        coordinator = db_session.query(User).filter(User.username == "ops_coord_denied").first()
        if not coordinator:
            coordinator = User(
                username="ops_coord_denied",
                email="ops_coord_denied@ops-tenant-2.test.local",
                full_name="Ops Coordinator Denied",
                role=UserRole.COORDINATOR,
                hashed_password=get_password_hash("pass"),
                is_active=True,
                university_id=uni.id,
            )
            db_session.add(coordinator)
            db_session.commit()
            db_session.refresh(coordinator)

        coord_token = create_access_token({"sub": coordinator.username})
        response = await async_client.post(
            f"/api/v1/superadmin/universities/{uni.id}/impersonate",
            headers={"Authorization": f"Bearer {coord_token}"},
        )
        assert response.status_code == 403

    async def test_cannot_impersonate_suspended_university(self, async_client: AsyncClient, db_session):
        uni = db_session.query(University).filter(University.domain == "ops-suspended.test.local").first()
        if not uni:
            uni = University(
                name="Suspended Ops University",
                short_name="SOU",
                domain="ops-suspended.test.local",
                timezone="Africa/Harare",
                is_active=False,
                registered_at=datetime.now(timezone.utc),
                plan_tier="free",
                max_users=100,
            )
            db_session.add(uni)
            db_session.commit()
            db_session.refresh(uni)
        else:
            uni.is_active = False
            db_session.commit()

        coordinator = db_session.query(User).filter(User.username == "ops_coord_suspended").first()
        if not coordinator:
            coordinator = User(
                username="ops_coord_suspended",
                email="ops_coord_suspended@ops-suspended.test.local",
                full_name="Ops Coordinator Suspended",
                role=UserRole.COORDINATOR,
                hashed_password=get_password_hash("pass"),
                is_active=True,
                university_id=uni.id,
            )
            db_session.add(coordinator)
            db_session.commit()

        superadmin = db_session.query(User).filter(User.username == "root_superadmin_2").first()
        if not superadmin:
            superadmin = User(
                username="root_superadmin_2",
                email="root_superadmin_2@platform.local",
                full_name="Platform Superadmin 2",
                role=UserRole.SUPERADMIN,
                hashed_password=get_password_hash("pass"),
                is_active=True,
                university_id=None,
            )
            db_session.add(superadmin)
            db_session.commit()
            db_session.refresh(superadmin)

        sa_token = create_access_token({"sub": superadmin.username})
        response = await async_client.post(
            f"/api/v1/superadmin/universities/{uni.id}/impersonate",
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert response.status_code == 400
        assert "suspended" in response.json()["detail"].lower()
