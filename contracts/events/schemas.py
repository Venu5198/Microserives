import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from contracts.events.types import EventType


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    event_version: int = 1
    aggregate_id: str
    correlation_id: str
    occurred_at: str = Field(default_factory=utc_now)
    producer: str
    payload: dict[str, Any]


class OrderItemPayload(BaseModel):
    product_id: str
    product_name: str
    unit_price: int  # in minor units (cents)
    quantity: int


class OrderCreatedPayload(BaseModel):
    order_id: str
    order_number: str
    customer_id: str
    customer_email: str
    items: list[OrderItemPayload]
    total_amount: int
    currency: str = "USD"
    shipping_address: dict[str, Any]


class InventoryReservedPayload(BaseModel):
    order_id: str
    reservation_id: str
    reserved_items: list[OrderItemPayload]


class InventoryReservationFailedPayload(BaseModel):
    order_id: str
    reason: str
    failed_items: list[OrderItemPayload]


class PaymentInitiatedPayload(BaseModel):
    payment_id: str
    order_id: str
    customer_id: str
    amount: int
    currency: str
    payment_method: str


class PaymentSucceededPayload(BaseModel):
    payment_id: str
    order_id: str
    transaction_id: str
    amount: int
    gateway: str = "sandbox"


class PaymentFailedPayload(BaseModel):
    payment_id: str
    order_id: str
    reason: str
    gateway: str = "sandbox"


class OrderConfirmedPayload(BaseModel):
    order_id: str
    order_number: str
    customer_id: str
    customer_email: str
    total_amount: int
    shipping_address: dict[str, Any]
    items: list[OrderItemPayload]


class ShipmentCreatedPayload(BaseModel):
    shipment_id: str
    order_id: str
    tracking_number: str
    carrier: str
    estimated_delivery: str
    recipient_email: str
    recipient_name: str
    shipping_address: dict[str, Any]


class ShipmentStatusUpdatedPayload(BaseModel):
    shipment_id: str
    order_id: str
    tracking_number: str
    old_status: str
    new_status: str
    location: str | None = None
    notes: str | None = None
    updated_at: str = Field(default_factory=utc_now)


class OrderCancelledPayload(BaseModel):
    order_id: str
    customer_id: str
    customer_email: str
    reason: str
    refund_required: bool
    inventory_release_required: bool
    items: list[OrderItemPayload]


class RefundInitiatedPayload(BaseModel):
    refund_id: str
    payment_id: str
    order_id: str
    amount: int
    reason: str


class RefundSucceededPayload(BaseModel):
    refund_id: str
    payment_id: str
    order_id: str
    amount: int
    gateway_refund_id: str


class RefundFailedPayload(BaseModel):
    refund_id: str
    payment_id: str
    order_id: str
    reason: str


class NotificationRequestedPayload(BaseModel):
    notification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recipient_email: str
    recipient_name: str | None = None
    subject: str
    template_name: str
    template_data: dict[str, Any]


class ProductCreatedPayload(BaseModel):
    product_id: str
    name: str
    price: int
    category: str
    sku: str


class ProductUpdatedPayload(BaseModel):
    product_id: str
    name: str | None = None
    price: int | None = None
    category: str | None = None
    is_active: bool | None = None


class ProductDeletedPayload(BaseModel):
    product_id: str
    sku: str
