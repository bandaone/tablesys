"""
Print Views Router

Provides print-optimized views for different schedule types:
- Lecturer schedules
- Student group schedules  
- Room schedules
- Weekly overview
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from ..database import get_db
from ..models import (
    Timetable,
    TimetableSlot,
    Lecturer,
    StudentGroup,
    Room,
    Course,
    Department
)
from ..auth import get_current_user
from ..models import User
from ..utils.group_audience import resolve_slot_audience_labels

router = APIRouter(prefix="/api/v1/print", tags=["print"])


def _slot_group_label(db: Session, slot: TimetableSlot) -> str:
    labels = resolve_slot_audience_labels(db, slot)
    return " + ".join(labels) if labels else "N/A"


@router.get("/lecturer/{lecturer_id}")
async def get_lecturer_schedule(
    lecturer_id: int,
    timetable_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get print-friendly schedule for a specific lecturer.
    If timetable_id not provided, uses active timetable.
    """
    # Get lecturer
    lecturer = db.query(Lecturer).filter(Lecturer.id == lecturer_id).first()
    if not lecturer:
        raise HTTPException(status_code=404, detail="Lecturer not found")
    
    # Get timetable
    if timetable_id:
        timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    else:
        timetable = db.query(Timetable).filter(Timetable.is_active == True).first()
    
    if not timetable:
        raise HTTPException(status_code=404, detail="No active timetable found")
    
    # Get all slots for this lecturer
    slots = (
        db.query(TimetableSlot)
        .filter(
            TimetableSlot.timetable_id == timetable.id,
            TimetableSlot.lecturer_id == lecturer_id
        )
        .all()
    )
    
    # Organize slots by day and time
    schedule_data = []
    for slot in slots:
        course = db.query(Course).filter(Course.id == slot.course_id).first()
        room = db.query(Room).filter(Room.id == slot.room_id).first() if slot.room_id else None
        schedule_data.append({
            "day": slot.day,
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "course_code": course.code if course else "N/A",
            "course_name": course.name if course else "N/A",
            "room": room.name if room else "TBA",
            "group": _slot_group_label(db, slot),
            "level": course.level if course else None,
        })
    
    # Sort by day and time
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    schedule_data.sort(key=lambda x: (day_order.index(x["day"]), x["start_time"]))
    
    return {
        "lecturer": {
            "id": lecturer.id,
            "staff_number": lecturer.staff_number,
            "full_name": lecturer.full_name,
            "email": lecturer.email,
            "department": lecturer.department.name if lecturer.department else "N/A",
        },
        "timetable": {
            "id": timetable.id,
            "name": timetable.name,
            "semester": timetable.semester,
            "year": timetable.year,
        },
        "schedule": schedule_data,
        "total_hours": sum(
            (slot.end_time.hour + slot.end_time.minute / 60) -
            (slot.start_time.hour + slot.start_time.minute / 60)
            for slot in slots
        ),
    }


@router.get("/group/{group_id}")
async def get_group_schedule(
    group_id: int,
    timetable_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get print-friendly schedule for a specific student group.
    If timetable_id not provided, uses active timetable.
    """
    # Get group
    group = db.query(StudentGroup).filter(StudentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Student group not found")
    
    # Get timetable
    if timetable_id:
        timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    else:
        timetable = db.query(Timetable).filter(Timetable.is_active == True).first()
    
    if not timetable:
        raise HTTPException(status_code=404, detail="No active timetable found")
    
    # Get all slots for this group
    slots = (
        db.query(TimetableSlot)
        .filter(
            TimetableSlot.timetable_id == timetable.id,
            TimetableSlot.group_id == group_id
        )
        .all()
    )
    
    # Organize slots
    schedule_data = []
    for slot in slots:
        course = db.query(Course).filter(Course.id == slot.course_id).first()
        room = db.query(Room).filter(Room.id == slot.room_id).first() if slot.room_id else None
        lecturer = db.query(Lecturer).filter(Lecturer.id == slot.lecturer_id).first() if slot.lecturer_id else None
        
        schedule_data.append({
            "day": slot.day,
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "course_code": course.code if course else "N/A",
            "course_name": course.name if course else "N/A",
            "room": room.name if room else "TBA",
            "lecturer": lecturer.full_name if lecturer else "TBA",
            "credits": course.credits if course else 0,
        })
    
    # Sort by day and time
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    schedule_data.sort(key=lambda x: (day_order.index(x["day"]), x["start_time"]))
    
    return {
        "group": {
            "id": group.id,
            "group_name": group.group_name,
            "level": group.level,
            "size": group.size,
            "department": group.department.name if group.department else "N/A",
        },
        "timetable": {
            "id": timetable.id,
            "name": timetable.name,
            "semester": timetable.semester,
            "year": timetable.year,
        },
        "schedule": schedule_data,
        "total_hours": sum(
            (slot.end_time.hour + slot.end_time.minute / 60) -
            (slot.start_time.hour + slot.start_time.minute / 60)
            for slot in slots
        ),
    }


@router.get("/room/{room_id}")
async def get_room_schedule(
    room_id: int,
    timetable_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get print-friendly schedule for a specific room.
    Shows all classes scheduled in that room.
    """
    # Get room
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Get timetable
    if timetable_id:
        timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    else:
        timetable = db.query(Timetable).filter(Timetable.is_active == True).first()
    
    if not timetable:
        raise HTTPException(status_code=404, detail="No active timetable found")
    
    # Get all slots for this room
    slots = (
        db.query(TimetableSlot)
        .filter(
            TimetableSlot.timetable_id == timetable.id,
            TimetableSlot.room_id == room_id
        )
        .all()
    )
    
    # Organize slots
    schedule_data = []
    for slot in slots:
        course = db.query(Course).filter(Course.id == slot.course_id).first()
        lecturer = db.query(Lecturer).filter(Lecturer.id == slot.lecturer_id).first() if slot.lecturer_id else None
        schedule_data.append({
            "day": slot.day,
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "course_code": course.code if course else "N/A",
            "course_name": course.name if course else "N/A",
            "lecturer": lecturer.full_name if lecturer else "TBA",
            "group": _slot_group_label(db, slot),
            "level": course.level if course else None,
        })
    
    # Sort by day and time
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    schedule_data.sort(key=lambda x: (day_order.index(x["day"]), x["start_time"]))
    
    return {
        "room": {
            "id": room.id,
            "name": room.name,
            "building": room.building,
            "capacity": room.capacity,
            "room_type": room.room_type,
        },
        "timetable": {
            "id": timetable.id,
            "name": timetable.name,
            "semester": timetable.semester,
            "year": timetable.year,
        },
        "schedule": schedule_data,
        "utilization_percentage": (len(slots) / 50) * 100 if slots else 0,  # 50 = approx slots per week
    }


@router.get("/weekly-overview")
async def get_weekly_overview(
    level: Optional[int] = None,
    timetable_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get weekly overview for print.
    Can filter by level (2, 3, 4, 5).
    """
    # Get timetable
    if timetable_id:
        timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    else:
        timetable = db.query(Timetable).filter(Timetable.is_active == True).first()
    
    if not timetable:
        raise HTTPException(status_code=404, detail="No active timetable found")
    
    # Build query
    query = db.query(TimetableSlot).filter(TimetableSlot.timetable_id == timetable.id)
    
    # Filter by level if provided
    if level:
        query = query.join(Course).filter(Course.level == level)
    
    slots = query.all()
    
    # Organize by day
    days_data = {
        "Monday": [],
        "Tuesday": [],
        "Wednesday": [],
        "Thursday": [],
        "Friday": [],
    }
    
    for slot in slots:
        course = db.query(Course).filter(Course.id == slot.course_id).first()
        room = db.query(Room).filter(Room.id == slot.room_id).first() if slot.room_id else None
        lecturer = db.query(Lecturer).filter(Lecturer.id == slot.lecturer_id).first() if slot.lecturer_id else None
        group = db.query(StudentGroup).filter(StudentGroup.id == slot.group_id).first() if slot.group_id else None
        
        days_data[slot.day].append({
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "course_code": course.code if course else "N/A",
            "course_name": course.name if course else "N/A",
            "room": room.name if room else "TBA",
            "lecturer": lecturer.full_name if lecturer else "TBA",
            "group": group.group_name if group else "N/A",
            "level": course.level if course else None,
        })
    
    # Sort each day by start time
    for day in days_data:
        days_data[day].sort(key=lambda x: x["start_time"])
    
    return {
        "timetable": {
            "id": timetable.id,
            "name": timetable.name,
            "semester": timetable.semester,
            "year": timetable.year,
        },
        "level_filter": level,
        "days": days_data,
        "total_slots": len(slots),
    }
