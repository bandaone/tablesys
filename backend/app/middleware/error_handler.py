"""
Centralized error handling middleware for TABLESYS.

Features:
- Catches all unhandled exceptions
- Returns consistent JSON error format
- Hides sensitive details in production
- Logs all errors with request context
- Custom exception classes for business logic
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import traceback
from datetime import datetime
import uuid
from ..config import settings
from ..utils.logging_utils import set_request_id
from ..utils.audit_logger import AuditLogger

logger = logging.getLogger("app")


# ============================================================================
# CUSTOM EXCEPTION CLASSES (Simplified)
# ============================================================================

class AppException(Exception):
    """Base exception with status code"""
    status_code = 500
    
    def __init__(self, message: str = None, detail: dict = None):
        self.message = message or "An error occurred"
        self.detail = detail or {}
        super().__init__(self.message)


class ValidationError(AppException):
    """Raised when input validation fails (400 Bad Request)"""
    status_code = 400


class AuthenticationError(AppException):
    """Raised when authentication fails (401 Unauthorized)"""
    status_code = 401


class AuthorizationError(AppException):
    """Raised when user lacks permission (403 Forbidden)"""
    status_code = 403


class NotFoundError(AppException):
    """Raised when resource not found (404 Not Found)"""
    status_code = 404


class ConflictError(AppException):
    """Raised when resource conflict occurs (409 Conflict)"""
    status_code = 409


# ============================================================================
# ERROR HANDLER MIDDLEWARE
# ============================================================================

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Centralized error handling middleware.
    
    Catches all exceptions and returns consistent JSON error responses.
    Logs all errors with full context for debugging.
    Hides sensitive details in production environment.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID for tracing
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        set_request_id(request_id)  # Set in context for automatic logging
        
        try:
            response = await call_next(request)
            return response
            
        except AppException as e:
            # Custom application exceptions (expected errors)
            logger.warning(
                f"Application error: {e.message}",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": e.status_code,
                    "detail": e.detail
                }
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "type": e.__class__.__name__,
                        "message": e.message,
                        "detail": e.detail if settings.ENVIRONMENT == "development" else {},
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "request_id": request_id
                    }
                }
            )
            
        except Exception as e:
            # Unexpected errors (bugs, infrastructure issues)
            logger.error(
                f"Unhandled exception: {str(e)}",
                exc_info=True,
                extra={
                    "path": request.url.path,
                    "method": request.method
                }
            )
            
            # Broadcast to World Monitor
            try:
                AuditLogger.log_system_error(
                    request=request,
                    error_message=str(e),
                    resource=str(request.url.path),
                )
            except Exception:
                pass
            
            # Production: Hide sensitive details
            if settings.ENVIRONMENT == "production":
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "error": {
                            "type": "InternalServerError",
                            "message": "An unexpected error occurred. Please try again later.",
                            "request_id": request_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z"
                        }
                    }
                )
            
            # Development: Show full details for debugging
            else:
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "error": {
                            "type": e.__class__.__name__,
                            "message": str(e),
                            "detail": traceback.format_exc(),
                            "request_id": request_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z"
                        }
                    }
                )
