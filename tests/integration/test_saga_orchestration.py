import pytest
from contracts.events.types import EventType


class MockSagaOrchestrator:
    def __init__(self):
        self.orders = {}
        self.saga_state = {}
        self.events_published = []
        self.inventory = {"prod-101": 5}

    def create_order(self, order_id: str, items: list, amount: int):
        self.orders[order_id] = {
            "status": "PENDING",
            "items": items,
            "amount": amount,
        }
        self.saga_state[order_id] = "STARTED"
        self.events_published.append({
            "event_type": EventType.ORDER_CREATED.value,
            "order_id": order_id,
        })

    def handle_inventory_reserved(self, order_id: str):
        self.saga_state[order_id] = "INVENTORY_RESERVED"
        self.orders[order_id]["status"] = "AWAITING_PAYMENT"
        self.events_published.append({
            "event_type": EventType.PAYMENT_INITIATED.value,
            "order_id": order_id,
        })

    def handle_inventory_failed(self, order_id: str, reason: str):
        self.saga_state[order_id] = "FAILED"
        self.orders[order_id]["status"] = "CANCELLED"
        self.orders[order_id]["reason"] = reason
        self.events_published.append({
            "event_type": EventType.ORDER_CANCELLED.value,
            "order_id": order_id,
        })

    def handle_payment_succeeded(self, order_id: str):
        self.saga_state[order_id] = "COMPLETED"
        self.orders[order_id]["status"] = "CONFIRMED"
        self.events_published.append({
            "event_type": EventType.ORDER_CONFIRMED.value,
            "order_id": order_id,
        })

    def handle_payment_failed(self, order_id: str):
        # Compensation: release inventory reservation
        self.saga_state[order_id] = "COMPENSATING"
        self.orders[order_id]["status"] = "CANCELLED"
        self.orders[order_id]["reason"] = "Payment Failed"
        self.events_published.append({
            "event_type": EventType.ORDER_CANCELLED.value,
            "order_id": order_id,
            "inventory_release_required": True,
        })


def test_happy_path_saga():
    saga = MockSagaOrchestrator()
    order_id = "ord-happy-1"

    saga.create_order(order_id, [{"product_id": "prod-101", "quantity": 1}], 2000)
    assert saga.orders[order_id]["status"] == "PENDING"
    assert saga.saga_state[order_id] == "STARTED"

    # Step 1: Inventory succeeds
    saga.handle_inventory_reserved(order_id)
    assert saga.orders[order_id]["status"] == "AWAITING_PAYMENT"
    assert saga.saga_state[order_id] == "INVENTORY_RESERVED"

    # Step 2: Payment succeeds
    saga.handle_payment_succeeded(order_id)
    assert saga.orders[order_id]["status"] == "CONFIRMED"
    assert saga.saga_state[order_id] == "COMPLETED"

    event_types = [e["event_type"] for e in saga.events_published]
    assert event_types == ["OrderCreated", "PaymentInitiated", "OrderConfirmed"]


def test_inventory_failure_compensation():
    saga = MockSagaOrchestrator()
    order_id = "ord-fail-inv"

    saga.create_order(order_id, [{"product_id": "prod-101", "quantity": 999}], 999000)
    saga.handle_inventory_failed(order_id, "Insufficient stock")

    assert saga.orders[order_id]["status"] == "CANCELLED"
    assert saga.saga_state[order_id] == "FAILED"
    assert saga.events_published[-1]["event_type"] == "OrderCancelled"


def test_payment_failure_compensation():
    saga = MockSagaOrchestrator()
    order_id = "ord-fail-pay"

    saga.create_order(order_id, [{"product_id": "prod-101", "quantity": 1}], 2000)
    saga.handle_inventory_reserved(order_id)

    # Payment fails
    saga.handle_payment_failed(order_id)

    assert saga.orders[order_id]["status"] == "CANCELLED"
    assert saga.saga_state[order_id] == "COMPENSATING"
    assert saga.events_published[-1]["event_type"] == "OrderCancelled"
    assert saga.events_published[-1]["inventory_release_required"] is True

