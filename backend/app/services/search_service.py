"""
Search Service

Provides global search functionality across courses, lecturers, rooms, and groups.
Supports fuzzy matching and advanced filtering.
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Dict, Any, Optional
from ..models import Course, Lecturer, Room, StudentGroup, Department, User


class SearchService:
    """Service for searching across entities"""
    
    def __init__(self, db: Session):
        self.db = db
    
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
        if not query or len(query.strip()) < 2:
            return {
                "courses": [],
                "lecturers": [],
                "rooms": [],
                "groups": [],
                "total": 0
            }
        
        search_term = f"%{query.lower()}%"
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
            courses = self.db.query(Course).filter(
                or_(
                    Course.code.ilike(search_term),
                    Course.title.ilike(search_term)
                )
            ).limit(limit).all()
            
            results["courses"] = [
                {
                    "id": c.id,
                    "code": c.code,
                    "title": c.title,
                    "year": c.year,
                    "credits": c.credits,
                    "type": c.type
                }
                for c in courses
            ]
            results["total"] += len(courses)
        
        # Search lecturers
        if "lecturers" in entity_types:
            lecturers = self.db.query(Lecturer).filter(
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
                    "email": l.email,
                    "department_id": l.department_id,
                    "max_hours_per_week": l.max_hours_per_week
                }
                for l in lecturers
            ]
            results["total"] += len(lecturers)
        
        # Search rooms
        if "rooms" in entity_types:
            rooms = self.db.query(Room).filter(
                or_(
                    Room.room_number.ilike(search_term),
                    Room.building.ilike(search_term),
                    Room.category.ilike(search_term)
                )
            ).limit(limit).all()
            
            results["rooms"] = [
                {
                    "id": r.id,
                    "room_number": r.room_number,
                    "building": r.building,
                    "capacity": r.capacity,
                    "category": r.category,
                    "available_for_timetabling": r.available_for_timetabling
                }
                for r in rooms
            ]
            results["total"] += len(rooms)
        
        # Search student groups
        if "groups" in entity_types:
            groups = self.db.query(StudentGroup).filter(
                or_(
                    StudentGroup.name.ilike(search_term),
                    StudentGroup.type.ilike(search_term)
                )
            ).limit(limit).all()
            
            results["groups"] = [
                {
                    "id": g.id,
                    "name": g.name,
                    "year": g.year,
                    "program": g.program,
                    "size": g.size,
                    "type": g.type
                }
                for g in groups
            ]
            results["total"] += len(groups)
        
        return results
    
    def search_courses(
        self,
        query: Optional[str] = None,
        year: Optional[int] = None,
        program: Optional[str] = None,
        department_id: Optional[int] = None,
        course_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Advanced course search with filters.
        
        Args:
            query: Text search query
            year: Filter by year level
            program: Filter by program code
            department_id: Filter by department
            course_type: Filter by course type
            limit: Maximum results
            
        Returns:
            List of course dictionaries
        """
        filters = []
        
        if query and len(query.strip()) >= 2:
            search_term = f"%{query.lower()}%"
            filters.append(
                or_(
                    Course.code.ilike(search_term),
                    Course.title.ilike(search_term)
                )
            )
        
        if year is not None:
            filters.append(Course.year == year)
        
        if program:
            filters.append(Course.program.ilike(f"%{program}%"))
        
        if department_id is not None:
            filters.append(Course.department_id == department_id)
        
        if course_type:
            filters.append(Course.type == course_type)
        
        query = self.db.query(Course)
        
        if filters:
            query = query.filter(and_(*filters))
        
        courses = query.limit(limit).all()
        
        return [
            {
                "id": c.id,
                "code": c.code,
                "title": c.title,
                "year": c.year,
                "program": c.program,
                "credits": c.credits,
                "type": c.type,
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
        
        if query and len(query.strip()) >= 2:
            search_term = f"%{query.lower()}%"
            filters.append(
                or_(
                    Lecturer.staff_number.ilike(search_term),
                    Lecturer.full_name.ilike(search_term),
                    Lecturer.email.ilike(search_term)
                )
            )
        
        if department_id is not None:
            filters.append(Lecturer.department_id == department_id)
        
        if min_hours is not None:
            filters.append(Lecturer.max_hours_per_week >= min_hours)
        
        if max_hours is not None:
            filters.append(Lecturer.max_hours_per_week <= max_hours)
        
        query = self.db.query(Lecturer)
        
        if filters:
            query = query.filter(and_(*filters))
        
        lecturers = query.limit(limit).all()
        
        return [
            {
                "id": l.id,
                "staff_number": l.staff_number,
                "full_name": l.full_name,
                "email": l.email,
                "department_id": l.department_id,
                "max_hours_per_week": l.max_hours_per_week
            }
            for l in lecturers
        ]
    
    def search_rooms(
        self,
        query: Optional[str] = None,
        building: Optional[str] = None,
        category: Optional[str] = None,
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
        
        if query and len(query.strip()) >= 2:
            search_term = f"%{query.lower()}%"
            filters.append(
                or_(
                    Room.room_number.ilike(search_term),
                    Room.building.ilike(search_term)
                )
            )
        
        if building:
            filters.append(Room.building.ilike(f"%{building}%"))
        
        if category:
            filters.append(Room.category == category)
        
        if min_capacity is not None:
            filters.append(Room.capacity >= min_capacity)
        
        if max_capacity is not None:
            filters.append(Room.capacity <= max_capacity)
        
        if available_only:
            filters.append(Room.available_for_timetabling == True)
        
        query = self.db.query(Room)
        
        if filters:
            query = query.filter(and_(*filters))
        
        rooms = query.limit(limit).all()
        
        return [
            {
                "id": r.id,
                "room_number": r.room_number,
                "building": r.building,
                "capacity": r.capacity,
                "category": r.category,
                "available_for_timetabling": r.available_for_timetabling
            }
            for r in rooms
        ]
    
    def search_groups(
        self,
        query: Optional[str] = None,
        year: Optional[int] = None,
        program: Optional[str] = None,
        group_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Advanced student group search with filters.
        
        Args:
            query: Text search query
            year: Filter by year level
            program: Filter by program code
            group_type: Filter by group type
            limit: Maximum results
            
        Returns:
            List of group dictionaries
        """
        filters = []
        
        if query and len(query.strip()) >= 2:
            search_term = f"%{query.lower()}%"
            filters.append(StudentGroup.name.ilike(search_term))
        
        if year is not None:
            filters.append(StudentGroup.year == year)
        
        if program:
            filters.append(StudentGroup.program.ilike(f"%{program}%"))
        
        if group_type:
            filters.append(StudentGroup.type == group_type)
        
        query = self.db.query(StudentGroup)
        
        if filters:
            query = query.filter(and_(*filters))
        
        groups = query.limit(limit).all()
        
        return [
            {
                "id": g.id,
                "name": g.name,
                "year": g.year,
                "program": g.program,
                "size": g.size,
                "type": g.type
            }
            for g in groups
        ]
