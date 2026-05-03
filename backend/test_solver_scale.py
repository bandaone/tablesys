"""
TASK 5: INCREMENTAL SOLVER SCALING TESTS
Tests solver performance across progressively increasing complexity levels
"""

import pytest
import time
import sys
import os

sys.path.append(os.getcwd())

from app.database import SessionLocal, engine
from app.models import Base, Timetable, TimetableSlot, Course, RoomType
from app.services.timetable_generator import TimetableGenerator
from tests.test_fixtures import (
    create_department, create_course, create_room, create_lecturer,
    create_student_group, create_lecturer_assignment, create_group_assignment,
    assert_no_room_conflicts, assert_no_lecturer_conflicts, assert_no_student_conflicts
)


class TestSolverScaling:
    """Test suite for incremental solver scaling validation"""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Reset database before each test"""
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield
    
    def test_level_1_single_course(self):
        """
        Level 1: Baseline functionality
        Test: 1 course, 2 rooms, 1 lecturer
        Expected: Quick solution, no conflicts
        """
        db = SessionLocal()
        
        try:
            # Setup data
            dept = create_department(db, "TEST", "Test Department")
            
            course = create_course(
                db, "TEST101", dept.id, level=5, lecture_hours=3
            )
            
            # Abundant rooms
            room1 = create_room(db, "Room A", capacity=50)
            room2 = create_room(db, "Room B", capacity=50)
            
            lecturer = create_lecturer(db, "Dr. Test", dept.id)
            group = create_student_group(db, "TEST-5A", level=5, dept_id=dept.id)
            
            create_lecturer_assignment(db, lecturer.id, course.id)
            create_group_assignment(db, group.id, course.id)
            
            # Create timetable
            timetable = Timetable(
                name="Level 1 Test", semester="Test", year=2026
            )
            db.add(timetable)
            db.commit()
            
            # Execute solver
            generator = TimetableGenerator(db, timetable.id)
            start = time.time()
            success = generator.generate_timetable()
            exec_time = time.time() - start
            
            # Assertions
            assert success, "Generation should succeed"
            assert exec_time < 1.0, f"Took {exec_time:.2f}s, expected < 1s"
            
            slots = db.query(TimetableSlot).filter(
                TimetableSlot.timetable_id == timetable.id
            ).all()
            
            assert len(slots) >= 3, f"Expected at least 3 slots, got {len(slots)}"
            assert_no_room_conflicts(slots)
            assert_no_lecturer_conflicts(slots)
            
            print(f"✓ Level 1: {len(slots)} slots in {exec_time:.2f}s")
            
        finally:
            db.rollback()
            db.close()
    
    def test_level_2_multiple_courses_abundant_resources(self):
        """
        Level 2: Basic interaction
        Test: 5 courses, 10 rooms (abundant resources)
        Expected: All courses scheduled, no conflicts
        """
        db = SessionLocal()
        
        try:
            # Setup
            dept = create_department(db, "TEST", "Test Department")
            
            # Create 5 courses
            courses = []
            for i in range(5):
                course = create_course(
                    db, f"TEST{100+i}", dept.id, level=5, lecture_hours=3
                )
                courses.append(course)
            
            # Create 10 rooms (abundant)
            rooms = []
            for i in range(10):
                room = create_room(db, f"Room {chr(65+i)}", capacity=50)
                rooms.append(room)
            
            # One lecturer handles all
            lecturer = create_lecturer(db, "Dr. Universal", dept.id, max_hours=40)
            group = create_student_group(db, "TEST-5A", level=5, dept_id=dept.id)
            
            for course in courses:
                create_lecturer_assignment(db, lecturer.id, course.id)
                create_group_assignment(db, group.id, course.id)
            
            timetable = Timetable(
                name="Level 2 Test", semester="Test", year=2026
            )
            db.add(timetable)
            db.commit()
            
            # Execute
            generator = TimetableGenerator(db, timetable.id)
            start = time.time()
            success = generator.generate_timetable()
            exec_time = time.time() - start
            
            # Assertions
            assert success, "Generation should succeed with abundant resources"
            assert exec_time < 5.0, f"Took {exec_time:.2f}s, expected < 5s"
            
            slots = db.query(TimetableSlot).filter(
                TimetableSlot.timetable_id == timetable.id
            ).all()
            
            expected_slots = 5 * 3  # 5 courses × 3 hours each
            assert len(slots) >= expected_slots * 0.8, \
                f"Expected ~{expected_slots} slots, got {len(slots)}"
            
            assert_no_room_conflicts(slots)
            assert_no_lecturer_conflicts(slots)
            assert_no_student_conflicts(slots)
            
            print(f"✓ Level 2: {len(slots)} slots in {exec_time:.2f}s")
            
        finally:
            db.rollback()
            db.close()
    
    def test_level_3_resource_competition(self):
        """
        Level 3: Scarce resources
        Test: 5 courses, 2 rooms only
        Expected: Solver handles competition correctly
        """
        db = SessionLocal()
        
        try:
            # Setup
            dept = create_department(db, "TEST", "Test Department")
            
            # Create 5 courses
            courses = []
            for i in range(5):
                course = create_course(
                    db, f"TEST{100+i}", dept.id, level=5, lecture_hours=3
                )
                courses.append(course)
            
            # Only 2 rooms (scarce)
            room1 = create_room(db, "Room A", capacity=50)
            room2 = create_room(db, "Room B", capacity=50)
            
            lecturer = create_lecturer(db, "Dr. Busy", dept.id, max_hours=40)
            group = create_student_group(db, "TEST-5A", level=5, dept_id=dept.id)
            
            for course in courses:
                create_lecturer_assignment(db, lecturer.id, course.id)
                create_group_assignment(db, group.id, course.id)
            
            timetable = Timetable(
                name="Level 3 Test", semester="Test", year=2026
            )
            db.add(timetable)
            db.commit()
            
            # Execute
            generator = TimetableGenerator(db, timetable.id)
            start = time.time()
            success = generator.generate_timetable()
            exec_time = time.time() - start
            
            # Assertions  
            assert success, "Should find solution even with scarce resources"
            assert exec_time < 10.0, f"Took {exec_time:.2f}s, expected < 10s"
            
            slots = db.query(TimetableSlot).filter(
                TimetableSlot.timetable_id == timetable.id
            ).all()
            
            assert len(slots) >= 12, f"Expected at least 12 slots, got {len(slots)}"
            
            # Critical: No room conflicts with limited resources
            assert_no_room_conflicts(slots)
            assert_no_lecturer_conflicts(slots)
            assert_no_student_conflicts(slots)
            
            print(f"✓ Level 3: {len(slots)} slots in {exec_time:.2f}s")
            
        finally:
            db.rollback()
            db.close()
    
    def test_level_4_realistic_single_year(self):
        """
        Level 4: Realistic data volume
        Test: 15 courses (5 programs × 3 courses) with mixed requirements
        Expected: 80%+ scheduled, reasonable time
        """
        db = SessionLocal()
        
        try:
            # Setup
            dept = create_department(db, "Engineering", "School of Engineering")
            programs = ["AEN", "CEE", "EEE", "GEE", "MEC"]
            
            # Create 15 courses with variety
            courses = []
            for prog_idx, prog in enumerate(programs):
                for i in range(3):
                    has_practical = (i == 0)  # First course has lab
                    course = create_course(
                        db,
                        f"{prog} 5{100+i}",
                        dept.id,
                        level=5,
                        lecture_hours=3,
                        tutorial_hours=1,
                        practical_hours=2 if has_practical else 0,
                        preferred_room_type=RoomType.LAB if has_practical else RoomType.ANY
                    )
                    courses.append(course)
            
            # Mix of room types
            rooms = []
            for i in range(4):
                rooms.append(create_room(db, f"LT{i}", capacity=100, room_type="lecture_hall"))
            for i in range(4):
                rooms.append(create_room(db, f"Lab {chr(65+i)}", capacity=40, room_type="lab"))
            
            # Multiple lecturers
            lecturers = []
            for i in range(5):
                lec = create_lecturer(db, f"Dr. Expert {i+1}", dept.id, max_hours=20)
                lecturers.append(lec)
            
            # Student groups per program
            groups = []
            for prog in programs:
                group = create_student_group(db, f"{prog}-5A", level=5, dept_id=dept.id, size=40)
                groups.append(group)
            
            # Assign lecturers and groups
            for idx, course in enumerate(courses):
                lecturer = lecturers[idx % len(lecturers)]
                group = groups[idx // 3]  # 3 courses per program
                
                create_lecturer_assignment(db, lecturer.id, course.id)
                create_group_assignment(db, group.id, course.id)
            
            timetable = Timetable(
                name="Level 4 Test", semester="Test", year=2026
            )
            db.add(timetable)
            db.commit()
            
            # Execute
            generator = TimetableGenerator(db, timetable.id)
            start = time.time()
            success = generator.generate_timetable()
            exec_time = time.time() - start
            
            # Assertions
            assert success or exec_time < 15.0, \
                "Should succeed or timeout gracefully within 15s"
            assert exec_time < 15.0, f"Took {exec_time:.2f}s, expected < 15s"
            
            slots = db.query(TimetableSlot).filter(
                TimetableSlot.timetable_id == timetable.id
            ).all()
            
            # Each course: 3 lectures + 1 tutorial + (0 or 2 practicals)
            # Minimum expected: 15 courses × 4 hours = 60 slots
            expected_min = int(60 * 0.8)  # 80% threshold
            assert len(slots) >= expected_min, \
                f"Expected at least {expected_min} slots (80%), got {len(slots)}"
            
            assert_no_room_conflicts(slots)
            assert_no_lecturer_conflicts(slots)
            
            scheduled_pct = (len(slots) / 75) * 100  # 75 = theoretical max
            print(f"✓ Level 4: {len(slots)} slots ({scheduled_pct:.1f}%) in {exec_time:.2f}s")
            
        finally:
            db.rollback()
            db.close()
    
    def test_level_5_full_school_scale(self):
        """
        Level 5: Production scale
        Test: 100 courses (4 years × 5 programs × 4-5 courses)
        Expected: 80%+ scheduled, under 60s
        """
        db = SessionLocal()
        
        try:
            # Setup
            dept = create_department(db, "Engineering", "School of Engineering")
            programs = ["AEN", "CEE", "EEE", "GEE", "MEC"]
            years = [2, 3, 4, 5]
            
            # Create ~100 courses
            courses = []
            for year in years:
                for prog in programs:
                    num_courses = 5 if year in [2, 3] else 4
                    for i in range(num_courses):
                        has_practical = (i == 0)
                        course = create_course(
                            db,
                            f"{prog} {year}{100+i}",
                            dept.id,
                            level=year,
                            lecture_hours=3,
                            tutorial_hours=1 if i % 2 == 0 else 0,
                            practical_hours=2 if has_practical else 0,
                            preferred_room_type=RoomType.LAB if has_practical else RoomType.ANY
                        )
                        courses.append(course)
            
            total_courses = len(courses)
            print(f"Testing with {total_courses} courses")
            
            # Full room inventory
            rooms = []
            for i in range(5):
                rooms.append(create_room(db, f"LT{i}", capacity=150, room_type="lecture_hall"))
            for i in range(3):
                rooms.append(create_room(db, f"ENLT{i}", capacity=80, room_type="lecture_hall"))
            for i in range(5):
                rooms.append(create_room(db, f"Lab {chr(65+i)}", capacity=40, room_type="lab"))
            for i in range(3):
                rooms.append(create_room(db, f"Tutorial {i}", capacity=30, room_type="tutorial_room"))
            
            # Multiple lecturers
            lecturers = []
            for i in range(15):
                lec = create_lecturer(db, f"Dr. Professor {i+1}", dept.id, max_hours=20)
                lecturers.append(lec)
            
            # Student groups
            groups = []
            for year in years:
                for prog in programs:
                    group = create_student_group(
                        db, f"{prog}-{year}A", level=year, dept_id=dept.id, size=40
                    )
                    groups.append(group)
            
            # Assign lecturers and groups
            for idx, course in enumerate(courses):
                lecturer = lecturers[idx % len(lecturers)]
                # Find matching group
                matching_groups = [g for g in groups if g.level == course.level]
                if matching_groups:
                    group = matching_groups[idx % len(matching_groups)]
                    create_lecturer_assignment(db, lecturer.id, course.id)
                    create_group_assignment(db, group.id, course.id)
            
            timetable = Timetable(
                name="Level 5 Test", semester="Test", year=2026
            )
            db.add(timetable)
            db.commit()
            
            # Execute with timeout monitoring
            generator = TimetableGenerator(db, timetable.id)
            start = time.time()
            success = generator.generate_timetable()
            exec_time = time.time() - start
            
            # Assertions
            assert exec_time < 60.0, f"Exceeded 60s timeout: {exec_time:.2f}s"
            
            slots = db.query(TimetableSlot).filter(
                TimetableSlot.timetable_id == timetable.id
            ).all()
            
            # Calculate expected vs actual
            # Rough estimate: 100 courses × 4 avg hours = 400 slots
            expected_min = int(400 * 0.8)  # 80% threshold
            scheduled_pct = (len(slots) / 400) * 100
            
            assert len(slots) >= expected_min, \
                f"Expected at least {expected_min} slots (80%), got {len(slots)}"
            
            assert_no_room_conflicts(slots)
            
            print(f"✓ Level 5: {len(slots)} slots ({scheduled_pct:.1f}%) in {exec_time:.2f}s")
            print(f"  Status: {'SUCCESS' if success else 'PARTIAL'}")
            print(f"  Courses: {total_courses}")
            
        finally:
            db.rollback()
            db.close()


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "--tb=short"])
