from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import io
from ..database import get_db
from ..schemas import StudentGroup, StudentGroupCreate, StudentGroupUpdate
from ..models import StudentGroup as StudentGroupModel, User
from ..auth import get_current_user, get_current_active_coordinator

router = APIRouter(prefix="/api/groups", tags=["student-groups"])

@router.get("/", response_model=List[StudentGroup])
async def get_groups(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all student groups. HODs see only their department's groups."""
    query = db.query(StudentGroupModel)
    
    if current_user.role == "hod" and current_user.department_id:
        query = query.filter(StudentGroupModel.department_id == current_user.department_id)
    
    groups = query.offset(skip).limit(limit).all()
    return groups

@router.post("/", response_model=StudentGroup, status_code=status.HTTP_201_CREATED)
async def create_group(
    group: StudentGroupCreate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Create a new student group. Coordinator only."""
    existing = db.query(StudentGroupModel).filter(StudentGroupModel.name == group.name).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Group already exists")
    
    db_group = StudentGroupModel(**group.model_dump())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

@router.put("/{group_id}", response_model=StudentGroup)
async def update_group(
    group_id: int,
    group_update: StudentGroupUpdate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Update a student group. Coordinator only."""
    db_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group_id).first()
    
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    update_data = group_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_group, field, value)
    
    db.commit()
    db.refresh(db_group)
    return db_group

@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Delete a student group. Coordinator only."""
    db_group = db.query(StudentGroupModel).filter(StudentGroupModel.id == group_id).first()
    
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    db.delete(db_group)
    db.commit()
    return None

@router.post("/bulk-upload", response_model=dict)
async def bulk_upload_groups(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """
    Bulk upload student groups from Excel/CSV file. Coordinator only.
    Expected columns: name, level, department_id, size
    """
    if file.content_type not in ["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")
    
    try:
        contents = await file.read()
        
        if file.content_type == "text/csv":
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        required_columns = ['name', 'level', 'department_id', 'size']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                existing = db.query(StudentGroupModel).filter(StudentGroupModel.name == str(row['name'])).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                group = StudentGroupModel(
                    name=str(row['name']),
                    level=int(row['level']),
                    department_id=int(row['department_id']),
                    size=int(row['size'])
                )
                
                db.add(group)
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
