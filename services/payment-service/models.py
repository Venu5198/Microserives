from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentCreateRequest(BaseModel):
    order_id: str
    amount: int = Field(gt=0, description="Amount in minor units (cents)")
    currency: str = "USD"
    payment_method: str = "sandbox_credit_card"
    idempotency_key: str = Field(min_length=8)
    # Masked card metadata for simulation
    card_last_four: str = "4242"
    simulate_failure: bool = False


class RefundRequest(BaseModel):
    amount: Optional[int] = None
    reason: str = Field(min_length=3, default="Customer return")
    idempotency_key: str = Field(min_length=8)


class PaymentResponse(BaseModel):
    id: str
    order_id: str
    amount: int
    currency: str
    status: PaymentStatus
    transaction_id: Optional[str] = None
    card_last_four: Optional[str] = None
    failure_reason: Optional[str] = None
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class RefundResponse(BaseModel):
    id: str
    payment_id: str
    order_id: str
    amount: int
    status: str
    gateway_refund_id: str
    reason: str
    created_at: datetime

