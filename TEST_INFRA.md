# TEST_INFRA.md — PRAMAN End-to-End Test Infrastructure

## 1. Overview & Architectural Philosophy
The PRAMAN E2E test suite (`tests_e2e/`) is an opaque-box, requirement-driven testing infrastructure designed to independently verify the complete platform lifecycle across mobile, backend, cryptography, local AI, reviewer workflows, and public verification.

### Core Testing Principles
1. **Opaque-Box & Interface-Driven**: Tests are designed strictly against public interface contracts (PROJECT.md § Interface Contracts), canonical specifications (RFC 8785 JCS, NIST P-256 ECDSA, WGS84, domain-separated RFC 6962 Merkle trees), and documented platform invariants. Tests do not inspect or depend on arbitrary private implementation details.
2. **Deterministic Test Oracles & Real Modules**: Rather than relying on self-referential mock algorithms, tests execute directly against the genuine platform modules (`crypto`, `backend.app`, `ai_engine`) or assert against mathematically authoritative reference vectors.
3. **Strict Categorization & Device Separation**: Unit tests, integration tests, end-to-end tests, mock/software tests, and physical Android hardware tests are strictly separated via pytest markers (`@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.mock_device`, `@pytest.mark.physical_device`, `@pytest.mark.security`). Mocked software tests are never counted as physical device tests.
4. **Synthetic Image Generation**: Zero external binary assets. Fixtures generate real JPEG/PNG files in memory using Pillow and OpenCV to test sharp images, Laplacian blur, underexposure, overexposure, resolution boundaries, and perceptual hashing (pHash/dHash).
5. **Zero Flakiness & Full Isolation**: Every test creates its own isolated state, in-memory SQLite database, or ephemeral temporary directory, ensuring zero inter-test dependency.
6. **Local Execution**: Validates local AI requirements (Laplacian blur, luminance histograms, exact SHA-256, 64-bit DCT pHash/dHash, MobileNetV3 consistency) using CPU-only local execution without external network calls.

---

## 2. Test Architecture: 4-Tier Test Pyramid

| Tier | Category | Scope | Test Count | Purpose |
|------|----------|-------|------------|---------|
| **Tier 1** | **Feature Coverage** | F-01 through F-45 | 225 tests (5 per feature) | Direct verification of the core specification of every single feature in `PROJECT.md § Feature Inventory`. |
| **Tier 2** | **Boundary & Corner Cases** | Edge cases & limits | 35 tests (5 per domain) | Maximum payloads, unclosed polygons, empty strings, float precision in JCS, extreme coordinates, odd leaf count Merkle trees, clock skew. |
| **Tier 3** | **Cross-Feature Interactions** | Pairwise module contracts | 25 tests (5 per interaction area) | Camera vs upload $\times$ offline sync, AI flags $\times$ reviewer console, approved decisions $\times$ Merkle batches, sequence replay $\times$ idempotency. |
| **Tier 4** | **Real-World Application Scenarios** | Multi-actor user journeys & Hardware | 8 tests (4 workflows + 4 hardware specs) | Full life-cycle journeys: Telugu farmer onboarding, offline monsoon capture, AI blur detection with retake request, Merkle batch anchor, and zero-PII consumer QR verification, alongside physical device hardware validation. |

### Test Categorization Breakdown
- **Unit Tests (180 tests)**: Isolated functional validation of cryptographic primitives (RFC 8785, P-256 low-$s$, Merkle proofs), deterministic CV algorithms (Laplacian blur, luminance histogram, dimensions, pHash/dHash), and spatial geometry (WGS84, polygon validity, hectares calculation).
- **Integration Tests (80 tests)**: Subsystem integration covering database models (PostgreSQL/SQLAlchemy), audit trail hash chaining, device enrollment, sequence enforcer row locks, idempotent retry handling, multipart evidence ingestion, content-addressable storage, async task dispatch, reviewer console queues, and public token resolution.
- **End-to-End Tests (33 tests)**: Multi-actor workflows combining client capture, offline queueing, backend ingestion, local AI assessment, human reviewer decisions, Merkle batching, and public verification.
- **Device Separation**:
  - **Mock / Software Emulation (289 tests)**: Local execution verifying mobile Keystore signing, SQLite persistent queueing, and retry state machines in software.
  - **Physical Android Hardware (4 tests)**: Hardware-specific tests requiring a physical Android device connected via ADB (`test_physical_device_hardware.py`), skipped automatically when physical hardware is not detected.

---

## 3. Directory Layout

```
tests_e2e/
├── __init__.py
├── conftest.py                     # Shared pytest fixtures, crypto oracles, mock device keys, dynamic markers
├── test_runner.py                  # Standalone CLI runner with exit codes, filtering, and JSON reporting
├── fixtures/                       # Synthetic test data generators & authoritative adapters
│   ├── __init__.py
│   ├── crypto_fixtures.py          # Real RFC 8785, P-256 ECDSA, and Merkle tree adapters
│   ├── image_generator.py          # Synthetic JPEG/PNG generator (sharp, blurry, dark, blown, duplicates)
│   ├── envelope_fixtures.py        # Canonical JSON evidence envelopes & mutation helpers
│   └── spatial_fixtures.py         # WGS84 GPS points and boundary polygon generators
├── tier1_features/                 # Feature Coverage (F-01 to F-45) — 225 tests
│   ├── test_f01_rfc8785.py         # RFC 8785 JCS canonicalization
│   ├── test_f02_ecdsa.py           # P-256 ECDSA key & signature engine
│   ├── test_f03_envelope.py        # Canonical evidence envelope schema
│   ├── test_f04_merkle_builder.py  # Domain-separated Merkle tree builder
│   ├── test_f05_odd_node_promotion.py # Odd-node promotion (CVE-2012-2459 prevention)
│   ├── test_f06_proof_generation.py# Merkle inclusion proof generator
│   ├── test_f07_proof_verification.py # Merkle inclusion proof verifier
│   ├── test_f08_db_schema.py       # PostgreSQL schema & SQLAlchemy models
│   ├── test_f09_audit_logging.py   # Tamper-evident append-only audit trail
│   ├── test_f10_farmer_identity.py # Farmer registration & auth
│   ├── test_f11_device_registration.py # Device enrollment & P-256 binding
│   ├── test_f12_farm_management.py # Farm creation & spatial parcels
│   ├── test_f13_sequence_enforcement.py # Monotonic sequence enforcer (S = S_last + 1)
│   ├── test_f14_idempotent_ingestion.py # Idempotent submission retry handler
│   ├── test_f15_evidence_ingest_api.py  # Multipart evidence upload API
│   ├── test_f16_content_storage.py # Content-addressable SHA-256 storage
│   ├── test_f17_async_ai_dispatch.py   # Asynchronous AI task queue
│   ├── test_f18_laplacian_blur.py  # Laplacian variance blur detector
│   ├── test_f19_exposure_luminance.py  # Luminance histogram under/over exposure
│   ├── test_f20_resolution_aspect.py   # Resolution & aspect ratio checks
│   ├── test_f21_exif_consistency.py    # EXIF metadata consistency inspector
│   ├── test_f22_exact_hash_dedup.py    # Exact SHA-256 duplicate detection
│   ├── test_f23_perceptual_hash.py # 64-bit DCT pHash & gradient dHash
│   ├── test_f24_crop_category.py   # MobileNetV3 crop stage consistency
│   ├── test_f25_model_registry.py  # 4-tier model registry governance
│   ├── test_f26_unvalidated_detector.py# Unvalidated manipulation heuristic guards
│   ├── test_f27_structured_ai_schema.py# Explainable structured assessment schema
│   ├── test_f28_never_reject_rule.py   # Invariant: AI never autonomously rejects
│   ├── test_f29_multilingual_onboarding.py # Telugu, Hindi, English catalogs
│   ├── test_f30_farmer_auth_screens.py # Mobile farmer registration/login UI logic
│   ├── test_f31_gps_coordinate_capture.py # WGS84 GPS acquisition & accuracy bounds
│   ├── test_f32_boundary_polygon.py    # Boundary polygon closure & non-self-intersection
│   ├── test_f33_camera_vs_upload.py    # CAMERA vs FILE_UPLOAD capture checks
│   ├── test_f34_lifecycle_stage.py # SOWING, INPUT_APPLICATION, CROP_GROWTH, HARVEST, STORAGE
│   ├── test_f35_keystore_signing.py    # Android Keystore P-256 simulation
│   ├── test_f36_offline_queue.py   # Local SQLite persistent offline queue
│   ├── test_f37_sync_state_machine.py  # QUEUED -> SYNCING -> DURABLY_ACKED -> FAILED
│   ├── test_f38_delay_legitimacy.py    # Offline delayed upload legitimacy rule
│   ├── test_f39_farmer_notifications.py# Reviewer decision notifications in mobile
│   ├── test_f40_reviewer_console.py    # Reviewer dashboard authentication & queues
│   ├── test_f41_signal_visualizer.py   # Crypto & AI signal visualization cards
│   ├── test_f42_review_decision_engine.py # APPROVE, REJECT, REQUEST_RETAKE engine
│   ├── test_f43_merkle_batch_anchor.py # Periodic Merkle batching & ledger anchors
│   ├── test_f44_public_token.py        # 256-bit unguessable public tokens
│   └── test_f45_privacy_public_verify.py# Zero PII/GPS public verification web page
├── tier2_boundaries/               # Boundary & Corner Cases — 35 tests
│   ├── test_b01_crypto_boundaries.py   # Empty payloads, Unicode normalization, DER encodings
│   ├── test_b02_merkle_boundaries.py   # 1 leaf, 2 leaves, odd leaves (3, 5, 17), 1024 leaves
│   ├── test_b03_spatial_boundaries.py  # Poles, anti-meridian, triangle, degenerate polygons
│   ├── test_b04_image_boundaries.py    # 1x1 pixels, extreme aspect ratios, all-black, all-white
│   ├── test_b05_sequence_boundaries.py # Sequence 0, 1, 2^31-1, 2^63-1, gaps, duplicates
│   ├── test_b06_offline_boundaries.py  # 30-day offline delay, power cut during sync, partial uploads
│   └── test_b07_review_verify_boundaries.py # Tampered proofs, expired tokens, revoked device keys
├── tier3_interactions/             # Cross-Feature Interactions — 25 tests
│   ├── test_i01_camera_offline_sync.py # Camera capture + offline queue + durable ACK
│   ├── test_i02_ai_flags_reviewer_flow.py # Blurry image + AI assessment + reviewer retake
│   ├── test_i03_review_merkle_batching.py # Review approval + Merkle batch + ledger anchor
│   ├── test_i04_duplicate_sequence_rejection.py # Replay attack + sequence enforcer + audit log
│   └── test_i05_public_verify_checkpoint_sync.py# Public token + client-side proof recompute + zero PII
└── tier4_real_world/               # Real-World Application Workloads & Hardware — 8 tests
    ├── test_rw01_full_telugu_farmer_lifecycle.py # Farmer in Adilabad registers cotton farm in Telugu, captures 5 lifecycle photos, commits to ledger
    ├── test_rw02_blurry_retake_workflow.py # Low-light blurry photo flagged by AI, reviewer requests retake, farmer resubmits, proof verified
    ├── test_rw03_offline_delayed_monsoon_sync.py # 14-day offline monsoon capture queue, restores connectivity, verifies no false fraud flags
    ├── test_rw04_multi_device_farm_audit.py # Multi-device concurrent farm capture with sequence isolation and audit verification
    └── test_physical_device_hardware.py # Real physical Android device tests via ADB
```

---

## 4. Test Runner CLI Specification (`tests_e2e/test_runner.py`)

The test runner provides a unified CLI for running any subset of tiers, filtering by test type or device execution mode, with structured JSON reports and terminal output.

### Usage Examples
```bash
# Run all 4 tiers across all available tests (default)
python tests_e2e/test_runner.py

# Run specific tier(s)
python tests_e2e/test_runner.py --tier 1
python tests_e2e/test_runner.py --tier 2
python tests_e2e/test_runner.py --tier 3
python tests_e2e/test_runner.py --tier 4
python tests_e2e/test_runner.py --tier 1,2

# Run strictly by test categorization
python tests_e2e/test_runner.py --type unit
python tests_e2e/test_runner.py --type integration
python tests_e2e/test_runner.py --type e2e

# Run strictly by device mode
python tests_e2e/test_runner.py --device mock       # Fast software-only execution (289 tests)
python tests_e2e/test_runner.py --device physical   # Physical hardware only (skips if no adb device)

# Save machine-readable JSON execution report
python tests_e2e/test_runner.py --report test_report.json

# Run via standard pytest directly
pytest tests_e2e/ -v
pytest tests_e2e/ -m unit -q
pytest tests_e2e/ -m integration -q
pytest tests_e2e/ -m e2e -q
pytest tests_e2e/ -m "not physical_device" -q
```

### Exit Codes
- `0`: All executed tests passed successfully (or optional physical hardware tests safely skipped).
- `1`: One or more tests failed or errored.
- `2`: CLI argument error or test execution interrupted.

---

## 5. Synthetic Fixture Architecture

All test fixtures are located in `tests_e2e/fixtures/` and provided via `tests_e2e/conftest.py`:
- `crypto_fixtures`: Binds directly to `crypto.rfc8785`, `crypto.ecdsa_p256`, and `crypto.merkle` without duplicate algorithm logic.
- `image_generator`: Generates genuine in-memory images and uses `ai_engine.quality` and `ai_engine.hashing` for sharpness, exposure, and pHash evaluations.
- `envelope_fixtures`: Binds directly to `crypto.envelope.EvidenceEnvelope` and `EvidenceMetadata`.
- `spatial_fixtures`: Binds directly to `backend.app.services.spatial` for polygon closure, WGS84 coordinates, and hectare area formulas.

---

## 6. Authoritative Expected Output Derivation

| Category | Authoritative Source | Derivation Method |
|---|---|---|
| RFC 8785 JCS | RFC 8785 §3 / `crypto.rfc8785` | Key UTF-16 code unit ordering, ECMAScript number format, UTF-8 byte comparison |
| P-256 ECDSA | SEC 1 / RFC 6979 / `crypto.ecdsa_p256` | SECP256R1 curve order $n$, low-$s$ normalization ($s \le n/2$), ASN.1 DER verification |
| Merkle Tree | RFC 6962 / `crypto.merkle` | $H_{leaf} = \text{SHA256}(0\text{x}00 \parallel \text{leaf})$, $H_{node} = \text{SHA256}(0\text{x}01 \parallel L \parallel R)$, odd-node promotion |
| Spatial Validation | EPSG:4326 WGS84 / `backend.app.services.spatial` | CCW segment intersection orientation, Shoelace formula for polygonal area |
| Blur & Exposure | OpenCV / NumPy / `ai_engine.quality` | 2D Laplacian discrete filter variance $\sigma^2 > 100$ (sharp) vs $< 50$ (blurry); luminance histogram clipping $< 35\%$ |
| Perceptual Hashing | 64-bit DCT / `ai_engine.hashing` | $32 \times 32$ resize, 2D DCT low frequency $8 \times 8$ matrix median thresholding, Hamming distance $\le 10$ |
| Monotonic Sequence | PRAMAN Contract R2 / `backend.app.services.sequence_service` | $S = S_{last} + 1 \implies 201$, $S \le S_{last} \implies 409$, idempotent matching hash $\implies 200$ |
| Legitimacy Rule | PRAMAN Invariant / `backend.app.services.delay_evaluator` | Delayed upload with authentic sequence + signature is classified as `LEGITIMATE_OFFLINE_DELAY`, never fraud |
