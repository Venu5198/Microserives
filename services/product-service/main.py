import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from typing import Literal

import redis.asyncio as aioredis
from ecommerce_common.config import BaseServiceSettings
from ecommerce_common.database import record_outbox_event, serialize_doc
from ecommerce_common.logging import setup_logger
from ecommerce_common.middleware import register_base_middlewares
from ecommerce_common.outbox_worker import OutboxWorker
from ecommerce_common.rabbitmq import RabbitMQClient
from ecommerce_common.security import (
    TokenUser,
    get_current_user_dependency,
    require_roles,
)
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from models import ProductCreate, ProductResponse, ProductUpdate, utc_now
from motor.motor_asyncio import AsyncIOMotorClient
from prometheus_client import Counter, Histogram, make_asgi_app

from contracts.events.types import EventType

logger = setup_logger("product-service")

CACHE_HITS = Counter("product_cache_hits_total", "Total Redis Cache Hits in Product Service")
CACHE_MISSES = Counter("product_cache_misses_total", "Total Redis Cache Misses in Product Service")
REQUEST_LATENCY = Histogram("product_request_duration_seconds", "Product request duration", ["endpoint"])


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "product-service"
    DATABASE_NAME: str = os.getenv("PRODUCT_DB_NAME", "product_db")
    PORT: int = int(os.getenv("PRODUCT_SERVICE_PORT", "8002"))
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    CACHE_TTL_SECONDS: int = 300


settings = Settings()
client: AsyncIOMotorClient | None = None
db = None
redis_client: aioredis.Redis | None = None
rabbitmq_client: RabbitMQClient | None = None
outbox_worker: OutboxWorker | None = None
worker_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, db, redis_client, rabbitmq_client, outbox_worker, worker_task

    # 1. MongoDB Setup
    logger.info(f"Connecting to MongoDB at {settings.MONGO_URI} ({settings.DATABASE_NAME})")
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.DATABASE_NAME]

    await db.products.create_index("sku", unique=True)
    await db.products.create_index("category")
    await db.products.create_index("is_active")
    await db.products.create_index([("name", "text"), ("description", "text")])
    await db.outbox.create_index("status")

    # 2. Redis Setup (Graceful degradation)
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info(f"Connected to Redis cache at {settings.REDIS_URL}")
    except Exception as ex:
        logger.warning(f"Redis cache unavailable at startup ({ex}). Operating in DB-only mode.")
        redis_client = None

    # 3. RabbitMQ & Outbox Worker Setup
    try:
        rabbitmq_client = RabbitMQClient(settings.RABBITMQ_URL, settings.EXCHANGE_NAME)
        await rabbitmq_client.connect()
        outbox_worker = OutboxWorker(db=db, rabbitmq_client=rabbitmq_client, poll_interval=1.0)
        worker_task = asyncio.create_task(outbox_worker.start())
        logger.info("RabbitMQ OutboxWorker initialized for Product Service")
    except Exception as ex:
        logger.warning(f"RabbitMQ connection failed ({ex}). Outbox events will persist in MongoDB.")

    # 4. Seed sample catalog if empty
    count = await db.products.count_documents({})
    if count == 0:
        sample_products = [
            {
                "_id": "prod-101",
                "name": "Noise Cancelling Headphones",
                "description": "Premium wireless headphones with active noise cancellation and 30-hour battery life.",
                "price": 19999,
                "category": "Electronics",
                "sku": "HEADPHONE-ANC-01",
                "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&auto=format&fit=crop&q=60",
                "is_active": True,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            },
            {
                "_id": "prod-102",
                "name": "Mechanical Gaming Keyboard",
                "description": "RGB mechanical keyboard with tactile switches and aircraft-grade aluminum frame.",
                "price": 8999,
                "category": "Electronics",
                "sku": "KB-MECH-RGB-02",
                "image_url": "https://images.unsplash.com/photo-1511467687858-23d96c32e4ae?w=500&auto=format&fit=crop&q=60",
                "is_active": True,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            },
            {
                "_id": "prod-103",
                "name": "Ceramic Pour-Over Coffee Dripper",
                "description": "Handcrafted minimalist ceramic coffee dripper for the perfect artisanal cup.",
                "price": 2850,
                "category": "Home & Kitchen",
                "sku": "COFFEE-DRIP-03",
                "image_url": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=500&auto=format&fit=crop&q=60",
                "is_active": True,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            },
            {
                "_id": "prod-104",
                "name": "Ergonomic Office Chair",
                "description": "Adjustable lumbar support, breathable mesh, and multi-tilt lock mechanism.",
                "price": 24900,
                "category": "Furniture",
                "sku": "CHAIR-ERGO-04",
                "image_url": "https://images.unsplash.com/photo-1580481077195-c3a821a58875?w=500&auto=format&fit=crop&q=60",
                "is_active": True,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            },
        ]
        await db.products.insert_many(sample_products)
        logger.info(f"Seeded {len(sample_products)} sample products into {settings.DATABASE_NAME}")

    yield

    if outbox_worker:
        await outbox_worker.stop()
    if worker_task:
        worker_task.cancel()
    if rabbitmq_client:
        await rabbitmq_client.close()
    if redis_client:
        await redis_client.aclose()
    client.close()
    logger.info("Product service shutdown completed")


app = FastAPI(title="Product Service", version="1.0.0", lifespan=lifespan)
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
        await db.command("ping")
        redis_status = "connected" if redis_client else "disabled"
        return {"status": "ready", "database": "connected", "cache": redis_status}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unready: {e}")


@app.get("/api/v1/products", response_model=list[ProductResponse])
async def list_products(
    category: str | None = None,
    search: str | None = None,
    active_only: bool = True,
    sort_by: Literal["created_at", "price", "name"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    query = {}
    if active_only:
        query["is_active"] = True
    if category:
        query["category"] = category
    if search:
        query["$text"] = {"$search": search}

    sort_direction = 1 if order == "asc" else -1
    cursor = db.products.find(query).skip(skip).limit(limit).sort(sort_by, sort_direction)
    items = await cursor.to_list(length=limit)
    return [ProductResponse(**serialize_doc(item)) for item in items]


@app.get("/api/v1/products/categories", response_model=list[str])
async def list_categories():
    categories = await db.products.distinct("category", {"is_active": True})
    return categories


@app.get("/api/v1/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, response: Response):
    cache_key = f"product:{product_id}"

    # Check Redis cache
    if redis_client:
        try:
            cached_json = await redis_client.get(cache_key)
            if cached_json:
                CACHE_HITS.inc()
                response.headers["X-Cache"] = "HIT"
                return ProductResponse.model_validate_json(cached_json)
        except Exception as ex:
            logger.debug(f"Redis get error: {ex}")

    CACHE_MISSES.inc()
    response.headers["X-Cache"] = "MISS"

    doc = await db.products.find_one({"_id": product_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")

    product_resp = ProductResponse(**serialize_doc(doc))

    # Populate Redis cache
    if redis_client:
        try:
            await redis_client.setex(cache_key, settings.CACHE_TTL_SECONDS, product_resp.model_dump_json())
        except Exception as ex:
            logger.debug(f"Redis set error: {ex}")

    return product_resp


@app.post(
    "/api/v1/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(["ADMIN", "OPERATIONS"]))],
)
async def create_product(
    product_in: ProductCreate,
    request: Request,
    user: TokenUser = Depends(get_current_user),
):
    existing_sku = await db.products.find_one({"sku": product_in.sku})
    if existing_sku:
        raise HTTPException(
            status_code=409, detail=f"Product SKU {product_in.sku} already exists"
        )

    product_id = f"prod-{uuid.uuid4().hex[:8]}"
    now = utc_now()
    doc = product_in.model_dump()
    doc["_id"] = product_id
    doc["created_at"] = now
    doc["updated_at"] = now

    await db.products.insert_one(doc)

    # Invalidate / Warm Cache
    if redis_client:
        try:
            cache_key = f"product:{product_id}"
            await redis_client.setex(cache_key, settings.CACHE_TTL_SECONDS, ProductResponse(**serialize_doc(doc)).model_dump_json())
        except Exception:
            pass

    # Transactional Outbox Event
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    event_payload = {
        "product_id": product_id,
        "name": doc["name"],
        "price": doc["price"],
        "category": doc["category"],
        "sku": doc["sku"],
    }
    await record_outbox_event(
        db=db,
        event_type=EventType.PRODUCT_CREATED.value,
        aggregate_type="PRODUCT",
        aggregate_id=product_id,
        payload=event_payload,
        correlation_id=correlation_id,
    )

    logger.info(f"Product {product_id} created by user {user.user_id}")
    return ProductResponse(**serialize_doc(doc))


@app.patch(
    "/api/v1/products/{product_id}",
    response_model=ProductResponse,
    dependencies=[Depends(require_roles(["ADMIN", "OPERATIONS"]))],
)
async def update_product(
    product_id: str,
    product_update: ProductUpdate,
    request: Request,
    user: TokenUser = Depends(get_current_user),
):
    existing = await db.products.find_one({"_id": product_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    update_fields = {k: v for k, v in product_update.model_dump().items() if v is not None}
    if not update_fields:
        return ProductResponse(**serialize_doc(existing))

    update_fields["updated_at"] = utc_now()
    await db.products.update_one({"_id": product_id}, {"$set": update_fields})
    updated = await db.products.find_one({"_id": product_id})

    # Cache Invalidation
    if redis_client:
        try:
            await redis_client.delete(f"product:{product_id}")
        except Exception:
            pass

    # Transactional Outbox Event
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    await record_outbox_event(
        db=db,
        event_type=EventType.PRODUCT_UPDATED.value,
        aggregate_type="PRODUCT",
        aggregate_id=product_id,
        payload={
            "product_id": product_id,
            "name": updated.get("name"),
            "price": updated.get("price"),
            "category": updated.get("category"),
            "is_active": updated.get("is_active"),
        },
        correlation_id=correlation_id,
    )

    return ProductResponse(**serialize_doc(updated))


@app.delete(
    "/api/v1/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(["ADMIN"]))],
)
async def delete_product(
    product_id: str,
    request: Request,
    user: TokenUser = Depends(get_current_user),
):
    existing = await db.products.find_one({"_id": product_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    # Soft delete / deactivation
    await db.products.update_one(
        {"_id": product_id},
        {"$set": {"is_active": False, "updated_at": utc_now()}},
    )

    # Invalidate Cache
    if redis_client:
        try:
            await redis_client.delete(f"product:{product_id}")
        except Exception:
            pass

    # Transactional Outbox Event
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    await record_outbox_event(
        db=db,
        event_type=EventType.PRODUCT_DELETED.value,
        aggregate_type="PRODUCT",
        aggregate_id=product_id,
        payload={"product_id": product_id, "sku": existing["sku"]},
        correlation_id=correlation_id,
    )

    logger.info(f"Product {product_id} deactivated by admin {user.user_id}")
