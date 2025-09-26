from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from .. import schemas, models
from ..hashing import Hash
from sqlalchemy.orm import Session
from .. import database
from fastapi import Request
from fastapi.responses import HTMLResponse
# routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from ..database import get_db
from ..models import User, Deposit, Withdrawal
from ..schemas import UserCreate, UserResponse, UserUpdate, DepositResponse, WithdrawalResponse
from .auth import get_current_user, get_current_admin


get_db = database.get_db

router = APIRouter(
    prefix="/user",
    tags=["User"]
)

@router.get("/signup", response_class=HTMLResponse)
async def get_signup_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "signup.html",{"request": request})

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == user_data.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # Check if email already exists
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        hashed_password = Hash.hash(user_data.password)
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            password=hashed_password,
            phone=user_data.phone,
            balance=0.0,
            is_active=True
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        return db_user
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )
    



@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user's profile information."""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update current user's profile information."""
    try:
        # Check if username is being changed and if it already exists
        if user_update.username and user_update.username != current_user.username:
            existing_user = db.query(User).filter(
                User.username == user_update.username,
                User.id != current_user.id
            ).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
        
        # Check if email is being changed and if it already exists
        if user_update.email and user_update.email != current_user.email:
            existing_email = db.query(User).filter(
                User.email == user_update.email,
                User.id != current_user.id
            ).first()
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
        if user_update.phone and user_update.phone != current_user.phone:
            existing_phone = db.query(User).filter(
                User.phone == user_update.phone,
                User.id != current_user.id
            ).first()
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number already registered"
                )
        
        # Update fields
        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(current_user, field, value)
        
        print(update_data)
        current_user.updated_at = datetime.now()
        
        db.commit()
        db.refresh(current_user)
        print(current_user.phone)
        return current_user
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user by ID (only own profile unless admin)."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

# @router.get("/{user_id}/summary", response_model=AccountSummary)
# async def get_user_account_summary(
#     user_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     """Get comprehensive account summary for user."""
#     if current_user.id != user_id:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Access denied"
#         )
    
#     try:
#         # Get user
#         user = db.query(User).filter(User.id == user_id).first()
#         if not user:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="User not found"
#             )
        
#         # Get deposits and withdrawals
#         deposits = db.query(Deposit).filter(Deposit.user_id == user_id).all()
#         withdrawals = db.query(Withdrawal).filter(Withdrawal.user_id == user_id).all()
        
#         # Calculate totals
#         total_deposits = sum(float(d.amount) for d in deposits if d.status == "COMPLETED")
#         total_withdrawals = sum(float(w.amount) for w in withdrawals if w.status == "COMPLETED")
        
#         # Transaction stats from existing transactions
#         total_transfers_out = sum(t.amount for t in user.transactions if t.type == "TRANSFER_OUT")
#         total_transfers_in = sum(t.amount for t in user.transactions if t.type == "TRANSFER_IN")
        
#         # Counts
#         transaction_count = len(user.transactions)
#         pending_deposits = len([d for d in deposits if d.status == "PENDING"])
#         pending_withdrawals = len([w for w in withdrawals if w.status == "PENDING"])
        
#         return AccountSummary(
#             current_balance=float(user.balance),
#             total_deposits=total_deposits,
#             total_withdrawals=total_withdrawals,
#             total_transfers_out=total_transfers_out,
#             total_transfers_in=total_transfers_in,
#             transaction_count=transaction_count,
#             pending_deposits=pending_deposits,
#             pending_withdrawals=pending_withdrawals
#         )
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to get account summary: {str(e)}"
#         )

# @router.get("/{user_id}/transactions", response_model=List[ShowOrgTransaction])
# async def get_user_transactions(
#     user_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user),
#     limit: int = Query(50, ge=1, le=100),
#     offset: int = Query(0, ge=0)
# ):
#     """Get user's transaction history."""
#     if current_user.id != user_id:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Access denied"
#         )
    
#     try:
#         transactions = db.query(OrgTransaction).filter(
#             OrgTransaction.user_id == user_id
#         ).order_by(
#             OrgTransaction.timestamp.desc()
#         ).offset(offset).limit(limit).all()
        
#         return transactions
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to get transactions: {str(e)}"
#         )

@router.get("/{user_id}/deposits", response_model=List[DepositResponse])
async def get_user_deposits(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50),
    status_filter: Optional[str] = Query(None)
):
    """Get user's deposit history."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    try:
        query = db.query(Deposit).filter(Deposit.user_id == user_id)
        
        if status_filter:
            query = query.filter(Deposit.status == status_filter)
        
        deposits = query.order_by(Deposit.created_at.desc()).limit(limit).all()
        
        return deposits
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get deposits: {str(e)}"
        )

@router.get("/{user_id}/withdrawals", response_model=List[WithdrawalResponse])
async def get_user_withdrawals(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50),
    status_filter: Optional[str] = Query(None)
):
    """Get user's withdrawal history."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    try:
        query = db.query(Withdrawal).filter(Withdrawal.user_id == user_id)
        
        if status_filter:
            query = query.filter(Withdrawal.status == status_filter)
        
        withdrawals = query.order_by(Withdrawal.created_at.desc()).limit(limit).all()
        
        return withdrawals
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get withdrawals: {str(e)}"
        )

# Admin endpoints for user management
@router.get("/", response_model=List[UserResponse])
async def get_all_users(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin),  # Only admins can see all users
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None)
):
    """Get all users (admin only)."""
    try:
        query = db.query(User)
        
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                (User.username.ilike(search_filter)) |
                (User.email.ilike(search_filter))
            )
        
        users = query.offset(offset).limit(limit).all()
        return users
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get users: {str(e)}"
        )