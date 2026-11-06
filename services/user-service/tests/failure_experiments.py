import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:18001")
JWT_SECRET = os.getenv(
    "JWT_SECRET_KEY", "supersecretjwtkeychangeinproductionminimum32characterslong"
)


async def run_failure_experiments():
    print("=" * 65)
    print("USER SERVICE INDEPENDENT FAILURE EXPERIMENTS")
    print("=" * 65)

    async with httpx.AsyncClient(base_url=USER_SERVICE_URL, timeout=10.0) as client:
        # Experiment 1: Duplicate Registration Conflict
        print("\n--- [Experiment 1] Duplicate Registration Conflict ---")
        email = f"fail_dupe_{uuid.uuid4().hex[:6]}@ecommerce.local"
        reg_payload = {
            "email": email,
            "password": "Password123!",
            "first_name": "Dupe",
            "last_name": "Test",
        }
        resp1 = await client.post("/api/v1/auth/register", json=reg_payload)
        print(f"Initial Registration Status: {resp1.status_code}")
        assert resp1.status_code == 201

        resp2 = await client.post("/api/v1/auth/register", json=reg_payload)
        print(
            f"Duplicate Registration Status: {resp2.status_code} - Detail: {resp2.json().get('detail')}"
        )
        assert resp2.status_code == 409
        print("[PASS] Duplicate registration rejected with 409 Conflict")

        # Experiment 2: Concurrent Registration with Same Email
        print("\n--- [Experiment 2] Concurrent Registration with Same Email ---")
        concurrent_email = f"fail_concurrent_{uuid.uuid4().hex[:6]}@ecommerce.local"
        c_payload = {
            "email": concurrent_email,
            "password": "Password123!",
            "first_name": "Concurrent",
            "last_name": "User",
        }
        resps = await asyncio.gather(
            client.post("/api/v1/auth/register", json=c_payload),
            client.post("/api/v1/auth/register", json=c_payload),
            client.post("/api/v1/auth/register", json=c_payload),
            return_exceptions=True,
        )
        status_codes = [r.status_code for r in resps if isinstance(r, httpx.Response)]
        print(f"Concurrent status codes: {status_codes}")
        assert 201 in status_codes
        assert 409 in status_codes
        assert status_codes.count(201) == 1
        print(
            "[PASS] Exactly one concurrent registration succeeded (201); others rejected with 409 Conflict"
        )

        # Experiment 3: Invalid JWT Handling
        print("\n--- [Experiment 3] Invalid and Tampered JWT Handling ---")
        tampered_resp = await client.get(
            "/api/v1/users/me",
            headers={
                "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.signature"
            },
        )
        print(
            f"Tampered Token Status: {tampered_resp.status_code} - Detail: {tampered_resp.json().get('detail')}"
        )
        assert tampered_resp.status_code == 401
        print("[PASS] Tampered JWT rejected with 401 Unauthorized")

        # Experiment 4: Expired JWT Handling
        print("\n--- [Experiment 4] Expired JWT Access Token Handling ---")
        expired_token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "email": "exp@test.com",
                "role": "CUSTOMER",
                "exp": datetime.now(UTC) - timedelta(hours=1),
            },
            JWT_SECRET,
            algorithm="HS256",
        )
        expired_resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        print(
            f"Expired Token Status: {expired_resp.status_code} - Detail: {expired_resp.json().get('detail')}"
        )
        assert expired_resp.status_code == 401
        print("[PASS] Expired JWT rejected with 401 Unauthorized")

        # Experiment 5: Invalid and Expired Refresh Token Handling
        print("\n--- [Experiment 5] Invalid and Expired Refresh Token Handling ---")
        invalid_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "non-existent-uuid-refresh-token"},
        )
        print(
            f"Invalid Refresh Token Status: {invalid_refresh.status_code} - Detail: {invalid_refresh.json().get('detail')}"
        )
        assert invalid_refresh.status_code == 401
        print("[PASS] Invalid refresh token rejected with 401 Unauthorized")

        # Experiment 6: Customer Access to Restricted Admin Endpoint
        print("\n--- [Experiment 6] RBAC Security Isolation ---")
        cust_token = resp1.json()["access_token"]
        forbidden_resp = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {cust_token}"},
        )
        print(
            f"Customer Accessing Admin API Status: {forbidden_resp.status_code} - Detail: {forbidden_resp.json().get('detail')}"
        )
        assert forbidden_resp.status_code == 403
        print("[PASS] Access denied with 403 Forbidden")

    print("\n" + "=" * 65)
    print("ALL 6 FAILURE & SECURITY EXPERIMENTS VERIFIED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_failure_experiments())
