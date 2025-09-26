# auth.py - Separate tokens for users and admins
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Admin

# Configuration
SECRET_KEY_USER = "83daa0256a2289b0fb23693bf1f6034d44396675749244721a2b20e896e11662"
SECRET_KEY_ADMIN = "83daa0256a2289a0fb23693bf1f6034d44396675749244721a2b20e896e11662123456"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES_USER = 60  # 24 hours for users
ACCESS_TOKEN_EXPIRE_MINUTES_ADMIN = 5  

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer(auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_user_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token specifically for users."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES_USER)
    
    to_encode.update({
        "exp": expire, 
        "iat": datetime.now(timezone.utc),
        "token_class": "user"  # Identifier for token type
    })
    
    # Use USER secret key
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY_USER, algorithm=ALGORITHM)
    return encoded_jwt

def create_admin_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token specifically for admins."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES_ADMIN)
    
    to_encode.update({
        "exp": expire, 
        "iat": datetime.now(timezone.utc),
        "token_class": "admin"  # Identifier for token type
    })
    
    # Use ADMIN secret key
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY_ADMIN, algorithm=ALGORITHM)
    return encoded_jwt

def verify_user_token(token: str) -> Optional[dict]:
    """Verify and decode a USER JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY_USER, algorithms=[ALGORITHM])
        # Check if it's a user token
        if payload.get("token_class") != "user":
            return None
        return payload
    except JWTError:
        return None

def verify_admin_token(token: str) -> Optional[dict]:
    """Verify and decode an ADMIN JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY_ADMIN, algorithms=[ALGORITHM])
        # Check if it's an admin token
        if payload.get("token_class") != "admin":
            return None
        return payload
    except JWTError:
        return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user using USER token."""
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
    
    token = credentials.credentials
    
    # Verify using USER secret key
    payload = verify_user_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token"
        )
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive"
        )
    
    return user

async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Admin:
    """Get current authenticated admin using ADMIN token."""
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
    
    token = credentials.credentials
    
    # Verify using ADMIN secret key
    payload = verify_admin_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )
    
    admin_id = payload.get("admin_id")
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token payload"
        )
    
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found"
        )
    
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account is inactive"
        )
    
    return admin

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user with username and password."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    return user

def authenticate_admin(db: Session, username: str, password: str) -> Optional[Admin]:
    """Authenticate an admin with username and password."""
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin:
        return None
    if not verify_password(password, admin.password):
        return None
    return admin

def create_user_token(user: User) -> dict:
    """Create USER access token with USER secret."""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES_USER)
    expires_at = datetime.now(timezone.utc) + access_token_expires
    
    token_data = {
        "sub": user.username,
        "user_id": user.id,
        "type": "user"
    }
    
    access_token = create_user_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "expires_at": expires_at,
        "token_class": "user"  # Indicate this is a user token
    }

def create_admin_token(admin: Admin) -> dict:
    """Create ADMIN access token with ADMIN secret."""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES_ADMIN)
    expires_at = datetime.now(timezone.utc) + access_token_expires
    
    token_data = {
        "sub": admin.username,
        "admin_id": admin.id,
        "role": admin.role.value,
        "type": "admin"
    }
    
    access_token = create_admin_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "admin_id": admin.id,
        "username": admin.username,
        "role": admin.role,
        "expires_at": expires_at,
        "token_class": "admin"  # Indicate this is an admin token
    }

# Utility function to identify token type without validation
def identify_token_type(token: str) -> str:
    """Identify if token is user or admin without full validation."""
    try:
        # Try to decode with user key first
        payload = jwt.decode(token, SECRET_KEY_USER, algorithms=[ALGORITHM], options={"verify_signature": False})
        token_class = payload.get("token_class", "unknown")
        if token_class == "user":
            return "user"
        
        # Try admin key
        payload = jwt.decode(token, SECRET_KEY_ADMIN, algorithms=[ALGORITHM], options={"verify_signature": False})
        token_class = payload.get("token_class", "unknown")
        if token_class == "admin":
            return "admin"
            
        return "unknown"
    except:
        return "invalid"