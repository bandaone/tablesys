from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import time
from enum import Enum

class UserRole(str, Enum):
    COORDINATOR = "coordinator"
    HOD = "hod"

class RoomType(str, Enum):
    LECTURE_HALL = "lecture_hall"
    DRAWING_ROOM = "drawing_room"
    SEMINAR_ROOM = "seminar_room"
    LAB = "lab"
    SURVEYING_ROOM = "surveying_room"
    ANY = "any"

class CourseType(str, Enum):
    DEPARTMENT_SPECIFIC = "department_specific"
    GENERAL = "general"
    MULTI_DEPARTMENT = "multi_department"

class GroupDivisionType(str, Enum):
    FULL_GROUP = "full_group"
    LAB_GROUPS = "lab_groups"
    DRAWING_GROUPS = "drawing_groups"
    TUTORIAL_GROUPS = "tutorial_groups"

class GroupType(str, Enum):
    GENERAL = "general"
    DEPARTMENT = "department"
    LAB_GROUP = "lab_group"
    DRAWING_GROUP = "drawing_group"
    TUTORIAL_GROUP = "tutorial_group"

class RoomCategory(str, Enum):
    LECTURE_HALL_LARGE = "lecture_hall_large"
    LECTURE_HALL_MEDIUM = "lecture_hall_medium"
    LECTURE_HALL_SMALL = "lecture_hall_small"
    DRAWING_ROOM = "drawing_room"
    COMPUTER_LAB = "computer_lab"
    MECHANICAL_LAB = "mechanical_lab"
    ELECTRICAL_LAB = "electrical_lab"
    SURVEYING_ROOM = "surveying_room"
    SEMINAR_ROOM = "seminar_room"
    CONFERENCE_ROOM = "conference_room"

# User Schemas
class UserBase(BaseModel):
    email: Optional[str] = None
    username: str
    full_name: str
    role: UserRole
    department_id: Optional[int] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    department_id: Optional[int] = None
    is_active: Optional[bool] = None

class User(UserBase):
    id: int
    is_active: bool
    
    class Config:
        from_attributes = True

# Department Schemas
class DepartmentBase(BaseModel):
    name: str
    code: str

class DepartmentCreate(DepartmentBase):
    pass

class Department(DepartmentBase):
    id: int
    
    class Config:
        from_attributes = True

# Course Schemas
class CourseBase(BaseModel):
    code: str
    name: str
    department_id: int
    level: int
    credits: int
    lecture_hours: int
    tutorial_hours: int = 0
    practical_hours: int = 0
    preferred_room_type: RoomType = RoomType.ANY
    course_type: CourseType = CourseType.DEPARTMENT_SPECIFIC
    session_configuration: Optional[dict] = None
    group_division_type: GroupDivisionType = GroupDivisionType.FULL_GROUP

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[int] = None
    credits: Optional[int] = None
    lecture_hours: Optional[int] = None
    tutorial_hours: Optional[int] = None
    practical_hours: Optional[int] = None
    preferred_room_type: Optional[RoomType] = None
    course_type: Optional[CourseType] = None
    session_configuration: Optional[dict] = None
    group_division_type: Optional[GroupDivisionType] = None

class Course(CourseBase):
    id: int
    
    class Config:
        from_attributes = True

class CourseBulkUpload(BaseModel):
    courses: List[CourseCreate]

# Lecturer Schemas
class LecturerBase(BaseModel):
    staff_number: str
    full_name: str
    email: EmailStr
    department_id: int
    max_hours_per_week: int = 20
    teaching_preferences: Optional[dict] = None

class LecturerCreate(LecturerBase):
    pass

class LecturerUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    max_hours_per_week: Optional[int] = None

class Lecturer(LecturerBase):
    id: int
    
    class Config:
        from_attributes = True

class LecturerBulkUpload(BaseModel):
    lecturers: List[LecturerCreate]

# Lecturer Assignment Schemas
class LecturerAssignmentCreate(BaseModel):
    lecturer_id: int
    course_id: int
    session_type: Optional[str] = None
    room_preference: Optional[RoomType] = None
    group_division_required: bool = False
    expertise_level: str = "primary"
    notes: Optional[str] = None

class LecturerAssignment(LecturerAssignmentCreate):
    id: int
    
    class Config:
        from_attributes = True

# Lecturer Unavailability Schemas
class LecturerUnavailabilityCreate(BaseModel):
    lecturer_id: int
    day_of_week: int
    start_time: time
    end_time: time

class LecturerUnavailability(LecturerUnavailabilityCreate):
    id: int
    
    class Config:
        from_attributes = True

# Room Schemas
class RoomBase(BaseModel):
    name: str
    building: str
    capacity: int
    room_type: str
    has_projector: bool = True
    has_computers: bool = False
    room_category: Optional[RoomCategory] = None
    department_affinity: Optional[str] = None
    
    furniture_type: Optional[str] = None
    equipment: List[str] = []
    availability: Optional[str] = None
    priority: str = "standard"

class RoomCreate(RoomBase):
    pass

class RoomUpdate(BaseModel):
    building: Optional[str] = None
    capacity: Optional[int] = None
    room_type: Optional[str] = None
    has_projector: Optional[bool] = None
    has_computers: Optional[bool] = None
    room_category: Optional[RoomCategory] = None
    department_affinity: Optional[str] = None

class Room(RoomBase):
    id: int
    
    class Config:
        from_attributes = True

class RoomBulkUpload(BaseModel):
    rooms: List[RoomCreate]

# Student Group Schemas
class StudentGroupBase(BaseModel):
    name: str
    level: int
    department_id: int
    size: int
    group_type: GroupType = GroupType.DEPARTMENT
    parent_group_id: Optional[int] = None
    display_code: Optional[str] = None

class StudentGroupCreate(StudentGroupBase):
    pass

class StudentGroupUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[int] = None
    size: Optional[int] = None
    group_type: Optional[GroupType] = None
    parent_group_id: Optional[int] = None
    display_code: Optional[str] = None

class StudentGroup(StudentGroupBase):
    id: int
    
    class Config:
        from_attributes = True

class StudentGroupBulkUpload(BaseModel):
    groups: List[StudentGroupCreate]

# Group Assignment Schemas
class GroupAssignmentCreate(BaseModel):
    group_id: int
    course_id: int

class GroupAssignment(GroupAssignmentCreate):
    id: int
    
    class Config:
        from_attributes = True

# Timetable Schemas
class TimetableSlotBase(BaseModel):
    course_id: int
    lecturer_id: int
    room_id: int
    group_id: int
    day_of_week: int
    start_time: time
    end_time: time
    session_type: str

class TimetableSlot(TimetableSlotBase):
    id: int
    timetable_id: int
    
    class Config:
        from_attributes = True

class TimetableBase(BaseModel):
    name: str
    semester: str
    year: int
    academic_half: str = "first_half"

class TimetableCreate(TimetableBase):
    pass

class Timetable(TimetableBase):
    id: int
    is_active: bool
    generation_metadata: Optional[dict] = None
    
    class Config:
        from_attributes = True

class TimetableWithSlots(Timetable):
    slots: List[TimetableSlot] = []

# Authentication Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# Timetable Generation Schemas
class GenerationProgress(BaseModel):
    level: int
    status: str
    percentage: float
    message: str

class TimetableGenerationRequest(BaseModel):
    name: str
    semester: str
    year: int
