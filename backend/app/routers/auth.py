from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from ..database import get_db
from ..schemas import Token, User
from ..auth import create_access_token, get_current_user
from ..config import settings
from ..models import User as UserModel
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["authentication"])

class SimpleLoginRequest(BaseModel):
    username: str

@router.post("/login", response_model=Token)
async def login(
    login_data: SimpleLoginRequest,
    db: Session = Depends(get_db)
):
    """Simple username-only authentication - no password required"""
    # Find user by username (case-insensitive)
    user = db.query(UserModel).filter(
        UserModel.username.ilike(login_data.username)
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: UserModel = Depends(get_current_user)
):
    """Get current user information"""
    return current_user
