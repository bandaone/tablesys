"""
Initial data seeding script for TABLESYS
Creates predefined users for easy access (username-only, no password)
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import Base, User, Department, UserRole
from app.auth import get_password_hash

def seed_database():
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Create sample departments first
        departments_data = [
            {"name": "Computer Science", "code": "CS"},
            {"name": "Mathematics", "code": "MATH"},
            {"name": "Mechanical Engineering", "code": "MEC"},
            {"name": "Electrical Engineering", "code": "ELE"},
            {"name": "Civil Engineering", "code": "CIV"},
            {"name": "Physics", "code": "PHY"},
            {"name": "Chemistry", "code": "CHEM"},
            {"name": "Biology", "code": "BIO"},
        ]
        
        dept_map = {}
        for dept_data in departments_data:
            existing = db.query(Department).filter(Department.code == dept_data["code"]).first()
            if not existing:
                dept = Department(**dept_data)
                db.add(dept)
                db.flush()
                dept_map[dept_data["code"]] = dept.id
                print(f"✓ Created department: {dept_data['name']}")
            else:
                dept_map[dept_data["code"]] = existing.id
        
        db.commit()
        
        # Create predefined users (username-only access)
        users_data = [
            # Coordinators
            {
                "username": "coordinator",
                "email": "coordinator@unza.zm",
                "full_name": "System Coordinator",
                "role": UserRole.COORDINATOR,
                "department_id": None
            },
            {
                "username": "admin",
                "email": "admin@unza.zm",
                "full_name": "System Administrator",
                "role": UserRole.COORDINATOR,
                "department_id": None
            },
            
            # HODs for each department
            {
                "username": "CS",
                "email": "hod.cs@unza.zm",
                "full_name": "Computer Science HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("CS")
            },
            {
                "username": "MATH",
                "email": "hod.math@unza.zm",
                "full_name": "Mathematics HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("MATH")
            },
            {
                "username": "MEC",
                "email": "hod.mec@unza.zm",
                "full_name": "Mechanical Engineering HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("MEC")
            },
            {
                "username": "ELE",
                "email": "hod.ele@unza.zm",
                "full_name": "Electrical Engineering HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("ELE")
            },
            {
                "username": "CIV",
                "email": "hod.civ@unza.zm",
                "full_name": "Civil Engineering HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("CIV")
            },
            {
                "username": "PHY",
                "email": "hod.phy@unza.zm",
                "full_name": "Physics HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("PHY")
            },
            {
                "username": "CHEM",
                "email": "hod.chem@unza.zm",
                "full_name": "Chemistry HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("CHEM")
            },
            {
                "username": "BIO",
                "email": "hod.bio@unza.zm",
                "full_name": "Biology HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("BIO")
            },
        ]
        
        for user_data in users_data:
            existing_user = db.query(User).filter(User.username == user_data["username"]).first()
            
            if not existing_user:
                # Create user (password not used but still stored for compatibility)
                user = User(
                    email=user_data["email"],
                    username=user_data["username"],
                    hashed_password=get_password_hash("unused"),  # Not used for auth
                    full_name=user_data["full_name"],
                    role=user_data["role"],
                    department_id=user_data["department_id"],
                    is_active=True
                )
                db.add(user)
                role_name = "Coordinator" if user_data["role"] == UserRole.COORDINATOR else "HOD"
                print(f"✓ Created user: {user_data['username']} ({role_name})")
        
        db.commit()
        print("\n✅ Database seeded successfully!")
        print("\n" + "="*60)
        print("SIMPLE USERNAME-ONLY ACCESS (No Password Required)")
        print("="*60)
        print("\nCOORDINATORS (Full Access):")
        print("  • coordinator")
        print("  • admin")
        print("\nHODs (Department-Specific Access):")
        print("  • CS    - Computer Science HOD")
        print("  • MATH  - Mathematics HOD")
        print("  • MEC   - Mechanical Engineering HOD")
        print("  • ELE   - Electrical Engineering HOD")
        print("  • CIV   - Civil Engineering HOD")
        print("  • PHY   - Physics HOD")
        print("  • CHEM  - Chemistry HOD")
        print("  • BIO   - Biology HOD")
        print("\nJust enter the username - no password needed!")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🌱 Seeding database...")
    seed_database()
