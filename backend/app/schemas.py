from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Literal
from datetime import time, date, datetime
from enum import Enum

class UserRole(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    COORDINATOR = "coordinator"
    HOD = "hod"
    LAB_COORDINATOR = "lab_coordinator"

class RoomType(str, Enum):
    LECTURE_HALL   = "lecture_hall"
    TUTORIAL_ROOM  = "tutorial_room"
    SEMINAR_ROOM   = "seminar_room"
    LAB            = "lab"
    DRAWING_ROOM   = "drawing_room"
    SURVEYING_ROOM = "surveying_room"
    AUDITORIUM     = "auditorium"
    ANY            = "any"

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
    STREAM = "stream"           # Tier 2 — elective stream group (separate lecture schedule)
    LAB_GROUP = "lab_group"     # Tier 3 — lab subgroup (4-13 students)
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
    # Departments that also take this course (Option A: course stays with owning dept).
    # null = not shared (or for GEN dept = shared with ALL depts by default)
    # [1, 5] = explicitly shared only with depts 1 and 5 at this course's level
    shared_with_department_ids: Optional[List[int]] = None

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
    shared_with_department_ids: Optional[List[int]] = None  # set to [] to make dept-private; null = GEN default (all)

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
    email: Optional[str] = None  # Using Optional[str] instead of EmailStr to support missing/internal .local domain emails
    department_id: int
    max_hours_per_week: int = 20
    teaching_preferences: Optional[dict] = None

class LecturerCreate(LecturerBase):
    course_ids: Optional[List[int]] = None

class LecturerUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None  # Using str instead of EmailStr to support internal .local domain emails
    max_hours_per_week: Optional[int] = None
    department_id: Optional[int] = None
    teaching_preferences: Optional[dict] = None
    course_ids: Optional[List[int]] = None



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

class CourseSimple(BaseModel):
    code: str
    name: str

    class Config:
        from_attributes = True

class LecturerAssignmentWithCourse(LecturerAssignment):
    course: CourseSimple

    class Config:
        from_attributes = True

class Lecturer(LecturerBase):
    id: int
    assignments: List[LecturerAssignmentWithCourse] = []
    
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
class TimeWindow(BaseModel):
    day: str
    start_time: str
    end_time: str

class RoomBase(BaseModel):
    name: str
    building: str
    capacity: int
    room_type: str

    # Core teaching equipment — the only three that matter for session delivery
    has_whiteboard: bool = True
    has_chalkboard: bool = False
    has_projector:  bool = True

    # Coordinator controls
    priority_level: int = 5
    coordinator_managed_affinities: Optional[dict] = None
    is_blocked: bool = False

    # Logistics
    availability: Optional[str] = None
    availability_blocks: Optional[List[dict]] = Field(default_factory=list) # e.g. [{"day": "Monday", "start_time": "08:00", "end_time": "17:00"}]
    department_id: Optional[int] = None

class RoomCreate(RoomBase):
    pass

class RoomUpdate(BaseModel):
    name: Optional[str] = None
    building: Optional[str] = None
    capacity: Optional[int] = None
    room_type: Optional[str] = None
    has_whiteboard: Optional[bool] = None
    has_chalkboard: Optional[bool] = None
    has_projector: Optional[bool] = None
    priority_level: Optional[int] = None
    is_blocked: Optional[bool] = None
    coordinator_managed_affinities: Optional[dict] = None
    availability: Optional[str] = None
    availability_blocks: Optional[List[dict]] = None
    department_id: Optional[int] = None

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
    preferred_venues: Optional[dict] = None # { "room_id": priority_1_10 }

class StudentGroupCreate(StudentGroupBase):
    pass

class StudentGroupUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[int] = None
    size: Optional[int] = None
    group_type: Optional[GroupType] = None
    parent_group_id: Optional[int] = None
    display_code: Optional[str] = None
    preferred_venues: Optional[dict] = None

class StudentGroup(StudentGroupBase):
    id: int
    
    class Config:
        from_attributes = True

class StudentGroupBulkUpload(BaseModel):
    groups: List[StudentGroupCreate]

class SubGroupBulkCreate(BaseModel):
    """
    Request body for bulk-generating lab subgroups from a parent group.
    naming_mode:
      - 'alpha'   : A, B, C, D ... (pure letters, up to 26)
      - 'numeric' : {prefix}1, {prefix}2, ... (e.g. A1, A2, B1, B2)
      - 'custom'  : explicit list of names in `custom_names`
    size_per_group: enforced between 4 and 13 for lab groups
    """
    prefix: str = "L"
    count: int
    size_per_group: int
    group_type: GroupType = GroupType.LAB_GROUP
    naming_mode: str = "numeric"  # 'alpha' | 'numeric' | 'custom'
    custom_names: Optional[List[str]] = None  # used when naming_mode == 'custom'

# Group Assignment Schemas (legacy — kept for backward compatibility)
class GroupAssignmentCreate(BaseModel):
    group_id: int
    course_id: int

class GroupAssignment(GroupAssignmentCreate):
    id: int
    
    class Config:
        from_attributes = True

class GroupCourseUpdate(BaseModel):
    course_ids: List[int]


class GroupCourseOption(BaseModel):
    id: int
    code: str
    name: str
    level: int
    department_id: int
    department_name: Optional[str] = None
    department_code: Optional[str] = None
    course_type: str
    shared_with_department_ids: Optional[List[int]] = None
    source_kind: Literal["own", "general", "shared"]
    owner_department_id: int
    owner_department_name: Optional[str] = None
    owner_department_code: Optional[str] = None
    editable: bool = False
    control_scope: Literal["owner", "read_only"] = "read_only"
    read_only_reason: Optional[str] = None
    inherited_from_parent: bool = False
    selected: bool = False
    recommended: bool = False


class GroupCourseMapping(BaseModel):
    group_id: int
    group_name: str
    group_level: int
    group_department_id: int
    group_department_name: Optional[str] = None
    selected_course_ids: List[int]
    recommended_course_ids: List[int]
    available_courses: List[GroupCourseOption]
    note: str


# Course-Group Link Schemas (new — supports shared lectures)
class CourseGroupLinkCreate(BaseModel):
    group_id: int
    is_shared: bool = False
    shared_batch_id: Optional[int] = None
    session_type: str = "lecture"  # 'lecture' | 'practical' | 'tutorial'

class CourseGroupLinkBatchCreate(BaseModel):
    """Assign multiple groups to a course in one call.
    When is_shared=True, all groups get the same shared_batch_id
    and will be scheduled into ONE combined lecture slot.
    """
    group_ids: List[int]
    is_shared: bool = False
    session_type: str = "lecture"

class CourseGroupLink(BaseModel):
    id: int
    course_id: int
    group_id: int
    is_shared: bool
    shared_batch_id: Optional[int] = None
    session_type: str

    class Config:
        from_attributes = True


class CourseEnrollmentGroupOption(BaseModel):
    id: int
    name: str
    display_code: Optional[str] = None
    level: int
    size: int
    department_id: int
    department_name: Optional[str] = None
    department_code: Optional[str] = None
    ownership_kind: Literal["owner", "shared"]
    selected: bool = False


class CourseEnrollmentMapping(BaseModel):
    course_id: int
    course_code: str
    course_name: str
    course_department_id: int
    course_department_name: Optional[str] = None
    lecture_mode: Literal["shared", "separate"]
    selected_group_ids: List[int]
    eligible_groups: List[CourseEnrollmentGroupOption]
    stream_mapping_note: str


class CourseEnrollmentUpdate(BaseModel):
    group_ids: List[int] = Field(default_factory=list)
    lecture_mode: Literal["shared", "separate"] = "separate"

# Timetable Schemas
class TimetableSlotBase(BaseModel):
    course_id: int
    lecturer_id: Optional[int] = None
    room_id: Optional[int] = None
    group_id: int
    day_of_week: int
    start_time: time
    end_time: time
    session_type: str
    # Shared-lecture extras (optional, populated by generator for shared slots)
    shared_group_ids: Optional[List[int]] = None
    combined_size: Optional[int] = None
    shared_batch_id: Optional[int] = None

class TimetableSlot(TimetableSlotBase):
    id: int
    timetable_id: int
    
    class Config:
        from_attributes = True

class GridConfig(BaseModel):
    start_time: str = "07:00"
    end_time: str = "17:00"
    lunch_start: str = "13:00"
    lunch_end: str = "14:00"
    active_days: List[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

class TimetableBase(BaseModel):
    name: str
    semester: str
    year: int
    academic_half: str = "first_half"
    grid_config: Optional[GridConfig] = None

class TimetableCreate(TimetableBase):
    pass

class TimetableUpdate(BaseModel):
    name: Optional[str] = None
    semester: Optional[str] = None
    year: Optional[int] = None
    academic_half: Optional[str] = None
    grid_config: Optional[GridConfig] = None
    is_active: Optional[bool] = None

class Timetable(TimetableBase):
    id: int
    is_active: bool
    generation_metadata: Optional[dict] = None
    
    class Config:
        from_attributes = True

class TimetableWithSlots(Timetable):
    slots: List[TimetableSlot] = []

class SlotAssignmentRequest(BaseModel):
    lecturer_id: Optional[int] = None
    group_id: Optional[int] = None

class ManualSlotCreate(BaseModel):
    course_id: int
    lecturer_id: int
    room_id: Optional[int] = None
    group_id: int
    day_of_week: int
    start_time: time
    end_time: time
    session_type: str = "practical"

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

# Self-Serve Registration Schemas
class TenantRegistrationRequest(BaseModel):
    organization_name: str = Field(..., min_length=2, max_length=200)
    subdomain: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-z0-9-]+$")
    admin_email: EmailStr
    admin_username: str = Field(..., min_length=3, max_length=50)
    admin_full_name: str = Field(..., min_length=2)
    admin_password: str = Field(..., min_length=8)

    @field_validator("admin_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v

class TenantVerificationRequest(BaseModel):
    token: str

class RoomBookingBase(BaseModel):
    room_id: int
    lecturer_id: int
    course_id: int
    booking_date: date
    start_time: time
    end_time: time
    booking_type: str = "test"

class RoomBookingCreate(RoomBookingBase):
    pass

class RoomBookingOut(RoomBookingBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class TestBookingRequest(BaseModel):
    course_id: int
    date: date
    start_time: time
    end_time: time
    room_id: Optional[int] = None
    title: str = "Test"
    message: Optional[str] = None
    capacity: Optional[int] = None


class ExamConstraintSettings(BaseModel):
    preferred_max_papers_per_day: int = 1
    hard_max_papers_per_day: int = 2
    min_gap_hours: int = 24
    allow_same_day_multiple_papers: bool = True


class ExamPeriodBase(BaseModel):
    name: str
    semester: str
    year: int
    start_date: date
    end_date: date
    constraint_settings: Optional[ExamConstraintSettings] = None


class ExamPeriodCreate(ExamPeriodBase):
    pass


class ExamPeriodUpdate(BaseModel):
    name: Optional[str] = None
    semester: Optional[str] = None
    year: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_published: Optional[bool] = None
    is_locked: Optional[bool] = None
    constraint_settings: Optional[ExamConstraintSettings] = None


class ExamSessionWindowBase(BaseModel):
    name: str
    start_time: time
    end_time: time
    allow_weekends: bool = False
    display_order: int = 0
    is_active: bool = True


class ExamSessionWindowCreate(ExamSessionWindowBase):
    pass


class ExamSessionWindowUpdate(BaseModel):
    name: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    allow_weekends: Optional[bool] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class ExamSessionWindow(ExamSessionWindowBase):
    id: int
    exam_period_id: int

    class Config:
        from_attributes = True


class ExamSeatingProfileBase(BaseModel):
    name: str
    description: Optional[str] = None
    capacity_factor: int = 100
    fixed_capacity: Optional[int] = None
    requires_computers: bool = False
    spacing_strategy: str = "standard"
    profile_metadata: Optional[dict] = None
    is_default: bool = False


class ExamSeatingProfileCreate(ExamSeatingProfileBase):
    pass


class ExamSeatingProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    capacity_factor: Optional[int] = None
    fixed_capacity: Optional[int] = None
    requires_computers: Optional[bool] = None
    spacing_strategy: Optional[str] = None
    profile_metadata: Optional[dict] = None
    is_default: Optional[bool] = None


class ExamSeatingProfile(ExamSeatingProfileBase):
    id: int

    class Config:
        from_attributes = True


class ExamPaperBase(BaseModel):
    paper_code: str
    paper_name: str
    course_id: Optional[int] = None
    duration_minutes: int
    candidate_count: Optional[int] = None
    group_ids: List[int]
    preferred_room_type: Optional[str] = None
    preferred_seating_profile_id: Optional[int] = None
    max_rooms: Optional[int] = None
    allow_custom_window: bool = False
    metadata_json: Optional[dict] = None


class ExamPaperCreate(ExamPaperBase):
    pass


class ExamPaperUpdate(BaseModel):
    paper_code: Optional[str] = None
    paper_name: Optional[str] = None
    course_id: Optional[int] = None
    duration_minutes: Optional[int] = None
    candidate_count: Optional[int] = None
    group_ids: Optional[List[int]] = None
    preferred_room_type: Optional[str] = None
    preferred_seating_profile_id: Optional[int] = None
    max_rooms: Optional[int] = None
    allow_custom_window: Optional[bool] = None
    metadata_json: Optional[dict] = None


class ExamPaper(ExamPaperBase):
    id: int
    exam_period_id: int

    class Config:
        from_attributes = True


class ExamPaperCandidateGroup(BaseModel):
    id: int
    name: str
    size: int
    level: int
    department_id: int
    department_name: Optional[str] = None

    class Config:
        from_attributes = True


class ExamPaperCandidate(BaseModel):
    course_id: int
    course_code: str
    course_name: str
    course_level: int
    department_id: int
    department_name: Optional[str] = None
    preferred_room_type: Optional[str] = None
    candidate_count: int
    group_ids: List[int]
    groups: List[ExamPaperCandidateGroup] = []
    ownership_kind: str = "owner"
    can_manage: bool = False
    already_included: bool = False
    existing_paper_id: Optional[int] = None
    existing_paper_code: Optional[str] = None
    existing_paper_name: Optional[str] = None
    existing_duration_minutes: Optional[int] = None
    existing_max_rooms: Optional[int] = None
    existing_preferred_seating_profile_id: Optional[int] = None


class ExamPaperSyncRequest(BaseModel):
    course_ids: List[int] = Field(default_factory=list)
    default_duration_minutes: int = 180
    default_max_rooms: int = 2
    preferred_seating_profile_id: Optional[int] = None
    allow_custom_window: bool = False


class ExamPaperSyncResponse(BaseModel):
    selected_count: int
    created_count: int
    updated_count: int
    removed_count: int


class ExamSlotRoomBase(BaseModel):
    room_id: int
    seating_profile_id: Optional[int] = None
    allocated_capacity: int
    allocated_group_ids: Optional[List[int]] = None
    sequence_no: int = 0


class ExamSlotRoom(ExamSlotRoomBase):
    id: int
    room: Optional[Room] = None
    seating_profile: Optional[ExamSeatingProfile] = None

    class Config:
        from_attributes = True


class ExamSlotBase(BaseModel):
    exam_paper_id: int
    session_window_id: int
    seating_profile_id: Optional[int] = None
    exam_date: date
    start_time: time
    end_time: time
    status: str = "draft"
    total_allocated_capacity: Optional[int] = None
    notes: Optional[str] = None
    generated_score: Optional[int] = None


class ExamSlot(ExamSlotBase):
    id: int
    exam_period_id: int
    paper: Optional[ExamPaper] = None
    session_window: Optional[ExamSessionWindow] = None
    seating_profile: Optional[ExamSeatingProfile] = None
    room_allocations: List[ExamSlotRoom] = []

    class Config:
        from_attributes = True


class ExamPeriod(ExamPeriodBase):
    id: int
    is_published: bool
    is_locked: bool
    generation_metadata: Optional[dict] = None
    session_windows: List[ExamSessionWindow] = []
    papers: List[ExamPaper] = []
    slots: List[ExamSlot] = []

    class Config:
        from_attributes = True


class ExamGenerateRequest(BaseModel):
    replace_existing: bool = True


class ExamPublishRequest(BaseModel):
    lock_after_publish: bool = True

