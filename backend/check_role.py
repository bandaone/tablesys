from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import json

# Create database connection
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/tablesys')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Check Dennis's role - get the actual string value
result = db.execute(text("SELECT role FROM users WHERE username = 'Dennis'"))
role = result.fetchone()

print(f"\nDennis's role value: '{role[0]}'")
print(f"Type: {type(role[0])}")
print(f"Repr: {repr(role[0])}")

db.close()
