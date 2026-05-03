from ..celery_app import celery_app
from ..utils.email_service import EmailService
import logging

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.send_verification_email")
def send_verification_email_task(recipient: str, organization_name: str, verification_link: str):
    """
    Celery task to send a registration verification email asynchronously.
    """
    logger.info(f"Sending verification email to {recipient} for {organization_name}")
    try:
        success = EmailService.send_registration_verification(
            recipient=recipient,
            organization_name=organization_name,
            verification_link=verification_link
        )
        if success:
            logger.info("Verification email dispatched successfully.")
        else:
            logger.warning("EmailService could not dispatch email (SMTP might not be configured).")
        return success
    except Exception as e:
        logger.error(f"Failed to send verification email inside Celery task: {e}")
        return False
