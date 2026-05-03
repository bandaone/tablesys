import sys
from pathlib import Path

# Setup path so we can import the app modules
backend_dir = Path(__file__).parent.absolute()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.models import Course, Room, Lecturer, StudentGroup, TimetableSlot, Timetable
from sqlalchemy import func

def get_stats():
    db = SessionLocal()
    try:
        # 1. Total Courses in DB vs Schduled
        total_courses = db.query(Course).count()
        # 2. Total Rooms (Venues)
        total_rooms = db.query(Room).count()
        # 3. Total Lecturers
        total_lecturers = db.query(Lecturer).count()
        # 4. Total Student Groups
        total_groups = db.query(StudentGroup).count()
        
        # Look for the active timetable
        active_timetable = db.query(Timetable).filter(Timetable.is_active == True).first()
        
        if active_timetable:
            slots_query = db.query(TimetableSlot).filter(TimetableSlot.timetable_id == active_timetable.id)
            
            # Scheduled Slots
            scheduled_slots = slots_query.count()
            
            # Active Courses (Distinct course codes assigned)
            active_courses = len(set(s.course_id for s in slots_query.all()))
            
            # Venues Used (Distinct rooms assigned)
            venues_used = len(set(s.room_id for s in slots_query.all()))
            
            # Active Lecturers
            active_lecturers = len(set(s.lecturer_id for s in slots_query.all() if s.lecturer_id))
            
            # Student Groups Scheduled
            active_groups = len(set(s.group_id for s in slots_query.all() if s.group_id))
            
            # Contact Hours
            contact_hours = sum(s.end_time.hour - s.start_time.hour + (s.end_time.minute - s.start_time.minute)/60.0 for s in slots_query.all())
            
        else:
            scheduled_slots = 0
            active_courses = 0
            venues_used = 0
            active_lecturers = 0
            active_groups = 0
            contact_hours = 0

        print(f"--- TABLESYS CURRENT DATABASE METRICS ---")
        print(f"Total Registered Courses: {total_courses} (Active in Schedule: {active_courses})")
        print(f"Total Registered Rooms: {total_rooms} (Used in Schedule: {venues_used})")
        print(f"Total Registered Lecturers: {total_lecturers} (Active in Schedule: {active_lecturers})")
        print(f"Total Registered Groups: {total_groups} (Active in Schedule: {active_groups})")
        print(f"")
        print(f"--- ACTIVE TIMETABLE METRICS ---")
        print(f"Scheduled Slots: {scheduled_slots}")
        print(f"Contact Hours per Week: {contact_hours} hours")
        print(f"Active Timetable Name: {active_timetable.name if active_timetable else 'None'}")
        
    finally:
        db.close()

if __name__ == "__main__":
    get_stats()
