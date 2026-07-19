"""
Pytest configuration and shared fixtures for TABLESYS tests.

Features:
- Test database isolation (separate from dev/prod)
- Async test client for FastAPI
- Authentication fixtures
- Sample data fixtures
- Mock fixtures for external dependencies
"""

import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator, Generator
from app.database import Base, get_db
from app.main import app
from app.config import settings


# ============================================================================
# DATABASE FIXTURES (Test Database Isolation)
# ============================================================================

# Test database URL (separate from dev/prod)
# Replace database name: tablesys_db -> tablesys_test
TEST_DATABASE_URL = settings.DATABASE_URL.replace("/tablesys_db", "/tablesys_test")
if "postgres" in TEST_DATABASE_URL and "localhost" not in settings.DATABASE_URL:
    pass # Keep it containerized if running in docker network


@pytest.fixture(scope="session")
def test_engine():
    """
    Create test database engine (session-scoped).
    
    Creates all tables at start of test session,
    drops all tables at end of test session.
    """
    engine = create_engine(TEST_DATABASE_URL)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Drop all tables after tests
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def seed_test_users(test_engine):
    """
    Seed test database with required users for authentication.
    
    Creates coordinator, HOD, and lab coordinator users with password 'pass'
    to match test fixture expectations.
    """
    from app.auth import get_password_hash
    from app.models import User, UserRole, Department, University
    from sqlalchemy.orm import Session
    
    from app.middleware.tenant import apply_orm_tenant_isolation
    
    TestingSessionLocal = sessionmaker(bind=test_engine)
    apply_orm_tenant_isolation(TestingSessionLocal)
    
    db = TestingSessionLocal()
    
    try:
        from app.seeding_utils import create_quota_placeholders
        create_quota_placeholders(db, commit=True)
        # Create University (Tenant 1) required by foreign keys
        from datetime import datetime, timezone
        uni = db.query(University).filter(University.id == 1).first()
        if not uni:
            uni = University(
                name="Test University",
                short_name="TU",
                domain="test.local",
                timezone="Africa/Harare",
                is_active=True,
                registered_at=datetime.now(timezone.utc),
                plan_tier="free",
                max_users=50
            )
            db.add(uni)
            db.commit()
            db.refresh(uni)

        # Create departments
        departments = [
            {"name": "General", "code": "GEN"},
            {"name": "Civil and Environmental Engineering", "code": "CEE"},
        ]
        
        dept_map = {}
        for d in departments:
            dept = db.query(Department).filter(Department.code == d["code"]).first()
            if not dept:
                dept = Department(name=d["name"], code=d["code"], university_id=1)
                db.add(dept)
                db.commit()
                db.refresh(dept)
            dept_map[d["code"]] = dept.id
        
        # Create tenant admin user
        user = db.query(User).filter(User.username == "coordinator").first()
        if not user:
            user = User(
                username="coordinator",
                email="coordinator@test.local",
                full_name="Tenant Admin",
                role=UserRole.TENANT_ADMIN,
                hashed_password=get_password_hash("pass"),
                is_active=True,
                university_id=1,
            )
            db.add(user)
            db.commit()
        
        # Create HOD user for Civil Engineering
        user = db.query(User).filter(User.username == "hod_civil").first()
        if not user:
            user = User(
                username="hod_civil",
                email="hod_civil@test.local",
                full_name="HOD Civil Engineering",
                role=UserRole.HOD,
                department_id=dept_map["CEE"],
                hashed_password=get_password_hash("pass"),
                is_active=True,
                university_id=1,
            )
            db.add(user)
            db.commit()

        # Create Lab Coordinator user for Civil Engineering
        user = db.query(User).filter(User.username == "lab_civil").first()
        if not user:
            user = User(
                username="lab_civil",
                email="lab_civil@test.local",
                full_name="Lab Coordinator Civil Engineering",
                role=UserRole.LAB_COORDINATOR,
                department_id=dept_map["CEE"],
                hashed_password=get_password_hash("pass"),
                is_active=True,
                university_id=1,
            )
            db.add(user)
            db.commit()
            
    finally:
        db.close()


@pytest.fixture(autouse=True)
def db_session(test_engine):
    """
    Create a new database session for each test.
    
    Each test gets a fresh session that is rolled back after the test,
    ensuring tests don't interfere with each other.
    """
    from app.middleware.tenant import apply_orm_tenant_isolation
    
    TestingSessionLocal = sessionmaker(bind=test_engine)
    apply_orm_tenant_isolation(TestingSessionLocal)
    
    session = TestingSessionLocal()
    
    # Override FastAPI dependency to use this test session
    def override_get_db():
        try:
            yield session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    
    yield session
    
    # Rollback after each test (clean state)
    session.rollback()
    session.close()
    app.dependency_overrides.clear()


# ============================================================================
# FASTAPI CLIENT FIXTURES (Async Support)
# ============================================================================

@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async test client for FastAPI endpoints.

    Uses ASGITransport for compatibility with httpx >= 0.20.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def client():
    """
    Synchronous test client for FastAPI endpoints.
    
    Use this for simple tests that don't need async support.
    """
    from fastapi.testclient import TestClient
    return TestClient(app)


# ============================================================================
# AUTHENTICATION FIXTURES
# ============================================================================

@pytest.fixture
async def auth_token(async_client: AsyncClient) -> str:
    """
    Get authentication token for the coordinator user.

    Returns a JWT token for use in Authorization headers.
    """
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "coordinator", "password": "pass"}
    )
    assert response.status_code == 200, (
        f"Coordinator login failed: {response.status_code} {response.text}"
    )
    return response.json()["access_token"]


@pytest.fixture
async def auth_headers(auth_token: str) -> dict:
    """
    Get authentication headers with Bearer token.
    
    Use this to make authenticated requests in tests.
    """
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def get_department_id(async_client: AsyncClient, auth_headers: dict) -> int:
    """
    Get a valid department_id from the database.
    
    Fetches the first available department from the API.
    Skips the test if no departments exist.
    """
    response = await async_client.get("/api/v1/departments/", headers=auth_headers)
    if response.status_code != 200 or not response.json():
        pytest.skip("No departments available in test database")
    return response.json()[0]["id"]


@pytest.fixture
async def hod_token(async_client: AsyncClient) -> str:
    """
    Get authentication token for an HOD user.

    Returns JWT token for testing HOD-specific permissions.
    Skips the test if no HOD user is seeded in the test database.
    """
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "hod_civil", "password": "pass"}
    )
    if response.status_code != 200:
        pytest.skip("HOD user not available in test database")
    return response.json()["access_token"]


@pytest.fixture
async def hod_headers(hod_token: str) -> dict:
    """Get authentication headers for HOD user"""
    return {"Authorization": f"Bearer {hod_token}"}


@pytest.fixture
async def lab_token(async_client: AsyncClient) -> str:
    """
    Get authentication token for a lab coordinator user.
    """
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "lab_civil", "password": "pass"}
    )
    if response.status_code != 200:
        pytest.skip("Lab coordinator user not available in test database")
    return response.json()["access_token"]


@pytest.fixture
async def lab_headers(lab_token: str) -> dict:
    """Get authentication headers for lab coordinator user"""
    return {"Authorization": f"Bearer {lab_token}"}


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
async def sample_course(get_department_id: int) -> dict:
    """
    Sample course data for testing.
    
    Matches CourseCreate schema requirements.
    Uses a real department_id fetched from the database.
    """
    return {
        "code": "TEST101",
        "name": "Test Course",
        "department_id": get_department_id,
        "level": 200,
        "credits": 3,
        "lecture_hours": 3,
        "tutorial_hours": 1,
        "practical_hours": 0,
        "preferred_room_type": "any",
        "course_type": "department_specific",
        "group_division_type": "full_group"
    }


@pytest.fixture
async def sample_lecturer(get_department_id: int) -> dict:
    """
    Sample lecturer data for testing.
    
    Matches LecturerCreate schema requirements.
    Uses a real department_id fetched from the database.
    """
    return {
        "staff_number": "TEST001",
        "full_name": "Test Lecturer",
        "email": "test.lecturer@unza.zm",
        "department_id": get_department_id,
        "max_hours_per_week": 20
    }


@pytest.fixture
def sample_room() -> dict:
    """
    Sample room data for testing.
    
    Matches Room database model fields (NOT schema).
    Only includes fields that exist in the database model.
    """
    return {
        "name": "TEST-101",
        "building": "Test Building",
        "capacity": 50,
        "room_type": "lecture_hall",
        "has_projector": True,
        "has_computers": False,
        "priority_level": 5,
        "is_blocked": False,
        "furniture_type": "Lecture Theatre",
        "equipment": [],
        "availability": "Mon-Fri 07:00-19:00",
        "priority": "standard"
    }


@pytest.fixture
async def sample_group(get_department_id: int) -> dict:
    """
    Sample student group data for testing.
    
    Matches StudentGroupCreate schema requirements.
    Uses a real department_id fetched from the database.
    """
    return {
        "name": "TEST-GRP",
        "department_id": get_department_id,
        "level": 2,
        "size": 30,
        "group_type": "department"
    }


# ============================================================================
# CSV UPLOAD FIXTURES
# ============================================================================

@pytest.fixture
def sample_courses_csv() -> str:
    """
    Sample CSV content for bulk course upload.
    
    Returns CSV string with valid course data.
    """
    return """code,name,department_id,level,credits,lecture_hours,tutorial_hours,practical_hours
TEST101,Test Course 1,1,200,3,3,1,0
TEST102,Test Course 2,1,200,3,3,1,0
TEST103,Test Course 3,1,300,4,4,2,0"""


@pytest.fixture
def malicious_csv() -> str:
    """
    Sample CSV with malicious content for security testing.
    
    Contains CSV injection and XSS attempts.
    """
    return """code,name,department_id,level,credits,lecture_hours,tutorial_hours,practical_hours
=1+1,<script>alert(1)</script>,1,2,3,3,1,0
+SUM(A1:A10),Normal Course,1,2,3,3,1,0"""


# ============================================================================
# MOCK FIXTURES (For Future External Dependencies)
# ============================================================================

@pytest.fixture
def mock_claude_api():
    """
    Mock Claude API for testing (for future AI integration).
    
    Returns a mock object that simulates Claude API responses.
    """
    from unittest.mock import MagicMock
    
    mock = MagicMock()
    mock.extract_constraints.return_value = {
        "hard": [],
        "soft": []
    }
    mock.generate_schedule.return_value = {
        "slots": [],
        "conflicts": []
    }
    return mock


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """
    Reset rate limiter between tests.
    
    Ensures rate limiting tests don't interfere with each other.
    """
    # Import here to avoid circular imports
    from app.routers.auth import rate_limiter
    
    # Clear rate limiter state before each test
    if rate_limiter:
        rate_limiter.attempts.clear()
        rate_limiter.blocked.clear()
    
    yield
    
    # Clear again after test
    if rate_limiter:
        rate_limiter.attempts.clear()
        rate_limiter.blocked.clear()


# ============================================================================
# END OF FIXTURES
# ============================================================================
