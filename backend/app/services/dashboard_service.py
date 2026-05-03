"""
Dashboard Service for Admin Statistics and Metrics
Provides comprehensive system-wide analytics and health monitoring
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, distinct
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from ..models import (
    User, Department, Course, Lecturer, Room, StudentGroup,
    Timetable, TimetableSlot, TimetableVersion, Notification,
    LecturerAssignment, CourseGroupLink, GroupAssignment
)


class DashboardService:
    """Service for generating admin dashboard statistics and metrics"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_overview_stats(self) -> Dict[str, Any]:
        """
        Get high-level overview statistics for the dashboard
        Returns counts of all major entities in the system
        """
        stats = {
            "total_users": self.db.query(func.count(User.id)).scalar() or 0,
            "total_departments": self.db.query(func.count(Department.id)).scalar() or 0,
            "total_courses": self.db.query(func.count(Course.id)).scalar() or 0,
            "total_lecturers": self.db.query(func.count(Lecturer.id)).scalar() or 0,
            "total_rooms": self.db.query(func.count(Room.id)).scalar() or 0,
            "total_groups": self.db.query(func.count(StudentGroup.id)).scalar() or 0,
            "total_timetables": self.db.query(func.count(Timetable.id)).scalar() or 0,
            "generated_timetables": self.db.query(func.count(Timetable.id)).filter(
                Timetable.is_generated == True
            ).scalar() or 0,
        }
        
        # Calculate additional metrics
        stats["draft_timetables"] = stats["total_timetables"] - stats["generated_timetables"]
        stats["active_users"] = self.db.query(func.count(User.id)).filter(
            User.is_active == True
        ).scalar() or 0
        
        return stats
    
    def get_user_statistics(self) -> Dict[str, Any]:
        """
        Get detailed user statistics broken down by role
        """
        # Count users by role
        role_counts = {}
        for role in ["Admin", "HOD", "Coordinator", "Lecturer"]:
            count = self.db.query(func.count(User.id)).filter(
                User.role == role,
                User.is_active == True
            ).scalar() or 0
            role_counts[role.lower()] = count
        
        # Recent user activity (users created in last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_users = self.db.query(func.count(User.id)).filter(
            User.created_at >= thirty_days_ago
        ).scalar() or 0
        
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
        total_timetables = self.db.query(func.count(Timetable.id)).scalar() or 0
        generated_count = self.db.query(func.count(Timetable.id)).filter(
            Timetable.is_generated == True
        ).scalar() or 0
        
        # Timetables by department
        dept_timetables = self.db.query(
            Department.name,
            func.count(Timetable.id).label('count')
        ).join(Timetable).group_by(Department.name).all()
        
        by_department = {dept: count for dept, count in dept_timetables}
        
        # Recent generation activity (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_generations = self.db.query(func.count(Timetable.id)).filter(
            Timetable.updated_at >= seven_days_ago,
            Timetable.is_generated == True
        ).scalar() or 0
        
        # Total slots scheduled
        total_slots = self.db.query(func.count(TimetableSlot.id)).scalar() or 0
        
        # Version statistics
        total_versions = self.db.query(func.count(TimetableVersion.id)).scalar() or 0
        
        return {
            "total_timetables": total_timetables,
            "generated_timetables": generated_count,
            "draft_timetables": total_timetables - generated_count,
            "by_department": by_department,
            "recent_generations": recent_generations,
            "total_slots": total_slots,
            "total_versions": total_versions
        }
    
    def get_resource_utilization(self) -> Dict[str, Any]:
        """
        Calculate resource utilization metrics for rooms and lecturers
        """
        # Room utilization
        total_rooms = self.db.query(func.count(Room.id)).scalar() or 0
        rooms_in_use = self.db.query(func.count(distinct(TimetableSlot.room_id))).scalar() or 0
        
        # Calculate room usage percentage by counting slots
        if total_rooms > 0:
            # Total possible slots per week: 5 days * 8 hours * total_rooms
            max_possible_slots = 5 * 8 * total_rooms
            actual_slots = self.db.query(func.count(TimetableSlot.id)).scalar() or 0
            room_utilization_percent = round((actual_slots / max_possible_slots) * 100, 2) if max_possible_slots > 0 else 0
        else:
            room_utilization_percent = 0
        
        # Lecturer utilization
        total_lecturers = self.db.query(func.count(Lecturer.id)).scalar() or 0
        lecturers_assigned = self.db.query(func.count(distinct(TimetableSlot.lecturer_id))).scalar() or 0
        
        # Average hours per lecturer
        total_hours = self.db.query(
            func.sum(Course.credit_hours)
        ).join(TimetableSlot).scalar() or 0
        
        avg_hours_per_lecturer = round(total_hours / total_lecturers, 2) if total_lecturers > 0 else 0
        
        # Room capacity utilization (group size vs room capacity)
        capacity_query = self.db.query(
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
    
    def get_department_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary statistics for each department
        """
        departments = self.db.query(Department).all()
        summary = []
        
        for dept in departments:
            # Count resources per department
            course_count = self.db.query(func.count(Course.id)).filter(
                Course.department_id == dept.id
            ).scalar() or 0
            
            lecturer_count = self.db.query(func.count(Lecturer.id)).filter(
                Lecturer.department_id == dept.id
            ).scalar() or 0
            
            group_count = self.db.query(func.count(StudentGroup.id)).filter(
                StudentGroup.department_id == dept.id
            ).scalar() or 0
            
            timetable_count = self.db.query(func.count(Timetable.id)).filter(
                Timetable.department_id == dept.id
            ).scalar() or 0
            
            # Get HOD info
            hod = self.db.query(User).filter(
                User.department_id == dept.id,
                User.role == "HOD"
            ).first()
            
            summary.append({
                "id": dept.id,
                "name": dept.name,
                "code": dept.code,
                "courses": course_count,
                "lecturers": lecturer_count,
                "groups": group_count,
                "timetables": timetable_count,
                "hod": hod.username if hod else None
            })
        
        return summary
    
    def get_recent_activity(self, limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get recent activity across the system
        """
        # Recent timetables
        recent_timetables = self.db.query(Timetable).order_by(
            Timetable.updated_at.desc()
        ).limit(limit).all()
        
        timetable_activity = []
        for tt in recent_timetables:
            timetable_activity.append({
                "id": tt.id,
                "name": tt.name,
                "department": tt.department.name if tt.department else None,
                "is_generated": tt.is_generated,
                "updated_at": tt.updated_at.isoformat() if tt.updated_at else None
            })
        
        # Recent users
        recent_users = self.db.query(User).order_by(
            User.created_at.desc()
        ).limit(limit).all()
        
        user_activity = []
        for user in recent_users:
            user_activity.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "created_at": user.created_at.isoformat() if user.created_at else None
            })
        
        # Recent notifications
        recent_notifications = self.db.query(Notification).order_by(
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
        overworked_lecturers = self.db.query(
            Lecturer.id,
            Lecturer.name,
            func.sum(Course.credit_hours).label('total_hours')
        ).join(TimetableSlot, TimetableSlot.lecturer_id == Lecturer.id)\
         .join(Course, TimetableSlot.course_id == Course.id)\
         .group_by(Lecturer.id, Lecturer.name)\
         .having(func.sum(Course.credit_hours) > 16).all()
        
        if overworked_lecturers:
            issues.append({
                "type": "lecturer_overload",
                "severity": "warning",
                "count": len(overworked_lecturers),
                "message": f"{len(overworked_lecturers)} lecturer(s) exceed 16 hours/week"
            })
        
        # Check for overcrowded rooms (group size > room capacity)
        overcrowded = self.db.query(func.count(TimetableSlot.id)).join(
            Room
        ).join(StudentGroup).filter(
            StudentGroup.size > Room.capacity
        ).scalar() or 0
        
        if overcrowded > 0:
            issues.append({
                "type": "room_overcrowding",
                "severity": "error",
                "count": overcrowded,
                "message": f"{overcrowded} slot(s) have group size exceeding room capacity"
            })
        
        # Check for rooms not in use
        total_rooms = self.db.query(func.count(Room.id)).scalar() or 0
        rooms_in_use = self.db.query(func.count(distinct(TimetableSlot.room_id))).scalar() or 0
        unused_rooms = total_rooms - rooms_in_use
        
        if unused_rooms > 0:
            warnings.append({
                "type": "unused_rooms",
                "severity": "info",
                "count": unused_rooms,
                "message": f"{unused_rooms} room(s) not assigned to any slots"
            })
        
        # Check for unassigned lecturers
        total_lecturers = self.db.query(func.count(Lecturer.id)).scalar() or 0
        assigned_lecturers = self.db.query(func.count(distinct(TimetableSlot.lecturer_id))).scalar() or 0
        unassigned_lecturers = total_lecturers - assigned_lecturers
        
        if unassigned_lecturers > 0:
            warnings.append({
                "type": "unassigned_lecturers",
                "severity": "info",
                "count": unassigned_lecturers,
                "message": f"{unassigned_lecturers} lecturer(s) not assigned to any slots"
            })
        
        # Check for draft timetables (not generated)
        draft_count = self.db.query(func.count(Timetable.id)).filter(
            Timetable.is_generated == False
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
        
        # Timetables generated this week
        timetables_this_week = self.db.query(func.count(Timetable.id)).filter(
            Timetable.updated_at >= week_start,
            Timetable.is_generated == True
        ).scalar() or 0
        
        # Users created this week
        users_this_week = self.db.query(func.count(User.id)).filter(
            User.created_at >= week_start
        ).scalar() or 0
        
        # Courses added this week
        courses_this_week = self.db.query(func.count(Course.id)).filter(
            Course.created_at >= week_start
        ).scalar() or 0
        
        # Notifications sent this week
        notifications_this_week = self.db.query(func.count(Notification.id)).filter(
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
        dept_count = self.db.query(func.count(Department.id)).scalar() or 0
        items.append({
            "key": "departments", "label": "Departments",
            "status": "done" if dept_count > 0 else "error",
            "count": dept_count,
            "hint": f"{dept_count} department(s)" if dept_count > 0 else "Add departments first",
        })

        # 2. Rooms
        room_count = self.db.query(func.count(Room.id)).scalar() or 0
        items.append({
            "key": "rooms", "label": "Rooms",
            "status": "done" if room_count > 0 else "error",
            "count": room_count,
            "hint": f"{room_count} room(s)" if room_count > 0 else "Add rooms before generating",
        })

        # 3. Lecturers (warn if any missing email)
        lec_count = self.db.query(func.count(Lecturer.id)).scalar() or 0
        no_email = self.db.query(func.count(Lecturer.id)).filter(
            (Lecturer.email == None) | (Lecturer.email == "")
        ).scalar() or 0
        lec_status = "error" if lec_count == 0 else ("warn" if no_email > 0 else "done")
        lec_hint = (
            "Upload lecturers first" if lec_count == 0
            else f"{lec_count} loaded" + (f" · {no_email} missing email" if no_email else "")
        )
        items.append({"key": "lecturers", "label": "Lecturers", "status": lec_status, "count": lec_count, "hint": lec_hint})

        # 4. Courses
        course_count = self.db.query(func.count(Course.id)).scalar() or 0
        items.append({
            "key": "courses", "label": "Courses",
            "status": "done" if course_count > 0 else "error",
            "count": course_count,
            "hint": f"{course_count} course(s)" if course_count > 0 else "Upload courses first",
        })

        # 5. Lecturer-course assignments
        assigned = self.db.query(func.count(distinct(LecturerAssignment.course_id))).scalar() or 0
        unassigned = course_count - assigned
        la_status = "done" if unassigned == 0 and course_count > 0 else ("warn" if assigned > 0 else "error")
        la_hint = (
            f"All {course_count} assigned" if unassigned == 0 and course_count > 0
            else f"{unassigned} course(s) need a lecturer"
        )
        items.append({"key": "lecturer_assignments", "label": "Lecturer Assignments", "status": la_status, "count": assigned, "hint": la_hint})

        # 6. Student groups
        group_count = self.db.query(func.count(StudentGroup.id)).filter(
            StudentGroup.parent_group_id == None
        ).scalar() or 0
        items.append({
            "key": "groups", "label": "Student Groups",
            "status": "done" if group_count > 0 else "error",
            "count": group_count,
            "hint": f"{group_count} main group(s)" if group_count > 0 else "Create student groups",
        })

        # 7. Course enrolment / delivery mapping coverage
        enrolled = self.db.query(func.count(distinct(GroupAssignment.course_id))).scalar() or 0
        delivered = self.db.query(func.count(distinct(CourseGroupLink.course_id))).scalar() or 0
        mapped = max(enrolled, delivered)
        unlinked = course_count - mapped
        ga_status = "done" if unlinked == 0 and course_count > 0 else ("warn" if mapped > 0 else "error")
        ga_hint = (
            f"All {course_count} courses have enrolment coverage" if unlinked == 0 and course_count > 0
            else f"{unlinked} course(s) still need enrolment mapping"
        )
        items.append({"key": "group_assignments", "label": "Course Enrolment", "status": ga_status, "count": mapped, "hint": ga_hint})

        # 9. Active timetable
        active_tt = self.db.query(Timetable).filter(Timetable.is_active == True).first()
        items.append({
            "key": "timetable", "label": "Active Timetable",
            "status": "done" if active_tt else "warn",
            "count": 1 if active_tt else 0,
            "hint": f"'{active_tt.name}' active" if active_tt else "Create & activate a timetable",
        })

        return items

    def get_complete_dashboard(self) -> Dict[str, Any]:
        """
        Get all dashboard data in a single call for efficiency
        """
        return {
            "overview": self.get_overview_stats(),
            "users": self.get_user_statistics(),
            "timetables": self.get_timetable_statistics(),
            "resources": self.get_resource_utilization(),
            "departments": self.get_department_summary(),
            "recent_activity": self.get_recent_activity(),
            "system_health": self.get_system_health(),
            "weekly_stats": self.get_weekly_statistics(),
            "readiness": self.get_readiness_checklist(),
            "timestamp": datetime.utcnow().isoformat()
        }
