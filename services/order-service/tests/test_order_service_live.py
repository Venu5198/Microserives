import os
import uuid

import httpx
import pytest
from ecommerce_common.security import create_jwt_token

BASE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:30080")
JWT_SECRET = os.getenv(
    "JWT_SECRET_KEY",
    "supersecretjwtkeychangeinproductionminimum32characterslong",
)


def make_token(
    user_id: str, email: str = "customer@ecommerce.local", role: str = "CUSTOMER"
) -> str:
    return create_jwt_token(
        payload={"sub": user_id, "email": email, "role": role},
        secret_key=JWT_SECRET,
    )


@pytest.mark.asyncio
async def test_order_health_and_ready():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_order_creation_and_query_flow():
    customer_id = f"cust-ord-{uuid.uuid4().hex[:8]}"
    customer_email = f"{customer_id}@ecommerce.local"
    cust_token = make_token(customer_id, customer_email)
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    order_payload = {
        "items": [
            {
                "product_id": "prod-101",
                "product_name": "Noise Cancelling Headphones",
                "unit_price": 19999,
                "quantity": 1,
            }
        ],
        "shipping_address": {
            "street": "100 Tech Way",
            "city": "Austin",
            "state": "TX",
            "postal_code": "78701",
            "country": "US",
        },
        "payment_method": "sandbox_credit_card",
    }

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Unauthenticated cannot create order
        unauth_resp = await client.post("/api/v1/orders", json=order_payload)
        assert unauth_resp.status_code == 401

        # 2. Authenticated user creates order
        create_resp = await client.post(
            "/api/v1/orders", json=order_payload, headers=cust_headers
        )
        assert create_resp.status_code == 201
        order_data = create_resp.json()
        order_id = order_data["id"]
        assert order_data["customer_id"] == customer_id
        assert order_data["total_amount"] == 19999
        assert order_data["status"] in ["PENDING", "AWAITING_PAYMENT", "CONFIRMED"]

        # 3. Retrieve single order
        get_resp = await client.get(
            f"/api/v1/orders/{order_id}", headers=cust_headers
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == order_id

        # 4. List orders for customer
        list_resp = await client.get("/api/v1/orders", headers=cust_headers)
        assert list_resp.status_code == 200
        orders_list = list_resp.json()
        items = (
            orders_list if isinstance(orders_list, list) else orders_list.get("items", [])
        )
        assert any(o["id"] == order_id for o in items)

