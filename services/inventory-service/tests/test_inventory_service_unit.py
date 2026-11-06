
import pytest
from ecommerce_common.security import (
    create_jwt_token,
    decode_jwt_token,
)
from models import (
    InventoryItemCreate,
    InventoryStockAdjust,
    ReserveItemRequest,
    ReserveStockRequest,
)
from pydantic import ValidationError

from contracts.events.schemas import (
    InventoryReservationFailedPayload,
    InventoryReservedPayload,
    OrderItemPayload,
)
from contracts.events.types import EventType

SECRET_KEY = "test-secret-key-at-least-32-chars-long-for-testing"


def test_inventory_item_create_model_valid():
    item = InventoryItemCreate(
        product_id="prod-101",
        sku="SKU-101",
        available_quantity=50,
        low_stock_threshold=5,
    )
    assert item.product_id == "prod-101"
    assert item.available_quantity == 50
    assert item.low_stock_threshold == 5


def test_inventory_item_create_negative_quantity():
    with pytest.raises(ValidationError):
        InventoryItemCreate(
            product_id="prod-102",
            sku="SKU-102",
            available_quantity=-10,
        )


def test_inventory_stock_adjust_model():
    adjust_pos = InventoryStockAdjust(adjustment=25, reason="Restock delivery")
    assert adjust_pos.adjustment == 25
    assert adjust_pos.reason == "Restock delivery"

    adjust_neg = InventoryStockAdjust(adjustment=-5, reason="Damaged items written off")
    assert adjust_neg.adjustment == -5


def test_reserve_stock_request_model():
    req = ReserveStockRequest(
        order_id="order-1234",
        items=[
            ReserveItemRequest(product_id="prod-101", quantity=2),
            ReserveItemRequest(product_id="prod-102", quantity=1),
        ],
    )
    assert req.order_id == "order-1234"
    assert len(req.items) == 2
    assert req.items[0].quantity == 2


def test_reserve_stock_request_invalid_zero_quantity():
    with pytest.raises(ValidationError):
        ReserveItemRequest(product_id="prod-101", quantity=0)


def test_inventory_events():
    assert EventType.INVENTORY_RESERVED.value == "InventoryReserved"
    assert EventType.INVENTORY_RESERVATION_FAILED.value == "InventoryReservationFailed"

    item_payload = OrderItemPayload(
        product_id="prod-101",
        product_name="Product 101",
        unit_price=1999,
        quantity=2,
    )

    reserved_payload = InventoryReservedPayload(
        order_id="order-999",
        reservation_id="res-001",
        reserved_items=[item_payload],
    )
    assert reserved_payload.order_id == "order-999"
    assert len(reserved_payload.reserved_items) == 1

    failed_payload = InventoryReservationFailedPayload(
        order_id="order-999",
        reason="Insufficient stock for product prod-101",
        failed_items=[item_payload],
    )
    assert "Insufficient" in failed_payload.reason


def test_inventory_rbac_roles():
    admin_token = create_jwt_token(
        payload={"sub": "admin-1", "role": "ADMIN"},
        secret_key=SECRET_KEY,
    )
    claims_admin = decode_jwt_token(admin_token, secret_key=SECRET_KEY)
    assert claims_admin["role"] in ["ADMIN", "OPERATIONS"]

    ops_token = create_jwt_token(
        payload={"sub": "ops-1", "role": "OPERATIONS"},
        secret_key=SECRET_KEY,
    )
    claims_ops = decode_jwt_token(ops_token, secret_key=SECRET_KEY)
    assert claims_ops["role"] in ["ADMIN", "OPERATIONS"]

    cust_token = create_jwt_token(
        payload={"sub": "cust-1", "role": "CUSTOMER"},
        secret_key=SECRET_KEY,
    )
    claims_cust = decode_jwt_token(cust_token, secret_key=SECRET_KEY)
    assert claims_cust["role"] not in ["ADMIN", "OPERATIONS"]
