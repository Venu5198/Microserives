import os
import uuid

import httpx
import pytest
from ecommerce_common.security import create_jwt_token

BASE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:18002")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:30080")
JWT_SECRET = os.getenv(
    "JWT_SECRET_KEY",
    "supersecretjwtkeychangeinproductionminimum32characterslong",
)


def make_token(user_id: str, role: str, email: str = "test@ecommerce.local") -> str:
    return create_jwt_token(
        payload={"sub": user_id, "email": email, "role": role},
        secret_key=JWT_SECRET,
    )


@pytest.mark.asyncio
async def test_product_health_and_ready_endpoints():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"
        if "18002" in BASE_URL or "product-service" in BASE_URL:
            assert health_resp.json()["service"] == "product-service"
            ready_resp = await client.get("/ready")
            assert ready_resp.status_code == 200
            assert ready_resp.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_product_admin_rbac_and_crud_flow():
    admin_token = make_token("admin-user-001", "ADMIN", "admin@ecommerce.local")
    cust_token = make_token("cust-user-001", "CUSTOMER", "cust@ecommerce.local")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    sku = f"SKU-{uuid.uuid4().hex[:6].upper()}"
    product_payload = {
        "name": "Noise Cancelling Headphones",
        "description": "Premium active noise cancellation",
        "price": 24999,
        "sku": sku,
        "category": "Audio",
        "is_active": True,
    }

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Non-admin cannot create product
        forbidden_resp = await client.post(
            "/api/v1/products", json=product_payload, headers=cust_headers
        )
        assert forbidden_resp.status_code == 403

        # 2. Admin can create product
        create_resp = await client.post(
            "/api/v1/products", json=product_payload, headers=admin_headers
        )
        assert create_resp.status_code == 201
        created_data = create_resp.json()
        product_id = created_data["id"]
        assert created_data["sku"] == sku
        assert created_data["price"] == 24999

        # 3. Read product — 1st read (MISS or HIT), 2nd read should return product
        get_resp1 = await client.get(f"/api/v1/products/{product_id}")
        assert get_resp1.status_code == 200
        assert get_resp1.json()["id"] == product_id

        get_resp2 = await client.get(f"/api/v1/products/{product_id}")
        assert get_resp2.status_code == 200
        assert get_resp2.json()["sku"] == sku

        # 4. Filter by category
        list_resp = await client.get("/api/v1/products?category=Audio")
        assert list_resp.status_code == 200
        raw_list = list_resp.json()
        items = raw_list if isinstance(raw_list, list) else raw_list.get("items", [])
        assert any(p["id"] == product_id for p in items)

        # 5. Update product as Admin
        update_resp = await client.put(
            f"/api/v1/products/{product_id}",
            json={"price": 22999, "name": "Noise Cancelling Headphones Pro"},
            headers=admin_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["price"] == 22999

        # 6. Delete product as Admin
        delete_resp = await client.delete(
            f"/api/v1/products/{product_id}", headers=admin_headers
        )
        assert delete_resp.status_code in [200, 204]

        # 7. Verify soft deletion
        get_deleted = await client.get(f"/api/v1/products/{product_id}")
        assert get_deleted.status_code == 200
        assert get_deleted.json()["is_active"] is False
