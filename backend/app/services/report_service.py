"""
Report Service - Advanced Report Generation System
Generates custom reports with PDF/Excel export capabilities
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, distinct
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from io import BytesIO
import json

from ..models import User, Department, Course, Lecturer, Room, StudentGroup, Timetable, TimetableSlot
from ..auth import is_tenant_admin, is_school_operator


class ReportService:
    """Service for generating various system reports"""
    
    def __init__(self, db: Session, user: Optional[User] = None):
        self.db = db
        self.user = user

    def _scoped_departments(self):
        query = self.db.query(Department)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(Department.university_id == self.user.university_id)
        if self.user and is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
            query = query.filter(Department.school_id == self.user.school_id)
        return query

    def _scoped_lecturers(self):
        query = self.db.query(Lecturer).join(Department, Lecturer.department_id == Department.id)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(Department.university_id == self.user.university_id)
        if self.user and is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
            query = query.filter(Department.school_id == self.user.school_id)
        return query

    def _scoped_rooms(self):
        query = self.db.query(Room)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(Room.university_id == self.user.university_id)
        if self.user and is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
            query = query.filter((Room.school_id == self.user.school_id) | (Room.school_id == None))
        return query

    def _scoped_timetables(self):
        query = self.db.query(Timetable)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(Timetable.university_id == self.user.university_id)
        if self.user and is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
            query = query.filter((Timetable.school_id == self.user.school_id) | (Timetable.school_id == None))
        return query
    
    def generate_lecturer_workload_report(
        self,
        department_id: Optional[int] = None,
        lecturer_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate detailed workload report for lecturers
        Shows hours taught, courses assigned, and workload distribution
        """
        query = self._scoped_lecturers()
        
        if department_id:
            query = query.filter(Lecturer.department_id == department_id)
        if lecturer_id:
            query = query.filter(Lecturer.id == lecturer_id)
        
        lecturers = query.all()
        report_data = []
        
        for lecturer in lecturers:
            # Get all courses taught by this lecturer
            courses_taught = self.db.query(
                Course.code,
                Course.name,
                Course.credit_hours,
                func.count(TimetableSlot.id).label('slot_count')
            ).join(TimetableSlot, TimetableSlot.course_id == Course.id)\
             .filter(TimetableSlot.lecturer_id == lecturer.id)\
             .group_by(Course.id, Course.code, Course.name, Course.credit_hours).all()
            
            total_hours = sum(c.credit_hours for c in courses_taught)
            total_slots = sum(c.slot_count for c in courses_taught)
            
            # Get department name
            dept = self._scoped_departments().filter(Department.id == lecturer.department_id).first()
            
            # Workload status
            workload_status = 'optimal'
            if total_hours > 16:
                workload_status = 'overloaded'
            elif total_hours < 8:
                workload_status = 'underutilized'
            
            report_data.append({
                'lecturer_id': lecturer.id,
                'staff_number': lecturer.staff_number,
                'name': lecturer.full_name,
                'email': lecturer.email,
                'department': dept.name if dept else 'N/A',
                'department_code': dept.code if dept else 'N/A',
                'max_hours': lecturer.max_hours_per_week,
                'actual_hours': total_hours,
                'total_slots': total_slots,
                'workload_percentage': round((total_hours / lecturer.max_hours_per_week) * 100, 2) if lecturer.max_hours_per_week > 0 else 0,
                'workload_status': workload_status,
                'courses': [
                    {
                        'code': c.code,
                        'name': c.name,
                        'credit_hours': c.credit_hours,
                        'slot_count': c.slot_count
                    } for c in courses_taught
                ]
            })
        
        # Calculate summary statistics
        total_lecturers = len(report_data)
        avg_hours = sum(l['actual_hours'] for l in report_data) / total_lecturers if total_lecturers > 0 else 0
        overloaded_count = sum(1 for l in report_data if l['workload_status'] == 'overloaded')
        underutilized_count = sum(1 for l in report_data if l['workload_status'] == 'underutilized')
        
        return {
            'report_type': 'lecturer_workload',
            'generated_at': datetime.utcnow().isoformat(),
            'filters': {
                'department_id': department_id,
                'lecturer_id': lecturer_id
            },
            'summary': {
                'total_lecturers': total_lecturers,
                'average_hours': round(avg_hours, 2),
                'overloaded_lecturers': overloaded_count,
                'underutilized_lecturers': underutilized_count,
                'optimal_lecturers': total_lecturers - overloaded_count - underutilized_count
            },
            'data': report_data
        }
    
    def generate_room_utilization_report(
        self,
        building: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate room utilization report
        Shows usage statistics, capacity utilization, and availability
        """
        query = self._scoped_rooms()
        
        if building:
            query = query.filter(Room.building == building)
        if category:
            query = query.filter(Room.category == category)
        
        rooms = query.all()
        report_data = []
        
        # Weekly time slots (5 days * 8 hours = 40 slots per week)
        total_possible_slots = 40
        
        for room in rooms:
            # Count slots assigned to this room
            slots_used = self.db.query(func.count(TimetableSlot.id))\
                .filter(TimetableSlot.room_id == room.id).scalar() or 0
            
            # Calculate utilization percentage
            utilization_percent = round((slots_used / total_possible_slots) * 100, 2)
            
            # Get courses using this room
            courses_in_room = self.db.query(
                Course.code,
                Course.name,
                StudentGroup.name.label('group_name'),
                StudentGroup.size,
                func.count(TimetableSlot.id).label('slot_count')
            ).join(TimetableSlot, TimetableSlot.room_id == room.id)\
             .join(Course, TimetableSlot.course_id == Course.id)\
             .join(StudentGroup, TimetableSlot.group_id == StudentGroup.id)\
             .filter(TimetableSlot.room_id == room.id)\
             .group_by(Course.code, Course.name, StudentGroup.name, StudentGroup.size).all()
            
            # Calculate average capacity usage
            capacity_usages = []
            for course in courses_in_room:
                if room.capacity > 0:
                    capacity_usages.append((course.size / room.capacity) * 100)
            
            avg_capacity_usage = round(sum(capacity_usages) / len(capacity_usages), 2) if capacity_usages else 0
            
            # Utilization status
            util_status = 'underutilized'
            if utilization_percent >= 70:
                util_status = 'well_utilized'
            elif utilization_percent >= 50:
                util_status = 'moderately_utilized'
            
            report_data.append({
                'room_id': room.id,
                'room_number': room.room_number,
                'building': room.building,
                'category': room.category,
                'capacity': room.capacity,
                'slots_used': slots_used,
                'slots_available': total_possible_slots - slots_used,
                'utilization_percent': utilization_percent,
                'avg_capacity_usage': avg_capacity_usage,
                'utilization_status': util_status,
                'courses': [
                    {
                        'code': c.code,
                        'name': c.name,
                        'group': c.group_name,
                        'group_size': c.size,
                        'slot_count': c.slot_count,
                        'capacity_usage': round((c.size / room.capacity) * 100, 2) if room.capacity > 0 else 0
                    } for c in courses_in_room
                ]
            })
        
        # Calculate summary statistics
        total_rooms = len(report_data)
        avg_utilization = sum(r['utilization_percent'] for r in report_data) / total_rooms if total_rooms > 0 else 0
        well_utilized = sum(1 for r in report_data if r['utilization_status'] == 'well_utilized')
        underutilized = sum(1 for r in report_data if r['utilization_status'] == 'underutilized')
        
        return {
            'report_type': 'room_utilization',
            'generated_at': datetime.utcnow().isoformat(),
            'filters': {
                'building': building,
                'category': category
            },
            'summary': {
                'total_rooms': total_rooms,
                'average_utilization': round(avg_utilization, 2),
                'well_utilized_rooms': well_utilized,
                'moderately_utilized_rooms': total_rooms - well_utilized - underutilized,
                'underutilized_rooms': underutilized
            },
            'data': report_data
        }
    
    def generate_department_comparison_report(self) -> Dict[str, Any]:
        """
        Generate comparative report across all departments
        Shows resource distribution, timetable status, and metrics
        """
        departments = self._scoped_departments().all()
        report_data = []
        
        for dept in departments:
            # Count resources
            course_count = self.db.query(func.count(Course.id))\
                .filter(Course.department_id == dept.id).scalar() or 0
            
            lecturer_count = self.db.query(func.count(Lecturer.id))\
                .filter(Lecturer.department_id == dept.id).scalar() or 0
            
            group_count = self.db.query(func.count(StudentGroup.id))\
                .filter(StudentGroup.department_id == dept.id).scalar() or 0
            
            timetable_count = self.db.query(func.count(Timetable.id))\
                .filter(Timetable.department_id == dept.id).scalar() or 0
            
            generated_timetables = self.db.query(func.count(Timetable.id))\
                .filter(
                    Timetable.department_id == dept.id,
                    Timetable.is_generated == True
                ).scalar() or 0
            
            # Calculate total teaching hours for the department
            total_teaching_hours = self.db.query(func.sum(Course.credit_hours))\
                .join(TimetableSlot, TimetableSlot.course_id == Course.id)\
                .filter(Course.department_id == dept.id).scalar() or 0
            
            # Average hours per lecturer
            avg_hours_per_lecturer = round(total_teaching_hours / lecturer_count, 2) if lecturer_count > 0 else 0
            
            # Total students (sum of group sizes)
            total_students = self.db.query(func.sum(StudentGroup.size))\
                .filter(StudentGroup.department_id == dept.id).scalar() or 0
            
            # Student-to-lecturer ratio
            student_lecturer_ratio = round(total_students / lecturer_count, 2) if lecturer_count > 0 else 0
            
            # Get HOD
            hod = self.db.query(User).filter(
                User.department_id == dept.id,
                User.role == "HOD"
            ).first()
            
            report_data.append({
                'department_id': dept.id,
                'name': dept.name,
                'code': dept.code,
                'hod': hod.full_name if hod else None,
                'courses': course_count,
                'lecturers': lecturer_count,
                'student_groups': group_count,
                'total_students': total_students,
                'timetables': timetable_count,
                'generated_timetables': generated_timetables,
                'total_teaching_hours': total_teaching_hours,
                'avg_hours_per_lecturer': avg_hours_per_lecturer,
                'student_lecturer_ratio': student_lecturer_ratio,
                'timetable_completion': round((generated_timetables / timetable_count) * 100, 2) if timetable_count > 0 else 0
            })
        
        # Calculate university-wide statistics
        total_depts = len(report_data)
        total_courses = sum(d['courses'] for d in report_data)
        total_lecturers = sum(d['lecturers'] for d in report_data)
        total_students = sum(d['total_students'] for d in report_data)
        avg_completion = sum(d['timetable_completion'] for d in report_data) / total_depts if total_depts > 0 else 0
        
        return {
            'report_type': 'department_comparison',
            'generated_at': datetime.utcnow().isoformat(),
            'summary': {
                'total_departments': total_depts,
                'total_courses': total_courses,
                'total_lecturers': total_lecturers,
                'total_students': total_students,
                'average_timetable_completion': round(avg_completion, 2)
            },
            'data': report_data
        }
    
    def generate_timetable_summary_report(
        self,
        timetable_id: int
    ) -> Dict[str, Any]:
        """
        Generate comprehensive summary report for a specific timetable
        """
        timetable = self._scoped_timetables().filter(Timetable.id == timetable_id).first()
        
        if not timetable:
            return {'error': 'Timetable not found'}
        
        # Get all slots
        slots = self.db.query(TimetableSlot).filter(
            TimetableSlot.timetable_id == timetable_id
        ).all()
        
        # Count unique resources
        unique_courses = len(set(slot.course_id for slot in slots))
        unique_lecturers = len(set(slot.lecturer_id for slot in slots))
        unique_rooms = len(set(slot.room_id for slot in slots))
        unique_groups = len(set(slot.group_id for slot in slots))
        
        # Slots by day
        slots_by_day = {}
        for slot in slots:
            day = slot.day_of_week
            slots_by_day[day] = slots_by_day.get(day, 0) + 1
        
        # Slots by time
        slots_by_time = {}
        for slot in slots:
            time_key = f"{slot.start_time}-{slot.end_time}"
            slots_by_time[time_key] = slots_by_time.get(time_key, 0) + 1
        
        # Get department info
        dept = self.db.query(Department).filter(
            Department.id == timetable.department_id
        ).first()
        
        return {
            'report_type': 'timetable_summary',
            'generated_at': datetime.utcnow().isoformat(),
            'timetable': {
                'id': timetable.id,
                'name': timetable.name,
                'semester': timetable.semester,
                'academic_year': timetable.academic_year,
                'department': dept.name if dept else None,
                'is_generated': timetable.is_generated,
                'created_at': timetable.created_at.isoformat() if timetable.created_at else None
            },
            'statistics': {
                'total_slots': len(slots),
                'unique_courses': unique_courses,
                'unique_lecturers': unique_lecturers,
                'unique_rooms': unique_rooms,
                'unique_groups': unique_groups,
                'slots_by_day': slots_by_day,
                'slots_by_time': slots_by_time
            }
        }
    
    def generate_custom_report(
        self,
        report_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate custom report based on user configuration
        
        Config structure:
        {
            'report_name': str,
            'entities': ['courses', 'lecturers', 'rooms'],
            'filters': {
                'department_id': int,
                'date_range': {'start': str, 'end': str}
            },
            'fields': ['field1', 'field2', ...],
            'group_by': str,
            'order_by': str
        }
        """
        report_name = report_config.get('report_name', 'Custom Report')
        entities = report_config.get('entities', [])
        filters = report_config.get('filters', {})
        
        results = {}
        
        # Generate data for requested entities
        if 'courses' in entities:
            query = self.db.query(Course)
            if 'department_id' in filters:
                query = query.filter(Course.department_id == filters['department_id'])
            courses = query.all()
            results['courses'] = [
                {
                    'id': c.id,
                    'code': c.code,
                    'name': c.name,
                    'credit_hours': c.credit_hours,
                    'level': c.level,
                    'course_type': c.course_type
                } for c in courses
            ]
        
        if 'lecturers' in entities:
            query = self.db.query(Lecturer)
            if 'department_id' in filters:
                query = query.filter(Lecturer.department_id == filters['department_id'])
            lecturers = query.all()
            results['lecturers'] = [
                {
                    'id': l.id,
                    'staff_number': l.staff_number,
                    'full_name': l.full_name,
                    'email': l.email,
                    'max_hours_per_week': l.max_hours_per_week
                } for l in lecturers
            ]
        
        if 'rooms' in entities:
            query = self.db.query(Room)
            rooms = query.all()
            results['rooms'] = [
                {
                    'id': r.id,
                    'room_number': r.room_number,
                    'building': r.building,
                    'capacity': r.capacity,
                    'category': r.category
                } for r in rooms
            ]
        
        if 'student_groups' in entities:
            query = self.db.query(StudentGroup)
            if 'department_id' in filters:
                query = query.filter(StudentGroup.department_id == filters['department_id'])
            groups = query.all()
            results['student_groups'] = [
                {
                    'id': g.id,
                    'name': g.name,
                    'size': g.size,
                    'year_level': g.year_level,
                    'program': g.program
                } for g in groups
            ]
        
        return {
            'report_type': 'custom',
            'report_name': report_name,
            'generated_at': datetime.utcnow().isoformat(),
            'filters': filters,
            'data': results
        }
    
    def export_report_to_json(self, report_data: Dict[str, Any]) -> str:
        """
        Export report data to JSON string
        """
        return json.dumps(report_data, indent=2, default=str)
    
    def get_available_report_types(self) -> List[Dict[str, str]]:
        """
        Get list of available report types with descriptions
        """
        return [
            {
                'type': 'lecturer_workload',
                'name': 'Lecturer Workload Report',
                'description': 'Detailed workload analysis for lecturers including hours taught and course assignments'
            },
            {
                'type': 'room_utilization',
                'name': 'Room Utilization Report',
                'description': 'Room usage statistics showing utilization rates and capacity usage'
            },
            {
                'type': 'department_comparison',
                'name': 'Department Comparison Report',
                'description': 'Comparative analysis of resources and metrics across all departments'
            },
            {
                'type': 'timetable_summary',
                'name': 'Timetable Summary Report',
                'description': 'Comprehensive summary of a specific timetable with statistics'
            },
            {
                'type': 'custom',
                'name': 'Custom Report',
                'description': 'Build a custom report with selected entities and filters'
            }
        ]
