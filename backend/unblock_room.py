from app.database import SessionLocal
from app.models import Room
db = SessionLocal()
r = db.query(Room).filter(Room.id == 35).first()
if r:
    r.is_blocked = False
    db.commit()
    print("Room unblocked")
