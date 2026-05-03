from app.database import SessionLocal
from app.models import User
db = SessionLocal()
for u in db.query(User).all():
    print(repr(u.role))
