# Microservices Architecture Specification

## 1. Overview
The platform is built on an event-driven microservices architecture where each domain service owns its state, database, application entry point, lifecycle, tests, and deployment artifacts.

```
                              [ React Frontend ]
                                      |
                                      v
                             [ API Gateway :8000 ]
                                      |
      +-------------------------------+-------------------------------+
      |               |               |               |               |
      v               v               v               v               v
[ User Service ] [ Product Svc ] [ Cart Service ] [ Order Service ] [ Shipping Svc ]
   (:8001)          (:8002)         (:8004)         (:8005)          (:8007)
      |                |               |               |                |
      +----------------+---------------+---------------+----------------+
                                       |
                   [ RabbitMQ Topic Exchange (ecommerce.events) ]
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
         [ Inventory Service ]                   [ Payment Service ]
                (:8003)                                 (:8006)
                   |                                       |
                   +-------------------+-------------------+
                                       |
                                       v
                           [ Notification Service ]
                                    (:8008)
```

## 2. Microservice Boundaries & Responsibilities

| Service | Port | Database | Primary Responsibility |
|---|---|---|---|
| **User Service** | 8001 | `user_db` | User identity, Argon2id hashing, JWT token issuance & verification, RBAC |
| **Product Service** | 8002 | `product_db` | Product catalog, Redis cache-aside (TTL 300s), invalidation on mutation |
| **Inventory Service** | 8003 | `inventory_db` | Atomic stock reservation (`$gte`), compensatory rollback, outbox publishing |
| **Cart Service** | 8004 | `cart_db` | Customer cart lifecycle isolated by JWT subject (`sub`), item calculations |
| **Order Service** | 8005 | `order_db` | Distributed Saga orchestrator, order transitions, compensating transactions |
| **Payment Service** | 8006 | `payment_db` | Idempotent transaction processing, sandbox payment execution, card masking |
| **Shipping Service** | 8007 | `shipping_db` | Tracking number generation, shipment dispatch timeline, tracking lookup |
| **Notification Service** | 8008 | `notification_db` | Multi-event notification dispatch, Jinja templating, async event consumption |
| **API Gateway** | 8000 / 30080 | None | Reverse proxy, route aggregation, token pass-through, CORS handling |
| **Frontend** | 80 / 30081 | None | React + TypeScript SPA, shopping cart, checkout, order tracking |

## 3. Database Isolation
- **Database-per-Service**: Each service connects strictly to its own logical database in MongoDB (`user_db`, `product_db`, etc.).
- **Zero Cross-Database Queries**: Direct database cross-joins or multi-database queries are strictly forbidden. Cross-service interactions occur exclusively through synchronous REST via the API Gateway or asynchronous domain events via RabbitMQ.
