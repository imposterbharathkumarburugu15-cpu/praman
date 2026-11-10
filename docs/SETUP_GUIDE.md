# PRAMAN Local Setup & Operational Guide

## 1. System Requirements & Prerequisites

- **Operating System**: Windows 10/11, macOS (Apple Silicon or Intel), or Linux (Ubuntu 22.04+).
- **Python**: Version **3.13.9** (or 3.11+).
- **PostgreSQL**: Version **17** running locally on port **1234** (user: `postgres`, password: `postgres`).
- **Node.js & npm**: Node.js **18.x** or higher with npm **9.x+**.
- **Hardware**: Standard x86_64 or ARM64 CPU. No GPU is required; all AI operations execute 100% locally on CPU.

---

## 2. Environment Configuration

The system uses standard environment variables with production defaults in `backend/app/core/config.py`:

```env
# PostgreSQL Database Connection
DATABASE_URL=postgresql://postgres:postgres@localhost:1234/praman

# Storage Directory
STORAGE_DIR=data/storage

# Server Host and Port
HOST=0.0.0.0
PORT=8000

# CORS Allowed Origins
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8081", "http://localhost:19006"]
```

---

## 3. Database Initialization & Migrations

### 3.1 Automated Database Creation
Run the database initialization script to ensure the `praman` database is created on PostgreSQL port 1234:
```bash
python backend/init_db.py
```

### 3.2 Running Alembic Migrations
Apply the schema migration to create all tables (`farmers`, `devices`, `farms`, `evidence`, `audit_log`) and PostgreSQL immutability triggers:
```bash
# Navigate to backend directory or run from root
alembic upgrade head
```

---

## 4. Running the Backend Service

Launch the FastAPI application server using Uvicorn:
```bash
# Start FastAPI backend on port 8000
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Verifying Service Health:
Open your browser or run curl:
```bash
curl http://localhost:8000/api/v1/health
```
Expected response:
```json
{
  "status": "HEALTHY",
  "version": "1.0.0",
  "database": "CONNECTED",
  "storage": "WRITABLE",
  "timestamp": "..."
}
```

Interactive OpenAPI documentation is available at:
- **Swagger UI**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **ReDoc**: [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)

---

## 5. Running the Test Suites

PRAMAN includes a comprehensive test harness comprising 457 automated tests across unit, adversarial, cryptographic, spatial, backend, AI, and dual-track end-to-end suites.

### 5.1 Running All Tests via Pytest
```bash
# Execute entire test suite
pytest
```
*Current test suite result: **457 passed**.*

### 5.2 Running the Unified E2E Test Runner
The E2E test runner executes 289 opaque-box, requirement-driven tests covering all 45 features across 4 tiers:
```bash
# Run all 4 tiers
python tests_e2e/test_runner.py

# Run specific tiers
python tests_e2e/test_runner.py --tier 1       # Tier 1: 45 Features (225 tests)
python tests_e2e/test_runner.py --tier 2       # Tier 2: Boundary Cases (35 tests)
python tests_e2e/test_runner.py --tier 3       # Tier 3: Interactions (25 tests)
python tests_e2e/test_runner.py --tier 4       # Tier 4: Real-World Scenarios (4 tests)

# Generate detailed JSON execution report
python tests_e2e/test_runner.py --verbose --report test_report_full.json
```

### 5.3 Running Subsystem Test Suites
```bash
# Cryptographic library & adversarial test vectors (138 tests)
pytest crypto/tests

# Backend API platform & database persistence (25 tests)
pytest backend/tests

# Local AI intelligence engine (5 tests)
python -m pytest ai_engine/tests
```

---

## 6. Subsystem Operation Guides

### 6.1 Farmer Mobile Application (`mobile/`)
The mobile application source code is located in `mobile/src/`:
- **Multilingual Catalogs**: `mobile/src/i18n/catalogs.ts` (Telugu `te`, Hindi `hi`, English `en`).
- **Android Keystore Bridge**: `mobile/src/crypto/keystore.ts` (P-256 key generation and signing).
- **Offline Storage Queue**: `mobile/src/storage/offlineQueue.ts` (SQLite storage with state transitions).
- **Synchronization Engine**: `mobile/src/services/syncService.ts` (Idempotent sync with durable server receipts).

### 6.2 Reviewer Console & Public Verification (`web_console/`)
- **Reviewer Visualizer & Decisions**: `web_console/reviewer/` (RBAC authentication, visualizer cards, attributable decisions).
- **Merkle Ledger Batching**: `web_console/ledger/merkle_anchor.py` (Domain-separated Merkle batch builder).
- **Public Verification Portal**: `web_console/public_verify/portal.py` (Sanitized public token generator ensuring zero PII and zero GPS leakage).

