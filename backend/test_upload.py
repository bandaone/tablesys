import pandas as pd
from app.database import SessionLocal
from app.models import Course, Department, Lecturer
import re

db = SessionLocal()
departments = db.query(Department).all()
courses = db.query(Course).all()

df = pd.read_excel("/app/lecturers_register.xlsx")
df.columns = [c.strip().lower() for c in df.columns]
rename_map = {
    "staff number": "staff_number",
    "full name": "full_name",
    "department name": "department_name",
}
df = df.rename(columns=rename_map)

for idx, row in df.iterrows():
    staff_number = str(row.get("staff_number")).strip()
    full_name = str(row.get("full_name")).strip()
    dept_name = str(row.get("department_name")).strip()
    
    # Try to find existing
    existing = db.query(Lecturer).filter(Lecturer.staff_number == staff_number).first()
    if existing:
        print(f"Row {idx+2}: {staff_number} EXISTS IN DB ALREADY!")
    
    print(f"Row {idx+2}: Attempting to process {staff_number} / {dept_name}")

db.close()
