# Cart Service — Independent Microservice Engineering Guide

**Service Name**: `cart-service`  
**Container Port**: `8004`  
**Default Database**: `cart_db` (MongoDB)  
**Primary Responsibilities**: Shopping cart lifecycle, authenticated customer isolation, real-time product validation, subtotal/total price calculation, item quantity manipulation, and cart clearing upon order checkout.

---

## 1. Architecture & Isolation

- **Owned Collections**:
  - `carts`: User shopping cart documents (`user_id` unique indexed, `items: [{product_id, product_name, unit_price, quantity, image_url}]`, `updated_at`).
- **Customer Isolation**:
  - Every cart endpoint extracts `user.user_id` from the cryptographically verified JWT bearer token.
  - A customer can never view, mutate, or delete another customer's cart.
- **Product Verification**:
  - When an item is added to the cart, the Cart Service verifies product existence and active status (`is_active: True`) via the Product Service (`GET /api/v1/products/{product_id}`).
  - If the product is inactive or deleted, the addition is rejected with a 400 Bad Request.

---

## 2. API Specification

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Liveness probe & service ping. |
| `GET` | `/ready` | Public | Readiness probe (MongoDB ping). |
| `GET` | `/metrics` | Public | Prometheus scrape metrics. |
| `GET` | `/api/v1/cart` | Bearer Token | Retrieve caller's shopping cart and computed totals. |
| `POST` | `/api/v1/cart/items` | Bearer Token | Add an item to the shopping cart. |
| `PUT` / `PATCH` | `/api/v1/cart/items/{product_id}` | Bearer Token | Update quantity for an existing cart item. |
| `DELETE`| `/api/v1/cart/items/{product_id}` | Bearer Token | Remove specific item from cart. |
| `DELETE`| `/api/v1/cart` | Bearer Token | Clear entire cart (204 No Content). |

---

## 3. Local Development & Testing

```bash
# Unit tests (models, calculations)
pytest services/cart-service/tests/test_cart_service_unit.py -v

# Live API tests (auth isolation, cart lifecycle)
pytest services/cart-service/tests/test_cart_service_live.py -v
```

