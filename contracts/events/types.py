from enum import Enum


class EventType(str, Enum):
    ORDER_CREATED = "OrderCreated"
    INVENTORY_RESERVED = "InventoryReserved"
    INVENTORY_RESERVATION_FAILED = "InventoryReservationFailed"
    PAYMENT_INITIATED = "PaymentInitiated"
    PAYMENT_SUCCEEDED = "PaymentSucceeded"
    PAYMENT_FAILED = "PaymentFailed"
    ORDER_CONFIRMED = "OrderConfirmed"
    SHIPMENT_CREATED = "ShipmentCreated"
    SHIPMENT_STATUS_UPDATED = "ShipmentStatusUpdated"
    NOTIFICATION_REQUESTED = "NotificationRequested"
    ORDER_CANCELLED = "OrderCancelled"
    REFUND_INITIATED = "RefundInitiated"
    REFUND_SUCCEEDED = "RefundSucceeded"
    REFUND_FAILED = "RefundFailed"
