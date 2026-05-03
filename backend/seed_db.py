"""
Reset and Initial data seeding script for TABLESYS
WARNING: THIS DROPS ALL TABLES AND CREATES A FRESH STATE WITH ONE SUPERADMIN.
"""
import os
import sys

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app.models import Base, User, UserRole
from app.auth import get_password_hash

def reset_and_seed_database():
    # 1. Drop all tables to guarantee a fresh state
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    # 2. Recreate all tables
    print("Recreating tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # 3. Create SuperAdmin
        print("\nSeeding SuperAdmin...")
        
        superadmin = User(
            email="superadmin@tablesys.com",
            username="superadmin",
            hashed_password=get_password_hash("Admin123!"),
            full_name="TABLESYS Super Administrator",
            role=UserRole.SUPERADMIN,
            is_active=True
        )
        db.add(superadmin)
        db.commit()
        
        print(f"Created SuperAdmin:")
        print(f"Username: superadmin")
        print(f"Password: Admin123!")
        
        print("\nDatabase reset and seeded successfully! System is clean.")
        
    except Exception as e:
        print(f"Error resetting database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_and_seed_database()
