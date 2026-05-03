from app.database import SessionLocal
from app.models import StudentGroup, Department
from sqlalchemy import or_

db = SessionLocal()
dep_id = 1

gen_dept = db.query(Department).filter(Department.code.ilike('ENG')).first()
gen_dept_id = gen_dept.id if gen_dept else -1

query = db.query(StudentGroup)
query = query.filter(
    or_(
        StudentGroup.department_id == dep_id,
        StudentGroup.department_id == gen_dept_id
    )
)

print(f"gen_dept_id detected: {gen_dept_id}")
for g in query.all():
    print(f"Group: {g.name}, Dept: {g.department_id}")
