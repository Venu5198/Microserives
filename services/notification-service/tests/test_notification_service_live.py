import os

import httpx
import pytest
from ecommerce_common.security import create_jwt_token

BASE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:30080")
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
async def test_notification_health():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_notification_send_and_list():
    admin_token = make_token("admin-notify-01", role="ADMIN")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    send_payload = {
        "recipient_email": "customer@example.com",
        "recipient_name": "Valued Customer",
        "subject": "Platform Update Notification",
        "template_name": "general",
        "template_data": {"message": "System running at full operational capacity"},
    }

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Send notification
        send_resp = await client.post(
            "/api/v1/notifications/send", json=send_payload, headers=admin_headers
        )
        assert send_resp.status_code == 200
        send_data = send_resp.json()
        assert send_data["recipient_email"] == "customer@example.com"
        assert send_data["status"] in ["SENT", "RETRYING", "FAILED"]

        # 2. List notifications
        list_resp = await client.get("/api/v1/notifications", headers=admin_headers)
        assert list_resp.status_code == 200
        notifications = list_resp.json()
        assert isinstance(notifications, list)
        assert any(n["recipient_email"] == "customer@example.com" for n in notifications)
