import argparse
import os
import sys

sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models import Department, Student, StudentGroup, Timetable, TimetableSlot
from app.routers.student_portal import get_password_hash


def find_demo_group(db):
    timetables = (
        db.query(Timetable)
        .filter(Timetable.is_active == True)
        .order_by(Timetable.id.desc())
        .all()
    )

    if not timetables:
        timetables = db.query(Timetable).order_by(Timetable.id.desc()).all()

    for timetable in timetables:
        slots = (
            db.query(TimetableSlot)
            .filter(TimetableSlot.timetable_id == timetable.id, TimetableSlot.group_id.isnot(None))
            .order_by(TimetableSlot.id.asc())
            .all()
        )
        for slot in slots:
            group = db.query(StudentGroup).filter(StudentGroup.id == slot.group_id).first()
            if group:
                return timetable, group

    return None, None


def main():
    parser = argparse.ArgumentParser(
        description="Create or refresh a predictable demo student account for /student manual testing.",
    )
    parser.add_argument("--student-number", default="STUDENT-DEMO-001")
    parser.add_argument("--password", default="StudentDemo123!")
    parser.add_argument("--full-name", default="Demo Student")
    parser.add_argument("--email", default="student.demo@tablesys.local")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        timetable, group = find_demo_group(db)
        if not timetable or not group:
            raise SystemExit(
                "No timetable slot with an assigned student group was found. "
                "Generate or import a timetable first, then rerun this script."
            )

        department = db.query(Department).filter(Department.id == group.department_id).first()
        student = db.query(Student).filter(Student.student_number == args.student_number).first()

        student_payload = {
            "full_name": args.full_name,
            "email": args.email,
            "hashed_password": get_password_hash(args.password),
            "program": department.name if department else group.name,
            "year_level": group.level,
            "group_id": group.id,
            "department_id": group.department_id,
            "is_active": True,
        }

        if student:
            for key, value in student_payload.items():
                setattr(student, key, value)
            action = "updated"
        else:
            student = Student(
                student_number=args.student_number,
                **student_payload,
            )
            db.add(student)
            action = "created"

        db.commit()
        db.refresh(student)

        print("Student access demo account ready.")
        print(f"Action: {action}")
        print(f"Student number: {student.student_number}")
        print(f"Password: {args.password}")
        print(f"Group: {group.name} (level {group.level})")
        print(f"Department: {department.name if department else 'N/A'}")
        print(f"Timetable: {timetable.name} (id={timetable.id})")
        print("Open the student portal at http://localhost:3002/student")
    finally:
        db.close()


if __name__ == "__main__":
    main()
