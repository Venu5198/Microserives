# Docker Desktop Kubernetes Deployment Guide

This guide documents the repeatable deployment and teardown of the E-Commerce Microservices Platform on local Docker Desktop Kubernetes.

---

## 1. Prerequisites

1. **Docker Desktop**:
   - Docker Desktop running with WSL2 backend.
   - Kubernetes enabled in Docker Desktop Settings -> **Kubernetes** -> **Enable Kubernetes**.
2. **Tools**:
   - `kubectl` configured to context `docker-desktop`:
     ```powershell
     kubectl config use-context docker-desktop
     ```
   - Python virtual environment `.venv` with `httpx` (for verification test runner).

---

## 2. One-Click Deployment

Deploy the complete platform using PowerShell:

```powershell
# From the repository root (C:\devops\Microservices)
.\k8s\deploy.ps1
```

Or using native `kubectl` commands sequentially:

```powershell
# 1. Namespace, Secrets, ConfigMaps, and Storage
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-secrets.yaml
kubectl apply -f k8s/02-configmaps.yaml
kubectl apply -f k8s/03-storage.yaml

# 2. Stateful Infrastructure
kubectl apply -f k8s/04-infrastructure/

# 3. Wait for database and broker to be ready
kubectl wait --namespace ecommerce --for=condition=ready pod -l app=mongodb --timeout=90s
kubectl wait --namespace ecommerce --for=condition=ready pod -l app=rabbitmq --timeout=90s
kubectl wait --namespace ecommerce --for=condition=ready pod -l app=redis --timeout=60s

# 4. Business Microservices
kubectl apply -f k8s/05-services/

# 5. Ingress & Frontend
kubectl apply -f k8s/06-gateway/
kubectl apply -f k8s/07-frontend/
```

Or apply all resources using Kustomize:
```powershell
kubectl apply -k k8s/
```

---

## 3. Verify Deployment

### 3.1 Check Pod Status
```powershell
kubectl get pods -n ecommerce -o wide
```
All 15 pods must report `STATUS: Running` and `READY: 1/1`.

### 3.2 Check Service Ingress
```powershell
kubectl get svc -n ecommerce
```

### 3.3 Verify Endpoints from Host
- **API Gateway Health**:
  ```powershell
  curl.exe http://localhost:30080/health
  ```
- **Downstream Aggregated Health**:
  ```powershell
  curl.exe http://localhost:30080/health/services
  ```
- **Frontend SPA**:
  Open browser at `http://localhost:30081`.

---

## 4. Run End-to-End Verification Test

Execute the 5 distributed scenarios against the local Kubernetes cluster:

```powershell
$env:GATEWAY_URL="http://localhost:30080"
.venv\Scripts\python tests/e2e_scenarios.py
```

Expected output:
```
ALL LIVE SCENARIOS AUDITED AND VERIFIED WITH 100% SUCCESS!
```

---

## 5. Teardown

To remove all workloads and free cluster resources:

```powershell
.\k8s\teardown.ps1
```
Or:
```powershell
kubectl delete namespace ecommerce
```
