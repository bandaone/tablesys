from sqlalchemy.orm import Session
from ..models import TimetableSlot, Room, StudentGroup, Course
from typing import Dict, List, Optional
import operator

class NeuralBrainService:
    """
    The Brain of TABLESYS: Implements Neural Pattern Recognition and 
    Statistical Learning from historical schedules.
    Inspired by Bishop's PRML and Neural Networks for Pattern Recognition.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def analyze_history(self) -> Dict:
        """
        Sensory Layer: Scans historical slots to identify patterns.
        """
        slots = self.db.query(TimetableSlot).all()
        level_room_affinity = {}
        
        for slot in slots:
            group = self.db.query(StudentGroup).get(slot.group_id)
            if not group: continue
            
            level = str(group.level)
            room_id = slot.room_id
            
            if level not in level_room_affinity:
                level_room_affinity[level] = {}
            
            level_room_affinity[level][room_id] = level_room_affinity[level].get(room_id, 0) + 1
            
        results = {}
        for level, affinities in level_room_affinity.items():
            total = sum(affinities.values())
            for room_id, count in affinities.items():
                weight = count / total
                room = self.db.query(Room).get(room_id)
                if room:
                    # We store learned patterns in a separate 'learned' key 
                    # to keep Coordinator manual settings separate.
                    cache = room.coordinator_managed_affinities or {"manual": {}, "learned": {}}
                    if "learned" not in cache: cache["learned"] = {}
                    cache["learned"][f"level_{level}"] = round(weight, 3)
                    room.coordinator_managed_affinities = cache
                    
            results[level] = affinities
            
        self.db.commit()
        return results

    def get_link_weight(self, level: int, room: Room, time_idx: int, group_id: Optional[int] = None) -> float:
        """
        Cognitive Layer: Returns the 'Strength' of a neural link.
        PRIORITY 1: Coordinator's Manual Settings (Ground Assessment)
        PRIORITY 2: Coordinator's Per-Group Settings
        PRIORITY 3: Statistical Habits (Learned)
        """
        # 1. Baseline Global priority (Coordinator's set level 1-10)
        base_weight = (room.priority_level or 5) / 10.0
        
        # 2. Extract Managed Affinities
        manual_affinity = 0.0
        learned_affinity = 0.0
        time_bias = 0.1
        
        if room.coordinator_managed_affinities:
            cache = room.coordinator_managed_affinities
            manual = cache.get("manual", {})
            learned = cache.get("learned", {})
            
            # Coordinator's manual "Ground Assessment" for this Level/Dept
            manual_affinity = manual.get(f"level_{level}", 0.0)
            
            # If the Coordinator hasn't set it, we look at history
            learned_affinity = learned.get(f"level_{level}", 0.0)
            
            # Time bias (could also be manual, but keeping simplified)
            time_bias = cache.get("time_affinity", {}).get(str(time_idx), 0.1)

        # 3. Group-Specific Priority (Coordinators "On the Ground" specific group fix)
        group_priority_weight = 0.0
        if group_id:
            group = self.db.query(StudentGroup).get(group_id)
            if group and group.preferred_venues:
                group_priority_weight = group.preferred_venues.get(str(room.id), 0.0) / 10.0

        # Weighted Sum (The Brain's Decision Formula)
        # We give the COORD SETTINGS the absolute dominance.
        # Coordinator Manual (0.4) + Group Priority (0.4) + Global Priority (0.1) + Learned (0.1)
        link_strength = (
            (manual_affinity * 0.4) + 
            (group_priority_weight * 0.4) + 
            (base_weight * 0.1) + 
            (learned_affinity * 0.1)
        )
        
        return round(link_strength, 4)

    def self_assemble_suggestions(self, level: int) -> List[Dict]:
        """
        Growth Layer: Suggest high-probability rooms for a level.
        Enables the 'Self-Assembling' behavior by flagging 'Ideal' venues.
        """
        all_rooms = self.db.query(Room).filter(Room.is_blocked == False).all()
        suggestions = []
        
        for room in all_rooms:
            weight = self.get_link_weight(level, room, 0) # simplified time_idx
            if weight > 0.6: # High confidence neural link
                suggestions.append({
                    "room_id": room.id,
                    "room_name": room.name,
                    "confidence": weight
                })
                
        # Sort by confidence
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        return suggestions
