# Inventory Service — Independent Microservice Engineering Guide

**Service Name**: `inventory-service`  
**Container Port**: `8003`  
**Default Database**: `inventory_db` (MongoDB)  
**Message Broker**: RabbitMQ (`ecommerce.events` exchange)  
**Primary Responsibilities**: Stock level tracking, atomic reservations with rollback, overselling prevention, low stock alerts, stock ledger transactions, and Saga orchestration event integration.

---

## 1. Architecture & Concurrency Guarantees

- **Owned Collections**:
  - `inventory`: Product stock records (`product_id` unique indexed, `sku`, `available_quantity`, `reserved_quantity`, `sold_quantity`, `low_stock_threshold`, `updated_at`).
  - `inventory_reservations`: Active/confirmed/released order reservations (`_id`, `order_id` indexed, `items`, `status: RESERVED|CONFIRMED|RELEASED`, `created_at`).
  - `inventory_txs`: Immutable stock adjustment ledger (`tx_id`, `order_id`, `product_id`, `type: RESERVE|ROLLBACK_RESERVE|SOLD|ADJUST`, `quantity`, `created_at`).
  - `outbox`: Transactional outbox collection for reliable RabbitMQ event delivery.
- **Overselling Defense**:
  - Stock reservation uses atomic single-document conditional updates:
    ```json
    { "product_id": p_id, "available_quantity": { "$gte": qty } }
    ```
    with `{ "$inc": { "available_quantity": -qty, "reserved_quantity": qty } }`.
  - If any item in a multi-item order fails the conditional match (insufficient stock), all previously reserved items in that order are atomically rolled back (`ROLLBACK_RESERVE`), and an `InventoryReservationFailed` event is emitted.
- **Saga Compensation**:
  - `PaymentFailed` or `OrderCancelled` events trigger automatic reservation release, returning `reserved_quantity` to `available_quantity`.
  - `OrderConfirmed` events transition reservations to finalized `sold_quantity`.

---

## 2. API Specification

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Liveness probe & service ping. |
| `GET` | `/ready` | Public | Readiness probe (MongoDB ping). |
| `GET` | `/metrics` | Public | Prometheus scrape metrics. |
| `GET` | `/api/v1/inventory/{product_id}` | Public | Real-time stock status for a product. |
| `GET` | `/api/v1/inventory` | Public | Paginated list of all inventory items. |
| `POST` | `/api/v1/inventory` | Admin/Operations | Initialize inventory record for new product. |
| `PATCH`| `/api/v1/inventory/{product_id}` | Admin/Operations | Restock or adjust inventory quantity with audit reason. |

---

## 3. Local Development & Testing

### 3.1 Running Tests
```bash
# Unit tests (models, schemas, atomic contracts, RBAC)
pytest services/inventory-service/tests/test_inventory_service_unit.py -v

# Live API tests (health, stock adjustments, RBAC)
pytest services/inventory-service/tests/test_inventory_service_live.py -v
```

