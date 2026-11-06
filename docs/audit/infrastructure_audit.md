# Engineering Audit: Infrastructure & DevOps Audit

**Auditor**: DevOps & Cloud Infrastructure Engineer  
**Environments Audited**: Docker Compose Local Orchestration, Kubernetes Manifests, Helm Chart  

---

## 1. Container Health & Network Isolation

All 15 containers reside in the isolated bridge network `microservices_ecommerce-net`:

| Container Name | Image | Host Port | Internal Port | Status | Healthcheck Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `ecommerce-api-gateway` | `microservices-api-gateway` | `18000` | `8000` | Up | HTTP `/health` |
| `ecommerce-user-service` | `microservices-user-service` | `18001` | `8001` | Up | HTTP `/ready` |
| `ecommerce-product-service` | `microservices-product-service` | `18002` | `8002` | Up | HTTP `/ready` |
| `ecommerce-inventory-service`| `microservices-inventory-service`| `18003` | `8003` | Up | HTTP `/ready` |
| `ecommerce-cart-service` | `microservices-cart-service` | `18004` | `8004` | Up | HTTP `/ready` |
| `ecommerce-order-service` | `microservices-order-service` | `18005` | `8005` | Up | HTTP `/ready` |
| `ecommerce-payment-service` | `microservices-payment-service` | `18006` | `8006` | Up | HTTP `/ready` |
| `ecommerce-shipping-service` | `microservices-shipping-service`| `18007` | `8007` | Up | HTTP `/ready` |
| `ecommerce-notification-service`| `microservices-notification-service`| `18008`| `8008` | Up | HTTP `/ready` |
| `ecommerce-frontend` | `microservices-frontend` | `13000` | `80` | Up | Nginx HTTP 200 |
| `ecommerce-mongo` | `mongo:7.0` | `27018` | `27017` | Up (healthy) | `mongosh db.adminCommand('ping')` |
| `ecommerce-rabbitmq` | `rabbitmq:3.13-management` | `5673`, `15673`| `5672`, `15672`| Up (healthy) | `rabbitmq-diagnostics ping` |
| `ecommerce-redis` | `redis:7.2-alpine` | `16379` | `6379` | Up (healthy) | `redis-cli ping` |
| `ecommerce-prometheus` | `prom/prometheus:v2.51.0` | `19090` | `9090` | Up | HTTP `/metrics` scrape active |
| `ecommerce-grafana` | `grafana/grafana:10.4.1` | `13001` | `3000` | Up | HTTP Web UI |

---

## 2. Kubernetes & Helm Review
- `infrastructure/kubernetes/`: Clean production manifests defining Namespace (`ecommerce-prod`), ConfigMaps, Secrets, Deployments with non-root security contexts, resource requests/limits, readiness/liveness probes, Ingress, and HorizontalPodAutoscalers (HPA).
- `infrastructure/helm/ecommerce-platform/`: Helm chart with configurable values (`values.yaml`), parameterized replica counts, image registries, and resource constraints for automated GKE rollouts.
- `.github/workflows/`: CI (`ci.yml`) and GKE deployment (`deploy.yml`) pipelines configured with Google Workload Identity Federation and Trivy vulnerability scanning.
