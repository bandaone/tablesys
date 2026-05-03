"""
Search Router

Provides global search and advanced filtering endpoints.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List
from ..database import get_db
from ..models import User
from ..auth import get_current_user
from ..services.search_service import SearchService

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("/", status_code=status.HTTP_200_OK)
async def global_search(
    q: str = Query(..., min_length=2, description="Search query"),
    types: Optional[List[str]] = Query(None, description="Entity types to search"),
    limit: int = Query(50, ge=1, le=100, description="Results per type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Global search across courses, lecturers, rooms, and groups.
    
    Query params:
    - q: Search query (minimum 2 characters)
    - types: Entity types to search (courses, lecturers, rooms, groups)
    - limit: Maximum results per entity type (1-100)
    """
    search_service = SearchService(db)
    results = search_service.global_search(q, types, limit)
    
    return results


@router.get("/courses", status_code=status.HTTP_200_OK)
async def search_courses(
    q: Optional[str] = Query(None, min_length=2, description="Search query"),
    year: Optional[int] = Query(None, ge=1, le=5, description="Year level"),
    program: Optional[str] = Query(None, description="Program code"),
    department_id: Optional[int] = Query(None, description="Department ID"),
    course_type: Optional[str] = Query(None, description="Course type"),
    limit: int = Query(100, ge=1, le=200, description="Maximum results"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Advanced course search with multiple filters.
    """
    search_service = SearchService(db)
    results = search_service.search_courses(
        query=q,
        year=year,
        program=program,
        department_id=department_id,
        course_type=course_type,
        limit=limit
    )
    
    return {
        "courses": results,
        "total": len(results)
    }


@router.get("/lecturers", status_code=status.HTTP_200_OK)
async def search_lecturers(
    q: Optional[str] = Query(None, min_length=2, description="Search query"),
    department_id: Optional[int] = Query(None, description="Department ID"),
    min_hours: Optional[int] = Query(None, ge=0, description="Minimum hours per week"),
    max_hours: Optional[int] = Query(None, ge=0, description="Maximum hours per week"),
    limit: int = Query(100, ge=1, le=200, description="Maximum results"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Advanced lecturer search with multiple filters.
    """
    search_service = SearchService(db)
    results = search_service.search_lecturers(
        query=q,
        department_id=department_id,
        min_hours=min_hours,
        max_hours=max_hours,
        limit=limit
    )
    
    return {
        "lecturers": results,
        "total": len(results)
    }


@router.get("/rooms", status_code=status.HTTP_200_OK)
async def search_rooms(
    q: Optional[str] = Query(None, min_length=2, description="Search query"),
    building: Optional[str] = Query(None, description="Building name"),
    category: Optional[str] = Query(None, description="Room category"),
    min_capacity: Optional[int] = Query(None, ge=0, description="Minimum capacity"),
    max_capacity: Optional[int] = Query(None, ge=0, description="Maximum capacity"),
    available_only: bool = Query(False, description="Only available rooms"),
    limit: int = Query(100, ge=1, le=200, description="Maximum results"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Advanced room search with multiple filters.
    """
    search_service = SearchService(db)
    results = search_service.search_rooms(
        query=q,
        building=building,
        category=category,
        min_capacity=min_capacity,
        max_capacity=max_capacity,
        available_only=available_only,
        limit=limit
    )
    
    return {
        "rooms": results,
        "total": len(results)
    }


@router.get("/groups", status_code=status.HTTP_200_OK)
async def search_groups(
    q: Optional[str] = Query(None, min_length=2, description="Search query"),
    year: Optional[int] = Query(None, ge=1, le=5, description="Year level"),
    program: Optional[str] = Query(None, description="Program code"),
    group_type: Optional[str] = Query(None, description="Group type"),
    limit: int = Query(100, ge=1, le=200, description="Maximum results"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Advanced student group search with multiple filters.
    """
    search_service = SearchService(db)
    results = search_service.search_groups(
        query=q,
        year=year,
        program=program,
        group_type=group_type,
        limit=limit
    )
    
    return {
        "groups": results,
        "total": len(results)
    }
