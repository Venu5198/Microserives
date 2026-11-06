# Teardown Script for Local Kubernetes Deployment
Write-Host ">>> Deleting ecommerce Kubernetes resources..." -ForegroundColor Yellow
kubectl delete namespace ecommerce --timeout=60s
Write-Host ">>> Teardown complete." -ForegroundColor Green
