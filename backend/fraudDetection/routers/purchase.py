# routers/purchases.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from ..database import get_db
from ..models import User, Purchase, Earning, PurchaseStatus, EarningStatus
from ..schemas import PurchaseCreate, PurchaseResponse, EarningResponse, PurchaseListResponse
from .auth import get_current_user

router = APIRouter(prefix="/purchases", tags=["purchases"])



@router.post("/buy", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    purchase_data: PurchaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new purchase."""
    try:
        # Check if user has sufficient balance
        if current_user.balance < float(purchase_data.purchase_price):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient balance"
            )
        
        # Calculate expires_at
        expires_at = datetime.now(timezone.utc) + timedelta(days=purchase_data.earning_duration_days)
        
        # Create purchase record
        db_purchase = Purchase(
            user_id=current_user.id,
            product_name=purchase_data.product_name,
            purchase_price=purchase_data.purchase_price,
            daily_earning_rate=purchase_data.daily_earning_rate,
            earning_duration_days=purchase_data.earning_duration_days,
            expires_at=expires_at,
            product_description=purchase_data.product_description,
            product_image_url=purchase_data.product_image_url
        )
        
        # Deduct balance
        current_user.balance -= float(purchase_data.purchase_price)
        
        db.add(db_purchase)
        db.commit()
        db.refresh(db_purchase)
        
        return db_purchase
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create purchase: {str(e)}"
        )

@router.get("/", response_model=PurchaseListResponse)
async def get_user_purchases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    active_only: bool = Query(False, description="Show only active purchases")
):
    """Get current user's purchases with pagination."""
    try:
        query = db.query(Purchase).filter(Purchase.user_id == current_user.id)

        
        
        if status_filter:
            query = query.filter(Purchase.status == status_filter)
        
        if active_only:
            query = query.filter(
                Purchase.status == PurchaseStatus.ACTIVE,
                Purchase.expires_at > datetime.now(timezone.utc)
            )
        
        total = query.count()
        purchases = query.order_by(Purchase.purchased_at.desc()).offset((page - 1) * size).limit(size).all()
        
        return PurchaseListResponse(
            items=purchases,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch purchases: {str(e)}"
        )

@router.get("/{purchase_id}", response_model=PurchaseResponse)
async def get_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific purchase by ID."""
    purchase = db.query(Purchase).filter(
        Purchase.id == purchase_id,
        Purchase.user_id == current_user.id
    ).first()
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )
    
    return purchase

@router.get("/active/summary")
async def get_active_purchases_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get summary of active purchases."""
    try:
        active_purchases = db.query(Purchase).filter(
            Purchase.user_id == current_user.id,
            Purchase.status == PurchaseStatus.ACTIVE,
            Purchase.expires_at > datetime.now(timezone.utc)
        ).all()
        
        total_daily_earnings = sum(p.daily_earning_amount for p in active_purchases)
        total_purchase_value = sum(p.purchase_price for p in active_purchases)
        total_earnings_generated = sum(p.total_earnings_generated for p in active_purchases)
        
        return {
            "active_purchases_count": len(active_purchases),
            "total_daily_earnings": float(total_daily_earnings),
            "total_purchase_value": float(total_purchase_value),
            "total_earnings_generated": float(total_earnings_generated),
            "active_purchases": active_purchases
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get purchases summary: {str(e)}"
        )

# ============================================================================
# EARNING ENDPOINTS
# ============================================================================

@router.get("/{purchase_id}/earnings", response_model=List[EarningResponse])
async def get_purchase_earnings(
    purchase_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get earnings for a specific purchase."""
    # Verify purchase belongs to current user
    purchase = db.query(Purchase).filter(
        Purchase.id == purchase_id,
        Purchase.user_id == current_user.id
    ).first()
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found"
        )
    
    earnings = db.query(Earning).filter(
        Earning.purchase_id == purchase_id
    ).order_by(Earning.earning_date.desc()).all()
    
    return earnings

@router.get("/earnings/all", response_model=List[EarningResponse])
async def get_user_earnings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get all earnings for current user."""
    try:
        query = db.query(Earning).filter(Earning.user_id == current_user.id)
        
        if status_filter:
            query = query.filter(Earning.status == status_filter)
        
        if date_from:
            from_date = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            query = query.filter(Earning.earning_date >= from_date)
        
        if date_to:
            to_date = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            query = query.filter(Earning.earning_date <= to_date)
        
        earnings = query.order_by(Earning.earning_date.desc()).limit(limit).all()
        
        return earnings
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch earnings: {str(e)}"
        )

@router.get("/earnings/summary")
async def get_earnings_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get earnings summary for current user."""
    try:
        # Get all earnings
        all_earnings = db.query(Earning).filter(Earning.user_id == current_user.id).all()
        
        # Get today's earnings
        today = datetime.now(timezone.utc).date()
        today_earnings = [e for e in all_earnings if e.earning_date.date() == today]
        
        # Calculate totals
        total_earnings = sum(e.amount for e in all_earnings)
        total_credited = sum(e.amount for e in all_earnings if e.status == EarningStatus.CREDITED)
        total_pending = sum(e.amount for e in all_earnings if e.status == EarningStatus.PENDING)
        today_total = sum(e.amount for e in today_earnings)
        
        return {
            "total_earnings": float(total_earnings),
            "total_credited": float(total_credited),
            "total_pending": float(total_pending),
            "today_earnings": float(today_total),
            "earnings_count": len(all_earnings),
            "today_earnings_count": len(today_earnings)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get earnings summary: {str(e)}"
        )

# ============================================================================
# DAILY EARNING GENERATION (Internal/Cron Job)
# ============================================================================



@router.post("/credit-pending-earnings")
async def credit_pending_earnings(
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user),
    batch_size: int = 100, 
    force: bool = False,
):
    """Generate & credit daily earnings to user balances.
       Each purchase earns only once every 24 hours.
    """

    try:
        now = datetime.now(timezone.utc)

        earnings_created = 0
        total_amount = Decimal("0")
        processed_purchases = []
        any_changes = False

        # Get all active purchases
        active_purchases = db.query(Purchase).filter(Purchase.status == PurchaseStatus.ACTIVE).all()

        for purchase in active_purchases:
            # Normalize datetimes
            purchase.expires_at = purchase._ensure_aware(getattr(purchase, "expires_at", None))
            purchase.purchased_at = purchase._ensure_aware(getattr(purchase, "purchased_at", None))
            purchase.last_earning_date = purchase._ensure_aware(getattr(purchase, "last_earning_date", None))

            # Skip if expired
            if purchase.expires_at is None:
                continue

            if now >= purchase.expires_at:
                if purchase.status != PurchaseStatus.COMPLETED:
                    purchase.status = PurchaseStatus.COMPLETED
                    db.add(purchase)
                    any_changes = True
                continue

            # Enforce 24-hour gap between earnings
            if not force and purchase.last_earning_date:
                time_since_last = now - purchase.last_earning_date
                if time_since_last.total_seconds() < 24 * 3600:
                    continue

            # Compute amount safely as Decimal
            try:
                amount = purchase.daily_earning_amount
                print(amount)
                if not isinstance(amount, Decimal):
                    amount = Decimal(str(amount))
            except Exception:
                price = Decimal(str(purchase.purchase_price))
                rate = Decimal(str(purchase.daily_earning_rate))
                amount = price * rate

          

            # Update purchase
            purchase.last_earning_date = now
            db.add(earning)
            db.add(purchase)

            earnings_created += 1
            total_amount += amount
            processed_purchases.append({
                "purchase_id": purchase.id,
                "user_id": purchase.user_id,
                "amount": float(amount),
            })
            any_changes = True

        # Commit earnings generation
        if any_changes:
            db.commit()

        # Now credit pending earnings
        total_credited_count = 0
        total_credited_amount = Decimal('0')

        while True:
            pending_earnings = db.query(Earning).filter(
                Earning.status == EarningStatus.PENDING
            ).limit(batch_size).all()

            if not pending_earnings:
                break

            batch_credited_count = 0
            batch_credited_amount = Decimal('0')

            for earning in pending_earnings:
                try:
                    earning.credit_to_user()
                    batch_credited_count += 1
                    batch_credited_amount += earning.amount
                except Exception as e:
                    print(f"Error crediting earning {earning.id}: {str(e)}")
                    continue

            db.commit()

            total_credited_count += batch_credited_count
            total_credited_amount += batch_credited_amount

            if len(pending_earnings) < batch_size:
                break

        return {
            "message": f"Generated {earnings_created} and credited {total_credited_count} earnings totaling ${total_credited_amount}",
            "generated_count": earnings_created,
            "credited_count": total_credited_count,
            "total_amount": float(total_credited_amount),
            "timestamp": now.isoformat(),
            "processed_purchases": processed_purchases,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to credit earnings: {str(e)}"
        )


# Additional endpoint for monitoring
@router.get("/earnings-status")
async def get_earnings_status(db: Session = Depends(get_db)):
    """Get status of earnings generation system"""
    try:
        now = datetime.now(timezone.utc)
        
        # Count active purchases
        active_purchases_count = db.query(Purchase).filter(
            Purchase.status == PurchaseStatus.ACTIVE,
            Purchase.expires_at > now
        ).count()
        
        # Count purchases that can generate earnings
        active_purchases = db.query(Purchase).filter(
            Purchase.status == PurchaseStatus.ACTIVE,
            Purchase.expires_at > now
        ).all()
        
        can_generate_count = sum(1 for p in active_purchases if p.can_generate_earnings_today())
        
        # Count pending earnings
        pending_earnings_count = db.query(Earning).filter(
            Earning.status == EarningStatus.PENDING
        ).count()
        
        return {
            "active_purchases": active_purchases_count,
            "can_generate_earnings": can_generate_count,
            "pending_earnings": pending_earnings_count,
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get earnings status: {str(e)}"
        )

# Cron job setup example (you would set this up in your deployment)
"""
# Add this to your crontab or use a task scheduler like Celery

# Generate earnings every day at midnight UTC
0 0 * * * curl -X POST "http://your-api-url/generate-daily-earnings"

# Credit pending earnings every hour (more frequent to ensure timely crediting)
0 * * * * curl -X POST "http://your-api-url/credit-pending-earnings"

# Alternative: Use APScheduler in your FastAPI app
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

# Schedule daily earnings generation
scheduler.add_job(
    func=lambda: generate_daily_earnings(db=get_db()),
    trigger=CronTrigger(hour=0, minute=0),  # Every day at midnight UTC
    id='generate_daily_earnings',
    replace_existing=True
)

# Schedule earnings crediting
scheduler.add_job(
    func=lambda: credit_pending_earnings(db=get_db()),
    trigger=CronTrigger(minute=0),  # Every hour
    id='credit_pending_earnings',
    replace_existing=True
)

scheduler.start()
"""