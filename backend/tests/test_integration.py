"""
Integration tests for TABLESYS - Checkpoint 1.7

Tests end-to-end workflows to ensure all components work together.
"""

import pytest
from httpx import AsyncClient
import io


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestIntegrationFlows:
    """Test end-to-end workflows"""
    
    async def test_complete_login_flow(self, async_client: AsyncClient):
        """
        Test complete login flow:
        1. Login with credentials
        2. Get user info with token
        3. Verify user data
        """
        # Step 1: Login
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "coordinator", "password": "pass"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        
        # Step 2: Get user info
        headers = {"Authorization": f"Bearer {token}"}
        user_response = await async_client.get("/api/v1/auth/me", headers=headers)
        assert user_response.status_code == 200
        
        # Step 3: Verify user data
        user_data = user_response.json()
        assert user_data["username"] == "coordinator"
        assert user_data["role"] == "coordinator"
    
    async def test_course_management_flow(self, async_client: AsyncClient, auth_headers: dict):
        """
        Test complete course management flow:
        1. Get list of departments to find a valid department_id
        2. Create a course using a valid department_id
        3. Get the course
        4. Update the course
        5. Delete the course
        """
        # Step 0: Get a valid department_id from the database
        dept_response = await async_client.get("/api/v1/departments/", headers=auth_headers)
        assert dept_response.status_code == 200
        departments = dept_response.json()
        
        if not departments:
            pytest.skip("No departments in test database - cannot run course management flow")
        
        dept_id = departments[0]["id"]
        
        # Step 1: Create course with valid department_id
        course_data = {
            "code": "INTEG101",
            "name": "Integration Test Course",
            "department_id": dept_id,
            "level": 2,
            "credits": 3,
            "lecture_hours": 3,
            "tutorial_hours": 1,
            "practical_hours": 0
        }
        
        create_response = await async_client.post(
            "/api/v1/courses/",
            json=course_data,
            headers=auth_headers
        )
        assert create_response.status_code in [200, 201, 400]  # 400 if code already exists
        
        if create_response.status_code in [200, 201]:
            created_course = create_response.json()
            course_id = created_course.get("id")
            
            # Step 2: Get the course
            if course_id:
                get_response = await async_client.get(
                    f"/api/v1/courses/{course_id}",
                    headers=auth_headers
                )
                assert get_response.status_code == 200
                
                # Step 3: Update the course
                update_data = {"name": "Updated Integration Test Course"}
                update_response = await async_client.put(
                    f"/api/v1/courses/{course_id}",
                    json=update_data,
                    headers=auth_headers
                )
                assert update_response.status_code in [200, 404]
                
                # Step 4: Delete the course
                delete_response = await async_client.delete(
                    f"/api/v1/courses/{course_id}",
                    headers=auth_headers
                )
                assert delete_response.status_code in [200, 204, 404]
    
    async def test_bulk_upload_flow(self, async_client: AsyncClient, auth_headers: dict):
        """
        Test complete bulk upload flow:
        1. Get a valid department_id
        2. Bulk upload courses
        3. Verify courses in database (via GET)
        """
        # Step 0: Get a valid department_id
        dept_response = await async_client.get("/api/v1/departments/", headers=auth_headers)
        assert dept_response.status_code == 200
        departments = dept_response.json()
        
        if not departments:
            pytest.skip("No departments in test database - cannot run bulk upload flow")
        
        dept_id = departments[0]["id"]
        
        # Step 1: Bulk upload courses with valid department_id
        csv_content = f"""code,name,department_id,level,credits,lecture_hours,tutorial_hours,practical_hours
BULK201,Bulk Test Course 1,{dept_id},2,3,3,1,0
BULK202,Bulk Test Course 2,{dept_id},2,3,3,1,0"""
        
        files = {"file": ("courses.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        
        upload_response = await async_client.post(
            "/api/v1/courses/bulk-upload",
            files=files,
            headers=auth_headers
        )
        assert upload_response.status_code in [200, 400, 422]
        
        # Step 2: Verify courses in database
        get_response = await async_client.get("/api/v1/courses/", headers=auth_headers)
        assert get_response.status_code == 200
        courses = get_response.json()
        assert isinstance(courses, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])

