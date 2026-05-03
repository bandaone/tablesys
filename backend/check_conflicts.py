from datetime import datetime, time, date
import sys
import os

sys.path.insert(0, '/home/on3/DENNIS/TABLESYS/backend')
from app.database import SessionLocal
from app.models import Room, TimetableSlot, RoomBooking, ExamPeriod, ExamSlotRoom, ExamSlot

db = SessionLocal()

room_name = "Ground Floor Room 10"
room = db.query(Room).filter(Room.name == room_name).first()
if not room:
    print(f"Room not found: {room_name}")
    sys.exit()

print(f"Room: {room.name} (ID: {room.id})")
print(f"Capacity: {room.capacity}, Blocked: {room.is_blocked}")

slots = db.query(TimetableSlot).filter(TimetableSlot.room_id == room.id).all()
print(f"\nTimetableSlots for room {room.id}:")
for s in slots:
    print(f"  ID:{s.id} Course:{s.course_id} Day:{s.day_of_week} {s.start_time}-{s.end_time} Type:{s.session_type}")

bookings = db.query(RoomBooking).filter(RoomBooking.room_id == room.id).all()
print(f"\nRoomBookings for room {room.id}:")
for b in bookings:
    print(f"  ID:{b.id} Course:{b.course_id} Date:{b.booking_date} {b.start_time}-{b.end_time} Type:{b.booking_type}")
