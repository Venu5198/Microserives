# OmniStore: Production-Quality Event-Driven Microservices Platform

An enterprise-grade, asynchronous e-commerce platform built with Python (FastAPI), React 18, TypeScript, MongoDB (Database-per-Service), RabbitMQ (Transactional Outbox & Orchestrated Saga), Docker Compose, and Kubernetes (GKE).

---

## 1. System Architecture

```
                                [React Frontend]
                                       │ (HTTP / JSON)
                                       ▼
                              [API Gateway :8000]
                                       │ (JWT / Rate Limit / Correlation ID)
         ┌──────────────┬──────────────┼──────────────┬──────────────┐
         ▼              ▼              ▼              ▼              ▼
   [User Service] [Product Svc]  [Cart Service] [Order Service] [Payment Svc]
       (:8001)        (:8002)        (:8004)        (:8005)        (:8006)
      user_db       product_db       cart_db        order_db      payment_db
         │              │              │          (Orchestrator)     │
         └──────────────┴──────────────┴──────────────┼──────────────┘
                                                      │
                                           [RabbitMQ Event Broker]
                                           (ecommerce.events / DLX)
                                                      │
                                       ┌──────────────┴──────────────┐
                                       ▼                             ▼
                              [Inventory Service]            [Shipping Service]
                                    (:8003)                        (:8007)
                                 inventory_db                    shipping_db
                                       │                             │
                                       └──────────────┬──────────────┘
                                                      ▼
                                           [Notification Service]
                                                   (:8008)
                                               notification_db
```

---

## 2. Microservice Catalog & Database Ownership

| Service                        | Port     | Database            | Primary Responsibility                                                           |
| :----------------------------- | :------- | :------------------ | :------------------------------------------------------------------------------- |
| **API Gateway**          | `8000` | *None*            | Reverse proxy, JWT authentication check, rate limiting, correlation ID injection |
| **User Service**         | `8001` | `user_db`         | Argon2id auth, JWT issuance, rotating refresh tokens, RBAC, address book         |
| **Product Service**      | `8002` | `product_db`      | Product catalog CRUD, categories, search, pricing (no stock quantities)          |
| **Inventory Service**    | `8003` | `inventory_db`    | Concurrency-safe atomic reservations (`$inc`), release, and transaction audit  |
| **Cart Service**         | `8004` | `cart_db`         | Shopping cart operations, catalog price validation, subtotal calculation         |
| **Order Service**        | `8005` | `order_db`        | Order placement, Saga state machine orchestrator, cancellation workflows         |
| **Payment Service**      | `8006` | `payment_db`      | Sandbox payment gateway, idempotency key guarantees, refund processing           |
| **Shipping Service**     | `8007` | `shipping_db`     | Automatic label creation, tracking timeline, courier status simulation           |
| **Notification Service** | `8008` | `notification_db` | Event-driven customer emails (SMTP / simulation), delivery audit log             |

---

## 3. Distributed Saga Orchestration & Failure Compensation

1. **Checkout Submission**: Customer submits order -> Order Service writes `PENDING` order and publishes `OrderCreated` via Transactional Outbox.
2. **Stock Reservation**: Inventory Service consumes `OrderCreated` and executes atomic reservation:
   - *If sufficient*: emits `InventoryReserved`.
   - *If out-of-stock*: emits `InventoryReservationFailed` -> Order Service cancels order and notifies customer.
3. **Payment Execution**: Order Service advances Saga to `INVENTORY_RESERVED` and emits `PaymentInitiated`. Payment Service executes sandbox charge using unique idempotency key:
   - *If successful*: emits `PaymentSucceeded`.
   - *If card declined*: emits `PaymentFailed` -> Order Service triggers compensation (releases reserved inventory) and marks order `CANCELLED`.
4. **Fulfillment**: Order Service marks order `CONFIRMED` and emits `OrderConfirmed` -> Shipping Service generates tracking label (`ShipmentCreated`) and Notification Service emails receipt.
5. **Customer Cancellation**: If cancelled before delivery, automated compensation initiates full refund and restores inventory stock.

---

## 4. Quickstart Guide (Local Development)

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 18+

### Running the Entire Platform

```bash
# 1. Clone repository
git clone https://github.com/your-org/ecommerce-platform.git
cd ecommerce-platform

# 2. Configure environment
cp .env.example .env

# 3. Start all 13 containers (Services, MongoDB, RabbitMQ, Redis, Frontend, Prometheus, Grafana)
docker compose up -d --build

# 4. Access Platform
# Frontend:     http://localhost:3000
# API Gateway:  http://localhost:8000/docs
# RabbitMQ UI:  http://localhost:15672 (guest/guest)
# Prometheus:   http://localhost:9090
# Grafana:      http://localhost:3001 (admin/admin)
```

---

Open the platform in your browser:

* Storefront & Checkout: [http://localhost:3000](http://localhost:3000)
* Admin Console & Courier Simulator: [http://localhost:3000/admin](http://localhost:3000/admin)
* API Gateway OpenAPI Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
* RabbitMQ Management Dashboard: [http://localhost:15672](http://localhost:15672)(User: `guest`, Pass: `guest`)
* Prometheus Metrics: [http://localhost:9090](http://localhost:9090)
* Grafana Observability: [http://localhost:3001](http://localhost:3001)(User: `admin`, Pass: `admin`)

## 5. Automated Testing

Run the automated test suite covering unit tests and integrated Saga compensation:

```bash
# Setup virtual environment
python -m venv .venv
.\.venv\Scripts\activate  # Windows (or source .venv/bin/activate on Linux/macOS)

# Install test dependencies
pip install -r packages/common/requirements.txt
pip install -e packages/common
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/ -v
```

---

## 6. Kubernetes & GKE Deployment

```bash
# Apply namespace, configmaps, and secrets
kubectl apply -f infrastructure/kubernetes/namespace.yaml
kubectl apply -f infrastructure/kubernetes/configmaps.yaml

# Deploy services and ingress
kubectl apply -f infrastructure/kubernetes/services.yaml
kubectl apply -f infrastructure/kubernetes/ingress.yaml

# Or deploy with Helm
helm upgrade --install ecommerce-platform infrastructure/helm/ecommerce-platform \
  --namespace ecommerce-prod --create-namespace
```
