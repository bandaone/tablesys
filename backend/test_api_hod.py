import asyncio
from app.database import SessionLocal
from app.models import User
from app.auth import create_access_token
from datetime import timedelta

db = SessionLocal()
user = db.query(User).filter_by(username='hodeee').first()
access_token = create_access_token(
    data={"sub": user.username, "roles": [user.role.value]},
    expires_delta=timedelta(minutes=30)
)
print(access_token)
