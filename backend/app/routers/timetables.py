from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import asyncio
from datetime import datetime
from ..database import get_db
from ..schemas import Timetable, TimetableCreate, TimetableWithSlots, SlotAssignmentRequest, ManualSlotCreate, TimetableSlot as TimetableSlotSchema
from ..models import ActivityType, Timetable as TimetableModel, TimetableSlot, Course, Room, Lecturer, User, StudentGroup, University, UserRole, LabSession, LabSessionStatus, Department
from ..auth import get_current_user, get_current_active_lab_coordinator
from ..services.timetable_generator import TimetableGenerator
from ..utils.conflict_detector import ConflictDetector
from ..services.analytics_service import AnalyticsService
from ..services.validation_service import ValidationService
from ..services.version_service import VersionService
from ..services.notification_service import NotificationService
from ..services.generation_observability import finalize_generation_run, mark_generation_started, utc_now
from ..utils.course_profile import COURSE_PROFILE_STATUS_COMPLETE
from ..utils.audit_logger import AuditLogger
from ..utils.group_audience import resolve_slot_audience_labels
from ..config import settings
from ..middleware.quota import enforce_generation_quota
from ..utils.school_scope import ensure_user_can_manage_school, filter_timetable_query_for_user
import json
import redis.asyncio as aioredis
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/timetables", tags=["timetables"])

# ---------------------------------------------------------------------------
# Local Pydantic models for Drag-and-Drop Overrides (Agent Beta scope only)
# These are deliberately kept local to avoid touching schemas.py, which is
# shared across all agents in the parallel workplan.
# ---------------------------------------------------------------------------

class SlotOverride(BaseModel):
    """
    Represents a manual positional override for a single timetable slot.
    The solver-generated position is preserved in the DB; only the
    generation_metadata['overrides'] dict is updated so the change is
    fully reversible without touching the constraint data.

    Fields:
        slot_id    — The DB primary key of the TimetableSlot to override.
        day        — Target day string: MONDAY | TUESDAY | ... | FRIDAY.
        start_time — New start time in HH:MM format (24-hour).
        end_time   — New end time in HH:MM format (24-hour).
        room       — Optional room override. If None, original room is kept.
    """
    slot_id: int
    day: str
    start_time: str  # "HH:MM"
    end_time: str    # "HH:MM"
    room: Optional[str] = None  # future room-swap support, ignored for now


class ApplyOverridesRequest(BaseModel):
    """
    Batch override payload.  Sending the same slot_id twice in one request
    keeps only the LAST entry to avoid ambiguity.
    """
    overrides: List[SlotOverride]


def _activity_type_map(db: Session, university_id: Optional[int]) -> dict[str, dict[str, str]]:
    if not university_id:
        return {}
    rows = (
        db.query(ActivityType)
        .filter(
            ActivityType.university_id == university_id,
            ActivityType.is_active == True,
        )
        .all()
    )
    return {
        str(row.key).strip().lower(): {
            "display_name": row.display_name,
            "color": row.color or "#3B82F6",
        }
        for row in rows
    }


class RedisConnectionManager:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.active_connections: dict[str, List[WebSocket]] = {}
        self.pubsub_tasks: dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
            self.pubsub_tasks[channel] = asyncio.create_task(self._listen(channel))
        self.active_connections[channel].append(websocket)

    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections and websocket in self.active_connections[channel]:
            self.active_connections[channel].remove(websocket)
            if not self.active_connections[channel]:
                if channel in self.pubsub_tasks:
                    self.pubsub_tasks[channel].cancel()
                    del self.pubsub_tasks[channel]
                del self.active_connections[channel]

    async def _listen(self, channel: str):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    data = message['data']
                    if channel in self.active_connections:
                        for ws in list(self.active_connections[channel]):
                            try:
                                await ws.send_text(data)
                            except Exception:
                                self.disconnect(ws, channel)
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel)

    async def send_progress(self, message: dict, channel: str):
        await self.redis.publish(channel, json.dumps(message))

manager = RedisConnectionManager(settings.REDIS_URL)


def _raise_validation_errors(validation_errors: list[dict]) -> None:
    blocking_errors = [error for error in validation_errors if error.get("severity", "error") == "error"]
    if blocking_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Slot validation failed",
                "errors": blocking_errors,
                "warnings": [error for error in validation_errors if error.get("severity") == "warning"],
            },
        )


def _normalize_hhmm(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot be empty")
    try:
        return datetime.strptime(text, "%H:%M").strftime("%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} must be in HH:MM format")


def _upsert_generation_window(
    db: Session,
    timetable: TimetableModel,
    start_time: Optional[str],
    end_time: Optional[str],
    lunch_start: Optional[str] = None,
    lunch_end: Optional[str] = None,
) -> None:
    normalized_start = _normalize_hhmm(start_time, "start_time")
    normalized_end = _normalize_hhmm(end_time, "end_time")
    normalized_lunch_start = _normalize_hhmm(lunch_start, "lunch_start")
    normalized_lunch_end = _normalize_hhmm(lunch_end, "lunch_end")

    if (
        normalized_start is None
        and normalized_end is None
        and normalized_lunch_start is None
        and normalized_lunch_end is None
    ):
        return

    meta = dict(timetable.generation_metadata or {})
    existing_grid = meta.get("grid_config") if isinstance(meta.get("grid_config"), dict) else {}
    grid = dict(existing_grid)

    if normalized_start is not None:
        grid["start_time"] = normalized_start
    if normalized_end is not None:
        grid["end_time"] = normalized_end
    if normalized_lunch_start is not None:
        grid["lunch_start"] = normalized_lunch_start
    if normalized_lunch_end is not None:
        grid["lunch_end"] = normalized_lunch_end

    final_start = grid.get("start_time")
    final_end = grid.get("end_time")
    if final_start and final_end:
        parsed_start = datetime.strptime(final_start, "%H:%M")
        parsed_end = datetime.strptime(final_end, "%H:%M")
        if parsed_start >= parsed_end:
            raise HTTPException(status_code=400, detail="start_time must be earlier than end_time")

    final_lunch_start = grid.get("lunch_start")
    final_lunch_end = grid.get("lunch_end")
    if final_lunch_start and final_lunch_end:
        parsed_lunch_start = datetime.strptime(final_lunch_start, "%H:%M")
        parsed_lunch_end = datetime.strptime(final_lunch_end, "%H:%M")
        if parsed_lunch_start >= parsed_lunch_end:
            raise HTTPException(status_code=400, detail="lunch_start must be earlier than lunch_end")

    meta["grid_config"] = grid
    timetable.generation_metadata = meta
    db.commit()
    db.refresh(timetable)


def resolve_university_id(db: Session, current_user: User) -> int:
    if getattr(current_user, "university_id", None):
        return current_user.university_id
    uni = db.query(University).order_by(University.id.asc()).first()
    if not uni:
        raise HTTPException(status_code=500, detail="No university found for timetable creation")
    return uni.id

@router.get("/", response_model=List[Timetable])
async def get_timetables(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all timetables."""
    timetables = filter_timetable_query_for_user(db.query(TimetableModel), current_user).offset(skip).limit(limit).all()
    return timetables

@router.get("/{timetable_id:int}", response_model=TimetableWithSlots)
async def get_timetable(
    timetable_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific timetable with all slots."""
    timetable = filter_timetable_query_for_user(
        db.query(TimetableModel).filter(TimetableModel.id == timetable_id),
        current_user,
    ).first()
    
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    return timetable

@router.post("/", response_model=Timetable, status_code=status.HTTP_201_CREATED)
async def create_timetable(
    timetable: TimetableCreate,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db)
):
    """Create a new timetable (without generating slots). Coordinator only."""
    timetable_data = timetable.model_dump()
    grid_config = timetable_data.pop("grid_config", None)
    timetable_data["university_id"] = resolve_university_id(db, current_user)
    if timetable_data.get("school_id") is None:
        raise HTTPException(status_code=422, detail="A timetable must belong to a school.")
    ensure_user_can_manage_school(db, current_user, timetable_data.get("school_id"))

    db_timetable = TimetableModel(**timetable_data)
    if grid_config:
        meta = db_timetable.generation_metadata or {}
        meta["grid_config"] = grid_config
        db_timetable.generation_metadata = meta

    db.add(db_timetable)
    db.commit()
    db.refresh(db_timetable)
    return db_timetable

@router.websocket("/generate/{timetable_id:int}")
async def generate_timetable_ws(
    websocket: WebSocket,
    timetable_id: int,
    components: Optional[str] = Query(None, description="Comma-separated list of components (lecture,tutorial,practical)"),
    start_time: Optional[str] = Query(None, description="Generation start time in HH:MM format"),
    end_time: Optional[str] = Query(None, description="Generation end time in HH:MM format"),
    lunch_start: Optional[str] = Query(None, description="Lunch break start time in HH:MM format"),
    lunch_end: Optional[str] = Query(None, description="Lunch break end time in HH:MM format"),
    profile: str = Query("balanced", description="Scheduling profile"),
    current_user: User = Depends(get_current_active_lab_coordinator) # Inject current user for logging
):
    """
    Generate timetable with real-time progress updates via WebSocket.
    This endpoint generates the timetable level by level (5th -> 4th -> 3rd -> 2nd).
    Can selectively generate components (e.g. lectures only).
    """
    channel = f"timetable_progress_{timetable_id}"
    await manager.connect(websocket, channel)
    
    # Mock request for AuditLogger in a WebSocket context
    class MockRequest:
        client = None
        headers = {}
        url = type('obj', (object,), {'path': f'/api/timetables/generate/{timetable_id}'})()
        method = "WS"
    
    mock_request = MockRequest()
    
    db = None # Initialize db to None for finally block
    try:
        # Get database session
        db = next(get_db())
        
        # Check if timetable exists
        timetable = filter_timetable_query_for_user(
            db.query(TimetableModel).filter(TimetableModel.id == timetable_id),
            current_user,
        ).first()
        
        if not timetable:
            await websocket.send_json({
                'status': 'error',
                'message': 'Timetable not found'
            })
            AuditLogger.log_timetable_generation(
                request=mock_request,
                user_id=current_user.id,
                username=current_user.username,
                timetable_id=timetable_id,
                success=False,
                details={"message": "Timetable not found"}
            )
            return

        quota_info = enforce_generation_quota(db, getattr(current_user, "university_id", None))
        if quota_info and quota_info.get("status") in {"warning", "hard_warning"}:
            await websocket.send_json({
                "status": "warning",
                "message": "Timetable generation quota threshold reached",
                "quota": quota_info,
            })

        # Persist per-run time-window selection before solver startup.
        _upsert_generation_window(db, timetable, start_time, end_time, lunch_start, lunch_end)
        
        async def progress_callback(progress_data: dict):
            await manager.send_progress(progress_data, channel)
        
        # Parse components if provided
        generation_components = None
        if components:
            generation_components = [c.strip() for c in components.split(',')]
            
        # Create generator instance
        generation_started_at = utc_now()
        mark_generation_started(
            timetable,
            mode="interactive",
            started_at=generation_started_at,
            components=generation_components,
        )
        db.commit()

        generator = TimetableGenerator(
            db=db,
            timetable_id=timetable_id,
            progress_callback=lambda data: asyncio.create_task(progress_callback(data)),
            components=generation_components,
            profile=profile
        )
        
        # Run generation
        await websocket.send_json({
            'status': 'started',
            'message': 'Timetable generation started',
            'quota': quota_info,
        })
        
        success = generator.generate_timetable()
        
        if success:
            levels_processed = [v[0] for v in db.query(Course.level).distinct().all() if v[0] is not None]
            levels_processed.sort(reverse=True)

            # Update timetable metadata while preserving existing keys like grid_config/overrides.
            meta = dict(timetable.generation_metadata or {})
            meta.update({
                'generated': True,
                'levels_processed': levels_processed
            })
            timetable.generation_metadata = meta
            finalize_generation_run(
                db,
                timetable,
                tenant_id=timetable.university_id,
                success=True,
                started_at=generation_started_at,
                mode="interactive",
                components=generation_components,
                saved_slot_count=db.query(TimetableSlot).filter(TimetableSlot.timetable_id == timetable_id).count(),
                solver_status_by_level=generator.solver_status_by_level,
                fallback_levels=generator.fallback_levels,
                diagnostics=generator.generation_diagnostics,
            )
            db.commit()
            
            # Send notifications to coordinators
            notification_service = NotificationService(db)
            notification_service.notify_coordinators(
                title="Timetable Generated",
                message=f"The timetable '{timetable.name}' has been successfully generated and is ready for review.",
                type="success",
                action_link=f"/timetables",
                send_email=False
            )
            
            await websocket.send_json({
                'status': 'success',
                'message': 'Timetable generated successfully',
                'timetable_id': timetable_id,
                'quota': quota_info,
            })
            
            AuditLogger.log_timetable_generation(
                request=mock_request,
                user_id=current_user.id,
                username=current_user.username,
                timetable_id=timetable_id,
                success=True,
                details={"message": "All levels generated successfully"}
            )
        else:
            finalize_generation_run(
                db,
                timetable,
                tenant_id=timetable.university_id,
                success=False,
                started_at=generation_started_at,
                mode="interactive",
                components=generation_components,
                saved_slot_count=db.query(TimetableSlot).filter(TimetableSlot.timetable_id == timetable_id).count(),
                error_message="Failed to generate timetable due to constraints.",
                solver_status_by_level=generator.solver_status_by_level,
                fallback_levels=generator.fallback_levels,
                diagnostics=generator.generation_diagnostics,
            )
            db.commit()
            await websocket.send_json({
                'status': 'error',
                'message': 'Failed to generate timetable. Please check constraints.'
            })
            AuditLogger.log_timetable_generation(
                request=mock_request,
                user_id=current_user.id,
                username=current_user.username,
                timetable_id=timetable_id,
                success=False,
                details={"message": "Failed to generate timetable due to constraints"}
            )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)
    except HTTPException as e:
        if db and 'timetable' in locals() and timetable:
            try:
                finalize_generation_run(
                    db,
                    timetable,
                    tenant_id=timetable.university_id,
                    success=False,
                    started_at=locals().get("generation_started_at", utc_now()),
                    mode="interactive",
                    components=locals().get("generation_components"),
                    error_message=str(e.detail),
                )
                db.commit()
            except Exception:
                db.rollback()
        await websocket.send_json({
            'status': 'error',
            'message': str(e.detail)
        })
        AuditLogger.log_timetable_generation(
            request=mock_request,
            user_id=current_user.id,
            username=current_user.username,
            timetable_id=timetable_id,
            success=False,
            details={"message": f"Validation error during generation setup: {e.detail}"}
        )
    except Exception as e:
        error_msg = str(e) if isinstance(e, ValueError) else "An unexpected error occurred during timetable generation."
        if db and 'timetable' in locals() and timetable:
            try:
                finalize_generation_run(
                    db,
                    timetable,
                    tenant_id=timetable.university_id,
                    success=False,
                    started_at=locals().get("generation_started_at", utc_now()),
                    mode="interactive",
                    components=locals().get("generation_components"),
                    error_message=str(e),
                )
                db.commit()
            except Exception:
                db.rollback()
        await websocket.send_json({
            'status': 'error',
            'message': f'Error generating timetable: {error_msg}'
        })
        AuditLogger.log_timetable_generation(
            request=mock_request,
            user_id=current_user.id,
            username=current_user.username,
            timetable_id=timetable_id,
            success=False,
            details={"message": f"Error during generation: {str(e)}"}
        )
    finally:
        if db:
            db.close()
        manager.disconnect(websocket, channel) # Ensure disconnection even on error

@router.post("/{timetable_id:int}/activate", response_model=Timetable)
async def activate_timetable(
    timetable_id: int,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db)
):
    """Activate a timetable (deactivate all others). Coordinator only."""
    timetable = filter_timetable_query_for_user(
        db.query(TimetableModel).filter(TimetableModel.id == timetable_id),
        current_user,
    ).first()
    
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    # Deactivate all other timetables
    filter_timetable_query_for_user(db.query(TimetableModel), current_user).update(
        {TimetableModel.is_active: False}
    )
    
    # Activate this one
    timetable.is_active = True
    db.commit()
    db.refresh(timetable)
    
    return timetable

@router.delete("/{timetable_id:int}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timetable(
    timetable_id: int,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db)
):
    """Delete a timetable. Coordinator only."""
    timetable = filter_timetable_query_for_user(
        db.query(TimetableModel).filter(TimetableModel.id == timetable_id),
        current_user,
    ).first()
    
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    db.delete(timetable)
    db.commit()
    return None


@router.get("/view")
async def get_timetable_view(
    request: Request,
    year: int = Query(..., ge=1, le=7, description="Year level: 1-7"),
    program: Optional[str] = Query(default="ALL", description="Program code or ALL"),
    timetable_id: Optional[int] = Query(None, description="Specific timetable to view. Defaults to active timetable."),
    academic_week: Optional[int] = Query(None, description="Current academic week number for lab rotation filtering (1-indexed)."),
    lab_subgroup_ids: Optional[str] = Query(None, description="Comma-separated list of selected lab subgroups."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return timetable slots for the active timetable, filtered by year level and program.

    Used by the TimetableGrid UI component. Returns a flat list of slot objects
    alongside summary metadata. When no active timetable exists, returns empty slots.
    """
    # Find the requested or active timetable inside the user's school/tenant
    # scope. This endpoint powers the staff dashboard, so an unscoped .first()
    # here would expose whichever active timetable happens to be returned first.
    timetable_query = filter_timetable_query_for_user(db.query(TimetableModel), current_user)
    if timetable_id:
        active_timetable = timetable_query.filter(TimetableModel.id == timetable_id).first()
    else:
        active_timetable = timetable_query.filter(
            TimetableModel.is_active == True,
        ).order_by(TimetableModel.id.desc()).first()

    if not active_timetable:
        return {
            "metadata": {
                "term": "N/A",
                "year": 0,
                "total_courses": 0,
                "available_years": [],
            },
            "slots": [],
        }

    def _normalize_year_level(raw_level: Optional[int]) -> Optional[int]:
        if raw_level is None:
            return None
        if 1 <= raw_level <= 7:
            return raw_level
        if raw_level % 100 == 0 and 100 <= raw_level <= 700:
            return raw_level // 100
        return None

    available_level_rows = (
        db.query(Course.level)
        .join(TimetableSlot, TimetableSlot.course_id == Course.id)
        .filter(TimetableSlot.timetable_id == active_timetable.id)
        .distinct()
        .all()
    )
    available_years = sorted(
        {
            normalized
            for (level_value,) in available_level_rows
            for normalized in [_normalize_year_level(level_value)]
            if normalized is not None
        }
    )

    query = (
        db.query(TimetableSlot)
        .join(Course, TimetableSlot.course_id == Course.id)
        .outerjoin(Room, TimetableSlot.room_id == Room.id)
        .filter(TimetableSlot.timetable_id == active_timetable.id)
        .filter(Course.level.in_([year, year * 100]))
    )

    if program and program.upper() != "ALL":
        query = query.filter(Course.code.like(f"{program.upper()}%"))

    slots = query.all()

    # --- HOD Filtering Logic ---
    if current_user.role == UserRole.HOD and current_user.department_id:
        hod_dept_id = current_user.department_id
        
        # Pre-fetch lecturers and groups for this dept
        hod_lecturer_ids = {l.id for l in db.query(Lecturer.id).filter(Lecturer.department_id == hod_dept_id).all()}
        hod_group_ids = {g.id for g in db.query(StudentGroup.id).filter(StudentGroup.department_id == hod_dept_id).all()}
        
        filtered_slots = []
        for slot in slots:
            # Check 1: Course belongs to HOD dept
            if slot.course.department_id == hod_dept_id:
                filtered_slots.append(slot)
                continue
                
            # Check 2: Lecturer belongs to HOD dept
            if slot.lecturer_id in hod_lecturer_ids:
                filtered_slots.append(slot)
                continue
                
            # Check 3: Main group belongs to HOD dept
            if slot.group_id in hod_group_ids:
                filtered_slots.append(slot)
                continue
                
            # Check 4: Shared groups include a group from HOD dept
            if slot.shared_group_ids:
                if any(gid in hod_group_ids for gid in slot.shared_group_ids):
                    filtered_slots.append(slot)
                    continue
                    
        slots = filtered_slots
    # ---------------------------

    grid_config = (active_timetable.generation_metadata or {}).get("grid_config") or {}
    active_days = grid_config.get("active_days") if isinstance(grid_config, dict) else None
    normalized_days = active_days if isinstance(active_days, list) and active_days else [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
    ]
    days_map = {idx: str(day).upper() for idx, day in enumerate(normalized_days)}
    activity_types_by_key = _activity_type_map(db, active_timetable.university_id)
    selected_lab_subgroup_ids = [
        int(value)
        for value in lab_subgroup_ids.split(",")
        if value.strip().isdigit()
    ] if lab_subgroup_ids else []

    group_cache = {}
    stream_children_cache = {}
    slot_list = []
    for slot in slots:
        lecturer_name: Optional[str] = None
        if slot.lecturer_id:
            lecturer_obj = db.query(Lecturer).filter(Lecturer.id == slot.lecturer_id).first()
            if lecturer_obj:
                lecturer_name = lecturer_obj.full_name

        audience_groups = resolve_slot_audience_labels(
            db,
            slot,
            group_cache=group_cache,
            stream_children_cache=stream_children_cache,
        )
        if not audience_groups:
            audience_groups = ["Unknown Group"]
        group_label = " + ".join(audience_groups[:3])
        if len(audience_groups) > 3:
            group_label += f" +{len(audience_groups) - 3} more"
        activity_key = str(slot.session_type or "").strip().lower()
        activity_meta = activity_types_by_key.get(activity_key, {})

        slot_list.append({
            "slot_id": slot.id,
            "day": days_map.get(slot.day_of_week, ""),
            "start_time": slot.start_time.strftime("%H:%M"),
            "end_time": slot.end_time.strftime("%H:%M"),
            "course_code": slot.course.code,
            "room": slot.room.name,
            "lecturer": lecturer_name,
            "session_type": slot.session_type,
            "activity_type_key": activity_key or None,
            "activity_display_name": activity_meta.get("display_name"),
            "activity_color": activity_meta.get("color"),
            "group_label": group_label,
            "groups": audience_groups,
            "shared_group_ids": slot.shared_group_ids,
            "combined_size": slot.combined_size,
            # Indicates the slot is in its solver-generated position (may be
            # overridden below by the override layer).
            "is_overridden": False,
            "timetable_id": active_timetable.id,
        })

    # ---------------------------------------------------------------------------
    # Override layer: apply any coordinator drag-and-drop overrides that are
    # stored in generation_metadata["overrides"].  This is a pure in-memory pass
    # over slot_list — no additional DB query is required.
    #
    # The overrides dict has the shape:  { "<slot_id>": { "day": ..., "start_time":
    # ..., "end_time": ..., "room": ... } }
    # ---------------------------------------------------------------------------
    raw_overrides: dict = (
        (active_timetable.generation_metadata or {}).get("overrides", {})
    )

    if raw_overrides:
        # Build a quick lookup by slot_id for O(1) per-slot resolution
        override_map: dict[str, dict] = {str(k): v for k, v in raw_overrides.items()}
        for entry in slot_list:
            ov = override_map.get(str(entry["slot_id"]))
            if ov:
                entry["day"] = ov.get("day", entry["day"])
                entry["start_time"] = ov.get("start_time", entry["start_time"])
                entry["end_time"] = ov.get("end_time", entry["end_time"])
                if ov.get("room"):
                    entry["room"] = ov["room"]
                entry["is_overridden"] = True

    # Broadcast viewing activity to real-time dashboard
    AuditLogger.log_event(
        event_type="VIEW_TIMETABLE",
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        action="GET",
        resource="/api/v1/timetables/view",
        details={
            "year": year,
            "program": program,
            "timetable_id": active_timetable.id,
            "slots_viewed": len(slot_list)
        },
        success=True
    )

    # ── Lab Session Rotation Injection ────────────────────────────────────────
    DAY_NAMES_LAB = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    lab_q = (
        db.query(LabSession)
        .join(Course, LabSession.course_id == Course.id)
        .filter(
            LabSession.university_id == active_timetable.university_id,
            LabSession.timetable_id == active_timetable.id,
            LabSession.status.in_([LabSessionStatus.PUBLISHED, LabSessionStatus.SCHEDULED]),
            Course.level.in_([year, year * 100]),
        )
    )
    if program and program.upper() != "ALL":
        lab_q = lab_q.filter(Course.code.like(f"{program.upper()}%"))

    for ls in lab_q.all():
        ls_course = db.query(Course).filter(Course.id == ls.course_id).first()
        ls_group = db.query(StudentGroup).filter(StudentGroup.id == ls.group_id).first()
        ls_room = db.query(Room).filter(Room.id == ls.room_id).first() if ls.room_id else None

        active_subgroup_ids = None
        subgroup_label = ls_group.name if ls_group else "Lab Group"
        if ls.rotation_configuration and academic_week is not None:
            cycle_pos = str(((academic_week - 1) % max(ls.rotation_cycle_length, 1)) + 1)
            active_subgroup_ids = [
                int(group_id)
                for group_id in ls.rotation_configuration.get(cycle_pos, [])
                if str(group_id).isdigit()
            ]
            if selected_lab_subgroup_ids and not any(
                subgroup_id in active_subgroup_ids for subgroup_id in selected_lab_subgroup_ids
            ):
                continue

            sub_names = []
            for sg_id in active_subgroup_ids:
                sg = db.query(StudentGroup).filter(StudentGroup.id == int(sg_id)).first()
                if sg:
                    sub_names.append(sg.name)
            subgroup_label = ", ".join(sub_names) if sub_names else "No subgroups this week"
        elif selected_lab_subgroup_ids and ls.rotation_configuration:
            all_rotation_ids = {
                int(group_id)
                for group_ids in ls.rotation_configuration.values()
                for group_id in (group_ids or [])
                if str(group_id).isdigit()
            }
            if not any(subgroup_id in all_rotation_ids for subgroup_id in selected_lab_subgroup_ids):
                continue

        slot_list.append({
            "slot_id": f"lab_{ls.id}",
            "day": DAY_NAMES_LAB[ls.day_of_week].upper() if 0 <= ls.day_of_week <= 6 else "",
            "start_time": ls.start_time.strftime("%H:%M"),
            "end_time": ls.end_time.strftime("%H:%M"),
            "course_code": ls_course.code if ls_course else "LAB",
            "room": ls_room.name if ls_room else "TBA",
            "lecturer": None,
            "session_type": ls.session_type or "lab",
            "activity_type_key": "lab",
            "activity_display_name": "Lab Session",
            "activity_color": "#7C3AED",
            "group_label": f"{ls_group.name if ls_group else 'Lab'} — {subgroup_label}",
            "groups": [subgroup_label],
            "shared_group_ids": None,
            "combined_size": None,
            "is_overridden": False,
            "is_lab_session": True,
            "lab_session_id": ls.id,
            "rotation_cycle_length": ls.rotation_cycle_length,
            "rotation_configuration": ls.rotation_configuration,
            "active_subgroup_ids": active_subgroup_ids,
            "timetable_id": active_timetable.id,
        })
    # ── End Lab Injection ──────────────────────────────────────────────────────

    return {
        "metadata": {
            "id": active_timetable.id,
            "term": active_timetable.semester,
            "year": active_timetable.year,
            "total_courses": len({s["course_code"] for s in slot_list}),
            "grid_config": grid_config,
            "available_years": available_years,
        },
        "slots": slot_list,
    }

@router.get("/{timetable_id:int}/conflicts")
async def get_timetable_conflicts(
    timetable_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all scheduling conflicts for a timetable.
    
    Detects:
    - Lecturer double-bookings (same lecturer, overlapping times)
    - Room double-bookings (same room, overlapping times)
    - Group double-bookings (same student group, overlapping times)
    
    Returns conflict summary with details for each conflict.
    """
    # Check if timetable exists
    timetable = filter_timetable_query_for_user(
        db.query(TimetableModel).filter(TimetableModel.id == timetable_id),
        current_user,
    ).first()
    
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    # Detect conflicts
    detector = ConflictDetector(db)
    conflict_summary = detector.get_conflict_summary(timetable_id)
    
    return conflict_summary


@router.get("/active/analytics", status_code=status.HTTP_200_OK)
async def get_active_timetable_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get analytics for the currently active timetable.
    """
    try:
        analytics = AnalyticsService(db, current_user)
        return analytics.get_active_timetable_analytics()
    except ValueError:
        raise HTTPException(status_code=404, detail="No active timetable found.")


@router.get("/{timetable_id:int}/analytics", status_code=status.HTTP_200_OK)
async def get_timetable_analytics(
    timetable_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get analytics and statistics for a specific timetable.
    
    Returns comprehensive analytics including:
    - Room utilization rates
    - Lecturer workload distribution
    - Course distribution by department
    - Time slot utilization
    """
    try:
        analytics = AnalyticsService(db, current_user)
        return analytics.get_timetable_analytics(timetable_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Timetable not found.")


@router.post("/slots/{slot_id}/assign", status_code=status.HTTP_200_OK)
async def assign_slot(
    slot_id: int,
    assignment: SlotAssignmentRequest,
    request: Request,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db)
):
    """
    Assign lecturer and/or student group to a timetable slot.
    Coordinator only. Used by the assignment UI to update slot assignments.
    Includes validation warnings.
    """
    # Find the slot
    slot = db.query(TimetableSlot).filter(TimetableSlot.id == slot_id).first()
    
    if not slot:
        raise HTTPException(status_code=404, detail="Timetable slot not found")
    
    # Validate lecturer_id if provided
    if assignment.lecturer_id is not None:
        lecturer = db.query(Lecturer).filter(Lecturer.id == assignment.lecturer_id).first()
        if not lecturer:
            raise HTTPException(status_code=422, detail="Invalid lecturer_id")
        slot.lecturer_id = assignment.lecturer_id
    
    # Validate group_id if provided
    if assignment.group_id is not None:
        group = db.query(StudentGroup).filter(StudentGroup.id == assignment.group_id).first()
        if not group:
            raise HTTPException(status_code=422, detail="Invalid group_id")
        slot.group_id = assignment.group_id
    
    # Run validation check
    validator = ValidationService(db)
    slot_data = {
        "course_id": slot.course_id,
        "room_id": slot.room_id,
        "lecturer_id": slot.lecturer_id,
        "group_id": slot.group_id,
        "day_of_week": slot.day_of_week,
        "start_time": slot.start_time,
        "end_time": slot.end_time,
        "session_type": slot.session_type,
        "shared_group_ids": slot.shared_group_ids,
        "combined_size": slot.combined_size,
    }
    is_valid, validation_errors = validator.validate_timetable_slot(
        slot_data, slot.timetable_id, exclude_slot_id=slot_id
    )
    _raise_validation_errors(validation_errors)
    
    # Commit the changes
    db.commit()
    db.refresh(slot)

    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UPDATE",
        resource_type="timetable_slot_assignment",
        resource_id=slot.id,
        details={
            "slot_id": slot.id,
            "course_id": slot.course_id,
            "lecturer_id": slot.lecturer_id,
            "group_id": slot.group_id,
        },
    )
    
    # Return with validation warnings
    return {
        "status": "success",
        "message": "Slot assignment updated",
        "slot_id": slot.id,
        "lecturer_id": slot.lecturer_id,
        "group_id": slot.group_id,
        "validation": {
            "has_issues": len(validation_errors) > 0,
            "issues": validation_errors
        }
    }


@router.post("/{timetable_id}/slots/manual", response_model=TimetableSlotSchema, status_code=status.HTTP_201_CREATED)
async def create_manual_slot(
    timetable_id: int,
    slot_request: ManualSlotCreate,
    request: Request,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db)
):
    """
    Create a manual timetable slot. Coordinator only.
    Useful for scheduling specific subgroups or custom sessions.
    """
    # Verify timetable exists
    timetable = filter_timetable_query_for_user(
        db.query(TimetableModel).filter(TimetableModel.id == timetable_id),
        current_user,
    ).first()
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    ensure_user_can_manage_school(db, current_user, timetable.school_id)

    # Verify course exists
    course = db.query(Course).filter(Course.id == slot_request.course_id).first()
    if not course:
        raise HTTPException(status_code=422, detail="Invalid course_id")
    if course.profile_status != COURSE_PROFILE_STATUS_COMPLETE:
        raise HTTPException(
            status_code=422,
            detail="This course is still profile-seeded. Complete its academic details before scheduling it.",
        )

    # Verify lecturer exists
    lecturer = db.query(Lecturer).filter(Lecturer.id == slot_request.lecturer_id).first()
    if not lecturer:
        raise HTTPException(status_code=422, detail="Invalid lecturer_id")

    # Verify room exists. Manual slots must always target a concrete venue.
    if slot_request.room_id is None:
        raise HTTPException(status_code=422, detail="room_id is required for manual slots")
    room = db.query(Room).filter(Room.id == slot_request.room_id).first()
    if not room:
        raise HTTPException(status_code=422, detail="Invalid room_id")
    if room.school_id != timetable.school_id:
        raise HTTPException(status_code=422, detail="Selected room is outside the timetable school scope")

    # Verify group exists
    group = db.query(StudentGroup).filter(StudentGroup.id == slot_request.group_id).first()
    if not group:
        raise HTTPException(status_code=422, detail="Invalid group_id")

    course_department = db.query(Department).filter(Department.id == course.department_id).first()
    group_department = db.query(Department).filter(Department.id == group.department_id).first()
    lecturer_department = db.query(Department).filter(Department.id == lecturer.department_id).first()
    if any(not department or department.school_id != timetable.school_id for department in (
        course_department, group_department, lecturer_department,
    )):
        raise HTTPException(status_code=422, detail="Course, group, lecturer, and room must belong to the timetable's school")

    validator = ValidationService(db)
    _, validation_errors = validator.validate_timetable_slot(
        {
            "course_id": slot_request.course_id,
            "lecturer_id": slot_request.lecturer_id,
            "room_id": slot_request.room_id,
            "group_id": slot_request.group_id,
            "day_of_week": slot_request.day_of_week,
            "start_time": slot_request.start_time,
            "end_time": slot_request.end_time,
            "session_type": slot_request.session_type,
        },
        timetable_id,
    )
    _raise_validation_errors(validation_errors)

    # Create the slot
    new_slot = TimetableSlot(
        timetable_id=timetable_id,
        course_id=slot_request.course_id,
        lecturer_id=slot_request.lecturer_id,
        room_id=slot_request.room_id,
        group_id=slot_request.group_id,
        day_of_week=slot_request.day_of_week,
        start_time=slot_request.start_time,
        end_time=slot_request.end_time,
        session_type=slot_request.session_type
    )

    db.add(new_slot)
    db.commit()
    db.refresh(new_slot)

    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="CREATE",
        resource_type="manual_timetable_slot",
        resource_id=new_slot.id,
        details={
            "timetable_id": timetable_id,
            "course_id": new_slot.course_id,
            "group_id": new_slot.group_id,
            "session_type": new_slot.session_type,
        },
    )
    
    return new_slot




@router.post("/api/v1/validate/slot", status_code=status.HTTP_200_OK)
async def validate_slot(
    slot_data: dict,
    timetable_id: int,
    exclude_slot_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate a timetable slot assignment before saving.
    Returns validation errors and warnings.
    """
    validator = ValidationService(db)
    is_valid, validation_errors = validator.validate_timetable_slot(
        slot_data, timetable_id, exclude_slot_id
    )
    
    # Categorize by severity
    errors_by_severity = {"error": [], "warning": [], "info": []}
    for error in validation_errors:
        severity = error.get("severity", "error")
        errors_by_severity[severity].append(error)
    
    return {
        "valid": is_valid,
        "total_issues": len(validation_errors),
        "errors": errors_by_severity["error"],
        "warnings": errors_by_severity["warning"],
        "info": errors_by_severity["info"]
    }


@router.get("/api/v1/validate/timetable/{timetable_id}", status_code=status.HTTP_200_OK)
async def validate_timetable(
    timetable_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate an entire timetable for all constraints.
    Returns comprehensive validation report.
    """
    # Check if timetable exists
    timetable = filter_timetable_query_for_user(
        db.query(TimetableModel).filter(TimetableModel.id == timetable_id),
        current_user,
    ).first()
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    # Run validation
    validator = ValidationService(db)
    validation_report = validator.validate_entire_timetable(timetable_id)
    
    return validation_report


# ---------------------------------------------------------------------------
# Version Management Endpoints
# ---------------------------------------------------------------------------

@router.get("/{timetable_id}/versions", status_code=status.HTTP_200_OK)
async def get_timetable_versions(
    timetable_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all versions for a timetable.
    Returns version history with metadata.
    """
    # Check if timetable exists
    timetable = filter_timetable_query_for_user(
        db.query(TimetableModel).filter(TimetableModel.id == timetable_id),
        current_user,
    ).first()
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    version_service = VersionService(db)
    versions = version_service.get_versions(timetable_id)
    
    return {
        "timetable_id": timetable_id,
        "timetable_name": timetable.name,
        "versions": versions
    }


@router.post("/{timetable_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_timetable_version(
    timetable_id: int,
    description: Optional[str] = None,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db)
):
    """
    Create a new version snapshot of the timetable.
    Coordinator only.
    """
    # Check if timetable exists
    timetable = filter_timetable_query_for_user(
        db.query(TimetableModel).filter(TimetableModel.id == timetable_id),
        current_user,
    ).first()
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    try:
        version_service = VersionService(db)
        version = version_service.create_version(timetable_id, current_user.id, description)
        
        return {
            "status": "success",
            "message": "Version created successfully",
            "version": {
                "id": version.id,
                "version_number": version.version_number,
                "description": version.description,
                "created_at": version.created_at
            }
        }
    except ValueError:
        raise HTTPException(status_code=404, detail="Timetable not found.")


@router.get("/{timetable_id}/versions/{version_id}", status_code=status.HTTP_200_OK)
async def get_timetable_version(
    timetable_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific version details.
    """
    version_service = VersionService(db)
    version = version_service.get_version(version_id)
    
    if not version or version.timetable_id != timetable_id:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # Get creator info
    creator = db.query(User).filter(User.id == version.created_by_id).first()
    
    return {
        "id": version.id,
        "version_number": version.version_number,
        "description": version.description,
        "created_at": version.created_at,
        "created_by": {
            "id": creator.id,
            "username": creator.username,
            "full_name": creator.full_name
        } if creator else None,
        "snapshot_data": version.snapshot_data
    }


@router.post("/{timetable_id}/versions/{version_id}/restore", status_code=status.HTTP_200_OK)
async def restore_timetable_version(
    timetable_id: int,
    version_id: int,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db)
):
    """
    Restore a timetable to a previous version.
    Creates a backup of the current state before restoring.
    Coordinator only.
    """
    try:
        version_service = VersionService(db)
        result = version_service.restore_version(timetable_id, version_id, current_user.id)
        
        # Get timetable details for notification
        timetable = filter_timetable_query_for_user(
            db.query(TimetableModel).filter(TimetableModel.id == timetable_id),
            current_user,
        ).first()
        
        # Send notification to coordinators
        notification_service = NotificationService(db)
        notification_service.notify_coordinators(
            title="Timetable Version Restored",
            message=f"The timetable '{timetable.name}' has been restored to version {result.get('version_number')}.",
            type="warning",
            action_link=f"/timetables",
            send_email=False
        )
        
        return result
    except ValueError:
        raise HTTPException(status_code=404, detail="Timetable or version not found.")


@router.get("/{timetable_id}/versions/compare", status_code=status.HTTP_200_OK)
async def compare_timetable_versions(
    timetable_id: int,
    version1_id: int = Query(..., description="First version ID"),
    version2_id: int = Query(..., description="Second version ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compare two versions of a timetable.
    Returns added, removed, and modified slots.
    """
    try:
        version_service = VersionService(db)
        comparison = version_service.compare_versions(timetable_id, version1_id, version2_id)
        return comparison
    except ValueError:
        raise HTTPException(status_code=404, detail="Version not found.")


@router.delete("/{timetable_id}/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timetable_version(
    timetable_id: int,
    version_id: int,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db)
):
    """
    Delete a specific version.
    Coordinator only.
    """
    version_service = VersionService(db)
    version = version_service.get_version(version_id)
    
    if not version or version.timetable_id != timetable_id:
        raise HTTPException(status_code=404, detail="Version not found")
    
    success = version_service.delete_version(version_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete version")


# ===========================================================================
# DRAG-AND-DROP OVERRIDE ENDPOINTS
# Agent Beta scope — these endpoints manage the coordinator's manual position
# overrides.  They do NOT touch the solver or any constraint data.
# Overrides are stored as a JSON dict inside timetable.generation_metadata
# under the key "overrides".  This keeps the feature 100% reversible and
# avoids any schema migrations.
#
# Override format stored in generation_metadata:
# {
#   "overrides": {
#     "<slot_id>": {
#       "day": "TUESDAY",
#       "start_time": "10:00",
#       "end_time": "12:00",
#       "room": null,            <- null means keep the original room
#       "overridden_by": <user_id>,
#       "overridden_at": "<ISO timestamp>"
#     },
#     ...
#   }
# }
# ===========================================================================

@router.post(
    "/{timetable_id}/overrides",
    status_code=status.HTTP_200_OK,
    tags=["timetables", "drag-and-drop"],
)
async def apply_slot_overrides(
    timetable_id: int,
    request_body: ApplyOverridesRequest,
    request: Request,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db),
):
    """
    **Drag-and-Drop Override — Batch Upsert**

    Saves one or more slot position overrides onto the active timetable's
    `generation_metadata['overrides']` dict.

    Rules enforced server-side:
    - The timetable must exist and be active.
    - Every `slot_id` in the payload must belong to this timetable.
    - `day` must be one of: MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY.
    - `start_time` and `end_time` must be valid HH:MM strings with end > start.
    - Sending the same `slot_id` in a subsequent request replaces the previous
      override (upsert semantics) — safe for rapid drag-and-drop autosave.

    This endpoint never runs the CP-SAT solver.
    """
    from datetime import datetime

    VALID_DAYS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"}

    # 1. Resolve timetable
    timetable = db.query(TimetableModel).filter(
        TimetableModel.id == timetable_id
    ).first()
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")

    # 2. Validate each override in the batch
    valid_slot_ids = {
        row[0]
        for row in db.query(TimetableSlot.id)
        .filter(TimetableSlot.timetable_id == timetable_id)
        .all()
    }

    errors = []
    for ov in request_body.overrides:
        if ov.slot_id not in valid_slot_ids:
            errors.append(f"slot_id {ov.slot_id} does not belong to timetable {timetable_id}")
            continue
        if ov.day.upper() not in VALID_DAYS:
            errors.append(f"slot_id {ov.slot_id}: '{ov.day}' is not a valid day")
            continue
        try:
            t_start = datetime.strptime(ov.start_time, "%H:%M")
            t_end = datetime.strptime(ov.end_time, "%H:%M")
            if t_end <= t_start:
                errors.append(
                    f"slot_id {ov.slot_id}: end_time must be after start_time"
                )
        except ValueError:
            errors.append(
                f"slot_id {ov.slot_id}: start_time/end_time must be HH:MM format"
            )

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Override validation failed", "errors": errors},
        )

    # 3. Upsert into generation_metadata — copy first to avoid SQLAlchemy
    #    mutation-tracking issues with nested dicts.
    import copy
    meta = copy.deepcopy(timetable.generation_metadata or {})
    stored_overrides: dict = meta.setdefault("overrides", {})
    now_iso = datetime.utcnow().isoformat()

    applied: list[int] = []
    for ov in request_body.overrides:
        stored_overrides[str(ov.slot_id)] = {
            "day": ov.day.upper(),
            "start_time": ov.start_time,
            "end_time": ov.end_time,
            "room": ov.room,
            "overridden_by": current_user.id,
            "overridden_at": now_iso,
        }
        applied.append(ov.slot_id)

    timetable.generation_metadata = meta
    db.commit()

    # 4. Audit trail
    AuditLogger.log_event(
        event_type="TIMETABLE_OVERRIDE_APPLIED",
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        action="POST",
        resource=f"/api/v1/timetables/{timetable_id}/overrides",
        details={"timetable_id": timetable_id, "slot_ids": applied, "count": len(applied)},
        success=True,
    )

    return {
        "status": "success",
        "message": f"{len(applied)} override(s) applied",
        "applied_slot_ids": applied,
        "timetable_id": timetable_id,
    }


@router.delete(
    "/{timetable_id}/overrides/{slot_id}",
    status_code=status.HTTP_200_OK,
    tags=["timetables", "drag-and-drop"],
)
async def reset_slot_override(
    timetable_id: int,
    slot_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db),
):
    """
    **Drag-and-Drop Override — Reset Single Slot**

    Removes the manual override for a slot, restoring it to the solver-
    generated position.  If the slot had no override, returns 200 anyway
    (idempotent).
    """
    import copy

    timetable = db.query(TimetableModel).filter(
        TimetableModel.id == timetable_id
    ).first()
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")

    meta = copy.deepcopy(timetable.generation_metadata or {})
    stored_overrides = meta.get("overrides", {})
    was_present = str(slot_id) in stored_overrides

    if was_present:
        del stored_overrides[str(slot_id)]
        meta["overrides"] = stored_overrides
        timetable.generation_metadata = meta
        db.commit()

    AuditLogger.log_event(
        event_type="TIMETABLE_OVERRIDE_RESET",
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        action="DELETE",
        resource=f"/api/v1/timetables/{timetable_id}/overrides/{slot_id}",
        details={"timetable_id": timetable_id, "slot_id": slot_id, "had_override": was_present},
        success=True,
    )

    return {
        "status": "success",
        "slot_id": slot_id,
        "was_overridden": was_present,
        "message": "Override removed. Slot reverted to solver position." if was_present else "Slot had no override.",
    }


@router.get(
    "/{timetable_id}/overrides",
    status_code=status.HTTP_200_OK,
    tags=["timetables", "drag-and-drop"],
)
async def get_slot_overrides(
    timetable_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Drag-and-Drop Override — Read All**

    Returns the full overrides map for a timetable so the frontend can
    hydrate its local state on mount.
    """
    timetable = db.query(TimetableModel).filter(
        TimetableModel.id == timetable_id
    ).first()
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")

    overrides = (timetable.generation_metadata or {}).get("overrides", {})
    return {
        "timetable_id": timetable_id,
        "override_count": len(overrides),
        "overrides": overrides,
    }
