from main import render_template
from models import NotificationSendRequest

from contracts.events.schemas import NotificationRequestedPayload
from contracts.events.types import EventType


def test_render_template_order_confirmed():
    subject, body = render_template(
        "order_confirmed",
        {"order_number": "ORD-12345", "total_amount": 25000},
    )
    assert "ORD-12345" in subject
    assert "$250.00" in body


def test_render_template_shipment_created():
    subject, body = render_template(
        "shipment_created",
        {
            "tracking_number": "TRK-USPS-998877",
            "carrier": "USPS Priority",
            "estimated_delivery": "2026-11-12",
        },
    )
    assert "TRK-USPS-998877" in subject
    assert "USPS Priority" in body


def test_render_template_payment_failed():
    subject, body = render_template(
        "payment_failed",
        {"order_id": "ord-001", "reason": "Card expired"},
    )
    assert "Payment Failed" in subject
    assert "Card expired" in body


def test_notification_send_request_model():
    req = NotificationSendRequest(
        recipient_email="user@example.com",
        recipient_name="John Doe",
        subject="Welcome to our platform",
        template_name="welcome",
        template_data={"username": "johndoe"},
    )
    assert req.recipient_email == "user@example.com"
    assert req.template_name == "welcome"


def test_notification_requested_event_schema():
    assert EventType.NOTIFICATION_REQUESTED.value == "NotificationRequested"
    payload = NotificationRequestedPayload(
        recipient_email="customer@example.com",
        subject="Order Confirmed",
        template_name="order_confirmed",
        template_data={"order_id": "ord-99"},
    )
    assert payload.recipient_email == "customer@example.com"
    assert payload.subject == "Order Confirmed"
