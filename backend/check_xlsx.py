import pandas as pd
from app.database import SessionLocal
from app.models import Course, Department

db = SessionLocal()
departments = db.query(Department).all()
courses = db.query(Course).all()
course_code_map = {c.code.upper(): c.id for c in courses}

df = pd.read_excel("/app/lecturers_register.xlsx")
import re
errors = []

df.columns = [c.strip().lower() for c in df.columns]
aliases = {
    "staff number": "staff_number",
    "staff_no": "staff_number",
    "full name": "full_name",
    "department": "department_id",
    "courses responsible for": "courses",
    "teaching": "courses"
}
rename_map = {col: aliases[col] for col in df.columns if col in aliases}
df = df.rename(columns=rename_map)

for idx, row in df.iterrows():
    raw_courses = str(row.get("courses", "") or "").strip()
    if raw_courses and raw_courses.lower() not in ("nan", "none", "-", ""):
        codes = [c.strip().upper() for c in re.split(r'[,;]+', raw_courses) if c.strip()]
        for code in codes:
            if code not in course_code_map:
                errors.append(f"Row {idx + 2} ({row.get('staff_number')}): '{code}' lookup failed.")

print("\n--- SKIPPED COURSES ---")
for e in errors:
    print(e)
if not errors:
    print("All courses mapped successfully!")
print("-----------------------")
