import pytest
from main import calculate_cart_response
from models import CartItemAdd, CartItemUpdate, utc_now
from pydantic import ValidationError


def test_cart_item_add_valid():
    item = CartItemAdd(product_id="prod-101", quantity=3)
    assert item.product_id == "prod-101"
    assert item.quantity == 3


def test_cart_item_add_invalid_quantity():
    with pytest.raises(ValidationError):
        CartItemAdd(product_id="prod-101", quantity=0)

    with pytest.raises(ValidationError):
        CartItemAdd(product_id="prod-101", quantity=-2)


def test_cart_item_update_model():
    update = CartItemUpdate(quantity=5)
    assert update.quantity == 5


def test_cart_calculations_subtotal_and_totals():
    items = [
        {
            "product_id": "prod-101",
            "product_name": "Mechanical Keyboard",
            "unit_price": 8999,  # $89.99
            "quantity": 2,
            "image_url": "https://example.com/kb.jpg",
        },
        {
            "product_id": "prod-102",
            "product_name": "Gaming Mouse",
            "unit_price": 4999,  # $49.99
            "quantity": 1,
            "image_url": "https://example.com/mouse.jpg",
        },
    ]

    cart_resp = calculate_cart_response(
        user_id="user-123",
        items=items,
        updated_at=utc_now(),
    )

    assert cart_resp.user_id == "user-123"
    assert len(cart_resp.items) == 2
    assert cart_resp.total_items == 3
    # Subtotals: (8999 * 2) + (4999 * 1) = 17998 + 4999 = 22997
    assert cart_resp.total_amount == 22997
    assert cart_resp.items[0].subtotal == 17998
    assert cart_resp.items[1].subtotal == 4999


def test_cart_empty_calculation():
    cart_resp = calculate_cart_response(
        user_id="user-empty",
        items=[],
        updated_at=utc_now(),
    )
    assert cart_resp.total_amount == 0
    assert cart_resp.total_items == 0
    assert len(cart_resp.items) == 0

