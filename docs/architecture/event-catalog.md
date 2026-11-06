# Domain Event Catalog

All asynchronous events flow across the durable RabbitMQ topic exchange `ecommerce.events`. Dead-letter exchange is configured as `ecommerce.dlx`.

## 1. Standard CloudEvent Envelope Structure
```json
{
  "event_id": "uuid-v4",
  "event_type": "EventType",
  "event_version": 1,
  "aggregate_id": "agg-id",
  "correlation_id": "corr-uuid-v4",
  "occurred_at": "2026-11-06T15:00:00Z",
  "producer": "service-name",
  "payload": {}
}
```

## 2. Event Registry

| Event Type | Producer | Routing Key | Consumers | Purpose |
|---|---|---|---|---|
| `OrderCreated` | `order-service` | `order-service.OrderCreated` | `inventory-service`, `notification-service` | Triggers atomic stock reservation |
| `InventoryReserved` | `inventory-service` | `inventory-service.InventoryReserved` | `order-service` | Saga: Advances order to `AWAITING_PAYMENT`, triggers `PaymentInitiated` |
| `InventoryReservationFailed` | `inventory-service` | `inventory-service.InventoryReservationFailed` | `order-service` | Saga: Fails reservation, cancels order with `OUT_OF_STOCK` |
| `PaymentInitiated` | `order-service` | `order-service.PaymentInitiated` | `payment-service` | Commands payment processing with idempotency key |
| `PaymentSucceeded` | `payment-service` | `payment-service.PaymentSucceeded` | `order-service`, `notification-service` | Saga: Confirms order, advances to `CONFIRMED` |
| `PaymentFailed` | `payment-service` | `payment-service.PaymentFailed` | `order-service`, `inventory-service`, `notification-service` | Saga: Triggers compensation (releases stock, cancels order) |
| `OrderConfirmed` | `order-service` | `order-service.OrderConfirmed` | `shipping-service`, `notification-service` | Triggers shipment creation and confirmation email |
| `OrderCancelled` | `order-service` | `order-service.OrderCancelled` | `inventory-service`, `notification-service` | Triggers stock release and cancellation email |
| `ShipmentCreated` | `shipping-service` | `shipping-service.ShipmentCreated` | `order-service`, `notification-service` | Saga: Updates order status to `SHIPPED` |
| `ProductCreated` | `product-service` | `product-service.ProductCreated` | `notification-service` | Notifies catalog updates |
| `ProductUpdated` | `product-service` | `product-service.ProductUpdated` | `notification-service` | Notifies catalog updates |
| `ProductDeleted` | `product-service` | `product-service.ProductDeleted` | `notification-service` | Notifies catalog updates |
