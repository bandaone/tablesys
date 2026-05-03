"""
Authentication and authorization tests for TABLESYS - Checkpoint 1.7

Tests password authentication and role-based access control.
"""

import pytest
from httpx import AsyncClient


# ============================================================================
# PASSWORD AUTHENTICATION TESTS (Checkpoint 1.1)
# ============================================================================

@pytest.mark.auth
@pytest.mark.asyncio
class TestPasswordAuthentication:
    """Test password-based authentication"""
    
    async def test_valid_login_returns_token(self, async_client: AsyncClient):
        """Test that valid credentials return JWT token"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "coordinator", "password": "pass"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
    
    async def test_invalid_username_returns_401(self, async_client: AsyncClient):
        """Test that invalid username returns 401"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "pass"}
        )
        assert response.status_code == 401
    
    async def test_invalid_password_returns_401(self, async_client: AsyncClient):
        """Test that invalid password returns 401"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "coordinator", "password": "wrong"}
        )
        assert response.status_code == 401
    
    async def test_empty_credentials_returns_error(self, async_client: AsyncClient):
        """Test that empty credentials return validation error"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "", "password": ""}
        )
        assert response.status_code in [400, 401, 422]
    
    async def test_token_validation(self, async_client: AsyncClient, auth_headers: dict):
        """Test that valid token can access protected endpoints"""
        response = await async_client.get(
            "/api/v1/auth/me",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "username" in data
        assert data["username"] == "coordinator"
    
    async def test_invalid_token_returns_401(self, async_client: AsyncClient):
        """Test that invalid token returns 401"""
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401


# ============================================================================
# ROLE-BASED ACCESS CONTROL TESTS
# ============================================================================

@pytest.mark.auth
@pytest.mark.asyncio
class TestRoleBasedAccess:
    """Test role-based access control"""
    
    async def test_coordinator_can_access_all_endpoints(self, async_client: AsyncClient, auth_headers: dict):
        """Test that coordinator can access all endpoints"""
        # Test courses endpoint
        response = await async_client.get("/api/v1/courses/", headers=auth_headers)
        assert response.status_code == 200
        
        # Test lecturers endpoint
        response = await async_client.get("/api/v1/lecturers/", headers=auth_headers)
        assert response.status_code == 200
        
        # Test rooms endpoint
        response = await async_client.get("/api/v1/rooms/", headers=auth_headers)
        assert response.status_code == 200
    
    async def test_hod_can_access_their_department(self, async_client: AsyncClient, hod_headers: dict):
        """Test that HOD can access their department data"""
        response = await async_client.get("/api/v1/courses/", headers=hod_headers)
        assert response.status_code == 200
    
    async def test_unauthenticated_requests_return_401(self, async_client: AsyncClient):
        """Test that unauthenticated requests return 401"""
        # Try to access protected endpoint without token
        response = await async_client.get("/api/v1/courses/")
        # Should return 401 or redirect to login
        assert response.status_code in [401, 403, 307]
    
    async def test_get_current_user_info(self, async_client: AsyncClient, auth_headers: dict):
        """Test getting current user information"""
        response = await async_client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "coordinator"
        assert data["role"] == "coordinator"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "auth"])

