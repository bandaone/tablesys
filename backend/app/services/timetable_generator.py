from ortools.sat.python import cp_model
from sqlalchemy.orm import Session
from typing import Dict, Callable, List
from datetime import time
from ..models import (
    Timetable, TimetableSlot, Room, Course, Lecturer,
    StudentGroup, GroupAssignment, LecturerAssignment,
    RoomType, UserRole, CourseType
)

class TimetableGenerator:
    def __init__(self, db: Session, timetable_id: int, progress_callback: Callable = None):
        self.db = db
        self.timetable_id = timetable_id
        self.progress_callback = progress_callback
        
        # Time slots configuration (07:00 - 19:00, 1-hour slots)
        self.days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        # 12 slots per day: 07:00, 08:00, ..., 18:00
        self.time_slots = [
            (time(7 + i, 0), time(8 + i, 0)) for i in range(12)
        ]
        
        self.all_slots = []  # Will store all generated slots
    
    def send_progress(self, level: int, status: str, percentage: float, message: str):
        """Send progress update via callback"""
        if self.progress_callback:
            self.progress_callback({
                'level': level,
                'status': status,
                'percentage': percentage,
                'message': message
            })
    
    def generate_timetable(self) -> bool:
        """Generate timetable level by level: 5th -> 4th -> 3rd -> 2nd"""
        levels = [5, 4, 3, 2]
        total_levels = len(levels)
        
        for idx, level in enumerate(levels):
            level_percentage_start = (idx / total_levels) * 100
            level_percentage_end = ((idx + 1) / total_levels) * 100
            
            self.send_progress(
                level=level,
                status='starting',
                percentage=level_percentage_start,
                message=f'Starting timetable generation for Level {level}...'
            )
            
            # Generate timetable for this level
            success = self.generate_level_timetable(level, level_percentage_start, level_percentage_end)
            
            if not success:
                self.send_progress(
                    level=level,
                    status='failed',
                    percentage=level_percentage_start,
                    message=f'Failed to generate timetable for Level {level}'
                )
                return False
            
            self.send_progress(
                level=level,
                status='completed',
                percentage=level_percentage_end,
                message=f'Level {level} timetable completed successfully'
            )
        
        # Save all slots to database
        self.send_progress(
            level=0,
            status='finalizing',
            percentage=95,
            message='Combining all levels and saving timetable...'
        )
        
        self.save_timetable()
        
        self.send_progress(
            level=0,
            status='completed',
            percentage=100,
            message='Timetable generation completed successfully!'
        )
        
        return True
    
    def _parse_course_sessions(self, course: Course) -> List[Dict]:
        """
        Break down a course into required sessions (blocks) based on config.
        Returns list of dicts: {'type': 'lecture', 'duration': 2, 'id': 0}
        """
        sessions = []
        
        # Parse session configuration
        config = course.session_configuration or {}
        # Default: respect consecutive requirements if present, else 1-hour blocks?
        # Actually, if lecture_hours=4 and consecutive=2, we want 2 blocks of 2.
        
        requires_consecutive = config.get('requires_consecutive', 1)
        if isinstance(requires_consecutive, bool):
             requires_consecutive = 2 if requires_consecutive else 1
        
        requires_consecutive = int(requires_consecutive)
        
        # 1. Lectures
        lecture_hours = course.lecture_hours
        while lecture_hours > 0:
            duration = min(requires_consecutive, lecture_hours)
            sessions.append({
                'type': 'lecture',
                'duration': duration,
                'course_id': course.id,
                's_id': len(sessions)
            })
            lecture_hours -= duration
            
        # 2. Tutorials
        # Tutorials usually 1 or 2 hours
        tut_hours = course.tutorial_hours
        while tut_hours > 0:
            duration = min(tut_hours, 2) # Cap tutorial blocks at 2 hours usually
            sessions.append({
                'type': 'tutorial',
                'duration': duration,
                'course_id': course.id,
                's_id': len(sessions)
            })
            tut_hours -= duration
            
        # 3. Practicals (Labs)
        # Labs are often 3 hours
        prac_hours = course.practical_hours
        while prac_hours > 0:
            duration = min(prac_hours, 3) # Cap lab blocks at 3 hours usually
            sessions.append({
                'type': 'practical',
                'duration': duration,
                'course_id': course.id,
                's_id': len(sessions)
            })
            prac_hours -= duration
            
        return sessions

    def _get_compatible_rooms(self, course: Course, session_type: str, all_rooms: List[Room]) -> List[Room]:
        """Filter rooms based on course preferences and capability"""
        compatible_rooms = []
        
        for room in all_rooms:
            # 1. Check Department Affinity
            if room.department_affinity:
                # If room has affinity, course must match.
                # Assuming department mapping or just checking if course.department.code matches
                # simplified: if affinity is string, check if it is part of display code or dept name
                # For now, strict check if available, or skip generic rooms
                pass 
                # Refined logic: If affinity is set, room is restricted.
                # But we don't have easy link to Dept Code here without extra queries.
                # Let's rely on room_type for now mostly.
            
            # 2. Check Room Type/Category
            # Map Course Preferred Room Type to Room Type
            # Course.preferred_room_type is enum RoomType (lecture_hall, lab, etc)
            # Room.room_type is string (legacy) or room_category (new Enum)
            
            if course.preferred_room_type == RoomType.ANY:
                # Allow any room that fits capacity (maybe)
                # But prefer Lecture Halls for Lectures
                if session_type == 'lecture' and 'lecture' in str(room.room_type).lower():
                    compatible_rooms.append(room)
                elif session_type == 'practical' and 'lab' in str(room.room_type).lower():
                    compatible_rooms.append(room)
                else:
                    compatible_rooms.append(room)
                continue

            # Strict matching if preference is set
            pref = course.preferred_room_type
            
            # Map Enum to string checks
            if pref == RoomType.LECTURE_HALL:
                if 'lecture' in str(room.room_type).lower() or 'class' in str(room.room_type).lower():
                    compatible_rooms.append(room)
            elif pref == RoomType.LAB:
                if 'lab' in str(room.room_type).lower():
                    compatible_rooms.append(room)
            elif pref == RoomType.DRAWING_ROOM:
                if 'drawing' in str(room.room_type).lower():
                    compatible_rooms.append(room)
            else:
                # Default loose match
                compatible_rooms.append(room)
                
        return compatible_rooms

    def generate_level_timetable(self, level: int, progress_start: float, progress_end: float) -> bool:
        """Generate timetable for a specific level using CP-SAT solver"""
        
        # 1. Fetch Data
        courses = self.db.query(Course).filter(Course.level == level).all()
        if not courses: return True
        
        groups = self.db.query(StudentGroup).filter(StudentGroup.level == level).all()
        if not groups: return True
        
        all_rooms = self.db.query(Room).all()
        
        self.send_progress(level, 'building', progress_start + 10, f'Preparing constraints for {len(courses)} courses...')
        
        model = cp_model.CpModel()
        
        # 2. Variables
        # Key: (course_id, group_id, session_idx, day, start_time, room_id, lecturer_id) -> BoolVar
        # To reduce size, we will only create valid variables
        
        vars_store = {} # Key -> BoolVar
        course_sessions = {} # course_id -> list of session dicts
        
        # Pre-process sessions
        for course in courses:
            course_sessions[course.id] = self._parse_course_sessions(course)
            
        # Loop to create variables
        for course in courses:
            # Lecturers
            lecturer_assignments = self.db.query(LecturerAssignment).filter(LecturerAssignment.course_id == course.id).all()
            possible_lecturers = [la.lecturer_id for la in lecturer_assignments]
            if not possible_lecturers: continue # Skip courses with no lecturer? Or allow TBD? For now skip.
            
            # Groups
            group_assignments = self.db.query(GroupAssignment).filter(GroupAssignment.course_id == course.id).all()
            possible_groups = [ga.group_id for ga in group_assignments]
            if not possible_groups: continue
            
            sessions = course_sessions[course.id]
            
            for session in sessions:
                duration = session['duration']
                s_id = session['s_id']
                
                # Filter valid rooms
                valid_rooms = self._get_compatible_rooms(course, session['type'], all_rooms)
                
                for group_id in possible_groups:
                    # Constraint: Create variables for each potential slot
                    for day_idx in range(len(self.days)):
                        # Ensure session fits in day (duration)
                        # Time slots are 0 to 11 (07:00 to 18:00 start)
                        # Last valid start index = 12 - duration
                        for start_t in range(12 - duration + 1):
                            
                            for room in valid_rooms:
                                for lecturer_id in possible_lecturers:
                                    # Create Variable
                                    var_name = f'c{course.id}_g{group_id}_s{s_id}_d{day_idx}_t{start_t}_r{room.id}_l{lecturer_id}'
                                    var = model.NewBoolVar(var_name)
                                    
                                    key = (course.id, group_id, s_id, day_idx, start_t, room.id, lecturer_id)
                                    vars_store[key] = var
        
        # 3. Constraints
        
        # C1. Each Session must be assigned exactly once per Group
        for course in courses:
            group_ids = [ga.group_id for ga in self.db.query(GroupAssignment).filter(GroupAssignment.course_id == course.id).all()]
            for group_id in group_ids:
                sessions = course_sessions[course.id]
                for session in sessions:
                    # Gather all vars for this specific session
                    session_vars = []
                    for k, var in vars_store.items():
                        # k: (c, g, s, d, t, r, l)
                        if k[0] == course.id and k[1] == group_id and k[2] == session['s_id']:
                            session_vars.append(var)
                    
                    if session_vars:
                        model.Add(sum(session_vars) == 1)
        
        # Helper to get "Active" status for resource at (day, time)
        # We need to map Block Starts to Time Coverage
        # A block starting at T with duration D covers [T, T+1, ..., T+D-1]
        
        # Optimization: Pre-calculate coverage maps?
        # Iterate Day, Time, Resource -> Sum constraints
        
        for day_idx in range(len(self.days)):
            for t_idx in range(12):
                
                # C2. Room Capacity / Overlap
                for room in all_rooms:
                    active_vars_room = []
                    # Check all variables that might cover this time
                    for k, var in vars_store.items():
                        # k: (c, g, s, d, start_t, r, l)
                        if k[3] == day_idx and k[5] == room.id:
                            start_t = k[4]
                            # Get duration
                            duration = course_sessions[k[0]][k[2]]['duration']
                            if start_t <= t_idx < start_t + duration:
                                active_vars_room.append(var)
                    
                    # Add Previous Level Constraints (Already scheduled slots)
                    # Check self.all_slots
                    is_blocked_externally = False
                    for slot in self.all_slots:
                        if slot['day_of_week'] == day_idx and slot['room_id'] == room.id:
                            slot_start_idx = self._time_to_idx(slot['start_time'])
                            slot_end_idx = self._time_to_idx(slot['end_time'])
                            # slot covers [start, end)
                            # t_idx covers [t, t+1)
                            # simplified: if t_idx matches any hour covered by slot
                            if slot_start_idx <= t_idx < slot_end_idx:
                                is_blocked_externally = True
                                break
                    
                    if is_blocked_externally:
                         if active_vars_room:
                             model.Add(sum(active_vars_room) == 0)
                    elif active_vars_room:
                        model.Add(sum(active_vars_room) <= 1)


                # C3. Lecturer Overlap
                # Get all unique lecturers in this level
                unique_lecturers = set(k[6] for k in vars_store.keys()) # k[6] is lecturer_id
                
                for lecturer_id in unique_lecturers:
                    active_vars_lec = []
                    for k, var in vars_store.items():
                        if k[3] == day_idx and k[6] == lecturer_id:
                            start_t = k[4]
                            duration = course_sessions[k[0]][k[2]]['duration']
                            if start_t <= t_idx < start_t + duration:
                                active_vars_lec.append(var)
                                
                    # External check
                    is_blocked_ext = False
                    for slot in self.all_slots:
                         if slot['day_of_week'] == day_idx and slot['lecturer_id'] == lecturer_id:
                            slot_start_idx = self._time_to_idx(slot['start_time'])
                            slot_end_idx = self._time_to_idx(slot['end_time'])
                            if slot_start_idx <= t_idx < slot_end_idx:
                                is_blocked_ext = True
                                break
                    
                    if is_blocked_ext:
                        if active_vars_lec:
                             model.Add(sum(active_vars_lec) == 0)
                    elif active_vars_lec:
                        model.Add(sum(active_vars_lec) <= 1)

                # C4. Group Overlap
                unique_groups = set(k[1] for k in vars_store.keys())
                for group_id in unique_groups:
                    active_vars_group = []
                    for k, var in vars_store.items():
                        if k[3] == day_idx and k[1] == group_id:
                            start_t = k[4]
                            duration = course_sessions[k[0]][k[2]]['duration']
                            if start_t <= t_idx < start_t + duration:
                                active_vars_group.append(var)
                    
                    # External check (if group was used in previous level?? Unlikely given strict levels, but safe to check)
                    # Actually, groups are usually distinct per level. But let's be safe.
                    is_blocked_ext = False
                    for slot in self.all_slots:
                         if slot['day_of_week'] == day_idx and slot['group_id'] == group_id:
                            slot_start_idx = self._time_to_idx(slot['start_time'])
                            slot_end_idx = self._time_to_idx(slot['end_time'])
                            if slot_start_idx <= t_idx < slot_end_idx:
                                is_blocked_ext = True
                                break
                    
                    if is_blocked_ext:
                        if active_vars_group: model.Add(sum(active_vars_group) == 0)
                    elif active_vars_group:
                        model.Add(sum(active_vars_group) <= 1)

        # 4. Soft Constraints & Objectives
        # Lecturer Preferences: Avoid Early Morning (07:00 at index 0) / Late Afternoon (17:00+ at index 10, 11)
        objective_terms = []
        
        for k, var in vars_store.items():
            # k: (c, g, s, d, start_t, r, l)
            lecturer_id = k[6]
            start_t = k[4]
            duration = course_sessions[k[0]][k[2]]['duration']
            end_t = start_t + duration
            
            lecturer = self.db.query(Lecturer).get(lecturer_id)
            if lecturer and lecturer.teaching_preferences:
                prefs = lecturer.teaching_preferences
                if isinstance(prefs, dict):
                    # Avoid Early Morning (07:00 start)
                    if prefs.get('avoid_early_morning') and start_t == 0:
                        objective_terms.append(var) # Minimize this being true
                    
                    # Avoid Late Afternoon (Any part of session touches 17:00+ i.e. index >= 10)
                    # 17:00 is index 10. 18:00 is index 11.
                    if prefs.get('avoid_late_afternoon') and end_t > 10:
                        objective_terms.append(var)

        if objective_terms:
            model.Minimize(sum(objective_terms))

        # 5. Solve
        self.send_progress(level, 'solving', progress_start + 60, f'Solving constraints for Level {level}...')
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 300
        
        status = solver.Solve(model)
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            self.send_progress(level, 'extracting', progress_start + 90, 'solution found! processing...')
            
            # Extract
            for k, var in vars_store.items():
                if solver.Value(var) == 1:
                    course_id, group_id, s_id, day_idx, start_t, room_id, lecturer_id = k
                    session_meta = course_sessions[course_id][s_id]
                    duration = session_meta['duration']
                    
                    # Create slot for each hour of the block (to match DB structure)
                    for i in range(duration):
                        current_t = start_t + i
                        slot_data = {
                            'course_id': course_id,
                            'lecturer_id': lecturer_id,
                            'room_id': room_id,
                            'group_id': group_id,
                            'day': self.days[day_idx],
                            'day_of_week': day_idx,
                            'start_time': self.time_slots[current_t][0],
                            'end_time': self.time_slots[current_t][1],
                            'session_type': session_meta['type']
                        }
                        self.all_slots.append(slot_data)
            return True
        else:
            return False

    def _time_to_idx(self, t: time) -> int:
        """Convert time object to 0-11 index (07:00 start)"""
        # 07:00 -> 0
        return t.hour - 7

    def save_timetable(self):
        """Save all generated slots to the database"""
        for slot_data in self.all_slots:
            slot = TimetableSlot(
                course_id=slot_data['course_id'],
                lecturer_id=slot_data['lecturer_id'],
                room_id=slot_data['room_id'],
                group_id=slot_data['group_id'],
                day_of_week=slot_data['day_of_week'],
                start_time=slot_data['start_time'],
                end_time=slot_data['end_time'],
                session_type=slot_data['session_type'],
                timetable_id=self.timetable_id
            )
            self.db.add(slot)
        
        self.db.commit()
