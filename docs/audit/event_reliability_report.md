# Engineering Audit: RabbitMQ & Event Reliability Report

**Auditor**: Distributed Systems & Message Broker Engineer  
**Message Broker**: RabbitMQ 3.13 (Management UI on `:15673`, AMQP on `:5673`)  

---

## 1. Exchange & Queue Topology Verification

```
[Main Topic Exchange: ecommerce.events]
  ├── routing_key: order-service.OrderCreated ────────► [inventory.order-events]
  ├── routing_key: order-service.OrderConfirmed ──────► [shipping.order-confirmed]
  │                                           └──────► [notification.all-events]
  ├── routing_key: order-service.OrderCancelled ──────► [inventory.order-events]
  │                                           └──────► [notification.all-events]
  ├── routing_key: inventory-service.InventoryReserved ──► [order.saga-events]
  ├── routing_key: inventory-service.InventoryReservationFailed ──► [order.saga-events]
  ├── routing_key: order-service.PaymentInitiated ────► [payment.events]
  ├── routing_key: payment-service.PaymentSucceeded ──► [order.saga-events]
  ├── routing_key: payment-service.PaymentFailed ─────► [order.saga-events]
  │                                           ├──────► [inventory.order-events]
  │                                           └──────► [notification.all-events]
  └── routing_key: shipping-service.Shipment* ────────► [order.saga-events]
                                              └──────► [notification.all-events]

[Dead Letter Exchange: ecommerce.dlx]
  ├── Bound to: *.dlq queues for poison pill isolation and manual inspection
```

---

## 2. Event Reliability Guarantees

| Requirement | Implementation Mechanism | Verification Result |
| :--- | :--- | :--- |
| **Durable Queues & Exchanges** | Declared with `durable=True` | **VERIFIED** via `rabbitmqctl list_queues` |
| **Persistent Messages** | `delivery_mode = DeliveryMode.PERSISTENT` | **VERIFIED** in `RabbitMQClient.publish_event` |
| **Manual Acknowledgment** | Explicit `await message.ack()` on success; reject without requeue to route to DLX on fatal error | **VERIFIED** in consumer loops |
| **Transactional Outbox** | Two-phase dispatch: database aggregate write + `db.outbox` insert in same MongoDB database, published via background OutboxWorker | **VERIFIED** in all event producers |
| **Correlation ID Tracking** | `X-Correlation-ID` injected into message properties and headers | **VERIFIED** across event logs |
| **Dead-Letter Queues (DLQ)** | Each queue has a corresponding `.dlq` configured via `x-dead-letter-exchange` | **VERIFIED** in topology |

