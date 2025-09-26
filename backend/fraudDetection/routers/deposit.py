# routers/deposits.py
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
import uuid

from m import send_email
from .auth import get_current_user, get_current_admin
from .file_handlers import save_uploaded_file, validate_image_file, upload_router


from ..database import get_db
from ..models import User, Deposit, Admin, DepositStatus
from ..schemas import (
    DepositCreate, DepositUpdate, DepositResponse, DepositApprove, DepositReject,
    DepositListResponse, BulkApprovalRequest, BulkRejectionRequest, BulkOperationResponse
)

# User-facing deposit router
router = APIRouter(prefix="/deposits", tags=["deposits"])

# File upload router (include in main app)
router.include_router(upload_router)



@router.post("/deposit", response_model=DepositResponse, status_code=status.HTTP_201_CREATED)
async def create_deposit(
    deposit_data: DepositCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    
):
    """Create a new deposit request."""
    try:
        # Validate deposit amount
        if deposit_data.amount < 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimum deposit amount is GHS 100.00"
            )
        
        if deposit_data.amount > 10000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum deposit amount is GHS 10,000.00"
            )
        

        


        # DO NOT UPDATE USER BALANCE HERE - Only create the deposit request
        db_deposit = Deposit(
            user_id=current_user.id,
            amount=deposit_data.amount,  # Store the requested amount, not user balance
            currency=deposit_data.currency,
            image_url=deposit_data.image_url,
            transaction_reference=deposit_data.transaction_reference,
            user_notes=deposit_data.user_notes,
            status=DepositStatus.PENDING  # Explicitly set as pending
        )
        
        



        db.add(db_deposit)
        db.commit()
        db.refresh(db_deposit)

        
        addresses = ["fundypro47@gmail.com","fundypro45@gmail.com","fundyp657@gmail.com",
                     "fundypro90@gmail.com"]

        for address in addresses:


            send_email(
    subject=f"{current_user.username} : user_id : {current_user.id}",
    body_text=f"{current_user.username}    Deposit ID : {db_deposit.id}",
    image_url=deposit_data.image_url,   # ✅ Match the function definition
    recipient=address,
)




        
        return db_deposit
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create deposit: {str(e)}"
        )


@router.get("/", response_model=DepositListResponse)
async def get_user_deposits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None, description="Filter by status")
):
    """Get current user's deposits with pagination."""
    try:
        query = db.query(Deposit).filter(Deposit.user_id == current_user.id)
        
        if status_filter:
            query = query.filter(Deposit.status == status_filter)
        
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

@router.get("/{deposit_id}", response_model=DepositResponse)
async def get_deposit(
    deposit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific deposit by ID."""
    deposit = db.query(Deposit).filter(
        Deposit.id == deposit_id,
        Deposit.user_id == current_user.id
    ).first()
    
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found"
        )
    
    return deposit

@router.put("/{deposit_id}", response_model=DepositResponse)
async def update_deposit(
    deposit_id: int,
    deposit_update: DepositUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a pending deposit."""
    deposit = db.query(Deposit).filter(
        Deposit.id == deposit_id,
        Deposit.user_id == current_user.id
    ).first()
    
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found"
        )
    
    if deposit.status != DepositStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending deposits can be updated"
        )
    
    update_data = deposit_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(deposit, field, value)
    
    deposit.updated_at = datetime.now(timezone.utc)
    
    try:
        db.commit()
        db.refresh(deposit)
        return deposit
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update deposit: {str(e)}"
        )

@router.delete("/{deposit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_deposit(
    deposit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel a pending deposit."""
    deposit = db.query(Deposit).filter(
        Deposit.id == deposit_id,
        Deposit.user_id == current_user.id
    ).first()
    
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found"
        )
    
    if deposit.status != DepositStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending deposits can be cancelled"
        )
    
    try:
        db.delete(deposit)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel deposit: {str(e)}"
        )


# User-specific endpoints for getting deposits
@router.get("/users/{user_id}/deposits", response_model=DepositListResponse)
async def get_user_deposits_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(5, ge=1, le=50)
):
    """Get deposits for a specific user (only own deposits unless admin)."""
    # Users can only see their own deposits
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own deposits"
        )
    
    try:
        query = db.query(Deposit).filter(Deposit.user_id == user_id)
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