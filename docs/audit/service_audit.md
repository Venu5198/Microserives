# Engineering Audit: Service-by-Service Review

**Audit Date**: November 2026  
**Auditor**: Senior Backend & Microservices Engineer  
**Scope**: All 8 Business Microservices + API Gateway  

---

## 1. Services Audit Matrix

| Service | Host Port | Internal Port | Database | Outbox Worker | Health / Ready Check |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `api-gateway` | `18000` | `8000` | *None* | N/A | `/health`, `/health/services` |
| `user-service` | `18001` | `8001` | `user_db` | N/A (Command source) | `/health`, `/ready` |
| `product-service` | `18002` | `8002` | `product_db` | N/A | `/health`, `/ready` |
| `inventory-service` | `18003` | `8003` | `inventory_db` | Active | `/health`, `/ready` |
| `cart-service` | `18004` | `8004` | `cart_db` | N/A | `/health`, `/ready` |
| `order-service` | `18005` | `8005` | `order_db` | Active | `/health`, `/ready` |
| `payment-service` | `18006` | `8006` | `payment_db` | Active | `/health`, `/ready` |
| `shipping-service` | `18007` | `8007` | `shipping_db` | Active | `/health`, `/ready` |
| `notification-service` | `18008` | `8008` | `notification_db` | Active | `/health`, `/ready` |

---

## 2. Defects Identified & Remediated

### Defect SVC-001 (CRITICAL - Resolved)
- **Component**: `payment-service` event listener (`handle_payment_events`)
- **Root Cause**: `handle_payment_events` consumed `PaymentInitiated` without extracting `payment_method` from the event payload. Consequently, simulated decline scenarios defaulted to successful charges, preventing failure compensation paths from triggering during checkout.
- **Evidence**: `tests/e2e_scenarios.py` Scenario C initially returned status `CONFIRMED` instead of `CANCELLED`.
- **Fix**: Extracted `payload.get("payment_method")` and passed `simulate_failure = (payment_method == "card_simulate_decline")` to `execute_payment()`.
- **Status**: FIXED & VERIFIED. Re-test passed with 100% compliance.

### Defect SVC-002 (HIGH - Resolved)
- **Component**: `user-service` and `notification-service` models
- **Root Cause**: `EmailStr` imported from Pydantic triggered RFC DNS checks rejecting `.local` domains during local container development (`admin@ecommerce.local`).
- **Fix**: Adjusted model definition to allow standard string email validation for offline/local environments.
- **Status**: FIXED & VERIFIED.

### Defect SVC-003 (HIGH - Resolved)
- **Component**: `payment-service` MongoDB initialization
- **Root Cause**: `db.idempotency_keys.create_index("_id", unique=True)` threw `InvalidIndexSpecificationOption` because MongoDB automatically creates a unique index on `_id`.
- **Fix**: Removed redundant index command on `_id`.
- **Status**: FIXED & VERIFIED.
