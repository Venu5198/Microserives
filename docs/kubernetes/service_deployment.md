# Independent Service Deployment & Lifecycle Guide

In this architecture, every microservice is independently deployable, configurable, and scalable without downtime or rebuilding unrelated services.

---

## 1. Independent Service Topology

Each business service in `k8s/05-services/` possesses:
- Dedicated **Deployment** with isolated container spec, env vars, and health probes.
- Dedicated **Service** with a stable cluster IP and port.
- Dedicated resource limits (`50m-300m CPU`, `64Mi-256Mi RAM`).
- Dedicated database partition in MongoDB (`user_db`, `order_db`, etc.).

---

## 2. Rebuilding and Updating an Individual Service

To update a single service (for example, `order-service`):

### Step 1: Rebuild the Container Image
```powershell
docker build -t ecommerce/order-service:latest -f services/order-service/Dockerfile .
```

### Step 2: Trigger a Zero-Downtime Rolling Update
```powershell
kubectl rollout restart deployment/order-service -n ecommerce
```

### Step 3: Monitor Rollout Progress
```powershell
kubectl rollout status deployment/order-service -n ecommerce
```
Kubernetes starts the new pod, verifies the `/ready` probe returns HTTP 200, directs traffic to the new replica, and gracefully terminates the older pod.

---

## 3. Scaling an Individual Service

To scale an individual service to handle increased load:

```powershell
# Scale order-service to 3 replicas
kubectl scale deployment/order-service --replicas=3 -n ecommerce

# Verify running replicas
kubectl get pods -n ecommerce -l app=order-service
```

---

## 4. Modifying Service-Specific Configuration

Each service's environment variables can be updated in `k8s/05-services/<service-name>.yaml` or `k8s/02-configmaps.yaml`.

Apply the modification without restarting other services:
```powershell
kubectl apply -f k8s/05-services/<service-name>.yaml
```
Kubernetes detects the spec change and triggers an atomic rolling update for that service alone.
