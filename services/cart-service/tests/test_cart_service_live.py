import os
import uuid

import httpx
import pytest
from ecommerce_common.security import create_jwt_token

BASE_URL = os.getenv("CART_SERVICE_URL", "http://localhost:30080")
JWT_SECRET = os.getenv(
    "JWT_SECRET_KEY",
    "supersecretjwtkeychangeinproductionminimum32characterslong",
)


def make_token(user_id: str, role: str = "CUSTOMER") -> str:
    return create_jwt_token(
        payload={"sub": user_id, "email": f"{user_id}@ecommerce.local", "role": role},
        secret_key=JWT_SECRET,
    )


@pytest.mark.asyncio
async def test_cart_health():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_cart_crud_flow():
    customer_id = f"cust-cart-{uuid.uuid4().hex[:8]}"
    cust_token = make_token(customer_id)
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Unauthenticated cannot access cart
        unauth_resp = await client.get("/api/v1/cart")
        assert unauth_resp.status_code == 401

        # 2. Authenticated user gets empty cart
        empty_resp = await client.get("/api/v1/cart", headers=cust_headers)
        assert empty_resp.status_code == 200
        empty_data = empty_resp.json()
        assert empty_data["total_items"] == 0
        assert empty_data["total_amount"] == 0

        # 3. Add seeded item prod-101 to cart
        add_resp = await client.post(
            "/api/v1/cart/items",
            json={"product_id": "prod-101", "quantity": 2},
            headers=cust_headers,
        )
        assert add_resp.status_code == 200
        cart_data = add_resp.json()
        assert cart_data["total_items"] == 2
        assert any(it["product_id"] == "prod-101" for it in cart_data["items"])

        # 4. Update item quantity to 3
        update_resp = await client.put(
            "/api/v1/cart/items/prod-101",
            json={"quantity": 3},
            headers=cust_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["total_items"] == 3

        # 5. Delete item from cart
        del_resp = await client.delete(
            "/api/v1/cart/items/prod-101",
            headers=cust_headers,
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["total_items"] == 0

