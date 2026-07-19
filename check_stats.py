from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
sys.path.append('/app')
from backend.app.database import engine, SessionLocal
from backend.app.models import User, Timetable, Lecturer, TimetableSlot
from backend.app.services.dashboard_service import DashboardService

db = SessionLocal()
admin_user = db.query(User).filter(User.username == "bandaone").first()
if not admin_user:
    admin_user = db.query(User).first()

print(f"Testing as User: {admin_user.username} (Role: {admin_user.role}, Uni: {admin_user.university_id}, School: {admin_user.school_id})")

service = DashboardService(db, admin_user)

print("Overview:")
print(service.get_overview_stats())
print("Resources:")
print(service.get_resource_utilization())
