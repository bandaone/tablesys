from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..schemas import Department, DepartmentCreate
from ..models import Department as DepartmentModel, User
from ..auth import get_current_user, get_current_active_coordinator

router = APIRouter(prefix="/api/departments", tags=["departments"])

@router.get("/", response_model=List[Department])
async def get_departments(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all departments."""
    departments = db.query(DepartmentModel).offset(skip).limit(limit).all()
    return departments

@router.post("/", response_model=Department, status_code=status.HTTP_201_CREATED)
async def create_department(
    department: DepartmentCreate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Create a new department. Coordinator only."""
    existing = db.query(DepartmentModel).filter(
        (DepartmentModel.name == department.name) |
        (DepartmentModel.code == department.code)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Department already exists")
    
    db_department = DepartmentModel(**department.model_dump())
    db.add(db_department)
    db.commit()
    db.refresh(db_department)
    return db_department

@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: int,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Delete a department. Coordinator only."""
    db_department = db.query(DepartmentModel).filter(DepartmentModel.id == department_id).first()
    
    if not db_department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    db.delete(db_department)
    db.commit()
    return None
