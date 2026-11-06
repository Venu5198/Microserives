# Order Service — Independent Microservice Engineering Guide

**Service Name**: `order-service`  
**Container Port**: `8005`  
**Default Database**: `order_db` (MongoDB)  
**Message Broker**: RabbitMQ (`ecommerce.events` topic exchange)  
**Primary Responsibilities**: Order lifecycle management, Saga orchestration, transaction state persistence, order cancellation, and status tracking.

---

## 1. Architecture & Distributed Saga Orchestration

- **Owned Collections**:
  - `orders`: Order master records (`_id`, `order_number`, `customer_id`, `customer_email`, `items`, `total_amount`, `status`, `shipping_address`, `payment_id`, `tracking_number`, `created_at`, `updated_at`).
  - `saga_instances`: Distributed Saga tracking documents (`order_id`, `current_state`, `history: [{state, details, timestamp}]`, `updated_at`).
  - `outbox`: Transactional outbox records for asynchronous RabbitMQ event publishing.
- **Saga State Machine**:
  - `STARTED`: Order created -> Emits `OrderCreated` -> Triggers stock reservation in Inventory Service.
  - `INVENTORY_RESERVED`: Inventory reserved -> Emits `PaymentInitiated` -> Triggers charge in Payment Service.
  - `COMPLETED`: Payment succeeded -> Transitions status to `CONFIRMED` -> Emits `OrderConfirmed` (triggers shipment creation in Shipping Service).
  - `COMPENSATING`: Payment failed -> Transitions status to `CANCELLED` -> Emits `OrderCancelled` (releases inventory in Inventory Service).
  - `FAILED`: Inventory reservation failed -> Transitions status to `CANCELLED` -> Emits `OrderCancelled`.

---

## 2. API Specification

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Liveness probe & service ping. |
| `GET` | `/ready` | Public | Readiness probe (MongoDB ping). |
| `GET` | `/metrics` | Public | Prometheus scrape metrics. |
| `POST` | `/api/v1/orders` | Bearer Token | Place new order and initialize Saga workflow. |
| `GET` | `/api/v1/orders/{order_id}` | Bearer Token | Retrieve single order details. |
| `GET` | `/api/v1/orders` | Bearer Token | List orders for authenticated user (or all if Admin). |
| `POST` | `/api/v1/orders/{order_id}/cancel` | Bearer Token | Request order cancellation with compensatory triggers. |

---

## 3. Local Development & Testing

```bash
# Unit tests
pytest services/order-service/tests/test_order_service_unit.py -v

# Live API tests
pytest services/order-service/tests/test_order_service_live.py -v
```

