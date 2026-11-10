# TEST_READY.md — PRAMAN E2E Test Suite Publication

## Test Suite Status: READY & VERIFIED
- **Date**: 2026-11-09T18:42:00Z
- **Working Directory**: `c:\Users\bhara\Downloads\final`
- **Test Directory**: `tests_e2e/`
- **Total Tests Collected**: 293
- **Passed (Software/Emulated & Integrated)**: 289 (100.0% of executable tests)
- **Failed**: 0
- **Errors**: 0
- **Skipped (Physical Android Hardware without USB device)**: 4
- **Execution Time**: ~5.45 seconds (test execution)

---

## How to Run the Tests

### 1. Using the Unified CLI Test Runner
```bash
# Run all 4 tiers across all available tests (default)
python tests_e2e/test_runner.py

# Run specific tiers
python tests_e2e/test_runner.py --tier 1       # Tier 1 Feature Coverage (225 tests)
python tests_e2e/test_runner.py --tier 2       # Tier 2 Boundary Cases (35 tests)
python tests_e2e/test_runner.py --tier 3       # Tier 3 Pairwise Interactions (25 tests)
python tests_e2e/test_runner.py --tier 4       # Tier 4 Real-World & Hardware (8 tests)
python tests_e2e/test_runner.py --tier 1,2     # Combined tiers

# Run strictly by test categorization
python tests_e2e/test_runner.py --type unit          # 180 unit tests
python tests_e2e/test_runner.py --type integration   # 80 integration tests
python tests_e2e/test_runner.py --type e2e           # 33 end-to-end tests

# Run strictly by device execution mode
python tests_e2e/test_runner.py --device mock        # 289 software/mock tests (100% pass)
python tests_e2e/test_runner.py --device physical    # 4 physical Android hardware tests

# Run with verbose output and save machine-readable JSON report
python tests_e2e/test_runner.py --verbose --report test_report_full.json
```

### 2. Using Pytest Directly
```bash
# Full test suite execution
pytest tests_e2e/ -v

# Individual tier executions
pytest tests_e2e/tier1_features/ -v
pytest tests_e2e/tier2_boundaries/ -v
pytest tests_e2e/tier3_interactions/ -v
pytest tests_e2e/tier4_real_world/ -v

# Filter by custom pytest markers
pytest tests_e2e/ -m unit -q
pytest tests_e2e/ -m integration -q
pytest tests_e2e/ -m e2e -q
pytest tests_e2e/ -m "not physical_device" -q
```

---

## Test Coverage Breakdown

### Execution Summary Table

| Category | Filter Option | Collected | Passed | Failed | Skipped | Pass Rate (%) |
|---|---|---|---|---|---|---|
| **Tier 1: Feature Coverage** | `--tier 1` | 225 | 225 | 0 | 0 | 100.0% |
| **Tier 2: Boundary Cases** | `--tier 2` | 35 | 35 | 0 | 0 | 100.0% |
| **Tier 3: Interactions** | `--tier 3` | 25 | 25 | 0 | 0 | 100.0% |
| **Tier 4: Real-World Scenarios** | `--tier 4` | 8 | 4 | 0 | 4 | 100.0%* |
| **Unit Tests** | `--type unit` | 180 | 180 | 0 | 0 | 100.0% |
| **Integration Tests** | `--type integration` | 80 | 80 | 0 | 0 | 100.0% |
| **End-to-End Tests** | `--type e2e` | 33 | 29 | 0 | 4 | 100.0%* |
| **Mock / Software Emulation** | `--device mock` | 289 | 289 | 0 | 0 | 100.0% |
| **Physical Android Hardware** | `--device physical`| 4 | 0 | 0 | 4 | N/A (Skipped)** |
| **Total Test Suite** | `--tier all` | **293** | **289** | **0** | **4** | **100.0%*** |

*\* Pass rate calculated over executable tests.*  
*\*\* Skipped honestly per project rule: "Do not count mocked tests as physical-device tests. Do not claim complete physical validation if no physical Android device was tested."*

---

## 4-Tier Test Coverage Details

### Tier 1: Feature Coverage (F-01 to F-45) — 225 Tests
Every feature from `PROJECT.md § Feature Inventory` has $\ge 5$ dedicated, isolated test cases executing against genuine platform modules:
- **Shared Cryptography (F-01 to F-07)**:
  - F-01: RFC 8785 JSON Canonicalization Scheme (JCS) (5 tests against `crypto.rfc8785`)
  - F-02: P-256 ECDSA Key & Signature Engine with low-$s$ (5 tests against `crypto.ecdsa_p256`)
  - F-03: Evidence Envelope Schema & Serialization (5 tests against `crypto.envelope`)
  - F-04: Domain-Separated Merkle Tree Builder (5 tests against `crypto.merkle.MerkleTree`)
  - F-05: Odd-Node Promotion Algorithm (CVE-2012-2459) (5 tests against `crypto.merkle.MerkleTree`)
  - F-06: Merkle Inclusion Proof Generation (5 tests against `crypto.merkle.MerkleTree.get_proof`)
  - F-07: Merkle Inclusion Proof Verification (5 tests against `crypto.merkle.verify_merkle_proof`)
- **Backend API Platform (F-08 to F-17)**:
  - F-08: PostgreSQL Database Schema & Migration (5 tests against `backend.app.models`)
  - F-09: Tamper-Evident Audit Logging (5 tests against `backend.app.services.audit_service`)
  - F-10: Farmer Identity & Auth Service (5 tests against `backend.app.schemas.farmer`)
  - F-11: Device Registration Service (5 tests against `backend.app.schemas.device`)
  - F-12: Farm Management Service (5 tests against `backend.app.services.spatial`)
  - F-13: Monotonic Sequence Number Enforcer ($S = S_{last} + 1$) (5 tests against `backend.app.services.sequence_service`)
  - F-14: Idempotent Ingestion Handler (5 tests against `backend.app.services.sequence_service`)
  - F-15: Evidence Ingestion REST API (5 tests against `backend.app.services.crypto_verifier`)
  - F-16: Local Content-Addressable File Storage (5 tests against `backend.app.storage.content_storage`)
  - F-17: Asynchronous AI Task Dispatcher (5 tests against `backend.app.services.ai_dispatcher`)
- **Local AI Intelligence Engine (F-18 to F-28)**:
  - F-18: Laplacian Blur Quality Detector (5 tests against `ai_engine.quality.compute_laplacian_variance`)
  - F-19: Exposure & Luminance Quality Checker (5 tests against `ai_engine.quality.compute_luminance_clipping`)
  - F-20: Image Resolution & Aspect Ratio Validator (5 tests against `ai_engine.quality.validate_image_dimensions`)
  - F-21: EXIF Metadata Consistency Inspector (5 tests against `ai_engine.quality.inspect_exif`)
  - F-22: Exact Hash Duplicate Detection (5 tests against `ai_engine.hashing.compute_sha256`)
  - F-23: Perceptual & Difference Hashing (pHash/dHash) (5 tests against `ai_engine.hashing`)
  - F-24: Crop Category Consistency Classifier (5 tests against `ai_engine.classifier.CropCategoryClassifier`)
  - F-25: 4-Tier Model Registry (5 tests against `ai_engine.registry.ModelRegistry`)
  - F-26: Unvalidated Manipulation Detector Governance (5 tests against `ai_engine.unvalidated`)
  - F-27: Explainable Structured AI Output Schema (5 tests against `ai_engine.evaluator.AIEvaluator`)
  - F-28: Never-Autonomous-Reject Rule Enforcer (5 tests against `ai_engine.evaluator.AIEvaluator`)
- **Farmer Android Application (F-29 to F-39)**:
  - F-29: Multilingual Onboarding UI (te/hi/en) (5 tests against `mobile/src/i18n/catalogs.ts`)
  - F-30: Farmer Registration & Login Screens (5 tests against `backend.app.schemas.farmer`)
  - F-31: WGS84 GPS Coordinate Capture (5 tests against `backend.app.services.spatial.is_valid_wgs84`)
  - F-32: Farm Boundary Polygon Capture & Validator (5 tests against `backend.app.services.spatial.validate_farm_polygon`)
  - F-33: Camera vs File-Upload Evidence Capture (5 tests against `crypto.envelope.VALID_CAPTURE_SOURCES`)
  - F-34: Farm Lifecycle Stage Categorization (5 tests against `crypto.envelope.VALID_LIFECYCLE_STAGES`)
  - F-35: On-Device P-256 Keystore Signing (5 tests against simulated Keystore using `crypto.ecdsa_p256`)
  - F-36: Persistent Offline Storage Queue (5 tests against Android `EvidenceDbHelper` SQLite schema)
  - F-37: Offline Sync State Machine & Protocol (5 tests against `mobile/src/storage/offlineQueue.ts`)
  - F-38: Offline Delay Legitimacy Handler (5 tests against `backend.app.services.delay_evaluator`)
  - F-39: Farmer Review Decision Notifications (5 tests)
- **Reviewer Console & Public Verification (F-40 to F-45)**:
  - F-40: Authenticated Reviewer Web Console (5 tests against `backend.app.api.v1.reviewer`)
  - F-41: Cryptographic & AI Signal Visualizer (5 tests)
  - F-42: Attributable Review Decision Engine (5 tests against `backend.app.api.v1.reviewer`)
  - F-43: Merkle Ledger Batching & Anchor Engine (5 tests against `crypto.merkle` and `backend.app.services.receipt_signer`)
  - F-44: Unguessable Public Verification Token (256-bit) (5 tests against `backend.app.models.public_token`)
  - F-45: Privacy-Preserving Public Web Verification (5 tests against `backend.app.api.v1.verify`)

### Tier 2: Boundary & Corner Cases — 35 Tests
- `test_b01_crypto_boundaries.py`: Empty payloads, float precision in RFC 8785, ASCII control character escapes, zero-byte payloads, 1000-key nested objects (5 tests).
- `test_b02_merkle_boundaries.py`: 17-leaf prime odd promotion, 256-leaf tree, identical leaves, 1-byte leaves, empty proofs (5 tests).
- `test_b03_spatial_boundaries.py`: Exact poles ($\pm 90.0^\circ$), anti-meridian ($\pm 180.0^\circ$), 3-vertex triangle parcel, degenerate collinear points, 7-decimal place coordinates (5 tests).
- `test_b04_image_boundaries.py`: 100% pitch black image, 100% white blown image, exact 800x600 resolution boundary, square (1:1) aspect ratio, 1x1 pixel image (5 tests).
- `test_b05_sequence_boundaries.py`: Sequence 0 rejection, negative sequence values, high 32-bit integer limits, multi-device interleaved sequence progression, identical retry (5 tests).
- `test_b06_offline_boundaries.py`: 60-day extreme delay, client-server clock skew (3 hours), 50-item burst queue sync, sync resumption after mid-batch drop, future capture timestamps (5 tests).
- `test_b07_review_verify_boundaries.py`: Reviewer notes length boundary (4 vs 5 chars), tampered Merkle sibling hashes, inverted sibling positions, revoked device key rejection, invalid checkpoint root (5 tests).

### Tier 3: Cross-Feature Interactions — 25 Tests
- `test_i01_camera_offline_sync.py`: CAMERA/UPLOAD capture $\times$ offline SQLite queue $\times$ durable server ACK (5 tests).
- `test_i02_ai_flags_reviewer_flow.py`: AI quality flag $\times$ reviewer console cards $\times$ attributable retake request $\times$ mobile notification (5 tests).
- `test_i03_review_merkle_batching.py`: Reviewer approval $\times$ Merkle batching engine $\times$ local ledger anchor record (5 tests).
- `test_i04_duplicate_sequence_rejection.py`: Sequence replay attack $\times$ sequence enforcer 409 Conflict $\times$ immutable audit log (5 tests).
- `test_i05_public_verify_checkpoint_sync.py`: 256-bit public token $\times$ WebCrypto Merkle proof recomputation $\times$ trusted checkpoint authority $\times$ zero PII/GPS (5 tests).

### Tier 4: Real-World Application Workloads & Hardware — 8 Tests
- `test_rw01_full_telugu_farmer_lifecycle.py`: Complete Telugu farmer lifecycle from Adilabad onboarding, cotton parcel registration, 5-stage offline capture, durable sync, AI scoring, reviewer approval, Merkle ledger anchor, and consumer QR verification.
- `test_rw02_blurry_retake_workflow.py`: Evening blurry photo flagged by AI, reviewer requests retake, farmer notified in Telugu, captures sharp morning photo, resubmits, approved, and batched into ledger anchor.
- `test_rw03_offline_delayed_monsoon_sync.py`: 14-day rural monsoon power/cellular outage, 8 offline queued items, day 15 batch sync, monotonic sequence validation, and legitimate delay verification without fraud flags.
- `test_rw04_multi_device_farm_audit.py`: Multi-device concurrent farm capture (phone + tablet) with independent sequence counters, consolidated into an immutable audit trail for inspection.
- `test_physical_device_hardware.py`: Real physical Android handset validation via ADB (ADB connectivity, camera hardware sensors, hardware Keystore backing, app private storage writable).

---

## Infrastructure Assets Maintained
- `pytest.ini` (project root)
- `TEST_INFRA.md` (project root)
- `TEST_READY.md` (project root)
- `test_report_full.json` (project root)
- `tests_e2e/conftest.py`
- `tests_e2e/test_runner.py`
- `tests_e2e/fixtures/` (`crypto_fixtures.py`, `image_generator.py`, `envelope_fixtures.py`, `spatial_fixtures.py`)
- `tests_e2e/tier1_features/` (45 test modules)
- `tests_e2e/tier2_boundaries/` (7 test modules)
- `tests_e2e/tier3_interactions/` (5 test modules)
- `tests_e2e/tier4_real_world/` (5 test modules including physical device hardware suite)
