# Product Service — Independent Microservice Engineering Guide

**Service Name**: `product-service`  
**Container Port**: `8002`  
**Default Database**: `product_db` (MongoDB)  
**Caching Layer**: Redis (TTL 300s, cache-aside with write invalidation)  
**Outbox Worker**: Transactional outbox polling MongoDB `outbox` collection and publishing to RabbitMQ topic exchange `ecommerce.events`.  
**Primary Responsibilities**: Product catalog management, categories, search/filter/sort, stock status views, and product lifecycle event publishing.

---

## 1. Architecture & Domain Isolation

- **Owned Collections**:
  - `products`: Product master records (`id`, `name`, `description`, `price` in cents, `sku` unique indexed, `category`, `image_url`, `is_active`, `created_at`, `updated_at`).
  - `outbox`: Transactional outbox records (`event_id`, `event_type`, `routing_key`, `payload`, `status: pending|published`, `created_at`).
- **Database Isolation**: The Product Service owns `product_db`. It never accesses `inventory_db`, `order_db`, or `cart_db` directly.
- **Cache Strategy**:
  - Reads check Redis key `product:{id}` first. If found, returns immediately with HTTP header `X-Cache: HIT`.
  - On cache miss, loads from MongoDB, sets key with 300s TTL, and returns with header `X-Cache: MISS`.
  - On product update or deletion, the Redis cache key is invalidated atomically (`redis_client.delete(f"product:{product_id}")`).
- **Event-Driven Integration**:
  - `ProductCreated`, `ProductUpdated`, and `ProductDeleted` events are inserted into the local `outbox` collection within the same MongoDB transaction/operation, guaranteeing zero dual-write inconsistency.
  - The background `OutboxWorker` asynchronously delivers these events to RabbitMQ with routing keys `product.created`, `product.updated`, and `product.deleted`.

---

## 2. API Specification

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Liveness probe & service ping. |
| `GET` | `/ready` | Public | Readiness probe (checks MongoDB and Redis connectivity). |
| `GET` | `/metrics` | Public | Prometheus scrape metrics (`product_cache_hits_total`, etc.). |
| `GET` | `/api/v1/products` | Public | Filtered & paginated product catalog (`category`, `search`, `min_price`, `max_price`, `sort_by`, `sort_dir`). |
| `GET` | `/api/v1/products/categories` | Public | List of distinct product categories. |
| `GET` | `/api/v1/products/{id}` | Public | Single product details with Redis caching (`X-Cache: HIT/MISS`). |
| `POST` | `/api/v1/products` | Admin (`ADMIN`) | Create product & record `ProductCreated` outbox event. |
| `PUT` | `/api/v1/products/{id}` | Admin (`ADMIN`) | Update product, invalidate cache & record `ProductUpdated` event. |
| `DELETE`| `/api/v1/products/{id}` | Admin (`ADMIN`) | Soft/hard delete product, invalidate cache & record `ProductDeleted`. |

---

## 3. Local Development & Testing

### 3.1 Environment Variables
| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `PRODUCT_SERVICE_PORT` | `8002` | Port for FastAPI / Uvicorn server. |
| `PRODUCT_DB_NAME` | `product_db` | MongoDB database owned by Product Service. |
| `MONGO_URI` | `mongodb://localhost:27018` | MongoDB connection string. |
| `REDIS_URL` | `redis://localhost:16379` | Redis cache connection string. |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5673/` | RabbitMQ AMQP connection string. |
| `EXCHANGE_NAME` | `ecommerce.events` | RabbitMQ topic exchange name. |

### 3.2 Running Tests
```bash
# Unit tests
pytest services/product-service/tests/test_product_service_unit.py -v

# Live integration tests against running environment
pytest services/product-service/tests/test_product_service_live.py -v
```

