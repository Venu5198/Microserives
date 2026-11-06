import os
import uuid

import httpx
import pytest

BASE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:18001")


@pytest.mark.asyncio
async def test_health_and_ready_endpoints():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"
        # If routed directly to user-service vs through API Gateway
        if "18001" in BASE_URL or "user-service" in BASE_URL:
            assert health_resp.json()["service"] == "user-service"
            ready_resp = await client.get("/ready")
            assert ready_resp.status_code == 200
            assert ready_resp.json()["status"] == "ready"
            assert ready_resp.json()["database"] == "connected"
        else:
            assert health_resp.json()["service"] in ["user-service", "api-gateway"]


@pytest.mark.asyncio
async def test_user_registration_and_login_flow():
    email = f"engineer_{uuid.uuid4().hex[:8]}@ecommerce.local"
    password = "StrongPassword987!"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Register new user
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Test",
                "last_name": "Engineer",
            },
        )
        assert reg_resp.status_code == 201
        reg_data = reg_resp.json()
        assert "access_token" in reg_data
        assert "refresh_token" in reg_data
        assert reg_data["email"] == email.lower()
        assert reg_data["role"] == "CUSTOMER"

        user_id = reg_data["user_id"]
        access_token = reg_data["access_token"]
        assert reg_data["refresh_token"]

        # 2. Login with correct password
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        assert login_data["user_id"] == user_id

        # 3. Login with wrong password (401 Unauthorized)
        wrong_pass_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword123!"},
        )
        assert wrong_pass_resp.status_code == 401

        # 4. Access user profile using access token
        profile_resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert profile_resp.status_code == 200
        profile_data = profile_resp.json()
        assert profile_data["email"] == email.lower()
        assert profile_data["role"] == "CUSTOMER"

        # 5. Add user address
        addr_resp = await client.post(
            "/api/v1/users/me/addresses",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "Headquarters",
                "street": "100 Innovation Way",
                "city": "Austin",
                "state": "TX",
                "postal_code": "78701",
                "is_default": True,
            },
        )
        assert addr_resp.status_code == 200
        assert addr_resp.json()["city"] == "Austin"


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_revocation():
    email = f"rotator_{uuid.uuid4().hex[:8]}@ecommerce.local"
    password = "RotationPassword123!"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # Register
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Token",
                "last_name": "Rotator",
            },
        )
        token1 = reg_resp.json()["refresh_token"]

        # 1. Rotate refresh token
        rotate_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token1},
        )
        assert rotate_resp.status_code == 200
        token2 = rotate_resp.json()["refresh_token"]
        assert token2 != token1

        # 2. Re-using old token must fail (revoked token replay defense)
        replay_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token1},
        )
        assert replay_resp.status_code == 401
        assert "Invalid refresh token" in replay_resp.json()["detail"]

        # 3. Logout with active refresh token
        new_access_token = rotate_resp.json()["access_token"]
        logout_resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {new_access_token}"},
            json={"refresh_token": token2},
        )
        assert logout_resp.status_code == 200

        # 4. Token2 should now also be rejected
        post_logout_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token2},
        )
        assert post_logout_resp.status_code == 401


@pytest.mark.asyncio
async def test_rbac_and_data_isolation():
    email = f"customer_{uuid.uuid4().hex[:8]}@ecommerce.local"
    password = "CustomerPass123!"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Cust",
                "last_name": "Omer",
            },
        )
        cust_token = reg_resp.json()["access_token"]

        # 1. Customer role cannot list all users (403 Forbidden)
        admin_endpoint_resp = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {cust_token}"},
        )
        assert admin_endpoint_resp.status_code == 403

        # 2. Admin role can list users
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@ecommerce.local", "password": "AdminPass123!"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]

        admin_list_resp = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_list_resp.status_code == 200
        assert isinstance(admin_list_resp.json(), list)


@pytest.mark.asyncio
async def test_duplicate_registration_conflict():
    email = f"dupe_{uuid.uuid4().hex[:8]}@ecommerce.local"
    password = "UniquePassword123!"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        first = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "A",
                "last_name": "B",
            },
        )
        assert first.status_code == 201

        # Duplicate email registration must return 409 Conflict
        duplicate = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": "A",
                "last_name": "B",
            },
        )
        assert duplicate.status_code == 409
        assert "already exists" in duplicate.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_jwt_handling():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # Tampered signature
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.tampered.token"},
        )
        assert resp.status_code == 401

        # Missing token
        resp_no_token = await client.get("/api/v1/users/me")
        assert resp_no_token.status_code == 401
