"""
TASK 5: Reusable Test Fixtures
Provides data generation and validation functions for scaling tests
"""

from app.models import (
    Department, Course, Room, Lecturer, StudentGroup, 
    LecturerAssignment, GroupAssignment, RoomType, GroupType
)


def create_department(db, code, name):
    """Create a department"""
    dept = Department(code=code, name=name)
    db.add(dept)
    db.flush()
    return dept


def create_course(db, code, dept_id, level, lecture_hours, 
                  tutorial_hours=0, practical_hours=0, 
                  preferred_room_type=RoomType.ANY):
    """Create a course with specified parameters"""
    course = Course(
        code=code,
        name=f"Course {code}",
        department_id=dept_id,
        level=level,
        credits=3,
        lecture_hours=lecture_hours,
        tutorial_hours=tutorial_hours,
        practical_hours=practical_hours,
        preferred_room_type=preferred_room_type
    )
    db.add(course)
    db.flush()
    return course


def create_room(db, name, capacity, room_type="lecture_hall"):
    """Create a room with specified parameters"""
    room = Room(
        name=name,
        building="Test Building",
        capacity=capacity,
        room_type=room_type
    )
    db.add(room)
    db.flush()
    return room


def create_lecturer(db, name, dept_id, max_hours=20):
    """Create a lecturer"""
    lecturer = Lecturer(
        staff_number=f"STAFF_{name.replace(' ', '_').upper()}",
        full_name=name,
        email=f"{name.lower().replace(' ', '.')}@unza.zm",
        department_id=dept_id,
        max_hours_per_week=max_hours
    )
    db.add(lecturer)
    db.flush()
    return lecturer


def create_student_group(db, name, level, dept_id, size=40):
    """Create a student group"""
    group = StudentGroup(
        name=name,
        level=level,
        department_id=dept_id,
        size=size,
        group_type=GroupType.DEPARTMENT,
        display_code=name
    )
    db.add(group)
    db.flush()
    return group


def create_lecturer_assignment(db, lecturer_id, course_id):
    """Assign a lecturer to a course"""
    assignment = LecturerAssignment(
        lecturer_id=lecturer_id,
        course_id=course_id
    )
    db.add(assignment)
    db.flush()
    return assignment


def create_group_assignment(db, group_id, course_id):
    """Assign a student group to a course"""
    assignment = GroupAssignment(
        group_id=group_id,
        course_id=course_id
    )
    db.add(assignment)
    db.flush()
    return assignment


def assert_no_room_conflicts(slots):
    """
    Verify no room double-booking exists.
    Raises AssertionError if conflicts found.
    """
    time_room_map = {}
    
    for slot in slots:
        # Create unique key for (day, time, room)
        key = (slot.day_of_week, slot.start_time, slot.room_id)
        
        if key in time_room_map:
            existing = time_room_map[key]
            raise AssertionError(
                f"Room conflict detected:\n"
                f"  Room: {slot.room.name}\n"
                f"  Time: Day {slot.day_of_week} at {slot.start_time}\n"
                f"  Course 1: {existing.course.code}\n"
                f"  Course 2: {slot.course.code}"
            )
        
        time_room_map[key] = slot


def assert_no_lecturer_conflicts(slots):
    """
    Verify no lecturer double-booking exists.
    Raises AssertionError if conflicts found.
    """
    time_lecturer_map = {}
    
    for slot in slots:
        if not slot.lecturer_id:
            continue
        
        # Create unique key for (day, time, lecturer)
        key = (slot.day_of_week, slot.start_time, slot.lecturer_id)
        
        if key in time_lecturer_map:
            existing = time_lecturer_map[key]
            raise AssertionError(
                f"Lecturer conflict detected:\n"
                f"  Lecturer: {slot.lecturer.full_name}\n"
                f"  Time: Day {slot.day_of_week} at {slot.start_time}\n"
                f"  Course 1: {existing.course.code}\n"
                f"  Course 2: {slot.course.code}"
            )
        
        time_lecturer_map[key] = slot


def assert_no_student_conflicts(slots):
    """
    Verify no student group double-booking exists.
    Raises AssertionError if conflicts found.
    """
    time_group_map = {}
    
    for slot in slots:
        if not slot.group_id:
            continue
        
        # Create unique key for (day, time, group)
        key = (slot.day_of_week, slot.start_time, slot.group_id)
        
        if key in time_group_map:
            existing = time_group_map[key]
            raise AssertionError(
                f"Student conflict detected:\n"
                f"  Group: {slot.group.name}\n"
                f"  Time: Day {slot.day_of_week} at {slot.start_time}\n"
                f"  Course 1: {existing.course.code}\n"
                f"  Course 2: {slot.course.code}"
            )
        
        time_group_map[key] = slot
