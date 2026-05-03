"""
Data Verification Script for Timetable Generation
Checks if all required data exists and is properly linked.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from app.models import (
    Department, Course, Lecturer, Room, StudentGroup,
    LecturerAssignment, GroupAssignment, Timetable, TimetableSlot
)
from app.config import settings

# Create database connection
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def print_section(title):
    """Print section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def check_basic_data(db):
    """Check if basic entities exist"""
    print_section("📊 BASIC DATA CHECK")
    
    checks = {
        "Departments": db.query(Department).count(),
        "Courses": db.query(Course).count(),
        "Lecturers": db.query(Lecturer).count(),
        "Rooms": db.query(Room).count(),
        "Student Groups": db.query(StudentGroup).count(),
        "Lecturer Assignments": db.query(LecturerAssignment).count(),
        "Group Assignments": db.query(GroupAssignment).count(),
    }
    
    all_good = True
    for entity, count in checks.items():
        status = "✅" if count > 0 else "❌"
        print(f"{status} {entity:.<40} {count:>5}")
        if count == 0:
            all_good = False
    
    return all_good

def check_level_distribution(db):
    """Check course distribution by level"""
    print_section("📈 COURSE DISTRIBUTION BY LEVEL")
    
    for level in [2, 3, 4, 5]:
        count = db.query(Course).filter(Course.level == level).count()
        courses = db.query(Course).filter(Course.level == level).limit(3).all()
        
        status = "✅" if count > 0 else "⚠️"
        print(f"{status} Level {level}: {count} courses")
        
        if courses:
            for course in courses:
                print(f"     - {course.code}: {course.name}")

def check_orphaned_courses(db):
    """Find courses without lecturers or groups"""
    print_section("🔍 ORPHANED COURSES CHECK")
    
    # Courses without lecturers
    courses_no_lecturers = db.query(Course).filter(
        ~db.query(LecturerAssignment).filter(
            LecturerAssignment.course_id == Course.id
        ).exists()
    ).all()
    
    # Courses without groups
    courses_no_groups = db.query(Course).filter(
        ~db.query(GroupAssignment).filter(
            GroupAssignment.course_id == Course.id
        ).exists()
    ).all()
    
    if courses_no_lecturers:
        print(f"❌ Found {len(courses_no_lecturers)} courses WITHOUT lecturers:")
        for course in courses_no_lecturers[:5]:
            print(f"   - {course.code}: {course.name}")
        if len(courses_no_lecturers) > 5:
            print(f"   ... and {len(courses_no_lecturers) - 5} more")
    else:
        print("✅ All courses have lecturers assigned")
    
    if courses_no_groups:
        print(f"❌ Found {len(courses_no_groups)} courses WITHOUT student groups:")
        for course in courses_no_groups[:5]:
            print(f"   - {course.code}: {course.name}")
        if len(courses_no_groups) > 5:
            print(f"   ... and {len(courses_no_groups) - 5} more")
    else:
        print("✅ All courses have student groups assigned")
    
    return len(courses_no_lecturers) == 0 and len(courses_no_groups) == 0

def check_room_types(db):
    """Check room type distribution"""
    print_section("🏛️ ROOM TYPE DISTRIBUTION")
    
    room_types = db.query(
        Room.room_type, 
        func.count(Room.id)
    ).group_by(Room.room_type).all()
    
    print("Room types available:")
    for room_type, count in room_types:
        print(f"  - {room_type:.<30} {count:>3} rooms")
    
    # Check for essential room types
    types_list = [rt[0].lower() for rt in room_types]
    essential = ['lecture', 'lab']
    
    for essential_type in essential:
        if any(essential_type in t for t in types_list):
            print(f"✅ {essential_type.capitalize()} rooms available")
        else:
            print(f"⚠️ No {essential_type} rooms found")

def check_course_configurations(db):
    """Check course session configurations"""
    print_section("⚙️ COURSE CONFIGURATIONS")
    
    # Sample 5 courses
    courses = db.query(Course).limit(5).all()
    
    print("Sample course configurations:")
    for course in courses:
        print(f"\n  {course.code} - {course.name}")
        print(f"    Level: {course.level}")
        print(f"    Hours: Lecture={course.lecture_hours}, "
              f"Tutorial={course.tutorial_hours}, "
              f"Practical={course.practical_hours}")
        print(f"    Room Type: {course.preferred_room_type}")
        print(f"    Session Config: {course.session_configuration}")
        
        # Check assignments
        lec_count = db.query(LecturerAssignment).filter(
            LecturerAssignment.course_id == course.id
        ).count()
        group_count = db.query(GroupAssignment).filter(
            GroupAssignment.course_id == course.id
        ).count()
        
        print(f"    Lecturers: {lec_count}, Groups: {group_count}")

def estimate_solver_complexity(db):
    """Estimate CP-SAT solver complexity"""
    print_section("🧮 SOLVER COMPLEXITY ESTIMATION")
    
    total_sessions = 0
    
    for level in [5, 4, 3, 2]:
        courses = db.query(Course).filter(Course.level == level).all()
        level_sessions = 0
        
        for course in courses:
            # Estimate sessions per course
            config = course.session_configuration or {}
            consecutive = config.get('requires_consecutive', 2)
            if isinstance(consecutive, bool):
                consecutive = 2 if consecutive else 1
            
            # Simple estimation
            sessions = (
                (course.lecture_hours // consecutive) +
                (course.tutorial_hours // 2) +
                (course.practical_hours // 3)
            )
            level_sessions += sessions
        
        total_sessions += level_sessions
        print(f"  Level {level}: ~{level_sessions} sessions")
    
    print(f"\n  Total estimated sessions: ~{total_sessions}")
    
    # Estimate variables
    rooms = db.query(Room).count()
    lecturers = db.query(Lecturer).count()
    groups = db.query(StudentGroup).count()
    
    # Rough estimate: sessions * avg_groups * avg_rooms * days * time_slots
    estimated_vars = total_sessions * 2 * (rooms // 2) * 5 * 12
    
    print(f"\n  Estimated CP-SAT variables: ~{estimated_vars:,}")
    
    if estimated_vars < 10000:
        print("  ✅ LOW complexity - should solve quickly")
    elif estimated_vars < 100000:
        print("  ⚠️ MEDIUM complexity - may take 30-60 seconds")
    else:
        print("  ❌ HIGH complexity - may take several minutes or fail")

def check_existing_timetables(db):
    """Check for existing timetables"""
    print_section("📅 EXISTING TIMETABLES")
    
    timetables = db.query(Timetable).all()
    
    if not timetables:
        print("  No timetables created yet")
        return False
    
    for tt in timetables:
        slots_count = db.query(TimetableSlot).filter(
            TimetableSlot.timetable_id == tt.id
        ).count()
        
        status = "🔴" if not tt.is_active else "🟢"
        print(f"{status} ID {tt.id}: {tt.name} ({tt.semester} {tt.year})")
        print(f"     Slots: {slots_count}, Active: {tt.is_active}")
        print(f"     Metadata: {tt.generation_metadata}")
    
    return True

def main():
    """Run all verification checks"""
    print("\n🔍 TABLESYS DATA VERIFICATION SUITE")
    print("=" * 70)
    
    db = SessionLocal()
    
    try:
        results = []
        
        # Run all checks
        results.append(check_basic_data(db))
        check_level_distribution(db)
        results.append(check_orphaned_courses(db))
        check_room_types(db)
        check_course_configurations(db)
        estimate_solver_complexity(db)
        check_existing_timetables(db)
        
        # Summary
        print_section("📋 SUMMARY")
        
        if all(results):
            print("✅ ALL DATA CHECKS PASSED")
            print("   The system has sufficient data for timetable generation.")
            print("\n   Next steps:")
            print("   1. Run: python test_ortools_basic.py")
            print("   2. Then: python test_solver_minimal.py")
            print("   3. Finally: Try generating a timetable from the UI")
            return 0
        else:
            print("⚠️ SOME DATA ISSUES DETECTED")
            print("   Fix the issues above before attempting generation.")
            print("\n   Common fixes:")
            print("   - Run: python seed_db.py (to populate sample data)")
            print("   - Ensure all courses have lecturers and groups assigned")
            return 1
            
    except Exception as e:
        print(f"\n❌ ERROR during verification: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()

if __name__ == "__main__":
    sys.exit(main())
