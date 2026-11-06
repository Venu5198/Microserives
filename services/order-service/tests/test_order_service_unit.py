import pytest
from models import (
    CancelOrderRequest,
    OrderCreateRequest,
    OrderItemInput,
    OrderStatus,
    SagaState,
    ShippingAddressInput,
)
from pydantic import ValidationError

from contracts.events.schemas import (
    OrderCreatedPayload,
    OrderItemPayload,
)
from contracts.events.types import EventType


def test_order_create_request_valid():
    req = OrderCreateRequest(
        items=[
            OrderItemInput(
                product_id="prod-101",
                product_name="Wireless Headphones",
                unit_price=19999,
                quantity=1,
            )
        ],
        shipping_address=ShippingAddressInput(
            street="123 Tech Lane",
            city="Seattle",
            state="WA",
            postal_code="98101",
            country="US",
        ),
        payment_method="sandbox_credit_card",
    )
    assert len(req.items) == 1
    assert req.items[0].product_id == "prod-101"
    assert req.shipping_address.city == "Seattle"
    assert req.payment_method == "sandbox_credit_card"


def test_order_create_request_empty_items():
    with pytest.raises(ValidationError):
        OrderCreateRequest(
            items=[],
            shipping_address=ShippingAddressInput(
                street="123 Tech Lane",
                city="Seattle",
                state="WA",
                postal_code="98101",
                country="US",
            ),
        )


def test_order_statuses_and_saga_states():
    assert OrderStatus.PENDING.value == "PENDING"
    assert OrderStatus.AWAITING_PAYMENT.value == "AWAITING_PAYMENT"
    assert OrderStatus.CONFIRMED.value == "CONFIRMED"
    assert OrderStatus.CANCELLED.value == "CANCELLED"

    assert SagaState.STARTED.value == "STARTED"
    assert SagaState.INVENTORY_RESERVED.value == "INVENTORY_RESERVED"
    assert SagaState.COMPENSATING.value == "COMPENSATING"
    assert SagaState.COMPLETED.value == "COMPLETED"
    assert SagaState.FAILED.value == "FAILED"


def test_order_created_event_payload():
    payload = OrderCreatedPayload(
        order_id="order-001",
        order_number="ORD-2026-001",
        customer_id="cust-101",
        customer_email="customer@example.com",
        items=[
            OrderItemPayload(
                product_id="prod-101",
                product_name="Product 101",
                unit_price=5000,
                quantity=2,
            )
        ],
        total_amount=10000,
        currency="USD",
        shipping_address={
            "street": "123 Main St",
            "city": "Boston",
            "state": "MA",
            "postal_code": "02108",
        },
    )
    assert payload.order_id == "order-001"
    assert payload.total_amount == 10000
    assert EventType.ORDER_CREATED.value == "OrderCreated"


def test_cancel_order_request():
    cancel = CancelOrderRequest(reason="Changed mind before shipment")
    assert cancel.reason == "Changed mind before shipment"

