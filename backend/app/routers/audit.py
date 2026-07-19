"""
Audit Logs Router - System Activity Tracking API
Provides endpoints for viewing and managing audit logs
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import json
import asyncio
from datetime import datetime
import redis.asyncio as aioredis
from ..config import settings

from ..database import get_db
from ..auth import get_current_user
from ..models import User, AuditLog
from ..services.audit_service import AuditService


router = APIRouter(prefix="/api/v1/audit", tags=["audit-logs"])


# Pydantic models
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    user_email: Optional[str]
    action: str
    entity_type: str
    entity_id: Optional[int]
    entity_name: Optional[str]
    changes: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    tenant_name: Optional[str]
    timestamp: str
    status: str
    error_message: Optional[str]

    class Config:
        from_attributes = True


class RedisAuditConnectionManager:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.active_connections: List[WebSocket] = []
        self.pubsub_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"=== WS ADMIN CONNECTED! Total active: {len(self.active_connections)} ===", flush=True)
        if self.pubsub_task is None:
            self.pubsub_task = asyncio.create_task(self._listen())

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            if not self.active_connections and self.pubsub_task:
                self.pubsub_task.cancel()
                self.pubsub_task = None

    async def _listen(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("audit_stream")
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    data = message['data']
                    dead = []
                    for connection in list(self.active_connections):
                        try:
                            await connection.send_text(data)
                        except Exception as e:
                            dead.append(connection)
                    for d in dead:
                        self.disconnect(d)
        except asyncio.CancelledError:
            await pubsub.unsubscribe("audit_stream")

    async def broadcast(self, message: dict):
        await self.redis.publish("audit_stream", json.dumps(message))

audit_manager = RedisAuditConnectionManager(settings.REDIS_URL)

class AuditLogCreate(BaseModel):
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    entity_name: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None
    status: str = "success"
    error_message: Optional[str] = None


def require_admin_or_coordinator(current_user: User = Depends(get_current_user)):
    """
    Dependency to ensure only Admins, Coordinators, or Superadmins can access audit logs
    """
    allowed_roles = {"Admin", "Coordinator", "superadmin"}
    if current_user.role not in allowed_roles and str(current_user.role) not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and coordinators can access audit logs"
        )
    return current_user


@router.get("/", response_model=List[AuditLogResponse])
async def get_audit_logs(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_admin_or_coordinator),
    db: Session = Depends(get_db)
):
    """
    Get audit logs with optional filters
    
    Query Parameters:
    - user_id: Filter by user ID
    - action: Filter by action type (CREATE, UPDATE, DELETE, etc.)
    - entity_type: Filter by entity type (course, timetable, user, etc.)
    - status: Filter by status (success, failure, error)
    - start_date: Filter logs after this date (ISO format)
    - end_date: Filter logs before this date (ISO format)
    - limit: Maximum number of logs (default: 100, max: 1000)
    - offset: Pagination offset
    
    Returns array of audit log entries ordered by most recent first
    """
    if limit > 1000:
        limit = 1000
    
    service = AuditService(db)
    logs = service.get_logs(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        status=status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )
    
    return logs


@router.get("/statistics", response_model=Dict[str, Any])
async def get_audit_statistics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(require_admin_or_coordinator),
    db: Session = Depends(get_db)
):
    """
    Get audit log statistics
    
    Query Parameters:
    - start_date: Start date for statistics (ISO format)
    - end_date: End date for statistics (ISO format)
    
    Returns statistics including:
    - Total log count
    - Breakdown by action type
    - Breakdown by entity type
    - Breakdown by status
    - Number of unique users
    """
    service = AuditService(db)
    return service.get_statistics(start_date=start_date, end_date=end_date)


@router.get("/user/{user_id}", response_model=List[AuditLogResponse])
async def get_user_activity(
    user_id: int,
    limit: int = 50,
    current_user: User = Depends(require_admin_or_coordinator),
    db: Session = Depends(get_db)
):
    """
    Get recent activity for a specific user
    
    Path Parameters:
    - user_id: ID of the user
    
    Query Parameters:
    - limit: Maximum number of logs (default: 50, max: 200)
    
    Returns array of recent audit logs for the user
    """
    if limit > 200:
        limit = 200
    
    service = AuditService(db)
    return service.get_user_activity(user_id=user_id, limit=limit)


@router.get("/entity/{entity_type}/{entity_id}", response_model=List[AuditLogResponse])
async def get_entity_history(
    entity_type: str,
    entity_id: int,
    current_user: User = Depends(require_admin_or_coordinator),
    db: Session = Depends(get_db)
):
    """
    Get complete history of changes for a specific entity
    
    Path Parameters:
    - entity_type: Type of entity (course, timetable, user, etc.)
    - entity_id: ID of the entity
    
    Returns array of all audit logs for the entity ordered by most recent first
    """
    service = AuditService(db)
    return service.get_entity_history(entity_type=entity_type, entity_id=entity_id)


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    current_user: User = Depends(require_admin_or_coordinator),
    db: Session = Depends(get_db)
):
    """
    Get a specific audit log by ID
    
    Path Parameters:
    - log_id: ID of the audit log
    """
    service = AuditService(db)
    log = service.get_log_by_id(log_id)
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )
    
    return log


@router.post("/", response_model=AuditLogResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_log(
    log_data: AuditLogCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new audit log entry
    
    Note: This endpoint is primarily for internal use.
    Most audit logs are created automatically by the system.
    
    Request Body:
    - action: Action performed (CREATE, UPDATE, DELETE, etc.)
    - entity_type: Type of entity affected
    - entity_id: ID of the affected entity (optional)
    - entity_name: Name/identifier of the entity (optional)
    - changes: Dictionary of changes (optional)
    - status: Status of the action (default: success)
    - error_message: Error message if action failed (optional)
    """
    service = AuditService(db)
    
    # Get client IP and user agent
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get('user-agent')
    
    log = service.log_action(
        action=log_data.action,
        entity_type=log_data.entity_type,
        user_id=current_user.id,
        user_email=current_user.email,
        entity_id=log_data.entity_id,
        entity_name=log_data.entity_name,
        changes=log_data.changes,
        ip_address=ip_address,
        user_agent=user_agent,
        status=log_data.status,
        error_message=log_data.error_message
    )
    
    return log


@router.get("/export/json", response_class=Response)
async def export_audit_logs(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000,
    current_user: User = Depends(require_admin_or_coordinator),
    db: Session = Depends(get_db)
):
    """
    Export audit logs to JSON file
    
    Query Parameters: Same as GET / endpoint
    
    Returns JSON file download with audit logs
    """
    if limit > 5000:
        limit = 5000
    
    service = AuditService(db)
    logs = service.get_logs(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        status=status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=0
    )
    
    json_data = service.export_logs_to_json(logs)
    
    return Response(
        content=json_data,
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=audit_logs.json"
        }
    )


@router.delete("/cleanup", response_model=Dict[str, int])
async def cleanup_old_logs(
    days: int = 90,
    current_user: User = Depends(require_admin_or_coordinator),
    db: Session = Depends(get_db)
):
    """
    Delete audit logs older than specified days
    
    Query Parameters:
    - days: Number of days to keep (default: 90, min: 30)
    
    Note: This is a destructive operation. Use with caution.
    Only administrators should have access to this endpoint.
    
    Returns:
    - deleted_count: Number of logs deleted
    """
    # Require admin for deletion
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete audit logs"
        )
    
    if days < 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete logs newer than 30 days"
        )
    
    service = AuditService(db)
    deleted_count = service.delete_old_logs(days=days)
    
    # Log the cleanup action
    service.log_action(
        action="CLEANUP",
        entity_type="audit_log",
        user_id=current_user.id,
        user_email=current_user.email,
        changes={"days": days, "deleted_count": deleted_count},
        status="success"
    )
    
    return {
        "deleted_count": deleted_count,
        "message": f"Successfully deleted {deleted_count} logs older than {days} days"
    }

# ============================================================================
# WEBSOCKET STREAM
# ============================================================================

@router.websocket("/stream")
async def audit_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time system monitoring.
    Accepts connections from authorized admin/coordinator clients.
    Handles pings from the frontend keep-alive mechanism.
    """
    await audit_manager.connect(websocket)
    try:
        while True:
            # Wait for any incoming message (including client pings)
            data = await websocket.receive_text()
            # If it is a ping from the client, reply with a pong so the connection stays alive
            if data == 'ping':
                await websocket.send_text('pong')
    except WebSocketDisconnect:
        audit_manager.disconnect(websocket)
        print(f"=== WS CLIENT DISCONNECTED (normal). Active: {len(audit_manager.active_connections)} ===", flush=True)
    except Exception as e:
        print(f"=== WS STREAM ERROR: {str(e)} ===", flush=True)
        audit_manager.disconnect(websocket)
