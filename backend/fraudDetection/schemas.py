from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict, model_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
from decimal import Decimal


class TransactionType(str, Enum):
    """Enumeration of valid transaction types for better type safety."""
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"


class RiskLevel(str, Enum):
    """Defines risk levels for fraud detection."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    ERROR = "ERROR"


# ============================================================================
# ADMIN SCHEMAS
# ============================================================================

class AdminRole(str, Enum):
    """Administrative role hierarchy with specific permissions."""
    SUPERADMIN = "SUPERADMIN"
    ADMIN = "ADMIN"
    MODERATOR = "MODERATOR"


class AdminStatus(str, Enum):
    """Administrative account status for access control."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class AdminBase(BaseModel):
    """Base model for admin data validation."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    role: AdminRole = AdminRole.MODERATOR


class AdminCreate(AdminBase):
    """Model for admin creation requests."""
    password: str = Field(..., min_length=8)


class AdminUpdate(BaseModel):
    """Model for admin update requests."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    role: Optional[AdminRole] = None
    status: Optional[AdminStatus] = None


class AdminLogin(BaseModel):
    """Model for admin login requests."""
    username: str
    password: str


class AdminResponse(AdminBase):
    """Response model for admin information."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    status: AdminStatus
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    full_name: str
    is_active: bool


class AdminToken(BaseModel):
    """Response model for admin authentication tokens."""
    access_token: str
    token_type: str = "bearer"
    admin_id: int
    username: str
    role: AdminRole
    expires_at: datetime


# ============================================================================
# DEPOSIT SCHEMAS
# ============================================================================

class DepositStatus(str, Enum):
    """Deposit processing status workflow."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class DepositBase(BaseModel):
    """Base model for deposit data validation."""
    amount: float
    currency: str = Field(default="GHS", max_length=3)
    user_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, value):
        if len(value) != 3:
            raise ValueError('Currency must be a 3-character ISO code')
        return value.upper()


class DepositCreate(DepositBase):
    """Model for deposit creation requests."""
    image_url: str = Field(..., max_length=500)
    transaction_reference: Optional[str] = Field(None, max_length=100)


class DepositUpdate(BaseModel):
    """Model for deposit update requests."""
    transaction_reference: Optional[str] = Field(None, max_length=100)
    user_notes: Optional[str] = Field(None, max_length=1000)


class DepositApprove(BaseModel):
    """Model for deposit approval requests."""
    admin_notes: Optional[str] = Field(None, max_length=1000)


class DepositReject(BaseModel):
    """Model for deposit rejection requests."""
    rejection_reason: str = Field(..., min_length=1, max_length=1000)


class DepositResponse(DepositBase):
    """Response model for deposit information."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    reference_number: str
    user_id: int
    status: DepositStatus
    image_url: str
    transaction_reference: Optional[str] = None
    approved_by: Optional[int] = None
    rejected_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None
    admin_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    is_pending: bool


# ============================================================================
# WITHDRAWAL SCHEMAS
# ============================================================================

class WithdrawalStatus(str, Enum):
    """Withdrawal processing status workflow."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class WithdrawalBase(BaseModel):
    """Base model for withdrawal data validation."""
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(default="USD", max_length=3)
    recipient_name: str = Field(..., min_length=1, max_length=100)
    recipient_account: str = Field(..., min_length=1, max_length=100)
    bank_name: Optional[str] = Field(None, max_length=100)
    user_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, value):
        if len(value) != 3:
            raise ValueError('Currency must be a 3-character ISO code')
        return value.upper()

    @field_validator('recipient_name', 'recipient_account')
    @classmethod
    def validate_required_fields(cls, value):
        if not value or not value.strip():
            raise ValueError('This field is required')
        return value.strip()


class WithdrawalCreate(WithdrawalBase):
    """Model for withdrawal creation requests."""
    pass


class WithdrawalUpdate(BaseModel):
    """Model for withdrawal update requests."""
    recipient_name: Optional[str] = Field(None, min_length=1, max_length=100)
    recipient_account: Optional[str] = Field(None, min_length=1, max_length=100)
    bank_name: Optional[str] = Field(None, max_length=100)
    user_notes: Optional[str] = Field(None, max_length=1000)


class WithdrawalApprove(BaseModel):
    """Model for withdrawal approval requests."""
    admin_notes: Optional[str] = Field(None, max_length=1000)


class WithdrawalReject(BaseModel):
    """Model for withdrawal rejection requests."""
    rejection_reason: str = Field(..., min_length=1, max_length=1000)


class WithdrawalResponse(WithdrawalBase):
    """Response model for withdrawal information."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    reference_number: str
    user_id: int
    status: WithdrawalStatus
    approved_by: Optional[int] = None
    rejected_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None
    admin_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    is_pending: bool



# ============================================================================
# EXISTING USER AND TRANSACTION SCHEMAS (UPDATED)
# ============================================================================

class UserBase(BaseModel):
    """Base model for user data validation."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    """Model for user creation requests."""
    password: str = Field(..., min_length=8)
    phone: Optional[str] = Field(None, max_length=20)


class UserUpdate(BaseModel):
    """Model for user update requests."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)


class Login(BaseModel):
    """Model for user login requests."""
    username: str
    password: str



class AccountSummary(BaseModel):
    """Summary of user account information."""
    current_balance: float
    total_deposits: float
    total_withdrawals: float
    total_transfers_out: float
    total_transfers_in: float
    transaction_count: int
    pending_deposits: int
    pending_withdrawals: int


class UserResponse(UserBase):
    """Enhanced response model for user information."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool = True
    balance: float
    phone: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    account_summary: Optional[AccountSummary] = None
    recent_deposits: List[DepositResponse] = []
    recent_withdrawals: List[WithdrawalResponse] = []


class WithdrawalListResponse(BaseModel):
    items: List[WithdrawalResponse]
    total: int
    page: int
    size: int
    pages: int

class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    size: int
    pages: int

# Fix BulkApprovalRequest to match frontend usage
class BulkApprovalRequest(BaseModel):
    deposit_ids: List[int]  # Changed from 'ids' to match frontend
    admin_notes: Optional[str] = "Bulk approved by admin"

class BulkRejectionRequest(BaseModel):
    deposit_ids: List[int]  # Changed from 'ids' to match frontend  
    rejection_reason: Optional[str] = "Bulk rejected by admin"

# Add required imports to your admin router file:
from sqlalchemy import or_, func
# Token Models for Authentication
class Token(BaseModel):
    """Response model for authentication tokens."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user_id: int
    username: str
    expires_at: datetime


class TokenData(BaseModel):
    """Model for token payload data."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    expires_at: Optional[datetime] = None


# Comprehensive Response Models for Financial Operations


# ============================================================================
# ADMIN DASHBOARD SCHEMAS
# ============================================================================

class AdminDashboardStats(BaseModel):
    """Statistics for admin dashboard."""
    total_users: int
    active_users: int
    pending_deposits: int
    pending_withdrawals: int
    total_deposits_today: Decimal
    total_withdrawals_today: Decimal
    flagged_transactions: int


class PaginationParams(BaseModel):
    """Parameters for paginated requests."""
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1, le=100)
    sort_by: Optional[str] = None
    sort_order: Optional[str] = Field(default="desc", pattern="^(asc|desc)$")


class PaginatedResponse(BaseModel):
    """Generic paginated response model."""
    items: List[dict]
    total: int
    page: int
    size: int
    pages: int


class DepositListResponse(BaseModel):
    """Paginated response for deposit listings."""
    items: List[DepositResponse]
    total: int
    page: int
    size: int
    pages: int


class WithdrawalListResponse(BaseModel):
    """Paginated response for withdrawal listings."""
    items: List[WithdrawalResponse]
    total: int
    page: int
    size: int
    pages: int


# Error Models
class ErrorResponse(BaseModel):
    """Standardized error response model."""
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ValidationErrorResponse(BaseModel):
    """Response model for validation errors."""
    detail: str
    field_errors: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# BULK OPERATIONS SCHEMAS
# ============================================================================

class BulkApprovalRequest(BaseModel):
    """Model for bulk approval operations."""
    ids: List[int] = Field(..., min_length=1, max_length=50)
    admin_notes: Optional[str] = Field(None, max_length=1000)


class BulkRejectionRequest(BaseModel):
    """Model for bulk rejection operations."""
    ids: List[int] = Field(..., min_length=1, max_length=50)
    rejection_reason: str = Field(..., min_length=1, max_length=1000)


class BulkOperationResponse(BaseModel):
    """Response model for bulk operations."""
    successful: List[int]
    failed: List[dict]
    total_processed: int
    message: str



# ============================================================================
# PURCHASE SCHEMAS
# ============================================================================

class PurchaseStatus(str, Enum):
    """Purchase status workflow."""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class PurchaseCreate(BaseModel):
    """Model for creating a new purchase."""
    product_name: str = Field(..., min_length=1, max_length=100)
    purchase_price: Decimal = Field(..., gt=0, decimal_places=2)
    daily_earning_rate: Decimal = Field(..., gt=0, le=1, decimal_places=4)  # Max 100% (1.0000)
    earning_duration_days: int = Field(..., gt=0, le=365)  # Max 1 year
    product_description: Optional[str] = Field(None, max_length=1000)
    product_image_url: Optional[str] = Field(None, max_length=500)

    @field_validator('daily_earning_rate')
    @classmethod
    def validate_earning_rate(cls, value):
        if value > Decimal('0.5'):  # Max 50% daily rate for safety
            raise ValueError('Daily earning rate cannot exceed 50%')
        return value
    
    @model_validator(mode="before")
    def choose_earning_rate(cls, values):
        product_name = values.get("product_name")
        purchase_price = values.get("purchase_price")

        if purchase_price is not None and purchase_price < 100:
            raise ValueError("Need more funds to purchase a product!")

        product_rates = {
            "Silver": 0.09,
            "Gold": 0.19,
            "Diamond": 0.23,
            "Platinum": 0.37,
            "Emerald": 0.41,
            "Ruby": 0.45,
            "Crown": 0.47,
            "Infinity": 0.49,
        }

        if product_name in product_rates:
            values["daily_earning_rate"] = product_rates[product_name]

        return values
    


    @field_validator('earning_duration_days')
    @classmethod
    def validate_duration(cls, value):
        if value > 365:
            raise ValueError('Earning duration cannot exceed 365 days')
        return value

class PurchaseResponse(BaseModel):
    """Response model for purchase information."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    reference_number: str
    user_id: int
    product_name: str
    purchase_price: Decimal
    daily_earning_rate: Decimal
    earning_duration_days: int
    status: PurchaseStatus
    
    purchased_at: datetime
    expires_at: datetime
    last_earning_date: Optional[datetime] = None
    
    product_description: Optional[str] = None
    product_image_url: Optional[str] = None
    
    # Computed fields
    is_active: bool
    days_remaining: int
    days_elapsed: int
    daily_earning_amount: Decimal
    total_earning_potential: Decimal
    total_earnings_generated: Decimal
    total_earnings_credited: Decimal
    earning_progress_percentage: float

class PurchaseListResponse(BaseModel):
    """Paginated response for purchase listings."""
    items: List[PurchaseResponse]
    total: int
    page: int
    size: int
    pages: int

# ============================================================================
# EARNING SCHEMAS
# ============================================================================

class EarningStatus(str, Enum):
    ACTIVE = "ACTIVE"   # add back if you want to support it
    PENDING = "PENDING"
    CREDITED = "CREDITED"
    CANCELLED = "CANCELLED"


class createEarning(BaseModel):
    amount: Decimal
    status: EarningStatus
    credited_at: Optional[datetime] = None
    created_at: datetime



class EarningResponse(BaseModel):
    """Response model for earning information."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    purchase_id: int
    amount: Decimal
    earning_date: datetime
    status: EarningStatus
    credited_at: Optional[datetime] = None
    created_at: datetime
    notes: Optional[str] = None
    
    # Include purchase info for context
    purchase: Optional[PurchaseResponse] = None

class EarningListResponse(BaseModel):
    """Paginated response for earning listings."""
    items: List[EarningResponse]
    total: int
    page: int
    size: int
    pages: int

class EarningSummary(BaseModel):
    """Summary of user earnings."""
    total_earnings: Decimal
    total_credited: Decimal
    total_pending: Decimal
    today_earnings: Decimal
    earnings_count: int
    today_earnings_count: int

class PurchaseSummary(BaseModel):
    """Summary of user purchases."""
    active_purchases_count: int
    total_daily_earnings: Decimal
    total_purchase_value: Decimal
    total_earnings_generated: Decimal
    active_purchases: List[PurchaseResponse]

# ============================================================================
# BATCH OPERATION SCHEMAS
# ============================================================================

class DailyEarningResult(BaseModel):
    """Result of daily earning generation."""
    message: str
    earnings_created: int
    date: str

class CreditEarningsResult(BaseModel):
    """Result of crediting earnings."""
    message: str
    credited_count: int
    total_amount: Decimal

# ============================================================================
# UPDATE USER RESPONSE SCHEMA
# ============================================================================

# Update your existing UserResponse schema to include purchase/earning info:
class UserResponseEnhanced(UserResponse):
    """Enhanced user response with purchase/earning data."""
    # Purchase summary
    active_purchases_count: int = 0
    total_daily_earnings: Decimal = Decimal('0')
    total_earnings_credited: Decimal = Decimal('0')
    total_purchase_value: Decimal = Decimal('0')
    
    # Recent activity
    recent_purchases: List[PurchaseResponse] = []
    recent_earnings: List[EarningResponse] = []