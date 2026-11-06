import os
import uuid
from contextlib import asynccontextmanager

from ecommerce_common.config import BaseServiceSettings
from ecommerce_common.database import DatabaseManager
from ecommerce_common.logging import correlation_id_ctx, setup_logger
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
    PaymentCreateRequest,
    PaymentResponse,
    PaymentStatus,
    RefundRequest,
    RefundResponse,
    utc_now,
)
from prometheus_client import make_asgi_app
from pymongo.errors import DuplicateKeyError

from contracts.events.types import EventType

logger = setup_logger("payment-service")


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "payment-service"
    DATABASE_NAME: str = os.getenv("PAYMENT_DB_NAME", "payment_db")
    PORT: int = int(os.getenv("PAYMENT_SERVICE_PORT", "8006"))


settings = Settings()
db_manager = DatabaseManager(settings.MONGO_URI, settings.DATABASE_NAME)
rabbitmq_client = RabbitMQClient(
    settings.RABBITMQ_URL, settings.EXCHANGE_NAME, settings.DLX_EXCHANGE_NAME
)
outbox_worker: OutboxWorker | None = None


async def execute_payment(
    order_id: str,
    amount: int,
    currency: str,
    idempotency_key: str,
    correlation_id: str,
    card_last_four: str = "4242",
    simulate_failure: bool = False,
) -> dict:
    """
    Executes payment against the sandbox gateway with idempotency check.
    """
    now = utc_now()
    existing_key = await db_manager.db.idempotency_keys.find_one(
        {"_id": idempotency_key}
    )
    if existing_key:
        logger.info(f"Idempotent payment replay detected for key {idempotency_key}")
        payment_doc = await db_manager.db.payments.find_one(
            {"_id": existing_key["payment_id"]}
        )
        return payment_doc

    payment_id = f"pay-{uuid.uuid4().hex[:10]}"
    try:
        await db_manager.db.idempotency_keys.insert_one(
            {
                "_id": idempotency_key,
                "payment_id": payment_id,
                "created_at": now,
            }
        )
    except DuplicateKeyError:
        existing_key = await db_manager.db.idempotency_keys.find_one(
            {"_id": idempotency_key}
        )
        payment_doc = await db_manager.db.payments.find_one(
            {"_id": existing_key["payment_id"]}
        )
        return payment_doc

    if simulate_failure or card_last_four == "0002":
        # Simulate payment failure
        payment_doc = {
            "_id": payment_id,
            "order_id": order_id,
            "amount": amount,
            "currency": currency,
            "status": PaymentStatus.FAILED.value,
            "card_last_four": card_last_four,
            "failure_reason": "Card declined: insufficient funds (Sandbox simulation)",
            "idempotency_key": idempotency_key,
            "created_at": now,
            "updated_at": now,
        }
        await db_manager.db.payments.insert_one(payment_doc)

        # Outbox: PaymentFailed
        await db_manager.create_outbox_message(
            event_type=EventType.PAYMENT_FAILED.value,
            aggregate_id=payment_id,
            correlation_id=correlation_id,
            producer=settings.SERVICE_NAME,
            payload={
                "payment_id": payment_id,
                "order_id": order_id,
                "reason": payment_doc["failure_reason"],
                "gateway": "sandbox",
            },
        )
        logger.warning(f"Payment {payment_id} declined for order {order_id}")
    else:
        # Simulate payment success
        tx_id = f"tx_sbx_{uuid.uuid4().hex[:16]}"
        payment_doc = {
            "_id": payment_id,
            "order_id": order_id,
            "amount": amount,
            "currency": currency,
            "status": PaymentStatus.SUCCEEDED.value,
            "transaction_id": tx_id,
            "card_last_four": card_last_four,
            "idempotency_key": idempotency_key,
            "created_at": now,
            "updated_at": now,
        }
        await db_manager.db.payments.insert_one(payment_doc)

        # Outbox: PaymentSucceeded
        await db_manager.create_outbox_message(
            event_type=EventType.PAYMENT_SUCCEEDED.value,
            aggregate_id=payment_id,
            correlation_id=correlation_id,
            producer=settings.SERVICE_NAME,
            payload={
                "payment_id": payment_id,
                "order_id": order_id,
                "transaction_id": tx_id,
                "amount": amount,
                "gateway": "sandbox",
            },
        )
        logger.info(
            f"Payment {payment_id} succeeded for order {order_id} (TX: {tx_id})"
        )

    return payment_doc


async def handle_payment_events(event_data: dict):
    event_type = event_data.get("event_type")
    payload = event_data.get("payload", {})
    correlation_id = event_data.get("correlation_id", "")

    if event_type == EventType.PAYMENT_INITIATED.value:
        order_id = payload.get("order_id")
        amount = payload.get("amount")
        currency = payload.get("currency", "USD")
        payment_method = payload.get("payment_method", "sandbox_credit_card")
        simulate_failure = payment_method == "card_simulate_decline"
        idempotency_key = f"idem-order-{order_id}"

        logger.info(
            f"Auto-processing PaymentInitiated event for order {order_id} (simulate_failure={simulate_failure})"
        )
        await execute_payment(
            order_id=order_id,
            amount=amount,
            currency=currency,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            simulate_failure=simulate_failure,
        )

    elif event_type == EventType.REFUND_INITIATED.value:
        refund_id = payload.get("refund_id")
        payment_id = payload.get("payment_id")
        order_id = payload.get("order_id")
        amount = payload.get("amount")
        reason = payload.get("reason", "Order cancellation refund")

        logger.info(f"Processing RefundInitiated for payment {payment_id}")
        now = utc_now()
        gateway_refund_id = f"reftx_{uuid.uuid4().hex[:12]}"
        refund_doc = {
            "_id": refund_id,
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": amount,
            "status": "COMPLETED",
            "gateway_refund_id": gateway_refund_id,
            "reason": reason,
            "created_at": now,
        }
        await db_manager.db.refunds.insert_one(refund_doc)
        await db_manager.db.payments.update_one(
            {"_id": payment_id},
            {"$set": {"status": PaymentStatus.REFUNDED.value, "updated_at": now}},
        )

        await db_manager.create_outbox_message(
            event_type=EventType.REFUND_SUCCEEDED.value,
            aggregate_id=refund_id,
            correlation_id=correlation_id,
            producer=settings.SERVICE_NAME,
            payload={
                "refund_id": refund_id,
                "payment_id": payment_id,
                "order_id": order_id,
                "amount": amount,
                "gateway_refund_id": gateway_refund_id,
            },
        )
        logger.info(f"Refund {refund_id} completed for order {order_id}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global outbox_worker
    await db_manager.connect()

    # Indexes
    await db_manager.db.payments.create_index("order_id")
    await db_manager.db.payments.create_index("status")
    await db_manager.db.outbox.create_index("status")

    try:
        await rabbitmq_client.connect()
        await rabbitmq_client.register_consumer(
            queue_name="payment.events",
            routing_keys=[
                "order-service.PaymentInitiated",
                "order-service.RefundInitiated",
            ],
            message_handler=handle_payment_events,
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
    logger.info("Payment service shutdown")


app = FastAPI(title="Payment Service", version="1.0.0", lifespan=lifespan)
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


@app.post(
    "/api/v1/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def process_payment(
    request: PaymentCreateRequest,
    user: TokenUser = Depends(get_current_user),
):
    corr_id = correlation_id_ctx.get()
    doc = await execute_payment(
        order_id=request.order_id,
        amount=request.amount,
        currency=request.currency,
        idempotency_key=request.idempotency_key,
        correlation_id=corr_id,
        card_last_four=request.card_last_four,
        simulate_failure=request.simulate_failure,
    )
    return PaymentResponse(
        id=str(doc["_id"]),
        order_id=doc["order_id"],
        amount=doc["amount"],
        currency=doc["currency"],
        status=PaymentStatus(doc["status"]),
        transaction_id=doc.get("transaction_id"),
        card_last_four=doc.get("card_last_four"),
        failure_reason=doc.get("failure_reason"),
        idempotency_key=doc["idempotency_key"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@app.get("/api/v1/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    user: TokenUser = Depends(get_current_user),
):
    doc = await db_manager.db.payments.find_one({"_id": payment_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentResponse(
        id=str(doc["_id"]),
        order_id=doc["order_id"],
        amount=doc["amount"],
        currency=doc["currency"],
        status=PaymentStatus(doc["status"]),
        transaction_id=doc.get("transaction_id"),
        card_last_four=doc.get("card_last_four"),
        failure_reason=doc.get("failure_reason"),
        idempotency_key=doc["idempotency_key"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@app.get(
    "/api/v1/payments",
    response_model=list[PaymentResponse],
    dependencies=[Depends(require_roles(["ADMIN", "OPERATIONS"]))],
)
async def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    cursor = (
        db_manager.db.payments.find().sort("created_at", -1).skip(skip).limit(limit)
    )
    items = await cursor.to_list(length=limit)
    return [
        PaymentResponse(
            id=str(doc["_id"]),
            order_id=doc["order_id"],
            amount=doc["amount"],
            currency=doc["currency"],
            status=PaymentStatus(doc["status"]),
            transaction_id=doc.get("transaction_id"),
            card_last_four=doc.get("card_last_four"),
            failure_reason=doc.get("failure_reason"),
            idempotency_key=doc["idempotency_key"],
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )
        for doc in items
    ]


@app.post("/api/v1/payments/{payment_id}/refund", response_model=RefundResponse)
async def refund_payment(
    payment_id: str,
    request: RefundRequest,
    user: TokenUser = Depends(get_current_user),
):
    payment = await db_manager.db.payments.find_one({"_id": payment_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment["status"] != PaymentStatus.SUCCEEDED.value:
        raise HTTPException(
            status_code=400, detail="Only successful payments can be refunded"
        )

    corr_id = correlation_id_ctx.get()
    refund_id = f"ref-{uuid.uuid4().hex[:10]}"
    gateway_refund_id = f"reftx_{uuid.uuid4().hex[:12]}"
    now = utc_now()
    amount = request.amount or payment["amount"]

    refund_doc = {
        "_id": refund_id,
        "payment_id": payment_id,
        "order_id": payment["order_id"],
        "amount": amount,
        "status": "COMPLETED",
        "gateway_refund_id": gateway_refund_id,
        "reason": request.reason,
        "idempotency_key": request.idempotency_key,
        "created_at": now,
    }
    await db_manager.db.refunds.insert_one(refund_doc)
    await db_manager.db.payments.update_one(
        {"_id": payment_id},
        {"$set": {"status": PaymentStatus.REFUNDED.value, "updated_at": now}},
    )

    await db_manager.create_outbox_message(
        event_type=EventType.REFUND_SUCCEEDED.value,
        aggregate_id=refund_id,
        correlation_id=corr_id,
        producer=settings.SERVICE_NAME,
        payload={
            "refund_id": refund_id,
            "payment_id": payment_id,
            "order_id": payment["order_id"],
            "amount": amount,
            "gateway_refund_id": gateway_refund_id,
        },
    )

    return RefundResponse(
        id=refund_id,
        payment_id=payment_id,
        order_id=payment["order_id"],
        amount=amount,
        status="COMPLETED",
        gateway_refund_id=gateway_refund_id,
        reason=request.reason,
        created_at=now,
    )
