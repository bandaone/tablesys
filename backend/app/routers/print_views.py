"""
Print Views Router

Provides print-optimized views for different schedule types.
All endpoints verify tenant ownership before returning data.
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


def _assert_timetable_owned(timetable: Timetable, user: User) -> None:
    """Raise 403 if the timetable belongs to a different university."""
    if (
        user.university_id is not None
        and timetable.university_id is not None
        and timetable.university_id != user.university_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this timetable.",
        )


def _get_active_timetable(db: Session, user: User, timetable_id: Optional[int]) -> Timetable:
    """Fetch the requested or active timetable, always scoped to the user's university."""
    if timetable_id:
        timetable = db.query(Timetable).filter(
            Timetable.id == timetable_id,
        ).first()
        if not timetable:
            raise HTTPException(status_code=404, detail="Timetable not found")
        _assert_timetable_owned(timetable, user)
        return timetable

    # Fall back to active timetable for this university
    timetable = db.query(Timetable).filter(
        Timetable.is_active == True,
        Timetable.university_id == user.university_id,
    ).first()
    if not timetable:
        raise HTTPException(status_code=404, detail="No active timetable found")
    return timetable


@router.get("/lecturer/{lecturer_id}")
async def get_lecturer_schedule(
    lecturer_id: int,
    timetable_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get print-friendly schedule for a specific lecturer.
    Ownership is verified: lecturer must belong to the requesting user's university.
    """
    lecturer = db.query(Lecturer).filter(Lecturer.id == lecturer_id).first()
    if not lecturer:
        raise HTTPException(status_code=404, detail="Lecturer not found")

    # Verify the lecturer belongs to this tenant
    if current_user.university_id is not None:
        dept = db.query(Department).filter(Department.id == lecturer.department_id).first()
        if dept and dept.university_id != current_user.university_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this lecturer's schedule.",
            )

    timetable = _get_active_timetable(db, current_user, timetable_id)

    slots = (
        db.query(TimetableSlot)
        .filter(
            TimetableSlot.timetable_id == timetable.id,
            TimetableSlot.lecturer_id == lecturer_id
        )
        .all()
    )

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    schedule_data = []
    for slot in slots:
        course = db.query(Course).filter(Course.id == slot.course_id).first()
        room = db.query(Room).filter(Room.id == slot.room_id).first() if slot.room_id else None
        day_label = day_names[slot.day_of_week] if isinstance(slot.day_of_week, int) else str(slot.day_of_week)
        schedule_data.append({
            "day": day_label,
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "course_code": course.code if course else "N/A",
            "course_name": course.name if course else "N/A",
            "room": room.name if room else "TBA",
            "group": _slot_group_label(db, slot),
            "level": course.level if course else None,
        })

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    schedule_data.sort(key=lambda x: (
        day_order.index(x["day"]) if x["day"] in day_order else 99,
        x["start_time"]
    ))

    return {
        "lecturer": {
            "id": lecturer.id,
            "staff_number": lecturer.staff_number,
            "full_name": lecturer.full_name,
            # email intentionally omitted from print view responses
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
    Ownership is verified: group must belong to the requesting user's university.
    """
    group = db.query(StudentGroup).filter(StudentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Student group not found")

    if current_user.university_id is not None and group.university_id != current_user.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this group's schedule.",
        )

    timetable = _get_active_timetable(db, current_user, timetable_id)

    slots = (
        db.query(TimetableSlot)
        .filter(
            TimetableSlot.timetable_id == timetable.id,
            TimetableSlot.group_id == group_id
        )
        .all()
    )

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    schedule_data = []
    for slot in slots:
        course = db.query(Course).filter(Course.id == slot.course_id).first()
        room = db.query(Room).filter(Room.id == slot.room_id).first() if slot.room_id else None
        lecturer = db.query(Lecturer).filter(Lecturer.id == slot.lecturer_id).first() if slot.lecturer_id else None
        day_label = day_names[slot.day_of_week] if isinstance(slot.day_of_week, int) else str(slot.day_of_week)
        schedule_data.append({
            "day": day_label,
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "course_code": course.code if course else "N/A",
            "course_name": course.name if course else "N/A",
            "room": room.name if room else "TBA",
            "lecturer": lecturer.full_name if lecturer else "TBA",
            "credits": course.credits if course else 0,
        })

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    schedule_data.sort(key=lambda x: (
        day_order.index(x["day"]) if x["day"] in day_order else 99,
        x["start_time"]
    ))

    return {
        "group": {
            "id": group.id,
            "name": group.name,
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
    Ownership verified: room must belong to the requesting user's university.
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if current_user.university_id is not None and room.university_id != current_user.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this room's schedule.",
        )

    timetable = _get_active_timetable(db, current_user, timetable_id)

    slots = (
        db.query(TimetableSlot)
        .filter(
            TimetableSlot.timetable_id == timetable.id,
            TimetableSlot.room_id == room_id
        )
        .all()
    )

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    schedule_data = []
    for slot in slots:
        course = db.query(Course).filter(Course.id == slot.course_id).first()
        lecturer = db.query(Lecturer).filter(Lecturer.id == slot.lecturer_id).first() if slot.lecturer_id else None
        day_label = day_names[slot.day_of_week] if isinstance(slot.day_of_week, int) else str(slot.day_of_week)
        schedule_data.append({
            "day": day_label,
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "course_code": course.code if course else "N/A",
            "course_name": course.name if course else "N/A",
            "lecturer": lecturer.full_name if lecturer else "TBA",
            "group": _slot_group_label(db, slot),
            "level": course.level if course else None,
        })

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    schedule_data.sort(key=lambda x: (
        day_order.index(x["day"]) if x["day"] in day_order else 99,
        x["start_time"]
    ))

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
        "utilization_percentage": (len(slots) / 50) * 100 if slots else 0,
    }


@router.get("/weekly-overview")
async def get_weekly_overview(
    level: Optional[int] = None,
    timetable_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get weekly overview for print. Scoped to the requesting user's university.
    Can filter by level (1-7).
    """
    timetable = _get_active_timetable(db, current_user, timetable_id)

    query = db.query(TimetableSlot).filter(TimetableSlot.timetable_id == timetable.id)

    if level:
        query = query.join(Course).filter(Course.level == level)

    slots = query.all()

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    days_data: Dict = {d: [] for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]}

    for slot in slots:
        course = db.query(Course).filter(Course.id == slot.course_id).first()
        room = db.query(Room).filter(Room.id == slot.room_id).first() if slot.room_id else None
        lecturer = db.query(Lecturer).filter(Lecturer.id == slot.lecturer_id).first() if slot.lecturer_id else None
        group = db.query(StudentGroup).filter(StudentGroup.id == slot.group_id).first() if slot.group_id else None
        day_label = day_names[slot.day_of_week] if isinstance(slot.day_of_week, int) else str(slot.day_of_week)

        if day_label not in days_data:
            continue

        days_data[day_label].append({
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "course_code": course.code if course else "N/A",
            "course_name": course.name if course else "N/A",
            "room": room.name if room else "TBA",
            "lecturer": lecturer.full_name if lecturer else "TBA",
            "group": group.name if group else "N/A",
            "level": course.level if course else None,
        })

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
