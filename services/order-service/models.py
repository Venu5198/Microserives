from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class SagaState(str, Enum):
    STARTED = "STARTED"
    INVENTORY_RESERVED = "INVENTORY_RESERVED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    COMPLETED = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    FAILED = "FAILED"


class OrderItemInput(BaseModel):
    product_id: str
    product_name: str
    unit_price: int  # cents
    quantity: int = Field(gt=0)


class ShippingAddressInput(BaseModel):
    street: str
    city: str
    state: str
    postal_code: str
    country: str = "US"


class OrderCreateRequest(BaseModel):
    items: List[OrderItemInput] = Field(min_length=1)
    shipping_address: ShippingAddressInput
    payment_method: str = "sandbox_credit_card"


class CancelOrderRequest(BaseModel):
    reason: str = Field(min_length=3, default="Customer requested cancellation")


class OrderItemResponse(BaseModel):
    product_id: str
    product_name: str
    unit_price: int
    quantity: int
    subtotal: int


class OrderResponse(BaseModel):
    id: str
    order_number: str
    customer_id: str
    customer_email: str
    items: List[OrderItemResponse]
    total_amount: int
    status: str
    shipping_address: Dict[str, Any]
    payment_id: Optional[str] = None
    tracking_number: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

