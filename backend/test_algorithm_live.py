from app.services.timetable_generator import TimetableGenerator
from app.schemas import Room, Lecturer, StudentGroup

# 1. Setup Data
rooms = [
    Room(id=1, name="LH1", capacity=100, room_type="lecture_hall", building="Main", department_id=1),
    Room(id=2, name="LAB1", capacity=30, room_type="lab", building="CS Block", department_id=1)
]

lecturers = [
    Lecturer(id=1, staff_number="L001", full_name="Dr. Smith", email="smith@test.com", department_id=1, max_hours_per_week=20, availability_blocks=[{"day": "Monday", "start_hour": 8, "end_hour": 12}]),
    Lecturer(id=2, staff_number="L002", full_name="Prof. Johnson", email="johnson@test.com", department_id=1, max_hours_per_week=20, availability_blocks=[])
]

courses = [
    {"id": 1, "code": "CS101", "name": "Intro to CS", "level": 100, "lecture_hours": 2, "practical_hours": 2, "tutorial_hours": 0, "department_id": 1, "credits": 4},
    {"id": 2, "code": "CS102", "name": "Data Structures", "level": 100, "lecture_hours": 3, "practical_hours": 0, "tutorial_hours": 1, "department_id": 1, "credits": 4}
]

groups = [
    StudentGroup(id=1, name="BSc CS Y1", level=100, size=50, department_id=1)
]

config = {
    "start_hour": 8,
    "end_hour": 17,
    "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
}

# 2. Run Generator
generator = TimetableGenerator(rooms=rooms, lecturers=lecturers, grid_config=config, max_time_seconds=30)
assignments = generator.generate_level_timetable(level=100, courses=courses, groups=groups)

# 3. Print Results
print("\n" + "="*80)
print("🎯 TIMETABLE ALGORITHM SCAN RESULTS")
print("="*80)
if not assignments:
    print("❌ FAILED: The CP-SAT solver could not find a feasible solution.")
else:
    print(f"✅ SUCCESS: Generated {len(assignments)} timeslot assignments!\n")
    print(f"{'DAY':<12} | {'TIME':<13} | {'COURSE':<10} | {'TYPE':<10} | {'ROOM':<6} | LECTURER ID")
    print("-" * 80)
    for a in assignments:
        time_str = f"{a['start_time']:02d}:00-{a['end_time']:02d}:00"
        print(f"{a['day']:<12} | {time_str:<13} | {a['course_code']:<10} | {a['session_type']:<10} | {a['room_name']:<6} | {a['lecturer_id']}")
print("="*80 + "\n")
