import pytest
from models import (
    PaymentCreateRequest,
    PaymentStatus,
)
from pydantic import ValidationError

from contracts.events.schemas import (
    PaymentInitiatedPayload,
    PaymentSucceededPayload,
)
from contracts.events.types import EventType


def test_payment_create_request_valid():
    req = PaymentCreateRequest(
        order_id="order-12345",
        amount=4999,
        currency="USD",
        payment_method="sandbox_credit_card",
        idempotency_key="unique-key-12345678",
        card_last_four="4242",
        simulate_failure=False,
    )
    assert req.order_id == "order-12345"
    assert req.amount == 4999
    assert req.idempotency_key == "unique-key-12345678"
    assert req.card_last_four == "4242"
    assert req.simulate_failure is False


def test_payment_create_request_short_idempotency_key():
    with pytest.raises(ValidationError):
        PaymentCreateRequest(
            order_id="order-1",
            amount=1000,
            idempotency_key="short",  # Must be >= 8 chars
        )


def test_payment_create_request_invalid_zero_amount():
    with pytest.raises(ValidationError):
        PaymentCreateRequest(
            order_id="order-1",
            amount=0,
            idempotency_key="valid-key-12345",
        )


def test_payment_statuses():
    assert PaymentStatus.PENDING.value == "PENDING"
    assert PaymentStatus.SUCCEEDED.value == "SUCCEEDED"
    assert PaymentStatus.FAILED.value == "FAILED"
    assert PaymentStatus.REFUNDED.value == "REFUNDED"


def test_payment_event_schemas():
    assert EventType.PAYMENT_INITIATED.value == "PaymentInitiated"
    assert EventType.PAYMENT_SUCCEEDED.value == "PaymentSucceeded"
    assert EventType.PAYMENT_FAILED.value == "PaymentFailed"

    init_payload = PaymentInitiatedPayload(
        payment_id="pay-001",
        order_id="order-001",
        customer_id="cust-001",
        amount=9999,
        currency="USD",
        payment_method="sandbox_credit_card",
    )
    assert init_payload.amount == 9999

    success_payload = PaymentSucceededPayload(
        payment_id="pay-001",
        order_id="order-001",
        transaction_id="txn-sandbox-12345",
        amount=9999,
    )
    assert success_payload.transaction_id == "txn-sandbox-12345"

