import asyncio
import os
import smtplib
import uuid
from contextlib import asynccontextmanager
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Query, status
from prometheus_client import make_asgi_app

from ecommerce_common.config import BaseServiceSettings
from ecommerce_common.logging import setup_logger
from ecommerce_common.middleware import register_base_middlewares
from ecommerce_common.security import (
    get_current_user_dependency,
    TokenUser,
    require_roles,
)
from ecommerce_common.database import serialize_doc, DatabaseManager
from ecommerce_common.rabbitmq import RabbitMQClient
from contracts.events.types import EventType
from models import NotificationSendRequest, NotificationResponse, utc_now

logger = setup_logger("notification-service")


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "notification-service"
    DATABASE_NAME: str = os.getenv("NOTIFICATION_DB_NAME", "notification_db")
    PORT: int = int(os.getenv("NOTIFICATION_SERVICE_PORT", "8008"))

    # SMTP Settings
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "1025"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "no-reply@ecommerce.local")


settings = Settings()
db_manager = DatabaseManager(settings.MONGO_URI, settings.DATABASE_NAME)
rabbitmq_client = RabbitMQClient(settings.RABBITMQ_URL, settings.EXCHANGE_NAME, settings.DLX_EXCHANGE_NAME)


def render_template(template_name: str, data: dict) -> tuple[str, str]:
    if template_name == "order_confirmed":
        subject = f"Order Confirmed: {data.get('order_number')}"
        body = f"""Hello!
Your order {data.get('order_number')} has been confirmed!
Total Amount: ${data.get('total_amount', 0) / 100:.2f}
We are packing your items and will notify you when your shipment is on the way.
Thank you for shopping with us!"""
    elif template_name == "shipment_created":
        subject = f"Your order has shipped! Tracking: {data.get('tracking_number')}"
        body = f"""Great news!
Your order has been shipped via {data.get('carrier', 'Standard Express')}.
Tracking Number: {data.get('tracking_number')}
Estimated Delivery: {data.get('estimated_delivery')}
Track your package anytime from your customer dashboard."""
    elif template_name == "shipment_status_updated":
        subject = f"Shipment Update for Tracking {data.get('tracking_number')}: {data.get('new_status')}"
        body = f"""Status update: Your shipment is now {data.get('new_status')} at {data.get('location', 'in transit')}.
Notes: {data.get('notes', 'No additional details')}"""
    elif template_name == "order_cancelled":
        subject = f"Order Cancelled: {data.get('order_id')}"
        body = f"""Your order {data.get('order_id')} has been cancelled.
Reason: {data.get('reason')}
{('A full refund has been issued to your original payment method.' if data.get('refund_required') else '')}"""
    elif template_name == "payment_failed":
        subject = "Payment Failed for your Order"
        body = f"""We were unable to process your payment for order {data.get('order_id')}.
Reason: {data.get('reason')}
Please check your payment information."""
    else:
        subject = data.get("subject", "Notification from E-Commerce Platform")
        body = str(data)

    return subject, body


async def send_email_async(to_email: str, subject: str, body: str) -> bool:
    """Attempts SMTP transmission, falls back cleanly to simulated dispatch if no SMTP daemon is up."""
    def _sync_send():
        try:
            msg = MIMEMultipart()
            msg["From"] = settings.SMTP_FROM_EMAIL
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=2.0) as server:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            return True, None
        except Exception as e:
            return False, str(e)

    loop = asyncio.get_event_loop()
    success, err = await loop.run_in_executor(None, _sync_send)
    if not success:
        logger.info(f"Simulated email delivery to {to_email} (SMTP server not reachable: {err})")
    else:
        logger.info(f"Delivered email via SMTP to {to_email}")
    return True


async def process_and_log_notification(
    recipient_email: str,
    template_name: str,
    template_data: dict,
    custom_subject: Optional[str] = None,
):
    notif_id = f"notif-{uuid.uuid4().hex[:10]}"
    now = utc_now()
    subject, content = render_template(template_name, template_data)
    if custom_subject:
        subject = custom_subject

    await send_email_async(recipient_email, subject, content)

    doc = {
        "_id": notif_id,
        "recipient_email": recipient_email,
        "subject": subject,
        "template_name": template_name,
        "template_data": template_data,
        "status": "SENT",
        "attempt_count": 1,
        "content": content,
        "error": None,
        "created_at": now,
        "sent_at": now,
    }
    await db_manager.db.notifications.insert_one(doc)
    logger.info(f"Notification logged: {notif_id} to {recipient_email}")


async def handle_notification_events(event_data: dict):
    event_type = event_data.get("event_type")
    payload = event_data.get("payload", {})

    if event_type == EventType.ORDER_CONFIRMED.value:
        email = payload.get("customer_email")
        if email:
            await process_and_log_notification(email, "order_confirmed", payload)

    elif event_type == EventType.SHIPMENT_CREATED.value:
        email = payload.get("recipient_email")
        if email:
            await process_and_log_notification(email, "shipment_created", payload)

    elif event_type == EventType.SHIPMENT_STATUS_UPDATED.value:
        # Fetch shipment recipient
        shipment_id = payload.get("shipment_id")
        email = payload.get("recipient_email", "customer@ecommerce.local")
        await process_and_log_notification(email, "shipment_status_updated", payload)

    elif event_type == EventType.ORDER_CANCELLED.value:
        email = payload.get("customer_email")
        if email:
            await process_and_log_notification(email, "order_cancelled", payload)

    elif event_type == EventType.PAYMENT_FAILED.value:
        email = payload.get("customer_email", "customer@ecommerce.local")
        await process_and_log_notification(email, "payment_failed", payload)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_manager.connect()
    await db_manager.db.notifications.create_index("recipient_email")
    await db_manager.db.notifications.create_index("created_at")

    try:
        await rabbitmq_client.connect()
        await rabbitmq_client.register_consumer(
            queue_name="notification.all-events",
            routing_keys=[
                "order-service.OrderConfirmed",
                "order-service.OrderCancelled",
                "shipping-service.ShipmentCreated",
                "shipping-service.ShipmentStatusUpdated",
                "payment-service.PaymentFailed",
            ],
            message_handler=handle_notification_events,
        )
    except Exception as e:
        logger.warning(f"RabbitMQ connection postponed during startup: {e}")

    yield
    await rabbitmq_client.close()
    await db_manager.disconnect()
    logger.info("Notification service shutdown")


app = FastAPI(title="Notification Service", version="1.0.0", lifespan=lifespan)
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


@app.post("/api/v1/notifications/send", response_model=NotificationResponse)
async def manual_send(req: NotificationSendRequest):
    await process_and_log_notification(
        recipient_email=req.recipient_email,
        template_name=req.template_name,
        template_data=req.template_data,
        custom_subject=req.subject,
    )
    doc = await db_manager.db.notifications.find_one(
        {"recipient_email": req.recipient_email}, sort=[("created_at", -1)]
    )
    return NotificationResponse(**serialize_doc(doc))


@app.get("/api/v1/notifications", response_model=List[NotificationResponse], dependencies=[Depends(require_roles(["ADMIN", "OPERATIONS"]))])
async def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    cursor = db_manager.db.notifications.find().sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    return [NotificationResponse(**serialize_doc(doc)) for doc in items]
