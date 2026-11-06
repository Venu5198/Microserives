# Local Development Guide

## 1. Prerequisites
- Docker Desktop with Kubernetes enabled
- Python 3.12+
- Node.js 18+ (for frontend)
- `kubectl` configured to context `docker-desktop`

## 2. Deploying to Local Kubernetes
To deploy the entire platform into the local `ecommerce` namespace:

```powershell
# Run deploy script
.\k8s\deploy.ps1

# Check pod readiness (15 pods expected)
kubectl get pods -n ecommerce
```

## 3. Port Mappings & Ingress
All external traffic flows through NodePort services:
- **API Gateway**: `http://localhost:30080`
- **React Frontend**: `http://localhost:30081`
- **Grafana Dashboard**: `kubectl port-forward -n ecommerce svc/grafana 3000:3000` (User: `admin`, Pass: `admin`)
- **Prometheus UI**: `kubectl port-forward -n ecommerce svc/prometheus 9090:9090`
- **RabbitMQ Management**: `kubectl port-forward -n ecommerce svc/rabbitmq 15672:15672` (User: `guest`, Pass: `guest`)

## 4. Running Microservices Locally (Out-of-Cluster)
Each microservice can be run independently using its dedicated virtual environment:
```powershell
cd services/product-service
uvicorn main:app --reload --port 8002
```
Ensure `MONGO_URI`, `REDIS_URL`, and `RABBITMQ_URL` point to reachable instances.
