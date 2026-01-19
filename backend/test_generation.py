
import sys
import os


# Add current directory to path so we can import app modules
sys.path.append(os.getcwd())

from app.database import SessionLocal, engine
from app.models import (
    Base, Department, Room, Course, Lecturer, StudentGroup,
    LecturerAssignment, GroupAssignment, Timetable, TimetableSlot,
    RoomType, RoomCategory, GroupType
)
from app.services.timetable_generator import TimetableGenerator

def test_generation():
    print("[*] Resetting Database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 1. Create Departments
        dept = Department(name="Test Dept", code="TEST")
        db.add(dept)
        db.commit()
        
        # 2. Create Rooms
        # - Lecture Hall (Generic)
        # - Drawing Room (Specific)
        r1 = Room(
            name="L1", building="B1", capacity=100, 
            room_type="lecture_hall", 
            room_category=RoomCategory.LECTURE_HALL_MEDIUM
        )
        r2 = Room(
            name="D1", building="B1", capacity=50, 
            room_type="drawing_room", 
            room_category=RoomCategory.DRAWING_ROOM
        )
        db.add(r1)
        db.add(r2)
        db.commit()
        
        # 3. Create Lecturer
        l1 = Lecturer(
            staff_number="L001", full_name="Dr. Tester", email="test@test.com",
            department_id=dept.id, max_hours_per_week=20,
            teaching_preferences={"avoid_early_morning": True}
        )
        db.add(l1)
        db.commit()
        
        # 4. Create Student Group
        g1 = StudentGroup(
            name="TEST-2A", level=2, department_id=dept.id, size=40,
            group_type=GroupType.DEPARTMENT, display_code="T2A"
        )
        db.add(g1)
        db.commit()
        
        # 5. Create Course
        # Course 1: Lecture (2hrs consecutive) + Drawing (3hrs)
        # Should prefer Drawing Room for the 3hr session
        c1 = Course(
            code="TEST201", name="Engineering Drawing", department_id=dept.id,
            level=2, credits=3, lecture_hours=2, tutorial_hours=0, practical_hours=3,
            preferred_room_type=RoomType.DRAWING_ROOM, # Prefer Drawing Room
            session_configuration={"requires_consecutive": 2}
        )
        db.add(c1)
        db.commit()
        
        # 6. Assignments
        la1 = LecturerAssignment(
            lecturer_id=l1.id, course_id=c1.id
        )
        ga1 = GroupAssignment(
            group_id=g1.id, course_id=c1.id
        )
        db.add(la1)
        db.add(ga1)
        db.commit()
        
        # 7. Create Timetable
        tt = Timetable(
            name="Test Timetable", semester="1", year=2024,
            academic_half="first_half"
        )
        db.add(tt)
        db.commit()
        
        print("\n[*] Starting Generation...")
        generator = TimetableGenerator(db, tt.id, progress_callback=lambda x: print(f"[{x['level']}] {x['message']}"))
        success = generator.generate_timetable()
        
        if success:
            print("\n[+] Generation Successful!")
            
            # Verify Slots
            slots = db.query(TimetableSlot).filter(TimetableSlot.timetable_id == tt.id).all()
            print(f"Total Slots Created: {len(slots)}")
            
            # Check Sessions
            lectures = [s for s in slots if s.session_type == 'lecture']
            practicals = [s for s in slots if s.session_type == 'practical'] # Our code maps based on hours
            
            print(f"Lecture Slots (Expect 2): {len(lectures)}")
            print(f"Practical Slots (Expect 3): {len(practicals)}")
            
            # Check Room Assignment
            # Practical slots should be in D1 (Drawing Room)
            d1_id = r2.id
            practical_rooms = {s.room_id for s in practicals}
            print(f"Practical Rooms (Expect {d1_id}): {practical_rooms}")
            
            # Check for Consecutive Blocks
            # Lectures should be contiguous
            lectures.sort(key=lambda x: (x.day_of_week, x.start_time))
            if len(lectures) == 2:
                s1, s2 = lectures[0], lectures[1]
                print(f"Lecture 1: {s1.day_of_week} {s1.start_time}-{s1.end_time}")
                print(f"Lecture 2: {s2.day_of_week} {s2.start_time}-{s2.end_time}")
                is_consecutive = (s1.day_of_week == s2.day_of_week) and (s1.end_time == s2.start_time)
                print(f"Lectures Consecutive? {is_consecutive}")
                
            else:
                 print("WARNING: Lecture count mismatch for consecutiveness check")
                 
        else:
            print("\n[-] Generation Failed")
            
    except Exception as e:
        print(f"\n[-] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_generation()
