import os

import httpx
import pytest
from ecommerce_common.security import create_jwt_token

BASE_URL = os.getenv("SHIPPING_SERVICE_URL", "http://localhost:30080")
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
async def test_shipping_health():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_shipping_rbac_and_tracking_lookup():
    cust_token = make_token("cust-ship-01", "CUSTOMER")
    ops_token = make_token("ops-ship-01", "OPERATIONS")
    cust_headers = {"Authorization": f"Bearer {cust_token}"}
    ops_headers = {"Authorization": f"Bearer {ops_token}"}

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Customer cannot update shipment status
        unauth_update = await client.patch(
            "/api/v1/shipments/shp-dummy-12345/status",
            json={"status": "IN_TRANSIT", "location": "Warehouse A"},
            headers=cust_headers,
        )
        assert unauth_update.status_code == 403

        # 2. Operations can list shipments
        list_resp = await client.get("/api/v1/shipments", headers=ops_headers)
        assert list_resp.status_code == 200
        assert isinstance(list_resp.json(), list)
