import uuid

import pytest
from ecommerce_common.security import (
    create_jwt_token,
    decode_jwt_token,
)
from models import ProductCreate, ProductUpdate
from pydantic import ValidationError

from contracts.events.schemas import (
    ProductCreatedPayload,
    ProductDeletedPayload,
    ProductUpdatedPayload,
)
from contracts.events.types import EventType

SECRET_KEY = "test-secret-key-at-least-32-chars-long-for-testing"


def test_product_create_model_valid():
    product = ProductCreate(
        name="Wireless Gaming Mouse",
        description="High-precision 16000 DPI sensor",
        price=7999,
        sku="MOUSE-PRO-001",
        category="Electronics",
        is_active=True,
    )
    assert product.name == "Wireless Gaming Mouse"
    assert product.sku == "MOUSE-PRO-001"
    assert product.price == 7999
    assert product.category == "Electronics"
    assert product.is_active is True


def test_product_create_model_invalid_price():
    with pytest.raises(ValidationError):
        ProductCreate(
            name="Free Product",
            description="desc",
            price=-1000,
            sku="FREE-001",
            category="Miscellaneous",
        )


def test_product_create_model_missing_sku():
    with pytest.raises(ValidationError):
        ProductCreate(
            name="No SKU Item",
            description="desc",
            price=1999,
            category="Home",
        )


def test_product_update_model_partial():
    update = ProductUpdate(price=8999, is_active=False)
    dumped = update.model_dump(exclude_unset=True)
    assert dumped == {"price": 8999, "is_active": False}
    assert "name" not in dumped


def test_product_events_and_payloads():
    product_id = str(uuid.uuid4())
    created = ProductCreatedPayload(
        product_id=product_id,
        sku="LAPTOP-ULTRA",
        name="Ultra Laptop 16",
        price=149999,
        category="Computers",
    )
    assert created.product_id == product_id
    assert created.price == 149999
    assert EventType.PRODUCT_CREATED.value == "ProductCreated"

    updated = ProductUpdatedPayload(
        product_id=product_id,
        sku="LAPTOP-ULTRA",
        price=139999,
        is_active=True,
    )
    assert updated.price == 139999
    assert EventType.PRODUCT_UPDATED.value == "ProductUpdated"

    deleted = ProductDeletedPayload(
        product_id=product_id,
        sku="LAPTOP-ULTRA",
    )
    assert deleted.sku == "LAPTOP-ULTRA"
    assert EventType.PRODUCT_DELETED.value == "ProductDeleted"


def test_product_admin_rbac_role():
    admin_token = create_jwt_token(
        payload={"sub": "admin-1", "email": "admin@ecommerce.local", "role": "ADMIN"},
        secret_key=SECRET_KEY,
    )
    claims = decode_jwt_token(admin_token, secret_key=SECRET_KEY)
    assert claims["role"] == "ADMIN"

    customer_token = create_jwt_token(
        payload={"sub": "cust-1", "email": "cust@ecommerce.local", "role": "CUSTOMER"},
        secret_key=SECRET_KEY,
    )
    claims_cust = decode_jwt_token(customer_token, secret_key=SECRET_KEY)
    assert claims_cust["role"] == "CUSTOMER"
