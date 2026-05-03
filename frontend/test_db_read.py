from app.database import SessionLocal
from app.models import Notification

db = SessionLocal()
try:
    c = db.query(Notification).count()
    print(f"Total count: {c}")
    items = db.query(Notification).order_by(Notification.created_at.desc()).limit(5).all()
    for n in items:
        print(f"ID:{n.id} Read:{n.is_read} C_AT:{type(n.created_at)} {n.created_at} R_AT:{type(n.read_at)} {n.read_at}")
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
