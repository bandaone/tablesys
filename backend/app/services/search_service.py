"""
Search Service

Provides global search functionality across courses, lecturers, rooms, and groups.
Supports fuzzy matching and advanced filtering.
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Dict, Any, Optional
from ..models import Course, Lecturer, Room, StudentGroup, Department, User
from ..utils.sanitization import sanitize_input


class SearchService:
    """Service for searching across entities — all queries are scoped to a university."""

    def __init__(self, db: Session, university_id: Optional[int] = None):
        self.db = db
        self.university_id = university_id

    def global_search(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Search across multiple entity types.
        
        Args:
            query: Search query string
            entity_types: List of entity types to search (courses, lecturers, rooms, groups)
            limit: Maximum results per entity type
            
        Returns:
            Dict with results categorized by entity type
        """
        safe_query = sanitize_input(query, max_length=100)
        if not safe_query or len(safe_query.strip()) < 2:
            return {
                "courses": [],
                "lecturers": [],
                "rooms": [],
                "groups": [],
                "total": 0
            }
        
        search_term = f"%{safe_query.lower()}%"
        results = {
            "courses": [],
            "lecturers": [],
            "rooms": [],
            "groups": [],
            "total": 0
        }
        
        # If no entity types specified, search all
        if not entity_types:
            entity_types = ["courses", "lecturers", "rooms", "groups"]
        
        # Search courses
        if "courses" in entity_types:
            course_q = self.db.query(Course).join(Department, Course.department_id == Department.id)
            if self.university_id:
                course_q = course_q.filter(Department.university_id == self.university_id)
            courses = course_q.filter(
                or_(
                    Course.code.ilike(search_term),
                    Course.name.ilike(search_term)
                )
            ).limit(limit).all()
            
            results["courses"] = [
                {
                    "id": c.id,
                    "code": c.code,
                    "name": c.name,
                    "level": c.level,
                    "credits": c.credits,
                    "course_type": getattr(c.course_type, "value", str(c.course_type)) if c.course_type else None,
                }
                for c in courses
            ]
            results["total"] += len(courses)
        
        # Search lecturers
        if "lecturers" in entity_types:
            lec_q = self.db.query(Lecturer).join(Department, Lecturer.department_id == Department.id)
            if self.university_id:
                lec_q = lec_q.filter(Department.university_id == self.university_id)
            lecturers = lec_q.filter(
                or_(
                    Lecturer.staff_number.ilike(search_term),
                    Lecturer.full_name.ilike(search_term),
                    Lecturer.email.ilike(search_term)
                )
            ).limit(limit).all()
            
            results["lecturers"] = [
                {
                    "id": l.id,
                    "staff_number": l.staff_number,
                    "full_name": l.full_name,
                    # email intentionally omitted from global search results
                    "department_id": l.department_id,
                    "max_hours_per_week": l.max_hours_per_week
                }
                for l in lecturers
            ]
            results["total"] += len(lecturers)
        
        # Search rooms
        if "rooms" in entity_types:
            room_q = self.db.query(Room)
            if self.university_id:
                room_q = room_q.filter(Room.university_id == self.university_id)
            rooms = room_q.filter(
                or_(
                    Room.name.ilike(search_term),
                    Room.building.ilike(search_term)
                )
            ).limit(limit).all()
            
            results["rooms"] = [
                {
                    "id": r.id,
                    "name": r.name,
                    "building": r.building,
                    "capacity": r.capacity,
                    "room_type": r.room_type,
                }
                for r in rooms
            ]
            results["total"] += len(rooms)
        
        # Search student groups
        if "groups" in entity_types:
            grp_q = self.db.query(StudentGroup)
            if self.university_id:
                grp_q = grp_q.filter(StudentGroup.university_id == self.university_id)
            groups = grp_q.filter(
                StudentGroup.name.ilike(search_term)
            ).limit(limit).all()
            
            results["groups"] = [
                {
                    "id": g.id,
                    "name": g.name,
                    "level": g.level,
                    "size": g.size,
                    "group_type": getattr(g.group_type, "value", str(g.group_type)) if g.group_type else None,
                }
                for g in groups
            ]
            results["total"] += len(groups)

        return results
    
    def search_courses(
        self,
        query: Optional[str] = None,
        year: Optional[int] = None,
        department_id: Optional[int] = None,
        course_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Advanced course search with filters, scoped to self.university_id.
        """
        filters = []

        safe_query = sanitize_input(query, max_length=100) if query else None
        if safe_query and len(safe_query.strip()) >= 2:
            search_term = f"%{safe_query.lower()}%"
            filters.append(
                or_(
                    Course.code.ilike(search_term),
                    Course.name.ilike(search_term)
                )
            )

        if year is not None:
            filters.append(Course.level == year)

        if department_id is not None:
            filters.append(Course.department_id == department_id)

        if course_type:
            safe_course_type = sanitize_input(course_type, max_length=50)
            filters.append(Course.course_type == safe_course_type)

        q = self.db.query(Course).join(Department, Course.department_id == Department.id)
        if self.university_id:
            q = q.filter(Department.university_id == self.university_id)

        if filters:
            q = q.filter(and_(*filters))

        courses = q.limit(limit).all()

        return [
            {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "level": c.level,
                "credits": c.credits,
                "course_type": getattr(c.course_type, "value", str(c.course_type)) if c.course_type else None,
                "department_id": c.department_id
            }
            for c in courses
        ]
    
    def search_lecturers(
        self,
        query: Optional[str] = None,
        department_id: Optional[int] = None,
        min_hours: Optional[int] = None,
        max_hours: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        # NOTE: university_id scoping is applied via self.university_id in __init__
        """
        Advanced lecturer search with filters.
        
        Args:
            query: Text search query
            department_id: Filter by department
            min_hours: Minimum hours per week
            max_hours: Maximum hours per week
            limit: Maximum results
            
        Returns:
            List of lecturer dictionaries
        """
        filters = []

        safe_query = sanitize_input(query, max_length=100) if query else None
        if safe_query and len(safe_query.strip()) >= 2:
            search_term = f"%{safe_query.lower()}%"
            filters.append(
                or_(
                    Lecturer.staff_number.ilike(search_term),
                    Lecturer.full_name.ilike(search_term)
                    # email intentionally excluded from search matching
                )
            )

        if department_id is not None:
            filters.append(Lecturer.department_id == department_id)

        if min_hours is not None:
            filters.append(Lecturer.max_hours_per_week >= min_hours)

        if max_hours is not None:
            filters.append(Lecturer.max_hours_per_week <= max_hours)

        q = self.db.query(Lecturer).join(Department, Lecturer.department_id == Department.id)
        if self.university_id:
            q = q.filter(Department.university_id == self.university_id)

        if filters:
            q = q.filter(and_(*filters))

        lecturers = q.limit(limit).all()

        return [
            {
                "id": l.id,
                "staff_number": l.staff_number,
                "full_name": l.full_name,
                "department_id": l.department_id,
                "max_hours_per_week": l.max_hours_per_week
            }
            for l in lecturers
        ]
    
    def search_rooms(
        self,
        query: Optional[str] = None,
        building: Optional[str] = None,
        room_type: Optional[str] = None,
        min_capacity: Optional[int] = None,
        max_capacity: Optional[int] = None,
        available_only: bool = False,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Advanced room search with filters.
        
        Args:
            query: Text search query
            building: Filter by building
            category: Filter by room category
            min_capacity: Minimum capacity
            max_capacity: Maximum capacity
            available_only: Only show available rooms
            limit: Maximum results
            
        Returns:
            List of room dictionaries
        """
        filters = []

        safe_query = sanitize_input(query, max_length=100) if query else None
        if safe_query and len(safe_query.strip()) >= 2:
            search_term = f"%{safe_query.lower()}%"
            filters.append(
                or_(
                    Room.name.ilike(search_term),
                    Room.building.ilike(search_term)
                )
            )

        if building:
            safe_building = sanitize_input(building, max_length=100)
            filters.append(Room.building.ilike(f"%{safe_building}%"))

        if room_type:
            safe_room_type = sanitize_input(room_type, max_length=50)
            filters.append(Room.room_type == safe_room_type)

        if min_capacity is not None:
            filters.append(Room.capacity >= min_capacity)

        if max_capacity is not None:
            filters.append(Room.capacity <= max_capacity)

        if available_only:
            filters.append(Room.is_blocked == False)

        q = self.db.query(Room)
        if self.university_id:
            q = q.filter(Room.university_id == self.university_id)

        if filters:
            q = q.filter(and_(*filters))

        rooms = q.limit(limit).all()

        return [
            {
                "id": r.id,
                "name": r.name,
                "building": r.building,
                "capacity": r.capacity,
                "room_type": r.room_type,
            }
            for r in rooms
        ]
    
    def search_groups(
        self,
        query: Optional[str] = None,
        level: Optional[int] = None,
        group_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Advanced student group search with filters.
        All results are scoped to self.university_id when set.
        """
        filters = []

        safe_query = sanitize_input(query, max_length=100) if query else None
        if safe_query and len(safe_query.strip()) >= 2:
            search_term = f"%{safe_query.lower()}%"
            filters.append(StudentGroup.name.ilike(search_term))

        if level is not None:
            filters.append(StudentGroup.level == level)

        if group_type:
            safe_group_type = sanitize_input(group_type, max_length=50)
            filters.append(StudentGroup.group_type == safe_group_type)

        q = self.db.query(StudentGroup)
        if self.university_id:
            q = q.filter(StudentGroup.university_id == self.university_id)

        if filters:
            q = q.filter(and_(*filters))

        groups = q.limit(limit).all()

        return [
            {
                "id": g.id,
                "name": g.name,
                "level": g.level,
                "size": g.size,
                "group_type": getattr(g.group_type, "value", str(g.group_type)) if g.group_type else None,
            }
            for g in groups
        ]
