from sqlalchemy.orm import Session
from ..models import Timetable, TimetableSlot, Course, Room, StudentGroup, Lecturer
from typing import Dict, Any
from collections import defaultdict

class ExportService:
    def __init__(self, db: Session):
        self.db = db

    def get_traditional_export_data(self, timetable_id: int) -> Dict[str, Any]:
        """
        Prepare data for the traditional grid view:
        Rows: 07:00 - 19:00
        Columns: 2nd Year (GEN LG1, LG2) | 3rd-5th (Depts)
        """
        timetable = self.db.query(Timetable).get(timetable_id)
        slots = self.db.query(TimetableSlot).filter(TimetableSlot.timetable_id == timetable_id).all()
        
        # Structure: data[day][hour][column_key] = [Slot info]
        # Column Keys: "GEN LG1", "GEN LG2", "AEN-3", "CEE-3", ...
        
        export_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        

        
        for slot in slots:
            course = self.db.query(Course).get(slot.course_id)
            room = self.db.query(Room).get(slot.room_id)
            group = self.db.query(StudentGroup).get(slot.group_id)
            lecturer = self.db.query(Lecturer).get(slot.lecturer_id)
            
            # Determine Column Key
            col_key = self._determine_column_key(group, course)
            
            day_name = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"][slot.day_of_week]
            start_hour = slot.start_time.strftime("%H:%M")
            
            entry = {
                "course_code": course.code,
                "room_name": room.name,
                "group_name": group.name,
                "lecturer_name": lecturer.full_name,
                "session_type": slot.session_type
            }
            
            export_data[day_name][start_hour][col_key].append(entry)
            
        return {
            "timetable_name": timetable.name,
            "semester": timetable.semester,
            "year": timetable.year,
            "academic_half": getattr(timetable, "academic_half", "first_half"),
            "grid_data": export_data
        }

    def _determine_column_key(self, group: StudentGroup, course: Course) -> str:
        """Map a group to a specific column in the traditional format"""
        # Logic to map 2nd year groups to GEN LG1/LG2
        if group.level == 2:
            if "LG1" in group.name or "GEN1" in group.name:
                return "GEN LG1"
            return "GEN LG2"
            
        # Logic for 3rd-5th year: Map to Department
        # In this format, columns are Dept headers under Year headers
        # We'll return a key like "LEVEL-DEPT" e.g., "3-AEN"
        
        # Only extract the Dept code
        dept_code = group.department.code if group.department else "UNK"
        
        return f"{group.level}-{dept_code}"
