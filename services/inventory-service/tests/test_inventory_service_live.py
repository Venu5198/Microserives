import os

import httpx
import pytest
from ecommerce_common.security import create_jwt_token

BASE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:30080")
JWT_SECRET = os.getenv(
    "JWT_SECRET_KEY",
    "supersecretjwtkeychangeinproductionminimum32characterslong",
)


def make_token(user_id: str, role: str) -> str:
    return create_jwt_token(
        payload={"sub": user_id, "email": f"{user_id}@ecommerce.local", "role": role},
        secret_key=JWT_SECRET,
    )


@pytest.mark.asyncio
async def test_inventory_health_and_ready():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_inventory_rbac_and_stock_adjust():
    admin_token = make_token("admin-ops-01", "ADMIN")
    ops_token = make_token("ops-user-01", "OPERATIONS")
    cust_token = make_token("cust-user-01", "CUSTOMER")

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    ops_headers = {"Authorization": f"Bearer {ops_token}"}
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Customer cannot adjust stock
        cust_resp = await client.patch(
            "/api/v1/inventory/prod-101",
            json={"adjustment": 10, "reason": "Unauthorized restock attempt"},
            headers=cust_headers,
        )
        assert cust_resp.status_code == 403

        # 2. Get current stock
        get_resp = await client.get("/api/v1/inventory/prod-101")
        assert get_resp.status_code == 200
        initial_avail = get_resp.json()["available_quantity"]

        # 3. Operations can adjust stock
        adjust_resp = await client.patch(
            "/api/v1/inventory/prod-101",
            json={"adjustment": 5, "reason": "Restocked 5 units"},
            headers=ops_headers,
        )
        assert adjust_resp.status_code == 200
        assert adjust_resp.json()["available_quantity"] == initial_avail + 5

        # 4. Revert adjustment to keep state clean
        revert_resp = await client.patch(
            "/api/v1/inventory/prod-101",
            json={"adjustment": -5, "reason": "Reverting test restock"},
            headers=admin_headers,
        )
        assert revert_resp.status_code == 200
        assert revert_resp.json()["available_quantity"] == initial_avail

