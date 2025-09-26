# routers/earnings.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, timezone

from ..database import get_db
from ..models import Earning, EarningStatus, Purchase
from ..schemas import createEarning
from .authentication import get_current_user
from ..models import User
from sqlalchemy import func


router = APIRouter(prefix="/earnings", tags=["Earnings"])

@router.post("/create_earning", response_model=createEarning)
def create_earning(
    earning_in: createEarning,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or update an earning for the current user.
    Users cannot earn beyond max_earning unless they invest again.
    """
    # Validate purchase
    purchase = db.query(Purchase).filter(
        Purchase.user_id == current_user.id
    ).order_by(Purchase.created_at.desc()).first()

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No purchase found for this user. Please invest to start earning."
        )
    
    # Calculate max potential earning
    max_earning = (
        Decimal(str(purchase.purchase_price))
        * Decimal(str(purchase.daily_earning_rate))
        * purchase.earning_duration_days
    )

    # Sum all active earnings for this purchase
    total_earnings = db.query(func.sum(Earning.amount)).filter(
        Earning.user_id == current_user.id,
        Earning.purchase_id == purchase.id,
        Earning.status == EarningStatus.ACTIVE
    ).scalar() or Decimal("0.00")

    # If user has already reached their cap
    if total_earnings >= max_earning:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Earning cap reached. Please invest again to continue earning."
        )

    # Daily earning amount
    amount = Decimal(str(purchase.purchase_price)) * Decimal(str(purchase.daily_earning_rate))

    # Check for existing earning
    earning = db.query(Earning).filter(
        Earning.user_id == current_user.id,
        Earning.purchase_id == purchase.id
    ).order_by(Earning.created_at.desc()).first()

    if earning:
        # Update existing earning record
        earning.amount += amount
        earning.earning_date = datetime.now(timezone.utc)
        earning.status = EarningStatus.ACTIVE
    else:
        # Create a new earning record
        earning = Earning(
            user_id=current_user.id,
            purchase_id=purchase.id,
            amount=amount,
            earning_date=datetime.now(timezone.utc),
            status=EarningStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
        )

    db.add(earning)
    db.commit()
    db.refresh(earning)

    return earning




@router.get("/my-total-earn")
def get_my_total_earnings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the latest earning record for the current user.
    """
    earning = db.query(Earning).filter(
        Earning.user_id == current_user.id,
        Earning.status == EarningStatus.ACTIVE
    ).order_by(Earning.created_at.desc()).first()

    purchase = db.query(Purchase).filter(
        Purchase.user_id == current_user.id
    ).first()

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No purchase found for this user"
        )
     # Calculate max earning potential
    max_earning = (
        Decimal(str(purchase.purchase_price))
        * Decimal(str(purchase.daily_earning_rate))
        * purchase.earning_duration_days
    )

    # Sum all active earnings
    total_earnings = db.query(func.sum(Earning.amount)).filter(
        Earning.user_id == current_user.id,
        Earning.status == EarningStatus.ACTIVE
    ).scalar() or Decimal("0.00")

    if not earning:
        return {"amount": "0.00", "status": None, "credited_at": None, "created_at": None}

    print(earning.amount)
    return {
        "totalearning":str(total_earnings),
        "maxearning":str(max_earning),
        "amount": str(earning.amount),
        "status": earning.status.value,
        "credited_at": earning.credited_at,
        "created_at": earning.created_at,
    }






@router.get("/my-earns", response_model=List[createEarning])
def get_my_earnings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all earnings for the current user.
    """
    earnings = db.query(Earning).filter(
        Earning.user_id == current_user.id
    ).order_by(Earning.created_at.desc()).all()

   
    if not earnings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No earnings found for this user"
        )

    return earnings


@router.post("/credit-total-earnings")
def credit_total_earnings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Credit all earnings to the user's balance if they have reached the max potential total earning.
    After crediting, delete the credited earnings from the database (reset to 0).
    """
    # Fetch purchase
    purchase = db.query(Purchase).filter(
        Purchase.user_id == current_user.id
    ).first()

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No purchase found for this user"
        )

    # Calculate max earning potential
    max_earning = (
        Decimal(str(purchase.purchase_price))
        * Decimal(str(purchase.daily_earning_rate))
        * purchase.earning_duration_days
    )

    # Sum all active earnings
    total_earnings = db.query(func.sum(Earning.amount)).filter(
        Earning.user_id == current_user.id,
        Earning.status == EarningStatus.ACTIVE
    ).scalar() or Decimal("0.00")

    if total_earnings < max_earning:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Total earnings ({total_earnings}) have not reached max potential ({max_earning})"
        )

    # ✅ Add to user balance
    current_user.balance = Decimal(str(current_user.balance)) + total_earnings

    # ✅ Delete all active earnings (reset to 0)
    db.query(Earning).filter(
        Earning.user_id == current_user.id,
        Earning.status == EarningStatus.ACTIVE
    ).delete(synchronize_session=False)

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Total earnings credited successfully and reset to 0",
        "credited_amount": str(total_earnings),
        "new_balance": str(current_user.balance),
        "max_earning": str(max_earning),
    }
