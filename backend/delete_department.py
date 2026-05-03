from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import sys

if len(sys.argv) < 2:
    print("Usage: python delete_department.py <department_id>")
    sys.exit(1)

dept_id = int(sys.argv[1])

# Create database connection
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/tablesys')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    # Check if department exists
    result = db.execute(text("SELECT id, code, name FROM departments WHERE id = :id"), {"id": dept_id})
    dept = result.fetchone()
    
    if not dept:
        print(f"\n❌ Department with ID {dept_id} not found!")
        sys.exit(1)
    
    print(f"\n🗑️  Deleting department:")
    print(f"   ID: {dept[0]} | Code: {dept[1]} | Name: {dept[2]}")
    
    # Delete the department
    db.execute(text("DELETE FROM departments WHERE id = :id"), {"id": dept_id})
    db.commit()
    
    print(f"✅ Department deleted successfully!\n")
    
except Exception as e:
    db.rollback()
    print(f"\n❌ Error deleting department: {str(e)}\n")
    sys.exit(1)
finally:
    db.close()
