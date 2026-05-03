"""
Notifications Router

Handles notification CRUD operations and user notification management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..models import User
from ..auth import get_current_user
from ..services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", status_code=status.HTTP_200_OK)
@router.get("/", status_code=status.HTTP_200_OK)
async def get_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get notifications for the current user.
    
    Query params:
    - unread_only: Only return unread notifications
    - limit: Maximum number of notifications (default 50)
    """
    notification_service = NotificationService(db)
    notifications = notification_service.get_user_notifications(
        current_user.id,
        unread_only,
        limit
    )
    
    return {
        "notifications": notifications,
        "total": len(notifications)
    }


@router.get("/unread-count", status_code=status.HTTP_200_OK)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get count of unread notifications for the current user.
    """
    notification_service = NotificationService(db)
    count = notification_service.get_unread_count(current_user.id)
    
    return {"unread_count": count}


@router.post("/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a notification as read.
    """
    notification_service = NotificationService(db)
    success = notification_service.mark_as_read(notification_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Notification not found or does not belong to this user"
        )
    
    return {"status": "success", "message": "Notification marked as read"}


@router.post("/mark-all-read", status_code=status.HTTP_200_OK)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark all notifications as read for the current user.
    """
    notification_service = NotificationService(db)
    count = notification_service.mark_all_as_read(current_user.id)
    
    return {
        "status": "success",
        "message": f"{count} notification(s) marked as read",
        "count": count
    }


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a notification.
    """
    notification_service = NotificationService(db)
    success = notification_service.delete_notification(notification_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Notification not found or does not belong to this user"
        )


@router.post("/test", status_code=status.HTTP_201_CREATED)
async def create_test_notification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a test notification for the current user (for testing).
    """
    notification_service = NotificationService(db)
    notification = notification_service.create_notification(
        user_id=current_user.id,
        title="Test Notification",
        message="This is a test notification to verify the notification system is working correctly.",
        type="info",
        action_link="/dashboard"
    )
    
    return {
        "status": "success",
        "message": "Test notification created",
        "notification": {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "type": notification.type,
            "created_at": notification.created_at
        }
    }
