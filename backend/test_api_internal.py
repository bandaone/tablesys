from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User

client = TestClient(app)
db = SessionLocal()

# Mock the dependency directly
def override_get_user():
    return db.query(User).filter_by(username="BMunkombwe").first()

app.dependency_overrides = {}
from app.auth import get_current_user
app.dependency_overrides[get_current_user] = override_get_user

try:
    response = client.get("/api/v1/lecturers?skip=0&limit=10")
    print(response.status_code)
    print(response.json()[0] if response.json() else "Empty")
finally:
    db.close()
