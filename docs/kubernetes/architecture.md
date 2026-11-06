# Local Kubernetes Architecture Documentation

**Target Environment**: Docker Desktop Kubernetes (`docker-desktop` cluster context)  
**Dedicated Namespace**: `ecommerce`  
**Storage Provisioner**: `docker.io/hostpath` (Default StorageClass)

---

## 1. Workload Architecture & Topology

The platform consists of 15 containerized workloads organized into 3 tiers:

```
                            [ Host Browser / Clients ]
                                  |         |
                  :30081 (Frontend)         :30080 (API Gateway)
                                  |         |
                     +------------+         +------------+
                     |                                   |
              [ frontend-pod ]                   [ api-gateway-pod ]
             (Nginx / React SPA)                 (FastAPI Reverse Proxy)
                                                         |
          +----------------------------------------------+-------------------------------------+
          |                      |                       |                       |             |
   [ user-service ]       [ product-service ]     [ inventory-service ]    [ cart-service ]    ...
     (:8001 / HTTP)         (:8002 / HTTP)          (:8003 / HTTP)          (:8004 / HTTP)
          |                      |                       |                       |
          +----------+-----------+-----------+-----------+                       |
                     |                       |                                   |
                     v                       v                                   v
             [ mongodb-0 ]             [ rabbitmq-0 ]                       [ redis ]
        (Database-per-Service)      (Async Event Broker)                 (Cart Storage)
```

### 1.1 Ingress & Routing (NodePort / ClusterIP)
- **API Gateway Service**: `type: NodePort`, maps container port `8000` to NodePort `30080`. External clients connect to `http://localhost:30080`.
- **Frontend Service**: `type: NodePort`, maps container port `80` to NodePort `30081`. External clients browse to `http://localhost:30081`.
- **Internal Microservices**: `type: ClusterIP`. Completely shielded from external network; addressable strictly through internal Kubernetes CoreDNS.

### 1.2 CoreDNS In-Cluster Service Registry
All services communicate over private cluster DNS without hardcoded IPs or `localhost`:
- `user-service.ecommerce.svc.cluster.local:8001`
- `product-service.ecommerce.svc.cluster.local:8002`
- `inventory-service.ecommerce.svc.cluster.local:8003`
- `cart-service.ecommerce.svc.cluster.local:8004`
- `order-service.ecommerce.svc.cluster.local:8005`
- `payment-service.ecommerce.svc.cluster.local:8006`
- `shipping-service.ecommerce.svc.cluster.local:8007`
- `notification-service.ecommerce.svc.cluster.local:8008`
- `mongodb.ecommerce.svc.cluster.local:27017`
- `rabbitmq.ecommerce.svc.cluster.local:5672`
- `redis.ecommerce.svc.cluster.local:6379`
- `prometheus.ecommerce.svc.cluster.local:9090`
- `grafana.ecommerce.svc.cluster.local:3000`

---

## 2. Configuration & Secrets Hierarchy

| Resource Name | Kind | Purpose |
| :--- | :--- | :--- |
| `ecommerce-secrets` | `Secret` | Holds `JWT_SECRET_KEY`, `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS`, `GRAFANA_ADMIN_PASSWORD`. |
| `ecommerce-common-config` | `ConfigMap` | Global connection strings (`MONGO_URI`, `RABBITMQ_URL`, `REDIS_URL`, `ENVIRONMENT: "local-k8s"`). |
| `api-gateway-config` | `ConfigMap` | Downstream service URLs for reverse proxy routing. |
| `ecommerce-services-config` | `ConfigMap` | Database names (`user_db`, `order_db`, etc.) and port mappings. |
| `prometheus-config` | `ConfigMap` | Prometheus scrape targets for all 9 services. |

---

## 3. Persistent Storage Architecture

Stateful workloads mount persistent storage using `hostpath` persistent volume claims (PVCs):
- `mongodb-pvc` (5Gi) mounted to `/data/db`
- `rabbitmq-pvc` (2Gi) mounted to `/var/lib/rabbitmq`
- `redis-pvc` (1Gi) mounted to `/data`
- `prometheus-pvc` (2Gi) mounted to `/prometheus`
- `grafana-pvc` (1Gi) mounted to `/var/lib/grafana`

Data survives pod eviction, rolling restarts, or manual pod recreation.

---

## 4. Health Checks & Reliability Controls

- **Readiness Probes**:
  - Python microservices: HTTP GET `/ready` (validates database connection and worker loop initialization).
  - API Gateway: HTTP GET `/health`.
  - RabbitMQ: TCP Socket check on port `5672`.
  - MongoDB: Exec check `mongosh --eval "db.adminCommand('ping')"`.
  - Redis: Exec check `redis-cli ping`.
- **Liveness Probes**:
  - Python microservices: HTTP GET `/health`.
  - Probes automatically restart degraded or deadlocked containers.
