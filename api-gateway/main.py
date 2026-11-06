import os
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager

import httpx
from ecommerce_common.config import BaseServiceSettings
from ecommerce_common.logging import correlation_id_ctx, setup_logger
from ecommerce_common.security import decode_jwt_token
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app

logger = setup_logger("api-gateway")


class GatewaySettings(BaseServiceSettings):
    SERVICE_NAME: str = "api-gateway"
    PORT: int = int(os.getenv("GATEWAY_PORT", "8000"))

    # Downstream service URLs
    USER_SERVICE_URL: str = os.getenv("USER_SERVICE_URL", "http://localhost:8001")
    PRODUCT_SERVICE_URL: str = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8002")
    INVENTORY_SERVICE_URL: str = os.getenv(
        "INVENTORY_SERVICE_URL", "http://localhost:8003"
    )
    CART_SERVICE_URL: str = os.getenv("CART_SERVICE_URL", "http://localhost:8004")
    ORDER_SERVICE_URL: str = os.getenv("ORDER_SERVICE_URL", "http://localhost:8005")
    PAYMENT_SERVICE_URL: str = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8006")
    SHIPPING_SERVICE_URL: str = os.getenv(
        "SHIPPING_SERVICE_URL", "http://localhost:8007"
    )
    NOTIFICATION_SERVICE_URL: str = os.getenv(
        "NOTIFICATION_SERVICE_URL", "http://localhost:8008"
    )


settings = GatewaySettings()
http_client: httpx.AsyncClient | None = None

# In-memory sliding window rate limiter: IP -> list of timestamps
rate_limit_records = defaultdict(list)
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 200

REQUEST_COUNT = Counter(
    "gateway_requests_total",
    "Total requests routed via gateway",
    ["service", "method", "status"],
)
REQUEST_LATENCY = Histogram(
    "gateway_request_duration_seconds", "Gateway request latency", ["service"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("API Gateway started. Downstream routes configured.")
    yield
    await http_client.aclose()
    logger.info("API Gateway shutdown.")


app = FastAPI(title="E-Commerce API Gateway", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


def get_service_route(path: str) -> tuple[str, str]:
    if path.startswith("/api/v1/auth") or path.startswith("/api/v1/users"):
        return settings.USER_SERVICE_URL, "user-service"
    elif path.startswith("/api/v1/products"):
        return settings.PRODUCT_SERVICE_URL, "product-service"
    elif path.startswith("/api/v1/inventory"):
        return settings.INVENTORY_SERVICE_URL, "inventory-service"
    elif path.startswith("/api/v1/cart"):
        return settings.CART_SERVICE_URL, "cart-service"
    elif path.startswith("/api/v1/orders"):
        return settings.ORDER_SERVICE_URL, "order-service"
    elif path.startswith("/api/v1/payments"):
        return settings.PAYMENT_SERVICE_URL, "payment-service"
    elif path.startswith("/api/v1/shipments"):
        return settings.SHIPPING_SERVICE_URL, "shipping-service"
    elif path.startswith("/api/v1/notifications"):
        return settings.NOTIFICATION_SERVICE_URL, "notification-service"
    return "", ""


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}


@app.get("/health/services")
async def health_aggregation():
    """Aggregates health checks of all 8 business microservices."""
    service_map = {
        "user-service": settings.USER_SERVICE_URL,
        "product-service": settings.PRODUCT_SERVICE_URL,
        "inventory-service": settings.INVENTORY_SERVICE_URL,
        "cart-service": settings.CART_SERVICE_URL,
        "order-service": settings.ORDER_SERVICE_URL,
        "payment-service": settings.PAYMENT_SERVICE_URL,
        "shipping-service": settings.SHIPPING_SERVICE_URL,
        "notification-service": settings.NOTIFICATION_SERVICE_URL,
    }
    results = {}
    all_ready = True

    for name, base_url in service_map.items():
        try:
            resp = await http_client.get(f"{base_url}/ready", timeout=2.0)
            if resp.status_code == 200:
                results[name] = {"status": "UP", "details": resp.json()}
            else:
                results[name] = {"status": "DEGRADED", "code": resp.status_code}
                all_ready = False
        except Exception as e:
            results[name] = {"status": "DOWN", "error": str(e)}
            all_ready = False

    return {
        "gateway_status": "UP",
        "system_ready": all_ready,
        "services": results,
    }


@app.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
)
async def route_proxy(request: Request, path: str):
    full_path = f"/{path}"
    target_base, service_name = get_service_route(full_path)

    if not target_base:
        raise HTTPException(
            status_code=404, detail=f"No route found for path '{full_path}'"
        )

    # Rate Limiting
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    rate_limit_records[client_ip] = [
        t for t in rate_limit_records[client_ip] if now - t < RATE_LIMIT_WINDOW_SECONDS
    ]
    if len(rate_limit_records[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please slow down.",
        )
    rate_limit_records[client_ip].append(now)

    # Correlation ID
    corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    correlation_id_ctx.set(corr_id)

    # Forward headers
    forward_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ["host", "content-length"]
    }
    forward_headers["X-Correlation-ID"] = corr_id

    # Token Validation & Identity Extraction
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            decoded = decode_jwt_token(
                token, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM
            )
            forward_headers["X-User-Id"] = decoded.get("sub", "")
            forward_headers["X-User-Email"] = decoded.get("email", "")
            forward_headers["X-User-Role"] = decoded.get("role", "")
        except HTTPException:
            # Let downstream reject or allow public access if token expired
            pass

    body = await request.body()
    query_params = request.url.query
    target_url = f"{target_base}{full_path}"
    if query_params:
        target_url = f"{target_url}?{query_params}"

    start_time = time.time()
    try:
        downstream_resp = await http_client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            content=body,
        )
        duration = time.time() - start_time
        REQUEST_COUNT.labels(
            service=service_name,
            method=request.method,
            status=downstream_resp.status_code,
        ).inc()
        REQUEST_LATENCY.labels(service=service_name).observe(duration)

        response_headers = dict(downstream_resp.headers)
        response_headers["X-Correlation-ID"] = corr_id
        # Remove hop-by-hop headers
        for h in ["content-encoding", "transfer-encoding", "content-length"]:
            response_headers.pop(h, None)

        return Response(
            content=downstream_resp.content,
            status_code=downstream_resp.status_code,
            headers=response_headers,
            media_type=downstream_resp.headers.get("content-type"),
        )
    except httpx.ConnectError:
        logger.error(
            f"Failed to connect to downstream service '{service_name}' at {target_url}"
        )
        raise HTTPException(
            status_code=503,
            detail=f"Service '{service_name}' is temporarily unavailable",
        )
    except Exception as e:
        logger.error(f"Gateway proxy error: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Bad Gateway: {e!s}")
