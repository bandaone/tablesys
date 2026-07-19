from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Department, Lecturer, School, StudentGroup, University, User, UserRole, ViewerActivity
from app.services.dashboard_service import DashboardService


def test_get_school_summary_supports_tenant_admin_without_school_departments_relationship():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        university = University(
            name="Test University",
            short_name="TU",
            domain="test.local",
        )
        session.add(university)
        session.flush()

        school = School(
            university_id=university.id,
            name="School of Engineering",
            code="SOE",
        )
        session.add(school)
        session.flush()

        department = Department(
            university_id=university.id,
            school_id=school.id,
            name="Electrical Engineering",
            code="EEE",
        )
        session.add(department)

        tenant_admin = User(
            university_id=university.id,
            email="tenant-admin@test.local",
            username="tenant-admin",
            hashed_password="not-used",
            full_name="Tenant Admin",
            role=UserRole.TENANT_ADMIN,
            is_active=True,
        )
        session.add(tenant_admin)
        session.commit()

        summary = DashboardService(session, tenant_admin).get_school_summary()

        assert len(summary) == 1
        assert summary[0]["name"] == "School of Engineering"
        assert summary[0]["departments_count"] == 1
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_dashboard_user_metrics_fallback_when_user_created_at_is_unavailable():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        university = University(
            name="Fallback University",
            short_name="FU",
            domain="fallback.local",
        )
        session.add(university)
        session.flush()

        tenant_admin = User(
            university_id=university.id,
            email="fallback-admin@test.local",
            username="fallback-admin",
            hashed_password="not-used",
            full_name="Fallback Admin",
            role=UserRole.TENANT_ADMIN,
            is_active=True,
        )
        coordinator = User(
            university_id=university.id,
            email="coord@test.local",
            username="coord",
            hashed_password="not-used",
            full_name="Coordinator",
            role=UserRole.COORDINATOR,
            is_active=True,
        )
        session.add_all([tenant_admin, coordinator])
        session.commit()

        service = DashboardService(session, tenant_admin)
        service._user_created_at_column = lambda: None

        user_stats = service.get_user_statistics()
        weekly_stats = service.get_weekly_statistics()
        recent_activity = service.get_recent_activity(limit=5)

        assert user_stats["by_role"]["tenant_admin"] == 1
        assert user_stats["by_role"]["coordinator"] == 1
        assert user_stats["recent_signups"] == 0
        assert weekly_stats["users_created"] == 0
        assert [user["username"] for user in recent_activity["users"]] == ["coord", "fallback-admin"]
        assert len(recent_activity["users"]) == 2
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_viewer_analytics_supports_school_segmentation_and_uses_7d_top_groups():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        university = University(
            name="Segmented University",
            short_name="SU",
            domain="segmented.local",
        )
        session.add(university)
        session.flush()

        school_alpha = School(university_id=university.id, name="School Alpha", code="ALP")
        school_beta = School(university_id=university.id, name="School Beta", code="BET")
        session.add_all([school_alpha, school_beta])
        session.flush()

        department_alpha = Department(
            university_id=university.id,
            school_id=school_alpha.id,
            name="Alpha Department",
            code="ALD",
        )
        department_beta = Department(
            university_id=university.id,
            school_id=school_beta.id,
            name="Beta Department",
            code="BED",
        )
        session.add_all([department_alpha, department_beta])
        session.flush()

        alpha_group = StudentGroup(
            university_id=university.id,
            name="Alpha Group",
            level=1,
            department_id=department_alpha.id,
            size=120,
        )
        beta_group = StudentGroup(
            university_id=university.id,
            name="Beta Group",
            level=1,
            department_id=department_beta.id,
            size=90,
        )
        session.add_all([alpha_group, beta_group])
        session.flush()

        beta_lecturer = Lecturer(
            staff_number="L-1001",
            full_name="Beta Lecturer",
            department_id=department_beta.id,
            email="beta.lecturer@test.local",
        )
        session.add(beta_lecturer)
        session.flush()

        tenant_admin = User(
            university_id=university.id,
            email="segmented-admin@test.local",
            username="segmented-admin",
            hashed_password="not-used",
            full_name="Segmented Admin",
            role=UserRole.TENANT_ADMIN,
            is_active=True,
        )
        session.add(tenant_admin)
        session.flush()

        now = datetime.now(timezone.utc)
        session.add_all([
            ViewerActivity(
                tenant_id=university.id,
                audience="student_public",
                viewer_id="alpha-device-1",
                group_id=alpha_group.id,
                route_key="/student/dashboard",
                method="GET",
                status_code=200,
                response_time_ms=120,
                occurred_at=now - timedelta(days=1),
            ),
            ViewerActivity(
                tenant_id=university.id,
                audience="student_public",
                viewer_id="alpha-device-2",
                group_id=alpha_group.id,
                route_key="/student/dashboard",
                method="GET",
                status_code=200,
                response_time_ms=100,
                occurred_at=now - timedelta(days=2),
            ),
            ViewerActivity(
                tenant_id=university.id,
                audience="lecturer_portal",
                viewer_id="lecturer-device-1",
                lecturer_id=beta_lecturer.id,
                route_key="/lecturer/dashboard",
                method="GET",
                status_code=200,
                response_time_ms=90,
                occurred_at=now - timedelta(days=1),
            ),
            ViewerActivity(
                tenant_id=university.id,
                audience="student_public",
                viewer_id="beta-old-device",
                group_id=beta_group.id,
                route_key="/student/legacy",
                method="GET",
                status_code=200,
                response_time_ms=130,
                occurred_at=now - timedelta(days=10),
            ),
        ])
        session.commit()

        analytics = DashboardService(session, tenant_admin).get_viewer_analytics()

        assert analytics["summary"]["viewer_requests_7d"] == 3
        assert analytics["summary"]["active_student_groups_7d"] == 1
        assert analytics["summary"]["total_student_groups"] == 2
        assert analytics["summary"]["group_coverage_percent_7d"] == 50.0

        assert len(analytics["school_options"]) == 2
        assert analytics["by_school"][str(school_alpha.id)]["summary"]["viewer_requests_7d"] == 2
        assert analytics["by_school"][str(school_alpha.id)]["summary"]["active_student_groups_7d"] == 1
        assert analytics["by_school"][str(school_beta.id)]["summary"]["viewer_requests_7d"] == 1
        assert analytics["by_school"][str(school_beta.id)]["summary"]["active_student_groups_7d"] == 0

        assert [group["group_name"] for group in analytics["top_student_groups"]] == ["Alpha Group"]
        assert analytics["by_school"][str(school_beta.id)]["top_student_groups"] == []
        assert analytics["by_school"][str(school_beta.id)]["top_routes"][0]["route"] == "/lecturer/dashboard"
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
