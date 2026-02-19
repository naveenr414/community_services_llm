"""Authentication utilities and FastAPI auth endpoints with MFA support."""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import timedelta
import jwt
from jwt.exceptions import InvalidTokenError
import os
from typing import Optional
from datetime import datetime, timezone
from app.database import CONNECTION_STRING
import hashlib
import secrets
import psycopg
import pyotp
import qrcode
import io
import base64
from app.audit_logger import AuditLogger


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 2 * 60  # 2 hours

# Global MFA toggle
MFA_GLOBALLY_ENABLED = True

router = APIRouter(prefix="/api/auth", tags=["authentication"])
security = HTTPBearer()

# Request/Response Models
class LoginRequest(BaseModel):
    username: str
    password: str
    mfa_code: Optional[str] = None

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    organization: str

class MFASetupResponse(BaseModel):
    qr_code: str
    secret: str

class MFAVerifyRequest(BaseModel):
    code: str

class UserData(BaseModel):
    username: str
    role: str
    organization: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    organization: Optional[str] = 'cspnj'

# JWT Token Verification
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserData:
    """Dependency to verify JWT token and extract user info."""
    token = credentials.credentials
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        organization: str = payload.get("organization")
        
        if username is None or role is None:
            raise credentials_exception
            
        return UserData(username=username, role=role, organization=organization)
    except InvalidTokenError:
        raise credentials_exception

# Login Endpoint
@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, req: Request):
    """Authenticate user and return JWT token"""
    
    ip_address = req.client.host if req.client else None
    
    # Log login attempt
    AuditLogger.log_authentication(
        username=request.username,
        action="login_attempt",
        status="in_progress",
        ip_address=ip_address
    )
    
    success, message, role, organization, mfa_enabled, mfa_secret = authenticate_user(
        request.username, 
        request.password
    )
    
    if not success:
        # Log failed login
        AuditLogger.log_authentication(
            username=request.username,
            action="login_failure",
            status="failure",
            ip_address=ip_address,
            details={"reason": "invalid_credentials"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check MFA
    if MFA_GLOBALLY_ENABLED and mfa_enabled:
        if not request.mfa_code:
            AuditLogger.log_authentication(
                username=request.username,
                action="mfa_required",
                status="pending",
                ip_address=ip_address
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MFA code required",
            )
        
        if not verify_mfa_code(mfa_secret, request.mfa_code):
            AuditLogger.log_authentication(
                username=request.username,
                action="mfa_failure",
                status="failure",
                ip_address=ip_address
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code",
            )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": request.username, "role": role, "organization": organization},
        expires_delta=access_token_expires
    )
    
    # Log successful login
    AuditLogger.log_authentication(
        username=request.username,
        action="login_success",
        status="success",
        ip_address=ip_address,
        details={
            "role": role,
            "organization": organization,
            "mfa_used": mfa_enabled
        }
    )

    return LoginResponse(
        access_token=access_token,
        role=role,
        organization=organization
    )
@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(current_user: UserData = Depends(get_current_user), req: Request = None):
    if not MFA_GLOBALLY_ENABLED:
        raise HTTPException(status_code=400, detail="MFA is disabled globally")

    secret = pyotp.random_base32()

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.username,
        issuer_name="PeerCopilot"
    )
    qr = qrcode.make(provisioning_uri)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()

    conn = psycopg.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET mfa_secret = %s WHERE username = %s",
        (secret, current_user.username)
    )
    conn.commit()
    conn.close()

    AuditLogger.log(
        username=current_user.username,
        user_role=current_user.role,
        action="mfa_setup_initiated",
        resource_type="security",
        status="success",
        ip_address=req.client.host if req and req.client else None
    )

    return MFASetupResponse(
        qr_code=f"data:image/png;base64,{img_str}",
        secret=secret
    )

# Update MFA enable endpoint:
@router.post("/mfa/enable")
async def enable_mfa(request: MFAVerifyRequest, current_user: UserData = Depends(get_current_user), req: Request = None):
    conn = psycopg.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    cursor.execute("SELECT mfa_secret FROM users WHERE username = %s", (current_user.username,))
    result = cursor.fetchone()

    if not result or not result[0]:
        conn.close()
        raise HTTPException(status_code=400, detail="MFA setup not initiated")

    if not verify_mfa_code(result[0], request.code):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid MFA code")

    cursor.execute("UPDATE users SET mfa_enabled = TRUE WHERE username = %s", (current_user.username,))
    conn.commit()
    conn.close()

    AuditLogger.log(
        username=current_user.username,
        user_role=current_user.role,
        action="mfa_enabled",
        resource_type="security",
        status="success",
        ip_address=req.client.host if req and req.client else None
    )

    return {"success": True, "message": "MFA enabled successfully"}


# MFA Disable
@router.post("/mfa/disable")
async def disable_mfa(
    request: MFAVerifyRequest,
    current_user: UserData = Depends(get_current_user)
):
    """Disable MFA"""
    
    conn = psycopg.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT mfa_secret FROM users WHERE username = %s",
        (current_user.username,)
    )
    result = cursor.fetchone()
    
    if not result or not result[0]:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA not enabled"
        )
    
    secret = result[0]
    
    if not verify_mfa_code(secret, request.code):
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code"
        )
    
    cursor.execute(
        "UPDATE users SET mfa_enabled = FALSE, mfa_secret = NULL WHERE username = %s",
        (current_user.username,)
    )
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "MFA disabled successfully"}

# MFA Status
@router.get("/mfa/status")
async def mfa_status(current_user: UserData = Depends(get_current_user)):
    """Check if MFA is enabled"""
    
    conn = psycopg.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT mfa_enabled FROM users WHERE username = %s",
        (current_user.username,)
    )
    result = cursor.fetchone()
    conn.close()
    
    return {
        "mfa_enabled": result[0] if result else False,
        "mfa_globally_enabled": MFA_GLOBALLY_ENABLED
    }

# Helper Functions
def verify_mfa_code(secret: str, code: str) -> bool:
    """Verify TOTP code"""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)

def authenticate_user(username, password):
    """Authenticate user"""
    conn = psycopg.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT username, password_hash, salt, role, organization, mfa_enabled, mfa_secret 
    FROM users 
    WHERE username = %s
    ''', (username,))
    
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return False, "Invalid username or password", None, None, False, None
    
    _, stored_password, stored_salt, role, organization, mfa_enabled, mfa_secret = user
    
    if verify_password(stored_password, stored_salt, password):
        return True, "Authentication successful", role, organization, mfa_enabled or False, mfa_secret
    else:
        return False, "Invalid username or password", None, None, False, None

def hash_password(password):
    """Create secure password hash"""
    salt = secrets.token_hex(16)
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), 
                                 salt.encode('utf-8'), 100000)
    return salt, pwdhash.hex()

def create_user(username, password, role='provider', organization='cspnj'):
    """Create new user"""
    conn = psycopg.connect(CONNECTION_STRING)
    cursor = conn.cursor()

    cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        conn.close()
        return False, "Username already exists"

    salt, password_hash = hash_password(password)

    try:
        cursor.execute('''
        INSERT INTO users (username, password_hash, salt, role, organization)
        VALUES (%s, %s, %s, %s, %s)
        ''', (username, password_hash, salt, role, organization))
        conn.commit()
        conn.close()
        return True, "User created successfully"
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Error creating user: {str(e)}"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(stored_password, stored_salt, provided_password):
    """Verify password"""
    pwdhash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), 
                                stored_salt.encode('utf-8'), 100000)
    return pwdhash.hex() == stored_password

@router.post("/register")
async def register(request: RegisterRequest):
    """Register new user"""
    success, message = create_user(
        username=request.username,
        password=request.password,
        role='provider',
        organization=request.organization
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    
    access_token = create_access_token(
        data={"sub": request.username, "role": "provider", "organization": request.organization},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return LoginResponse(
        access_token=access_token,
        role="provider",
        organization=request.organization
    )

@router.get("/me", response_model=UserData)
async def get_current_user_info(current_user: UserData = Depends(get_current_user)):
    """Get current user info"""
    return current_user