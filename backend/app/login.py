import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
import jwt
from typing import Optional

DATABASE_PATH = "data/wellness_database.db"
SECRET_KEY = "your_secret_key_here"  # Change this in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

def hash_password(password):
    """Create secure password hash with salt
    
    Arguments:
        password: string, password to hash
    
    Returns: a secret salt and a hashed password under that salt"""
    salt = secrets.token_hex(16)
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), 
                                 salt.encode('utf-8'), 100000)
    return salt, pwdhash.hex()

def verify_password(stored_password, stored_salt, provided_password):
    """Verify password against stored hash
    
    Arguments:
        stored_password: string, some stored password
        stored_salt: Corresponding salt for that password
        provided_password: What the user entered
    
    Returns: Boolean, whether the provided_password = stored password"""
    pwdhash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), 
                                stored_salt.encode('utf-8'), 100000)
    return pwdhash.hex() == stored_password

def create_user(username, password, role='provider'):
    """Create a new user with secure password storage
    
    Arguments:
        username: string, username
        password: string, password
    
    Returns: Boolean success and string message 
    
    Side Effects: Create a new username + password"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return False, "Username already exists"
    
    salt, password_hash = hash_password(password)
    
    try:
        cursor.execute('''
        INSERT INTO users (username, password_hash, salt, role)
        VALUES (?, ?, ?, ?)
        ''', (username, password_hash, salt, role))
        conn.commit()
        conn.close()
        return True, "User created successfully"
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Error creating user: {str(e)}"

def authenticate_user(username, password):
    """Authenticate a username + password combo
    
    Arguments:
        username: string, username
        password: string, password
    
    Returns: Boolean success and string message 
    
    Side Effects: Checks if a username-password combo is valid"""

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT username, password_hash, salt, role FROM users 
    WHERE username = ?
    ''', (username,))
    
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return False, "Invalid username or password", None
    
    _, stored_password, stored_salt, role = user
    
    if verify_password(stored_password, stored_salt, password):
        return True, "Authentication successful", role
    else:
        return False, "Invalid username or password", None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT token for a given set of information
    
    Arguments:
        data: Username/authentication to encode
    
    Returns: Encoded version of data via JWT"""
    
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt