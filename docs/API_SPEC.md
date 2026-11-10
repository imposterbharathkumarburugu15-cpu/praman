# PRAMAN REST API Specification

## 1. Overview & Base Configuration

- **Base URL**: `http://localhost:8000/api/v1`
- **Protocol**: HTTP/1.1 with TLS (production) / Plain HTTP (local development)
- **Content Types**:
  - `application/json` for standard payload exchange.
  - `multipart/form-data` for evidence ingestion (canonical envelope, cryptographic signature, and binary JPEG/PNG file).
- **Interactive Documentation**:
  - Swagger UI: `http://localhost:8000/api/v1/docs`
  - ReDoc: `http://localhost:8000/api/v1/redoc`
  - OpenAPI JSON: `http://localhost:8000/api/v1/openapi.json`

---

## 2. API Endpoints Catalog

### 2.1 System & Health

#### `GET /api/v1/health`
Returns system operational status, database connectivity, and local storage health.

- **Response `200 OK`**:
```json
{
  "status": "HEALTHY",
  "version": "1.0.0",
  "database": "CONNECTED",
  "storage": "WRITABLE",
  "timestamp": "2026-11-09T14:30:00Z"
}
```

---

### 2.2 Farmer Identity & Authentication

#### `POST /api/v1/farmers/register` (or `POST /api/v1/farmers`)
Registers a new farmer profile.

- **Request Body**:
```json
{
  "full_name": "Ramesh Goud",
  "phone_number": "+919876543210",
  "language_pref": "te"
}
```
- **Response `201 Created`**:
```json
{
  "farmer": {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "full_name": "Ramesh Goud",
    "phone_number": "+919876543210",
    "language_pref": "te",
    "created_at": "2026-11-09T14:31:00Z"
  },
  "access_token": "praman_session_token_...",
  "token_type": "bearer"
}
```

#### `POST /api/v1/farmers/login`
Authenticates a registered farmer via verified phone number.

- **Request Body**:
```json
{
  "phone_number": "+919876543210"
}
```
- **Response `200 OK`**: Same schema as registration response.

#### `PATCH /api/v1/farmers/{farmer_id}/language`
Updates the UI language preference for the farmer.

- **Request Body**:
```json
{
  "language_pref": "hi"
}
```
- **Response `200 OK`**: Updated farmer object.

---

### 2.3 Device Registration & Public Key Management

#### `POST /api/v1/devices/register`
Binds an Android device hardware identifier and NIST P-256 public key to a registered farmer.

- **Request Body**:
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "farmer_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "public_key_pem": "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...\n-----END PUBLIC KEY-----\n"
}
```
- **Response `201 Created`**:
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "farmer_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "ACTIVE",
  "last_sequence_number": 0,
  "created_at": "2026-11-09T14:32:00Z"
}
```

#### `PATCH /api/v1/devices/{device_id}/status`
Allows administrative revocation or suspension of compromised devices.

- **Request Body**:
```json
{
  "status": "REVOKED"
}
```
- **Response `200 OK`**: Updated device record.

---

### 2.4 Farm Land Parcel Management

#### `POST /api/v1/farms`
Registers a new agricultural parcel with GeoJSON boundary polygon validation.

- **Request Body**:
```json
{
  "farmer_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "farm_name": "Adilabad Cotton Plot A",
  "crop_type": "Cotton",
  "boundary_geojson": "{\"type\":\"Polygon\",\"coordinates\":[[[78.48,17.38],[78.49,17.38],[78.49,17.39],[78.48,17.39],[78.48,17.38]]]}",
  "area_hectares": 1.25
}
```
- **Response `201 Created`**:
```json
{
  "id": "b1b11b11-1111-1111-1111-111111111111",
  "farmer_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "farm_name": "Adilabad Cotton Plot A",
  "crop_type": "Cotton",
  "boundary_geojson": "{...}",
  "area_hectares": 1.25,
  "created_at": "2026-11-09T14:33:00Z"
}
```
- **Error `400 Bad Request`**: Raised if the polygon has fewer than 3 vertices, is unclosed, or exhibits self-intersecting "bowtie" edges.

---

### 2.5 Evidence Ingestion & Cryptographic Verification

#### `POST /api/v1/evidence/ingest`
Receives field capture evidence, performs P-256 signature verification over RFC 8785 canonical envelopes, executes row-level sequence locking, writes images to content-addressable storage, and dispatches local AI evaluation.

- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `envelope` (string, required): RFC 8785 canonical JSON envelope string.
  - `signature` (string, required): Base64-encoded ASN.1 DER P-256 signature.
  - `file` (binary, required): JPEG or PNG image file.

- **Canonical Envelope Format**:
```json
{
  "device_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "evidence_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "farm_id": "b1b11b11-1111-1111-1111-111111111111",
  "image_hash": "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
  "lifecycle_stage": "CROP_GROWTH",
  "metadata": {
    "capture_source": "CAMERA",
    "capture_timestamp": "2026-11-09T14:30:00Z",
    "gps_accuracy": 3.5,
    "latitude": 17.385044,
    "longitude": 78.486671
  },
  "schema_version": "1.0",
  "sequence_number": 1
}
```

- **Responses**:
  - **`201 Created`**: New evidence accepted and persisted:
    ```json
    {
      "status": "DURABLY_ACKED",
      "evidence_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "server_timestamp": "2026-11-09T14:34:00Z",
      "sequence_number": 1,
      "receipt_signature": "MEUCIQC..."
    }
    ```
  - **`200 OK`**: Idempotent duplicate re-submission (identical device ID, sequence number, and image hash). Returns durable receipt without duplicate processing.
  - **`409 Conflict`**: Sequence violation:
    - Replay attempt ($S \le S_{\text{last}}$ with different hash).
    - Sequence gap ($S > S_{\text{last}} + 1$).
  - **`400 Bad Request`**: Signature verification failure, image hash mismatch, or device revoked.

---

### 2.6 Reviewer Console Endpoints

#### `GET /api/v1/reviewer/queue`
Retrieves pending evidence flagged for human assessment by the AI engine.

- **Headers**: `Authorization: Bearer <reviewer_token>`
- **Response `200 OK`**:
```json
[
  {
    "evidence_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "farm_id": "b1b11b11-1111-1111-1111-111111111111",
    "lifecycle_stage": "CROP_GROWTH",
    "capture_timestamp": "2026-11-09T14:30:00Z",
    "flags": ["BLUR_WARNING", "OFFLINE_DELAY_14_DAYS"],
    "quality_card": {
      "blur_status": "WARNING",
      "blur_score": 62.4,
      "exposure_valid": true,
      "resolution": "1920x1080"
    },
    "crypto_badge": {
      "is_valid": true,
      "status_label": "VERIFIED_ECDSA"
    }
  }
]
```

#### `POST /api/v1/reviewer/decisions`
Submits an attributable human review decision.

- **Request Body**:
```json
{
  "evidence_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "reviewer_id": "rev-alice",
  "action": "REQUEST_RETAKE",
  "notes": "Image is slightly blurred; please retake steady photo under daylight"
}
```
- **Response `200 OK`**:
```json
{
  "decision_id": "d0e1f2a3-...",
  "evidence_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "action": "REQUEST_RETAKE",
  "new_state": "RETAKE_REQUESTED",
  "decided_at": "2026-11-09T14:40:00Z"
}
```

---

### 2.7 Privacy-Preserving Public Verification

#### `GET /api/v1/verify/{public_token}`
Public endpoint providing cryptographic Merkle proofs and checkpoint data. Guarantees zero leakage of farmer PII and exact GPS coordinates.

- **Response `200 OK`**:
```json
{
  "public_token": "e4d3c2b1a09876543210...",
  "provenance_status": "COMMITTED_TO_LEDGER",
  "crop_type": "Cotton",
  "lifecycle_stage": "CROP_GROWTH",
  "capture_date": "2026-11-09",
  "region_coarse": "Adilabad, Telangana",
  "image_sha256": "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
  "leaf_hash": "3f4a9b...",
  "merkle_root": "8c7d2e...",
  "inclusion_proof": [
    {"position": "right", "hash": "1a2b3c..."},
    {"position": "left", "hash": "4d5e6f..."}
  ],
  "checkpoint": {
    "checkpoint_id": "cp-20261109-001",
    "timestamp": "2026-11-09T15:00:00Z",
    "signer_id": "praman-trusted-authority-1",
    "signature": "MEQCIF..."
  }
}
```
- **Invariant**: The JSON payload is programmatically scanned to verify zero presence of PII keys (`farmer_name`, `phone_number`, etc.) and fine-grained GPS keys (`latitude`, `longitude`, `coordinates`, `polygon`).

