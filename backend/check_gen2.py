import sys
from pathlib import Path

backend_dir = Path(__file__).parent.absolute()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.models import Course, Room, Lecturer, StudentGroup, TimetableSlot, Timetable, GroupAssignment, CourseGroupLink, LecturerAssignment

def diagnose_gen2():
    db = SessionLocal()
    try:
        # Find GEN2 groups
        gen2_groups = db.query(StudentGroup).filter(
            StudentGroup.name.ilike('%GEN%'),
            StudentGroup.level == 2
        ).all()
        
        print("--- GEN2 DIAGNOSTIC ---")
        if not gen2_groups:
            print("No GEN2 groups found in database.")
            return

        for g in gen2_groups:
            print(f"\nGroup: {g.name} (ID: {g.id})")
            
            # Check legacy assignments
            assignments = db.query(GroupAssignment).filter(GroupAssignment.group_id == g.id).all()
            # Check new links
            links = db.query(CourseGroupLink).filter(CourseGroupLink.group_id == g.id).all()
            
            assigned_c_ids = set([a.course_id for a in assignments] + [l.course_id for l in links])
            
            if not assigned_c_ids:
                print("  -> ERROR: No courses assigned to this group!")
                continue
                
            print(f"  -> Assigned Courses (IDs): {assigned_c_ids}")
            
            # Check if those courses have lecturers
            for cid in assigned_c_ids:
                c = db.query(Course).filter(Course.id == cid).first()
                if not c: continue
                l_assigns = db.query(LecturerAssignment).filter(LecturerAssignment.course_id == cid).all()
                if not l_assigns:
                    print(f"    -> Course {c.code} is BLOCKED (No Lecturers Assigned)")
                else:
                    print(f"    -> Course {c.code} is ready (Has Lecturers)")
    finally:
        db.close()

if __name__ == "__main__":
    diagnose_gen2()
