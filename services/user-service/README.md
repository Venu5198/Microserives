# User Service — Independent Microservice Engineering Guide

**Service Name**: `user-service`  
**Container Port**: `8001`  
**Default Database**: `user_db` (MongoDB)  
**Authentication Standard**: Argon2id password hashing + HS256 JWT access and refresh tokens  
**Primary Responsibilities**: Identity management, customer registration, authentication, token rotation/revocation, user profile & shipping address management, and administrative user directory.

---

## 1. Architecture & Domain Isolation

The User Service conforms strictly to the **Database-per-Service** pattern:
- **Owned Collections**:
  - `users`: User identities, emails (unique indexed), Argon2id password hashes, first/last names, roles (`CUSTOMER`, `ADMIN`, `OPERATIONS`), and account status.
  - `refresh_tokens`: Cryptographically random UUID refresh tokens, associated user ID, expiration timestamp, and `revoked` flag.
  - `addresses`: Shipping addresses per user with compound index on `(user_id, is_default)`.
- **Zero Cross-Database Coupling**: The User Service has no network access or references to `order_db`, `payment_db`, `product_db`, or any foreign database.
- **Stateless Verification**: Downstream services (e.g., Order Service, API Gateway) verify JWT signatures symmetrically using `JWT_SECRET_KEY` without performing synchronous RPCs back to the User Service.

---

## 2. API Specification

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Kubernetes liveness probe & service ping. |
| `GET` | `/ready` | Public | Kubernetes readiness probe (checks MongoDB ping). |
| `GET` | `/metrics` | Public | Prometheus scrape endpoint. |
| `POST` | `/api/v1/auth/register` | Public | Register a new user (`CUSTOMER` default; 201 Created). |
| `POST` | `/api/v1/auth/login` | Public | Authenticate with email/password; returns access & refresh tokens. |
| `POST` | `/api/v1/auth/refresh` | Public | Rotate refresh token; revokes old token and issues fresh pair. |
| `POST` | `/api/v1/auth/logout` | Bearer Token | Revoke active refresh token. |
| `GET` | `/api/v1/users/me` | Bearer Token | Retrieve authenticated user profile and addresses. |
| `POST` | `/api/v1/users/me/addresses`| Bearer Token | Add shipping address to profile. |
| `GET` | `/api/v1/users` | Admin Role (`ADMIN`) | Paginated administrative user directory (403 for Customer). |

---

## 3. Local Development

### 3.1 Environment Variables
| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `USER_SERVICE_PORT` | `8001` | TCP port for FastAPI / Uvicorn server. |
| `USER_DB_NAME` | `user_db` | MongoDB database name owned by User Service. |
| `MONGO_URI` | `mongodb://localhost:27018` | MongoDB connection string. |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5673/` | RabbitMQ broker AMQP URL. |
| `JWT_SECRET_KEY` | *(Set in Secrets)* | Minimum 32-character HMAC secret key. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifespan. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifespan. |

### 3.2 Running Locally
```powershell
# From repository root
cd C:\devops\Microservices

# Activate Python environment
.\.venv\Scripts\Activate.ps1

# Start User Service locally
python -m uvicorn services.user-service.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## 4. Independent Docker Lifecycle

The User Service can be packaged and executed as a standalone container without building or running other microservices.

### 4.1 Build Standalone Image
```powershell
docker build -t ecommerce/user-service:latest -f services/user-service/Dockerfile .
```

### 4.2 Run Standalone Container
```powershell
docker run -d `
  --name standalone-user-service `
  --network microservices_ecommerce-net `
  -p 18001:8001 `
  -e MONGO_URI=mongodb://mongodb:27017 `
  -e USER_DB_NAME=user_db `
  -e JWT_SECRET_KEY=supersecretjwtkeychangeinproductionminimum32characterslong `
  ecommerce/user-service:latest
```

---

## 5. Independent Kubernetes Lifecycle

The User Service is deployed in the `ecommerce` namespace via [`k8s/05-services/user-service.yaml`](file:///c:/devops/Microservices/k8s/05-services/user-service.yaml).

### 5.1 Deploy or Update User Service Only
```powershell
# Apply spec changes without affecting other services
kubectl apply -f k8s/05-services/user-service.yaml

# Perform a rolling restart of User Service
kubectl rollout restart deployment/user-service -n ecommerce

# Check rollout status
kubectl rollout status deployment/user-service -n ecommerce
```

---

## 6. Testing & Quality Assurance

### 6.1 Execute User Service Test Suite
```powershell
# Run unit & live integration tests
$env:USER_SERVICE_URL="http://localhost:18001"
python -m pytest services/user-service/tests/ -v

# Run dedicated failure and security experiments
python services/user-service/tests/failure_experiments.py
```

### 6.2 Test Coverage Highlights
- **Unit Tests (`test_user_service_unit.py`)**: Argon2id password hash/verify, JWT generation/tampering/expiration, Pydantic model validation.
- **Live Lifecycle (`test_user_service_live.py`)**: Registration, login, profile retrieval, address management, refresh token rotation, replay prevention, logout.
- **Security & RBAC (`failure_experiments.py`)**: 409 duplicate registration, concurrent email creation race conditions, 403 Forbidden customer enforcement, 401 tampered/expired token handling.

---

## 7. Dedicated GitHub CI/CD Workflow

The User Service features an independent CI pipeline defined in [`.github/workflows/user-service-ci.yml`](file:///c:/devops/Microservices/.github/workflows/user-service-ci.yml):
1. **Change Detection**: Triggers only on PRs or pushes affecting `services/user-service/**`, `packages/common/**`, or the workflow file itself.
2. **Linting & Code Quality**: Executes `ruff check` on the service and shared packages.
3. **Static Security Analysis**: Scans with `bandit -r services/user-service -ll -ii` (zero high/medium vulnerability requirement).
4. **Isolated Automated Tests**: Spins up a containerized MongoDB service (`mongo:7.0`) and runs the pytest test suite.
5. **Artifact Packaging**: Builds the Docker container and tags it with semantic versions and commit SHAs (`ecommerce/user-service:${{ github.sha }}`) without automatic cloud deployment.

