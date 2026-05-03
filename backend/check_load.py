import sys
from pathlib import Path

backend_dir = Path(__file__).parent.absolute()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.models import Course, StudentGroup, GroupAssignment, CourseGroupLink

def diagnose_load():
    db = SessionLocal()
    try:
        groups = db.query(StudentGroup).filter(StudentGroup.level == 2).all()
        for g in groups:
            # Get assigned courses
            assignments = db.query(GroupAssignment).filter(GroupAssignment.group_id == g.id).all()
            links = db.query(CourseGroupLink).filter(CourseGroupLink.group_id == g.id).all()
            
            c_ids = set([a.course_id for a in assignments] + [l.course_id for l in links])
            if not c_ids: continue
            
            total_hours = 0
            print(f"Group: {g.name}")
            for cid in c_ids:
                c = db.query(Course).filter(Course.id == cid).first()
                if not c: continue
                config = c.session_configuration or {}
                duration = c.lecture_hours
                frequency = config.get('lecture_sessions', 2)
                ch = duration * frequency
                total_hours += ch
                print(f"  - {c.code}: {duration}hrs x {frequency} = {ch} hrs/week")
                
            print(f"  --> TOTAL LOAD: {total_hours} hours/week")
            
    finally:
        db.close()

if __name__ == "__main__":
    diagnose_load()
