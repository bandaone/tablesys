"""
Dashboard Service for Admin Statistics and Metrics
Provides comprehensive system-wide analytics and health monitoring
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, distinct
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from ..models import (
    User, School, Department, Course, Lecturer, Student, Room, StudentGroup,
    Timetable, TimetableSlot, TimetableVersion, Notification,
    LecturerAssignment, CourseGroupLink, GroupAssignment, UserRole, ViewerActivity
)
from ..auth import is_tenant_admin, is_school_operator


class DashboardService:
    """Service for generating admin dashboard statistics and metrics"""
    
    def __init__(self, db: Session, user: Optional[User] = None):
        self.db = db
        self.user = user

    @staticmethod
    def _user_created_at_column():
        return getattr(User, "created_at", None)

    @staticmethod
    def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.isoformat()

    @staticmethod
    def _empty_viewer_analytics() -> Dict[str, Any]:
        return {
            "summary": {
                "student_unique_viewers_7d": 0,
                "lecturer_unique_viewers_7d": 0,
                "viewer_requests_7d": 0,
                "avg_response_ms_7d": 0,
                "active_student_groups_7d": 0,
                "total_student_groups": 0,
                "inactive_student_groups_7d": 0,
                "group_coverage_percent_7d": 0,
                "estimated_student_reach_percent_7d": 0,
                "estimated_students_reached_7d": 0,
                "total_student_capacity": 0,
                "requests_per_viewer_7d": 0,
                "request_growth_percent": 0,
            },
            "daily_trend": [],
            "top_student_groups": [],
            "adoption_segments": [],
            "top_routes": [],
            "school_options": [],
            "school_summaries": [],
            "by_school": {},
        }

    def _department_query(self):
        query = self.db.query(Department)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(Department.university_id == self.user.university_id)
        if self.user and is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
            query = query.filter(Department.school_id == self.user.school_id)
        return query

    def _user_query(self):
        query = self.db.query(User)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(User.university_id == self.user.university_id)
        if self.user and is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
            query = query.filter((User.school_id == self.user.school_id) | (User.id == self.user.id))
        return query
        
    def _course_query(self):
        query = self.db.query(Course)
        if self.user and getattr(self.user, "university_id", None):
            query = query.join(Department, Course.department_id == Department.id)
            query = query.filter(Department.university_id == self.user.university_id)
            if is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
                query = query.filter(Department.school_id == self.user.school_id)
        return query
        
    def _lecturer_query(self):
        query = self.db.query(Lecturer)
        if self.user and getattr(self.user, "university_id", None):
            query = query.join(Department, Lecturer.department_id == Department.id)
            query = query.filter(Department.university_id == self.user.university_id)
            if is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
                query = query.filter(Department.school_id == self.user.school_id)
        return query
        
    def _room_query(self):
        query = self.db.query(Room)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(Room.university_id == self.user.university_id)
            if is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
                query = query.filter(Room.school_id == self.user.school_id)
        return query
        
    def _group_query(self):
        query = self.db.query(StudentGroup)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(StudentGroup.university_id == self.user.university_id)
            # Groups are scoped to department, which is scoped to school. For simplicity, join department if school is needed.
            if is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
                query = query.join(Department, StudentGroup.department_id == Department.id).filter(Department.school_id == self.user.school_id)
        return query
        
    def _timetable_query(self):
        query = self.db.query(Timetable)
        if self.user and getattr(self.user, "university_id", None):
            query = query.filter(Timetable.university_id == self.user.university_id)
            if is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
                query = query.filter(Timetable.school_id == self.user.school_id)
        return query
    
    def get_overview_stats(self) -> Dict[str, Any]:
        """
        Get high-level overview statistics for the dashboard
        Returns counts of all major entities in the system
        """
        stats = {
            "total_users": self._user_query().with_entities(func.count(User.id)).scalar() or 0,
            "total_departments": self._department_query().with_entities(func.count(Department.id)).scalar() or 0,
            "total_courses": self._course_query().with_entities(func.count(Course.id)).scalar() or 0,
            "total_lecturers": self._lecturer_query().with_entities(func.count(Lecturer.id)).scalar() or 0,
            "total_rooms": self._room_query().with_entities(func.count(Room.id)).scalar() or 0,
            "total_groups": self._group_query().with_entities(func.count(StudentGroup.id)).scalar() or 0,
            "total_timetables": self._timetable_query().with_entities(func.count(Timetable.id)).scalar() or 0,
            "generated_timetables": self._timetable_query().with_entities(func.count(Timetable.id)).filter(
                Timetable.generation_metadata != None
            ).scalar() or 0,
        }
        
        # Calculate additional metrics
        stats["draft_timetables"] = stats["total_timetables"] - stats["generated_timetables"]
        stats["active_users"] = self._user_query().with_entities(func.count(User.id)).filter(
            User.is_active == True
        ).scalar() or 0

        # Viewer-based active counts (logged in last 30 days)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        uni_id = getattr(self.user, "university_id", None) if self.user else None

        lecturer_q = self.db.query(func.count(Lecturer.id)).join(
            Department, Lecturer.department_id == Department.id
        ).filter(Lecturer.last_login_at >= thirty_days_ago)
        if uni_id:
            lecturer_q = lecturer_q.filter(Department.university_id == uni_id)
        stats["active_lecturers_30d"] = lecturer_q.scalar() or 0

        student_q = self.db.query(func.count(Student.id)).filter(
            Student.last_login_at >= thirty_days_ago
        )
        if uni_id:
            dept_ids_sub = self.db.query(Department.id).filter(
                Department.university_id == uni_id
            ).subquery()
            student_q = student_q.filter(Student.department_id.in_(dept_ids_sub))
        stats["active_students_30d"] = student_q.scalar() or 0

        # Total portal viewer counts (all time)
        total_lecturer_q = self._lecturer_query().with_entities(func.count(Lecturer.id))
        stats["total_lecturers"] = total_lecturer_q.scalar() or 0

        total_student_q = self.db.query(func.count(Student.id))
        if uni_id:
            dept_ids_sub2 = self.db.query(Department.id).filter(
                Department.university_id == uni_id
            ).subquery()
            total_student_q = total_student_q.filter(Student.department_id.in_(dept_ids_sub2))
        stats["total_students"] = total_student_q.scalar() or 0

        return stats
    
    def get_user_statistics(self) -> Dict[str, Any]:
        """
        Get detailed user statistics broken down by role
        """
        # Count users by role
        role_counts = {}
        role_map = {
            "tenant_admin": UserRole.TENANT_ADMIN,
            "school_coordinator": UserRole.SCHOOL_COORDINATOR,
            "coordinator": UserRole.COORDINATOR,
            "hod": UserRole.HOD,
            "lecturer": UserRole.LECTURER,
        }
        for key, role in role_map.items():
            count = self._user_query().with_entities(func.count(User.id)).filter(
                User.role == role,
                User.is_active == True
            ).scalar() or 0
            role_counts[key] = count
        
        recent_users = 0
        user_created_at = self._user_created_at_column()
        if user_created_at is not None:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_users = self._user_query().filter(
                user_created_at >= thirty_days_ago
            ).count()
        
        return {
            "by_role": role_counts,
            "recent_signups": recent_users,
            "total_active": sum(role_counts.values())
        }
    
    def get_timetable_statistics(self) -> Dict[str, Any]:
        """
        Get detailed timetable statistics and generation metrics
        """
        # Basic timetable counts
        total_timetables = self._timetable_query().with_entities(func.count(Timetable.id)).scalar() or 0
        generated_count = self._timetable_query().with_entities(func.count(Timetable.id)).filter(
            Timetable.generation_metadata != None
        ).scalar() or 0
        
        # Timetables by school (since Timetable doesn't have department_id)
        by_school: Dict[str, int] = {}
        try:
            school_rows = self.db.query(School.name, School.id).filter(
                School.university_id == self.user.university_id
            ).all()
            for school_name, school_id in school_rows:
                count = self._timetable_query().with_entities(func.count(Timetable.id)).filter(
                    Timetable.school_id == school_id
                ).scalar() or 0
                by_school[school_name] = count
        except Exception:
            by_school = {}
        
        # Total slots scheduled
        total_slots = self.db.query(func.count(TimetableSlot.id)).join(
            Timetable, TimetableSlot.timetable_id == Timetable.id
        ).filter(Timetable.id.in_(self._timetable_query().with_entities(Timetable.id))).scalar() or 0
        
        # Version statistics
        total_versions = self.db.query(func.count(TimetableVersion.id)).join(
            Timetable, TimetableVersion.timetable_id == Timetable.id
        ).filter(Timetable.university_id == self.user.university_id).scalar() or 0
        
        return {
            "total_timetables": total_timetables,
            "generated_timetables": generated_count,
            "draft_timetables": total_timetables - generated_count,
            "by_school": by_school,
            "recent_generations": generated_count,
            "total_slots": total_slots,
            "total_versions": total_versions
        }
    
    def get_resource_utilization(self) -> Dict[str, Any]:
        """
        Calculate resource utilization metrics for rooms and lecturers
        """
        # Room utilization
        total_rooms = self._room_query().with_entities(func.count(Room.id)).scalar() or 0
        rooms_in_use = self.db.query(func.count(distinct(TimetableSlot.room_id))).join(
            Timetable, TimetableSlot.timetable_id == Timetable.id
        ).filter(Timetable.id.in_(self._timetable_query().with_entities(Timetable.id))).scalar() or 0
        
        # Calculate room usage percentage by counting slots
        if total_rooms > 0:
            max_possible_slots = 5 * 8 * total_rooms
            actual_slots = self.db.query(func.count(TimetableSlot.id)).join(
                Timetable, TimetableSlot.timetable_id == Timetable.id
            ).filter(Timetable.id.in_(self._timetable_query().with_entities(Timetable.id))).scalar() or 0
            room_utilization_percent = round((actual_slots / max_possible_slots) * 100, 2) if max_possible_slots > 0 else 0
        else:
            room_utilization_percent = 0
        
        # Lecturer utilization
        total_lecturers = self._lecturer_query().with_entities(func.count(Lecturer.id)).scalar() or 0
        lecturers_assigned = self.db.query(func.count(distinct(TimetableSlot.lecturer_id))).join(
            Timetable, TimetableSlot.timetable_id == Timetable.id
        ).filter(Timetable.id.in_(self._timetable_query().with_entities(Timetable.id))).scalar() or 0
        
        # Average hours per lecturer
        total_hours = self._course_query().join(TimetableSlot, TimetableSlot.course_id == Course.id).with_entities(func.sum(Course.lecture_hours)).scalar() or 0
        
        avg_hours_per_lecturer = round(total_hours / total_lecturers, 2) if total_lecturers > 0 else 0
        
        # Room capacity utilization (group size vs room capacity)
        capacity_query = self._room_query().with_entities(
            func.avg(
                case(
                    (Room.capacity > 0, (StudentGroup.size * 100.0) / Room.capacity),
                    else_=0
                )
            )
        ).join(TimetableSlot, TimetableSlot.room_id == Room.id)\
         .join(StudentGroup, TimetableSlot.group_id == StudentGroup.id).scalar()
        
        avg_capacity_usage = round(capacity_query or 0, 2)
        
        return {
            "rooms": {
                "total": total_rooms,
                "in_use": rooms_in_use,
                "utilization_percent": room_utilization_percent,
                "avg_capacity_usage": avg_capacity_usage
            },
            "lecturers": {
                "total": total_lecturers,
                "assigned": lecturers_assigned,
                "unassigned": total_lecturers - lecturers_assigned,
                "avg_hours": avg_hours_per_lecturer
            }
        }
    
    def get_school_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary statistics for each school
        """
        school_query = self.db.query(School)
        if self.user and getattr(self.user, "university_id", None):
            school_query = school_query.filter(School.university_id == self.user.university_id)
        if self.user and is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
            school_query = school_query.filter(School.id == self.user.school_id)

        schools = school_query.all()
        summary = []
        
        for school in schools:
            dept_ids = [
                department_id
                for (department_id,) in self._department_query()
                .with_entities(Department.id)
                .filter(Department.school_id == school.id)
                .all()
            ]
            
            # Count resources across these departments
            course_count = self._course_query().with_entities(func.count(Course.id)).filter(
                Course.department_id.in_(dept_ids) if dept_ids else False
            ).scalar() or 0
            
            lecturer_count = self._lecturer_query().with_entities(func.count(Lecturer.id)).filter(
                Lecturer.department_id.in_(dept_ids) if dept_ids else False
            ).scalar() or 0
            
            group_count = self._group_query().with_entities(func.count(StudentGroup.id)).filter(
                StudentGroup.department_id.in_(dept_ids) if dept_ids else False
            ).scalar() or 0
            
            timetable_count = self._timetable_query().with_entities(func.count(Timetable.id)).filter(
                Timetable.school_id == school.id
            ).scalar() or 0
            
            # Get School Coordinator info
            coordinator = self._user_query().filter(
                User.school_id == school.id,
                User.role == UserRole.SCHOOL_COORDINATOR
            ).first()
            
            summary.append({
                "id": school.id,
                "name": school.name,
                "code": school.code,
                "departments_count": len(dept_ids),
                "courses": course_count,
                "lecturers": lecturer_count,
                "groups": group_count,
                "timetables": timetable_count,
                "coordinator": coordinator.username if coordinator else None
            })
        
        return summary
    
    def get_recent_activity(self, limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get recent activity across the system
        """
        # Recent timetables
        recent_timetables = self._timetable_query().order_by(
            Timetable.id.desc()
        ).limit(limit).all()
        
        timetable_activity = []
        for tt in recent_timetables:
            # Get latest version for updated_at date
            latest_version = self.db.query(TimetableVersion).filter(TimetableVersion.timetable_id == tt.id).order_by(TimetableVersion.id.desc()).first()
            school_name = tt.school.name if tt.school else "General"
            
            # Fallback for N/A: If no versions exist yet, use the current time (since it's recent anyway) or an empty string, but a real ISO timestamp is best for the UI formatter.
            updated_time = latest_version.created_at.isoformat() if latest_version and latest_version.created_at else datetime.utcnow().isoformat()
            
            timetable_activity.append({
                "id": tt.id,
                "name": tt.name,
                "department": school_name,
                "is_generated": tt.generation_metadata is not None,
                "updated_at": updated_time
            })
        
        # Recent users
        user_created_at = self._user_created_at_column()
        recent_user_query = self._user_query()
        if user_created_at is not None:
            recent_user_query = recent_user_query.order_by(user_created_at.desc())
        else:
            recent_user_query = recent_user_query.order_by(User.id.desc())
        recent_users = recent_user_query.limit(limit).all()
        
        user_activity = []
        for user in recent_users:
            user_activity.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "created_at": self._serialize_datetime(getattr(user, "created_at", None))
            })
        
        # Recent notifications
        recent_notifications = self.db.query(Notification).join(User, Notification.user_id == User.id).filter(User.university_id == self.user.university_id if getattr(self.user, 'university_id', None) else True).order_by(
            Notification.created_at.desc()
        ).limit(limit).all()
        
        notification_activity = []
        for notif in recent_notifications:
            notification_activity.append({
                "id": notif.id,
                "title": notif.title,
                "type": notif.type,
                "user_id": notif.user_id,
                "created_at": notif.created_at.isoformat()
            })
        
        return {
            "timetables": timetable_activity,
            "users": user_activity,
            "notifications": notification_activity
        }
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Calculate system health metrics and identify potential issues
        """
        issues = []
        warnings = []
        
        # Check for overutilized lecturers (>16 hours/week)
        try:
            overworked_lecturers = self._lecturer_query().with_entities(
                Lecturer.id, Lecturer.full_name, func.sum(Course.lecture_hours).label('total_hours')
            ).join(TimetableSlot, TimetableSlot.lecturer_id == Lecturer.id)\
             .join(Course, TimetableSlot.course_id == Course.id)\
             .group_by(Lecturer.id, Lecturer.full_name)\
             .having(func.sum(Course.lecture_hours) > 16).all()
        except Exception:
            overworked_lecturers = []
        
        if overworked_lecturers:
            issues.append({
                "type": "lecturer_overload",
                "severity": "warning",
                "count": len(overworked_lecturers),
                "message": f"{len(overworked_lecturers)} lecturer(s) exceed 16 hours/week"
            })
        
        # Check for overcrowded rooms (group size > room capacity)
        try:
            overcrowded = self.db.query(func.count(TimetableSlot.id)).join(
                Timetable, TimetableSlot.timetable_id == Timetable.id
            ).join(
                Room, TimetableSlot.room_id == Room.id
            ).join(
                StudentGroup, TimetableSlot.group_id == StudentGroup.id
            ).filter(
                Timetable.id.in_(self._timetable_query().with_entities(Timetable.id)),
                StudentGroup.size > Room.capacity
            ).scalar() or 0
        except Exception:
            overcrowded = 0
        
        if overcrowded > 0:
            issues.append({
                "type": "room_overcrowding",
                "severity": "error",
                "count": overcrowded,
                "message": f"{overcrowded} slot(s) have group size exceeding room capacity"
            })
        
        # Check for rooms not in use
        total_rooms = self._room_query().with_entities(func.count(Room.id)).scalar() or 0
        rooms_in_use = self.db.query(func.count(distinct(TimetableSlot.room_id))).join(
            Timetable, TimetableSlot.timetable_id == Timetable.id
        ).filter(Timetable.id.in_(self._timetable_query().with_entities(Timetable.id))).scalar() or 0
        unused_rooms = total_rooms - rooms_in_use
        
        if unused_rooms > 0:
            warnings.append({
                "type": "unused_rooms",
                "severity": "info",
                "count": unused_rooms,
                "message": f"{unused_rooms} room(s) not assigned to any slots"
            })
        
        # Check for unassigned lecturers
        total_lecturers = self._lecturer_query().with_entities(func.count(Lecturer.id)).scalar() or 0
        assigned_lecturers = self.db.query(func.count(distinct(TimetableSlot.lecturer_id))).join(
            Timetable, TimetableSlot.timetable_id == Timetable.id
        ).filter(Timetable.id.in_(self._timetable_query().with_entities(Timetable.id))).scalar() or 0
        unassigned_lecturers = total_lecturers - assigned_lecturers
        
        if unassigned_lecturers > 0:
            warnings.append({
                "type": "unassigned_lecturers",
                "severity": "info",
                "count": unassigned_lecturers,
                "message": f"{unassigned_lecturers} lecturer(s) not assigned to any slots"
            })
        
        # Check for draft timetables (not generated)
        draft_count = self._timetable_query().with_entities(func.count(Timetable.id)).filter(
            Timetable.generation_metadata == None
        ).scalar() or 0
        
        if draft_count > 0:
            warnings.append({
                "type": "draft_timetables",
                "severity": "info",
                "count": draft_count,
                "message": f"{draft_count} timetable(s) in draft status"
            })
        
        # Overall health score (0-100)
        total_issues = len(issues)
        total_warnings = len(warnings)
        health_score = max(0, 100 - (total_issues * 20) - (total_warnings * 5))
        
        return {
            "health_score": health_score,
            "status": "healthy" if health_score >= 80 else "warning" if health_score >= 60 else "critical",
            "issues": issues,
            "warnings": warnings,
            "total_issues": total_issues,
            "total_warnings": total_warnings
        }
    
    def get_weekly_statistics(self) -> Dict[str, Any]:
        """
        Get statistics for the current week
        """
        week_start = datetime.utcnow() - timedelta(days=7)
        
        # Timetables generated (no updated_at on Timetable — return total generated)
        timetables_this_week = self._timetable_query().with_entities(func.count(Timetable.id)).filter(
            Timetable.generation_metadata != None
        ).scalar() or 0
        
        users_this_week = 0
        user_created_at = self._user_created_at_column()
        if user_created_at is not None:
            users_this_week = self._user_query().with_entities(func.count(User.id)).filter(
                user_created_at >= week_start
            ).scalar() or 0
        
        # Courses added this week (no created_at on Course — return total)
        courses_this_week = self._course_query().with_entities(func.count(Course.id)).scalar() or 0
        
        # Notifications sent this week
        notifications_this_week = self.db.query(func.count(Notification.id)).join(
            User, Notification.user_id == User.id
        ).filter(
            User.university_id == self.user.university_id if getattr(self.user, 'university_id', None) else True,
            Notification.created_at >= week_start
        ).scalar() or 0
        
        return {
            "timetables_generated": timetables_this_week,
            "users_created": users_this_week,
            "courses_added": courses_this_week,
            "notifications_sent": notifications_this_week,
            "period_start": week_start.isoformat(),
            "period_end": datetime.utcnow().isoformat()
        }
    
    def get_readiness_checklist(self) -> list:
        """
        Return a compact checklist of generation-readiness items.
        Each item: { key, label, status ('done'|'warn'|'error'), count, hint }
        """
        items = []

        # 1. Departments
        dept_count = self._department_query().with_entities(func.count(Department.id)).scalar() or 0
        items.append({
            "key": "departments", "label": "Departments",
            "status": "done" if dept_count > 0 else "error",
            "count": dept_count,
            "hint": f"{dept_count} department(s)" if dept_count > 0 else "Add departments first",
        })

        # 2. Rooms
        room_count = self._room_query().with_entities(func.count(Room.id)).scalar() or 0
        items.append({
            "key": "rooms", "label": "Rooms",
            "status": "done" if room_count > 0 else "error",
            "count": room_count,
            "hint": f"{room_count} room(s)" if room_count > 0 else "Add rooms before generating",
        })

        # 3. Lecturers (warn if any missing email)
        lec_count = self._lecturer_query().with_entities(func.count(Lecturer.id)).scalar() or 0
        no_email = self._lecturer_query().with_entities(func.count(Lecturer.id)).filter(
            (Lecturer.email == None) | (Lecturer.email == "")
        ).scalar() or 0
        lec_status = "error" if lec_count == 0 else ("warn" if no_email > 0 else "done")
        lec_hint = (
            "Upload lecturers first" if lec_count == 0
            else f"{lec_count} loaded" + (f" · {no_email} missing email" if no_email else "")
        )
        items.append({"key": "lecturers", "label": "Lecturers", "status": lec_status, "count": lec_count, "hint": lec_hint})

        # 4. Courses
        course_count = self._course_query().with_entities(func.count(Course.id)).scalar() or 0
        items.append({
            "key": "courses", "label": "Courses",
            "status": "done" if course_count > 0 else "error",
            "count": course_count,
            "hint": f"{course_count} course(s)" if course_count > 0 else "Upload courses first",
        })

        # 5. Lecturer-course assignments
        assigned = self._course_query().join(LecturerAssignment).with_entities(func.count(distinct(LecturerAssignment.course_id))).scalar() or 0
        unassigned = course_count - assigned
        la_status = "done" if unassigned == 0 and course_count > 0 else ("warn" if assigned > 0 else "error")
        la_hint = (
            f"All {course_count} assigned" if unassigned == 0 and course_count > 0
            else f"{unassigned} course(s) need a lecturer"
        )
        items.append({"key": "lecturer_assignments", "label": "Lecturer Assignments", "status": la_status, "count": assigned, "hint": la_hint})

        # 6. Student groups
        group_count = self._group_query().with_entities(func.count(StudentGroup.id)).filter(
            StudentGroup.parent_group_id == None
        ).scalar() or 0
        items.append({
            "key": "groups", "label": "Student Groups",
            "status": "done" if group_count > 0 else "error",
            "count": group_count,
            "hint": f"{group_count} main group(s)" if group_count > 0 else "Create student groups",
        })

        # 7. Course enrolment / delivery mapping coverage
        enrolled = self._course_query().join(GroupAssignment).with_entities(func.count(distinct(GroupAssignment.course_id))).scalar() or 0
        delivered = self._course_query().join(CourseGroupLink).with_entities(func.count(distinct(CourseGroupLink.course_id))).scalar() or 0
        mapped = max(enrolled, delivered)
        unlinked = course_count - mapped
        ga_status = "done" if unlinked == 0 and course_count > 0 else ("warn" if mapped > 0 else "error")
        ga_hint = (
            f"All {course_count} courses have enrolment coverage" if unlinked == 0 and course_count > 0
            else f"{unlinked} course(s) still need enrolment mapping"
        )
        items.append({"key": "group_assignments", "label": "Course Enrolment", "status": ga_status, "count": mapped, "hint": ga_hint})

        # 9. Active timetable
        active_tt = self._timetable_query().filter(Timetable.is_active == True).first()
        items.append({
            "key": "timetable", "label": "Active Timetable",
            "status": "done" if active_tt else "warn",
            "count": 1 if active_tt else 0,
            "hint": f"'{active_tt.name}' active" if active_tt else "Create & activate a timetable",
        })

        return items

    def get_viewer_analytics(self) -> Dict[str, Any]:
        if not self.user or not getattr(self.user, "university_id", None):
            return self._empty_viewer_analytics()

        tenant_id = self.user.university_id

        def _normalize_timestamp(value: Optional[datetime]) -> Optional[datetime]:
            if value is None:
                return None
            if value.tzinfo is not None:
                return value.astimezone(timezone.utc).replace(tzinfo=None)
            return value

        def _serialize_scope(
            scope_rows_7d: List[ViewerActivity],
            previous_rows_7d: List[ViewerActivity],
            scope_groups: List[Any],
        ) -> Dict[str, Any]:
            student_rows_7d = [row for row in scope_rows_7d if row.audience == "student_public"]
            lecturer_rows_7d = [row for row in scope_rows_7d if row.audience == "lecturer_portal"]

            student_unique_viewers_7d = len({row.viewer_id for row in student_rows_7d if row.viewer_id})
            lecturer_unique_viewers_7d = len(
                {
                    row.lecturer_id if row.lecturer_id is not None else row.viewer_id
                    for row in lecturer_rows_7d
                    if row.lecturer_id is not None or row.viewer_id
                }
            )
            viewer_requests_7d = len(scope_rows_7d)
            avg_response_ms_7d = round(
                sum(max(int(row.response_time_ms or 0), 0) for row in scope_rows_7d) / max(len(scope_rows_7d), 1),
                2,
            ) if scope_rows_7d else 0

            scope_group_ids = {group.id for group in scope_groups}
            parent_ids = {group.parent_group_id for group in scope_groups if group.parent_group_id}
            leaf_groups = [group for group in scope_groups if group.id not in parent_ids]
            leaf_group_ids = {group.id for group in leaf_groups}

            active_leaf_group_ids_7d = sorted(
                {row.group_id for row in student_rows_7d if row.group_id is not None and row.group_id in leaf_group_ids}
            )
            total_leaf_groups = len(leaf_groups)
            covered_leaf_groups = len(active_leaf_group_ids_7d)
            group_coverage_percent_7d = round(
                (covered_leaf_groups / total_leaf_groups) * 100,
                2,
            ) if total_leaf_groups else 0
            inactive_student_groups_7d = max(total_leaf_groups - covered_leaf_groups, 0)

            active_leaf_groups = [group for group in leaf_groups if group.id in active_leaf_group_ids_7d]
            total_student_capacity = sum(group.size or 0 for group in leaf_groups)
            estimated_students_reached_7d = sum(
                min(
                    len(
                        {
                            row.viewer_id
                            for row in student_rows_7d
                            if row.group_id == group.id and row.viewer_id
                        }
                    ),
                    group.size or 0,
                )
                for group in active_leaf_groups
            )
            estimated_student_reach_percent_7d = round(
                (estimated_students_reached_7d / total_student_capacity) * 100,
                2,
            ) if total_student_capacity else 0

            current_request_count = len(scope_rows_7d)
            previous_request_count = len(previous_rows_7d)
            if previous_request_count == 0:
                request_growth_percent = 100.0 if current_request_count > 0 else 0.0
            else:
                request_growth_percent = round(
                    ((current_request_count - previous_request_count) / previous_request_count) * 100,
                    2,
                )

            requests_per_viewer_7d = round(
                viewer_requests_7d / max(student_unique_viewers_7d + lecturer_unique_viewers_7d, 1),
                2,
            ) if viewer_requests_7d else 0

            now_local = datetime.utcnow()
            daily_trend_map: Dict[str, Dict[str, Any]] = {}
            for offset in range(6, -1, -1):
                day = (now_local - timedelta(days=offset)).date().isoformat()
                daily_trend_map[day] = {
                    "date": day,
                    "requests": 0,
                    "student_unique_viewers": set(),
                    "lecturer_unique_viewers": set(),
                }

            for row in scope_rows_7d:
                occurred_at = _normalize_timestamp(row.occurred_at)
                if occurred_at is None:
                    continue
                bucket = daily_trend_map.get(occurred_at.date().isoformat())
                if not bucket:
                    continue
                bucket["requests"] += 1
                if row.audience == "student_public" and row.viewer_id:
                    bucket["student_unique_viewers"].add(row.viewer_id)
                if row.audience == "lecturer_portal":
                    bucket["lecturer_unique_viewers"].add(
                        row.lecturer_id if row.lecturer_id is not None else row.viewer_id
                    )

            daily_trend = [
                {
                    "date": day,
                    "requests": payload["requests"],
                    "student_unique_viewers": len(payload["student_unique_viewers"]),
                    "lecturer_unique_viewers": len(payload["lecturer_unique_viewers"]),
                }
                for day, payload in daily_trend_map.items()
            ]

            group_lookup = {group.id: group for group in scope_groups}
            group_totals: Dict[int, Dict[str, Any]] = {}
            for row in student_rows_7d:
                if row.group_id is None or row.group_id not in scope_group_ids:
                    continue
                bucket = group_totals.setdefault(
                    row.group_id,
                    {"requests": 0, "viewers": set()},
                )
                bucket["requests"] += 1
                if row.viewer_id:
                    bucket["viewers"].add(row.viewer_id)

            top_student_groups = [
                {
                    "group_id": group_id,
                    "group_name": group_lookup[group_id].name if group_id in group_lookup else f"Group {group_id}",
                    "size": group_lookup[group_id].size if group_id in group_lookup else None,
                    "requests": payload["requests"],
                    "unique_viewers": len(payload["viewers"]),
                    "adoption_percent": round(
                        (len(payload["viewers"]) / max(group_lookup[group_id].size or 0, 1)) * 100,
                        2,
                    ) if group_id in group_lookup and group_lookup[group_id].size else 0,
                }
                for group_id, payload in sorted(
                    group_totals.items(),
                    key=lambda item: (-item[1]["requests"], -len(item[1]["viewers"])),
                )[:5]
            ]

            adoption_segments = []
            for group in sorted(active_leaf_groups, key=lambda item: item.name.lower())[:8]:
                viewer_count = len(
                    {
                        row.viewer_id
                        for row in student_rows_7d
                        if row.group_id == group.id and row.viewer_id
                    }
                )
                adoption_segments.append({
                    "group_id": group.id,
                    "group_name": group.name,
                    "size": group.size or 0,
                    "unique_viewers": viewer_count,
                    "adoption_percent": round((viewer_count / max(group.size or 0, 1)) * 100, 2) if group.size else 0,
                    "status": "active",
                })

            if len(adoption_segments) < 8:
                inactive_candidates = [group for group in leaf_groups if group.id not in active_leaf_group_ids_7d]
                for group in sorted(inactive_candidates, key=lambda item: (-(item.size or 0), item.name.lower()))[: 8 - len(adoption_segments)]:
                    adoption_segments.append({
                        "group_id": group.id,
                        "group_name": group.name,
                        "size": group.size or 0,
                        "unique_viewers": 0,
                        "adoption_percent": 0,
                        "status": "inactive",
                    })

            route_totals: Dict[str, int] = {}
            for row in scope_rows_7d:
                route_totals[row.route_key] = route_totals.get(row.route_key, 0) + 1
            top_routes = [
                {"route": route, "requests": requests}
                for route, requests in sorted(route_totals.items(), key=lambda item: (-item[1], item[0]))[:5]
            ]

            return {
                "summary": {
                    "student_unique_viewers_7d": student_unique_viewers_7d,
                    "lecturer_unique_viewers_7d": lecturer_unique_viewers_7d,
                    "viewer_requests_7d": viewer_requests_7d,
                    "avg_response_ms_7d": avg_response_ms_7d,
                    "active_student_groups_7d": covered_leaf_groups,
                    "total_student_groups": total_leaf_groups,
                    "inactive_student_groups_7d": inactive_student_groups_7d,
                    "group_coverage_percent_7d": group_coverage_percent_7d,
                    "estimated_student_reach_percent_7d": estimated_student_reach_percent_7d,
                    "estimated_students_reached_7d": estimated_students_reached_7d,
                    "total_student_capacity": total_student_capacity,
                    "requests_per_viewer_7d": requests_per_viewer_7d,
                    "request_growth_percent": request_growth_percent,
                },
                "daily_trend": daily_trend,
                "top_student_groups": top_student_groups,
                "adoption_segments": adoption_segments,
                "top_routes": top_routes,
            }

        now = datetime.utcnow()
        start_30d = now - timedelta(days=30)
        start_14d = now - timedelta(days=14)
        start_7d = now - timedelta(days=7)

        try:
            rows = (
                self.db.query(ViewerActivity)
                .filter(ViewerActivity.tenant_id == tenant_id)
                .filter(ViewerActivity.occurred_at >= start_30d)
                .all()
            )
        except Exception:
            self.db.rollback()
            return self._empty_viewer_analytics()

        rows_14d = [row for row in rows if _normalize_timestamp(row.occurred_at) and _normalize_timestamp(row.occurred_at) >= start_14d]
        rows_7d = [row for row in rows if _normalize_timestamp(row.occurred_at) and _normalize_timestamp(row.occurred_at) >= start_7d]
        prev_7d = [
            row for row in rows_14d
            if _normalize_timestamp(row.occurred_at) and start_14d <= _normalize_timestamp(row.occurred_at) < start_7d
        ]
        school_query = self.db.query(School.id, School.name, School.code).filter(School.university_id == tenant_id)
        if self.user and is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
            school_query = school_query.filter(School.id == self.user.school_id)
        school_rows = school_query.order_by(School.name.asc()).all()

        group_scope_query = (
            self.db.query(
                StudentGroup.id,
                StudentGroup.name,
                StudentGroup.size,
                StudentGroup.parent_group_id,
                Department.school_id.label("school_id"),
                School.name.label("school_name"),
            )
            .join(Department, StudentGroup.department_id == Department.id)
            .outerjoin(School, Department.school_id == School.id)
            .filter(StudentGroup.university_id == tenant_id)
        )
        if self.user and is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
            group_scope_query = group_scope_query.filter(Department.school_id == self.user.school_id)
        tenant_groups = group_scope_query.all()

        lecturer_scope_query = (
            self.db.query(
                Lecturer.id,
                Department.school_id.label("school_id"),
            )
            .join(Department, Lecturer.department_id == Department.id)
            .filter(Department.university_id == tenant_id)
        )
        if self.user and is_school_operator(self.user) and getattr(self.user, "school_id", None) is not None and not is_tenant_admin(self.user):
            lecturer_scope_query = lecturer_scope_query.filter(Department.school_id == self.user.school_id)
        lecturer_rows = lecturer_scope_query.all()
        lecturer_school_map = {row.id: row.school_id for row in lecturer_rows}
        group_school_map = {group.id: group.school_id for group in tenant_groups}

        def _row_school_id(row: ViewerActivity) -> Optional[int]:
            if row.group_id is not None:
                return group_school_map.get(row.group_id)
            if row.lecturer_id is not None:
                return lecturer_school_map.get(row.lecturer_id)
            return None

        aggregate = _serialize_scope(rows_7d, prev_7d, tenant_groups)

        by_school: Dict[str, Dict[str, Any]] = {}
        school_summaries: List[Dict[str, Any]] = []
        for school_id, school_name, school_code in school_rows:
            school_groups = [group for group in tenant_groups if group.school_id == school_id]
            school_rows_7d = [row for row in rows_7d if _row_school_id(row) == school_id]
            school_prev_7d = [row for row in prev_7d if _row_school_id(row) == school_id]
            school_payload = _serialize_scope(school_rows_7d, school_prev_7d, school_groups)
            by_school[str(school_id)] = school_payload
            school_summaries.append({
                "school_id": school_id,
                "school_name": school_name,
                "school_code": school_code,
                "viewer_requests_7d": school_payload["summary"]["viewer_requests_7d"],
                "active_student_groups_7d": school_payload["summary"]["active_student_groups_7d"],
                "total_student_groups": school_payload["summary"]["total_student_groups"],
                "estimated_students_reached_7d": school_payload["summary"]["estimated_students_reached_7d"],
                "group_coverage_percent_7d": school_payload["summary"]["group_coverage_percent_7d"],
            })

        return {
            **aggregate,
            "school_options": [
                {"id": school_id, "name": school_name, "code": school_code}
                for school_id, school_name, school_code in school_rows
            ],
            "school_summaries": school_summaries,
            "by_school": by_school,
        }

    def get_complete_dashboard(self) -> Dict[str, Any]:
        """
        Get all dashboard data in a single call for efficiency
        """
        return {
            "overview": self.get_overview_stats(),
            "users": self.get_user_statistics(),
            "timetables": self.get_timetable_statistics(),
            "resources": self.get_resource_utilization(),
            "schools": self.get_school_summary(),
            "recent_activity": self.get_recent_activity(),
            "system_health": self.get_system_health(),
            "weekly_stats": self.get_weekly_statistics(),
            "viewer_analytics": self.get_viewer_analytics(),
            "readiness": self.get_readiness_checklist(),
            "timestamp": datetime.utcnow().isoformat()
        }
