import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.models import User, UserRole
from app.auth import get_current_active_hod

client = TestClient(app)

def override_get_current_active_hod():
    return User(id=1, username="coord", role=UserRole.COORDINATOR, department_id=0, university_id=1, is_active=True)

app.dependency_overrides[get_current_active_hod] = override_get_current_active_hod

with open("engineering_courses_master_corrected.csv", "rb") as f:
    files = {"file": ("engineering_courses_master_corrected.csv", f, "text/csv")}
    response = client.post("/api/v1/courses/bulk-upload", files=files)
    print(response.status_code)
    print(response.json())
