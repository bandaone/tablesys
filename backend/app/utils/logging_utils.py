"""
Logging utilities for TABLESYS.

Features:
- Request context filter (automatic request_id in all logs)
- Thread-safe request ID storage
- Helper functions for request tracking
"""

import logging
from contextvars import ContextVar
from typing import Optional


# Thread-safe request context storage
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class RequestContextFilter(logging.Filter):
    """
    Add request_id to all log records automatically.
    
    This filter ensures every log message includes the current request ID,
    making it easy to trace all logs related to a specific request.
    """
    
    def filter(self, record):
        record.request_id = request_id_var.get() or 'no-request'
        return True


def set_request_id(request_id: str):
    """
    Set request ID for current request context.
    
    Args:
        request_id: Unique identifier for the current request
    """
    request_id_var.set(request_id)


def get_request_id() -> str:
    """
    Get request ID for current request context.
    
    Returns:
        Current request ID or 'no-request' if not set
    """
    return request_id_var.get() or 'no-request'
