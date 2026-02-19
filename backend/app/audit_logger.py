"""HIPAA-compliant audit logging utility."""

import psycopg
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json
import os
from app.database import CONNECTION_STRING
from app.phi_scrubber import PHIScrubber

class AuditLogger:
    """Centralized audit logger for HIPAA compliance."""
    
    @staticmethod
    def log(
        username: str,
        user_role: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """Log an audit event with PHI scrubbing."""
        try:
            conn = psycopg.connect(CONNECTION_STRING,sslmode="require")
            cursor = conn.cursor()
            
            # Scrub PHI from details
            scrubbed_details = PHIScrubber.scrub_for_logging(details) if details else None
            
            cursor.execute('''
                INSERT INTO audit_logs 
                (timestamp, username, user_role, ip_address, action, 
                 resource_type, resource_id, details, status, session_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                datetime.now(timezone.utc),
                username,
                user_role,
                ip_address,
                action,
                resource_type,
                resource_id,
                json.dumps(scrubbed_details) if scrubbed_details else None,
                status,
                session_id
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"[AUDIT LOG ERROR] Failed to log event: {e}")
            
    @staticmethod
    def log_authentication(username: str, action: str, status: str, ip_address: Optional[str] = None, details: Optional[Dict] = None):
        """Log authentication events."""
        AuditLogger.log(
            username=username,
            user_role="unknown",  # Role not known until after successful login
            action=action,  # "login_attempt", "login_success", "login_failure", "logout", "mfa_setup", etc.
            resource_type="authentication",
            status=status,
            ip_address=ip_address,
            details=details
        )
    
    @staticmethod
    def log_phi_access(username: str, user_role: str, action: str, patient_id: str, details: Optional[Dict] = None, ip_address: Optional[str] = None):
        """Log access to Protected Health Information."""
        AuditLogger.log(
            username=username,
            user_role=user_role,
            action=action,  # "view_patient", "update_patient", "delete_patient", "export_data"
            resource_type="patient",
            resource_id=patient_id,
            status="success",
            ip_address=ip_address,
            details=details
        )
    
    @staticmethod
    def log_gpt_request(username: str, user_role: str, patient_id: Optional[str], conversation_id: str, prompt_length: int, response_length: int, ip_address: Optional[str] = None):
        """Log requests to GPT that may contain PHI."""
        AuditLogger.log(
            username=username,
            user_role=user_role,
            action="gpt_request",
            resource_type="ai_interaction",
            resource_id=conversation_id,
            details={
                "patient_id": patient_id,
                "prompt_length": prompt_length,
                "response_length": response_length,
                "model": "gpt-4"
            },
            status="success",
            ip_address=ip_address,
            session_id=conversation_id
        )
    
    @staticmethod
    def log_database_operation(username: str, user_role: str, operation: str, table: str, record_id: Optional[str] = None, before: Optional[Dict] = None, after: Optional[Dict] = None):
        """Log database operations on sensitive tables."""
        AuditLogger.log(
            username=username,
            user_role=user_role,
            action=f"db_{operation}",  # "db_insert", "db_update", "db_delete"
            resource_type=f"table_{table}",
            resource_id=record_id,
            details={
                "before": before,
                "after": after
            },
            status="success"
        )