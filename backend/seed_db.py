"""
Initial data seeding script for TABLESYS
Creates predefined users for easy access (username-only, no password)
"""
from app.database import SessionLocal, engine
from app.models import Base, User, Department, UserRole
from app.auth import get_password_hash

def seed_database():
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Create School of Engineering departments
        departments_data = [
            {"name": "Agricultural Engineering", "code": "AEN"},
            {"name": "Mechanical Engineering", "code": "MEC"},
            {"name": "Electrical & Electronics Engineering", "code": "EEE"},
            {"name": "Civil & Environmental Engineering", "code": "CEE"},
            {"name": "Geomatics Engineering", "code": "GEE"},
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
                "email": "",
                "full_name": "System Coordinator",
                "role": UserRole.COORDINATOR,
                "department_id": None
            },
            {
                "username": "admin",
                "email": "",
                "full_name": "System Administrator",
                "role": UserRole.COORDINATOR,
                "department_id": None
            },
            
            # HODs for each department
            {
                "username": "AEN",
                "email": "",
                "full_name": "Agricultural Engineering HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("AEN")
            },
            {
                "username": "MEC",
                "email": "",
                "full_name": "Mechanical Engineering HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("MEC")
            },
            {
                "username": "EEE",
                "email": "",
                "full_name": "Electrical & Electronics Engineering HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("EEE")
            },
            {
                "username": "CEE",
                "email": "",
                "full_name": "Civil & Environmental Engineering HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("CEE")
            },
            {
                "username": "GEE",
                "email": "",
                "full_name": "Geomatics Engineering HOD",
                "role": UserRole.HOD,
                "department_id": dept_map.get("GEE")
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
        print("  • AEN   - Agricultural Engineering HOD")
        print("  • MEC   - Mechanical Engineering HOD")
        print("  • EEE   - Electrical & Electronics Engineering HOD")
        print("  • CEE   - Civil & Environmental Engineering HOD")
        print("  • GEE   - Geomatics Engineering HOD")
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
