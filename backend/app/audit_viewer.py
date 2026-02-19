"""Audit log viewer and reporting for HIPAA compliance."""

from fastapi import APIRouter, Depends, HTTPException, Query
from app.login import get_current_user, UserData
import psycopg
from app.database import CONNECTION_STRING
from typing import Optional, List
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("/logs")
async def get_audit_logs(
    current_user: UserData = Depends(get_current_user),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    limit: int = Query(100, le=1000)
):
    """
    Get audit logs with filters.
    Requires admin role.
    """
    # Only admins can view audit logs
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = psycopg.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND timestamp >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND timestamp <= %s"
        params.append(end_date)
    
    if username:
        query += " AND username = %s"
        params.append(username)
    
    if action:
        query += " AND action = %s"
        params.append(action)
    
    if resource_type:
        query += " AND resource_type = %s"
        params.append(resource_type)
    
    query += " ORDER BY timestamp DESC LIMIT %s"
    params.append(limit)
    
    cursor.execute(query, params)
    
    columns = [desc[0] for desc in cursor.description]
    results = []
    for row in cursor.fetchall():
        results.append(dict(zip(columns, row)))
    
    conn.close()
    
    return {
        "logs": results,
        "count": len(results)
    }

@router.get("/suspicious-activity")
async def get_suspicious_activity(
    current_user: UserData = Depends(get_current_user),
    days: int = 7
):
    """
    Get suspicious activity report.
    Requires admin role.
    """
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = psycopg.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    # Failed logins
    cursor.execute('''
        SELECT username, COUNT(*) as failed_attempts, MAX(timestamp) as last_attempt
        FROM audit_logs
        WHERE action = 'login_failure' 
        AND timestamp > NOW() - INTERVAL '%s days'
        GROUP BY username
        HAVING COUNT(*) > 3
        ORDER BY failed_attempts DESC
    ''', (days,))
    
    failed_logins = cursor.fetchall()
    
    # After-hours access
    cursor.execute('''
        SELECT username, action, resource_type, resource_id, timestamp
        FROM audit_logs
        WHERE (EXTRACT(HOUR FROM timestamp) < 6 OR EXTRACT(HOUR FROM timestamp) > 22)
        AND action LIKE 'view%'
        AND timestamp > NOW() - INTERVAL '%s days'
        ORDER BY timestamp DESC
        LIMIT 50
    ''', (days,))
    
    after_hours = cursor.fetchall()
    
    conn.close()
    
    return {
        "failed_logins": [
            {"username": row[0], "attempts": row[1], "last_attempt": row[2]}
            for row in failed_logins
        ],
        "after_hours_access": [
            {
                "username": row[0],
                "action": row[1],
                "resource": f"{row[2]}:{row[3]}",
                "timestamp": row[4]
            }
            for row in after_hours
        ]
    }
