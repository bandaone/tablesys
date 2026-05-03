import sys
from pathlib import Path

backend_dir = Path(__file__).parent.absolute()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.models import Course, Room, StudentGroup, GroupAssignment, CourseGroupLink

def diagnose():
    db = SessionLocal()
    try:
        level = 5 # Let's test the specific level that just failed. Oh wait, the logs didn't specify which level failed? It says "level: 0" inside the worker? No, it's just generating.
        # Actually Timetable Generator generates one level at a time. So Pigeonhole principle applies PER LEVEL.
        
        # Let's assess Level 2
        groups = db.query(StudentGroup).filter(StudentGroup.level == 2).all()
        rooms = db.query(Room).all() # All rooms are shared across levels
        
        # In a real timetable, rooms are shared, so a level does NOT have 100% of rooms!
        # But even assuming Level 2 has 100% of rooms:
        total_room_hours = len(rooms) * 12 * 5
        print(f"Total physical room-hours available (if Level 2 uses 100% of school): {total_room_hours}")
        
        total_class_hours = 0
        courses = db.query(Course).filter(Course.level == 2).all()
        
        for c in courses:
            # How many times is this scheduled? 
            config = c.session_configuration or {}
            duration = c.lecture_hours
            freq = config.get('lecture_sessions', 2)
            
            # CGL links determines how many unique "batches" of groups need a physically distinct instance!
            cgl_links = db.query(CourseGroupLink).filter(CourseGroupLink.course_id == c.id).all()
            if cgl_links:
                batches = set([l.shared_batch_id if l.is_shared else l.group_id for l in cgl_links])
                num_classes = len(batches)
            else:
                ga = db.query(GroupAssignment).filter(GroupAssignment.course_id == c.id).all()
                num_classes = len(ga)
                
            total_class_hours += (duration * freq * num_classes)
            
        print(f"Total Level 2 Class-Hours Required: {total_class_hours}")
        
    finally:
        db.close()

if __name__ == "__main__":
    diagnose()
