"""
Security audit logging for TABLESYS.

Features:
- Comprehensive security event tracking
- JSON-formatted logs for easy parsing
- Authentication, data modification, and access events
- Search functionality for investigations
"""

import logging
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import Request
from .logging_utils import get_request_id
from ..routers.audit import audit_manager

# Global reference to the main ASGI event loop
_global_loop = None

def set_audit_loop(loop):
    global _global_loop
    _global_loop = loop


# Create dedicated audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)


class AuditLogger:
    """
    Centralized security audit logging.
    
    Tracks all security-relevant events for compliance and incident investigation.
    All events are logged in JSON format for easy parsing and analysis.
    """
    
    @staticmethod
    def log_event(
        event_type: str,
        request: Optional[Request] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True
    ):
        """
        Log a security audit event.
        
        Args:
            event_type: Type of event (e.g., LOGIN_SUCCESS, CREATE_COURSE)
            request: FastAPI request object (optional for background tasks)
            user_id: ID of user performing action
            username: Username of user performing action
            resource: Resource being accessed (defaults to request path)
            action: Action being performed (defaults to HTTP method)
            details: Additional event-specific details
            success: Whether the action succeeded
        """
        
        # Get client IP (handles proxies correctly)
        client_ip = "system"
        user_agent = "Background Worker"
        req_path = "/system/background"
        req_method = "SYSTEM"
        
        if request:
            client_ip = request.client.host if request and request.client else "unknown"
            if forwarded_for := request.headers.get("X-Forwarded-For"):
                client_ip = forwarded_for.split(",")[0].strip()
            user_agent = request.headers.get("User-Agent", "Unknown")
            req_path = str(request.url.path)
            req_method = request.method
        
        # Build audit log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "user_id": user_id,
            "username": username,
            "ip_address": client_ip,
            "user_agent": user_agent,
            "resource": resource or req_path,
            "action": action or req_method,
            "success": success,
            "details": details or {},
            "request_id": get_request_id()
        }
        
        # Log as JSON for easy parsing
        audit_logger.info(json.dumps(log_entry))
        
        # Broadcast to real-time WebSocket dashboard in the background
        # We use asyncio.create_task so it doesn't block the synchronous execution of log_event
        try:
            # Try to get the running loop (if we are in an async function)
            loop = asyncio.get_running_loop()
            loop.create_task(audit_manager.broadcast(log_entry))
        except RuntimeError:
            # We are likely in a synchronous thread pool (e.g., standard def router)
            try:
                # Fall back to the globally captured ASGI loop
                global _global_loop
                if _global_loop and _global_loop.is_running():
                    asyncio.run_coroutine_threadsafe(audit_manager.broadcast(log_entry), _global_loop)
            except Exception as e:
                audit_logger.error(f"Audit WS Broadcast failed: {e}")
    
    # ========================================================================
    # CONVENIENCE METHODS FOR COMMON EVENTS
    # ========================================================================
    
    @staticmethod
    def log_login_attempt(
        request: Request,
        username: str,
        success: bool,
        details: Optional[Dict] = None
    ):
        """
        Log login attempt (success or failure).
        
        Args:
            request: FastAPI request object
            username: Username attempting to login
            success: Whether login succeeded
            details: Additional details (user_id, role, etc.)
        """
        AuditLogger.log_event(
            event_type="LOGIN_SUCCESS" if success else "LOGIN_FAILURE",
            request=request,
            username=username,
            resource="/api/auth/login",
            action="POST",
            details=details or {},
            success=success
        )
    
    @staticmethod
    def log_logout(request: Request, user_id: int, username: str):
        """
        Log logout event.
        
        Args:
            request: FastAPI request object
            user_id: ID of user logging out
            username: Username logging out
        """
        AuditLogger.log_event(
            event_type="LOGOUT",
            request=request,
            user_id=user_id,
            username=username,
            resource="/api/auth/logout",
            action="POST"
        )
    
    @staticmethod
    def log_data_modification(
        request: Request,
        user_id: int,
        username: str,
        operation: str,  # CREATE, UPDATE, DELETE
        resource_type: str,  # course, lecturer, room, etc.
        resource_id: Optional[int] = None,
        details: Optional[Dict] = None
    ):
        """
        Log data modification event.
        
        Args:
            request: FastAPI request object
            user_id: ID of user performing modification
            username: Username performing modification
            operation: Type of operation (CREATE, UPDATE, DELETE)
            resource_type: Type of resource being modified
            resource_id: ID of resource being modified
            details: Additional details about the modification
        """
        AuditLogger.log_event(
            event_type=f"{operation}_{resource_type.upper()}",
            request=request,
            user_id=user_id,
            username=username,
            details={
                "resource_type": resource_type,
                "resource_id": resource_id,
                **(details or {})
            }
        )
    
    @staticmethod
    def log_bulk_upload(
        request: Request,
        user_id: int,
        username: str,
        resource_type: str,
        count: int,
        success: bool,
        details: Optional[Dict] = None
    ):
        """
        Log bulk upload event.
        
        Args:
            request: FastAPI request object
            user_id: ID of user performing upload
            username: Username performing upload
            resource_type: Type of resource being uploaded
            count: Number of records uploaded
            success: Whether upload succeeded
            details: Additional details (filename, errors, etc.)
        """
        AuditLogger.log_event(
            event_type=f"BULK_UPLOAD_{resource_type.upper()}",
            request=request,
            user_id=user_id,
            username=username,
            details={
                "resource_type": resource_type,
                "count": count,
                **(details or {})
            },
            success=success
        )
    
    @staticmethod
    def log_rate_limit_block(request: Request, username: Optional[str] = None):
        """
        Log rate limit block event.
        
        Args:
            request: FastAPI request object
            username: Username being rate limited (if known)
        """
        AuditLogger.log_event(
            event_type="RATE_LIMIT_BLOCK",
            request=request,
            username=username,
            success=False
        )
    
    @staticmethod
    def log_timetable_generation(
        request: Request,
        user_id: int,
        username: str,
        timetable_id: int,
        success: bool,
        details: Optional[Dict] = None
    ):
        """
        Log timetable generation event.
        
        Args:
            request: FastAPI request object
            user_id: ID of user generating timetable
            username: Username generating timetable
            timetable_id: ID of generated timetable
            success: Whether generation succeeded
            details: Additional details (duration, conflicts, etc.)
        """
        AuditLogger.log_event(
            event_type="GENERATE_TIMETABLE",
            request=request,
            user_id=user_id,
            username=username,
            details={
                "timetable_id": timetable_id,
                **(details or {})
            },
            success=success
        )
    
    @staticmethod
    def log_system_error(
        request: Request,
        error_message: str,
        resource: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """
        Log system-level errors or backend exceptions.
        """
        AuditLogger.log_event(
            event_type="SYSTEM_ERROR",
            request=request,
            user_id=user_id,
            username=username,
            resource=resource,
            action="SCREAM",
            details={
                "error_message": error_message,
                **(details or {})
            },
            success=False
        )

    @staticmethod
    def log_engine_event(
        event_name: str,
        timetable_id: int,
        request: Optional[Request] = None,
        details: Optional[Dict] = None
    ):
        """
        Log granular engine events (e.g. Generation Step, Conflict Detected).
        """
        AuditLogger.log_event(
            event_type=f"ENGINE_{event_name.upper()}",
            request=request,
            resource="timetable_generator",
            action="PROCESS",
            details={
                "timetable_id": timetable_id,
            },
            success=True
        )


    @staticmethod
    def log_action(
        action: str,
        user_id: Optional[int] = None,
        details: Optional[Dict] = None
    ):
        """
        Log an explicit user action (e.g. from users router).
        """
        AuditLogger.log_event(
            event_type=action,
            user_id=user_id,
            resource="users_router",
            action="UPDATE_USER_STATE",
            details=details,
            success=True
        )

    # ========================================================================
    # SEARCH FUNCTIONALITY
    # ========================================================================
    
    @staticmethod
    def search_logs(
        event_type: Optional[str] = None,
        username: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Search audit logs (for admin dashboard or investigations).
        
        Args:
            event_type: Filter by event type
            username: Filter by username
            start_date: Filter by start date (ISO format)
            end_date: Filter by end date (ISO format)
            limit: Maximum number of results to return
        
        Returns:
            List of matching audit log entries
        """
        results = []
        
        try:
            with open("logs/audit.log", "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        
                        # Apply filters
                        if event_type and entry.get("event_type") != event_type:
                            continue
                        if username and entry.get("username") != username:
                            continue
                        if start_date and entry.get("timestamp", "") < start_date:
                            continue
                        if end_date and entry.get("timestamp", "") > end_date:
                            continue
                        
                        results.append(entry)
                        
                        # Limit results
                        if len(results) >= limit:
                            break
                            
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            # Log file doesn't exist yet
            pass
        
        return results
