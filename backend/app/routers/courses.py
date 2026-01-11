from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import io
from ..database import get_db
from ..schemas import Course, CourseCreate, CourseUpdate, CourseBulkUpload
from ..models import Course as CourseModel, User
from ..auth import get_current_user, get_current_active_coordinator, get_current_active_hod

router = APIRouter(prefix="/api/courses", tags=["courses"])

@router.get("/", response_model=List[Course])
async def get_courses(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all courses. HODs see only their department's courses."""
    query = db.query(CourseModel)
    
    if current_user.role == "hod" and current_user.department_id:
        query = query.filter(CourseModel.department_id == current_user.department_id)
    
    courses = query.offset(skip).limit(limit).all()
    return courses

@router.get("/{course_id}", response_model=Course)
async def get_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific course."""
    course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # HODs can only view courses in their department
    if current_user.role == "hod" and current_user.department_id != course.department_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return course

@router.post("/", response_model=Course, status_code=status.HTTP_201_CREATED)
async def create_course(
    course: CourseCreate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Create a new course. Coordinator only."""
    # Check if course code already exists
    existing = db.query(CourseModel).filter(CourseModel.code == course.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Course code already exists")
    
    db_course = CourseModel(**course.model_dump())
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

@router.put("/{course_id}", response_model=Course)
async def update_course(
    course_id: int,
    course_update: CourseUpdate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Update a course. Coordinator only."""
    db_course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    update_data = course_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_course, field, value)
    
    db.commit()
    db.refresh(db_course)
    return db_course

@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: int,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Delete a course. Coordinator only."""
    db_course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    db.delete(db_course)
    db.commit()
    return None

@router.post("/bulk-upload", response_model=dict)
async def bulk_upload_courses(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bulk upload courses from Excel/CSV file.
    Coordinators can upload for any department.
    HODs can only upload for their department.
    
    Expected columns: code, name, department_id, level, credits, lecture_hours, tutorial_hours, practical_hours
    """
    if file.content_type not in ["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")
    
    try:
        contents = await file.read()
        
        # Read file based on type
        if file.content_type == "text/csv":
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        # Validate required columns
        required_columns = ['code', 'name', 'department_id', 'level', 'credits', 'lecture_hours']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        # Set default values for optional columns
        if 'tutorial_hours' not in df.columns:
            df['tutorial_hours'] = 0
        if 'practical_hours' not in df.columns:
            df['practical_hours'] = 0
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                # HODs can only upload courses for their department
                if current_user.role == "hod":
                    if current_user.department_id != int(row['department_id']):
                        errors.append(f"Row {idx + 2}: Access denied - not your department")
                        skipped_count += 1
                        continue
                
                # Check if course already exists
                existing = db.query(CourseModel).filter(CourseModel.code == row['code']).first()
                if existing:
                    skipped_count += 1
                    continue
                
                # Create course
                course = CourseModel(
                    code=str(row['code']),
                    name=str(row['name']),
                    department_id=int(row['department_id']),
                    level=int(row['level']),
                    credits=int(row['credits']),
                    lecture_hours=int(row['lecture_hours']),
                    tutorial_hours=int(row.get('tutorial_hours', 0)),
                    practical_hours=int(row.get('practical_hours', 0))
                )
                
                db.add(course)
                created_count += 1
                
            except Exception as e:
                errors.append(f"Row {idx + 2}: {str(e)}")
                skipped_count += 1
        
        db.commit()
        
        return {
            "status": "success",
            "created": created_count,
            "skipped": skipped_count,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")
