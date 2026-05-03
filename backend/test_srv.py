import sys
import os

from sqlalchemy.orm import Session
from sqlalchemy import create_engine

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models import Notification, User
from app.config import settings
from app.services.notification_service import NotificationService

engine = create_engine(settings.DATABASE_URL)
with Session(engine) as db:
    users = db.query(User).all()
    print("Users: ", [u.username for u in users])
    
    # We test user 2 (coordinator)
    srv = NotificationService(db)
    notifs = srv.get_user_notifications(user_id=2, unread_only=False, limit=20)
    print("Notifs user 2:", notifs)
