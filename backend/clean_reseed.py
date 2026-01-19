"""
Clean re-seed script for TABLESYS
Wipes conflicting tables and re-initializes with correct IDs
"""
from app.database import SessionLocal, engine
from app.models import Base, User, Department, UserRole, LecturerAssignment, GroupAssignment, StudentGroup, Lecturer
from app.auth import get_password_hash

def clean_reseed():
    db = SessionLocal()
    try:
        print("Cleaning up existing data...")
        print("Cleaning up existing data...")
        # Drop all tables to ensure schema updates are applied
        Base.metadata.drop_all(bind=engine)
        # Re-create all tables
        Base.metadata.create_all(bind=engine)
        print("Schema update and cleanup successful.")
        print("Cleanup successful.")
        
        # Expected Mapping:
        # 0: GEN - General
        # 1: AEN - Agricultural Engineering
        # 2: CEE - Civil and Environmental Engineering
        # 3: EEE - Electrical and Electronic Engineering
        # 4: GEE - Geomatics Engineering
        # 5: MEC - Mechanical Engineering
        
        departments_data = [
            {"id": 0, "name": "General", "code": "GEN"},
            {"id": 1, "name": "Agricultural Engineering", "code": "AEN"},
            {"id": 2, "name": "Civil & Environmental Engineering", "code": "CEE"},
            {"id": 3, "name": "Electrical & Electronics Engineering", "code": "EEE"},
            {"id": 4, "name": "Geomatics Engineering", "code": "GEE"},
            {"id": 5, "name": "Mechanical Engineering", "code": "MEC"},
        ]
        
        print("\nSeeding departments...")
        for dept_data in departments_data:
            dept = Department(id=dept_data["id"], name=dept_data["name"], code=dept_data["code"])
            db.add(dept)
            print(f"Created department ID {dept_data['id']}: {dept_data['code']}")
        
        db.commit()
        
        # Create predefined users
        users_data = [
            {"username": "coordinator", "email": "coordinator@tablesys.local", "name": "System Coordinator", "role": UserRole.COORDINATOR, "dept": None},
            {"username": "admin", "email": "admin@tablesys.local", "name": "System Administrator", "role": UserRole.COORDINATOR, "dept": None},
            {"username": "GEN", "email": "gen@tablesys.local", "name": "General Department HOD", "role": UserRole.HOD, "dept": 0},
            {"username": "AEN", "email": "aen@tablesys.local", "name": "Agricultural Engineering HOD", "role": UserRole.HOD, "dept": 1},
            {"username": "CEE", "email": "cee@tablesys.local", "name": "Civil Engineering HOD", "role": UserRole.HOD, "dept": 2},
            {"username": "EEE", "email": "eee@tablesys.local", "name": "Electrical Engineering HOD", "role": UserRole.HOD, "dept": 3},
            {"username": "GEE", "email": "gee@tablesys.local", "name": "Geomatics Engineering HOD", "role": UserRole.HOD, "dept": 4},
            {"username": "MEC", "email": "mec@tablesys.local", "name": "Mechanical Engineering HOD", "role": UserRole.HOD, "dept": 5},
        ]
        
        print("\nSeeding users...")
        for user_data in users_data:
            user = User(
                email=user_data["email"],
                username=user_data["username"],
                hashed_password=get_password_hash("pass"),
                full_name=user_data["name"],
                role=user_data["role"],
                department_id=user_data["dept"],
                is_active=True
            )
            db.add(user)
            print(f"Created user: {user_data['username']}")
        
        db.commit()
        print("\nDatabase clean re-seeded successfully!")
        
    except Exception as e:
        print(f"Error during re-seed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clean_reseed()
