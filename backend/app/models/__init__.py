from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum, Time, JSON, Index, DateTime, Date, func
from sqlalchemy.orm import relationship
import enum
from ..database import Base

class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"          # Platform owner — sees all universities
    COORDINATOR = "coordinator"
    HOD = "hod"
    LAB_COORDINATOR = "lab_coordinator"

class RoomType(str, enum.Enum):
    LECTURE_HALL   = "lecture_hall"
    TUTORIAL_ROOM  = "tutorial_room"
    SEMINAR_ROOM   = "seminar_room"
    LAB            = "lab"
    DRAWING_ROOM   = "drawing_room"
    SURVEYING_ROOM = "surveying_room"
    AUDITORIUM     = "auditorium"
    ANY            = "any"

class CourseType(str, enum.Enum):
    DEPARTMENT_SPECIFIC = "department_specific"
    GENERAL = "general"
    MULTI_DEPARTMENT = "multi_department"

class GroupDivisionType(str, enum.Enum):
    FULL_GROUP = "full_group"
    LAB_GROUPS = "lab_groups"
    DRAWING_GROUPS = "drawing_groups"
    TUTORIAL_GROUPS = "tutorial_groups"

class GroupType(str, enum.Enum):
    GENERAL = "general"
    DEPARTMENT = "department"
    STREAM = "stream"          # Tier 2 — elective stream (has lecture timetable)
    LAB_GROUP = "lab_group"    # Tier 3 — lab subgroup (4-13 students)
    DRAWING_GROUP = "drawing_group"
    TUTORIAL_GROUP = "tutorial_group"

class RoomCategory(str, enum.Enum):
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

class University(Base):
    __tablename__ = "universities"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, unique=True, nullable=False)
    short_name    = Column(String, nullable=True)                  # e.g. "UNI"
    domain        = Column(String, unique=True, nullable=False)    # e.g. "uni.edu"
    timezone      = Column(String, default="Africa/Harare")
    is_active     = Column(Boolean, default=True)
    registered_at = Column(DateTime(timezone=True), nullable=True)

    # ── Branding ─────────────────────────────────────────────────────────
    logo_url        = Column(String, nullable=True)                # URL or path to logo image
    primary_color   = Column(String, default="#1976d2")            # Hex — main brand colour
    secondary_color = Column(String, default="#9c27b0")            # Hex — accent colour
    tagline         = Column(String, nullable=True)                # e.g. "Excellence in Education"

    # ── Plan / Licensing ─────────────────────────────────────────────────
    plan_tier = Column(String, default="free")                     # free | pro | enterprise
    max_users = Column(Integer, default=50)

class AcademicCalendar(Base):
    __tablename__ = "academic_calendars"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    days_of_week = Column(JSON, nullable=False) # e.g. ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    start_time = Column(Time, nullable=False)   # e.g. 07:00
    end_time = Column(Time, nullable=False)     # e.g. 18:00
    slot_duration_minutes = Column(Integer, default=60)
    is_default = Column(Boolean, default=False)
    
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    
    department = relationship("Department", back_populates="hods")

class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=True, index=True)
    name = Column(String, unique=True, nullable=False)
    code = Column(String, unique=True, nullable=False)
    
    hods = relationship("User", back_populates="department")
    courses = relationship("Course", back_populates="department")

class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    level = Column(Integer, nullable=False, index=True)  # 2, 3, 4, 5
    credits = Column(Integer, nullable=False)
    lecture_hours = Column(Integer, nullable=False)
    tutorial_hours = Column(Integer, default=0)
    practical_hours = Column(Integer, default=0)
    
    # New Fields
    preferred_room_type = Column(Enum(RoomType), default=RoomType.ANY)
    course_type = Column(Enum(CourseType), default=CourseType.DEPARTMENT_SPECIFIC)
    session_configuration = Column(JSON, nullable=True) # { "lecture_sessions": 2, "requires_consecutive": false }
    group_division_type = Column(Enum(GroupDivisionType), default=GroupDivisionType.FULL_GROUP)
    
    # Sharing: which other departments also take this course (level-strict)
    # GEN dept + null = universally shared with all depts (e.g. MAT 3110)
    # GEN dept + [1,5] = GEN course targeted only at EEE + MEC
    # EEE dept + [6] = EEE-owned but GEN Year2 groups attend (e.g. EEE 2019)
    # any dept + [2,5] = cross-dept shared (e.g. CEE course with MEC)
    shared_with_department_ids = Column(JSON, nullable=True)

    department = relationship("Department", back_populates="courses")
    lecturer_assignments = relationship("LecturerAssignment", back_populates="course")
    group_assignments = relationship("GroupAssignment", back_populates="course")
    group_links = relationship("CourseGroupLink", back_populates="course", cascade="all, delete-orphan")
    
    # Composite index for common query pattern: filter by department AND level
    __table_args__ = (
        Index('ix_course_dept_level', 'department_id', 'level'),
    )

class Lecturer(Base):
    __tablename__ = "lecturers"
    
    id = Column(Integer, primary_key=True, index=True)
    staff_number = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    max_hours_per_week = Column(Integer, default=20)
    
    # New Fields
    teaching_preferences = Column(JSON, nullable=True) # { "preferred_days": [], "avoid_early_morning": false }
    
    department = relationship("Department")
    assignments = relationship("LecturerAssignment", back_populates="lecturer")
    unavailability = relationship("LecturerUnavailability", back_populates="lecturer")

class LecturerAssignment(Base):
    __tablename__ = "lecturer_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    lecturer_id = Column(Integer, ForeignKey("lecturers.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    
    # New Fields
    session_type = Column(String, nullable=True) # lecture, tutorial, practical
    room_preference = Column(Enum(RoomType), nullable=True)
    group_division_required = Column(Boolean, default=False)
    expertise_level = Column(String, default="primary") # primary, assistant
    notes = Column(String, nullable=True)
    
    lecturer = relationship("Lecturer", back_populates="assignments")
    course = relationship("Course", back_populates="lecturer_assignments")
    
    # Composite index for unique constraint check
    __table_args__ = (
        Index('ix_assignment_lecturer_course', 'lecturer_id', 'course_id'),
    )

class LecturerUnavailability(Base):
    __tablename__ = "lecturer_unavailability"
    
    id = Column(Integer, primary_key=True, index=True)
    lecturer_id = Column(Integer, ForeignKey("lecturers.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 4=Friday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    lecturer = relationship("Lecturer", back_populates="unavailability")

class Room(Base):
    __tablename__ = "rooms"

    id           = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False, index=True)
    name         = Column(String, unique=True, nullable=False, index=True)
    building     = Column(String, nullable=False)
    capacity     = Column(Integer, nullable=False)
    room_type    = Column(String, nullable=False)  # maps to RoomType enum values

    # ── Core teaching equipment ──────────────────────────────────────────
    # These three flags are the only equipment indicators that matter for
    # determining whether a session can be delivered in this room.
    has_whiteboard = Column(Boolean, default=True)   # marker board / whiteboard
    has_chalkboard = Column(Boolean, default=False)  # traditional chalkboard
    has_projector  = Column(Boolean, default=True)   # screen + projector / smart board

    # ── Coordinator scheduling controls ─────────────────────────────────
    priority_level = Column(Integer, default=5)       # 1 (lowest) – 10 (highest)
    is_blocked     = Column(Boolean, default=False)   # hard exclude from generation
    # e.g. { "level_2": 0.9, "level_5": 0.3, "dept_CEE": 0.8 }
    coordinator_managed_affinities = Column(JSON, nullable=True)

    # ── Logistics ────────────────────────────────────────────────────────
    # Structured availability blocks: [{"day": "Monday", "start_time": "08:00", "end_time": "17:00"}]
    availability_blocks = Column(JSON, default=list)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)

    # ── Relationships ────────────────────────────────────────────────────
    department = relationship("Department")

class StudentGroup(Base):
    __tablename__ = "student_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False, index=True)
    name = Column(String, unique=True, nullable=False)
    level = Column(Integer, nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    size = Column(Integer, nullable=False)
    
    # New Fields
    group_type = Column(Enum(GroupType), default=GroupType.DEPARTMENT)
    parent_group_id = Column(Integer, ForeignKey("student_groups.id"), nullable=True, index=True)
    display_code = Column(String, nullable=True) # "GEN1", "AEN", "D1"
    preferred_venues = Column(JSON, nullable=True) # e.g., { "room_id_1": 10, "room_id_2": 8 }
    
    parent_group = relationship("StudentGroup", remote_side="StudentGroup.id", backref="subgroups")
    
    department = relationship("Department")
    assignments = relationship("GroupAssignment", back_populates="group")

class GroupAssignment(Base):
    __tablename__ = "group_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("student_groups.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    
    group = relationship("StudentGroup", back_populates="assignments")
    course = relationship("Course", back_populates="group_assignments")


class CourseGroupLink(Base):
    """
    Replaces/extends GroupAssignment with shared-lecture support.

    is_shared=False  → this group gets its own independent slot (legacy behaviour).
    is_shared=True   → this group shares ONE lecture slot with other groups
                       that have the same course_id + shared_batch_id.

    shared_batch_id  → integer key grouping all groups that attend the same
                       combined lecture.  NULL when is_shared=False.
    """
    __tablename__ = "course_group_links"

    id               = Column(Integer, primary_key=True, index=True)
    course_id        = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    group_id         = Column(Integer, ForeignKey("student_groups.id"), nullable=False, index=True)
    is_shared        = Column(Boolean, default=False, nullable=False)
    shared_batch_id  = Column(Integer, nullable=True, index=True)
    # 'lecture' | 'practical' | 'tutorial' — which session type this link covers
    session_type     = Column(String, default="lecture", nullable=False)

    course = relationship("Course", back_populates="group_links")
    group  = relationship("StudentGroup")

    __table_args__ = (
        Index("ix_cgl_course_batch", "course_id", "shared_batch_id"),
        Index("ix_cgl_course_group", "course_id", "group_id"),
    )

class TimetableSlot(Base):
    __tablename__ = "timetable_slots"
    
    id           = Column(Integer, primary_key=True, index=True)
    course_id    = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    lecturer_id  = Column(Integer, ForeignKey("lecturers.id"), nullable=True, index=True)
    room_id      = Column(Integer, ForeignKey("rooms.id"), nullable=True, index=True)
    group_id     = Column(Integer, ForeignKey("student_groups.id"), nullable=False, index=True)
    day_of_week  = Column(Integer, nullable=False, index=True)  # 0=Monday, 4=Friday
    start_time   = Column(Time, nullable=False)
    end_time     = Column(Time, nullable=False)
    session_type = Column(String, nullable=False)  # lecture, tutorial, practical
    timetable_id = Column(Integer, ForeignKey("timetables.id"), nullable=False, index=True)

    # ── Shared-lecture fields ────────────────────────────────────────────────
    # When a slot covers multiple groups (shared lecture), group_id holds the
    # primary/representative group; shared_group_ids holds the rest as a JSON
    # list of integers.  combined_size = sum of all attending groups' sizes.
    shared_group_ids = Column(JSON, nullable=True)   # e.g. [12, 17] (additional group IDs)
    combined_size    = Column(Integer, nullable=True) # total headcount for room sizing
    shared_batch_id  = Column(Integer, nullable=True, index=True)  # links back to CourseGroupLink batch

    course    = relationship("Course")
    lecturer  = relationship("Lecturer")
    room      = relationship("Room")
    group     = relationship("StudentGroup")
    timetable = relationship("Timetable", back_populates="slots")
    
    __table_args__ = (
        Index('ix_slot_timetable_day', 'timetable_id', 'day_of_week'),
        Index('ix_slot_course_time',   'course_id',    'day_of_week'),
        Index('ix_slot_batch',         'timetable_id', 'shared_batch_id'),
    )

class Timetable(Base):
    __tablename__ = "timetables"
    
    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    semester = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    academic_half = Column(String, default="first_half") # "first_half" or "second_half"
    academic_calendar_id = Column(Integer, ForeignKey("academic_calendars.id"), nullable=True)
    is_active = Column(Boolean, default=False)
    generation_metadata = Column(JSON, nullable=True)  # Stores level-by-level generation info

    academic_calendar = relationship("AcademicCalendar")
    slots = relationship("TimetableSlot", back_populates="timetable", cascade="all, delete-orphan")
    versions = relationship("TimetableVersion", back_populates="timetable", cascade="all, delete-orphan")


class TimetableVersion(Base):
    __tablename__ = "timetable_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    timetable_id = Column(Integer, ForeignKey("timetables.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    description = Column(String, nullable=True)
    snapshot_data = Column(JSON, nullable=False)  # Diff-based payload (or full baseline for first version)
    created_at = Column(DateTime(timezone=True), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    timetable = relationship("Timetable", back_populates="versions")
    created_by = relationship("User")
    
    __table_args__ = (
        Index('ix_timetable_versions_timetable_id', 'timetable_id'),
    )


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    type = Column(String, default="info")  # "info", "success", "warning", "error"
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    action_link = Column(String, nullable=True)  # Optional link for "View" action
    
    user = relationship("User")
    
    __table_args__ = (
        Index('ix_notifications_user_id', 'user_id'),
        Index('ix_notifications_is_read', 'is_read'),
    )


class Student(Base):
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True, index=True)
    student_number = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    program = Column(String, nullable=False)  # e.g., "Mechanical Engineering"
    year_level = Column(Integer, nullable=False)  # 1, 2, 3, 4, 5
    group_id = Column(Integer, ForeignKey("student_groups.id"), nullable=True)  # Optional: specific group assignment
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    group = relationship("StudentGroup", back_populates="students")
    department = relationship("Department")
    
    __table_args__ = (
        # Indexes are already created via index=True on column definitions above
        # Index('ix_students_student_number', 'student_number'),  # Already indexed
        # Index('ix_students_email', 'email'),  # Already indexed
        # Index('ix_students_group_id', 'group_id'),  # Already indexed
    )


# Update StudentGroup to include students relationship
StudentGroup.students = relationship("Student", back_populates="group")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null for system actions
    user_email = Column(String, nullable=True)  # Store email for reference
    action = Column(String, nullable=False)  # CREATE, UPDATE, DELETE, LOGIN, LOGOUT, GENERATE, etc.
    entity_type = Column(String, nullable=False)  # course, timetable, user, etc.
    entity_id = Column(Integer, nullable=True)  # ID of the affected entity
    entity_name = Column(String, nullable=True)  # Name/identifier of the entity
    changes = Column(JSON, nullable=True)  # JSON of what changed (before/after values)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="success")  # success, failure, error
    error_message = Column(String, nullable=True)
    
    # Relationships
    user = relationship("User")
    
    __table_args__ = (
        Index('ix_audit_logs_user_id', 'user_id'),
        Index('ix_audit_logs_action', 'action'),
        Index('ix_audit_logs_entity_type', 'entity_type'),
        Index('ix_audit_logs_timestamp', 'timestamp'),
    )




class PendingRegistration(Base):
    """
    Holds registration data temporarily until email verification completes.

    Security rationale: instead of embedding hashed passwords into JWT tokens
    (which appear in email URLs, browser history, and proxy logs), we store
    all sensitive data server-side and reference it with a short-lived opaque
    token.
    """
    __tablename__ = "pending_registrations"

    id              = Column(Integer, primary_key=True, index=True)
    token           = Column(String, unique=True, nullable=False, index=True)  # Opaque UUID
    org_name        = Column(String, nullable=False)
    subdomain       = Column(String, nullable=False)
    admin_email     = Column(String, nullable=False)
    admin_username  = Column(String, nullable=False)
    admin_full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    status          = Column(String, default="pending")  # pending | verified | expired
    ip_address      = Column(String, nullable=True)
    created_at      = Column(DateTime(timezone=True), nullable=False)
    expires_at      = Column(DateTime(timezone=True), nullable=False)


class CourseAnnouncement(Base):
    __tablename__ = "course_announcements"
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    lecturer_id = Column(Integer, ForeignKey("lecturers.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    
    # "general", "test_scheduled", "class_cancelled"
    announcement_type = Column(String, default="general") 
    
    # Optional targeted date (e.g., the date of the test or cancellation)
    target_date = Column(DateTime(timezone=True), nullable=True) 
    venue = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    course = relationship("Course")
    lecturer = relationship("Lecturer")


class RoomBooking(Base):
    __tablename__ = "room_bookings"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)
    lecturer_id = Column(Integer, ForeignKey("lecturers.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    booking_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    booking_type = Column(String, default="test")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    room = relationship("Room")
    lecturer = relationship("Lecturer")
    course = relationship("Course")


class ExamPeriod(Base):
    __tablename__ = "exam_periods"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    semester = Column(String, nullable=False)
    year = Column(Integer, nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    is_published = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    constraint_settings = Column(JSON, nullable=True)
    generation_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_by = relationship("User")
    session_windows = relationship(
        "ExamSessionWindow",
        back_populates="exam_period",
        cascade="all, delete-orphan",
        order_by="ExamSessionWindow.display_order.asc()",
    )
    papers = relationship(
        "ExamPaper",
        back_populates="exam_period",
        cascade="all, delete-orphan",
    )
    slots = relationship(
        "ExamSlot",
        back_populates="exam_period",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_exam_period_university_year", "university_id", "year"),
    )


class ExamSessionWindow(Base):
    __tablename__ = "exam_session_windows"

    id = Column(Integer, primary_key=True, index=True)
    exam_period_id = Column(Integer, ForeignKey("exam_periods.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    allow_weekends = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    exam_period = relationship("ExamPeriod", back_populates="session_windows")
    slots = relationship("ExamSlot", back_populates="session_window")

    __table_args__ = (
        Index("ix_exam_session_window_period_order", "exam_period_id", "display_order"),
    )


class ExamSeatingProfile(Base):
    __tablename__ = "exam_seating_profiles"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    capacity_factor = Column(Integer, nullable=False, default=100)  # stored as percentage
    fixed_capacity = Column(Integer, nullable=True)
    requires_computers = Column(Boolean, default=False)
    spacing_strategy = Column(String, default="standard")
    profile_metadata = Column(JSON, nullable=True)
    is_default = Column(Boolean, default=False)

    slot_defaults = relationship("ExamSlot", back_populates="seating_profile")
    room_allocations = relationship("ExamSlotRoom", back_populates="seating_profile")

    __table_args__ = (
        Index("ix_exam_seating_profile_university_name", "university_id", "name"),
    )


class ExamPaper(Base):
    __tablename__ = "exam_papers"

    id = Column(Integer, primary_key=True, index=True)
    exam_period_id = Column(Integer, ForeignKey("exam_periods.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    paper_code = Column(String, nullable=False, index=True)
    paper_name = Column(String, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    candidate_count = Column(Integer, nullable=True)
    group_ids = Column(JSON, nullable=False)
    preferred_room_type = Column(String, nullable=True)
    preferred_seating_profile_id = Column(Integer, ForeignKey("exam_seating_profiles.id"), nullable=True)
    max_rooms = Column(Integer, nullable=True)
    allow_custom_window = Column(Boolean, default=False)
    metadata_json = Column(JSON, nullable=True)

    exam_period = relationship("ExamPeriod", back_populates="papers")
    course = relationship("Course")
    preferred_seating_profile = relationship("ExamSeatingProfile")
    slots = relationship("ExamSlot", back_populates="paper")

    __table_args__ = (
        Index("ix_exam_paper_period_code", "exam_period_id", "paper_code"),
    )


class ExamSlot(Base):
    __tablename__ = "exam_slots"

    id = Column(Integer, primary_key=True, index=True)
    exam_period_id = Column(Integer, ForeignKey("exam_periods.id"), nullable=False, index=True)
    exam_paper_id = Column(Integer, ForeignKey("exam_papers.id"), nullable=False, index=True)
    session_window_id = Column(Integer, ForeignKey("exam_session_windows.id"), nullable=False, index=True)
    seating_profile_id = Column(Integer, ForeignKey("exam_seating_profiles.id"), nullable=True, index=True)
    exam_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(String, default="draft")
    total_allocated_capacity = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
    generated_score = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)

    exam_period = relationship("ExamPeriod", back_populates="slots")
    paper = relationship("ExamPaper", back_populates="slots")
    session_window = relationship("ExamSessionWindow", back_populates="slots")
    seating_profile = relationship("ExamSeatingProfile", back_populates="slot_defaults")
    room_allocations = relationship(
        "ExamSlotRoom",
        back_populates="exam_slot",
        cascade="all, delete-orphan",
        order_by="ExamSlotRoom.sequence_no.asc()",
    )

    __table_args__ = (
        Index("ix_exam_slot_period_date", "exam_period_id", "exam_date"),
        Index("ix_exam_slot_paper_date", "exam_paper_id", "exam_date"),
    )


class ExamSlotRoom(Base):
    __tablename__ = "exam_slot_rooms"

    id = Column(Integer, primary_key=True, index=True)
    exam_slot_id = Column(Integer, ForeignKey("exam_slots.id"), nullable=False, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)
    seating_profile_id = Column(Integer, ForeignKey("exam_seating_profiles.id"), nullable=True, index=True)
    allocated_capacity = Column(Integer, nullable=False)
    allocated_group_ids = Column(JSON, nullable=True)
    sequence_no = Column(Integer, default=0)

    exam_slot = relationship("ExamSlot", back_populates="room_allocations")
    room = relationship("Room")
    seating_profile = relationship("ExamSeatingProfile", back_populates="room_allocations")

    __table_args__ = (
        Index("ix_exam_slot_room_slot_room", "exam_slot_id", "room_id"),
    )
