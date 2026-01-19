from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import io
from ..database import get_db
from ..schemas import Lecturer, LecturerCreate, LecturerUpdate
from ..models import Lecturer as LecturerModel, User
from ..auth import get_current_user, get_current_active_coordinator

router = APIRouter(prefix="/api/lecturers", tags=["lecturers"])

@router.get("/", response_model=List[Lecturer])
async def get_lecturers(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all lecturers. HODs see only their department's lecturers."""
    query = db.query(LecturerModel)
    
    if current_user.role == "hod" and current_user.department_id:
        query = query.filter(LecturerModel.department_id == current_user.department_id)
    
    lecturers = query.offset(skip).limit(limit).all()
    return lecturers

@router.post("/", response_model=Lecturer, status_code=status.HTTP_201_CREATED)
async def create_lecturer(
    lecturer: LecturerCreate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Create a new lecturer. Coordinator only."""
    existing = db.query(LecturerModel).filter(
        (LecturerModel.staff_number == lecturer.staff_number) |
        (LecturerModel.email == lecturer.email)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Lecturer with this staff number or email already exists")
    
    db_lecturer = LecturerModel(**lecturer.model_dump())
    db.add(db_lecturer)
    db.commit()
    db.refresh(db_lecturer)
    return db_lecturer

@router.put("/{lecturer_id}", response_model=Lecturer)
async def update_lecturer(
    lecturer_id: int,
    lecturer_update: LecturerUpdate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Update a lecturer. Coordinator only."""
    db_lecturer = db.query(LecturerModel).filter(LecturerModel.id == lecturer_id).first()
    
    if not db_lecturer:
        raise HTTPException(status_code=404, detail="Lecturer not found")
    
    update_data = lecturer_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_lecturer, field, value)
    
    db.commit()
    db.refresh(db_lecturer)
    return db_lecturer

@router.delete("/{lecturer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lecturer(
    lecturer_id: int,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Delete a lecturer. Coordinator only."""
    db_lecturer = db.query(LecturerModel).filter(LecturerModel.id == lecturer_id).first()
    
    if not db_lecturer:
        raise HTTPException(status_code=404, detail="Lecturer not found")
    
    db.delete(db_lecturer)
    db.commit()
    return None

@router.delete("/", status_code=status.HTTP_200_OK)
async def delete_all_lecturers(
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Delete all lecturers. Coordinator only. Use before bulk re-upload."""
    count = db.query(LecturerModel).count()
    db.query(LecturerModel).delete()
    db.commit()
    return {"status": "success", "deleted": count, "message": f"Deleted {count} lecturers"}

@router.post("/bulk-upload", response_model=dict)
async def bulk_upload_lecturers(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """
    Bulk upload lecturers from Excel/CSV file. Coordinator only.
    Expected columns: staff_number, full_name, email, department_id, max_hours_per_week
    """
    if file.content_type not in ["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")
    
    try:
        contents = await file.read()
        
        if file.content_type == "text/csv":
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        required_columns = ['staff_number', 'full_name', 'email', 'department_id']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        if 'max_hours_per_week' not in df.columns:
            df['max_hours_per_week'] = 20
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                existing = db.query(LecturerModel).filter(
                    (LecturerModel.staff_number == str(row['staff_number'])) |
                    (LecturerModel.email == str(row['email']))
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                lecturer = LecturerModel(
                    staff_number=str(row['staff_number']),
                    full_name=str(row['full_name']),
                    email=str(row['email']),
                    department_id=int(row['department_id']),
                    max_hours_per_week=int(row.get('max_hours_per_week', 20))
                )
                
                db.add(lecturer)
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
