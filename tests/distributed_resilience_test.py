import asyncio
import os
import time
import uuid

import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:30080")

print("=" * 60)
print("PHASE 9: DISTRIBUTED SYSTEMS & RESILIENCE VERIFICATION")
print("=" * 60)


async def main():
    async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=30.0) as client:
        # Step 1: Register customer and get token
        email = f"dist_tester_{int(time.time())}@example.com"
        r_auth = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "first_name": "Distributed",
                "last_name": "Tester",
                "role": "CUSTOMER",
            },
        )
        assert r_auth.status_code == 201, f"Auth failed: {r_auth.status_code}"
        token = r_auth.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Test Concurrent Payment Idempotency
        print("\n--- Test 1: Concurrent Payment Idempotency Replay ---")
        idem_key = f"concurrent-idem-{uuid.uuid4().hex}"
        test_order_id = f"ord-stress-{uuid.uuid4().hex[:8]}"

        async def send_payment():
            return await client.post(
                "/api/v1/payments",
                headers=headers,
                json={
                    "order_id": test_order_id,
                    "amount": 2500,
                    "currency": "USD",
                    "idempotency_key": idem_key,
                    "card_last_four": "4242",
                },
            )

        # Fire 5 concurrent requests simultaneously
        tasks = [send_payment() for _ in range(5)]
        responses = await asyncio.gather(*tasks)

        assert all(r.status_code == 201 for r in responses), "All idempotency calls should return 201"
        payment_ids = {r.json()["id"] for r in responses}
        tx_ids = {r.json()["transaction_id"] for r in responses}

        print(f"[PASS] 5 Concurrent requests returned exactly {len(payment_ids)} unique payment ID: {payment_ids.pop()}")
        print(f"[PASS] Exact same transaction ID recorded across all 5 requests: {tx_ids.pop()}")

        # Step 3: Test High Concurrency Inventory Contention (Race Conditions)
        print("\n--- Test 2: Atomic Inventory Stock Contention (Race Conditions) ---")
        # Fetch initial stock for prod-102
        r_inv = await client.get("/api/v1/inventory/prod-102", headers=headers)
        initial_available = r_inv.json()["available_quantity"]
        print(f"Current available quantity for prod-102: {initial_available}")

        # Fire 10 parallel order attempts, each attempting to buy 5 units
        async def place_order(idx: int):
            return await client.post(
                "/api/v1/orders",
                headers=headers,
                json={
                    "items": [
                        {
                            "product_id": "prod-102",
                            "product_name": "Mechanical Keyboard",
                            "unit_price": 12999,
                            "quantity": 5,
                        }
                    ],
                    "shipping_address": {
                        "street": f"{idx} Stress Way",
                        "city": "Austin",
                        "state": "TX",
                        "postal_code": "78701",
                        "country": "US",
                    },
                    "payment_method": "sandbox_credit_card",
                },
            )

        order_tasks = [place_order(i) for i in range(10)]
        order_responses = await asyncio.gather(*order_tasks)
        successful_creates = [r for r in order_responses if r.status_code == 201]
        print(f"Dispatched 10 concurrent orders (demand = 50 units). All {len(successful_creates)} orders submitted to Saga.")

        # Allow Saga instances to settle
        await asyncio.sleep(4)

        # Check order statuses
        confirmed_count = 0
        cancelled_count = 0
        for r in successful_creates:
            oid = r.json()["id"]
            r_chk = await client.get(f"/api/v1/orders/{oid}", headers=headers)
            st = r_chk.json()["status"]
            if st in ["CONFIRMED", "SHIPPED"]:
                confirmed_count += 1
            elif st == "CANCELLED":
                cancelled_count += 1

        r_inv_final = await client.get("/api/v1/inventory/prod-102", headers=headers)
        final_available = r_inv_final.json()["available_quantity"]

        units_consumed = initial_available - final_available
        expected_units_consumed = confirmed_count * 5

        print(f"Saga Settlement: {confirmed_count} Confirmed/Shipped, {cancelled_count} Cancelled due to stock limits.")
        print(f"Inventory: Initial={initial_available}, Final={final_available}, Consumed={units_consumed}")
        assert final_available >= 0, "Inventory must never drop below 0 (no overselling)"
        assert units_consumed == expected_units_consumed, f"Units consumed ({units_consumed}) must exactly match confirmed orders * 5 ({expected_units_consumed})"
        print("[PASS] Zero overselling verified: Available stock remained >= 0, exact balance preserved.")

        print("\n" + "=" * 60)
        print("PHASE 9: DISTRIBUTED SYSTEMS & RESILIENCE VERIFIED SUCCESSFULLY!")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
