# Distributed Systems & Resilience Verification Guide

## 1. Overview
This test suite validates core distributed systems properties across asynchronous microservices:
1. **At-Least-Once Delivery**: Transactional Outbox pattern guarantees event persistence prior to broker publish.
2. **Exactly-Once Semantics**: Idempotency keys prevent double charge / duplicate side-effects.
3. **Atomic Concurrency**: Database-level conditional operations (`$gte`) prevent race conditions and overselling under load.
4. **Compensating Transactions**: Saga orchestration cleanly reverts state when downstream failures occur.

## 2. End-to-End Functional Test Suite
Validates Scenarios A through E live against the API Gateway (`http://localhost:30080`):
```powershell
.venv\Scripts\python.exe tests/e2e_scenarios.py
```
- **Scenario A**: End-to-end checkout, saga orchestration, inventory reservation, tracking generation.
- **Scenario B**: Insufficient inventory rejection and saga cancellation.
- **Scenario C**: Payment declined simulation and automatic inventory compensation rollback.
- **Scenario D**: Order cancellation workflow and rejection on final states.
- **Scenario E**: Payment idempotency duplicate replay validation.

## 3. High-Concurrency & Stress Test Suite
Simulates concurrent race conditions and parallel idempotency attacks:
```powershell
.venv\Scripts\python.exe tests/distributed_resilience_test.py
```
- **Test 1: Concurrent Payment Idempotency**: 5 simultaneous HTTP POST requests with identical idempotency key returning the exact same payment record.
- **Test 2: Atomic Stock Contention**: 10 simultaneous orders competing for limited stock; confirms zero overselling and exact mathematical balance.
