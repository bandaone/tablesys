from app.database import SessionLocal
from app.models import TimetableSlot, Course, Room

db = SessionLocal()
slots = db.query(TimetableSlot).filter(TimetableSlot.timetable_id == 5).all()
print(f"Total slots for TT 5: {len(slots)}")
for s in slots[:5]:
    print(s.id, s.course_id, s.room_id, s.lecturer_id)
