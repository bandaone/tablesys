from app.database import SessionLocal
from app.models import User
from app.auth import get_password_hash

db = SessionLocal()
try:
    user = db.query(User).filter(User.username == 'superadmin').first()
    if user:
        user.hashed_password = get_password_hash('K3yp@ssw0rd!')
        db.commit()
        print('Password reset successfully!')
    else:
        print('Superadmin not found!')
finally:
    db.close()
