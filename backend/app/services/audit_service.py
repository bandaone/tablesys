"""
Audit Service - System Activity Logging and Tracking
Logs all CRUD operations, authentication events, and critical actions
"""
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json

from ..models import AuditLog, User


class AuditService:
    """Service for logging and retrieving audit trail"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_action(
        self,
        action: str,
        entity_type: str,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        entity_id: Optional[int] = None,
        entity_name: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> AuditLog:
        """
        Log an action to the audit trail
        
        Args:
            action: Action performed (CREATE, UPDATE, DELETE, LOGIN, etc.)
            entity_type: Type of entity (course, timetable, user, etc.)
            user_id: ID of user who performed the action
            user_email: Email of user (for reference)
            entity_id: ID of the affected entity
            entity_name: Name/identifier of the entity
            changes: Dictionary of changes (before/after values)
            ip_address: Client IP address
            user_agent: Client user agent string
            status: Status of the action (success, failure, error)
            error_message: Error message if action failed
        
        Returns:
            Created AuditLog instance
        """
        log_entry = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow().isoformat(),
            status=status,
            error_message=error_message
        )
        
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        
        return log_entry
    
    def get_logs(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """
        Retrieve audit logs with optional filters
        
        Args:
            user_id: Filter by user ID
            action: Filter by action type
            entity_type: Filter by entity type
            status: Filter by status
            start_date: Filter logs after this date (ISO format)
            end_date: Filter logs before this date (ISO format)
            limit: Maximum number of logs to return
            offset: Number of logs to skip (pagination)
        
        Returns:
            List of AuditLog instances
        """
        query = self.db.query(AuditLog)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            query = query.filter(AuditLog.action == action)
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        if status:
            query = query.filter(AuditLog.status == status)
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        # Order by most recent first
        query = query.order_by(AuditLog.timestamp.desc())
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        return query.all()
    
    def get_log_by_id(self, log_id: int) -> Optional[AuditLog]:
        """
        Get a specific audit log by ID
        
        Args:
            log_id: ID of the audit log
        
        Returns:
            AuditLog instance or None if not found
        """
        return self.db.query(AuditLog).filter(AuditLog.id == log_id).first()
    
    def get_user_activity(
        self,
        user_id: int,
        limit: int = 50
    ) -> List[AuditLog]:
        """
        Get recent activity for a specific user
        
        Args:
            user_id: ID of the user
            limit: Maximum number of logs to return
        
        Returns:
            List of AuditLog instances for the user
        """
        return self.db.query(AuditLog).filter(
            AuditLog.user_id == user_id
        ).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    def get_entity_history(
        self,
        entity_type: str,
        entity_id: int
    ) -> List[AuditLog]:
        """
        Get complete history of changes for a specific entity
        
        Args:
            entity_type: Type of entity (course, timetable, etc.)
            entity_id: ID of the entity
        
        Returns:
            List of AuditLog instances for the entity
        """
        return self.db.query(AuditLog).filter(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id
        ).order_by(AuditLog.timestamp.desc()).all()
    
    def get_statistics(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get audit log statistics
        
        Args:
            start_date: Start date for statistics (ISO format)
            end_date: End date for statistics (ISO format)
        
        Returns:
            Dictionary with statistics
        """
        query = self.db.query(AuditLog)
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        total_logs = query.count()
        
        # Count by action
        actions_query = self.db.query(
            AuditLog.action,
            self.db.func.count(AuditLog.id).label('count')
        )
        if start_date:
            actions_query = actions_query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            actions_query = actions_query.filter(AuditLog.timestamp <= end_date)
        
        actions_count = {}
        for action, count in actions_query.group_by(AuditLog.action).all():
            actions_count[action] = count
        
        # Count by entity type
        entities_query = self.db.query(
            AuditLog.entity_type,
            self.db.func.count(AuditLog.id).label('count')
        )
        if start_date:
            entities_query = entities_query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            entities_query = entities_query.filter(AuditLog.timestamp <= end_date)
        
        entities_count = {}
        for entity_type, count in entities_query.group_by(AuditLog.entity_type).all():
            entities_count[entity_type] = count
        
        # Count by status
        status_query = self.db.query(
            AuditLog.status,
            self.db.func.count(AuditLog.id).label('count')
        )
        if start_date:
            status_query = status_query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            status_query = status_query.filter(AuditLog.timestamp <= end_date)
        
        status_count = {}
        for status, count in status_query.group_by(AuditLog.status).all():
            status_count[status] = count
        
        # Count unique users
        unique_users = query.filter(AuditLog.user_id.isnot(None)).distinct(
            AuditLog.user_id
        ).count()
        
        return {
            'total_logs': total_logs,
            'actions': actions_count,
            'entities': entities_count,
            'status': status_count,
            'unique_users': unique_users,
            'period': {
                'start': start_date,
                'end': end_date
            }
        }
    
    def export_logs_to_json(
        self,
        logs: List[AuditLog]
    ) -> str:
        """
        Export audit logs to JSON format
        
        Args:
            logs: List of AuditLog instances to export
        
        Returns:
            JSON string
        """
        export_data = []
        for log in logs:
            export_data.append({
                'id': log.id,
                'timestamp': log.timestamp,
                'user_id': log.user_id,
                'user_email': log.user_email,
                'action': log.action,
                'entity_type': log.entity_type,
                'entity_id': log.entity_id,
                'entity_name': log.entity_name,
                'changes': log.changes,
                'ip_address': log.ip_address,
                'status': log.status,
                'error_message': log.error_message
            })
        
        return json.dumps(export_data, indent=2, default=str)
    
    def delete_old_logs(
        self,
        days: int = 90
    ) -> int:
        """
        Delete audit logs older than specified days
        
        Args:
            days: Number of days to keep (default: 90)
        
        Returns:
            Number of logs deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        cutoff_iso = cutoff_date.isoformat()
        
        deleted_count = self.db.query(AuditLog).filter(
            AuditLog.timestamp < cutoff_iso
        ).delete()
        
        self.db.commit()
        
        return deleted_count
