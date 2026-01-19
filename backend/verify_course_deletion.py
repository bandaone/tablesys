import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import Course, TimetableSlot, LecturerAssignment, GroupAssignment

def verify_deletion():
    db = SessionLocal()
    try:
        print("Checking for courses and related records...")
        course_count = db.query(Course).count()
        slot_count = db.query(TimetableSlot).count()
        lecturer_assign_count = db.query(LecturerAssignment).count()
        group_assign_count = db.query(GroupAssignment).count()
        
        print(f"Courses: {course_count}")
        print(f"Timetable Slots: {slot_count}")
        print(f"Lecturer Assignments: {lecturer_assign_count}")
        print(f"Group Assignments: {group_assign_count}")
        
        # We don't want to actually delete if the user didn't ask us to run a "clear all" right now,
        # but the user DID say "Error deleting courses" which happens when they TRY to delete.
        # So I will simulate the deletion logic in a transaction and rollback.
        
        print("\nSimulating 'Delete All' operation...")
        
        # Delete related records first
        db.query(TimetableSlot).delete()
        db.query(GroupAssignment).delete()
        db.query(LecturerAssignment).delete()
        
        # Now delete all courses
        db.query(Course).delete()
        
        print("Success! All records deleted in current transaction.")
        
    except Exception as e:
        print(f"Error during simulated deletion: {e}")
    finally:
        print("Rolling back transaction to preserve data.")
        db.rollback()
        db.close()

if __name__ == "__main__":
    verify_deletion()
