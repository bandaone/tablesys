import os
import sys

sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models import User
from app.services.dashboard_service import DashboardService
from sqlalchemy import func
from app.models import Course, Lecturer

db = SessionLocal()
user = db.query(User).filter(User.university_id == 2).first()
if not user:
    print("No user for univ 2")
    sys.exit(0)

print(f"Testing with user: {user.username}, university_id: {user.university_id}")

service = DashboardService(db, user)
course_count = service._course_query().with_entities(func.count(Course.id)).scalar()
print("Course Count:", course_count)

lecturer_count = service._lecturer_query().with_entities(func.count(Lecturer.id)).scalar()
print("Lecturer Count:", lecturer_count)

