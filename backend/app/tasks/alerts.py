"""
Periodic alert-checking Celery task.
Runs every 2 minutes via Celery beat to evaluate all platform alert thresholds.
"""
from celery import shared_task
from app.database import SessionLocal
from app.services.alert_engine import AlertEngine


@shared_task(name="app.tasks.alerts.check_platform_alerts")
def check_platform_alerts():
    """Run the AlertEngine and persist/broadcast any new alerts."""
    db = SessionLocal()
    try:
        engine = AlertEngine(db)
        fired = engine.run()
        return {"fired": len(fired)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()
