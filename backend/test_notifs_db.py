import sys
import os

from sqlalchemy.orm import Session
from sqlalchemy import create_engine

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models import Notification, User
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
with Session(engine) as db:
    users = db.query(User).all()
    count = db.query(Notification).count()
    print("Total users:", len(users))
    print("Total notifications in DB:", count)
    
    # Check top 5 notifications
    notifs = db.query(Notification).limit(5).all()
    for n in notifs:
        print(f"Notif {n.id} for user {n.user_id}: unread={not n.is_read}, title={n.title}")

