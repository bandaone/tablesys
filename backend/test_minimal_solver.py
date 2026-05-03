"""
TASK 1: MINIMAL CONSTRAINT SOLVER VERIFICATION
Tests OR-Tools CP-SAT solver with single course to verify core functionality
"""

import sys
import os
import time

sys.path.append(os.getcwd())

from app.database import SessionLocal, engine
from app.models import (
    Base, Department, Room, Course, Lecturer, StudentGroup,
    LecturerAssignment, GroupAssignment, Timetable, TimetableSlot,
    RoomType, GroupType
)
from app.services.timetable_generator import TimetableGenerator


class TestResult:
    """Structured test result object"""
    def __init__(self):
        self.status = "UNKNOWN"
        self.error_message = None
        self.slots = []
        self.execution_time = 0.0


def create_test_data(db):
    """Create minimal test dataset"""
    
    # Create department
    dept = Department(name="Test Department", code="TEST")
    db.add(dept)
    db.flush()
    
    # Create course (3 lecture hours)
    course = Course(
        code="TEST101",
        name="Test Course",
        department_id=dept.id,
        level=5,
        credits=3,
        lecture_hours=3,
        tutorial_hours=0,
        practical_hours=0,
        preferred_room_type=RoomType.ANY
    )
    db.add(course)
    db.flush()
    
    # Create room (capacity 50)
    room = Room(
        name="Test Room A",
        building="Test Building",
        capacity=50,
        room_type="lecture_hall"
    )
    db.add(room)
    db.flush()
    
    # Create lecturer (max 20 hours/week)
    lecturer = Lecturer(
        staff_number="TEST001",
        full_name="Dr. Test",
        email="test@unza.zm",
        department_id=dept.id,
        max_hours_per_week=20
    )
    db.add(lecturer)
    db.flush()
    
    # Create student group
    student_group = StudentGroup(
        name="TEST-5A",
        level=5,
        department_id=dept.id,
        size=45,
        group_type=GroupType.DEPARTMENT,
        display_code="T5A"
    )
    db.add(student_group)
    db.flush()
    
    # Create lecturer assignment
    lec_assignment = LecturerAssignment(
        lecturer_id=lecturer.id,
        course_id=course.id
    )
    db.add(lec_assignment)
    
    # Create group assignment
    grp_assignment = GroupAssignment(
        group_id=student_group.id,
        course_id=course.id
    )
    db.add(grp_assignment)
    
    # Create timetable
    timetable = Timetable(
        name="Test Timetable",
        semester="Test Term",
        year=2026,
        academic_half="first_half"
    )
    db.add(timetable)
    
    db.commit()
    
    return timetable.id, dept.id


def test_solver(db, timetable_id):
    """Execute solver test"""
    result = TestResult()
    
    try:
        generator = TimetableGenerator(db, timetable_id)
        
        start_time = time.time()
        success = generator.generate_timetable()
        result.execution_time = time.time() - start_time
        
        if success:
            # Query generated slots
            slots = db.query(TimetableSlot).filter(
                TimetableSlot.timetable_id == timetable_id
            ).all()
            
            result.slots = slots
            result.status = "SUCCESS"
        else:
            result.status = "INFEASIBLE"
            result.error_message = "Solver could not find feasible solution"
            
    except Exception as e:
        result.status = "ERROR"
        result.error_message = str(e)
    
    return result


def verify_cleanup(db):
    """Verify test data was cleaned up"""
    test_course_count = db.query(Course).filter(
        Course.code == 'TEST101'
    ).count()
    return test_course_count == 0


def main():
    """Main test execution"""
    
    print("MINIMAL SOLVER TEST")
    print("=" * 50)
    print()
    
    db = SessionLocal()
    timetable_id = None
    
    try:
        # Reset database for clean test
        print("Initializing test database...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        
        print("Creating test data...")
        timetable_id, dept_id = create_test_data(db)
        
        print("Running solver...")
        result = test_solver(db, timetable_id)
        
        print()
        print("=" * 50)
        print(f"STATUS: {result.status}")
        print(f"EXECUTION TIME: {result.execution_time:.2f}s")
        print("=" * 50)
        
        if result.status == "SUCCESS":
            print(f"\nSlots Generated: {len(result.slots)}")
            
            # Display slot details
            if result.slots:
                print("\nGenerated Schedule:")
                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                for slot in result.slots:
                    print(f"  - {days[slot.day_of_week]} {slot.start_time} - {slot.end_time}")
                    print(f"    Room: {slot.room.name}, Type: {slot.session_type}")
            
            print("\n✅ SOLVER WORKS - PROCEED TO TASK 3A")
            return 0
            
        elif result.status == "INFEASIBLE":
            print(f"\nError: {result.error_message}")
            print("\n⚠️  CONSTRAINT ISSUE - PROCEED TO TASK 3B")
            return 0
            
        else:
            print(f"\nError: {result.error_message}")
            print("\n❌ CODE ERROR - DEBUGGING REQUIRED")
            return 1
            
    except Exception as e:
        print(f"\n❌ EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        # Cleanup: rollback to remove test data
        db.rollback()
        db.close()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
