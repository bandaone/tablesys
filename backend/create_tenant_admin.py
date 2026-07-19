import sys
import os

from app.database import SessionLocal
from app.models import User, UserRole, University
from app.auth import get_password_hash

def create_tenant_admin(university_id: int, username: str, email: str, password: str):
    db = SessionLocal()
    try:
        # Check if uni exists
        uni = db.query(University).filter(University.id == university_id).first()
        if not uni:
            print(f"[-] Error: University with ID {university_id} not found.")
            return

        # Check if user already exists
        if db.query(User).filter(User.username == username).first():
            print(f"[-] Error: Username '{username}' already exists.")
            return

        new_user = User(
            username=username,
            email=email,
            full_name=username.replace("_", " ").title(),
            hashed_password=get_password_hash(password),
            role=UserRole.TENANT_ADMIN,
            university_id=university_id,
            is_active=True
        )
        db.add(new_user)
        db.commit()
        print(f"[+] Successfully created TENANT_ADMIN '{username}' for {uni.name}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python create_tenant_admin.py <university_id> <username> <email> <password>")
        sys.exit(1)
    
    create_tenant_admin(int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4])
