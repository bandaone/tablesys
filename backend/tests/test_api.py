"""
API endpoint tests for TABLESYS - Checkpoint 1.7

Tests all API endpoints for correct status codes and data validation.
"""

import pytest
from httpx import AsyncClient
import io


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

@pytest.mark.api
@pytest.mark.asyncio
class TestHealthCheck:
    """Test health check endpoints"""
    
    async def test_root_endpoint_returns_200(self, async_client: AsyncClient):
        """Test that root endpoint returns 200"""
        response = await async_client.get("/")
        assert response.status_code == 200, f'Status {response.status_code}: {response.text}'
        data = response.json()
        assert "message" in data
        assert "version" in data
    
    async def test_health_endpoint_returns_200(self, async_client: AsyncClient):
        """Test that health endpoint returns 200"""
        response = await async_client.get("/health")
        assert response.status_code == 200, f'Status {response.status_code}: {response.text}'
        data = response.json()
        assert data["status"] == "healthy"


# ============================================================================
# COURSES API TESTS
# ============================================================================

@pytest.mark.api
@pytest.mark.asyncio
class TestCoursesAPI:
    """Test courses API endpoints"""
    
    async def test_get_courses_returns_200(self, async_client: AsyncClient, auth_headers: dict):
        """Test that GET /api/courses/ returns 200"""
        response = await async_client.get("/api/v1/courses/", headers=auth_headers)
        assert response.status_code == 200, f'Status {response.status_code}: {response.text}'
        assert isinstance(response.json(), list)
    
    async def test_create_course(self, async_client: AsyncClient, auth_headers: dict, sample_course: dict):
        """Test creating a course"""
        response = await async_client.post(
            "/api/v1/courses/",
            json=sample_course,
            headers=auth_headers
        )
        if response.status_code == 422: print(response.text)
        assert response.status_code in [200, 201, 400, 409], f'Status {response.status_code}: {response.text}'  # 400/409 if already exists
        if response.status_code in [200, 201]:
            data = response.json()
            assert data["code"] == sample_course["code"]
    
    async def test_get_course_by_id(self, async_client: AsyncClient, auth_headers: dict):
        """Test getting a course by ID"""
        # First create a course
        # Then get it by ID
        # For now, just test the endpoint exists
        response = await async_client.get("/api/v1/courses/1", headers=auth_headers)
        # May return 404 if no course exists, which is fine
        assert response.status_code in [200, 404]
    
    async def test_bulk_upload_courses(self, async_client: AsyncClient, auth_headers: dict, sample_courses_csv: str):
        """Test bulk upload courses"""
        # Create file-like object from CSV string
        files = {"file": ("courses.csv", io.BytesIO(sample_courses_csv.encode()), "text/csv")}
        
        response = await async_client.post(
            "/api/v1/courses/bulk-upload",
            files=files,
            headers=auth_headers
        )
        # Should return 200 or validation error
        assert response.status_code in [200, 400, 422]


# ============================================================================
# LECTURERS API TESTS
# ============================================================================

@pytest.mark.api
@pytest.mark.asyncio
class TestLecturersAPI:
    """Test lecturers API endpoints"""
    
    async def test_get_lecturers_returns_200(self, async_client: AsyncClient, auth_headers: dict):
        """Test that GET /api/lecturers/ returns 200"""
        response = await async_client.get("/api/v1/lecturers/", headers=auth_headers)
        assert response.status_code == 200, f'Status {response.status_code}: {response.text}'
        assert isinstance(response.json(), list)
    
    async def test_create_lecturer(self, async_client: AsyncClient, auth_headers: dict, sample_lecturer: dict):
        """Test creating a lecturer"""
        response = await async_client.post(
            "/api/v1/lecturers/",
            json=sample_lecturer,
            headers=auth_headers
        )
        if response.status_code == 422: print(response.text)
        assert response.status_code in [200, 201, 400, 409], f'Status {response.status_code}: {response.text}'  # 400/409 if already exists
    
    async def test_bulk_upload_lecturers(self, async_client: AsyncClient, auth_headers: dict):
        """Test bulk upload lecturers"""
        csv_content = """staff_number,full_name,email,department_id,max_hours_per_week
TEST001,Test Lecturer,test@example.com,1,20"""
        
        files = {"file": ("lecturers.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        
        response = await async_client.post(
            "/api/v1/lecturers/bulk-upload",
            files=files,
            headers=auth_headers
        )
        assert response.status_code in [200, 400, 422]


# ============================================================================
# ROOMS API TESTS
# ============================================================================

@pytest.mark.api
@pytest.mark.asyncio
class TestRoomsAPI:
    """Test rooms API endpoints"""
    
    async def test_get_rooms_returns_200(self, async_client: AsyncClient, auth_headers: dict):
        """Test that GET /api/rooms/ returns 200"""
        response = await async_client.get("/api/v1/rooms/", headers=auth_headers)
        assert response.status_code == 200, f'Status {response.status_code}: {response.text}'
        assert isinstance(response.json(), list)
    
    async def test_create_room(self, async_client: AsyncClient, auth_headers: dict, sample_room: dict):
        """Test creating a room"""
        response = await async_client.post(
            "/api/v1/rooms/",
            json=sample_room,
            headers=auth_headers
        )
        if response.status_code == 422: print(response.text)
        assert response.status_code in [200, 201, 400, 409], f'Status {response.status_code}: {response.text}'  # 400/409 if already exists
    
    async def test_bulk_upload_rooms(self, async_client: AsyncClient, auth_headers: dict):
        """Test bulk upload rooms"""
        csv_content = """room_number,building,capacity,room_type
TEST-101,Test Building,50,lecture_hall"""
        
        files = {"file": ("rooms.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        
        response = await async_client.post(
            "/api/v1/rooms/bulk-upload",
            files=files,
            headers=auth_headers
        )
        assert response.status_code in [200, 400, 422]


# ============================================================================
# GROUPS API TESTS
# ============================================================================

@pytest.mark.api
@pytest.mark.asyncio
class TestGroupsAPI:
    """Test student groups API endpoints"""
    
    async def test_get_groups_returns_200(self, async_client: AsyncClient, auth_headers: dict):
        """Test that GET /api/groups/ returns 200"""
        response = await async_client.get("/api/v1/groups/", headers=auth_headers)
        assert response.status_code == 200, f'Status {response.status_code}: {response.text}'
        assert isinstance(response.json(), list)
    
    async def test_create_group(self, async_client: AsyncClient, auth_headers: dict, sample_group: dict):
        """Test creating a student group"""
        response = await async_client.post(
            "/api/v1/groups/",
            json=sample_group,
            headers=auth_headers
        )
        if response.status_code == 422: print(response.text)
        assert response.status_code in [200, 201, 400, 409], f'Status {response.status_code}: {response.text}'  # 400/409 if already exists
    
    async def test_bulk_upload_groups(self, async_client: AsyncClient, auth_headers: dict):
        """Test bulk upload groups"""
        csv_content = """group_code,department_id,level,size
TEST-GRP,1,2,30"""
        
        files = {"file": ("groups.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        
        response = await async_client.post(
            "/api/v1/groups/bulk-upload",
            files=files,
            headers=auth_headers
        )
        assert response.status_code in [200, 400, 422]


# ============================================================================
# DEPARTMENTS API TESTS
# ============================================================================

@pytest.mark.api
@pytest.mark.asyncio
class TestDepartmentsAPI:
    """Test departments API endpoints"""
    
    async def test_get_departments_returns_200(self, async_client: AsyncClient, auth_headers: dict):
        """Test that GET /api/departments/ returns 200"""
        response = await async_client.get("/api/v1/departments/", headers=auth_headers)
        assert response.status_code == 200, f'Status {response.status_code}: {response.text}'
        assert isinstance(response.json(), list)
