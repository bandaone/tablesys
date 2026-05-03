import asyncio
from app.database import SessionLocal
from app.models import Department
db = SessionLocal()
depts = db.query(Department).all()
for d in depts:
    print(f"ID: {d.id}, Code: {d.code}, Name: {d.name}")
