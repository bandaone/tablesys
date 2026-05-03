"""
Lecturer Portal Router - Lecturer Authentication and Timetable Access
Provides endpoints for lecturer login and personal timetable viewing
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from jose import JWTError, jwt
from prometheus_client import Counter

from pydantic import BaseModel
from ..database import get_db
from ..models import Lecturer, Timetable, TimetableSlot, Course, Room, LecturerAssignment, CourseAnnouncement
from ..config import settings

router = APIRouter(prefix="/api/v1/lecturer", tags=["lecturer-portal"])

# OAuth2 scheme for lecturers
oauth2_scheme_lecturer = OAuth2PasswordBearer(tokenUrl="/api/v1/lecturer/login")

# Metrics
_LECTURER_LOGIN_COUNT = Counter('lecturer_logins_total', 'Total lecturer login attempts')
_LECTURER_TIMETABLE_VIEWS = Counter('lecturer_timetable_views_total', 'Total lecturer timetable views')

DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def _time_to_minutes(value) -> int:
    """Convert a time value (string 'HH:MM' or datetime.time object) to minutes since midnight."""
    if hasattr(value, 'hour'):
        # datetime.time object
        return value.hour * 60 + value.minute
    # string "HH:MM"
    hours, minutes = map(int, str(value).split(':')[:2])
    return hours * 60 + minutes


def _format_time(value) -> str:
    """Convert a time value to 'HH:MM' string."""
    if hasattr(value, 'strftime'):
        return value.strftime('%H:%M')
    return str(value)[:5]


def _day_int_to_name(day_int) -> str:
    """Convert integer day (0=Monday) to day name string."""
    try:
        return DAY_ORDER[int(day_int)]
    except (IndexError, ValueError, TypeError):
        return str(day_int)


def _session_duration_minutes(slot: TimetableSlot) -> int:
    try:
        return _time_to_minutes(slot.end_time) - _time_to_minutes(slot.start_time)
    except Exception:
        return 0


def _day_index(day_name: str) -> int:
    try:
        return DAY_ORDER.index(day_name)
    except ValueError:
        return 999


def _minutes_until_session(day_name: str, start_time) -> int:
    now = datetime.now()
    current_day = now.strftime('%A')
    current_index = _day_index(current_day)
    session_index = _day_index(day_name)
    now_minutes = now.hour * 60 + now.minute
    start_minutes = _time_to_minutes(start_time)

    day_delta = session_index - current_index
    if day_delta < 0 or (day_delta == 0 and start_minutes < now_minutes):
        day_delta += 7

    return day_delta * 24 * 60 + (start_minutes - now_minutes if day_delta == 0 else start_minutes - now_minutes)


def create_lecturer_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire, "type": "lecturer"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_lecturer(
    token: str = Depends(oauth2_scheme_lecturer), db: Session = Depends(get_db)
) -> Lecturer:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        staff_number: str = payload.get("sub")
        token_type: str = payload.get("type")

        if staff_number is None or token_type != "lecturer":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    lecturer = db.query(Lecturer).filter(Lecturer.staff_number == staff_number).first()
    if lecturer is None:
        raise credentials_exception

    return lecturer


@router.post("/login", response_model=Dict[str, Any])
async def login_lecturer(payload: Dict[str, str] = Body(...), db: Session = Depends(get_db)):
    """
    Lecturer login endpoint
    Request body: { "staff_number": "..." }
    """
    staff_number = payload.get("staff_number")
    if not staff_number:
        raise HTTPException(status_code=400, detail="staff_number is required")

    lecturer = db.query(Lecturer).filter(Lecturer.staff_number == staff_number).first()
    if not lecturer:
        _LECTURER_LOGIN_COUNT.inc()
        raise HTTPException(status_code=404, detail="Staff number not recognised. Contact your coordinator.")

    access_token = create_lecturer_access_token({"sub": lecturer.staff_number, "lecturer_id": lecturer.id})
    _LECTURER_LOGIN_COUNT.inc()

    return {"access_token": access_token, "token_type": "bearer", "lecturer": {
        "id": lecturer.id,
        "staff_number": lecturer.staff_number,
        "full_name": lecturer.full_name,
        "email": lecturer.email,
        "department_id": lecturer.department_id
    }}


@router.get("/me", response_model=Dict[str, Any])
async def get_lecturer_info(current_lecturer: Lecturer = Depends(get_current_lecturer)):
    return {
        "id": current_lecturer.id,
        "staff_number": current_lecturer.staff_number,
        "full_name": current_lecturer.full_name,
        "email": current_lecturer.email,
        "department_id": current_lecturer.department_id,
        "max_hours_per_week": current_lecturer.max_hours_per_week,
    }


@router.get("/timetable", response_model=Dict[str, Any])
async def get_lecturer_timetable(
    current_lecturer: Lecturer = Depends(get_current_lecturer), db: Session = Depends(get_db)
):
    """Return timetable sessions assigned to the authenticated lecturer"""
    # Find most recent generated timetable for the lecturer's department (fallback)
    timetable = db.query(Timetable).filter(Timetable.is_active == True).first()
    # Get all slots where lecturer_id == current_lecturer.id
    slots = db.query(TimetableSlot).filter(TimetableSlot.lecturer_id == current_lecturer.id).all()

    _LECTURER_TIMETABLE_VIEWS.inc()
    formatted = []
    for slot in slots:
        course = db.query(Course).filter(Course.id == slot.course_id).first()
        room = db.query(Room).filter(Room.id == slot.room_id).first()
        formatted.append({
            "id": slot.id,
            "course_code": course.code if course else 'N/A',
            "course_name": course.name if course else 'N/A',
            "group_id": slot.group_id,
            "session_type": slot.session_type,
            "day_of_week": _day_int_to_name(slot.day_of_week),
            "start_time": _format_time(slot.start_time),
            "end_time": _format_time(slot.end_time),
            "room_number": room.room_number if room and hasattr(room, 'room_number') else (room.name if room else 'N/A'),
            "building": room.building if room else 'N/A'
        })

    return {
        "profile": {
            "lecturer_id": current_lecturer.id,
            "staff_number": current_lecturer.staff_number,
            "full_name": current_lecturer.full_name,
            "department_id": current_lecturer.department_id,
        },
        "timetable": {
            "id": timetable.id if timetable else None,
            "name": timetable.name if timetable else None,
            "semester": timetable.semester if timetable else None,
            "year": getattr(timetable, 'academic_year', None) if timetable else None,
        },
        "sessions": formatted,
        "total_sessions": len(formatted),
    }


@router.get("/courses", response_model=List[Dict[str, Any]])
async def get_lecturer_courses(current_lecturer: Lecturer = Depends(get_current_lecturer), db: Session = Depends(get_db)):
    assignments = db.query(LecturerAssignment).filter(LecturerAssignment.lecturer_id == current_lecturer.id).all()
    courses = []
    for a in assignments:
        c = db.query(Course).filter(Course.id == a.course_id).first()
        if not c:
            continue
        courses.append({
            "id": c.id,
            "code": c.code,
            "name": c.name,
            "level": c.level,
            "assignment": {
                "session_type": a.session_type,
                "room_preference": a.room_preference,
                "expertise_level": a.expertise_level,
            }
        })
    return courses


@router.get("/dashboard", response_model=Dict[str, Any])
async def get_lecturer_dashboard(current_lecturer: Lecturer = Depends(get_current_lecturer), db: Session = Depends(get_db)):
    # Summary metrics
    total_courses = db.query(LecturerAssignment).filter(LecturerAssignment.lecturer_id == current_lecturer.id).count()
    total_sessions = db.query(TimetableSlot).filter(TimetableSlot.lecturer_id == current_lecturer.id).count()
    # Hours this week (rough estimate: sum of durations)
    sessions = db.query(TimetableSlot).filter(TimetableSlot.lecturer_id == current_lecturer.id).all()
    session_rows: List[Tuple[TimetableSlot, int]] = [(slot, _session_duration_minutes(slot)) for slot in sessions]
    total_minutes = sum(duration for _, duration in session_rows)

    today_name = datetime.now().strftime('%A')
    daily_minutes = sum(
        duration
        for slot, duration in session_rows
        if _day_int_to_name(slot.day_of_week) == today_name
    )
    daily_sessions = sum(1 for slot, _ in session_rows if _day_int_to_name(slot.day_of_week) == today_name)

    total_hours = round(total_minutes / 60, 2)
    daily_hours = round(daily_minutes / 60, 2)
    max_hours = current_lecturer.max_hours_per_week or 0
    weekly_load_percent = round((total_hours / max_hours) * 100, 1) if max_hours > 0 else None

    next_session = None
    if sessions:
        now = datetime.now()
        current_index = _day_index(now.strftime('%A'))
        now_minutes = now.hour * 60 + now.minute

        def sort_key(slot: TimetableSlot):
            slot_day_name = _day_int_to_name(slot.day_of_week)
            slot_index = _day_index(slot_day_name)
            start_minutes = _time_to_minutes(slot.start_time)
            day_delta = slot_index - current_index
            if day_delta < 0 or (day_delta == 0 and start_minutes < now_minutes):
                day_delta += 7
            return (day_delta, start_minutes)

        sorted_sessions = sorted(sessions, key=sort_key)
        upcoming_slot = sorted_sessions[0]
        course = db.query(Course).filter(Course.id == upcoming_slot.course_id).first()
        next_session = {
            "id": upcoming_slot.id,
            "day": _day_int_to_name(upcoming_slot.day_of_week),
            "start_time": _format_time(upcoming_slot.start_time),
            "end_time": _format_time(upcoming_slot.end_time),
            "course_id": upcoming_slot.course_id,
            "course_code": course.code if course else None,
            "course_name": course.name if course else None,
            "room_id": upcoming_slot.room_id,
            "minutes_until_start": max(_minutes_until_session(_day_int_to_name(upcoming_slot.day_of_week), upcoming_slot.start_time), 0),
        }

    course_workload = []
    courses_by_id = {c.id: c for c in db.query(Course).filter(Course.id.in_([a.course_id for a in db.query(LecturerAssignment).filter(LecturerAssignment.lecturer_id == current_lecturer.id).all()])).all()} if total_courses else {}
    for course_id, course in courses_by_id.items():
        course_sessions = [slot for slot, _ in session_rows if slot.course_id == course_id]
        course_minutes = sum(_session_duration_minutes(slot) for slot in course_sessions)
        course_workload.append({
            "course_id": course.id,
            "course_code": course.code,
            "course_name": course.name,
            "sessions": len(course_sessions),
            "hours": round(course_minutes / 60, 2),
        })
    course_workload.sort(key=lambda item: item["course_code"] or "")

    return {
        "profile": {
            "lecturer_id": current_lecturer.id,
            "staff_number": current_lecturer.staff_number,
            "full_name": current_lecturer.full_name,
            "max_hours_per_week": current_lecturer.max_hours_per_week,
        },
        "summary": {
            "total_courses": total_courses,
            "total_sessions": total_sessions,
            "daily_session_count": daily_sessions,
            "daily_teaching_hours": daily_hours,
            "weekly_load_hours": total_hours,
            "max_hours_per_week": max_hours,
            "weekly_load_percent": weekly_load_percent,
            "next_session": next_session,
        }
        ,
        "course_workload": course_workload,
    }

# ── Announcements Schemas & Endpoints ────────────────────────────────────

class AnnouncementCreate(BaseModel):
    course_id: int
    title: str
    message: str
    announcement_type: str = "general"
    target_date: str | None = None
    venue: str | None = None


@router.post("/announcements", response_model=Dict[str, Any])
async def create_announcement(
    req: AnnouncementCreate,
    current_lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    # Verify course belongs to lecturer via assignments
    assignment = db.query(LecturerAssignment).filter(
        LecturerAssignment.lecturer_id == current_lecturer.id,
        LecturerAssignment.course_id == req.course_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="You are not assigned to this course.")

    # Parse targeted date if provided
    parsed_date = None
    if req.target_date:
        try:
            from dateutil.parser import parse
            parsed_date = parse(req.target_date)
        except Exception:
            pass

    announcement = CourseAnnouncement(
        course_id=req.course_id,
        lecturer_id=current_lecturer.id,
        title=req.title,
        message=req.message,
        announcement_type=req.announcement_type,
        target_date=parsed_date,
        venue=req.venue,
        created_at=datetime.utcnow()
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return {"status": "success", "announcement_id": announcement.id}


@router.get("/announcements", response_model=List[Dict[str, Any]])
async def get_lecturer_announcements(
    course_id: int | None = None,
    current_lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    query = db.query(CourseAnnouncement).filter(CourseAnnouncement.lecturer_id == current_lecturer.id)
    if course_id:
        query = query.filter(CourseAnnouncement.course_id == course_id)
    
    announcements = query.order_by(CourseAnnouncement.created_at.desc()).all()
    
    return [
        {
            "id": a.id,
            "course_id": a.course_id,
            "title": a.title,
            "message": a.message,
            "type": a.announcement_type,
            "target_date": a.target_date.isoformat() if a.target_date else None,
            "venue": a.venue,
            "created_at": a.created_at.isoformat()
        }
        for a in announcements
    ]

@router.delete("/announcements/{announcement_id}", response_model=Dict[str, Any])
async def delete_announcement(
    announcement_id: int,
    current_lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    announcement = db.query(CourseAnnouncement).filter(
        CourseAnnouncement.id == announcement_id,
        CourseAnnouncement.lecturer_id == current_lecturer.id
    ).first()
    
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found or you don't have permission to delete it.")
        
    db.delete(announcement)
    db.commit()
    
    return {"status": "success", "message": "Announcement deleted successfully"}

# ── Test Booking Endpoints ────────────────────────────────────

@router.get("/venues/available", response_model=Dict[str, Any])
async def get_available_venues(
    date: str,
    start_time: str,
    end_time: str,
    capacity: int = 0,
    course_id: int = None,
    current_lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    from datetime import datetime
    target_date = datetime.strptime(date, "%Y-%m-%d").date()
    start = datetime.strptime(start_time, "%H:%M").time()
    end = datetime.strptime(end_time, "%H:%M").time()

    from ..utils.conflict_detector import ConflictDetector
    detector = ConflictDetector(db=db)

    # Find which rooms are free, excluding the current course's own recurring slots
    # so the lecturer can overwrite their own class time with a test in the same room.
    truly_free_rooms = detector.get_available_rooms(target_date, start, end, capacity, exclude_course_id=course_id)
    truly_free_ids = {r.id for r in truly_free_rooms}

    # Identify the course's default lecture room (if course_id provided)
    default_room_id: int | None = None
    default_room_info: dict | None = None
    default_room_available: bool = False

    if course_id:
        active_tt = db.query(Timetable).filter(Timetable.is_active == True).first()
        if active_tt:
            lslot = db.query(TimetableSlot).filter(
                TimetableSlot.course_id == course_id,
                TimetableSlot.session_type == "lecture",
                TimetableSlot.timetable_id == active_tt.id
            ).first()
            if lslot and lslot.room_id:
                default_room_id = lslot.room_id
                droom = db.query(Room).filter(Room.id == default_room_id).first()
                if droom:
                    default_room_available = default_room_id in truly_free_ids
                    default_room_info = {
                        "id": droom.id,
                        "name": droom.name,
                        "building": droom.building,
                        "capacity": droom.capacity,
                        "type": droom.room_type,
                        "has_projector": droom.has_projector,
                        "is_default_venue": True,
                        "available": default_room_available,
                    }

    rooms_out = [
        {
            "id": r.id,
            "name": r.name,
            "building": r.building,
            "capacity": r.capacity,
            "type": r.room_type,
            "has_projector": r.has_projector,
            "is_default_venue": r.id == default_room_id,
        }
        for r in truly_free_rooms
    ]

    return {
        "rooms": rooms_out,
        "default_room": default_room_info,
    }

from ..schemas import TestBookingRequest
from ..services.exam_mode_service import ExamModeService

@router.post("/tests", response_model=Dict[str, Any])
async def schedule_test(
    req: TestBookingRequest,
    current_lecturer: Lecturer = Depends(get_current_lecturer),
    db: Session = Depends(get_db)
):
    ExamModeService(db).ensure_non_exam_activity_allowed(
        target_date=req.date,
        university_id=getattr(current_lecturer, "university_id", None),
        activity_label="Test scheduling",
    )

    # Verify assignment
    assignment = db.query(LecturerAssignment).filter(
        LecturerAssignment.lecturer_id == current_lecturer.id,
        LecturerAssignment.course_id == req.course_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=403, detail="You are not assigned to this course.")
        
    room_id = req.room_id
    using_default = False

    if not room_id:
        using_default = True
        # Resolve the course's default lecture room
        timetable = db.query(Timetable).filter(Timetable.is_active == True).first()
        if timetable:
            lecture_slot = db.query(TimetableSlot).filter(
                TimetableSlot.course_id == req.course_id,
                TimetableSlot.session_type == "lecture",
                TimetableSlot.timetable_id == timetable.id
            ).first()
            if lecture_slot and lecture_slot.room_id:
                room_id = lecture_slot.room_id

    if not room_id:
        raise HTTPException(
            status_code=400,
            detail="No default lecture room is configured for this course. Please select a venue manually."
        )

    # Availability check — we DO use exclude_course_id because we WANT the lecturer
    # to be able to overwrite their own regular class schedule with a test in the
    # same room at the same time.
    from ..utils.conflict_detector import ConflictDetector
    from ..models import RoomBooking
    detector = ConflictDetector(db=db)
    available = detector.get_available_rooms(req.date, req.start_time, req.end_time, req.capacity or 0, exclude_course_id=req.course_id)

    if not any(r.id == room_id for r in available):
        if using_default:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Your course's default lecture room is occupied by another booking at the requested time. "
                    "Please use 'Find Available Venues' to select a free room."
                )
            )
        raise HTTPException(
            status_code=409,
            detail="The selected room is not available at the specified time. Please choose another venue."
        )

    from datetime import datetime as _dt
    now = _dt.utcnow()

    booking = RoomBooking(
        room_id=room_id,
        lecturer_id=current_lecturer.id,
        course_id=req.course_id,
        booking_date=req.date,
        start_time=req.start_time,
        end_time=req.end_time,
        booking_type="test",
        created_at=now,
    )
    db.add(booking)

    # Create an announcement for the students
    target_dt = _dt.combine(req.date, req.start_time)

    room = db.query(Room).filter(Room.id == room_id).first()
    venue_str = f"{room.name} ({room.building})" if room else "TBA"

    announcement = CourseAnnouncement(
        course_id=req.course_id,
        lecturer_id=current_lecturer.id,
        title=req.title,
        message=req.message or f"A test has been scheduled on {req.date.strftime('%Y-%m-%d')} at {req.start_time.strftime('%H:%M')}.",
        announcement_type="test_scheduled",
        target_date=target_dt,
        venue=venue_str,
        created_at=now,
    )
    db.add(announcement)

    db.commit()
    return {"status": "success", "booking_id": booking.id, "announcement_id": announcement.id}
