import os
import random
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Query, status
from prometheus_client import make_asgi_app

from ecommerce_common.config import BaseServiceSettings
from ecommerce_common.logging import setup_logger, correlation_id_ctx
from ecommerce_common.middleware import register_base_middlewares
from ecommerce_common.security import (
    get_current_user_dependency,
    TokenUser,
    require_roles,
)
from ecommerce_common.database import serialize_doc, DatabaseManager
from ecommerce_common.rabbitmq import RabbitMQClient
from ecommerce_common.outbox_worker import OutboxWorker
from contracts.events.types import EventType
from models import (
    ShipmentStatusUpdateRequest,
    ShipmentResponse,
    TrackingEventResponse,
    ShipmentStatus,
    utc_now,
)

logger = setup_logger("shipping-service")


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "shipping-service"
    DATABASE_NAME: str = os.getenv("SHIPPING_DB_NAME", "shipping_db")
    PORT: int = int(os.getenv("SHIPPING_SERVICE_PORT", "8007"))


settings = Settings()
db_manager = DatabaseManager(settings.MONGO_URI, settings.DATABASE_NAME)
rabbitmq_client = RabbitMQClient(settings.RABBITMQ_URL, settings.EXCHANGE_NAME, settings.DLX_EXCHANGE_NAME)
outbox_worker: Optional[OutboxWorker] = None


async def create_shipment_for_order(payload: dict, correlation_id: str):
    order_id = payload.get("order_id")
    customer_email = payload.get("customer_email")
    shipping_address = payload.get("shipping_address", {})

    existing = await db_manager.db.shipments.find_one({"order_id": order_id})
    if existing:
        logger.info(f"Shipment already exists for order {order_id}")
        return

    now = utc_now()
    shipment_id = f"shp-{uuid.uuid4().hex[:10]}"
    tracking_number = f"TRK-{random.choice(['USPS', 'FEDEX', 'UPS'])}-{random.randint(10000000, 99999999)}"
    estimated_delivery = now + timedelta(days=3)

    initial_event = {
        "status": ShipmentStatus.CREATED.value,
        "location": "Central Fulfillment Center",
        "description": "Shipping label created. Package awaiting carrier pickup.",
        "timestamp": now,
    }

    shipment_doc = {
        "_id": shipment_id,
        "order_id": order_id,
        "tracking_number": tracking_number,
        "carrier": "Standard Express",
        "status": ShipmentStatus.CREATED.value,
        "estimated_delivery": estimated_delivery,
        "shipping_address": shipping_address,
        "recipient_email": customer_email,
        "events": [initial_event],
        "created_at": now,
        "updated_at": now,
    }
    await db_manager.db.shipments.insert_one(shipment_doc)

    # Publish ShipmentCreated via Outbox
    await db_manager.create_outbox_message(
        event_type=EventType.SHIPMENT_CREATED.value,
        aggregate_id=shipment_id,
        correlation_id=correlation_id,
        producer=settings.SERVICE_NAME,
        payload={
            "shipment_id": shipment_id,
            "order_id": order_id,
            "tracking_number": tracking_number,
            "carrier": "Standard Express",
            "estimated_delivery": estimated_delivery.isoformat(),
            "recipient_email": customer_email or "customer@example.com",
            "recipient_name": "Valued Customer",
            "shipping_address": shipping_address,
        },
    )
    logger.info(f"Shipment {shipment_id} created for order {order_id} (Tracking: {tracking_number})")


async def handle_shipping_events(event_data: dict):
    event_type = event_data.get("event_type")
    payload = event_data.get("payload", {})
    correlation_id = event_data.get("correlation_id", "")

    if event_type == EventType.ORDER_CONFIRMED.value:
        logger.info(f"Handling OrderConfirmed in shipping-service for order {payload.get('order_id')}")
        await create_shipment_for_order(payload, correlation_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global outbox_worker
    await db_manager.connect()

    # Indexes
    await db_manager.db.shipments.create_index("order_id", unique=True)
    await db_manager.db.shipments.create_index("tracking_number", unique=True)
    await db_manager.db.outbox.create_index("status")

    try:
        await rabbitmq_client.connect()
        await rabbitmq_client.register_consumer(
            queue_name="shipping.order-confirmed",
            routing_keys=["order-service.OrderConfirmed"],
            message_handler=handle_shipping_events,
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
    logger.info("Shipping service shutdown")


app = FastAPI(title="Shipping Service", version="1.0.0", lifespan=lifespan)
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


def serialize_shipment(doc: dict) -> ShipmentResponse:
    events = [
        TrackingEventResponse(
            status=ev["status"],
            location=ev["location"],
            description=ev["description"],
            timestamp=ev["timestamp"],
        )
        for ev in doc.get("events", [])
    ]
    return ShipmentResponse(
        id=str(doc["_id"]),
        order_id=doc["order_id"],
        tracking_number=doc["tracking_number"],
        carrier=doc["carrier"],
        status=ShipmentStatus(doc["status"]),
        estimated_delivery=doc["estimated_delivery"],
        shipping_address=doc["shipping_address"],
        events=events,
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@app.get("/api/v1/shipments/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(shipment_id: str):
    doc = await db_manager.db.shipments.find_one({"_id": shipment_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return serialize_shipment(doc)


@app.get("/api/v1/orders/{order_id}/tracking", response_model=ShipmentResponse)
async def get_order_tracking(order_id: str):
    doc = await db_manager.db.shipments.find_one({"order_id": order_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Shipment tracking not found for this order")
    return serialize_shipment(doc)


@app.get("/api/v1/shipments", response_model=List[ShipmentResponse], dependencies=[Depends(require_roles(["ADMIN", "OPERATIONS"]))])
async def list_shipments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    cursor = db_manager.db.shipments.find().sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    return [serialize_shipment(doc) for doc in items]


@app.patch(
    "/api/v1/shipments/{shipment_id}/status",
    response_model=ShipmentResponse,
    dependencies=[Depends(require_roles(["ADMIN", "OPERATIONS"]))],
)
async def update_shipment_status(
    shipment_id: str,
    update_in: ShipmentStatusUpdateRequest,
    user: TokenUser = Depends(get_current_user),
):
    doc = await db_manager.db.shipments.find_one({"_id": shipment_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Shipment not found")

    now = utc_now()
    corr_id = correlation_id_ctx.get()
    old_status = doc["status"]

    new_event = {
        "status": update_in.status.value,
        "location": update_in.location,
        "description": update_in.notes or f"Package status updated to {update_in.status.value}",
        "timestamp": now,
    }

    await db_manager.db.shipments.update_one(
        {"_id": shipment_id},
        {
            "$set": {
                "status": update_in.status.value,
                "updated_at": now,
            },
            "$push": {"events": new_event},
        },
    )

    # Publish ShipmentStatusUpdated event via Outbox
    await db_manager.create_outbox_message(
        event_type=EventType.SHIPMENT_STATUS_UPDATED.value,
        aggregate_id=shipment_id,
        correlation_id=corr_id,
        producer=settings.SERVICE_NAME,
        payload={
            "shipment_id": shipment_id,
            "order_id": doc["order_id"],
            "tracking_number": doc["tracking_number"],
            "old_status": old_status,
            "new_status": update_in.status.value,
            "location": update_in.location,
            "notes": update_in.notes,
        },
    )

    updated_doc = await db_manager.db.shipments.find_one({"_id": shipment_id})
    return serialize_shipment(updated_doc)

