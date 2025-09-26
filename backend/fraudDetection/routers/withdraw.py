# routers/withdrawals.py
import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from decimal import Decimal

from m import  send_withdraw_email

from ..database import get_db
from ..models import Withdrawal, WithdrawalStatus, User, Admin
from ..schemas import (
    WithdrawalCreate, WithdrawalResponse,
    WithdrawalApprove,
)
from .authentication import get_current_user

router = APIRouter(prefix="/withdrawals", tags=["Withdrawals"])





@router.post("/", response_model=WithdrawalResponse, status_code=status.HTTP_201_CREATED)
def create_withdrawal(
    withdrawal_in: WithdrawalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """User requests a withdrawal (balance not deducted until admin approves)."""
    user_balance = Decimal(str(current_user.balance))  # normalize to Decimal

    if user_balance < withdrawal_in.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance"
        )

    withdrawal = Withdrawal(
        user_id=current_user.id,
        amount=withdrawal_in.amount,
        currency=withdrawal_in.currency,
        recipient_name=withdrawal_in.recipient_name,
        recipient_account=withdrawal_in.recipient_account,
        bank_name=withdrawal_in.bank_name,
        user_notes=withdrawal_in.user_notes,
        status=WithdrawalStatus.PENDING,
    )

    # Persist first so withdrawal.id is generated
    db.add(withdrawal)
    db.commit()
    db.refresh(withdrawal)

    # Build plain subject and HTML body (sanitization will be done inside send_withdraw_email)
    subject = f"{current_user.username} | user_id:{current_user.id} | withdraw_id:{withdrawal.id} | CRYPTO:{withdrawal.bank_name or ''}"
    body_html = f"""
        <h2>New Withdrawal Request</h2>
        <p><strong>User:</strong> {current_user.username} (ID: {current_user.id})</p>
        <p><strong>Withdraw ID:</strong> {withdrawal.id}</p>
        <p><strong>Amount:</strong> {withdrawal.amount} {withdrawal.currency}</p>
        <p><strong>Method / Bank:</strong> {withdrawal.bank_name or 'N/A'}</p>
        <p><strong>Account/Wallet:</strong> {withdrawal.recipient_account}</p>
        <p><strong>Notes:</strong> {withdrawal.user_notes or ''}</p>
        <p>Approve or reject this withdrawal in the admin panel.</p>
    """

    # send notification (recipient should be admin email)
    try:
        addresses = ["fundypro47@gmail.com","fundypro45@gmail.com","fundyp657@gmail.com",
                     "fundypro90@gmail.com"]

        for address in addresses:
            send_withdraw_email(subject=subject, body_html=body_html, recipient=address)
    except Exception as e:
        # Log the email failure but DO NOT fail the whole request
        # (you may want to handle retries / background tasks for email)
        print("Warning: failed to send withdraw notification email:", e)

    return withdrawal



# 2️⃣ User - View My Withdrawals
@router.get("/my", response_model=List[WithdrawalResponse])
def get_my_withdrawals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all withdrawals made by the current user."""
    withdrawals = db.query(Withdrawal).filter(
        Withdrawal.user_id == current_user.id
    ).order_by(Withdrawal.created_at.desc()).all()

    return withdrawals


