"""
Unit tests for router validation (Task T2)

Tests comprehensive validation logic implemented in Task T2 across all CRUD routers:
- HTTP 422: Invalid field values and foreign key validation
- HTTP 409: Duplicate detection (conflicts)
- HTTP 404: Resource not found
- HTTP 200/201: Success cases

Test Coverage:
- courses.py: 12 tests
- lecturers.py: 10 tests
- rooms.py: 10 tests
- groups.py: 10 tests
- departments.py: 8 tests
Total: 50 tests
"""

import pytest
from httpx import AsyncClient


# ============================================================================
# COURSES ROUTER VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
class TestCoursesValidation:
    """Test validation for courses router"""
    
    # ---------- HTTP 422: Invalid Field Values ----------
    
    async def test_create_course_invalid_level(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test course creation with invalid level (not 100-600)"""
        response = await async_client.post(
            "/api/v1/courses/",
            json={
                "code": "TEST999",
                "name": "Test Course",
                "department_id": get_department_id,
                "level": 700,  # Invalid - should be 100, 200, 300, 400, 500, or 600
                "credits": 3,
                "lecture_hours": 3,
                "tutorial_hours": 1,
                "practical_hours": 0
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "level" in str(response.json()["detail"]).lower()
    
    async def test_create_course_invalid_credits(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test course creation with credits outside 1-12 range"""
        response = await async_client.post(
            "/api/v1/courses/",
            json={
                "code": "TEST998",
                "name": "Test Course",
                "department_id": get_department_id,
                "level": 200,
                "credits": 15,  # Invalid - should be 1-12
                "lecture_hours": 3,
                "tutorial_hours": 1,
                "practical_hours": 0
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "credits" in str(response.json()["detail"]).lower()
    
    async def test_create_course_negative_hours(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test course creation with negative lecture hours"""
        response = await async_client.post(
            "/api/v1/courses/",
            json={
                "code": "TEST997",
                "name": "Test Course",
                "department_id": get_department_id,
                "level": 200,
                "credits": 3,
                "lecture_hours": -1,  # Invalid - cannot be negative
                "tutorial_hours": 1,
                "practical_hours": 0
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "hours" in str(response.json()["detail"]).lower()
    
    async def test_create_course_excessive_total_hours(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test course creation with total hours exceeding 15"""
        response = await async_client.post(
            "/api/v1/courses/",
            json={
                "code": "TEST996",
                "name": "Test Course",
                "department_id": get_department_id,
                "level": 200,
                "credits": 3,
                "lecture_hours": 10,
                "tutorial_hours": 10,  # Total = 20, exceeds limit
                "practical_hours": 0
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "total hours" in str(response.json()["detail"]).lower() or "hours" in str(response.json()["detail"]).lower()
    
    async def test_create_course_empty_code(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test course creation with empty course code"""
        response = await async_client.post(
            "/api/v1/courses/",
            json={
                "code": "",  # Invalid - cannot be empty
                "name": "Test Course",
                "department_id": get_department_id,
                "level": 200,
                "credits": 3,
                "lecture_hours": 3,
                "tutorial_hours": 1,
                "practical_hours": 0
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "code" in str(response.json()["detail"]).lower()
    
    async def test_create_course_empty_name(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test course creation with empty course name"""
        response = await async_client.post(
            "/api/v1/courses/",
            json={
                "code": "TEST995",
                "name": "",  # Invalid - cannot be empty
                "department_id": get_department_id,
                "level": 200,
                "credits": 3,
                "lecture_hours": 3,
                "tutorial_hours": 1,
                "practical_hours": 0
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "name" in str(response.json()["detail"]).lower()
    
    # ---------- HTTP 422: Invalid Foreign Key ----------
    
    async def test_create_course_invalid_department(self, async_client: AsyncClient, auth_headers: dict):
        """Test course creation with non-existent department_id"""
        response = await async_client.post(
            "/api/v1/courses/",
            json={
                "code": "TEST994",
                "name": "Test Course",
                "department_id": 99999,  # Doesn't exist
                "level": 200,
                "credits": 3,
                "lecture_hours": 3,
                "tutorial_hours": 1,
                "practical_hours": 0
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "department" in str(response.json()["detail"]).lower()
    
    # ---------- HTTP 409: Duplicate Detection ----------
    
    async def test_create_course_duplicate_code(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test that duplicate course codes are rejected"""
        course_data = {
            "code": "DUP101",
            "name": "Duplicate Test",
            "department_id": get_department_id,
            "level": 200,
            "credits": 3,
            "lecture_hours": 3,
            "tutorial_hours": 1,
            "practical_hours": 0
        }
        
        # Create first course
        response1 = await async_client.post("/api/v1/courses/", json=course_data, headers=auth_headers)
        assert response1.status_code in [200, 201]
        
        # Try to create duplicate
        response2 = await async_client.post("/api/v1/courses/", json=course_data, headers=auth_headers)
        assert response2.status_code == 409
        assert "already exists" in str(response2.json()["detail"]).lower()
    
    # ---------- HTTP 404: Resource Not Found ----------
    
    async def test_get_nonexistent_course(self, async_client: AsyncClient, auth_headers: dict):
        """Test getting a course that doesn't exist"""
        response = await async_client.get("/api/v1/courses/99999", headers=auth_headers)
        assert response.status_code == 404
        assert "not found" in str(response.json()["detail"]).lower()
    
    async def test_update_nonexistent_course(self, async_client: AsyncClient, auth_headers: dict):
        """Test updating a course that doesn't exist"""
        response = await async_client.put(
            "/api/v1/courses/99999",
            json={"name": "Updated Name"},
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "not found" in str(response.json()["detail"]).lower()
    
    # ---------- Success Cases ----------
    
    async def test_create_course_valid(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test successful course creation with valid data"""
        response = await async_client.post(
            "/api/v1/courses/",
            json={
                "code": "VALID101",
                "name": "Valid Course",
                "department_id": get_department_id,
                "level": 300,
                "credits": 4,
                "lecture_hours": 3,
                "tutorial_hours": 2,
                "practical_hours": 1
            },
            headers=auth_headers
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["code"] == "VALID101"
        assert data["level"] == 300
        assert data["credits"] == 4
    
    async def test_update_course_valid(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test successful course update with valid data"""
        # First create a course
        create_response = await async_client.post(
            "/api/v1/courses/",
            json={
                "code": "UPDATE101",
                "name": "Original Name",
                "department_id": get_department_id,
                "level": 200,
                "credits": 3,
                "lecture_hours": 3,
                "tutorial_hours": 1,
                "practical_hours": 0
            },
            headers=auth_headers
        )
        assert create_response.status_code in [200, 201]
        course_id = create_response.json()["id"]
        
        # Update the course
        update_response = await async_client.put(
            f"/api/v1/courses/{course_id}",
            json={"name": "Updated Name"},
            headers=auth_headers
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Name"


# ============================================================================
# LECTURERS ROUTER VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
class TestLecturersValidation:
    """Test validation for lecturers router"""
    
    # ---------- HTTP 422: Invalid Field Values ----------
    
    async def test_create_lecturer_invalid_email(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test lecturer creation with malformed email"""
        response = await async_client.post(
            "/api/v1/lecturers/",
            json={
                "staff_number": "L999",
                "full_name": "Test Lecturer",
                "email": "notanemail",  # Invalid format
                "department_id": get_department_id,
                "max_hours_per_week": 20
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "email" in str(response.json()["detail"]).lower()
    
    async def test_create_lecturer_invalid_max_hours_high(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test lecturer creation with max_hours > 40"""
        response = await async_client.post(
            "/api/v1/lecturers/",
            json={
                "staff_number": "L998",
                "full_name": "Test Lecturer",
                "email": "test@unza.zm",
                "department_id": get_department_id,
                "max_hours_per_week": 50  # Invalid - max is 40
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "hours" in str(response.json()["detail"]).lower()
    
    async def test_create_lecturer_invalid_max_hours_zero(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test lecturer creation with max_hours = 0"""
        response = await async_client.post(
            "/api/v1/lecturers/",
            json={
                "staff_number": "L997",
                "full_name": "Test Lecturer",
                "email": "test2@unza.zm",
                "department_id": get_department_id,
                "max_hours_per_week": 0  # Invalid - min is 1
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "hours" in str(response.json()["detail"]).lower()
    
    async def test_create_lecturer_empty_staff_number(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test lecturer creation with empty staff number"""
        response = await async_client.post(
            "/api/v1/lecturers/",
            json={
                "staff_number": "",  # Invalid - cannot be empty
                "full_name": "Test Lecturer",
                "email": "test3@unza.zm",
                "department_id": get_department_id,
                "max_hours_per_week": 20
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "staff" in str(response.json()["detail"]).lower() or "number" in str(response.json()["detail"]).lower()
    
    async def test_create_lecturer_empty_full_name(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test lecturer creation with empty full name"""
        response = await async_client.post(
            "/api/v1/lecturers/",
            json={
                "staff_number": "L996",
                "full_name": "",  # Invalid - cannot be empty
                "email": "test4@unza.zm",
                "department_id": get_department_id,
                "max_hours_per_week": 20
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "name" in str(response.json()["detail"]).lower()
    
    # ---------- HTTP 422: Invalid Foreign Key ----------
    
    async def test_create_lecturer_invalid_department(self, async_client: AsyncClient, auth_headers: dict):
        """Test lecturer creation with non-existent department_id"""
        response = await async_client.post(
            "/api/v1/lecturers/",
            json={
                "staff_number": "L995",
                "full_name": "Test Lecturer",
                "email": "test5@unza.zm",
                "department_id": 99999,  # Doesn't exist
                "max_hours_per_week": 20
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "department" in str(response.json()["detail"]).lower()
    
    # ---------- HTTP 409: Duplicate Detection ----------
    
    async def test_create_lecturer_duplicate_staff_number(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test that duplicate staff numbers are rejected"""
        lecturer_data = {
            "staff_number": "DUPL001",
            "full_name": "Duplicate Lecturer",
            "email": "dup1@unza.zm",
            "department_id": get_department_id,
            "max_hours_per_week": 20
        }
        
        # Create first lecturer
        response1 = await async_client.post("/api/v1/lecturers/", json=lecturer_data, headers=auth_headers)
        assert response1.status_code in [200, 201]
        
        # Try to create duplicate with different email
        lecturer_data["email"] = "different@unza.zm"
        response2 = await async_client.post("/api/v1/lecturers/", json=lecturer_data, headers=auth_headers)
        assert response2.status_code == 409
        assert "already exists" in str(response2.json()["detail"]).lower()
    
    async def test_create_lecturer_duplicate_email(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test that duplicate emails are rejected"""
        # Create first lecturer
        response1 = await async_client.post(
            "/api/v1/lecturers/",
            json={
                "staff_number": "DUPL002",
                "full_name": "Lecturer One",
                "email": "duplicate@unza.zm",
                "department_id": get_department_id,
                "max_hours_per_week": 20
            },
            headers=auth_headers
        )
        assert response1.status_code in [200, 201]
        
        # Try to create duplicate email with different staff number
        response2 = await async_client.post(
            "/api/v1/lecturers/",
            json={
                "staff_number": "DUPL003",
                "full_name": "Lecturer Two",
                "email": "duplicate@unza.zm",
                "department_id": get_department_id,
                "max_hours_per_week": 20
            },
            headers=auth_headers
        )
        assert response2.status_code == 409
        assert "already exists" in str(response2.json()["detail"]).lower()
    
    # ---------- HTTP 404: Resource Not Found ----------
    
    async def test_update_nonexistent_lecturer(self, async_client: AsyncClient, auth_headers: dict):
        """Test updating a lecturer that doesn't exist"""
        response = await async_client.put(
            "/api/v1/lecturers/99999",
            json={"full_name": "Updated Name"},
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "not found" in str(response.json()["detail"]).lower()
    
    # ---------- Success Cases ----------
    
    async def test_create_lecturer_valid(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test successful lecturer creation with valid data"""
        response = await async_client.post(
            "/api/v1/lecturers/",
            json={
                "staff_number": "VALID001",
                "full_name": "Valid Lecturer",
                "email": "valid@unza.zm",
                "department_id": get_department_id,
                "max_hours_per_week": 25
            },
            headers=auth_headers
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["staff_number"] == "VALID001"
        assert data["max_hours_per_week"] == 25


# ============================================================================
# ROOMS ROUTER VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
class TestRoomsValidation:
    """Test validation for rooms router"""
    
    # ---------- HTTP 422: Invalid Field Values ----------
    
    async def test_create_room_zero_capacity(self, async_client: AsyncClient, auth_headers: dict):
        """Test room creation with capacity = 0"""
        response = await async_client.post(
            "/api/v1/rooms/",
            json={
                "name": "ROOM999",
                "capacity": 0,  # Invalid - min is 1
                "room_type": "lecture_hall", "building": "Main"
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "capacity" in str(response.json()["detail"]).lower()
    
    async def test_create_room_excessive_capacity(self, async_client: AsyncClient, auth_headers: dict):
        """Test room creation with capacity > 1000"""
        response = await async_client.post(
            "/api/v1/rooms/",
            json={
                "name": "ROOM998",
                "capacity": 1500,  # Invalid - max is 1000
                "room_type": "lecture_hall", "building": "Main"
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "capacity" in str(response.json()["detail"]).lower()
    
    async def test_create_room_invalid_type(self, async_client: AsyncClient, auth_headers: dict):
        """Test room creation with invalid room_type"""
        response = await async_client.post(
            "/api/v1/rooms/",
            json={
                "name": "ROOM997",
                "capacity": 50,
                "room_type": "invalid_type"  # Invalid - must be lecture_hall, lab, or tutorial_room
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "type" in str(response.json()["detail"]).lower()
    
    async def test_create_room_empty_name(self, async_client: AsyncClient, auth_headers: dict):
        """Test room creation with empty name"""
        response = await async_client.post(
            "/api/v1/rooms/",
            json={
                "name": "",  # Invalid - cannot be empty
                "capacity": 50,
                "room_type": "lecture_hall", "building": "Main"
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "name" in str(response.json()["detail"]).lower()
    
    # ---------- HTTP 422: Invalid Foreign Key ----------
    
    async def test_create_room_invalid_department(self, async_client: AsyncClient, auth_headers: dict):
        """Test room creation with non-existent department_id"""
        response = await async_client.post(
            "/api/v1/rooms/",
            json={
                "name": "ROOM996",
                "capacity": 50,
                "room_type": "lab", "building": "Main",
                "department_id": 99999  # Doesn't exist
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "department" in str(response.json()["detail"]).lower()
    
    # ---------- HTTP 409: Duplicate Detection ----------
    
    async def test_create_room_duplicate_name(self, async_client: AsyncClient, auth_headers: dict):
        """Test that duplicate room names are rejected"""
        room_data = {
            "name": "DUPROOM",
            "capacity": 50,
            "room_type": "lecture_hall", "building": "Main"
        }
        
        # Create first room
        response1 = await async_client.post("/api/v1/rooms/", json=room_data, headers=auth_headers)
        assert response1.status_code in [200, 201]
        
        # Try to create duplicate
        response2 = await async_client.post("/api/v1/rooms/", json=room_data, headers=auth_headers)
        assert response2.status_code == 409
        assert "already exists" in str(response2.json()["detail"]).lower()
    
    # ---------- HTTP 404: Resource Not Found ----------
    
    async def test_update_nonexistent_room(self, async_client: AsyncClient, auth_headers: dict):
        """Test updating a room that doesn't exist"""
        response = await async_client.put(
            "/api/v1/rooms/99999",
            json={"capacity": 100},
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "not found" in str(response.json()["detail"]).lower()
    
    # ---------- Success Cases ----------
    
    async def test_create_room_valid_lecture_hall(self, async_client: AsyncClient, auth_headers: dict):
        """Test successful room creation - lecture hall"""
        response = await async_client.post(
            "/api/v1/rooms/",
            json={
                "name": "LH-VALID",
                "capacity": 150,
                "room_type": "lecture_hall", "building": "Main"
            },
            headers=auth_headers
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["name"] == "LH-VALID"
        assert data["capacity"] == 150
        assert data["room_type"] == "lecture_hall"
    
    async def test_create_room_valid_lab(self, async_client: AsyncClient, auth_headers: dict):
        """Test successful room creation - lab"""
        response = await async_client.post(
            "/api/v1/rooms/",
            json={
                "name": "LAB-VALID",
                "capacity": 30,
                "room_type": "lab", "building": "Main"
            },
            headers=auth_headers
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["room_type"] == "lab"
    
    async def test_create_room_valid_tutorial_room(self, async_client: AsyncClient, auth_headers: dict):
        """Test successful room creation - tutorial_room"""
        response = await async_client.post(
            "/api/v1/rooms/",
            json={
                "name": "TUT-VALID",
                "capacity": 25,
                "room_type": "tutorial_room", "building": "Main"
            },
            headers=auth_headers
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["room_type"] == "tutorial_room"


# ============================================================================
# GROUPS ROUTER VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
class TestGroupsValidation:
    """Test validation for student groups router"""
    
    # ---------- HTTP 422: Invalid Field Values ----------
    
    async def test_create_group_zero_size(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test group creation with size = 0"""
        response = await async_client.post(
            "/api/v1/groups/",
            json={
                "name": "GRP999",
                "department_id": get_department_id,
                "level": 200,
                "size": 0  # Invalid - min is 1
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "size" in str(response.json()["detail"]).lower()
    
    async def test_create_group_excessive_size(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test group creation with size > 500"""
        response = await async_client.post(
            "/api/v1/groups/",
            json={
                "name": "GRP998",
                "department_id": get_department_id,
                "level": 200,
                "size": 600  # Invalid - max is 500
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "size" in str(response.json()["detail"]).lower()
    
    async def test_create_group_invalid_level(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test group creation with invalid level"""
        response = await async_client.post(
            "/api/v1/groups/",
            json={
                "name": "GRP997",
                "department_id": get_department_id,
                "level": 150,  # Invalid - must be 100, 200, 300, 400, 500, or 600
                "size": 50
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "level" in str(response.json()["detail"]).lower()
    
    async def test_create_group_empty_name(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test group creation with empty name"""
        response = await async_client.post(
            "/api/v1/groups/",
            json={
                "name": "",  # Invalid - cannot be empty
                "department_id": get_department_id,
                "level": 200,
                "size": 50
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "name" in str(response.json()["detail"]).lower()
    
    # ---------- HTTP 422: Invalid Foreign Key ----------
    
    async def test_create_group_invalid_department(self, async_client: AsyncClient, auth_headers: dict):
        """Test group creation with non-existent department_id"""
        response = await async_client.post(
            "/api/v1/groups/",
            json={
                "name": "GRP996",
                "department_id": 99999,  # Doesn't exist
                "level": 200,
                "size": 50
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "department" in str(response.json()["detail"]).lower()
    
    # ---------- HTTP 409: Duplicate Detection ----------
    
    async def test_create_group_duplicate_name(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test that duplicate group names are rejected"""
        group_data = {
            "name": "DUPGRP",
            "department_id": get_department_id,
            "level": 200,
            "size": 50
        }
        
        # Create first group
        response1 = await async_client.post("/api/v1/groups/", json=group_data, headers=auth_headers)
        assert response1.status_code in [200, 201]
        
        # Try to create duplicate
        response2 = await async_client.post("/api/v1/groups/", json=group_data, headers=auth_headers)
        assert response2.status_code == 409
        assert "already exists" in str(response2.json()["detail"]).lower()
    
    # ---------- HTTP 404: Resource Not Found ----------
    
    async def test_update_nonexistent_group(self, async_client: AsyncClient, auth_headers: dict):
        """Test updating a group that doesn't exist"""
        response = await async_client.put(
            "/api/v1/groups/99999",
            json={"size": 100},
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "not found" in str(response.json()["detail"]).lower()
    
    # ---------- Success Cases ----------
    
    async def test_create_group_valid(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test successful group creation with valid data"""
        response = await async_client.post(
            "/api/v1/groups/",
            json={
                "name": "VALIDGRP",
                "department_id": get_department_id,
                "level": 300,
                "size": 75
            },
            headers=auth_headers
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["name"] == "VALIDGRP"
        assert data["level"] == 300
        assert data["size"] == 75
    
    async def test_create_group_minimum_size(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test group creation with minimum allowed size"""
        response = await async_client.post(
            "/api/v1/groups/",
            json={
                "name": "MINGRP",
                "department_id": get_department_id,
                "level": 200,
                "size": 1  # Minimum allowed
            },
            headers=auth_headers
        )
        assert response.status_code in [200, 201]
        assert response.json()["size"] == 1
    
    async def test_create_group_maximum_size(self, async_client: AsyncClient, auth_headers: dict, get_department_id: int):
        """Test group creation with maximum allowed size"""
        response = await async_client.post(
            "/api/v1/groups/",
            json={
                "name": "MAXGRP",
                "department_id": get_department_id,
                "level": 200,
                "size": 500  # Maximum allowed
            },
            headers=auth_headers
        )
        assert response.status_code in [200, 201]
        assert response.json()["size"] == 500


# ============================================================================
# DEPARTMENTS ROUTER VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
class TestDepartmentsValidation:
    """Test validation for departments router"""
    
    # ---------- HTTP 422: Invalid Field Values ----------
    
    async def test_create_department_empty_name(self, async_client: AsyncClient, auth_headers: dict):
        """Test department creation with empty name"""
        response = await async_client.post(
            "/api/v1/departments/",
            json={
                "code": "TEST",
                "name": ""  # Invalid - cannot be empty
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "name" in str(response.json()["detail"]).lower()
    
    async def test_create_department_empty_code(self, async_client: AsyncClient, auth_headers: dict):
        """Test department creation with empty code"""
        response = await async_client.post(
            "/api/v1/departments/",
            json={
                "code": "",  # Invalid - cannot be empty
                "name": "Test Department"
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "code" in str(response.json()["detail"]).lower()
    
    # ---------- HTTP 409: Duplicate Detection ----------
    
    async def test_create_department_duplicate_code(self, async_client: AsyncClient, auth_headers: dict):
        """Test that duplicate department codes are rejected"""
        dept_data = {
            "code": "DUPCODE",
            "name": "Duplicate Test Department"
        }
        
        # Create first department
        response1 = await async_client.post("/api/v1/departments/", json=dept_data, headers=auth_headers)
        assert response1.status_code in [200, 201]
        
        # Try to create duplicate code with different name
        response2 = await async_client.post(
            "/api/v1/departments/",
            json={"code": "DUPCODE", "name": "Different Name"},
            headers=auth_headers
        )
        assert response2.status_code == 409
        assert "already exists" in str(response2.json()["detail"]).lower()
    
    async def test_create_department_duplicate_name(self, async_client: AsyncClient, auth_headers: dict):
        """Test that duplicate department names are rejected"""
        # Create first department
        response1 = await async_client.post(
            "/api/v1/departments/",
            json={"code": "DEPT1", "name": "Unique Department Name 123"},
            headers=auth_headers
        )
        assert response1.status_code in [200, 201]
        
        # Try to create duplicate name with different code
        response2 = await async_client.post(
            "/api/v1/departments/",
            json={"code": "DEPT2", "name": "Unique Department Name 123"},
            headers=auth_headers
        )
        assert response2.status_code == 409
        assert "already exists" in str(response2.json()["detail"]).lower()
    
    # ---------- HTTP 404: Resource Not Found ----------
    
    async def test_delete_nonexistent_department(self, async_client: AsyncClient, auth_headers: dict):
        """Test deleting a department that doesn't exist"""
        response = await async_client.delete("/api/v1/departments/99999", headers=auth_headers)
        assert response.status_code == 404
        assert "not found" in str(response.json()["detail"]).lower()
    
    # ---------- Success Cases ----------
    
    async def test_create_department_valid(self, async_client: AsyncClient, auth_headers: dict):
        """Test successful department creation with valid data"""
        response = await async_client.post(
            "/api/v1/departments/",
            json={
                "code": "VALIDX",
                "name": "Valid Test Department X"
            },
            headers=auth_headers
        )
        # May already exist from seed data, so accept 200, 201, or 409
        assert response.status_code in [200, 201, 409]
        if response.status_code in [200, 201]:
            data = response.json()
            assert data["code"] == "VALIDX"
            assert data["name"] == "Valid Test Department X"
    
    async def test_create_multiple_departments_different_codes(self, async_client: AsyncClient, auth_headers: dict):
        """Test creating multiple departments with unique codes and names"""
        # Create first department
        response1 = await async_client.post(
            "/api/v1/departments/",
            json={"code": "MULTI1", "name": "Multi Department One"},
            headers=auth_headers
        )
        assert response1.status_code in [200, 201]
        
        # Create second department with different code and name
        response2 = await async_client.post(
            "/api/v1/departments/",
            json={"code": "MULTI2", "name": "Multi Department Two"},
            headers=auth_headers
        )
        assert response2.status_code in [200, 201]
        
        # Both should succeed
        assert response1.json()["code"] != response2.json()["code"]
        assert response1.json()["name"] != response2.json()["name"]
    
    async def test_get_all_departments(self, async_client: AsyncClient, auth_headers: dict):
        """Test retrieving all departments"""
        response = await async_client.get("/api/v1/departments/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least the departments we created
        assert len(data) >= 1
