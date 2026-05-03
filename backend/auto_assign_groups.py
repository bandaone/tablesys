import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.database import SessionLocal
from app.models import Course, StudentGroup, GroupAssignment, CourseGroupLink

def assign():
    db = SessionLocal()
    courses = db.query(Course).all()
    
    count = 0
    for c in courses:
        # Find groups in the same level as the course
        groups = db.query(StudentGroup).filter(StudentGroup.level == c.level).all()
        for g in groups:
            # Avoid duplicates
            exists = db.query(GroupAssignment).filter_by(course_id=c.id, group_id=g.id).first()
            if not exists:
                ga = GroupAssignment(course_id=c.id, group_id=g.id)
                db.add(ga)
                count += 1
    
    db.commit()
    print(f"Auto-assigned {count} Group Assignments successfully matching Courses to Groups by Level!")

if __name__ == "__main__":
    assign()
