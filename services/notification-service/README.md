# Notification Service — Independent Microservice Engineering Guide

**Service Name**: `notification-service`  
**Container Port**: `8008`  
**Default Database**: `notification_db` (MongoDB)  
**Message Broker**: RabbitMQ (`ecommerce.events` topic exchange)  
**Primary Responsibilities**: Transactional email dispatch, template rendering (`order_confirmed`, `shipment_created`, `shipment_status_updated`, `order_cancelled`, `payment_failed`), retry logic, and simulated/SMTP delivery.

---

## 1. Architecture & Resilient Delivery

- **Owned Collections**:
  - `notifications`: History of all rendered and dispatched notifications (`_id`, `recipient_email`, `subject`, `template_name`, `status: SENT|RETRYING|FAILED`, `attempt_count`, `content`, `error`, `created_at`, `sent_at`).
- **Asynchronous Event Handlers**:
  - Consumes order and shipment events via dedicated durable RabbitMQ queue `notifications.all-events`.
  - Automatically triggers template rendering and background email sending for:
    - `OrderConfirmed` -> Order confirmation receipt
    - `ShipmentCreated` -> Shipment tracking announcement
    - `ShipmentStatusUpdated` -> Real-time transit updates
    - `PaymentFailed` -> Payment recovery prompt
    - `OrderCancelled` -> Cancellation notice & refund information
- **Graceful Fallback**:
  - In local and test environments where an external SMTP server is not reachable, the service transparently logs and records a simulated dispatch without crashing or dropping events.

---

## 2. API Specification

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Liveness probe & service ping. |
| `GET` | `/ready` | Public | Readiness probe (MongoDB ping). |
| `GET` | `/metrics` | Public | Prometheus scrape metrics. |
| `POST` | `/api/v1/notifications/send` | Admin/Operations | Trigger immediate notification dispatch. |
| `GET` | `/api/v1/notifications` | Admin/Operations | Paginated audit log of dispatched notifications. |

---

## 3. Local Development & Testing

```bash
# Unit tests
pytest services/notification-service/tests/test_notification_service_unit.py -v

# Live API tests
pytest services/notification-service/tests/test_notification_service_live.py -v
```

