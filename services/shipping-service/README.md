# Shipping Service — Independent Microservice Engineering Guide

**Service Name**: `shipping-service`  
**Container Port**: `8007`  
**Default Database**: `shipping_db` (MongoDB)  
**Message Broker**: RabbitMQ (`ecommerce.events` topic exchange)  
**Primary Responsibilities**: Package shipment creation upon order confirmation, synthetic carrier tracking number generation, transit checkpoint logging, real-time tracking lookup, and status update events.

---

## 1. Architecture & Domain Isolation

- **Owned Collections**:
  - `shipments`: Shipment records (`_id`, `order_id` unique indexed, `tracking_number` indexed, `carrier`, `status: CREATED|PICKED_UP|IN_TRANSIT|OUT_FOR_DELIVERY|DELIVERED|RETURNED`, `estimated_delivery`, `shipping_address`, `recipient_email`, `events: [{status, location, description, timestamp}]`, `created_at`, `updated_at`).
  - `outbox`: Transactional outbox records for RabbitMQ publishing.
- **Event-Driven Fulfillment**:
  - Consumes `order-service.OrderConfirmed` events from RabbitMQ queue `shipping.order-confirmed`.
  - Automatically provisions a shipment record, generates tracking number (e.g., `TRK-FEDEX-87654321`), writes initial checkpoint event, and publishes `ShipmentCreated` via the outbox worker.
- **Lifecycle Tracking Updates**:
  - Admin/Operations roles can update status via `PATCH /api/v1/shipments/{shipment_id}/status`.
  - Emits `ShipmentStatusUpdated` to notify customers asynchronously via Notification Service.

---

## 2. API Specification

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Liveness probe & service ping. |
| `GET` | `/ready` | Public | Readiness probe (MongoDB ping). |
| `GET` | `/metrics` | Public | Prometheus scrape metrics. |
| `GET` | `/api/v1/shipments/{shipment_id}` | Bearer Token | Retrieve single shipment by shipment ID. |
| `GET` | `/api/v1/orders/{order_id}/tracking`| Bearer Token | Customer tracking history lookup by order ID. |
| `GET` | `/api/v1/shipments` | Admin/Operations | Paginated shipment directory. |
| `PATCH`| `/api/v1/shipments/{shipment_id}/status` | Admin/Operations | Append tracking checkpoint & advance status. |

---

## 3. Local Development & Testing

```bash
# Unit tests
pytest services/shipping-service/tests/test_shipping_service_unit.py -v

# Live API tests
pytest services/shipping-service/tests/test_shipping_service_live.py -v
```

