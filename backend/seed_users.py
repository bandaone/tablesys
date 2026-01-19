
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from app.auth import get_password_hash
from app.models import User, UserRole, Department
from app.database import SessionLocal

def seed_users():
    db = SessionLocal()
    try:
        # 1. Ensure Departments Exist
        departments = [
            {"name": "General", "code": "GEN"},
            {"name": "Agricultural Engineering", "code": "AEN"},
            {"name": "Civil and Environmental Engineering", "code": "CEE"},
            {"name": "Electrical and Electronic Engineering", "code": "EEE"},
            {"name": "Geomatic Engineering", "code": "GEE"},
            {"name": "Mechanical Engineering", "code": "MEC"},
        ]
        
        dept_map = {}
        for d in departments:
            dept = db.query(Department).filter(Department.code == d["code"]).first()
            if not dept:
                print(f"[*] Creating Department: {d['name']}")
                dept = Department(name=d["name"], code=d["code"])
                db.add(dept)
                db.commit()
                db.refresh(dept)
            dept_map[d["code"]] = dept.id

        # 2. Coordinator
        user = db.query(User).filter(User.username == "coordinator").first()
        if not user:
            print("[*] Creating 'coordinator' user...")
            user = User(
                username="coordinator",
                email="coordinator@unza.zm",
                full_name="Timetable Coordinator",
                role=UserRole.COORDINATOR,
                hashed_password=get_password_hash("pass"),
                is_active=True
            )
            db.add(user)
            db.commit()
            print("[+] User 'coordinator' created.")

        # 3. HODs
        for code, dept_id in dept_map.items():
            username = f"hod_{code.lower()}"
            user = db.query(User).filter(User.username == username).first()
            if not user:
                print(f"[*] Creating HOD user: {username}...")
                user = User(
                    username=username,
                    email=f"{username}@unza.zm",
                    full_name=f"HOD {code}",
                    role=UserRole.HOD,
                    department_id=dept_id,
                    hashed_password=get_password_hash("pass"),
                    is_active=True
                )
                db.add(user)
                db.commit()
                print(f"[+] User '{username}' created.")
        
    except Exception as e:
        print(f"[-] Error seeding users: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    seed_users()
