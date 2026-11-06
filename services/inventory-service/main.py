import os
import uuid
from contextlib import asynccontextmanager

from ecommerce_common.config import BaseServiceSettings
from ecommerce_common.database import DatabaseManager
from ecommerce_common.logging import setup_logger
from ecommerce_common.middleware import register_base_middlewares
from ecommerce_common.outbox_worker import OutboxWorker
from ecommerce_common.rabbitmq import RabbitMQClient
from ecommerce_common.security import (
    TokenUser,
    get_current_user_dependency,
    require_roles,
)
from fastapi import Depends, FastAPI, HTTPException, Query, status
from models import (
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryStockAdjust,
    ReserveStockRequest,
    utc_now,
)
from prometheus_client import make_asgi_app

from contracts.events.types import EventType

logger = setup_logger("inventory-service")


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "inventory-service"
    DATABASE_NAME: str = os.getenv("INVENTORY_DB_NAME", "inventory_db")
    PORT: int = int(os.getenv("INVENTORY_SERVICE_PORT", "8003"))


settings = Settings()
db_manager = DatabaseManager(settings.MONGO_URI, settings.DATABASE_NAME)
rabbitmq_client = RabbitMQClient(
    settings.RABBITMQ_URL, settings.EXCHANGE_NAME, settings.DLX_EXCHANGE_NAME
)
outbox_worker: OutboxWorker | None = None


async def reserve_stock_atomic(order_id: str, items: list, correlation_id: str) -> bool:
    """
    Attempts atomic stock reservation for an order.
    Returns True if fully reserved, False if insufficient stock.
    Rolls back partial reservations on failure.
    """
    reserved_so_far = []
    now = utc_now()

    for item in items:
        p_id = item.get("product_id")
        qty = item.get("quantity")

        result = await db_manager.db.inventory.update_one(
            {"product_id": p_id, "available_quantity": {"$gte": qty}},
            {
                "$inc": {"available_quantity": -qty, "reserved_quantity": qty},
                "$set": {"updated_at": now},
            },
        )

        if result.modified_count > 0:
            reserved_so_far.append((p_id, qty))
            # Log transaction
            await db_manager.db.inventory_txs.insert_one(
                {
                    "tx_id": str(uuid.uuid4()),
                    "order_id": order_id,
                    "product_id": p_id,
                    "type": "RESERVE",
                    "quantity": qty,
                    "created_at": now,
                }
            )
        else:
            # Insufficient stock - rollback previous items
            logger.warning(
                f"Insufficient stock for product {p_id} (needed {qty}). Rolling back."
            )
            for rb_pid, rb_qty in reserved_so_far:
                await db_manager.db.inventory.update_one(
                    {"product_id": rb_pid},
                    {
                        "$inc": {
                            "available_quantity": rb_qty,
                            "reserved_quantity": -rb_qty,
                        },
                        "$set": {"updated_at": now},
                    },
                )
                await db_manager.db.inventory_txs.insert_one(
                    {
                        "tx_id": str(uuid.uuid4()),
                        "order_id": order_id,
                        "product_id": rb_pid,
                        "type": "ROLLBACK_RESERVE",
                        "quantity": rb_qty,
                        "created_at": now,
                    }
                )

            # Emit InventoryReservationFailed event to outbox
            await db_manager.create_outbox_message(
                event_type=EventType.INVENTORY_RESERVATION_FAILED.value,
                aggregate_id=order_id,
                correlation_id=correlation_id,
                producer=settings.SERVICE_NAME,
                payload={
                    "order_id": order_id,
                    "reason": f"Insufficient stock for product {p_id}",
                    "failed_items": items,
                },
            )
            return False

    # Success: Save reservation document
    res_id = str(uuid.uuid4())
    await db_manager.db.inventory_reservations.insert_one(
        {
            "_id": res_id,
            "order_id": order_id,
            "items": items,
            "status": "RESERVED",
            "created_at": now,
        }
    )

    # Emit InventoryReserved event to outbox
    await db_manager.create_outbox_message(
        event_type=EventType.INVENTORY_RESERVED.value,
        aggregate_id=order_id,
        correlation_id=correlation_id,
        producer=settings.SERVICE_NAME,
        payload={
            "order_id": order_id,
            "reservation_id": res_id,
            "reserved_items": items,
        },
    )
    logger.info(f"Successfully reserved inventory for order {order_id}")
    return True


async def release_reservation(order_id: str, reason: str = "PaymentFailed"):
    now = utc_now()
    reservation = await db_manager.db.inventory_reservations.find_one(
        {"order_id": order_id, "status": "RESERVED"}
    )
    if not reservation:
        logger.info(f"No active reservation to release for order {order_id}")
        return

    for item in reservation.get("items", []):
        p_id = item["product_id"]
        qty = item["quantity"]
        await db_manager.db.inventory.update_one(
            {"product_id": p_id},
            {
                "$inc": {"available_quantity": qty, "reserved_quantity": -qty},
                "$set": {"updated_at": now},
            },
        )
        await db_manager.db.inventory_txs.insert_one(
            {
                "tx_id": str(uuid.uuid4()),
                "order_id": order_id,
                "product_id": p_id,
                "type": "RELEASE",
                "quantity": qty,
                "reason": reason,
                "created_at": now,
            }
        )

    await db_manager.db.inventory_reservations.update_one(
        {"_id": reservation["_id"]},
        {"$set": {"status": "RELEASED", "updated_at": now}},
    )
    logger.info(f"Released reservation for order {order_id} (Reason: {reason})")


async def confirm_reservation(order_id: str):
    now = utc_now()
    reservation = await db_manager.db.inventory_reservations.find_one(
        {"order_id": order_id, "status": "RESERVED"}
    )
    if not reservation:
        return

    for item in reservation.get("items", []):
        p_id = item["product_id"]
        qty = item["quantity"]
        # Move from reserved to sold
        await db_manager.db.inventory.update_one(
            {"product_id": p_id},
            {
                "$inc": {"reserved_quantity": -qty, "sold_quantity": qty},
                "$set": {"updated_at": now},
            },
        )
        await db_manager.db.inventory_txs.insert_one(
            {
                "tx_id": str(uuid.uuid4()),
                "order_id": order_id,
                "product_id": p_id,
                "type": "SOLD",
                "quantity": qty,
                "created_at": now,
            }
        )

    await db_manager.db.inventory_reservations.update_one(
        {"_id": reservation["_id"]},
        {"$set": {"status": "CONFIRMED", "updated_at": now}},
    )
    logger.info(f"Inventory reservation confirmed as sold for order {order_id}")


async def handle_order_events(event_data: dict):
    event_type = event_data.get("event_type")
    payload = event_data.get("payload", {})
    correlation_id = event_data.get("correlation_id", "")
    order_id = payload.get("order_id")

    if event_type == EventType.ORDER_CREATED.value:
        logger.info(f"Handling OrderCreated event for order {order_id}")
        items = payload.get("items", [])
        await reserve_stock_atomic(order_id, items, correlation_id)

    elif event_type in [
        EventType.PAYMENT_FAILED.value,
        EventType.ORDER_CANCELLED.value,
    ]:
        logger.info(
            f"Handling {event_type} event: releasing reservation for order {order_id}"
        )
        await release_reservation(order_id, reason=event_type)

    elif event_type == EventType.ORDER_CONFIRMED.value:
        logger.info(
            f"Handling OrderConfirmed event: finalizing sale for order {order_id}"
        )
        await confirm_reservation(order_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global outbox_worker
    await db_manager.connect()

    # Indexes
    await db_manager.db.inventory.create_index("product_id", unique=True)
    await db_manager.db.inventory.create_index("sku")
    await db_manager.db.inventory_reservations.create_index("order_id")
    await db_manager.db.outbox.create_index("status")

    # Seed sample stock if empty
    count = await db_manager.db.inventory.count_documents({})
    if count == 0:
        sample_inventory = [
            {
                "product_id": "prod-101",
                "sku": "HEADPHONE-ANC-01",
                "available_quantity": 50,
                "reserved_quantity": 0,
                "sold_quantity": 0,
                "low_stock_threshold": 5,
                "updated_at": utc_now(),
            },
            {
                "product_id": "prod-102",
                "sku": "KB-MECH-RGB-02",
                "available_quantity": 30,
                "reserved_quantity": 0,
                "sold_quantity": 0,
                "low_stock_threshold": 5,
                "updated_at": utc_now(),
            },
            {
                "product_id": "prod-103",
                "sku": "COFFEE-DRIP-03",
                "available_quantity": 100,
                "reserved_quantity": 0,
                "sold_quantity": 0,
                "low_stock_threshold": 10,
                "updated_at": utc_now(),
            },
            {
                "product_id": "prod-104",
                "sku": "CHAIR-ERGO-04",
                "available_quantity": 15,
                "reserved_quantity": 0,
                "sold_quantity": 0,
                "low_stock_threshold": 3,
                "updated_at": utc_now(),
            },
        ]
        await db_manager.db.inventory.insert_many(sample_inventory)
        logger.info("Seeded initial inventory stock")

    # Connect RabbitMQ and start consumers
    try:
        await rabbitmq_client.connect()
        await rabbitmq_client.register_consumer(
            queue_name="inventory.order-events",
            routing_keys=[
                "order-service.OrderCreated",
                "order-service.OrderCancelled",
                "order-service.OrderConfirmed",
                "payment-service.PaymentFailed",
            ],
            message_handler=handle_order_events,
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
    logger.info("Inventory service shutdown")


app = FastAPI(title="Inventory Service", version="1.0.0", lifespan=lifespan)
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


@app.get("/api/v1/inventory/{product_id}", response_model=InventoryItemResponse)
async def get_inventory(product_id: str):
    doc = await db_manager.db.inventory.find_one({"product_id": product_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    avail = doc.get("available_quantity", 0)
    res = doc.get("reserved_quantity", 0)
    sold = doc.get("sold_quantity", 0)
    return InventoryItemResponse(
        product_id=doc["product_id"],
        sku=doc["sku"],
        available_quantity=avail,
        reserved_quantity=res,
        sold_quantity=sold,
        total_quantity=avail + res + sold,
        low_stock_threshold=doc.get("low_stock_threshold", 5),
        updated_at=doc.get("updated_at", utc_now()),
    )


@app.get("/api/v1/inventory", response_model=list[InventoryItemResponse])
async def list_all_inventory(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    cursor = db_manager.db.inventory.find().skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    res = []
    for doc in items:
        avail = doc.get("available_quantity", 0)
        res_qty = doc.get("reserved_quantity", 0)
        sold = doc.get("sold_quantity", 0)
        res.append(
            InventoryItemResponse(
                product_id=doc["product_id"],
                sku=doc["sku"],
                available_quantity=avail,
                reserved_quantity=res_qty,
                sold_quantity=sold,
                total_quantity=avail + res_qty + sold,
                low_stock_threshold=doc.get("low_stock_threshold", 5),
                updated_at=doc.get("updated_at", utc_now()),
            )
        )
    return res


@app.post(
    "/api/v1/inventory",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(["ADMIN", "OPERATIONS"]))],
)
async def create_inventory(
    item_in: InventoryItemCreate, user: TokenUser = Depends(get_current_user)
):
    existing = await db_manager.db.inventory.find_one(
        {"product_id": item_in.product_id}
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="Inventory already exists for this product"
        )

    now = utc_now()
    doc = {
        "product_id": item_in.product_id,
        "sku": item_in.sku,
        "available_quantity": item_in.available_quantity,
        "reserved_quantity": 0,
        "sold_quantity": 0,
        "low_stock_threshold": item_in.low_stock_threshold,
        "updated_at": now,
    }
    await db_manager.db.inventory.insert_one(doc)
    return InventoryItemResponse(
        product_id=doc["product_id"],
        sku=doc["sku"],
        available_quantity=doc["available_quantity"],
        reserved_quantity=0,
        sold_quantity=0,
        total_quantity=doc["available_quantity"],
        low_stock_threshold=doc["low_stock_threshold"],
        updated_at=now,
    )


@app.patch(
    "/api/v1/inventory/{product_id}",
    response_model=InventoryItemResponse,
    dependencies=[Depends(require_roles(["ADMIN", "OPERATIONS"]))],
)
async def adjust_stock(
    product_id: str,
    adjust_in: InventoryStockAdjust,
    user: TokenUser = Depends(get_current_user),
):
    existing = await db_manager.db.inventory.find_one({"product_id": product_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Inventory record not found")

    new_avail = existing["available_quantity"] + adjust_in.adjustment
    if new_avail < 0:
        raise HTTPException(status_code=400, detail="Cannot reduce stock below 0")

    now = utc_now()
    await db_manager.db.inventory.update_one(
        {"product_id": product_id},
        {
            "$inc": {"available_quantity": adjust_in.adjustment},
            "$set": {"updated_at": now},
        },
    )
    await db_manager.db.inventory_txs.insert_one(
        {
            "tx_id": str(uuid.uuid4()),
            "product_id": product_id,
            "type": "MANUAL_ADJUSTMENT",
            "quantity": adjust_in.adjustment,
            "reason": adjust_in.reason,
            "user_id": user.user_id,
            "created_at": now,
        }
    )

    return await get_inventory(product_id)


@app.post("/api/v1/inventory/reserve")
async def manual_reserve_stock(req: ReserveStockRequest):
    """Internal/test direct reservation endpoint."""
    success = await reserve_stock_atomic(
        order_id=req.order_id,
        items=[item.model_dump() for item in req.items],
        correlation_id=str(uuid.uuid4()),
    )
    if not success:
        raise HTTPException(status_code=400, detail="Insufficient stock")
    return {"status": "reserved", "order_id": req.order_id}
