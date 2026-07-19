from app.database import SessionLocal
from app.models import TimetableSlot, StudentGroup, Course, Room, Timetable
from sqlalchemy.orm import joinedload
from datetime import datetime

db = SessionLocal()

# Get the most recent active timetable
active_timetable = db.query(Timetable).filter(Timetable.is_active == True).order_by(Timetable.id.desc()).first()

if not active_timetable:
    print("No active timetable found.")
    exit(0)

print(f"Analyzing Timetable: {active_timetable.name} (ID: {active_timetable.id})")

# Get all slots for this timetable
slots = db.query(TimetableSlot).options(
    joinedload(TimetableSlot.group),
    joinedload(TimetableSlot.course),
    joinedload(TimetableSlot.room)
).filter(TimetableSlot.timetable_id == active_timetable.id).all()

# Group by group_id and day_of_week
from collections import defaultdict
grouped_slots = defaultdict(list)

for slot in slots:
    if slot.group_id and slot.room_id:
        grouped_slots[(slot.group_id, slot.day_of_week)].append(slot)

# Find back-to-back issues in different rooms
issues_found = 0

print("\n--- Transit Time Issues Found ---")
for (group_id, day), day_slots in grouped_slots.items():
    # Sort slots by start time
    day_slots.sort(key=lambda x: x.start_time)
    
    for i in range(len(day_slots) - 1):
        current_slot = day_slots[i]
        next_slot = day_slots[i+1]
        
        # Check if current slot ends exactly when next slot begins
        if current_slot.end_time == next_slot.start_time:
            # Check if they are in different rooms
            if current_slot.room_id != next_slot.room_id:
                issues_found += 1
                group_name = current_slot.group.name if current_slot.group else f"Group {group_id}"
                c_course = current_slot.course.code if current_slot.course else "Unknown"
                n_course = next_slot.course.code if next_slot.course else "Unknown"
                c_room = current_slot.room.name if current_slot.room else "Unknown"
                n_room = next_slot.room.name if next_slot.room else "Unknown"
                
                print(f"Issue #{issues_found}:")
                print(f"  Group: {group_name}")
                print(f"  Day  : {day}")
                print(f"  Time : {current_slot.start_time}-{current_slot.end_time} ({c_course} in {c_room}) -> {next_slot.start_time}-{next_slot.end_time} ({n_course} in {n_room})")
                print(f"  Gap  : 0 minutes transit time between {c_room} and {n_room}")
                print()

if issues_found == 0:
    print("No zero-transit-time back-to-back room changes found.")
else:
    print(f"Total issues found: {issues_found}")

