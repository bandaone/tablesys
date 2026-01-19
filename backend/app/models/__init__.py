from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum, Time, JSON
from sqlalchemy.orm import relationship
import enum
from ..database import Base

class UserRole(str, enum.Enum):
    COORDINATOR = "coordinator"

    HOD = "hod"

class RoomType(str, enum.Enum):
    LECTURE_HALL = "lecture_hall"
    DRAWING_ROOM = "drawing_room"
    SEMINAR_ROOM = "seminar_room"
    LAB = "lab"
    SURVEYING_ROOM = "surveying_room"
    ANY = "any"

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
    LAB_GROUP = "lab_group"
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

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
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
    name = Column(String, unique=True, nullable=False)
    code = Column(String, unique=True, nullable=False)
    
    hods = relationship("User", back_populates="department")
    courses = relationship("Course", back_populates="department")

class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    level = Column(Integer, nullable=False)  # 2, 3, 4, 5
    credits = Column(Integer, nullable=False)
    lecture_hours = Column(Integer, nullable=False)
    tutorial_hours = Column(Integer, default=0)
    practical_hours = Column(Integer, default=0)
    
    # New Fields
    preferred_room_type = Column(Enum(RoomType), default=RoomType.ANY)
    course_type = Column(Enum(CourseType), default=CourseType.DEPARTMENT_SPECIFIC)
    session_configuration = Column(JSON, nullable=True) # { "lecture_sessions": 2, "requires_consecutive": false }
    group_division_type = Column(Enum(GroupDivisionType), default=GroupDivisionType.FULL_GROUP)
    
    department = relationship("Department", back_populates="courses")
    lecturer_assignments = relationship("LecturerAssignment", back_populates="course")
    group_assignments = relationship("GroupAssignment", back_populates="course")

class Lecturer(Base):
    __tablename__ = "lecturers"
    
    id = Column(Integer, primary_key=True, index=True)
    staff_number = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    max_hours_per_week = Column(Integer, default=20)
    
    # New Fields
    teaching_preferences = Column(JSON, nullable=True) # { "preferred_days": [], "avoid_early_morning": false }
    
    department = relationship("Department")
    assignments = relationship("LecturerAssignment", back_populates="lecturer")
    unavailability = relationship("LecturerUnavailability", back_populates="lecturer")

class LecturerAssignment(Base):
    __tablename__ = "lecturer_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    lecturer_id = Column(Integer, ForeignKey("lecturers.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    
    # New Fields
    session_type = Column(String, nullable=True) # lecture, tutorial, practical
    room_preference = Column(Enum(RoomType), nullable=True)
    group_division_required = Column(Boolean, default=False)
    expertise_level = Column(String, default="primary") # primary, assistant
    notes = Column(String, nullable=True)
    
    lecturer = relationship("Lecturer", back_populates="assignments")
    course = relationship("Course", back_populates="lecturer_assignments")

class LecturerUnavailability(Base):
    __tablename__ = "lecturer_unavailability"
    
    id = Column(Integer, primary_key=True, index=True)
    lecturer_id = Column(Integer, ForeignKey("lecturers.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 4=Friday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    lecturer = relationship("Lecturer", back_populates="unavailability")

class Room(Base):
    __tablename__ = "rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    building = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    room_type = Column(String, nullable=False)  # lecture, lab, tutorial
    has_projector = Column(Boolean, default=True)
    has_computers = Column(Boolean, default=False)
    
    # New Fields
    room_category = Column(Enum(RoomCategory), nullable=True)
    department_affinity = Column(String, nullable=True) # "AEN", "general", etc.
    
    # Enhanced Fields for Scheduling & Logistics
    furniture_type = Column(String, nullable=True) # e.g., "Lecture Theatre", "Seminar Room"
    equipment = Column(JSON, default=list) # List of equipment strings
    availability = Column(String, nullable=True) # e.g., "Mon-Fri 07:00-19:00"
    priority = Column(String, default="standard") # "high" or "standard"

class StudentGroup(Base):
    __tablename__ = "student_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    level = Column(Integer, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    size = Column(Integer, nullable=False)
    
    # New Fields
    group_type = Column(Enum(GroupType), default=GroupType.DEPARTMENT)
    parent_group_id = Column(Integer, ForeignKey("student_groups.id"), nullable=True)
    display_code = Column(String, nullable=True) # "GEN1", "AEN", "D1"
    
    parent_group = relationship("StudentGroup", remote_side="StudentGroup.id", backref="subgroups")
    
    department = relationship("Department")
    assignments = relationship("GroupAssignment", back_populates="group")

class GroupAssignment(Base):
    __tablename__ = "group_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("student_groups.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    
    group = relationship("StudentGroup", back_populates="assignments")
    course = relationship("Course", back_populates="group_assignments")

class TimetableSlot(Base):
    __tablename__ = "timetable_slots"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    lecturer_id = Column(Integer, ForeignKey("lecturers.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("student_groups.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 4=Friday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    session_type = Column(String, nullable=False)  # lecture, tutorial, practical
    timetable_id = Column(Integer, ForeignKey("timetables.id"), nullable=False)
    
    course = relationship("Course")
    lecturer = relationship("Lecturer")
    room = relationship("Room")
    group = relationship("StudentGroup")
    timetable = relationship("Timetable", back_populates="slots")

class Timetable(Base):
    __tablename__ = "timetables"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    semester = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    academic_half = Column(String, default="first_half") # "first_half" or "second_half"
    is_active = Column(Boolean, default=False)
    generation_metadata = Column(JSON, nullable=True)  # Stores level-by-level generation info
    
    slots = relationship("TimetableSlot", back_populates="timetable")
