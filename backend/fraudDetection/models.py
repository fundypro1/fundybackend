from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime, Enum, Index, Text
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime, timedelta
import enum
from .database import Base
import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Boolean, 
    Numeric, Enum, JSON, Index, CheckConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property


class TransactionType(str, enum.Enum):
    """Ensures consistent transaction types between schemas and models."""
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"


class RiskLevel(str, enum.Enum):
    """Defines risk levels for fraud detection."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    ERROR = "ERROR"


# ============================================================================
# ADMIN MODEL
# ============================================================================

class AdminRole(str, enum.Enum):
    """Administrative role hierarchy with specific permissions."""
    SUPERADMIN = "SUPERADMIN"
    ADMIN = "ADMIN"
    MODERATOR = "MODERATOR"


class AdminStatus(str, enum.Enum):
    """Administrative account status for access control."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class Admin(Base):
    """Administrative user model with role-based access control."""
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    
    role = Column(Enum(AdminRole), default=AdminRole.MODERATOR, nullable=False)
    status = Column(Enum(AdminStatus), default=AdminStatus.ACTIVE, nullable=False, index=True)
    
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), 
                       onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships - Fixed to avoid conflicts
    approved_deposits = relationship("Deposit", foreign_keys="Deposit.approved_by", back_populates="approving_admin")
    rejected_deposits = relationship("Deposit", foreign_keys="Deposit.rejected_by", back_populates="rejecting_admin")
    approved_withdrawals = relationship("Withdrawal", foreign_keys="Withdrawal.approved_by", back_populates="approving_admin")
    rejected_withdrawals = relationship("Withdrawal", foreign_keys="Withdrawal.rejected_by", back_populates="rejecting_admin")
    
    @hybrid_property
    def full_name(self) -> str:
        """Return formatted full name or username as fallback."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        return self.username
    
    @hybrid_property
    def is_active(self) -> bool:
        """Check if admin account is currently active."""
        return self.status == AdminStatus.ACTIVE
    
    def __repr__(self) -> str:
        return f"<Admin {self.id} [{self.username}] - {self.role.value}>"


# ============================================================================
# USER MODEL
# ============================================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    phone = Column(String(20), nullable=True)  # Added phone field
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships - Fixed to avoid conflicts
    deposits = relationship("Deposit", back_populates="user", cascade="all, delete-orphan")
    withdrawals = relationship("Withdrawal", back_populates="user", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="user", cascade="all, delete-orphan")
    earnings = relationship("Earning", back_populates="user", cascade="all, delete-orphan")

    # Hybrid properties for account metrics
    @hybrid_property
    def total_deposits(self):
        """Calculate total deposits made by the user."""
        return sum(t.amount for t in self.transactions if t.type == TransactionType.DEPOSIT.value)
    
    @hybrid_property
    def total_withdrawals(self):
        """Calculate total withdrawals made by the user."""
        return sum(t.amount for t in self.transactions if t.type == TransactionType.WITHDRAWAL.value)
    
    @hybrid_property
    def total_transfers_out(self):
        """Calculate total transfers sent by the user."""
        return sum(t.amount for t in self.transactions if t.type == TransactionType.TRANSFER_OUT.value)
    
    @hybrid_property
    def total_transfers_in(self):
        """Calculate total transfers received by the user."""
        return sum(t.amount for t in self.transactions if t.type == TransactionType.TRANSFER_IN.value)
    
    @hybrid_property
    def transaction_count(self):
        """Count total number of transactions."""
        return len(self.transactions)
    
    @hybrid_property
    def pending_deposits(self):
        """Count pending deposits."""
        return len([d for d in self.deposits if d.status == DepositStatus.PENDING])
    
    @hybrid_property
    def pending_withdrawals(self):
        """Count pending withdrawals."""
        return len([w for w in self.withdrawals if w.status == WithdrawalStatus.PENDING])
    
    @validates('balance')
    def validate_balance(self, key, balance):
        """Ensure balance never goes below zero."""
        if balance < 0:
            raise ValueError("Account balance cannot be negative")
        return balance

    def __repr__(self):
        return f"<User {self.username} (ID: {self.id})>"


# ============================================================================
# DEPOSIT MODEL
# ============================================================================

class DepositStatus(str, enum.Enum):
    """Deposit processing status workflow."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class Deposit(Base):
    """Deposit model for handling user deposit requests with approval workflow."""
    __tablename__ = "deposits"
    
    id = Column(Integer, primary_key=True, index=True)
    reference_number = Column(String(50), unique=True, nullable=False, index=True)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="GHS")
    
    status = Column(Enum(DepositStatus), default=DepositStatus.PENDING, nullable=False, index=True)
    
    image_url = Column(String(500), nullable=False)
    transaction_reference = Column(String(100), nullable=True)
    
    approved_by = Column(Integer, ForeignKey("admins.id"), nullable=True)
    rejected_by = Column(Integer, ForeignKey("admins.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), 
                       onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    user_notes = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Database constraints
    __table_args__ = (
        CheckConstraint('amount > 0', name='check_positive_deposit_amount'),
        Index('ix_deposits_user_status', 'user_id', 'status'),
    )
    
    # Relationships - Fixed to avoid backref conflicts
    user = relationship("User", back_populates="deposits")
    approving_admin = relationship("Admin", foreign_keys=[approved_by], back_populates="approved_deposits")
    rejecting_admin = relationship("Admin", foreign_keys=[rejected_by], back_populates="rejected_deposits")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.reference_number:
            self.reference_number = self.generate_reference_number()
    
    @staticmethod
    def generate_reference_number() -> str:
        """Generate unique reference number for deposit tracking."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = str(uuid.uuid4()).replace('-', '')[:6].upper()
        return f"DEP-{timestamp}-{random_suffix}"
    
    @hybrid_property
    def is_pending(self) -> bool:
        """Check if deposit is pending approval."""
        return self.status == DepositStatus.PENDING
    
    @validates('amount')
    def validate_amount(self, key: str, value) -> Decimal:
        """Validate deposit amount is positive."""
        if value <= 0:
            raise ValueError("Deposit amount must be positive")
        return Decimal(str(value)).quantize(Decimal('0.01'))
    
    def approve(self, admin_id: int, notes: Optional[str] = None) -> None:
        """Approve the deposit."""
        self.status = DepositStatus.APPROVED
        self.approved_by = admin_id
        self.processed_at = datetime.now(timezone.utc)
        
        if notes:
            self.admin_notes = notes
    
    def reject(self, admin_id: int, reason: str) -> None:
        """Reject the deposit with reason."""
        self.status = DepositStatus.REJECTED
        self.rejected_by = admin_id
        self.processed_at = datetime.now(timezone.utc)
        self.rejection_reason = reason
    
    def complete(self) -> None:
        """Mark deposit as completed."""
        if self.status != DepositStatus.APPROVED:
            raise ValueError("Only approved deposits can be completed")
        self.status = DepositStatus.COMPLETED
    
    def __repr__(self) -> str:
        return f"<Deposit {self.id} [{self.reference_number}] - {self.status.value} - ${self.amount}>"


# ============================================================================
# WITHDRAWAL MODEL
# ============================================================================

class WithdrawalStatus(str, enum.Enum):
    """Withdrawal processing status workflow."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class Withdrawal(Base):
    """Withdrawal model for handling user withdrawal requests with approval workflow."""
    __tablename__ = "withdrawals"
    
    id = Column(Integer, primary_key=True, index=True)
    reference_number = Column(String(50), unique=True, nullable=False, index=True)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    
    status = Column(Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING, nullable=False, index=True)
    
    recipient_name = Column(String(100), nullable=False)
    recipient_account = Column(String(100), nullable=False)
    bank_name = Column(String(100), nullable=True)
    
    approved_by = Column(Integer, ForeignKey("admins.id"), nullable=True)
    rejected_by = Column(Integer, ForeignKey("admins.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), 
                       onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    user_notes = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Database constraints
    __table_args__ = (
        CheckConstraint('amount > 0', name='check_positive_withdrawal_amount'),
        Index('ix_withdrawals_user_status', 'user_id', 'status'),
    )
    
    # Relationships - Fixed to avoid backref conflicts
    user = relationship("User", back_populates="withdrawals")
    approving_admin = relationship("Admin", foreign_keys=[approved_by], back_populates="approved_withdrawals")
    rejecting_admin = relationship("Admin", foreign_keys=[rejected_by], back_populates="rejected_withdrawals")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.reference_number:
            self.reference_number = self.generate_reference_number()
    
    @staticmethod
    def generate_reference_number() -> str:
        """Generate unique reference number for withdrawal tracking."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = str(uuid.uuid4()).replace('-', '')[:6].upper()
        return f"WTH-{timestamp}-{random_suffix}"
    
    @hybrid_property
    def is_pending(self) -> bool:
        """Check if withdrawal is pending approval."""
        return self.status == WithdrawalStatus.PENDING
    
    @validates('amount')
    def validate_amount(self, key: str, value) -> Decimal:
        """Validate withdrawal amount is positive."""
        if value <= 0:
            raise ValueError("Withdrawal amount must be positive")
        return Decimal(str(value)).quantize(Decimal('0.01'))
    
    def approve(self, admin_id: int, notes: Optional[str] = None) -> None:
        """Approve the withdrawal."""
        self.status = WithdrawalStatus.APPROVED
        self.approved_by = admin_id
        self.processed_at = datetime.now(timezone.utc)
        
        if notes:
            self.admin_notes = notes
    
    def reject(self, admin_id: int, rejection_reason: Optional[str] = None) -> None:
        """Reject the withdrawal with reason."""
        self.status = WithdrawalStatus.REJECTED
        self.rejected_by = admin_id
        self.processed_at = datetime.now(timezone.utc)
        if rejection_reason:
            self.rejection_reason = rejection_reason

    def complete(self) -> None:
        """Mark withdrawal as completed."""
        if self.status != WithdrawalStatus.APPROVED:
            raise ValueError("Only approved withdrawals can be completed")
        self.status = WithdrawalStatus.COMPLETED
    
    def __repr__(self) -> str:
        return f"<Withdrawal {self.id} [{self.reference_number}] - {self.status.value} - ${self.amount}>"



# ============================================================================
# PURCHASE MODEL - FIXED VERSION
# ============================================================================



class PurchaseStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    reference_number = Column(String(50), unique=True, nullable=False, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    product_name = Column(String(100), nullable=False)
    purchase_price = Column(Numeric(10, 2), nullable=False)
    daily_earning_rate = Column(Numeric(5, 4), nullable=False)
    earning_duration_days = Column(Integer, nullable=False, default=30)

    status = Column(Enum(PurchaseStatus), default=PurchaseStatus.ACTIVE, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    purchased_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_earning_date = Column(DateTime(timezone=True), nullable=True)

    product_description = Column(Text, nullable=True)
    product_image_url = Column(String(500), nullable=True)

    __table_args__ = (
        CheckConstraint('purchase_price > 0', name='check_positive_purchase_price'),
        CheckConstraint('daily_earning_rate > 0', name='check_positive_earning_rate'),
        Index('ix_purchases_user_status', 'user_id', 'status'),
    )

    user = relationship("User", back_populates="purchases")
    earnings = relationship("Earning", back_populates="purchase", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.reference_number:
            self.reference_number = self.generate_reference_number()

        # If expires_at not set, base it off purchased_at (normalize)
        if not self.expires_at and self.earning_duration_days:
            purchased_time = kwargs.get("purchased_at", datetime.now(timezone.utc))
            purchased_time = self._ensure_aware(purchased_time)
            self.expires_at = purchased_time + timedelta(days=self.earning_duration_days)

    @staticmethod
    def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
        """Return a timezone-aware datetime in UTC or None."""
        if dt is None:
            return None
        if not isinstance(dt, datetime):
            # not a datetime — return as-is (shouldn't happen)
            return dt
        if dt.tzinfo is None:
            # assume stored values are UTC if naive
            return dt.replace(tzinfo=timezone.utc)
        # convert to UTC to have a canonical form
        return dt.astimezone(timezone.utc)
    
    # def _ensure_aware(dt):
    #     """Return a timezone-aware datetime in UTC, or None if dt is None."""
    #     if dt is None:
    #         return None
    #     if not isinstance(dt, datetime):
    #         return dt  # unexpected type — let other code handle it
    #     if dt.tzinfo is None:
    #         return dt.replace(tzinfo=timezone.utc)
    #     return dt.astimezone(timezone.utc)

    @staticmethod
    def generate_reference_number() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        random_suffix = str(uuid.uuid4()).replace("-", "")[:6].upper()
        return f"PUR-{timestamp}-{random_suffix}"

    @hybrid_property
    def is_active(self) -> bool:
        now_utc = datetime.now(timezone.utc)
        expires_at = self._ensure_aware(self.expires_at)
        return self.status == PurchaseStatus.ACTIVE and expires_at is not None and now_utc < expires_at

    @hybrid_property
    def days_remaining(self) -> int:
        expires_at = self._ensure_aware(self.expires_at)
        if not expires_at:
            return 0
        now_utc = datetime.now(timezone.utc)
        remaining = (expires_at - now_utc).days
        return max(0, remaining)

    @hybrid_property
    def days_elapsed(self) -> int:
        purchased_at = self._ensure_aware(self.purchased_at)
        if not purchased_at:
            return 0
        now_utc = datetime.now(timezone.utc)
        elapsed = (now_utc - purchased_at).days
        return max(0, elapsed)

    def _to_decimal(self, value) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        # Convert carefully (handles Decimal, strings, ints, floats)
        try:
            return Decimal(value)
        except Exception:
            return Decimal(str(value))

    @hybrid_property
    def daily_earning_amount(self) -> Decimal:
        price = self._to_decimal(self.purchase_price)
        rate = self._to_decimal(self.daily_earning_rate)
        return price * rate

    @hybrid_property
    def total_earning_potential(self) -> Decimal:
        return self.daily_earning_amount * Decimal(self.earning_duration_days)

    @hybrid_property
    def total_earnings_generated(self) -> Decimal:
        return sum((self._to_decimal(e.amount) for e in self.earnings), Decimal("0"))

    @hybrid_property
    def total_earnings_credited(self) -> Decimal:
        return sum((self._to_decimal(e.amount) for e in self.earnings if e.status == EarningStatus.CREDITED), Decimal("0"))

    @hybrid_property
    def earning_progress_percentage(self) -> float:
        if not self.earning_duration_days:
            return 0.0
        return min(100.0, (self.days_elapsed / self.earning_duration_days) * 100.0)

    def can_generate_earnings_today(self) -> bool:
        """Check if this purchase can generate earnings today"""
        if not self.is_active:
            return False
        
        # Check if purchase has expired
        now = datetime.now(timezone.utc)
        if self.expires_at and self.expires_at <= now:
            return False
        
        # If no last earning date, can generate (first time)
        if not self.last_earning_date:
            return True
        
        # Ensure timezone awareness
        last_date = self._ensure_aware(self.last_earning_date)
        
        # Calculate time difference (should be at least 24 hours)
        time_diff = now - last_date
        return time_diff >= timedelta(hours=24)

# Alternative method using date comparison (more lenient)
    def can_generate_earnings_today_date_based(self) -> bool:
        """Check if earnings can be generated based on date (not exact 24hr timing)"""
        if not self.is_active:
            return False
        
        now = datetime.now(timezone.utc)
        today = now.date()
        
        # Check if purchase has expired
        if self.expires_at and self.expires_at <= now:
            return False
        
        # If no last earning date, can generate
        if not self.last_earning_date:
            return True
        
        # Check if last earning was on a different date
        last_date = self._ensure_aware(self.last_earning_date)
        return last_date.date() < today  # Changed from == to < for proper logic


    def complete(self) -> None:
        self.status = PurchaseStatus.COMPLETED

    def cancel(self) -> None:
        self.status = PurchaseStatus.CANCELLED

    def __repr__(self) -> str:
        return f"<Purchase {self.id} [{self.reference_number}] - {self.product_name} - {self.status.value}>"

# ============================================================================
# EARNING MODEL
# ============================================================================

class EarningStatus(str, enum.Enum):
    PENDING = "PENDING"
    CREDITED = "CREDITED"
    CANCELLED = "CANCELLED"
    ACTIVE = "ACTIVE"   # add back if you want to support it

class Earning(Base):
    """Daily earning model for purchases."""
    __tablename__ = "earnings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False, index=True)
    
    amount = Column(Numeric(10, 2), nullable=False)
    earning_date = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Enum(EarningStatus), default=EarningStatus.PENDING, nullable=False)
    
    # Timing
    credited_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Optional notes
    notes = Column(String(255), nullable=True)
    
    # Database constraints
    __table_args__ = (
        CheckConstraint('amount > 0', name='check_positive_earning_amount'),
        # Unique constraint to prevent duplicate earnings per day per purchase
        Index('ix_earning_unique_daily', 'purchase_id', 'earning_date', unique=True),
        Index('ix_earning_user_date', 'user_id', 'earning_date'),
        Index('ix_earning_status', 'status'),
    )
    
    # Relationships
    user = relationship("User", back_populates="earnings")
    purchase = relationship("Purchase", back_populates="earnings")
    
    @hybrid_property
    def is_credited(self) -> bool:
        """Check if earning has been credited."""
        return self.status == EarningStatus.CREDITED
    
    def credit_to_user(self) -> None:
        """Credit earning amount to the user's balance."""
        if self.status != EarningStatus.PENDING:
            return

        if not self.user:
            raise ValueError("No user associated with this earning")

        
        # Safely update the user's balance
        
        # self.user.balance += float(self.amount)
        
        # print(f"balance : {self.user.balance}")

        # Update earning status
        self.status = EarningStatus.CREDITED
        self.credited_at = datetime.now(timezone.utc)

        print(f"Earning {self.id} credited: {self.amount} -> User {self.user_id} new balance = {self.user.balance}")



    def cancel(self) -> None:
        """Cancel the earning and rollback user balance if already credited."""
        if not self.user:
            raise ValueError("No user associated with this earning")

        if self.status == EarningStatus.CREDITED:
            # Rollback credited amount
            self.user.balance -= float(self.amount)

        self.status = EarningStatus.CANCELLED
