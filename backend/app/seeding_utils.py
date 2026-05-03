from app.database import SessionLocal
from app.models import User, UserRole, Department, Lecturer
from app.auth import get_password_hash
from app.config import settings

def seed_database_at_startup():
    db = SessionLocal()
    try:
        # 0. Auto-seed SUPERADMIN from environment variables
        #    Only runs once — skipped if any SUPERADMIN already exists.
        if settings.SUPERADMIN_USERNAME and settings.SUPERADMIN_EMAIL and settings.SUPERADMIN_PASSWORD:
            existing_superadmin = db.query(User).filter(User.role == UserRole.SUPERADMIN).first()
            if not existing_superadmin:
                print("[*] No SUPERADMIN found. Creating platform super-admin from environment variables...")
                superadmin = User(
                    username=settings.SUPERADMIN_USERNAME,
                    email=settings.SUPERADMIN_EMAIL,
                    full_name="Platform Administrator",
                    role=UserRole.SUPERADMIN,
                    hashed_password=get_password_hash(settings.SUPERADMIN_PASSWORD),
                    is_active=True,
                    university_id=None,  # SUPERADMIN belongs to no single university
                )
                db.add(superadmin)
                db.commit()
                print(f"[+] SUPERADMIN created: {settings.SUPERADMIN_USERNAME}")
            else:
                print("[*] SUPERADMIN already exists — skipping seed.")

        print("[+] Automatic seeding completed successfully.")
        
    except Exception as e:
        print(f"[-] Error during automatic seeding: {e}")
        db.rollback()
    finally:
        db.close()
