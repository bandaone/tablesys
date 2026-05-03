"""
Debug Generation Script - Full timetable generation with verbose logging
Use this to see exactly what happens during generation.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Timetable, Course, Room, StudentGroup, Lecturer
from app.services.timetable_generator import TimetableGenerator
from app.config import settings
from datetime import datetime

# Create database connection
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def print_section(title):
    """Print section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def create_test_timetable(db):
    """Create a test timetable if none exists"""
    tt = Timetable(
        name=f"Debug Test Timetable",
        semester="Second",
        year=2026,
        academic_half="first_half",
        is_active=False
    )
    db.add(tt)
    db.commit()
    db.refresh(tt)
    return tt

def progress_logger(data):
    """Simple progress callback"""
    level = data.get('level', '?')
    status = data.get('status', '?')
    percentage = data.get('percentage', 0)
    message = data.get('message', '')
    
    icons = {
        'starting': '🚀',
        'building': '🔧',
        'solving': '🧠',
        'extracting': '📦',
        'completed': '✅',
        'failed': '❌',
        'finalizing': '💾'
    }
    
    icon = icons.get(status, '📍')
    print(f"{icon} [{percentage:5.1f}%] Level {level}: {message}")

def main():
    """Run debug generation"""
    print("\n🐛 TABLESYS DEBUG GENERATION")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")
    
    db = SessionLocal()
    
    try:
        # Step 1: Check data
        print_section("STEP 1: DATA AUDIT")
        
        stats = {
            'Courses': db.query(Course).count(),
            'Rooms': db.query(Room).count(),
            'Groups': db.query(StudentGroup).count(),
            'Lecturers': db.query(Lecturer).count()
        }
        
        print("Current database stats:")
        for entity, count in stats.items():
            print(f"  {entity}: {count}")
        
        if stats['Courses'] == 0:
            print("\n❌ ERROR: No courses in database")
            print("   Run: python seed_db.py")
            return 1
        
        # Step 2: Check by level
        print_section("STEP 2: COURSES BY LEVEL")
        
        for level in [5, 4, 3, 2]:
            count = db.query(Course).filter(Course.level == level).count()
            print(f"  Level {level}: {count} courses")
            
            if count == 0:
                print(f"    ⚠️ No courses for level {level} - will be skipped")
        
        # Step 3: Create timetable
        print_section("STEP 3: CREATE TEST TIMETABLE")
        
        timetable = create_test_timetable(db)
        print(f"✅ Created timetable ID: {timetable.id}")
        print(f"   Name: {timetable.name}")
        print(f"   Semester: {timetable.semester} {timetable.year}")
        
        # Step 4: Initialize generator
        print_section("STEP 4: INITIALIZE GENERATOR")
        
        generator = TimetableGenerator(
            db=db,
            timetable_id=timetable.id,
            progress_callback=progress_logger
        )
        
        print("✅ Generator initialized")
        print(f"   Days: {generator.days}")
        print(f"   Time slots: {len(generator.time_slots)} per day")
        
        # Step 5: Run generation
        print_section("STEP 5: RUN GENERATION")
        print("Starting generation... (this may take a while)")
        print("")
        
        start_time = datetime.now()
        
        try:
            success = generator.generate_timetable()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print("")
            print_section("STEP 6: RESULTS")
            
            if success:
                print("✅ GENERATION SUCCESSFUL!")
                print(f"   Duration: {duration:.2f} seconds")
                print(f"   Total slots created: {len(generator.all_slots)}")
                
                # Show sample slots
                if generator.all_slots:
                    print("\n   Sample slots:")
                    for slot in generator.all_slots[:5]:
                        course = db.query(Course).get(slot['course_id'])
                        room = db.query(Room).get(slot['room_id'])
                        print(f"     - {course.code} in {room.name} on "
                              f"{slot['day']} at {slot['start_time']}")
                    
                    if len(generator.all_slots) > 5:
                        print(f"     ... and {len(generator.all_slots) - 5} more")
                
                return 0
            else:
                print("❌ GENERATION FAILED")
                print(f"   Duration: {duration:.2f} seconds")
                print("\n   Possible reasons:")
                print("   1. Over-constrained problem (no valid solution exists)")
                print("   2. Insufficient resources (rooms, lecturers)")
                print("   3. Conflicting requirements")
                print("\n   Debugging tips:")
                print("   - Check if all courses have lecturers assigned")
                print("   - Verify room types match course requirements")
                print("   - Try reducing the number of courses")
                return 1
                
        except Exception as e:
            print("")
            print_section("STEP 6: ERROR")
            print(f"❌ EXCEPTION during generation: {e}")
            import traceback
            traceback.print_exc()
            return 1
            
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()

if __name__ == "__main__":
    sys.exit(main())
