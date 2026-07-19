import json
import redis
from datetime import datetime, timezone
from celery import shared_task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.timetable_generator import TimetableGenerator
from app.services.generation_observability import finalize_generation_run, mark_generation_started
from app.models import Timetable, Course, TimetableSlot
from app.config import settings
from app.middleware.tenant import set_current_tenant_id
from app.services.notification_service import NotificationService
from app.middleware.tenant import _current_tenant_id
import time

try:
    from app.observability import task_queue_time_histogram, task_processing_time_histogram
except ImportError:
    pass

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

@shared_task(bind=True)
def generate_timetable_task(self, timetable_id: int, components: list = None, university_id: int = 1, user_id: int = None, profile: str = "balanced"):
    """
    Background task to generate a timetable.
    """
    start_time = time.time()
    
    # 1. Establish tenant isolation for this background thread
    token = set_current_tenant_id(university_id)
    
    db = SessionLocal()
    try:
        timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
        if not timetable:
            return {"status": "error", "message": f"Timetable {timetable_id} not found."}
        mark_generation_started(
            timetable,
            mode="async",
            started_at=datetime.fromtimestamp(start_time, tz=timezone.utc),
            components=components,
            job_id=self.request.id,
        )
        db.commit()

        # 2. Redis-backed progress callback
        def progress_callback(progress_data: dict):
            # Append progress event to a Redis List
            key = f"job:{self.request.id}:progress"
            redis_client.rpush(key, json.dumps(progress_data))
            # Keep progress data for 1 hour after it's logged
            redis_client.expire(key, 3600)

        # 3. Spin up generator
        generator = TimetableGenerator(
            db=db,
            timetable_id=timetable_id,
            progress_callback=progress_callback,
            components=components,
            profile=profile
        )
        
        success = generator.generate_timetable()
        saved_slot_count = db.query(TimetableSlot).filter(TimetableSlot.timetable_id == timetable_id).count()
        
        # 4. Handle results
        if success and saved_slot_count > 0:
            levels_processed = [v[0] for v in db.query(Course.level).distinct().all() if v[0] is not None]
            levels_processed.sort(reverse=True)
            meta = dict(timetable.generation_metadata or {})
            meta.update({
                'generated': True,
                'levels_processed': levels_processed,
                'component_layers': generator._component_sequence(),
                'job_id': self.request.id,
                'solver_status_by_level': generator.solver_status_by_level,
                'fallback_levels': generator.fallback_levels,
                'generation_diagnostics': generator.generation_diagnostics,
                'slot_annotations': generator.saved_slot_annotations,
                'cleared_slot_counts': generator.cleared_slot_counts,
                'saved_slot_count': saved_slot_count,
            })
            timetable.generation_metadata = meta
            finalize_generation_run(
                db,
                timetable,
                tenant_id=university_id,
                success=True,
                started_at=datetime.fromtimestamp(start_time, tz=timezone.utc),
                mode="async",
                components=components,
                job_id=self.request.id,
                saved_slot_count=saved_slot_count,
                solver_status_by_level=generator.solver_status_by_level,
                fallback_levels=generator.fallback_levels,
                diagnostics=generator.generation_diagnostics,
                status_override="degraded" if getattr(generator, "is_degraded", False) else None,
            )
            db.commit()
            
            if user_id:
                notification_service = NotificationService(db)
                notification_service.notify_coordinators(
                    title="Timetable Generated (Async)",
                    message=f"The timetable '{timetable.name}' has been successfully generated in the background.",
                    type="success",
                    action_link=f"/timetables",
                    send_email=False
                )
            
            final_status = "degraded" if getattr(generator, "is_degraded", False) else "success"
            return {"status": final_status, "timetable_id": timetable_id, "saved_slot_count": saved_slot_count}
        else:
            meta = dict(timetable.generation_metadata or {})
            meta.update({
                'generated': False,
                'component_layers': generator._component_sequence(),
                'job_id': self.request.id,
                'solver_status_by_level': generator.solver_status_by_level,
                'fallback_levels': generator.fallback_levels,
                'generation_diagnostics': generator.generation_diagnostics,
                'slot_annotations': generator.saved_slot_annotations,
                'cleared_slot_counts': generator.cleared_slot_counts,
                'saved_slot_count': saved_slot_count,
            })
            timetable.generation_metadata = meta
            finalize_generation_run(
                db,
                timetable,
                tenant_id=university_id,
                success=False,
                started_at=datetime.fromtimestamp(start_time, tz=timezone.utc),
                mode="async",
                components=components,
                job_id=self.request.id,
                saved_slot_count=saved_slot_count,
                error_message="Failed to generate timetable due to constraints." if not success else "Generation completed without producing any timetable slots.",
                solver_status_by_level=generator.solver_status_by_level,
                fallback_levels=generator.fallback_levels,
                diagnostics=generator.generation_diagnostics,
            )
            db.commit()
            if success and saved_slot_count == 0:
                return {
                    "status": "error",
                    "message": "Generation completed without producing any timetable slots.",
                    "timetable_id": timetable_id,
                    "saved_slot_count": saved_slot_count,
                }
            return {"status": "error", "message": "Failed to generate timetable due to constraints.", "saved_slot_count": saved_slot_count}
            
    except Exception as e:
        import traceback
        import logging
        logging.error(f"Timetable generation failed: {str(e)}\n{traceback.format_exc()}")
        error_msg = str(e) if isinstance(e, ValueError) else "An unexpected error occurred during timetable generation. Please contact support."
        db.rollback()
        try:
            timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
            if timetable:
                finalize_generation_run(
                    db,
                    timetable,
                    tenant_id=university_id,
                    success=False,
                    started_at=datetime.fromtimestamp(start_time, tz=timezone.utc),
                    mode="async",
                    components=components,
                    job_id=self.request.id,
                    error_message=error_msg,
                )
                db.commit()
        except Exception:
            db.rollback()
        return {"status": "error", "message": error_msg}
    finally:
        db.close()
        _current_tenant_id.reset(token)
        try:
            tags = {"tenant_id": str(university_id), "task_type": "generate_timetable"}
            task_processing_time_histogram.record((time.time() - start_time) * 1000, tags)
        except NameError: pass
