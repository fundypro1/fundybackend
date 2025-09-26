# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from ..database import get_db
from ..models import User, Admin
from ..schemas import UserCreate, Login, Token, AdminLogin, AdminToken, UserResponse
from .auth import (
    authenticate_user, authenticate_admin, get_password_hash,
    create_user_token, create_admin_token, get_current_user
)

router = APIRouter()



@router.post("/login", response_model=Token)
async def login_user(login_data:OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user and return access token."""
    print(f"Login attempt for user: {login_data.username}")  # Debug
    
    user = authenticate_user(db, login_data.username, login_data.password)
    
    if not user:
        print(f"Authentication failed for user: {login_data.username}")  # Debug
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        print(f"Inactive user tried to login: {login_data.username}")  # Debug
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive"
        )
    
    # Create and return token
    token_data = create_user_token(user)
    print(f"Token created successfully for user: {user.username}")  # Debug
    
    return Token(
        access_token=token_data["access_token"],
        token_type=token_data["token_type"],
        user_id=token_data["user_id"],
        username=token_data["username"],
        expires_at=token_data["expires_at"]
    )

# OAuth2 compatible login endpoint
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """OAuth2 compatible login endpoint."""
    print(f"OAuth2 login attempt for user: {form_data.username}")  # Debug
    
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive"
        )
    
    token_data = create_user_token(user)
    
    return Token(
        access_token=token_data["access_token"],
        token_type=token_data["token_type"],
        user_id=token_data["user_id"],
        username=token_data["username"],
        expires_at=token_data["expires_at"]
    )

@router.post("/admin/login", response_model=AdminToken)
async def login_admin(login_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate admin and return access token."""
    print(f"Admin login attempt: {login_data.username}")  # Debug
    
    admin = authenticate_admin(db, login_data.username, login_data.password)
    print(admin)
    
    if not admin:
        print(f"Admin authentication failed: {login_data.username}")  # Debug
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not admin.is_active:
        print(f"Inactive admin tried to login: {login_data.username}")  # Debug
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account is inactive"
        )
    
    # Update last login time
    admin.last_login_at = datetime.now(timezone.utc)
    db.commit()
    
    # Create and return token
    token_data = create_admin_token(admin)
    print(f"Admin token created successfully: {admin.username}")  # Debug
    
    return AdminToken(
        access_token=token_data["access_token"],
        token_type=token_data["token_type"],
        admin_id=token_data["admin_id"],
        username=token_data["username"],
        role=token_data["role"],
        expires_at=token_data["expires_at"]
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    print(f"Getting user info for: {current_user.username}")  # Debug
    return current_user

@router.post("/logout")
async def logout():
    """Logout endpoint (client should discard token)."""
    return {"message": "Successfully logged out"}

@router.post("/refresh")
async def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh user access token."""
    print(f"Refreshing token for user: {current_user.username}")  # Debug
    
    # Create new token for the current user
    token_data = create_user_token(current_user)
    
    return Token(
        access_token=token_data["access_token"],
        token_type=token_data["token_type"],
        user_id=token_data["user_id"],
        username=token_data["username"],
        expires_at=token_data["expires_at"]
    )

# @router.get("/test")
# async def test_auth():
#     """Test endpoint to verify auth system is working."""
#     result = test_auth_system()
#     return {
#         "message": "Auth system test",
#         "working": result,
#         "status": "ok" if result else "error"
#     }

@router.get("/protected")
async def protected_route(current_user: User = Depends(get_current_user)):
    """Test protected route."""
    return {
        "message": f"Hello {current_user.username}!",
        "user_id": current_user.id,
        "balance": current_user.balance
    }