from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Create database connection
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/tablesys')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Query departments with user counts
result = db.execute(text("""
    SELECT d.id, d.code, d.name, COUNT(u.id) as user_count
    FROM departments d
    LEFT JOIN users u ON d.id = u.department_id
    GROUP BY d.id, d.code, d.name
    ORDER BY d.code
"""))
depts = result.fetchall()

print('\n' + '='*70)
print('DEPARTMENTS WITH USER COUNTS')
print('='*70)
for d in depts:
    safe = "✅ SAFE TO DELETE" if d[3] == 0 else f"⚠️  {d[3]} users"
    print(f"ID: {d[0]:2} | Code: {d[1]:6} | Users: {d[3]:2} | {safe}")
    print(f"     Name: {d[2]}")
print('='*70 + '\n')

db.close()
