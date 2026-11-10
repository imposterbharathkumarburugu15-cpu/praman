# Project: PRAMAN Complete Implementation Recovery

## Architecture
PRAMAN is a locally executable, farmer-first evidence provenance platform built across five core subsystems:
1. **Mobile Subsystem (`mobile/`)**: Native Android application with robust hardware Keystore integration, camera/picker media pipelines, crash-resilient persistent queue, and a commercial-grade multilingual farmer UI.
2. **Backend Subsystem (`backend/app/`)**: FastAPI application backed by PostgreSQL, managing farmer identity, device enrollment, spatial farm validation, sharded CAS image storage, reviewer decision workflows, and public verification.
3. **Cryptographic Pipeline (`crypto/`, `backend/app/services/`)**: RFC 8785 JSON canonicalization, NIST P-256 ECDSA signatures with strict low-$s$ anti-malleability, monotonic sequence enforcement, domain-separated Merkle batch trees, and signed checkpoint authority publication.
4. **Local AI & CV Subsystem (`ai_engine/`)**: Fully offline computer vision and machine learning engine executing deterministic quality analysis (blur, exposure, EXIF), duplicate detection (SHA-256, 64-bit DCT pHash/dHash), forensic tamper detection (ELA, noise residuals), and local PyTorch crop classification with verifiable weights.
5. **E2E Testing & Security Subsystem (`tests_e2e/`)**: Independent opaque-box test harness spanning Tiers 1–4, coupled with Tier 5 adversarial stress testing (Red Team).

```
                      [ Android Mobile Client ]
                     /                         \
         (Capture / Pick)                   (Offline SQLite)
                 │                                 │
           [ Android Keystore ]              [ Sync Engine ]
         (P-256 RFC 8785 Sign)                     │
                 │                                 │
                 └───────────────┬─────────────────┘
                                 │ HTTP POST multipart/form-data
                                 ▼
                      [ FastAPI Backend API ]
                     /           │           \
        (Identity / Farms)  (CAS Storage)  (PostgreSQL DB)
                                 │
                     [ Async AI Dispatcher ]
                                 │
                     [ Local AI & CV Engine ]
                    (Blur, pHash, ELA, PyTorch)
                                 │
                     [ Reviewer Decisions ]
                                 │
                     [ Merkle Batch Engine ]
                                 │
               [ Signed Checkpoint Authority & Public Verify ]
```

---

## Feature Inventory

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Android Camera Capture | Launch native camera, capture real photo, preserve raw image bytes and file path on disk without OOM | M1 | Survey / Spec Agent A |
| 2 | Android Gallery / Document Picker | Modern photo picker (API 33+) / document picker (API 24-32) retaining raw image bytes in app storage | M1 | Survey / Spec Agent A |
| 3 | Android Permissions & Lifecycle | Manifest declarations (`READ_MEDIA_IMAGES`, `READ_MEDIA_VISUAL_USER_SELECTED`), queries tag, and `onRequestPermissionsResult` | M1 | Survey / Spec Agent A |
| 4 | Persistent Offline Queue | Native persistent SQLite/Room storage surviving app restart, task killer, and device reboot | M1 | Survey / Spec Agent A |
| 5 | Real Network Sync Engine | Real multipart HTTP upload to backend with retry backoff, replacing fake `setTimeout` and dummy bytes | M1 | Survey / Spec Agent A |
| 6 | Commercial Farmer UI (12 Screens) | Complete redesign with Forest Green/Emerald palette, clean typography, large touch targets, real states | M1 | Survey / Spec Agent B |
| 7 | Multilingual Localization | Full UI parity across Telugu (`te`), Hindi (`hi`), and English (`en`) | M1 | Survey / Spec Agent B |
| 8 | Developer Jargon Removal | Hide raw SHA-256, WGS84 coordinates, EPSG:4326, and SQLite internals behind clean farmer UX; optional audit sheet | M1 | Survey / Spec Agent B |
| 9 | Demo Data Clean Sweep | Eliminate all hardcoded farmer names, phones, pins, fake GPS jitter, and mock signatures | M1 | Survey / Spec Agent B |
| 10 | Keystore P-256 Key Binding | Native Keystore key generation, security level probe (StrongBox/TEE/Software), and error handling | M1 | Survey / Spec Agent A/F |
| 11 | Client RFC 8785 Canonicalization | Emit strict canonical envelope matching backend schema and sign canonical bytes | M1 | Survey / Spec Agent A/F |
| 12 | Backend PostgreSQL Connectivity | Verified connection, schema migrations, and clean empty production state | M2 | Survey / Spec Agent C |
| 13 | Farmer Registration & Auth | Validate phone format, handle duplicate registration, issue JWT session tokens, audit logging | M2 | Survey / Spec Agent C |
| 14 | Device Enrollment & Key Validation | Enroll NIST P-256 public keys (SPKI PEM/DER/raw point), sequence tracking, revocation | M2 | Survey / Spec Agent C |
| 15 | Farm Boundary Spatial Validation | WGS84 coordinate bounds, self-intersection check, area calculation | M2 | Survey / Spec Agent C |
| 16 | Evidence Ingestion & CAS Storage | Multipart ingest, hash verification, atomic bit-for-bit CAS storage, row-level concurrency lock | M2 | Survey / Spec Agent C |
| 17 | Monotonic Sequence & Replay Protection | Strict sequence order, rejection of gaps and stale replays | M2 | Survey / Spec Agent C |
| 18 | Idempotent Sync Retries | Re-transmissions of identical sequence & hash return original receipt with 200 OK | M2 | Survey / Spec Agent C |
| 19 | Server Receipt Signing Key Persistence | Load server P-256 key from file/env rather than generating ephemeral in-memory keys on startup | M2 | Survey / Spec Agent C |
| 20 | Reviewer Workflow API & Persistence | FastAPI endpoints (`/api/v1/reviewer/queue`, `/decision`) backed by DB model `ReviewDecision` | M2 | Survey / Spec Agent C |
| 21 | Public Verification Portal API | FastAPI endpoints (`/api/v1/verify/{token}`) returning privacy-sanitized payload and cryptographic proof | M2 | Survey / Spec Agent C |
| 22 | Local PyTorch Crop Classification | Genuine local PyTorch inference with evaluated model weights, replacing `predict_mock` 0.88 | M3 | Survey / Spec Agent D |
| 23 | Agricultural Dataset Provenance | Documented open-source dataset, licenses, stratified train/val/test splits, and confusion matrix | M3 | Survey / Spec Agent D |
| 24 | Deterministic Image Quality Analysis | Laplacian variance blur, luminance histogram exposure clipping, dimension/EXIF validation | M3 | Survey / Spec Agent E |
| 25 | Duplicate Image Detection | Bit-exact SHA-256 and 64-bit DCT pHash/dHash with Hamming distance against historical evidence | M3 | Survey / Spec Agent E |
| 26 | Image Manipulation Forensics | Error Level Analysis (ELA) and noise residual variance detecting splices and edits | M3 | Survey / Spec Agent E |
| 27 | Backend AI Dispatcher Integration | Rewire background worker to fetch raw CAS bytes, run AI evaluation, and persist assessment in DB | M3 | Survey / Spec Agent C/E |
| 28 | Merkle Batch Engine | Periodic/triggered aggregation of approved evidence into RFC 6962 domain-separated Merkle trees | M4 | Survey / Spec Agent F |
| 29 | Signed Checkpoint Authority | Replace mock string with genuine NIST P-256 authority signatures over canonical checkpoints | M4 | Survey / Spec Agent F |
| 30 | Independent Cryptographic Proofs | Merkle inclusion proof verification and end-to-end provenance validation | M4 | Survey / Spec Agent F |
| 31 | E2E Testing Suite (Tiers 1–4) | Opaque-box requirement-driven test suite with >=11*N + N/2 tests, publishing TEST_READY.md | Track 2 | Survey / Spec Agent G |
| 32 | Red-Team Adversarial Hardening (Tier 5) | Adversarial coverage against GPS spoofing, image replay, signature tampering, and key compromise | M5 | Survey / Spec Agent H |
| 33 | Implementation Audit Documentation | Comprehensive markdown reports documenting physical validation, models, datasets, and readiness | M5 | Survey / Spec Phase 4 |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Mobile Platform & Commercial Farmer UI | Android native camera/picker, permissions, SQLite queue, real sync, 12-screen commercial UI, i18n | none | DONE |
| M2 | Backend API, Reviewer & Verification Services | Reviewer API/DB, Public Verify API/DB, persisted receipt key, DB migrations for AI & Merkle | none | DONE |
| M3 | Local AI Engine & Computer Vision Pipeline | Local PyTorch crop model, weights registry, ELA forensics, AI dispatcher wiring, DB persistence | M2 | DONE |
| M4 | Cryptographic Merkle Batching & Checkpoint Authority | Merkle batch service, authority checkpoint signing, proof verification, mobile-backend crypto parity | M1, M2 | DONE |
| M5 | Final Milestone: E2E Integration & Adversarial Hardening | Phase 1: 100% E2E test pass across full workflow. Phase 2: Red-team adversarial hardening (Tier 5). | M1, M2, M3, M4, TEST_READY | DONE |

*(In parallel, the E2E Testing Track builds the comprehensive test suite and publishes `TEST_READY.md`.)*

---

## Interface Contracts

### 1. Mobile Client ↔ Backend Ingest (`POST /api/v1/evidence/ingest`)
- **Multipart parts**:
  - `envelope`: JSON string conforming strictly to `EvidenceEnvelopeSchema`:
    ```json
    {
      "device_id": "<uuid>",
      "evidence_id": "<uuid>",
      "farm_id": "<uuid>",
      "image_hash": "<64-char lowercase hex sha256 of raw image file>",
      "lifecycle_stage": "SOWING | INPUT_APPLICATION | CROP_GROWTH | HARVEST | STORAGE",
      "metadata": {
        "capture_source": "CAMERA | FILE_UPLOAD",
        "capture_timestamp": "ISO 8601 UTC timestamp",
        "gps_accuracy": 5.0,
        "latitude": 17.385044,
        "longitude": 78.486671
      },
      "schema_version": "1.0",
      "sequence_number": 1
    }
    ```
  - `signature`: Base64-encoded NIST P-256 signature over RFC 8785 canonical bytes of envelope (low-$s$ normalized).
  - `image`: Raw binary image bytes (JPEG or PNG).
- **Responses**:
  - `201 Created` on new ingest: returns receipt with server signature.
  - `200 OK` on idempotent retry of identical sequence + hash: returns original receipt.
  - `400 Bad Request` if hash mismatch, clock skew > 5 min, invalid signature, or schema failure.
  - `409 Conflict` on sequence gap or stale replay.

### 2. Backend ↔ AI Engine (`ai_engine.evaluator.AIEvaluator`)
- **Invocation**:
  ```python
  assessment = ai_evaluator.evaluate_evidence(
      evidence_id=str(evidence.id),
      image_bytes=raw_bytes,
      envelope=canonical_envelope_dict,
  )
  ```
- **Return Structure**:
  ```python
  {
      "evidence_id": str,
      "quality": {
          "blur": {"variance": float, "is_sharp": bool},
          "exposure": {"underexposed_pct": float, "overexposed_pct": float, "is_balanced": bool},
          "dimensions": {"width": int, "height": int, "valid": bool},
          "exif": {"present": bool, "timestamp_delta_sec": float, "valid": bool}
      },
      "dedup": {
          "sha256": str,
          "phash": str,
          "is_exact_duplicate": bool,
          "is_perceptual_duplicate": bool
      },
      "crop_classification": {
          "predicted_class": str,
          "confidence": float,
          "is_consistent": bool
      },
      "forensics": {
          "ela_variance": float,
          "noise_variance": float,
          "is_tamper_suspected": bool
      },
      "recommendation": "AUTO_APPROVE | PENDING_REVIEW"
  }
  ```

### 3. Reviewer API Contract (`/api/v1/reviewer/`)
- `GET /api/v1/reviewer/queue`: Returns list of evidence records with status `PENDING_REVIEW` including metadata, thumbnail/image URL, and AI assessment breakdown.
- `POST /api/v1/reviewer/decision`:
  - Request: `{"evidence_id": str, "decision": "APPROVE | REJECT | REQUEST_RETAKE", "notes": str}`
  - Updates evidence status to `APPROVED` or `REJECTED`, creates audit log entry, and transitions record to Merkle batch eligibility.

### 4. Merkle Batch & Checkpoint Authority Contract
- **Merkle Tree**: Leaves are domain-separated `SHA-256(0x00 || canonical_envelope_bytes)`. Odd nodes promoted directly without duplication.
- **Checkpoint Object**:
  ```json
  {
    "checkpoint_id": "cp-20261109-001",
    "batch_id": "<uuid>",
    "merkle_root": "<64-char hex>",
    "leaf_count": 42,
    "timestamp": "2026-11-09T18:30:00Z",
    "authority_id": "praman-root-authority-1",
    "signature": "<base64-encoded P-256 signature over RFC 8785 canonical bytes of checkpoint>"
  }
  ```

### 5. Public Verification Contract (`GET /api/v1/verify/{token}`)
- Returns privacy-preserving evidence payload:
  - Masked farmer ID / phone.
  - Coarse location (district/mandal level only, exact coordinates redacted).
  - Lifecycle stage, capture timestamp, and cryptographic status.
  - Merkle inclusion proof: array of sibling hashes and positions.
  - Authority checkpoint and authority signature.

---

## Code Layout

- `mobile/android/`: Android native project (Java/Kotlin, AndroidManifest, Keystore bridge, Camera/Picker native modules, SQLite persistent queue, network sync).
- `mobile/android/app/src/main/assets/`: Farmer-first commercial mobile web interface (clean Forest Green design, i18n Telugu/Hindi/English, no developer jargon).
- `backend/app/`: FastAPI application:
  - `api/v1/`: Endpoints (`farmers.py`, `devices.py`, `farms.py`, `evidence.py`, `reviewer.py`, `verify.py`, `audit.py`).
  - `models/`: SQLAlchemy models (`farmer.py`, `device.py`, `farm.py`, `evidence.py`, `ai_assessment.py`, `review_decision.py`, `merkle_batch.py`, `audit_log.py`).
  - `services/`: Business logic (`ai_dispatcher.py`, `receipt_signer.py`, `merkle_service.py`, `spatial.py`).
  - `storage/`: Content-Addressable Storage (`content_storage.py`).
- `ai_engine/`: Local ML & CV engine:
  - `weights/`: Checked-in local PyTorch model weights with SHA-256 validation.
  - `classifier.py`: Real local PyTorch crop inference engine.
  - `quality.py`: Deterministic Laplacian blur, luminance histogram, and EXIF analysis.
  - `hashing.py`: SHA-256 and 64-bit DCT pHash/dHash.
  - `forensics.py`: Error Level Analysis (ELA) and noise residual variance.
  - `registry.py`: Model provenance, architecture, dataset, and metric registry.
  - `evaluator.py`: Unified evaluation coordinator.
- `crypto/`: Cryptographic core:
  - `rfc8785.py`: JSON canonicalization scheme.
  - `ecdsa_p256.py`: NIST P-256 signing and verification with low-$s$ enforcement.
  - `envelope.py`: Evidence envelope canonical binding.
  - `merkle.py`: RFC 6962 domain-separated Merkle trees with odd-node promotion.
- `tests_e2e/`: Opaque-box E2E test suite (Tiers 1–4) and test runner.
