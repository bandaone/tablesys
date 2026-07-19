"""
Reports Router - Advanced Reporting API Endpoints
Provides endpoints for generating and exporting various reports
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from ..database import get_db
from ..auth import get_current_active_hod_or_school_operator
from ..models import User, UserRole
from ..services.report_service import ReportService


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


# Pydantic models for request/response
class CustomReportConfig(BaseModel):
    report_name: str
    entities: List[str]
    filters: Dict[str, Any] = {}
    fields: List[str] = []
    group_by: Optional[str] = None
    order_by: Optional[str] = None


def require_reports_access(current_user: User = Depends(get_current_active_hod_or_school_operator)):
    """
    Dependency to ensure only Coordinators, HODs, or Admins can access reports
    """
    return current_user


@router.get("/types", response_model=List[Dict[str, str]])
async def get_report_types(
    current_user: User = Depends(require_reports_access),
    db: Session = Depends(get_db)
):
    """
    Get list of available report types
    
    Returns array of report type definitions with:
    - type: Report type identifier
    - name: Display name
    - description: Report description
    """
    service = ReportService(db, current_user)
    return service.get_available_report_types()


@router.get("/lecturer-workload", response_model=Dict[str, Any])
async def generate_lecturer_workload_report(
    department_id: Optional[int] = None,
    lecturer_id: Optional[int] = None,
    current_user: User = Depends(require_reports_access),
    db: Session = Depends(get_db)
):
    """
    Generate lecturer workload report
    
    Query Parameters:
    - department_id: Filter by department (optional)
    - lecturer_id: Filter by specific lecturer (optional)
    
    Returns detailed workload analysis including:
    - Hours taught per lecturer
    - Course assignments
    - Workload percentage vs maximum hours
    - Workload status (optimal/overloaded/underutilized)
    """
    service = ReportService(db, current_user)
    report = service.generate_lecturer_workload_report(
        department_id=department_id,
        lecturer_id=lecturer_id
    )
    return report


@router.get("/room-utilization", response_model=Dict[str, Any])
async def generate_room_utilization_report(
    building: Optional[str] = None,
    category: Optional[str] = None,
    current_user: User = Depends(require_reports_access),
    db: Session = Depends(get_db)
):
    """
    Generate room utilization report
    
    Query Parameters:
    - building: Filter by building (optional)
    - category: Filter by room category (optional)
    
    Returns usage statistics including:
    - Slots used vs available
    - Utilization percentage
    - Average capacity usage
    - Courses scheduled in each room
    """
    service = ReportService(db, current_user)
    report = service.generate_room_utilization_report(
        building=building,
        category=category
    )
    return report


@router.get("/department-comparison", response_model=Dict[str, Any])
async def generate_department_comparison_report(
    current_user: User = Depends(require_reports_access),
    db: Session = Depends(get_db)
):
    """
    Generate department comparison report
    
    Returns comparative analysis across all departments including:
    - Resource distribution (courses, lecturers, groups)
    - Timetable completion status
    - Teaching hours distribution
    - Student-to-lecturer ratios
    """
    service = ReportService(db, current_user)
    report = service.generate_department_comparison_report()
    return report


@router.get("/timetable-summary/{timetable_id}", response_model=Dict[str, Any])
async def generate_timetable_summary_report(
    timetable_id: int,
    current_user: User = Depends(require_reports_access),
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive summary report for a specific timetable
    
    Path Parameters:
    - timetable_id: ID of the timetable
    
    Returns:
    - Timetable metadata
    - Statistics (total slots, unique resources)
    - Distribution by day and time
    """
    service = ReportService(db, current_user)
    report = service.generate_timetable_summary_report(timetable_id=timetable_id)
    
    if 'error' in report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=report['error']
        )
    
    return report


@router.post("/custom", response_model=Dict[str, Any])
async def generate_custom_report(
    config: CustomReportConfig,
    current_user: User = Depends(require_reports_access),
    db: Session = Depends(get_db)
):
    """
    Generate custom report based on configuration
    
    Request Body:
    - report_name: Name of the report
    - entities: List of entities to include (courses, lecturers, rooms, student_groups)
    - filters: Dictionary of filters to apply
    - fields: List of fields to include (optional)
    - group_by: Field to group results by (optional)
    - order_by: Field to order results by (optional)
    
    Example:
    ```json
    {
        "report_name": "MEC Department Courses",
        "entities": ["courses", "lecturers"],
        "filters": {
            "department_id": 1
        },
        "fields": ["code", "name", "credit_hours"]
    }
    ```
    """
    service = ReportService(db, current_user)
    report = service.generate_custom_report(config.dict())
    return report


@router.get("/export/{report_type}", response_class=Response)
async def export_report(
    report_type: str,
    format: str = "json",
    department_id: Optional[int] = None,
    lecturer_id: Optional[int] = None,
    building: Optional[str] = None,
    category: Optional[str] = None,
    timetable_id: Optional[int] = None,
    current_user: User = Depends(require_reports_access),
    db: Session = Depends(get_db)
):
    """
    Export report in specified format
    
    Path Parameters:
    - report_type: Type of report (lecturer-workload, room-utilization, department-comparison, timetable-summary)
    
    Query Parameters:
    - format: Export format (json, csv) - default: json
    - Additional filters based on report type
    
    Returns file download with appropriate content type
    """
    service = ReportService(db, current_user)
    
    # Generate report based on type
    if report_type == "lecturer-workload":
        report = service.generate_lecturer_workload_report(
            department_id=department_id,
            lecturer_id=lecturer_id
        )
    elif report_type == "room-utilization":
        report = service.generate_room_utilization_report(
            building=building,
            category=category
        )
    elif report_type == "department-comparison":
        report = service.generate_department_comparison_report()
    elif report_type == "timetable-summary":
        if not timetable_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="timetable_id is required for timetable-summary report"
            )
        report = service.generate_timetable_summary_report(timetable_id=timetable_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown report type: {report_type}"
        )
    
    # Export in specified format
    if format == "json":
        json_data = service.export_report_to_json(report)
        return Response(
            content=json_data,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={report_type}_report.json"
            }
        )
    elif format == "csv":
        # CSV export would require converting the nested JSON to flat CSV
        # For now, return JSON with a note
        json_data = service.export_report_to_json(report)
        return Response(
            content=json_data,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={report_type}_report.json"
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported export format: {format}"
        )


@router.get("/quick-stats", response_model=Dict[str, Any])
async def get_quick_stats(
    current_user: User = Depends(get_current_active_hod_or_school_operator),
    db: Session = Depends(get_db)
):
    """
    Get quick statistics for reports dashboard
    
    Returns high-level metrics useful for reports overview page
    """
    service = ReportService(db)
    
    # Generate multiple reports for quick overview
    lecturer_report = service.generate_lecturer_workload_report()
    room_report = service.generate_room_utilization_report()
    dept_report = service.generate_department_comparison_report()
    
    return {
        'lecturer_stats': lecturer_report['summary'],
        'room_stats': room_report['summary'],
        'department_stats': dept_report['summary'],
        'generated_at': lecturer_report['generated_at']
    }
