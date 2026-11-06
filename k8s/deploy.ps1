# Automated Repeatable Kubernetes Deployment Script for Docker Desktop
Write-Host ">>> [1/4] Applying Kubernetes Namespace, Secrets, and ConfigMaps..." -ForegroundColor Cyan
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-secrets.yaml
kubectl apply -f k8s/02-configmaps.yaml
kubectl apply -f k8s/03-storage.yaml

Write-Host ">>> [2/4] Deploying Core Infrastructure (MongoDB, RabbitMQ, Redis, Monitoring)..." -ForegroundColor Cyan
kubectl apply -f k8s/04-infrastructure/mongodb.yaml
kubectl apply -f k8s/04-infrastructure/rabbitmq.yaml
kubectl apply -f k8s/04-infrastructure/redis.yaml
kubectl apply -f k8s/04-infrastructure/prometheus.yaml
kubectl apply -f k8s/04-infrastructure/grafana.yaml

Write-Host ">>> Waiting for MongoDB and RabbitMQ to reach Ready status..." -ForegroundColor Yellow
kubectl wait --namespace ecommerce --for=condition=ready pod -l app=mongodb --timeout=90s
kubectl wait --namespace ecommerce --for=condition=ready pod -l app=rabbitmq --timeout=90s
kubectl wait --namespace ecommerce --for=condition=ready pod -l app=redis --timeout=60s

Write-Host ">>> [3/4] Deploying Business Microservices..." -ForegroundColor Cyan
kubectl apply -f k8s/05-services/

Write-Host ">>> [4/4] Deploying API Gateway and Frontend Ingress..." -ForegroundColor Cyan
kubectl apply -f k8s/06-gateway/
kubectl apply -f k8s/07-frontend/

Write-Host ">>> Deployment triggered! Checking status..." -ForegroundColor Green
kubectl get pods -n ecommerce
