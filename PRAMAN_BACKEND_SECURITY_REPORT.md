# PRAMAN Backend Security & Data Persistence Audit Report

**Scope**: FastAPI Backend Platform, PostgreSQL 17 Database, Storage, and Authorization  
**Audit Date**: November 9, 2026  
**Test Suites**: `backend/tests/`, `tests_e2e/tier1_features/test_f08_db_schema.py` through `test_f17_async_ai_dispatch.py`  

---

## 1. Authentication & Authorization Boundaries

### 1.1 Cross-Farmer Tenant Isolation
- **Mechanism**: All farm and evidence queries filter strictly on authenticated `farmer_id` extracted from JWT session.
- **Verification**: Submitting evidence or reading farm data belonging to `farmer_A` using a valid JWT for `farmer_B` results in `403 Forbidden` / `404 Not Found`.

### 1.2 Reviewer Role-Based Access Control (RBAC)
- **Role Separation**: Endpoints under `/api/v1/reviewer/` require explicit `role: reviewer` or `role: admin`.
- **Farmer Token Prohibited**: Farmer JWTs attempting to access review queues or submit review decisions receive `403 Forbidden`.

### 1.3 Device Management & Revocation
- **Enrollment**: Devices submit public key via `/api/v1/devices/enroll` with farmer JWT.
- **Revocation**: Device status set to `REVOKED`. Subsequent evidence submissions signed by the revoked device key are rejected with `401 Unauthorized: Device revoked`.

---

## 2. Spatial Geometry & Farm Boundary Security

- **Coordinate System**: WGS84 (`EPSG:4326`).
- **Polygon Invariants Enforced**:
  1. Minimum 3 distinct vertices.
  2. Polygon must be explicitly closed (first vertex == last vertex).
  3. No self-intersections (Bow-tie polygons rejected with `422 Unprocessable Content`).
  4. Latitude $\in [-90, 90]$, Longitude $\in [-180, 180]$.
- **Pure-Python Validation**: Implemented without external unstable geospatial libraries, ensuring reproducible cross-platform operation.

---

## 3. Database Integrity & Immutability Triggers

- **Database Engine**: PostgreSQL 17 running on port `1234`.
- **Primary Keys**: UUIDv4 across all entities.
- **Append-Only Immutability**:
  - `audit_log` table protected by PostgreSQL row-level trigger preventing `UPDATE` and `DELETE` operations.
  - Evidence records and signatures cannot be deleted once committed.

---

## 4. Input Validation & Content-Addressable Storage

- **Pydantic V2 Schemas**: Strict type checking and constraint enforcement on all request bodies.
- **Local Storage Architecture**:
  - Images stored in sharded directory hierarchy: `data/storage/ab/cd/abcdef1234...jpg`.
  - Directory path derived directly from the computed SHA-256 digest of original bytes.
  - Path traversal attacks (`../../`) eliminated by strict hex validation on SHA-256 digest before filesystem lookup.

---

## 5. Secrets Management & Local Development Boundaries

- No hardcoded secrets in source control.
- Configuration managed via `pydantic-settings` with `.env` fallback.
- **Production Warning Note**: For local development, JWT secret is loaded from environment variables (`SECRET_KEY`). Production deployment must use a cryptographically strong secret stored in a hardware vault / KMS.

---

## Verdict: VALIDATED WITHIN TESTED SCOPE
Cross-tenant isolation, reviewer RBAC, device revocation, and database immutability triggers function correctly with zero security bypasses.

