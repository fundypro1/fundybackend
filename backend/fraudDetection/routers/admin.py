from decimal import Decimal
from operator import or_
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from .. import schemas, models
from ..hashing import Hash
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import database
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from ..database import get_db
from ..models import Admin, Deposit, DepositStatus, User, Withdrawal, WithdrawalStatus
from ..schemas import AdminCreate, AdminResponse, BulkApprovalRequest, BulkOperationResponse, BulkRejectionRequest, DepositApprove, DepositListResponse, DepositReject, UserCreate, UserListResponse, UserResponse, UserUpdate,DepositResponse, WithdrawalApprove, WithdrawalListResponse, WithdrawalReject, WithdrawalResponse
from .auth import get_current_user, get_current_admin


get_db = database.get_db

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


@router.post("/create_admin", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
async def register_admin(admin_data: AdminCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    try:
        existing_user = db.query(Admin).filter(Admin.username == admin_data.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # Check if email already exists
        existing_email = db.query(Admin).filter(Admin.email == admin_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        

        hashed_password = Hash.hash(admin_data.password)
        db_admin = Admin(
            username=admin_data.username,
            email=admin_data.email,
            password=hashed_password,
            first_name=admin_data.first_name,
            last_name= admin_data.last_name,
        )
        
        db.add(db_admin )
        db.commit()
        db.refresh(db_admin)
        
        return db_admin 
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )
    





# Admin router for deposit management

@router.get("admin/deposit", response_model=DepositListResponse)
async def get_all_deposits(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    amount_min: Optional[float] = Query(None),
    amount_max: Optional[float] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get all deposits for admin review with advanced filtering."""
    try:
        query = db.query(Deposit)
        
        # Apply filters
        if status_filter:
            query = query.filter(Deposit.status == status_filter)
        if user_id:
            query = query.filter(Deposit.user_id == user_id)
        if amount_min:
            query = query.filter(Deposit.amount >= amount_min)
        if amount_max:
            query = query.filter(Deposit.amount <= amount_max)
        if date_from:
            try:
                from_date = datetime.fromisoformat(date_from)
                query = query.filter(Deposit.created_at >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.fromisoformat(date_to)
                query = query.filter(Deposit.created_at <= to_date)
            except ValueError:
                pass
        
        total = query.count()
        deposits = query.order_by(Deposit.created_at.desc()).offset((page - 1) * size).limit(size).all()
        
        return DepositListResponse(
            items=deposits,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deposits: {str(e)}"
        )

@router.get("/deposit/{deposit_id}", response_model=DepositResponse)
async def get_deposit_admin(
    deposit_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Get a specific deposit by ID (admin view)."""
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found"
        )
    
    return deposit

@router.post("/{deposit_id}/approve", response_model=DepositResponse)
async def approve_deposit(
    deposit_id: int,
    approval_data: DepositApprove,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Approve a deposit and update user balance."""
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found"
        )
    
    if deposit.status != DepositStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending deposits can be approved"
        )
    
    try:
        # Get the user
        user = db.query(User).filter(User.id == deposit.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Approve deposit first
        deposit.approve(current_admin.id, approval_data.admin_notes)
        
        # ONLY NOW update user balance after approval
        user.balance += float(deposit.amount)
        # Mark deposit as completed
        deposit.complete()
        
        db.commit()
        db.refresh(deposit)
        db.refresh(user)
        
        return deposit
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve deposit: {str(e)}"
        )

@router.post("/{deposit_id}/reject", response_model=DepositResponse)
async def reject_deposit(
    deposit_id: int,
    rejection_data: DepositReject,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Reject a deposit with reason."""
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found"
        )
    
    if deposit.status != DepositStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending deposits can be rejected"
        )
    
    try:
        # Reject deposit
        deposit.reject(current_admin.id, rejection_data.rejection_reason)
        
        db.commit()
        db.refresh(deposit)
        
        return deposit
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject deposit: {str(e)}"
        )

@router.post("/bulk-approve", response_model=BulkOperationResponse)
async def bulk_approve_deposits(
    bulk_data: BulkApprovalRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Bulk approve multiple deposits."""
    successful = []
    failed = []
    
    for deposit_id in bulk_data.ids:
        try:
            deposit = db.query(Deposit).filter(
                Deposit.id == deposit_id,
                Deposit.status == DepositStatus.PENDING
            ).first()
            
            if not deposit:
                failed.append({
                    "id": deposit_id,
                    "error": "Deposit not found or not pending"
                })
                continue
            
            # Get the user
            user = db.query(User).filter(User.id == deposit.user_id).first()
            if not user:
                failed.append({
                    "id": deposit_id,
                    "error": "User not found"
                })
                continue
            
            # Approve deposit
            deposit.approve(current_admin.id, bulk_data.admin_notes)
            
            # ONLY update user balance after approval
            user.balance += float(deposit.amount)
            
            # Mark as completed
            deposit.complete()
            successful.append(deposit_id)
            
        except Exception as e:
            failed.append({
                "id": deposit_id,
                "error": str(e)
            })
    
    try:
        db.commit()
        
        return BulkOperationResponse(
            successful=successful,
            failed=failed,
            total_processed=len(bulk_data.ids),
            message=f"Successfully processed {len(successful)} out of {len(bulk_data.ids)} deposits"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk operation failed: {str(e)}"
        )

@router.post("/bulk-reject", response_model=BulkOperationResponse)
async def bulk_reject_deposits(
    bulk_data: BulkRejectionRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Bulk reject multiple deposits."""
    successful = []
    failed = []
    
    for deposit_id in bulk_data.ids:
        try:
            deposit = db.query(Deposit).filter(
                Deposit.id == deposit_id,
                Deposit.status == DepositStatus.PENDING
            ).first()
            
            if not deposit:
                failed.append({
                    "id": deposit_id,
                    "error": "Deposit not found or not pending"
                })
                continue
            
            # Reject deposit
            deposit.reject(current_admin.id, bulk_data.rejection_reason)
            successful.append(deposit_id)
            
        except Exception as e:
            failed.append({
                "id": deposit_id,
                "error": str(e)
            })
    
    try:
        db.commit()
        
        return BulkOperationResponse(
            successful=successful,
            failed=failed,
            total_processed=len(bulk_data.ids),
            message=f"Successfully processed {len(successful)} out of {len(bulk_data.ids)} deposits"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk operation failed: {str(e)}"
        )


# 3️⃣ Admin - Approve Withdrawal
@router.post("/{withdrawal_id}/withdraw-approve", response_model=WithdrawalResponse)
def approve_withdrawal(
    withdrawal_id: int,
    approval: WithdrawalApprove,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Admin approves a withdrawal (deducts balance)."""
    withdrawal = db.query(Withdrawal).filter(
        Withdrawal.id == withdrawal_id
    ).first()

    if not withdrawal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Withdrawal not found"
        )

    if withdrawal.status != WithdrawalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending withdrawals can be approved"
        )

    # Deduct balance here (on approval)
    user = db.query(User).filter(User.id == withdrawal.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if Decimal(str(user.balance)) < withdrawal.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance for approval")

    user.balance = Decimal(str(user.balance)) - withdrawal.amount

    # Mark as approved
    withdrawal.approve(admin_id=current_admin.id, notes=approval.admin_notes)

    db.commit()
    db.refresh(withdrawal)

    return withdrawal



# 4️⃣ Admin - Reject Withdrawal
@router.post("/{withdrawal_id}/withdraw-reject", response_model=WithdrawalResponse)
def reject_withdrawal(
    withdrawal_id: int,
    rejection: WithdrawalReject,   # we can reuse the same schema since it has admin_notes
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Admin rejects a withdrawal request."""
    withdrawal = db.query(Withdrawal).filter(
        Withdrawal.id == withdrawal_id
    ).first()

    if not withdrawal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Withdrawal not found"
        )

    if withdrawal.status != WithdrawalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending withdrawals can be rejected"
        )

    # Call model's reject method
    withdrawal.reject(admin_id=current_admin.id, rejection_reason=rejection.rejection_reason)

    db.commit()
    db.refresh(withdrawal)

    return withdrawal


# 5️⃣ Admin - Mark as Completed
@router.post("/{withdrawal_id}/complete", response_model=WithdrawalResponse)
def complete_withdrawal(
    withdrawal_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Admin marks an approved withdrawal as completed (final step)."""
    withdrawal = db.query(Withdrawal).filter(
        Withdrawal.id == withdrawal_id,
        Withdrawal.status == WithdrawalStatus.APPROVED
    ).first()

    if not withdrawal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Withdrawal not found or not approved yet"
        )

    withdrawal.complete()
    withdrawal.processed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(withdrawal)

    return withdrawal




@router.get("/deposit", response_model=DepositListResponse)  # Remove "admin/" prefix
async def get_all_deposits(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    image_url: Optional[str] =Query(None),
    user_id: Optional[int] = Query(None),
    amount_min: Optional[float] = Query(None),
    amount_max: Optional[float] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get all deposits for admin review with advanced filtering."""
    try:
        query = db.query(Deposit)
        
        # Apply filters
        if status_filter:
            query = query.filter(Deposit.status == status_filter)
        if user_id:
            query = query.filter(Deposit.user_id == user_id)
        if amount_min:
            query = query.filter(Deposit.amount >= amount_min)
        if amount_max:
            query = query.filter(Deposit.amount <= amount_max)
        if image_url:
            query= query.filter(Deposit.image_url==image_url)
        if date_from:
            try:
                from_date = datetime.fromisoformat(date_from)
                query = query.filter(Deposit.created_at >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.fromisoformat(date_to)
                query = query.filter(Deposit.created_at <= to_date)
            except ValueError:
                pass
        
        total = query.count()
        deposits = query.order_by(Deposit.created_at.desc()).offset((page - 1) * size).limit(size).all()
        
        return DepositListResponse(
            items=deposits,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deposits: {str(e)}"
        )

# Add missing withdrawal endpoints
@router.get("/withdrawals", response_model=WithdrawalListResponse)
async def get_all_withdrawals(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    amount_min: Optional[float] = Query(None),
    amount_max: Optional[float] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get all withdrawals for admin review with advanced filtering."""
    try:
        query = db.query(Withdrawal)
        
        # Apply filters
        if status_filter:
            query = query.filter(Withdrawal.status == status_filter)
        if user_id:
            query = query.filter(Withdrawal.user_id == user_id)
        if amount_min:
            query = query.filter(Withdrawal.amount >= amount_min)
        if amount_max:
            query = query.filter(Withdrawal.amount <= amount_max)
        if date_from:
            try:
                from_date = datetime.fromisoformat(date_from)
                query = query.filter(Withdrawal.created_at >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.fromisoformat(date_to)
                query = query.filter(Withdrawal.created_at <= to_date)
            except ValueError:
                pass
        
        total = query.count()
        withdrawals = query.order_by(Withdrawal.created_at.desc()).offset((page - 1) * size).limit(size).all()
        
        return WithdrawalListResponse(
            items=withdrawals,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch withdrawals: {str(e)}"
        )

@router.get("/withdrawals/{withdrawal_id}", response_model=WithdrawalResponse)
async def get_withdrawal_admin(
    withdrawal_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Get a specific withdrawal by ID (admin view)."""
    withdrawal = db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).first()
    
    if not withdrawal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Withdrawal not found"
        )
    
    return withdrawal

# Add users endpoint
@router.get("/users", response_model=UserListResponse)
async def get_all_users(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None)
):
    """Get all users for admin management."""
    try:
        query = db.query(User)
        
        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term),
                    func.concat(User.first_name, ' ', User.last_name).ilike(search_term)
                )
            )
        
        total = query.count()
        users = query.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size).all()
        
        return UserListResponse(
            items=users,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )

# Add bulk operations for deposits (fix the request structure)
@router.post("/deposits/bulk-approve", response_model=BulkOperationResponse)
async def bulk_approve_deposits(
    bulk_data: BulkApprovalRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Bulk approve multiple deposits."""
    successful = []
    failed = []
    
    # Fix: use deposit_ids instead of ids to match frontend
    deposit_ids = bulk_data.deposit_ids if hasattr(bulk_data, 'deposit_ids') else bulk_data.ids
    
    for deposit_id in deposit_ids:
        try:
            deposit = db.query(Deposit).filter(
                Deposit.id == deposit_id,
                Deposit.status == DepositStatus.PENDING
            ).first()
            
            if not deposit:
                failed.append({
                    "id": deposit_id,
                    "error": "Deposit not found or not pending"
                })
                continue
            
            # Get the user
            user = db.query(User).filter(User.id == deposit.user_id).first()
            if not user:
                failed.append({
                    "id": deposit_id,
                    "error": "User not found"
                })
                continue
            
            # Approve deposit
            deposit.approve(current_admin.id, bulk_data.admin_notes)
            
            # Update user balance after approval
            user.balance += float(deposit.amount)
            
            # Mark as completed
            deposit.complete()
            successful.append(deposit_id)
            
        except Exception as e:
            failed.append({
                "id": deposit_id,
                "error": str(e)
            })
    
    try:
        db.commit()
        
        return BulkOperationResponse(
            successful=successful,
            failed=failed,
            total_processed=len(deposit_ids),
            message=f"Successfully processed {len(successful)} out of {len(deposit_ids)} deposits"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk operation failed: {str(e)}"
        )

@router.post("/deposits/bulk-reject", response_model=BulkOperationResponse)
async def bulk_reject_deposits(
    bulk_data: BulkRejectionRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Bulk reject multiple deposits."""
    successful = []
    failed = []
    
    # Fix: use deposit_ids instead of ids to match frontend
    deposit_ids = bulk_data.deposit_ids if hasattr(bulk_data, 'deposit_ids') else bulk_data.ids
    
    for deposit_id in deposit_ids:
        try:
            deposit = db.query(Deposit).filter(
                Deposit.id == deposit_id,
                Deposit.status == DepositStatus.PENDING
            ).first()
            
            if not deposit:
                failed.append({
                    "id": deposit_id,
                    "error": "Deposit not found or not pending"
                })
                continue
            
            # Reject deposit
            deposit.reject(current_admin.id, bulk_data.rejection_reason)
            successful.append(deposit_id)
            
        except Exception as e:
            failed.append({
                "id": deposit_id,
                "error": str(e)
            })
    
    try:
        db.commit()
        
        return BulkOperationResponse(
            successful=successful,
            failed=failed,
            total_processed=len(deposit_ids),
            message=f"Successfully processed {len(successful)} out of {len(deposit_ids)} deposits"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk operation failed: {str(e)}"
        )





# 1. Put static routes FIRST
@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Get detailed user registration statistics (admin only)."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    inactive_users = db.query(User).filter(User.is_active == False).count()

    today = datetime.now(timezone.utc).date()
    users_today = db.query(User).filter(func.date(User.created_at) == today).count()

    current_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    users_this_month = db.query(User).filter(User.created_at >= current_month).count()

    users_with_balance = db.query(User).filter(User.balance > 0).count()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "users_registered_today": users_today,
        "users_registered_this_month": users_this_month,
        "users_with_balance": users_with_balance,
    }

# 2. Dynamic route AFTER
@router.get("/{admin_id}", response_model=AdminResponse)
async def get_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)  # protect with admin token
):
    """Fetch admin profile by ID."""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    return admin

