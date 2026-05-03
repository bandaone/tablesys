import asyncio
from app.database import SessionLocal
from app.models import User
from app.services.notification_service import NotificationService

db = SessionLocal()
service = NotificationService(db)
admin = db.query(User).filter(User.username == 'admin').first()
if not admin:
    admin = db.query(User).first()

if admin:
    print(f"Creating notification for user: {admin.username}")
    notif = service.create_notification(admin.id, "Test", "This is a test notification")
    db.commit()
    print("Notification created!")
    
    notifs = service.get_user_notifications(admin.id)
    print(notifs)
