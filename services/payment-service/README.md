# Payment Service — Independent Microservice Engineering Guide

**Service Name**: `payment-service`  
**Container Port**: `8006`  
**Default Database**: `payment_db` (MongoDB)  
**Message Broker**: RabbitMQ (`ecommerce.events` topic exchange)  
**Primary Responsibilities**: Payment processing against sandbox gateway, strict idempotency enforcement, card masking, decline simulations, refund processing, and Saga orchestration events.

---

## 1. Architecture & Idempotency Guarantees

- **Owned Collections**:
  - `payments`: Processed charges (`_id`, `order_id`, `amount` in cents, `currency`, `status: PENDING|SUCCEEDED|FAILED|REFUNDED`, `transaction_id`, `card_last_four`, `failure_reason`, `idempotency_key`, `created_at`, `updated_at`).
  - `idempotency_keys`: Unique indexed idempotency registry (`_id: idempotency_key`, `payment_id`, `created_at`).
  - `refunds`: Refund transactions (`_id`, `payment_id`, `order_id`, `amount`, `status`, `reason`, `created_at`).
  - `outbox`: Transactional outbox records for RabbitMQ event publishing.
- **Duplicate Charge Prevention**:
  - Every payment mutation requires an `idempotency_key` (minimum 8 characters).
  - An atomic insert into `idempotency_keys` ensures that concurrent or repeated submissions with the same key never charge twice; subsequent requests return the cached result.
- **Sandbox Simulation**:
  - Cards ending in `0002` or requests with `simulate_failure=True` trigger sandbox declines ("Card declined: insufficient funds") and emit `PaymentFailed`.
  - Normal cards (e.g., `4242`) trigger successful sandbox authorizations with synthetic transaction IDs and emit `PaymentSucceeded`.

---

## 2. API Specification

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Liveness probe & service ping. |
| `GET` | `/ready` | Public | Readiness probe (MongoDB ping). |
| `GET` | `/metrics` | Public | Prometheus scrape metrics. |
| `POST` | `/api/v1/payments` | Bearer Token | Process payment charge with mandatory idempotency key. |
| `GET` | `/api/v1/payments/{payment_id}` | Bearer Token | Retrieve single payment record. |
| `GET` | `/api/v1/payments/order/{order_id}`| Bearer Token | Retrieve payment record by associated order ID. |
| `POST` | `/api/v1/payments/{payment_id}/refund` | Admin/Operations | Initiate refund with compensatory outbox events. |

---

## 3. Local Development & Testing

```bash
# Unit tests
pytest services/payment-service/tests/test_payment_service_unit.py -v

# Live API tests (idempotency, decline simulation)
pytest services/payment-service/tests/test_payment_service_live.py -v
```

