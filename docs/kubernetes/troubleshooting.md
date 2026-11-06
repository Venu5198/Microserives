# Kubernetes Troubleshooting & Diagnostic Guide

This guide details common diagnostic techniques, failure modes, and resolution steps for the local Docker Desktop Kubernetes environment.

---

## 1. Quick Diagnostic Commands

```powershell
# 1. Check all pods and restart counts
kubectl get pods -n ecommerce

# 2. Inspect events in the ecommerce namespace
kubectl get events -n ecommerce --sort-by='.metadata.creationTimestamp'

# 3. Stream logs for a specific service
kubectl logs -n ecommerce deployment/order-service --tail 50 -f

# 4. Describe pod for scheduling or probe failure diagnosis
kubectl describe pod <pod-name> -n ecommerce
```

---

## 2. Common Issues & Remediations

### 2.1 Pod Stuck in `ImagePullBackOff` or `ErrImagePull`
- **Root Cause**: Kubernetes cannot find the image locally because it is missing or tagged with an incorrect registry name.
- **Remediation**:
  Ensure image is present in Docker Desktop and tagged with `ecommerce/<service>:latest`.
  Verify `imagePullPolicy: IfNotPresent` is set in the Deployment spec.
  ```powershell
  docker images | Select-String "ecommerce/"
  ```

### 2.2 RabbitMQ Memory Watermark Alarm / Probe Timeout
- **Root Cause**: `rabbitmq-diagnostics ping` spins up a short-lived Erlang CLI node that can exceed tight memory limits and timeout. Also, RabbitMQ 3.13 deprecates `RABBITMQ_VM_MEMORY_HIGH_WATERMARK` env variable.
- **Remediation**:
  Use `tcpSocket: port: 5672` for Kubernetes liveness and readiness probes.
  Set memory limits to at least `2Gi` for RabbitMQ StatefulSets.

### 2.3 Host Port Conflicts on Ingress
- **Root Cause**: Windows host has existing background processes listening on ports `8000` or `3000`.
- **Remediation**:
  The Kubernetes API Gateway and Frontend services use high-range NodePorts:
  - API Gateway: `NodePort 30080` (connect via `http://localhost:30080`)
  - Frontend: `NodePort 30081` (connect via `http://localhost:30081`)
  Verify NodePort availability:
  ```powershell
  Get-NetTCPConnection -LocalPort 30080,30081 -ErrorAction SilentlyContinue
  ```

### 2.4 Internal CoreDNS Resolution Failures
- **Root Cause**: CoreDNS in `kube-system` not ready or pod attempting to use unqualified hostnames without namespace suffix.
- **Remediation**:
  Verify CoreDNS pods:
  ```powershell
  kubectl get pods -n kube-system -l k8s-app=kube-dns
  ```
  Ensure all inter-service URLs in ConfigMaps use full FQDNs:
  `http://<service-name>.ecommerce.svc.cluster.local:<port>`

### 2.5 Persistent Storage Allocation Failures
- **Root Cause**: Hostpath storage provisioner uninitialized in Docker Desktop.
- **Remediation**:
  Verify the default StorageClass:
  ```powershell
  kubectl get storageclass
  ```
  Check that `hostpath (default)` is listed. Restart Docker Desktop if storage provisioner pod is crashed.
