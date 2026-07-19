from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .database import get_db
from .models import User, UserRole
from .schemas import TokenData
from .config import settings
from .access_policy import enforce_active_account, enforce_user_roles

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

from fastapi import Request

async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    # Fallback to query parameter 'token' if the header token is missing or invalid.
    # OAuth2PasswordBearer throws a 401 if it's missing, so we must intercept it or make it optional.
    # Actually, if OAuth2PasswordBearer is used as above, it forces the header.
    if not token:
        token = request.query_params.get("token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    enforce_active_account(user.is_active)

    # Enforce tenant context from authenticated identity so clients cannot
    # escalate access by omitting/spoofing X-University-ID.
    from .middleware.tenant import set_current_tenant_id
    set_current_tenant_id(user.university_id)

    return user

async def get_current_active_coordinator(
    current_user: User = Depends(get_current_user)
) -> User:
    enforce_user_roles(
        current_user.role,
        [UserRole.COORDINATOR, UserRole.SCHOOL_COORDINATOR, UserRole.TENANT_ADMIN],
        "Not enough permissions. Coordinator access required.",
    )
    return current_user

async def get_current_active_hod(
    current_user: User = Depends(get_current_user)
) -> User:
    enforce_user_roles(
        current_user.role,
        [UserRole.COORDINATOR, UserRole.SCHOOL_COORDINATOR, UserRole.TENANT_ADMIN, UserRole.HOD],
        "Not enough permissions. HOD or Coordinator access required.",
    )
    return current_user


async def get_current_active_lab_coordinator(
    current_user: User = Depends(get_current_user)
) -> User:
    enforce_user_roles(
        current_user.role,
        [
            UserRole.COORDINATOR,
            UserRole.SCHOOL_COORDINATOR,
            UserRole.TENANT_ADMIN,
            UserRole.HOD,
            UserRole.LAB_COORDINATOR,
        ],
        "Lab coordinator access required.",
    )
    return current_user

async def get_current_active_lab_coordinator_writer(
    current_user: User = Depends(get_current_user)
) -> User:
    enforce_user_roles(
        current_user.role,
        [
            UserRole.COORDINATOR,
            UserRole.TENANT_ADMIN,
            UserRole.HOD,
            UserRole.LAB_COORDINATOR,
        ],
        "Lab coordinator write access required.",
    )
    return current_user


def is_tenant_admin(user: User) -> bool:
    return user.role == UserRole.TENANT_ADMIN


def is_school_operator(user: User) -> bool:
    return user.role in {
        UserRole.TENANT_ADMIN,
        UserRole.SCHOOL_COORDINATOR,
        UserRole.COORDINATOR,
    }


def resolve_effective_school_scope(user: User, explicit_school_id: Optional[int] = None) -> Optional[int]:
    if explicit_school_id is not None:
        if is_tenant_admin(user):
            return explicit_school_id
        if getattr(user, "school_id", None) == explicit_school_id:
            return explicit_school_id
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to the requested school scope.",
        )
    if is_tenant_admin(user):
        return None
    return getattr(user, "school_id", None)


async def get_current_active_tenant_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    enforce_user_roles(
        current_user.role,
        [UserRole.TENANT_ADMIN],
        "Tenant admin access required.",
    )
    return current_user


async def get_current_active_school_operator(
    current_user: User = Depends(get_current_user)
) -> User:
    enforce_user_roles(
        current_user.role,
        [UserRole.TENANT_ADMIN, UserRole.SCHOOL_COORDINATOR, UserRole.COORDINATOR],
        "School operator access required.",
    )
    return current_user


async def get_current_active_hod_or_school_operator(
    current_user: User = Depends(get_current_user)
) -> User:
    enforce_user_roles(
        current_user.role,
        [UserRole.TENANT_ADMIN, UserRole.SCHOOL_COORDINATOR, UserRole.COORDINATOR, UserRole.HOD],
        "HOD or school operator access required.",
    )
    return current_user

async def get_current_superadmin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Platform-level guard — only the SUPERADMIN role passes."""
    enforce_user_roles(
        current_user.role,
        [UserRole.SUPERADMIN],
        "Super-admin access required. This area is restricted to platform administrators.",
    )
    return current_user
