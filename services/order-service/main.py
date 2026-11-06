import os
import random
import uuid
from contextlib import asynccontextmanager

from ecommerce_common.config import BaseServiceSettings
from ecommerce_common.database import DatabaseManager, serialize_doc
from ecommerce_common.logging import correlation_id_ctx, setup_logger
from ecommerce_common.middleware import register_base_middlewares
from ecommerce_common.outbox_worker import OutboxWorker
from ecommerce_common.rabbitmq import RabbitMQClient
from ecommerce_common.security import (
    TokenUser,
    get_current_user_dependency,
)
from fastapi import Depends, FastAPI, HTTPException, Query, status
from models import (
    CancelOrderRequest,
    OrderCreateRequest,
    OrderItemResponse,
    OrderResponse,
    OrderStatus,
    SagaState,
    utc_now,
)
from prometheus_client import make_asgi_app

from contracts.events.types import EventType

logger = setup_logger("order-service")


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "order-service"
    DATABASE_NAME: str = os.getenv("ORDER_DB_NAME", "order_db")
    PORT: int = int(os.getenv("ORDER_SERVICE_PORT", "8005"))


settings = Settings()
db_manager = DatabaseManager(settings.MONGO_URI, settings.DATABASE_NAME)
rabbitmq_client = RabbitMQClient(
    settings.RABBITMQ_URL, settings.EXCHANGE_NAME, settings.DLX_EXCHANGE_NAME
)
outbox_worker: OutboxWorker | None = None


async def advance_saga(
    order_id: str,
    new_state: str,
    details: dict,
    correlation_id: str,
):
    now = utc_now()
    await db_manager.db.saga_instances.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "current_state": new_state,
                "updated_at": now,
            },
            "$push": {
                "history": {
                    "state": new_state,
                    "details": details,
                    "timestamp": now,
                }
            },
        },
        upsert=True,
    )
    logger.info(f"Saga for order {order_id} advanced to {new_state}")


async def handle_saga_events(event_data: dict):
    event_type = event_data.get("event_type")
    payload = event_data.get("payload", {})
    correlation_id = event_data.get("correlation_id", "")
    order_id = payload.get("order_id")

    if not order_id:
        return

    order = await db_manager.db.orders.find_one({"_id": order_id})
    if not order:
        logger.warning(f"Received event {event_type} for unknown order {order_id}")
        return

    now = utc_now()

    if event_type == EventType.INVENTORY_RESERVED.value:
        logger.info(
            f"Saga: Inventory reserved for order {order_id}. Initiating payment."
        )
        await advance_saga(
            order_id, SagaState.INVENTORY_RESERVED.value, payload, correlation_id
        )
        await db_manager.db.orders.update_one(
            {"_id": order_id},
            {"$set": {"status": OrderStatus.AWAITING_PAYMENT.value, "updated_at": now}},
        )

        # Trigger payment via outbox
        payment_id = f"pay-{uuid.uuid4().hex[:10]}"
        await db_manager.create_outbox_message(
            event_type=EventType.PAYMENT_INITIATED.value,
            aggregate_id=payment_id,
            correlation_id=correlation_id,
            producer=settings.SERVICE_NAME,
            payload={
                "payment_id": payment_id,
                "order_id": order_id,
                "customer_id": order["customer_id"],
                "customer_email": order["customer_email"],
                "amount": order["total_amount"],
                "currency": "USD",
                "payment_method": order.get("payment_method", "sandbox_credit_card"),
            },
        )

    elif event_type == EventType.INVENTORY_RESERVATION_FAILED.value:
        logger.warning(
            f"Saga: Inventory reservation failed for order {order_id}. Cancelling order."
        )
        await advance_saga(order_id, SagaState.FAILED.value, payload, correlation_id)
        await db_manager.db.orders.update_one(
            {"_id": order_id},
            {
                "$set": {
                    "status": OrderStatus.CANCELLED.value,
                    "cancellation_reason": payload.get("reason", "OUT_OF_STOCK"),
                    "updated_at": now,
                }
            },
        )
        # Notify customer about out-of-stock cancellation
        await db_manager.create_outbox_message(
            event_type=EventType.ORDER_CANCELLED.value,
            aggregate_id=order_id,
            correlation_id=correlation_id,
            producer=settings.SERVICE_NAME,
            payload={
                "order_id": order_id,
                "customer_id": order["customer_id"],
                "customer_email": order["customer_email"],
                "reason": payload.get("reason", "Out of stock"),
                "refund_required": False,
                "inventory_release_required": False,
                "items": order["items"],
            },
        )

    elif event_type == EventType.PAYMENT_SUCCEEDED.value:
        logger.info(f"Saga: Payment succeeded for order {order_id}. Confirming order.")
        await advance_saga(order_id, SagaState.COMPLETED.value, payload, correlation_id)
        await db_manager.db.orders.update_one(
            {"_id": order_id},
            {
                "$set": {
                    "status": OrderStatus.CONFIRMED.value,
                    "payment_id": payload.get("payment_id"),
                    "updated_at": now,
                }
            },
        )
        # Publish OrderConfirmed (triggers shipment and notification)
        await db_manager.create_outbox_message(
            event_type=EventType.ORDER_CONFIRMED.value,
            aggregate_id=order_id,
            correlation_id=correlation_id,
            producer=settings.SERVICE_NAME,
            payload={
                "order_id": order_id,
                "order_number": order["order_number"],
                "customer_id": order["customer_id"],
                "customer_email": order["customer_email"],
                "total_amount": order["total_amount"],
                "shipping_address": order["shipping_address"],
                "items": order["items"],
            },
        )

    elif event_type == EventType.PAYMENT_FAILED.value:
        logger.warning(
            f"Saga: Payment failed for order {order_id}. Executing compensation."
        )
        await advance_saga(
            order_id, SagaState.COMPENSATING.value, payload, correlation_id
        )
        await db_manager.db.orders.update_one(
            {"_id": order_id},
            {
                "$set": {
                    "status": OrderStatus.CANCELLED.value,
                    "cancellation_reason": f"Payment Failed: {payload.get('reason', 'Card declined')}",
                    "updated_at": now,
                }
            },
        )
        # Compensating transaction: release inventory and notify customer
        await db_manager.create_outbox_message(
            event_type=EventType.ORDER_CANCELLED.value,
            aggregate_id=order_id,
            correlation_id=correlation_id,
            producer=settings.SERVICE_NAME,
            payload={
                "order_id": order_id,
                "customer_id": order["customer_id"],
                "customer_email": order["customer_email"],
                "reason": f"Payment failed: {payload.get('reason', 'Card declined')}",
                "refund_required": False,
                "inventory_release_required": True,
                "items": order["items"],
            },
        )

    elif event_type == EventType.SHIPMENT_CREATED.value:
        tracking_num = payload.get("tracking_number")
        logger.info(
            f"Saga: Shipment created for order {order_id} (Tracking: {tracking_num})"
        )
        await db_manager.db.orders.update_one(
            {"_id": order_id},
            {
                "$set": {
                    "status": OrderStatus.SHIPPED.value,
                    "tracking_number": tracking_num,
                    "updated_at": now,
                }
            },
        )

    elif event_type == EventType.SHIPMENT_STATUS_UPDATED.value:
        new_status = payload.get("new_status")
        if new_status == "DELIVERED":
            logger.info(f"Saga: Order {order_id} marked as DELIVERED")
            await db_manager.db.orders.update_one(
                {"_id": order_id},
                {"$set": {"status": OrderStatus.DELIVERED.value, "updated_at": now}},
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global outbox_worker
    await db_manager.connect()

    # Indexes
    await db_manager.db.orders.create_index("order_number", unique=True)
    await db_manager.db.orders.create_index("customer_id")
    await db_manager.db.orders.create_index("status")
    await db_manager.db.saga_instances.create_index("order_id", unique=True)
    await db_manager.db.outbox.create_index("status")

    try:
        await rabbitmq_client.connect()
        await rabbitmq_client.register_consumer(
            queue_name="order.saga-events",
            routing_keys=[
                "inventory-service.InventoryReserved",
                "inventory-service.InventoryReservationFailed",
                "payment-service.PaymentSucceeded",
                "payment-service.PaymentFailed",
                "shipping-service.ShipmentCreated",
                "shipping-service.ShipmentStatusUpdated",
            ],
            message_handler=handle_saga_events,
        )

        outbox_worker = OutboxWorker(db_manager, rabbitmq_client)
        outbox_worker.start()
    except Exception as e:
        logger.warning(f"RabbitMQ connection postponed during startup: {e}")

    yield
    if outbox_worker:
        await outbox_worker.stop()
    await rabbitmq_client.close()
    await db_manager.disconnect()
    logger.info("Order service shutdown")


app = FastAPI(title="Order Service", version="1.0.0", lifespan=lifespan)
register_base_middlewares(app)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

get_current_user = get_current_user_dependency(
    secret_key=settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/ready")
async def ready():
    try:
        await db_manager.db.command("ping")
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unready: {e}")


def serialize_order(doc: dict) -> OrderResponse:
    item_responses = [
        OrderItemResponse(
            product_id=it["product_id"],
            product_name=it["product_name"],
            unit_price=it["unit_price"],
            quantity=it["quantity"],
            subtotal=it["unit_price"] * it["quantity"],
        )
        for it in doc.get("items", [])
    ]
    return OrderResponse(
        id=str(doc["_id"]),
        order_number=doc["order_number"],
        customer_id=doc["customer_id"],
        customer_email=doc["customer_email"],
        items=item_responses,
        total_amount=doc["total_amount"],
        status=doc["status"],
        shipping_address=doc["shipping_address"],
        payment_id=doc.get("payment_id"),
        tracking_number=doc.get("tracking_number"),
        cancellation_reason=doc.get("cancellation_reason"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@app.post(
    "/api/v1/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED
)
async def create_order(
    request: OrderCreateRequest,
    user: TokenUser = Depends(get_current_user),
):
    corr_id = correlation_id_ctx.get()
    order_id = f"ord-{uuid.uuid4().hex[:12]}"
    order_number = f"ORD-{random.randint(100000, 999999)}"
    now = utc_now()

    total_amount = sum(it.unit_price * it.quantity for it in request.items)
    items_dict = [it.model_dump() for it in request.items]

    order_doc = {
        "_id": order_id,
        "order_number": order_number,
        "customer_id": user.user_id,
        "customer_email": user.email,
        "items": items_dict,
        "total_amount": total_amount,
        "status": OrderStatus.PENDING.value,
        "shipping_address": request.shipping_address.model_dump(),
        "payment_method": request.payment_method,
        "created_at": now,
        "updated_at": now,
    }

    # Initialize Saga Instance
    saga_doc = {
        "order_id": order_id,
        "order_number": order_number,
        "customer_id": user.user_id,
        "current_state": SagaState.STARTED.value,
        "history": [
            {
                "state": SagaState.STARTED.value,
                "details": {
                    "message": "Order created, beginning inventory reservation"
                },
                "timestamp": now,
            }
        ],
        "created_at": now,
        "updated_at": now,
    }

    await db_manager.db.orders.insert_one(order_doc)
    await db_manager.db.saga_instances.insert_one(saga_doc)

    # Place OrderCreated in Outbox
    await db_manager.create_outbox_message(
        event_type=EventType.ORDER_CREATED.value,
        aggregate_id=order_id,
        correlation_id=corr_id,
        producer=settings.SERVICE_NAME,
        payload={
            "order_id": order_id,
            "order_number": order_number,
            "customer_id": user.user_id,
            "customer_email": user.email,
            "items": items_dict,
            "total_amount": total_amount,
            "currency": "USD",
            "shipping_address": request.shipping_address.model_dump(),
        },
    )

    logger.info(f"Order {order_id} ({order_number}) created. Saga started.")
    return serialize_order(order_doc)


@app.get("/api/v1/orders", response_model=list[OrderResponse])
async def list_orders(
    user: TokenUser = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    query = {}
    if user.role not in ["ADMIN", "OPERATIONS"]:
        query["customer_id"] = user.user_id

    cursor = (
        db_manager.db.orders.find(query).sort("created_at", -1).skip(skip).limit(limit)
    )
    orders = await cursor.to_list(length=limit)
    return [serialize_order(o) for o in orders]


@app.get("/api/v1/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    user: TokenUser = Depends(get_current_user),
):
    query = {"_id": order_id}
    if user.role not in ["ADMIN", "OPERATIONS"]:
        query["customer_id"] = user.user_id

    doc = await db_manager.db.orders.find_one(query)
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found")
    return serialize_order(doc)


@app.get("/api/v1/orders/{order_id}/saga")
async def get_order_saga(
    order_id: str,
    user: TokenUser = Depends(get_current_user),
):
    query = {"_id": order_id}
    if user.role not in ["ADMIN", "OPERATIONS"]:
        query["customer_id"] = user.user_id

    order = await db_manager.db.orders.find_one(query)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    saga = await db_manager.db.saga_instances.find_one({"order_id": order_id})
    if not saga:
        raise HTTPException(status_code=404, detail="Saga instance not found")
    return serialize_doc(saga)


@app.post("/api/v1/orders/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    request: CancelOrderRequest,
    user: TokenUser = Depends(get_current_user),
):
    query = {"_id": order_id}
    if user.role not in ["ADMIN", "OPERATIONS"]:
        query["customer_id"] = user.user_id

    order = await db_manager.db.orders.find_one(query)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order["status"] == OrderStatus.DELIVERED.value:
        raise HTTPException(
            status_code=400,
            detail="Delivered orders cannot be cancelled directly. Please initiate a return.",
        )
    if order["status"] == OrderStatus.CANCELLED.value:
        raise HTTPException(status_code=400, detail="Order is already cancelled")

    now = utc_now()
    corr_id = correlation_id_ctx.get()

    needs_refund = order["status"] in [
        OrderStatus.CONFIRMED.value,
        OrderStatus.SHIPPED.value,
    ]
    release_inventory = True

    await db_manager.db.orders.update_one(
        {"_id": order_id},
        {
            "$set": {
                "status": OrderStatus.CANCELLED.value,
                "cancellation_reason": request.reason,
                "updated_at": now,
            }
        },
    )

    # If already paid, trigger refund via Outbox
    if needs_refund and order.get("payment_id"):
        refund_id = f"ref-{uuid.uuid4().hex[:10]}"
        await db_manager.create_outbox_message(
            event_type=EventType.REFUND_INITIATED.value,
            aggregate_id=refund_id,
            correlation_id=corr_id,
            producer=settings.SERVICE_NAME,
            payload={
                "refund_id": refund_id,
                "payment_id": order["payment_id"],
                "order_id": order_id,
                "amount": order["total_amount"],
                "reason": request.reason,
            },
        )

    # Publish OrderCancelled
    await db_manager.create_outbox_message(
        event_type=EventType.ORDER_CANCELLED.value,
        aggregate_id=order_id,
        correlation_id=corr_id,
        producer=settings.SERVICE_NAME,
        payload={
            "order_id": order_id,
            "customer_id": order["customer_id"],
            "customer_email": order["customer_email"],
            "reason": request.reason,
            "refund_required": needs_refund,
            "inventory_release_required": release_inventory,
            "items": order["items"],
        },
    )

    logger.info(f"Order {order_id} cancelled by user {user.user_id}")
    updated_order = await db_manager.db.orders.find_one({"_id": order_id})
    return serialize_order(updated_order)
