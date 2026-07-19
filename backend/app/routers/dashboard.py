"""
Dashboard Router - Admin Dashboard API Endpoints
Provides comprehensive system statistics and analytics
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from ..database import get_db
from ..auth import get_current_active_school_operator
from ..models import User
from ..services.dashboard_service import DashboardService


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def require_dashboard_access(current_user: User = Depends(get_current_active_school_operator)):
    """
    Dependency to ensure only Admin users can access dashboard endpoints
    """
    return current_user


@router.get("/", response_model=Dict[str, Any])
async def get_complete_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_dashboard_access)
):
    """
    Get complete dashboard with all statistics in a single call
    
    Returns comprehensive analytics including:
    - Overview statistics
    - User metrics
    - Timetable statistics
    - Resource utilization
    - Department summaries
    - Recent activity
    - System health
    - Weekly statistics
    """
    service = DashboardService(db, current_user)
    return service.get_complete_dashboard()


@router.get("/overview", response_model=Dict[str, Any])
async def get_overview_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_dashboard_access)
):
    """
    Get high-level overview statistics
    
    Returns counts of all major entities:
    - Total users, departments, courses, lecturers, rooms, groups
    - Total timetables (generated and draft)
    - Active users
    """
    service = DashboardService(db, current_user)
    return service.get_overview_stats()


@router.get("/users", response_model=Dict[str, Any])
async def get_user_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_dashboard_access)
):
    """
    Get detailed user statistics
    
    Returns:
    - User counts by role (Admin, HOD, Coordinator, Lecturer)
    - Recent user signups (last 30 days)
    - Total active users
    """
    service = DashboardService(db, current_user)
    return service.get_user_statistics()


@router.get("/timetables", response_model=Dict[str, Any])
async def get_timetable_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_dashboard_access)
):
    """
    Get detailed timetable statistics
    
    Returns:
    - Total timetables (generated and draft)
    - Timetables by department
    - Recent generation activity (last 7 days)
    - Total slots scheduled
    - Version statistics
    """
    service = DashboardService(db, current_user)
    return service.get_timetable_statistics()


@router.get("/resources", response_model=Dict[str, Any])
async def get_resource_utilization(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_dashboard_access)
):
    """
    Get resource utilization metrics
    
    Returns:
    - Room utilization (total, in use, utilization percent, capacity usage)
    - Lecturer utilization (total, assigned, unassigned, average hours)
    """
    service = DashboardService(db, current_user)
    return service.get_resource_utilization()


@router.get("/departments", response_model=List[Dict[str, Any]])
async def get_department_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_dashboard_access)
):
    """
    Get summary statistics for each department
    
    Returns array of department summaries with:
    - Department info (id, name, code)
    - Resource counts (courses, lecturers, groups, timetables)
    - HOD information
    """
    service = DashboardService(db, current_user)
    return service.get_department_summary()


@router.get("/activity", response_model=Dict[str, List[Dict[str, Any]]])
async def get_recent_activity(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_dashboard_access)
):
    """
    Get recent activity across the system
    
    Query Parameters:
    - limit: Maximum number of items per category (default: 10, max: 50)
    
    Returns recent:
    - Timetables (created/updated)
    - Users (signups)
    - Notifications (sent)
    """
    if limit > 50:
        limit = 50
    
    service = DashboardService(db, current_user)
    return service.get_recent_activity(limit=limit)


@router.get("/health", response_model=Dict[str, Any])
async def get_system_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_dashboard_access)
):
    """
    Get system health metrics and identify potential issues
    
    Returns:
    - Health score (0-100)
    - Status (healthy, warning, critical)
    - Issues (errors that need attention)
    - Warnings (informational alerts)
    
    Checks for:
    - Overutilized lecturers (>16 hours/week)
    - Overcrowded rooms (group size > room capacity)
    - Unused rooms
    - Unassigned lecturers
    - Draft timetables
    """
    service = DashboardService(db)
    return service.get_system_health()


@router.get("/weekly", response_model=Dict[str, Any])
async def get_weekly_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_dashboard_access)
):
    """
    Get statistics for the current week
    
    Returns metrics for the last 7 days:
    - Timetables generated
    - Users created
    - Courses added
    - Notifications sent
    - Period start and end timestamps
    """
    service = DashboardService(db)
    return service.get_weekly_statistics()


@router.get("/readiness", response_model=List[Dict[str, Any]])
async def get_readiness_checklist(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_dashboard_access)
):
    """
    Setup-readiness checklist for the dashboard chip strip.
    Each item: { key, label, status ('done'|'warn'|'error'), count, hint }
    """
    service = DashboardService(db, current_user)
    return service.get_readiness_checklist()
