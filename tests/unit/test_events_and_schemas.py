import json
from contracts.events.types import EventType
from contracts.events.schemas import (
    EventEnvelope,
    OrderCreatedPayload,
    OrderItemPayload,
    PaymentSucceededPayload,
    ShipmentCreatedPayload,
)


def test_order_created_event_serialization():
    payload = OrderCreatedPayload(
        order_id="ord-001",
        order_number="ORD-123456",
        customer_id="cust-99",
        customer_email="cust@example.com",
        items=[
            OrderItemPayload(
                product_id="prod-101",
                product_name="Headphones",
                unit_price=19999,
                quantity=2,
            )
        ],
        total_amount=39998,
        currency="USD",
        shipping_address={"street": "123 Main St", "city": "NYC", "state": "NY", "postal_code": "10001"},
    )

    envelope = EventEnvelope(
        event_type=EventType.ORDER_CREATED,
        aggregate_id="ord-001",
        correlation_id="corr-test-01",
        producer="order-service",
        payload=payload.model_dump(),
    )

    serialized = envelope.model_dump_json()
    data = json.loads(serialized)

    assert data["event_type"] == "OrderCreated"
    assert data["aggregate_id"] == "ord-001"
    assert data["payload"]["total_amount"] == 39998
    assert len(data["payload"]["items"]) == 1
