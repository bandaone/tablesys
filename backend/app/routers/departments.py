from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..schemas import Department, DepartmentCreate
from ..models import Department as DepartmentModel, User
from ..auth import get_current_user, get_current_active_coordinator
from ..utils.sanitization import sanitize_input

router = APIRouter(prefix="/api/v1/departments", tags=["departments"])

# Validation helpers
def validate_department_fields(name: str, code: str) -> Optional[dict]:
    """Validate department field values. Returns error dict if invalid, None if valid."""
    if not name or len(name.strip()) == 0:
        return {"detail": "Department name cannot be empty", "field": "name"}
    if len(name) > 200:
        return {"detail": "Department name must be 200 characters or less", "field": "name"}
    if not code or len(code.strip()) == 0:
        return {"detail": "Department code cannot be empty", "field": "code"}
    if len(code) > 10:
        return {"detail": "Department code must be 10 characters or less", "field": "code"}
    return None

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
    # Validate field values
    validation_error = validate_department_fields(department.name, department.code)
    if validation_error:
        raise HTTPException(status_code=422, detail=validation_error["detail"])
    
    # Check for duplicate name or code
    existing = db.query(DepartmentModel).filter(
        (DepartmentModel.name == department.name) |
        (DepartmentModel.code == department.code)
    ).first()
    
    if existing:
        if existing.name == department.name:
            raise HTTPException(status_code=409, detail=f"Department with name '{department.name}' already exists")
        else:
            raise HTTPException(status_code=409, detail=f"Department with code '{department.code}' already exists")
    
    # Sanitize inputs
    dept_data = department.model_dump()
    dept_data['name'] = sanitize_input(department.name, max_length=200)
    dept_data['code'] = sanitize_input(department.code, max_length=10)
    
    db_department = DepartmentModel(**dept_data, university_id=current_user.university_id)
    db.add(db_department)
    db.commit()
    db.refresh(db_department)
    return db_department

@router.put("/{department_id}", response_model=Department)
async def update_department(
    department_id: int,
    department: DepartmentCreate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Update a department. Coordinator only."""
    db_department = db.query(DepartmentModel).filter(DepartmentModel.id == department_id).first()
    
    if not db_department:
        raise HTTPException(status_code=404, detail="Department not found")

    validation_error = validate_department_fields(department.name, department.code)
    if validation_error:
        raise HTTPException(status_code=422, detail=validation_error["detail"])

    existing = db.query(DepartmentModel).filter(
        (DepartmentModel.id != department_id) &
        ((DepartmentModel.name == department.name) |
        (DepartmentModel.code == department.code))
    ).first()
    
    if existing:
        if existing.name == department.name:
            raise HTTPException(status_code=409, detail=f"Department with name '{department.name}' already exists")
        else:
            raise HTTPException(status_code=409, detail=f"Department with code '{department.code}' already exists")

    db_department.name = sanitize_input(department.name, max_length=200)
    db_department.code = sanitize_input(department.code, max_length=10)
    
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
