from models import (
    ShipmentStatus,
    ShipmentStatusUpdateRequest,
    TrackingEventResponse,
    utc_now,
)

from contracts.events.schemas import (
    ShipmentCreatedPayload,
    ShipmentStatusUpdatedPayload,
)
from contracts.events.types import EventType


def test_shipment_statuses():
    assert ShipmentStatus.CREATED.value == "CREATED"
    assert ShipmentStatus.IN_TRANSIT.value == "IN_TRANSIT"
    assert ShipmentStatus.OUT_FOR_DELIVERY.value == "OUT_FOR_DELIVERY"
    assert ShipmentStatus.DELIVERED.value == "DELIVERED"
    assert ShipmentStatus.RETURNED.value == "RETURNED"


def test_shipment_status_update_request_valid():
    req = ShipmentStatusUpdateRequest(
        status=ShipmentStatus.IN_TRANSIT,
        location="Chicago Distribution Hub",
        notes="Arrived at sorting center",
    )
    assert req.status == ShipmentStatus.IN_TRANSIT
    assert req.location == "Chicago Distribution Hub"


def test_tracking_event_response_model():
    now = utc_now()
    event = TrackingEventResponse(
        status="IN_TRANSIT",
        location="Dallas Hub",
        description="Departed facility",
        timestamp=now,
    )
    assert event.status == "IN_TRANSIT"
    assert event.location == "Dallas Hub"
    assert event.timestamp == now


def test_shipping_events():
    assert EventType.SHIPMENT_CREATED.value == "ShipmentCreated"
    assert EventType.SHIPMENT_STATUS_UPDATED.value == "ShipmentStatusUpdated"

    created = ShipmentCreatedPayload(
        shipment_id="shp-001",
        order_id="order-001",
        tracking_number="TRK-FEDEX-12345678",
        carrier="Standard Express",
        estimated_delivery="2026-11-10T12:00:00Z",
        recipient_email="customer@example.com",
        recipient_name="Jane Doe",
        shipping_address={"street": "123 Tech Rd", "city": "Seattle", "state": "WA"},
    )
    assert created.shipment_id == "shp-001"
    assert created.tracking_number == "TRK-FEDEX-12345678"

    updated = ShipmentStatusUpdatedPayload(
        shipment_id="shp-001",
        order_id="order-001",
        tracking_number="TRK-FEDEX-12345678",
        old_status="CREATED",
        new_status="IN_TRANSIT",
        location="Atlanta",
        notes="Out for transit",
    )
    assert updated.new_status == "IN_TRANSIT"
