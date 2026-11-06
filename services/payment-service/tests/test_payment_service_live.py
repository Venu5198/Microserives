import os
import uuid

import httpx
import pytest
from ecommerce_common.security import create_jwt_token

BASE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:30080")
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
async def test_payment_health():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_payment_idempotency_and_decline_simulation():
    cust_token = make_token("cust-pay-01")
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    idempotency_key = f"idem-key-{uuid.uuid4().hex}"
    order_id = f"ord-{uuid.uuid4().hex[:8]}"

    payload = {
        "order_id": order_id,
        "amount": 4999,
        "currency": "USD",
        "payment_method": "sandbox_credit_card",
        "idempotency_key": idempotency_key,
        "card_last_four": "4242",
        "simulate_failure": False,
    }

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. First charge succeeds
        resp1 = await client.post(
            "/api/v1/payments", json=payload, headers=cust_headers
        )
        assert resp1.status_code == 201
        data1 = resp1.json()
        assert data1["status"] == "SUCCEEDED"
        payment_id_1 = data1["id"]
        assert data1["idempotency_key"] == idempotency_key

        # 2. Replay with identical idempotency key returns exact same payment ID and status
        resp2 = await client.post(
            "/api/v1/payments", json=payload, headers=cust_headers
        )
        assert resp2.status_code in [200, 201]
        data2 = resp2.json()
        assert data2["id"] == payment_id_1
        assert data2["status"] == "SUCCEEDED"

        # 3. Simulate declined card (card ending in 0002)
        decline_key = f"idem-decl-{uuid.uuid4().hex}"
        decline_payload = {
            "order_id": f"ord-decl-{uuid.uuid4().hex[:8]}",
            "amount": 2500,
            "currency": "USD",
            "payment_method": "sandbox_credit_card",
            "idempotency_key": decline_key,
            "card_last_four": "0002",
            "simulate_failure": True,
        }
        resp_decl = await client.post(
            "/api/v1/payments", json=decline_payload, headers=cust_headers
        )
        assert resp_decl.status_code == 201
        decl_data = resp_decl.json()
        assert decl_data["status"] == "FAILED"
        assert "declined" in decl_data["failure_reason"].lower()

