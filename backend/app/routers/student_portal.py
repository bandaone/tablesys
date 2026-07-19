"""
Student Portal Router - Student Authentication and Timetable Access
Provides endpoints for student login and personal timetable viewing
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

from ..database import get_db
from ..models import Student, StudentGroup, Department, Timetable, TimetableSlot, Course, Lecturer, Room, CourseAnnouncement
from ..config import settings
from ..access_policy import enforce_active_student
from ..utils.display_formatting import format_department_name, format_group_label, format_person_name, format_room_name
from ..utils.sanitization import sanitize_input


router = APIRouter(prefix="/api/v1/student", tags=["student-portal"])

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for students
oauth2_scheme_student = OAuth2PasswordBearer(tokenUrl="/api/v1/student/login")


# Pydantic models
class StudentCreate(BaseModel):
    student_number: str
    full_name: str
    email: EmailStr
    password: str
    program: str
    year_level: int
    group_id: Optional[int] = None
    department_id: Optional[int] = None


class StudentResponse(BaseModel):
    id: int
    student_number: str
    full_name: str
    email: str
    program: str
    year_level: int
    group_id: Optional[int]
    department_id: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True


class StudentLoginResponse(BaseModel):
    access_token: str
    token_type: str
    student: StudentResponse


class TimetableSlotResponse(BaseModel):
    id: int
    day_of_week: str
    start_time: str
    end_time: str
    course_code: str
    course_name: str
    lecturer_name: str
    room_number: str
    building: str


# Helper functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_student_access_token(data: dict, expires_delta: timedelta = None):
    """Create JWT token for student"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)  # Default 7 days for students
    
    to_encode.update({"exp": expire, "type": "student"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def _resolve_requested_university_id(request: Request) -> Optional[int]:
    raw = request.headers.get("X-University-ID")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid university context header.",
        )


async def get_current_student(
    token: str = Depends(oauth2_scheme_student),
    db: Session = Depends(get_db)
) -> Student:
    """Get current authenticated student from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        student_number: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if student_number is None or token_type != "student":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    student = db.query(Student).filter(Student.student_number == student_number).first()
    
    if student is None:
        raise credentials_exception

    enforce_active_student(student.is_active)
    
    return student


# Endpoints
@router.post("/register", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def register_student(
    student_data: StudentCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register a new student account
    
    Note: In production, this should be restricted to administrators
    or integrated with university registration system
    """
    tenant_id = _resolve_requested_university_id(request)
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="University context is required. Include X-University-ID header.",
        )

    student_number = sanitize_input(student_data.student_number, max_length=50)
    full_name = sanitize_input(student_data.full_name, max_length=200)
    email = sanitize_input(student_data.email, max_length=200).lower()
    program = sanitize_input(student_data.program, max_length=200)

    if not 1 <= student_data.year_level <= 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="year_level must be between 1 and 7.",
        )

    if student_data.group_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group selection is required for student registration",
        )

    # Validate full ownership chain: group -> department -> university
    group = db.query(StudentGroup).filter(StudentGroup.id == student_data.group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student group not found")

    if group.university_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student group does not belong to this institution",
        )

    if student_data.department_id and student_data.department_id != group.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student group does not match the provided department",
        )

    # Check if student already exists
    existing = db.query(Student).filter(
        (Student.student_number == student_number) |
        (Student.email == email)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student number or email already registered"
        )
    
    # Create new student
    hashed_password = get_password_hash(student_data.password)
    new_student = Student(
        student_number=student_number,
        full_name=full_name,
        email=email,
        hashed_password=hashed_password,
        program=program,
        year_level=student_data.year_level,
        group_id=student_data.group_id,
        department_id=group.department_id,
        university_id=group.university_id,
        created_at=datetime.utcnow().isoformat()
    )
    
    db.add(new_student)
    try:
        db.commit()
        db.refresh(new_student)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student number or email already registered"
        )
    
    return new_student


@router.post("/login", response_model=StudentLoginResponse)
async def login_student(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Student login endpoint
    
    Accepts student_number as username and password
    Returns JWT access token
    """
    tenant_id = _resolve_requested_university_id(request)
    student_number = sanitize_input(form_data.username, max_length=50)
    student = db.query(Student).filter(
        Student.student_number == student_number
    ).first()
    
    if not student or not verify_password(form_data.password, student.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect student number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not student.is_active:
        enforce_active_student(student.is_active)

    if tenant_id is not None:
        dept = None
        group = None
        if student.department_id:
            dept = db.query(Department).filter(Department.id == student.department_id).first()
        if student.group_id:
            group = db.query(StudentGroup).filter(StudentGroup.id == student.group_id).first()
        resolved_uni_id = group.university_id if group else (dept.university_id if dept else None)
        if resolved_uni_id is not None and resolved_uni_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student does not belong to this institution",
            )
    
    # Record last login timestamp for dashboard active-user tracking
    from datetime import datetime, timezone
    student.last_login_at = datetime.now(timezone.utc)
    db.commit()

    # Create access token
    access_token = create_student_access_token(
        data={"sub": student.student_number}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "student": student
    }


@router.get("/me", response_model=StudentResponse)
async def get_current_student_info(
    current_student: Student = Depends(get_current_student)
):
    """
    Get current student's information
    """
    return current_student


@router.get("/timetable", response_model=Dict[str, Any])
async def get_student_timetable(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Get student's personal timetable based on their group assignment
    
    Returns the most recent generated timetable for the student's group
    """
    if not current_student.group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student is not assigned to a group. Please contact your department."
        )
    
    # Get student's group
    group = db.query(StudentGroup).filter(StudentGroup.id == current_student.group_id).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student group not found"
        )
    
    # Find the active timetable for this student's university
    student_uni_id = getattr(current_student, 'university_id', None)
    if student_uni_id is None and group:
        student_uni_id = group.university_id
        
    department = db.query(Department).filter(Department.id == group.department_id).first() if group else None
    school_id = department.school_id if department else None

    timetable = db.query(Timetable).filter(
        Timetable.university_id == student_uni_id,
        Timetable.is_active == True,
        or_(Timetable.school_id == school_id, Timetable.school_id == None) if school_id else True
    ).order_by(Timetable.school_id.isnot(None).desc(), Timetable.id.desc()).first()
    
    if not timetable:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No timetable available for your department yet"
        )
    
    # Get all slots for this student's group
    slots = db.query(TimetableSlot).filter(
        TimetableSlot.timetable_id == timetable.id,
        TimetableSlot.group_id == current_student.group_id
    ).all()
    
    # Format slots with full details
    formatted_slots = []
    for slot in slots:
        course = db.query(Course).filter(Course.id == slot.course_id).first()
        lecturer = db.query(Lecturer).filter(Lecturer.id == slot.lecturer_id).first()
        room = db.query(Room).filter(Room.id == slot.room_id).first()
        
        formatted_slots.append({
            'id': slot.id,
            'day_of_week': slot.day_of_week,
            'start_time': slot.start_time,
            'end_time': slot.end_time,
            'course_code': course.code if course else 'N/A',
            'course_name': course.name if course else 'N/A',
            'lecturer_name': format_person_name(lecturer.full_name) if lecturer else 'N/A',
            'room_number': format_room_name(getattr(room, 'room_number', None) or room.name) if room else 'N/A',
            'building': room.building if room else 'N/A'
        })
    
    # Get department info
    department = db.query(Department).filter(
        Department.id == current_student.department_id
    ).first()
    
    return {
        'student': {
            'student_number': current_student.student_number,
            'full_name': format_person_name(current_student.full_name),
            'program': current_student.program,
            'year_level': current_student.year_level,
            'group_name': format_group_label(group)
        },
        'timetable': {
            'id': timetable.id,
            'name': timetable.name,
            'semester': timetable.semester,
            'academic_year': timetable.year,
            'department': format_department_name(department.name) if department else 'N/A'
        },
        'slots': formatted_slots,
        'total_slots': len(formatted_slots)
    }


@router.get("/courses", response_model=List[Dict[str, Any]])
async def get_student_courses(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Get list of courses for the student's program and year level
    """
    if not current_student.department_id:
        return []
    
    courses = db.query(Course).filter(
        Course.department_id == current_student.department_id,
        Course.level == current_student.year_level
    ).all()
    
    course_list = []
    
    group = db.query(StudentGroup).filter(StudentGroup.id == current_student.group_id).first() if current_student.group_id else None
    student_uni_id = getattr(current_student, 'university_id', group.university_id if group else None)
    department = db.query(Department).filter(Department.id == group.department_id).first() if group else None
    school_id = department.school_id if department else None

    for course in courses:
        # Get lecturer if assigned
        slot = db.query(TimetableSlot).join(Timetable).filter(
            TimetableSlot.course_id == course.id,
            TimetableSlot.group_id == current_student.group_id,
            Timetable.university_id == student_uni_id,
            Timetable.is_active == True,
            or_(Timetable.school_id == school_id, Timetable.school_id == None) if school_id else True
        ).first()
        
        lecturer = None
        if slot:
            lecturer_obj = db.query(Lecturer).filter(Lecturer.id == slot.lecturer_id).first()
            if lecturer_obj:
                lecturer = {
                    'name': format_person_name(lecturer_obj.full_name),
                    'email': lecturer_obj.email
                }
        
        course_list.append({
            'id': course.id,
            'code': course.code,
            'name': course.name,
            'credit_hours': course.credits,
            'course_type': course.course_type,
            'lecturer': lecturer
        })
    
    return course_list


@router.put("/update-password")
async def update_password(
    current_password: str,
    new_password: str,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Update student password
    """
    # Verify current password
    if not verify_password(current_password, current_student.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_student.hashed_password = get_password_hash(new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}


@router.get("/announcements", response_model=List[Dict[str, Any]])
async def get_student_announcements(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """
    Get active announcements for courses the student is enrolled in.
    """
    if not current_student.department_id:
        return []

    # Get course IDs this student is taking
    courses = db.query(Course).filter(
        Course.department_id == current_student.department_id,
        Course.level == current_student.year_level
    ).all()
    course_ids = [c.id for c in courses]

    if not course_ids:
        return []

    # Fetch announcements for these courses, ordered by most recent first
    announcements = db.query(CourseAnnouncement).filter(
        CourseAnnouncement.course_id.in_(course_ids)
    ).order_by(CourseAnnouncement.created_at.desc()).all()

    return [
        {
            "id": a.id,
            "course_id": a.course_id,
            "title": a.title,
            "message": a.message,
            "type": a.announcement_type,
            "target_date": a.target_date.isoformat() if a.target_date else None,
            "created_at": a.created_at.isoformat(),
            "lecturer_name": format_person_name(a.lecturer.full_name) if a.lecturer else "Lecturer",
            "course_code": a.course.code if a.course else ""
        }
        for a in announcements
    ]
