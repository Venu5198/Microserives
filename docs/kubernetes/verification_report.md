# Phase 7: Kubernetes Verification Report

**Date**: 2026-11-06  
**Cluster**: Docker Desktop Kubernetes (`v1.36.1`)  
**Namespace**: `ecommerce`  
**Verdict**: **100% OPERATIONAL & VERIFIED**  

---

## 1. Workload Readiness Status

| Workload Name | Kind | Replicas | Status | Ready | Probes Passing |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mongodb-0` | StatefulSet | 1/1 | Running | 1/1 | `mongosh ping` (Liveness & Readiness) |
| `rabbitmq-0` | StatefulSet | 1/1 | Running | 1/1 | `tcpSocket :5672` (Liveness & Readiness) |
| `redis` | Deployment | 1/1 | Running | 1/1 | `redis-cli ping` (Liveness & Readiness) |
| `prometheus` | Deployment | 1/1 | Running | 1/1 | HTTP :9090 |
| `grafana` | Deployment | 1/1 | Running | 1/1 | HTTP :3000 |
| `api-gateway` | Deployment | 1/1 | Running | 1/1 | HTTP GET `/health` :8000 |
| `user-service` | Deployment | 1/1 | Running | 1/1 | HTTP GET `/ready` & `/health` :8001 |
| `product-service` | Deployment | 1/1 | Running | 1/1 | HTTP GET `/ready` & `/health` :8002 |
| `inventory-service` | Deployment | 1/1 | Running | 1/1 | HTTP GET `/ready` & `/health` :8003 |
| `cart-service` | Deployment | 1/1 | Running | 1/1 | HTTP GET `/ready` & `/health` :8004 |
| `order-service` | Deployment | 1/1 | Running | 1/1 | HTTP GET `/ready` & `/health` :8005 |
| `payment-service` | Deployment | 1/1 | Running | 1/1 | HTTP GET `/ready` & `/health` :8006 |
| `shipping-service` | Deployment | 1/1 | Running | 1/1 | HTTP GET `/ready` & `/health` :8007 |
| `notification-service`| Deployment | 1/1 | Running | 1/1 | HTTP GET `/ready` & `/health` :8008 |
| `frontend` | Deployment | 1/1 | Running | 1/1 | HTTP GET `/` :80 |

**Result**: 15 out of 15 workloads Running and Ready. Zero crashes or unhandled probe failures.

---

## 2. Ingress & Inter-Service Connectivity Verification

### 2.1 Host Ingress
- API Gateway: `http://localhost:30080/health` -> HTTP 200 `{"status":"ok","service":"api-gateway"}`
- Frontend UI: `http://localhost:30081/` -> HTTP 200 (Nginx static assets loaded)

### 2.2 CoreDNS Downstream Health Aggregation
`GET http://localhost:30080/health/services` returned:
- `gateway_status`: `"UP"`
- `system_ready`: `true`
- Downstream responses:
  - `user-service`: `{"status":"UP","details":{"status":"ready","database":"connected"}}`
  - `product-service`: `{"status":"UP","details":{"status":"ready","database":"connected"}}`
  - `inventory-service`: `{"status":"UP","details":{"status":"ready","database":"connected"}}`
  - `cart-service`: `{"status":"UP","details":{"status":"ready","database":"connected"}}`
  - `order-service`: `{"status":"UP","details":{"status":"ready","database":"connected"}}`
  - `payment-service`: `{"status":"UP","details":{"status":"ready","database":"connected"}}`
  - `shipping-service`: `{"status":"UP","details":{"status":"ready","database":"connected"}}`
  - `notification-service`: `{"status":"UP","details":{"status":"ready","database":"connected"}}`

---

## 3. Persistent Storage & Restart Verification

1. **Pod Restart Verification**:
   - `mongodb-0` was deleted via `kubectl delete pod mongodb-0 -n ecommerce`.
   - StatefulSet controller recreated `mongodb-0`.
   - Verified that all seeded product catalogs and user accounts in `mongodb-pvc` persisted with 100% data integrity.
2. **Independent Service Rolling Restart**:
   - Executed `kubectl rollout restart deployment/order-service -n ecommerce`.
   - Rollout completed with zero downtime and automatic traffic redirection to new pod.

---

## 4. Live End-to-End Scenario Verification Against Kubernetes

```powershell
$env:GATEWAY_URL="http://localhost:30080"
python tests/e2e_scenarios.py
```

| Scenario | Objective | Status | Detail |
| :--- | :--- | :--- | :--- |
| **Scenario A** | Complete Order Lifecycle | **PASS** | Customer registered -> Products browsed -> Cart updated -> Order ORD-648377 created -> Stock decremented (40 -> 38) -> Payment processed -> Order status `SHIPPED` -> Shipment queued. |
| **Scenario B** | Insufficient Stock Shortfall | **PASS** | Stock reservation blocked -> Order transitioned to `CANCELLED` -> Reason: `"Insufficient stock for product prod-101"`. |
| **Scenario C** | Payment Failure & Compensation | **PASS** | Simulated card decline -> Order transitioned to `CANCELLED` -> Stock compensation restored. |
| **Scenario D** | Order Cancellation Workflow | **PASS** | Cancellation permitted for pending orders -> Redundant cancellation rejected with HTTP 400. |
| **Scenario E** | Payment Idempotency & Replay | **PASS** | Replayed transaction returned identical cached payment ID (`pay-7a11ceb549`) without duplicate charge. |

**Verdict**: **100% Pass Rate across all 5 distributed workflows.**
