"""Helpers to retrieve and format service user profiles and outreach lists."""

import os
import psycopg
from psycopg.rows import dict_row
from app.database import CONNECTION_STRING

def get_all_service_users(provider_username, organization):
    """Get all service users for a given provider with their latest outreach details."""

    conn = psycopg.connect(CONNECTION_STRING)
    conn.row_factory = dict_row  # Return results as dictionaries
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT DISTINCT ON (p.service_user_id) 
           p.service_user_id, p.service_user_name, p.location, p.status, 
           o.last_session, o.check_in, o.follow_up_message
    FROM profiles p
    LEFT JOIN outreach_details o ON p.service_user_id = o.service_user_id
    WHERE p.provider = %s
    ORDER BY p.service_user_id, o.created_at DESC NULLS LAST
    ''', (provider_username,))
    
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append(dict(row))
    
    return result

def get_all_outreach(provider_username, organization):
    """Get all outreach details for service users of a given provider."""    
    conn = psycopg.connect(CONNECTION_STRING)
    conn.row_factory = dict_row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT p.service_user_id, p.service_user_name as name, o.last_session, o.check_in, o.follow_up_message
    FROM outreach_details o
    JOIN profiles p ON o.service_user_id = p.service_user_id
    WHERE p.provider = %s
    ''', (provider_username,))
    
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append(dict(row))
    
    return result