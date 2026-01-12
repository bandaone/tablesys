from ortools.sat.python import cp_model
from sqlalchemy.orm import Session
from typing import Dict, Callable
from datetime import time
from ..models import Course, Lecturer, Room, StudentGroup, TimetableSlot

class TimetableGenerator:
    def __init__(self, db: Session, timetable_id: int, progress_callback: Callable = None):
        self.db = db
        self.timetable_id = timetable_id
        self.progress_callback = progress_callback
        
        # Time slots configuration (8:00 - 17:00, 1-hour slots)
        self.days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        self.time_slots = [
            (time(8, 0), time(9, 0)),
            (time(9, 0), time(10, 0)),
            (time(10, 0), time(11, 0)),
            (time(11, 0), time(12, 0)),
            (time(12, 0), time(13, 0)),
            (time(13, 0), time(14, 0)),
            (time(14, 0), time(15, 0)),
            (time(15, 0), time(16, 0)),
            (time(16, 0), time(17, 0)),
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
    
    def generate_level_timetable(self, level: int, progress_start: float, progress_end: float) -> bool:
        """Generate timetable for a specific level using CP-SAT solver"""
        
        # Get all courses for this level
        courses = self.db.query(Course).filter(Course.level == level).all()
        
        if not courses:
            return True  # No courses for this level, skip
        
        self.send_progress(
            level=level,
            status='loading',
            percentage=progress_start + 5,
            message=f'Loading {len(courses)} courses for Level {level}...'
        )
        
        # Get groups for this level
        groups = self.db.query(StudentGroup).filter(StudentGroup.level == level).all()
        
        if not groups:
            return True  # No groups, skip
        
        # Get all available rooms
        rooms = self.db.query(Room).all()
        
        # Create the CP-SAT model
        model = cp_model.CpModel()
        
        self.send_progress(
            level=level,
            status='building',
            percentage=progress_start + 10,
            message=f'Building constraint model for Level {level}...'
        )
        
        # Variables: assignment[course][group][day][time_slot][room][lecturer]
        assignments = {}
        
        for course in courses:
            # Get lecturers assigned to this course
            lecturer_assignments = self.db.query(LecturerAssignment).filter(
                LecturerAssignment.course_id == course.id
            ).all()
            lecturers = [self.db.query(Lecturer).get(la.lecturer_id) for la in lecturer_assignments]
            
            if not lecturers:
                continue
            
            # Get groups assigned to this course
            group_assignments = self.db.query(GroupAssignment).filter(
                GroupAssignment.course_id == course.id
            ).all()
            course_groups = [self.db.query(StudentGroup).get(ga.group_id) for ga in group_assignments]
            
            if not course_groups:
                continue
            
            for group in course_groups:
                for day_idx, day in enumerate(self.days):
                    for time_idx, (start_time, end_time) in enumerate(self.time_slots):
                        for room in rooms:
                            for lecturer in lecturers:
                                var_name = f'c{course.id}_g{group.id}_d{day_idx}_t{time_idx}_r{room.id}_l{lecturer.id}'
                                assignments[(course.id, group.id, day_idx, time_idx, room.id, lecturer.id)] = \
                                    model.NewBoolVar(var_name)
        
        self.send_progress(
            level=level,
            status='constraints',
            percentage=progress_start + 30,
            message=f'Adding constraints for Level {level}...'
        )
        
        # Constraint 1: Each course-group combination must have the required number of hours
        for course in courses:
            group_assignments = self.db.query(GroupAssignment).filter(
                GroupAssignment.course_id == course.id
            ).all()
            course_groups = [self.db.query(StudentGroup).get(ga.group_id) for ga in group_assignments]
            
            for group in course_groups:
                # Calculate total required hours
                total_hours = course.lecture_hours + course.tutorial_hours + course.practical_hours
                
                # Sum all assignments for this course-group combination
                course_group_vars = [
                    assignments[(course.id, group.id, d, t, r, l)]
                    for (c, g, d, t, r, l) in assignments.keys()
                    if c == course.id and g == group.id
                ]
                
                if course_group_vars:
                    model.Add(sum(course_group_vars) == total_hours)
        
        # Constraint 2: No room can be used by multiple courses at the same time
        for day_idx in range(len(self.days)):
            for time_idx in range(len(self.time_slots)):
                for room in rooms:
                    room_vars = [
                        assignments[(c, g, d, t, r, l)]
                        for (c, g, d, t, r, l) in assignments.keys()
                        if d == day_idx and t == time_idx and r == room.id
                    ]
                    
                    if room_vars:
                        model.Add(sum(room_vars) <= 1)
        
        # Constraint 3: No lecturer can teach multiple courses at the same time
        lecturers_in_level = set()
        for course in courses:
            lecturer_assignments = self.db.query(LecturerAssignment).filter(
                LecturerAssignment.course_id == course.id
            ).all()
            for la in lecturer_assignments:
                lecturers_in_level.add(la.lecturer_id)
        
        for lecturer_id in lecturers_in_level:
            for day_idx in range(len(self.days)):
                for time_idx in range(len(self.time_slots)):
                    lecturer_vars = [
                        assignments[(c, g, d, t, r, l)]
                        for (c, g, d, t, r, l) in assignments.keys()
                        if d == day_idx and t == time_idx and l == lecturer_id
                    ]
                    
                    if lecturer_vars:
                        model.Add(sum(lecturer_vars) <= 1)
        
        # Constraint 4: No group can have multiple courses at the same time
        for group in groups:
            for day_idx in range(len(self.days)):
                for time_idx in range(len(self.time_slots)):
                    group_vars = [
                        assignments[(c, g, d, t, r, l)]
                        for (c, g, d, t, r, l) in assignments.keys()
                        if g == group.id and d == day_idx and t == time_idx
                    ]
                    
                    if group_vars:
                        model.Add(sum(group_vars) <= 1)
        
        # Constraint 5: Check for already scheduled slots from previous levels
        for slot in self.all_slots:
            for day_idx in range(len(self.days)):
                if self.days[day_idx] == slot['day']:
                    for time_idx, (start, end) in enumerate(self.time_slots):
                        if start == slot['start_time']:
                            # Block this room
                            room_vars = [
                                assignments[(c, g, d, t, r, l)]
                                for (c, g, d, t, r, l) in assignments.keys()
                                if d == day_idx and t == time_idx and r == slot['room_id']
                            ]
                            if room_vars:
                                model.Add(sum(room_vars) == 0)
                            
                            # Block this lecturer
                            lecturer_vars = [
                                assignments[(c, g, d, t, r, l)]
                                for (c, g, d, t, r, l) in assignments.keys()
                                if d == day_idx and t == time_idx and l == slot['lecturer_id']
                            ]
                            if lecturer_vars:
                                model.Add(sum(lecturer_vars) == 0)
        
        self.send_progress(
            level=level,
            status='solving',
            percentage=progress_start + 50,
            message=f'Solving constraints for Level {level}... This may take a moment.'
        )
        
        # Solve the model
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 300  # 5 minutes max per level
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            self.send_progress(
                level=level,
                status='extracting',
                percentage=progress_start + 80,
                message=f'Extracting solution for Level {level}...'
            )
            
            # Extract solution
            for (course_id, group_id, day_idx, time_idx, room_id, lecturer_id), var in assignments.items():
                if solver.Value(var) == 1:
                    course = self.db.query(Course).get(course_id)
                    
                    # Determine session type based on hours
                    session_type = 'lecture'
                    if course.practical_hours > 0:
                        session_type = 'practical'
                    elif course.tutorial_hours > 0:
                        session_type = 'tutorial'
                    
                    slot_data = {
                        'course_id': course_id,
                        'lecturer_id': lecturer_id,
                        'room_id': room_id,
                        'group_id': group_id,
                        'day': self.days[day_idx],
                        'day_of_week': day_idx,
                        'start_time': self.time_slots[time_idx][0],
                        'end_time': self.time_slots[time_idx][1],
                        'session_type': session_type
                    }
                    self.all_slots.append(slot_data)
            
            return True
        else:
            return False
    
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
