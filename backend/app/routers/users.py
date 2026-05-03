"""
Users Management Router

Provides CRUD operations for user accounts, password management,
and profile updates. Only Coordinators can manage other users.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from ..database import get_db
from ..schemas import User, UserRole
from ..models import User as UserModel
from ..auth import get_current_user, get_current_active_coordinator, get_password_hash, verify_password
from ..utils.sanitization import sanitize_input
from ..utils.audit_logger import AuditLogger
from ..utils.email_service import EmailService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# Request/Response Models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str
    role: UserRole
    department_id: Optional[int] = None
    is_active: bool = True


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    department_id: Optional[int] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class ProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


@router.get("/", response_model=List[User])
async def get_all_users(
    current_user: UserModel = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """
    Get all users. Coordinator only.
    Returns list of all users in the system.
    """
    users = db.query(UserModel).filter(UserModel.university_id == current_user.university_id).all()
    return users


@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: int,
    current_user: UserModel = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """
    Get user by ID. Coordinator only.
    """
    user = db.query(UserModel).filter(
        UserModel.id == user_id,
        UserModel.university_id == current_user.university_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.post("/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: UserModel = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """
    Create new user. Coordinator only.
    Username and email must be unique.
    """
    # Sanitize inputs
    username = sanitize_input(user_data.username)
    email = sanitize_input(user_data.email)
    full_name = sanitize_input(user_data.full_name)
    
    # Check if username already exists
    existing_user = db.query(UserModel).filter(UserModel.username == username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    existing_email = db.query(UserModel).filter(UserModel.email == email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate department if provided
    if user_data.department_id:
        from ..models import Department
        dept = db.query(Department).filter(Department.id == user_data.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid department_id"
            )
    
    # Hash password
    hashed_password = get_password_hash(user_data.password)
    
    # Create user
    db_user = UserModel(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password=hashed_password,
        role=user_data.role,
        department_id=user_data.department_id,
        university_id=current_user.university_id,
        is_active=user_data.is_active
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Log user creation
    AuditLogger.log_action(
        action="USER_CREATED",
        user_id=current_user.id,
        details={
            "new_user_id": db_user.id,
            "username": db_user.username,
            "role": db_user.role.value
        }
    )
    
    # Send welcome email with credentials
    import logging
    try:
        EmailService.send_new_user_welcome_email(
            recipient=db_user.email,
            user_name=db_user.full_name,
            username=db_user.username,
            password=user_data.password,
            role=db_user.role.value
        )
    except Exception as e:
        # Don't fail user creation if email fails
        logging.getLogger(__name__).warning(f"Failed to send welcome email to {db_user.email}: {e}")
    
    return db_user


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: UserModel = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """
    Update user. Coordinator only.
    Can update email, full_name, role, department, and active status.
    """
    db_user = db.query(UserModel).filter(
        UserModel.id == user_id,
        UserModel.university_id == current_user.university_id
    ).first()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent coordinator from deactivating themselves
    if user_id == current_user.id and user_data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    # Update fields if provided
    if user_data.email is not None:
        # Check email uniqueness
        existing_email = db.query(UserModel).filter(
            UserModel.email == user_data.email,
            UserModel.id != user_id
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        db_user.email = sanitize_input(user_data.email)
    
    if user_data.full_name is not None:
        db_user.full_name = sanitize_input(user_data.full_name)
    
    if user_data.role is not None:
        db_user.role = user_data.role
    
    if user_data.department_id is not None:
        # Validate department
        from ..models import Department
        dept = db.query(Department).filter(Department.id == user_data.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid department_id"
            )
        db_user.department_id = user_data.department_id
    
    if user_data.is_active is not None:
        db_user.is_active = user_data.is_active
    
    db.commit()
    db.refresh(db_user)
    
    # Log user update
    AuditLogger.log_action(
        action="USER_UPDATED",
        user_id=current_user.id,
        details={
            "updated_user_id": user_id,
            "changes": user_data.dict(exclude_unset=True)
        }
    )
    
    return db_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: UserModel = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """
    Delete user. Coordinator only.
    Cannot delete yourself.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    db_user = db.query(UserModel).filter(
        UserModel.id == user_id,
        UserModel.university_id == current_user.university_id
    ).first()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Log deletion before removing
    AuditLogger.log_action(
        action="USER_DELETED",
        user_id=current_user.id,
        details={
            "deleted_user_id": user_id,
            "username": db_user.username
        }
    )
    
    db.delete(db_user)
    db.commit()
    
    return None


@router.post("/{user_id}/reset-password", response_model=dict)
async def reset_user_password(
    user_id: int,
    password_data: PasswordReset,
    current_user: UserModel = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """
    Reset user password. Coordinator only.
    Used when a user forgets their password.
    """
    db_user = db.query(UserModel).filter(
        UserModel.id == user_id,
        UserModel.university_id == current_user.university_id
    ).first()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Hash new password
    db_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    
    # Log password reset
    AuditLogger.log_action(
        action="PASSWORD_RESET",
        user_id=current_user.id,
        details={
            "reset_user_id": user_id,
            "username": db_user.username
        }
    )
    
    return {"status": "success", "message": "Password reset successfully"}


@router.post("/me/change-password", response_model=dict)
async def change_own_password(
    password_data: PasswordChange,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change own password. Any authenticated user.
    Requires current password for verification.
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Hash new password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    
    # Log password change
    AuditLogger.log_action(
        action="PASSWORD_CHANGED",
        user_id=current_user.id,
        details={"self_initiated": True}
    )
    
    return {"status": "success", "message": "Password changed successfully"}


@router.put("/me/profile", response_model=User)
async def update_own_profile(
    profile_data: ProfileUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update own profile. Any authenticated user.
    Can only update email and full_name.
    """
    if profile_data.email is not None:
        # Check email uniqueness
        existing_email = db.query(UserModel).filter(
            UserModel.email == profile_data.email,
            UserModel.id != current_user.id
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        current_user.email = sanitize_input(profile_data.email)
    
    if profile_data.full_name is not None:
        current_user.full_name = sanitize_input(profile_data.full_name)
    
    db.commit()
    db.refresh(current_user)
    
    # Log profile update
    AuditLogger.log_action(
        action="PROFILE_UPDATED",
        user_id=current_user.id,
        details={"changes": profile_data.dict(exclude_unset=True)}
    )
    
    return current_user
