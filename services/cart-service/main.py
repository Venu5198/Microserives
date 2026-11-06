import os
from contextlib import asynccontextmanager

import httpx
from ecommerce_common.config import BaseServiceSettings
from ecommerce_common.logging import setup_logger
from ecommerce_common.middleware import register_base_middlewares
from ecommerce_common.security import TokenUser, get_current_user_dependency
from fastapi import Depends, FastAPI, HTTPException, status
from models import CartItemAdd, CartItemResponse, CartItemUpdate, CartResponse, utc_now
from motor.motor_asyncio import AsyncIOMotorClient
from prometheus_client import make_asgi_app

logger = setup_logger("cart-service")


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "cart-service"
    DATABASE_NAME: str = os.getenv("CART_DB_NAME", "cart_db")
    PORT: int = int(os.getenv("CART_SERVICE_PORT", "8004"))
    PRODUCT_SERVICE_URL: str = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8002")


settings = Settings()
client: AsyncIOMotorClient | None = None
db = None
http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, db, http_client
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.DATABASE_NAME]
    http_client = httpx.AsyncClient(timeout=5.0)

    await db.carts.create_index("user_id", unique=True)
    yield
    await http_client.aclose()
    client.close()
    logger.info("Cart service shutdown")


app = FastAPI(title="Cart Service", version="1.0.0", lifespan=lifespan)
register_base_middlewares(app)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

get_current_user = get_current_user_dependency(
    secret_key=settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
)


async def fetch_product_details(product_id: str) -> dict:
    try:
        url = f"{settings.PRODUCT_SERVICE_URL}/api/v1/products/{product_id}"
        resp = await http_client.get(url)
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Product not found")
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Unable to validate product with Product Service",
            )
        return resp.json()
    except httpx.RequestError as e:
        logger.error(f"Error calling Product Service: {e}")
        raise HTTPException(status_code=503, detail="Product Service unavailable")


def calculate_cart_response(user_id: str, items: list, updated_at) -> CartResponse:
    item_responses = []
    total_amount = 0
    total_items = 0

    for it in items:
        subtotal = it["unit_price"] * it["quantity"]
        total_amount += subtotal
        total_items += it["quantity"]
        item_responses.append(
            CartItemResponse(
                product_id=it["product_id"],
                product_name=it["product_name"],
                unit_price=it["unit_price"],
                quantity=it["quantity"],
                image_url=it.get("image_url"),
                subtotal=subtotal,
            )
        )

    return CartResponse(
        user_id=user_id,
        items=item_responses,
        total_amount=total_amount,
        total_items=total_items,
        updated_at=updated_at,
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


@app.get("/api/v1/cart", response_model=CartResponse)
async def get_cart(user: TokenUser = Depends(get_current_user)):
    cart = await db.carts.find_one({"user_id": user.user_id})
    if not cart:
        return CartResponse(
            user_id=user.user_id,
            items=[],
            total_amount=0,
            total_items=0,
            updated_at=utc_now(),
        )
    return calculate_cart_response(
        user.user_id, cart.get("items", []), cart.get("updated_at", utc_now())
    )


@app.post("/api/v1/cart/items", response_model=CartResponse)
async def add_item_to_cart(
    item_in: CartItemAdd, user: TokenUser = Depends(get_current_user)
):
    product = await fetch_product_details(item_in.product_id)
    if not product.get("is_active", True):
        raise HTTPException(status_code=400, detail="Product is currently inactive")

    now = utc_now()
    cart = await db.carts.find_one({"user_id": user.user_id})
    items = cart.get("items", []) if cart else []

    found = False
    for it in items:
        if it["product_id"] == item_in.product_id:
            it["quantity"] += item_in.quantity
            it["unit_price"] = product["price"]  # update price with fresh catalog
            found = True
            break

    if not found:
        items.append(
            {
                "product_id": product["id"],
                "product_name": product["name"],
                "unit_price": product["price"],
                "quantity": item_in.quantity,
                "image_url": product.get("image_url"),
            }
        )

    await db.carts.update_one(
        {"user_id": user.user_id},
        {"$set": {"items": items, "updated_at": now}},
        upsert=True,
    )

    return calculate_cart_response(user.user_id, items, now)


@app.put("/api/v1/cart/items/{product_id}", response_model=CartResponse)
@app.patch("/api/v1/cart/items/{product_id}", response_model=CartResponse)
async def update_cart_item(
    product_id: str,
    update_in: CartItemUpdate,
    user: TokenUser = Depends(get_current_user),
):
    cart = await db.carts.find_one({"user_id": user.user_id})
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    items = cart.get("items", [])
    found = False
    for it in items:
        if it["product_id"] == product_id:
            it["quantity"] = update_in.quantity
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail="Item not found in cart")

    now = utc_now()
    await db.carts.update_one(
        {"user_id": user.user_id},
        {"$set": {"items": items, "updated_at": now}},
    )

    return calculate_cart_response(user.user_id, items, now)


@app.delete("/api/v1/cart/items/{product_id}", response_model=CartResponse)
async def remove_cart_item(
    product_id: str, user: TokenUser = Depends(get_current_user)
):
    cart = await db.carts.find_one({"user_id": user.user_id})
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    items = [it for it in cart.get("items", []) if it["product_id"] != product_id]
    now = utc_now()
    await db.carts.update_one(
        {"user_id": user.user_id},
        {"$set": {"items": items, "updated_at": now}},
    )

    return calculate_cart_response(user.user_id, items, now)


@app.delete("/api/v1/cart", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(user: TokenUser = Depends(get_current_user)):
    await db.carts.delete_one({"user_id": user.user_id})
