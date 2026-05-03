from app.database import SessionLocal
from app.models import Lecturer, LecturerAssignment, Course
from sqlalchemy.orm import joinedload
from app.schemas import Lecturer as LecturerSchema
import json

db = SessionLocal()
try:
    lecturer = db.query(Lecturer).options(
        joinedload(Lecturer.assignments).joinedload(LecturerAssignment.course)
    ).order_by(Lecturer.id.desc()).first()

    if lecturer:
        serialized = LecturerSchema.model_validate(lecturer)
        print(serialized.model_dump_json(indent=2))
finally:
    db.close()
