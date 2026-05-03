"""
Student Portal Router - Student Authentication and Timetable Access
Provides endpoints for student login and personal timetable viewing
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
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
    db: Session = Depends(get_db)
):
    """
    Register a new student account
    
    Note: In production, this should be restricted to administrators
    or integrated with university registration system
    """
    # Check if student already exists
    existing = db.query(Student).filter(
        (Student.student_number == student_data.student_number) |
        (Student.email == student_data.email)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student number or email already registered"
        )
    
    # Create new student
    hashed_password = get_password_hash(student_data.password)
    new_student = Student(
        student_number=student_data.student_number,
        full_name=student_data.full_name,
        email=student_data.email,
        hashed_password=hashed_password,
        program=student_data.program,
        year_level=student_data.year_level,
        group_id=student_data.group_id,
        department_id=student_data.department_id,
        created_at=datetime.utcnow().isoformat()
    )
    
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    
    return new_student


@router.post("/login", response_model=StudentLoginResponse)
async def login_student(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Student login endpoint
    
    Accepts student_number as username and password
    Returns JWT access token
    """
    student = db.query(Student).filter(
        Student.student_number == form_data.username
    ).first()
    
    if not student or not verify_password(form_data.password, student.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect student number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not student.is_active:
        enforce_active_student(student.is_active)
    
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
    
    # Find the most recent generated timetable for this department
    timetable = db.query(Timetable).filter(
        Timetable.department_id == current_student.department_id,
        Timetable.is_generated == True
    ).order_by(Timetable.updated_at.desc()).first()
    
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
            'academic_year': timetable.academic_year,
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
    for course in courses:
        # Get lecturer if assigned
        slot = db.query(TimetableSlot).join(Timetable).filter(
            TimetableSlot.course_id == course.id,
            Timetable.department_id == current_student.department_id,
            Timetable.is_generated == True
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
            'credit_hours': course.credit_hours,
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
