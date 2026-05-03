import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from app.database import engine, SessionLocal
from app.models import User
from app.auth import authenticate_user

db = SessionLocal()

print("Connecting to DB...")
start = time.time()
user = db.query(User).first()
print(f"DB connection took: {time.time() - start:.4f}s")
if not user:
    print("No user found")
    sys.exit(0)

print(f"Testing auth for user: {user.username}")

start = time.time()
res = authenticate_user(db, user.username, "admin123") # Assuming default password or just check time
duration = time.time() - start

print(f"Authenticate takes: {duration:.4f}s")
print("Result:", res is not None)
