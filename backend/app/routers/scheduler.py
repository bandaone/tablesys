from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models import Timetable, User
from app.config import settings
from app.middleware.tenant import get_current_tenant_id
from app.tasks.generation import generate_timetable_task
from app.middleware.quota import enforce_generation_quota
import redis
import json
from datetime import datetime

router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def _normalize_hhmm(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot be empty")
    try:
        return datetime.strptime(text, "%H:%M").strftime("%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} must be in HH:MM format")


def _persist_generation_window(
    db: Session,
    timetable: Timetable,
    start_time: str = None,
    end_time: str = None,
    lunch_start: str = None,
    lunch_end: str = None,
) -> None:
    if start_time is None and end_time is None and lunch_start is None and lunch_end is None:
        return

    meta = dict(timetable.generation_metadata or {})
    existing_grid = meta.get("grid_config") if isinstance(meta.get("grid_config"), dict) else {}
    grid = dict(existing_grid)

    if start_time is not None:
        grid["start_time"] = _normalize_hhmm(start_time, "start_time")
    if end_time is not None:
        grid["end_time"] = _normalize_hhmm(end_time, "end_time")
    if lunch_start is not None:
        grid["lunch_start"] = _normalize_hhmm(lunch_start, "lunch_start")
    if lunch_end is not None:
        grid["lunch_end"] = _normalize_hhmm(lunch_end, "lunch_end")

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

@router.post("/generate/{timetable_id:int}")
def trigger_async_generation(
    timetable_id: int,
    components: str = None,
    start_time: str = Query(None, description="Generation start time in HH:MM format"),
    end_time: str = Query(None, description="Generation end time in HH:MM format"),
    lunch_start: str = Query(None, description="Lunch break start time in HH:MM format"),
    lunch_end: str = Query(None, description="Lunch break end time in HH:MM format"),
    profile: str = Query("balanced", description="Scheduling profile (balanced, compact, wellbeing)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trigger generation asynchronously via Celery + Redis.
    """
    timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")

    tenant_id = get_current_tenant_id() or getattr(current_user, "university_id", None)
    quota_info = enforce_generation_quota(db, tenant_id)

    # Persist coordinator-selected window before background task starts.
    _persist_generation_window(db, timetable, start_time, end_time, lunch_start, lunch_end)
        
    comp_list = [c.strip() for c in components.split(',')] if components else None
    try:
        from app.celery_app import celery_app
        task = celery_app.send_task(
            'app.tasks.generation.generate_timetable_task',
            kwargs={
                'timetable_id': timetable_id,
                'components': comp_list,
                'university_id': get_current_tenant_id(),
                'user_id': current_user.id,
                'profile': profile
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Broker error: {e}")
    
    response_payload = {
        "job_id": task.id, 
        "status": "started", 
        "message": "Timetable generation enqueued."
    }
    if quota_info:
        response_payload["quota"] = quota_info

    return response_payload

@router.get("/status/{job_id}")
def get_job_status(job_id: str, current_user: User = Depends(get_current_user)):
    """
    Poll job status and retrieve the latest CP-SAT solver progress.
    """
    from app.celery_app import celery_app
    task = celery_app.AsyncResult(job_id)
    
    # Read progress events from Redis
    progress_raw = redis_client.lrange(f"job:{job_id}:progress", 0, -1)
    progress_events = [json.loads(p) for p in progress_raw]
    
    return {
        "job_id": job_id,
        "state": task.state,
        "result": task.result if task.ready() else None,
        "progress": progress_events
    }

@router.delete("/cancel/{job_id}")
def cancel_job(job_id: str, current_user: User = Depends(get_current_user)):
    """
    Revokes the task from Celery. (Cannot reliably interrupt a running CP-SAT process).
    """
    from app.celery_app import celery_app
    celery_app.control.revoke(job_id, terminate=True)
    return {"message": "Job cancellation requested"}
