from app.database import SessionLocal
from app.models import Course, Department, User, UserRole
from sqlalchemy import or_, and_, cast
from sqlalchemy.dialects.postgresql import JSONB

db = SessionLocal()
dept_id = 1  # Assume EEE is 1
gen_dept_id = 6  # ENG is 6

dept_in_shared = cast(Course.shared_with_department_ids, JSONB).contains([dept_id])
query = db.query(Course).filter(
    or_(
        Course.department_id == dept_id,
        and_(
            Course.department_id == gen_dept_id,
            or_(
                Course.shared_with_department_ids.is_(None),
                dept_in_shared
            )
        ),
        and_(
            Course.department_id != dept_id,
            Course.department_id != gen_dept_id,
            dept_in_shared
        )
    )
)
print("Query generated successfully.")
try:
    print(f"Count: {query.count()}")
    for c in query.limit(5).all():
        print(f"{c.code} - Dept {c.department_id}")
except Exception as e:
    print(f"Error: {e}")
