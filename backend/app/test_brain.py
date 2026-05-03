import sys
import os
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.services.neural_brain import NeuralBrainService
from app.models import TimetableSlot, Room, StudentGroup

def test_brain():
    db = SessionLocal()
    brain = NeuralBrainService(db)
    
    print("--- Bootstrapping Manual Patterns ---")
    brain.bootstrap_manual_patterns()
    
    print("\n--- Verifying Intuition (2nd Years in MLT) ---")
    mlt_room = db.query(Room).filter(Room.name.ilike("%MLT%")).first()
    if mlt_room:
        weight = brain.get_link_weight(2, mlt_room, 1) # morning
        print(f"Weight for 2nd Year in {mlt_room.name} (Morning): {weight}")
        
    print("\n--- Verifying Time Affinity (Labs in Afternoon) ---")
    lab_room = db.query(Room).filter(Room.room_type == "lab").first()
    if lab_room:
        morning_weight = brain.get_link_weight(4, lab_room, 1) # 09:00
        afternoon_weight = brain.get_link_weight(4, lab_room, 6) # 14:00
        print(f"Lab {lab_room.name} - Morning: {morning_weight}, Afternoon: {afternoon_weight}")

if __name__ == "__main__":
    test_brain()
