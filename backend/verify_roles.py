from app.database import SessionLocal
from app.models import User, UserRole

def verify_roles():
    db = SessionLocal()
    for username in ['coordinator', 'admin']:
        user = db.query(User).filter(User.username == username).first()
        if user:
            print(f"\nUser: {username}")
            print(f"Role: {user.role}")
            print(f"Role type: {type(user.role)}")
            print(f"Comparison with 'coordinator': {user.role == 'coordinator'}")
            print(f"Comparison with UserRole.COORDINATOR: {user.role == UserRole.COORDINATOR}")
        else:
            print(f"User '{username}' not found.")
    db.close()

if __name__ == "__main__":
    verify_roles()
