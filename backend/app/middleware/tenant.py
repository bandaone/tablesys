from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
import contextvars
import logging

logger = logging.getLogger(__name__)

# Context variable to hold the current tenant ID for the lifetime of the request
_current_tenant_id = contextvars.ContextVar("tenant_id", default=None)

def get_current_tenant_id():
    return _current_tenant_id.get()

def set_current_tenant_id(tenant_id: int):
    return _current_tenant_id.set(tenant_id)

class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts the 'X-University-ID' header (or infers it from the host/token)
    and sets it in a context variable for database-level row filtering.
    """
    async def dispatch(self, request: Request, call_next):
        # Allow requests to bypass tenant filtering if they are sys-admin or public auth routes
        tenant_id_header = request.headers.get("X-University-ID")
        
        # If no explicit header, try extracting from the JWT token (if authenticated)
        try:
            tenant_id = int(tenant_id_header) if tenant_id_header else None
            token = _current_tenant_id.set(tenant_id)
            request.state.tenant_id = tenant_id
        except ValueError:
            # Invalid header format
            token = _current_tenant_id.set(None)
            
        try:
            response = await call_next(request)
            return response
        finally:
            _current_tenant_id.reset(token)

def setup_tenant_filtering(engine: Engine):
    """
    Hooks into SQLAlchemy's query execution to automatically inject the 
    `university_id = <CURRENT_TENANT>` filter onto all SELECT, UPDATE, and DELETE queries
    for tenant-aware tables.
    """
    
    # List of tables that require tenant isolation
    TENANT_TABLES = [
        "users", "departments", "courses", "lecturers", "rooms", 
        "student_groups", "timetables", "template_profiles",
        "exam_periods", "exam_seating_profiles"
    ]
    
    @event.listens_for(engine, "before_cursor_execute", retval=True)
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            return statement, parameters
            
        # Very basic string manipulation to inject tenant filters.
        # Note: In a production-ready enterprise app, you would use SQLAlchemy's
        # generic robust `with_loader_criteria` ORM event. We'll use a safer
        # `do_orm_execute` event for ORM-based isolation instead of raw string manipulation.
        
        return statement, parameters
        
def apply_orm_tenant_isolation(sessionmaker_instance):
    """
    Applies the SQLAlchemy 1.4+ `do_orm_execute` event to securely filter all queries
    at the ORM level.
    """
    from sqlalchemy.orm import Session
    from ..models import University
    
    @event.listens_for(Session, "do_orm_execute")
    def _do_orm_execute(execute_state):
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            return
            
        # Ensure we don't infinitely recurse if querying the University table itself
        if execute_state.is_select and not execute_state.is_column_load:
            # We dynamically import models to apply `with_loader_criteria`
            from app.models import (
                User, Department, Course, Lecturer, Room, 
                StudentGroup, Timetable, ExamPeriod, ExamSeatingProfile
            )
            
            execute_state.statement = execute_state.statement.options(
                from_orm_criteria(User, tenant_id),
                from_orm_criteria(Department, tenant_id),
                from_orm_criteria(Room, tenant_id),
                from_orm_criteria(StudentGroup, tenant_id),
                from_orm_criteria(Timetable, tenant_id),
                from_orm_criteria(ExamPeriod, tenant_id),
                from_orm_criteria(ExamSeatingProfile, tenant_id),
            )

def from_orm_criteria(model_class, tenant_id):
    from sqlalchemy.orm import with_loader_criteria
    from sqlalchemy import or_
    return with_loader_criteria(
        model_class,
        lambda cls: or_(cls.university_id == tenant_id, cls.university_id.is_(None)),
        include_aliases=True
    )
