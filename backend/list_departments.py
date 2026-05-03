from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Create database connection
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/tablesys')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Query departments
result = db.execute(text("SELECT id, code, name FROM departments ORDER BY code"))
depts = result.fetchall()

print('\n' + '='*60)
print('AVAILABLE DEPARTMENTS')
print('='*60)
for d in depts:
    print(f"ID: {d[0]:2} | Code: {d[1]:6} | Name: {d[2]}")
print('='*60 + '\n')

db.close()
