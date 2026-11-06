# CI/CD Workflows & Release Engineering

## 1. Pipeline Architecture
Each service is decoupled and has its own independent GitHub Actions CI workflow in `.github/workflows/`. Changes to a specific service or its shared contracts trigger only that service's pipeline.

| Workflow File | Service | Triggers |
|---|---|---|
| `user-service-ci.yml` | User Service | `services/user-service/**`, `packages/common/**` |
| `product-service-ci.yml` | Product Service | `services/product-service/**`, `packages/common/**` |
| `inventory-service-ci.yml` | Inventory Service | `services/inventory-service/**`, `packages/common/**` |
| `cart-service-ci.yml` | Cart Service | `services/cart-service/**`, `packages/common/**` |
| `order-service-ci.yml` | Order Service | `services/order-service/**`, `packages/common/**` |
| `payment-service-ci.yml` | Payment Service | `services/payment-service/**`, `packages/common/**` |
| `shipping-service-ci.yml` | Shipping Service | `services/shipping-service/**`, `packages/common/**` |
| `notification-service-ci.yml` | Notification Service | `services/notification-service/**`, `packages/common/**` |
| `api-gateway-ci.yml` | API Gateway | `services/api-gateway/**` |
| `frontend-ci.yml` | Frontend | `frontend/**` |

## 2. CI Verification Steps
Each backend workflow executes:
1. **Linting & Code Quality**: `ruff check .`
2. **Security Static Analysis**: `bandit -r . -c pyproject.toml`
3. **Unit Tests**: `pytest tests/test_*_unit.py -v`
4. **Docker Container Build**: Multi-stage Docker image verification ensuring unprivileged container execution (`USER appuser`).
