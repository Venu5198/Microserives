# Engineering Audit: Security & Threat Assessment

**Auditor**: Application Security Engineer  
**Security Tools Used**: Bandit Static Security Scanner, Manual Code Audit  

---

## 1. Security Controls Assessment

| Control Area | Implementation | Evaluation |
| :--- | :--- | :--- |
| **Password Hashing** | Argon2id (`time_cost=3`, `memory_cost=65536`, `parallelism=4`) via `argon2-cffi` | **EXCELLENT** — Exceeds standard bcrypt/PBKDF2 industry baselines |
| **Token Architecture** | JWT HS256 access tokens (60 min expiration) + rotating UUID4 refresh tokens stored in MongoDB with explicit revocation support | **VERIFIED** |
| **Role-Based Access Control (RBAC)**| FastAPI dependency injection checking claims for `CUSTOMER`, `ADMIN`, `OPERATIONS` | **VERIFIED** — Non-admin calls to `/admin/*` or `/api/v1/inventory` PATCH rejected with 403 Forbidden |
| **Card Data Masking** | Only `card_last_four` and tokenized transaction IDs persisted; no raw PANs or CVVs stored | **PCI-DSS COMPLIANT ARCHITECTURE** |
| **Injection Protection** | Motor asynchronous BSON drivers with parameterized query dicts; zero raw eval | **PASSED** |
| **API Rate Limiting** | Gateway sliding-window limiter (200 req/min per client IP) | **ACTIVE** |
| **Static Security Scan** | Bandit AST analysis on Python backend (`bandit -r services/ packages/ -ll -ii`) | **CLEAN** — 0 High, 0 Medium severity issues across 3,137 LOC |
