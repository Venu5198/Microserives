.PHONY: help up down build test lint clean

help:
	@echo "Available commands:"
	@echo "  make up      - Start all services with Docker Compose"
	@echo "  make down    - Stop all services"
	@echo "  make build   - Build all microservice Docker images"
	@echo "  make test    - Run automated test suite with Pytest"
	@echo "  make clean   - Remove caches and build artifacts"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

test:
	pytest tests/ -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache frontend/dist
