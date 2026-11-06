import os
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorClient
from prometheus_client import Counter, Histogram, make_asgi_app

from ecommerce_common.config import BaseServiceSettings
from ecommerce_common.logging import setup_logger
from ecommerce_common.middleware import register_base_middlewares
from ecommerce_common.security import (
    get_current_user_dependency,
    TokenUser,
    require_roles,
)
from ecommerce_common.database import serialize_doc
from models import ProductCreate, ProductUpdate, ProductResponse, utc_now

logger = setup_logger("product-service")


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "product-service"
    DATABASE_NAME: str = os.getenv("PRODUCT_DB_NAME", "product_db")
    PORT: int = int(os.getenv("PRODUCT_SERVICE_PORT", "8002"))


settings = Settings()
client: Optional[AsyncIOMotorClient] = None
db = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, db
    logger.info(f"Connecting to MongoDB at {settings.MONGO_URI} ({settings.DATABASE_NAME})")
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.DATABASE_NAME]

    # Indexes
    await db.products.create_index("sku", unique=True)
    await db.products.create_index("category")
    await db.products.create_index([("name", "text"), ("description", "text")])

    # Seed sample catalog if empty
    count = await db.products.count_documents({})
    if count == 0:
        sample_products = [
            {
                "_id": "prod-101",
                "name": "Noise Cancelling Headphones",
                "description": "Premium wireless headphones with active noise cancellation and 30-hour battery life.",
                "price": 19999,  # $199.99
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
                "price": 8999,  # $89.99
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
                "price": 2850,  # $28.50
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
                "price": 24900,  # $249.00
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
    client.close()
    logger.info("Product service shutdown")


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
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unready: {e}")


@app.get("/api/v1/products", response_model=List[ProductResponse])
async def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    active_only: bool = True,
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

    cursor = db.products.find(query).skip(skip).limit(limit).sort("created_at", -1)
    items = await cursor.to_list(length=limit)
    return [ProductResponse(**serialize_doc(item)) for item in items]


@app.get("/api/v1/products/categories", response_model=List[str])
async def list_categories():
    categories = await db.products.distinct("category", {"is_active": True})
    return categories


@app.get("/api/v1/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    doc = await db.products.find_one({"_id": product_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse(**serialize_doc(doc))


@app.post(
    "/api/v1/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(["ADMIN", "OPERATIONS"]))],
)
async def create_product(
    product_in: ProductCreate, user: TokenUser = Depends(get_current_user)
):
    existing_sku = await db.products.find_one({"sku": product_in.sku})
    if existing_sku:
        raise HTTPException(status_code=409, detail=f"Product SKU {product_in.sku} already exists")

    product_id = f"prod-{uuid.uuid4().hex[:8]}"
    now = utc_now()
    doc = product_in.model_dump()
    doc["_id"] = product_id
    doc["created_at"] = now
    doc["updated_at"] = now

    await db.products.insert_one(doc)
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
    return ProductResponse(**serialize_doc(updated))


@app.delete(
    "/api/v1/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(["ADMIN"]))],
)
async def delete_product(product_id: str, user: TokenUser = Depends(get_current_user)):
    existing = await db.products.find_one({"_id": product_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    # Soft delete / deactivation
    await db.products.update_one(
        {"_id": product_id},
        {"$set": {"is_active": False, "updated_at": utc_now()}},
    )
    logger.info(f"Product {product_id} deactivated by admin {user.user_id}")

