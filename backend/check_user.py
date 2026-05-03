from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Create database connection
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/tablesys')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Check if username "Dennis" exists
result = db.execute(text("SELECT id, username, email, full_name, role FROM users WHERE username = :name"), {"name": "Dennis"})
user = result.fetchone()

if user:
    print(f'\n❌ USERNAME ALREADY EXISTS:')
    print(f'   ID: {user[0]}')
    print(f'   Username: {user[1]}')
    print(f'   Email: {user[2]}')
    print(f'   Full Name: {user[3]}')
    print(f'   Role: {user[4]}')
    print('\n⚠️  Cannot create duplicate username. Try a different username.\n')
else:
    print('\n✅ Username "Dennis" is available\n')

# Also show all existing usernames
print('='*60)
print('ALL EXISTING USERS:')
print('='*60)
result = db.execute(text("SELECT username, email, full_name FROM users ORDER BY username"))
users = result.fetchall()
for u in users:
    print(f'  • {u[0]:15} | {u[1]:30} | {u[2]}')
print('='*60 + '\n')

db.close()
