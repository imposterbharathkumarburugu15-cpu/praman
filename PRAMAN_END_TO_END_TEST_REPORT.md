# PRAMAN End-to-End Test & Quality Assurance Report

**Document ID**: PRAMAN-E2E-M5-001  
**Platform Version**: PRAMAN v1.0.0-rc1  
**Evaluation Date**: November 10, 2026  
**Auditor / Specialist**: QA & Test Automation Specialist (Agent G)  
**Execution Environment**: Python 3.13.9, Pytest 8.4.2, Windows 11 / Local CPU  
**Governance Standard**: Non-Negotiable Rules 6, 7, 8, 12 — "Never claim a feature works without an execution test. Do not count mocked tests as physical-device tests. Do not claim complete physical validation if no physical Android device was tested."

---

## 1. Executive Summary & Testing Philosophy

The PRAMAN End-to-End Test Suite (`tests_e2e/`) provides opaque-box, contract-driven verification across the entire platform: Android mobile client, FastAPI backend, local AI and computer vision engine, cryptographic Merkle batching, reviewer console, and public verification portal.

### Key Architectural Standards
1. **Zero Self-Referential Mocks**: Tests execute directly against genuine production modules (`crypto`, `backend.app`, `ai_engine`) rather than duplicate test oracles.
2. **Deterministic Test Oracles**: Boundary assertions are derived mathematically from authoritative specifications (RFC 8785, SEC 1 / RFC 6979, RFC 6962, EPSG:4326 WGS84).
3. **Strict Categorization**: Every test is categorized via Pytest markers (`unit`, `integration`, `e2e`, `mock_device`, `physical_device`, `security`).
4. **Transparent Hardware Accounting**: Physical hardware tests requiring an attached Android device via ADB are segregated and truthfully reported as skipped when no physical device is detected.

---

## 2. Test Execution Summary

### 2.1 Repository-Wide Test Totals

| Subsystem / Test Suite | Path | Total Tests | Passed | Failed | Skipped | Pass Rate (%) |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **Cryptographic Core** | `crypto/tests/` | 143 | 143 | 0 | 0 | 100.0% |
| **Backend API Platform** | `backend/tests/` | 50 | 50 | 0 | 0 | 100.0% |
| **Local AI & Forensics** | `ai_engine/tests/` | 15 | 15 | 0 | 0 | 100.0% |
| **Android Unit Tests** | `mobile/` (JUnit) | 2 | 2 | 0 | 0 | 100.0% |
| **E2E Core (Tiers 1–4)** | `tests_e2e/` (Tiers 1–4) | 293 | 289 | 0 | 4* | 100.0%** |
| **Total Executable Tests** | **Repository Wide** | **503** | **499** | **0** | **4** | **100.0%** |

*\* The 4 skipped tests represent physical Android device hardware tests skipped due to lack of a connected physical USB handset.*  
*\*\* Pass rate is calculated over all executable tests.*

---

## 3. Comprehensive E2E Test Suite Breakdown (`tests_e2e/`)

### 3.1 Execution Matrix by Tier

```
========================================================================
 PRAMAN E2E TEST RUNNER
 Targets:     tests_e2e/tier1_features, tests_e2e/tier2_boundaries, 
              tests_e2e/tier3_interactions, tests_e2e/tier4_real_world
 Test Type:   all
 Device Mode: all
========================================================================
289 passed, 4 skipped in 4.50s
```

| Tier | Category | Scope | Collected | Passed | Failed | Skipped | Pass Rate (%) |
|---|---|---|:---:|:---:|:---:|:---:|:---:|
| **Tier 1** | **Feature Coverage** | F-01 through F-45 | 225 | 225 | 0 | 0 | 100.0% |
| **Tier 2** | **Boundary Cases** | Edge inputs & limits | 35 | 35 | 0 | 0 | 100.0% |
| **Tier 3** | **Interactions** | Cross-module pairwise | 25 | 25 | 0 | 0 | 100.0% |
| **Tier 4** | **Real-World & Hardware** | Full workflows & Device | 8 | 4 | 0 | 4 | 100.0%* |
| **Total (Tiers 1–4)** | | | **293** | **289** | **0** | **4** | **100.0%*** |

*Optional Red-Team Extension*: Running with Tier 5 (`tests_e2e/tier5_adversarial`) collects **333 tests**, passing **329** with **4 skipped** in 7.47s.

### 3.2 Breakdown by Test Type

| Test Type | Marker | Count | Passed | Failed | Skipped | Description |
|---|---|:---:|:---:|:---:|:---:|---|
| **Unit Tests** | `@pytest.mark.unit` | 180 | 180 | 0 | 0 | Pure algorithmic validation of RFC 8785, P-256 low-$s$, Merkle proofs, Laplacian blur, pHash/dHash, and spatial geometry. |
| **Integration Tests** | `@pytest.mark.integration` | 80 | 80 | 0 | 0 | Subsystem interaction across SQLAlchemy models, sequence locks, CAS storage, AI dispatch, and reviewer queues. |
| **End-to-End Tests** | `@pytest.mark.e2e` | 33 | 29 | 0 | 4 | Multi-stage user journeys combining capture, queueing, backend ingest, AI assessment, review, batching, and public verification. |

### 3.3 Breakdown by Device Execution Mode

| Device Mode | Marker | Collected | Passed | Failed | Skipped | Description |
|---|---|:---:|:---:|:---:|:---:|---|
| **Mock / Software** | `@pytest.mark.mock_device` | 289 | 289 | 0 | 0 | Local software emulation of Android Keystore P-256 signing, SQLite queueing, and retry state machines. |
| **Physical Hardware**| `@pytest.mark.physical_device`| 4 | 0 | 0 | 4 | Physical USB Android handset validation via ADB (gracefully skipped when no physical phone is connected). |

---

## 4. Detailed Tier-by-Tier Verification

### 4.1 Tier 1: Feature Coverage (F-01 to F-45) — 225 Tests
Every feature defined in `PROJECT.md § Feature Inventory` has $\ge 5$ dedicated, isolated test cases:

#### Cryptography & Integrity (F-01 to F-07) — 35 Tests
- **F-01 (RFC 8785 JCS)**: 5 tests verifying UTF-16 code unit key sorting, IEEE 754 number formatting, surrogate pairs, and whitespace elimination.
- **F-02 (P-256 ECDSA Engine)**: 5 tests verifying keypair generation, low-$s$ anti-malleability ($s \le n/2$), and DER/P1363 conversions.
- **F-03 (Evidence Envelope)**: 5 tests verifying canonical serialization, schema validation, and image hash binding.
- **F-04 (Merkle Tree Builder)**: 5 tests verifying domain separation prefixes ($0\text{x}00$ leaf, $0\text{x}01$ internal node) and root computation.
- **F-05 (Odd-Node Promotion)**: 5 tests verifying CVE-2012-2459 immunity across odd leaf counts.
- **F-06 (Proof Generation)**: 5 tests verifying compact $O(\log_2 N)$ sibling path generation.
- **F-07 (Proof Verification)**: 5 tests verifying mathematical proof evaluation against known Merkle roots.

#### Backend API Platform (F-08 to F-17) — 50 Tests
- **F-08 (Database Schema)**: 5 tests verifying PostgreSQL models, foreign keys, and status enum constraints.
- **F-09 (Audit Logging)**: 5 tests verifying tamper-evident append-only audit trail with cryptographic hash chaining.
- **F-10 (Farmer Identity)**: 5 tests verifying farmer registration, phone number deduplication, and auth tokens.
- **F-11 (Device Registration)**: 5 tests verifying device enrollment and P-256 public key binding.
- **F-12 (Farm Management)**: 5 tests verifying farm boundary polygons, centroid calculation, and hectare areas.
- **F-13 (Sequence Enforcer)**: 5 tests verifying strictly monotonic sequence numbers ($S = S_{\text{last}} + 1$) and row-level locks.
- **F-14 (Idempotent Ingestion)**: 5 tests verifying that duplicate submissions return original receipts without creating redundant records.
- **F-15 (Evidence Ingest API)**: 5 tests verifying multipart file upload, MIME validation, and metadata extraction.
- **F-16 (Content Storage)**: 5 tests verifying sharded SHA-256 content-addressable storage (CAS).
- **F-17 (Async AI Dispatch)**: 5 tests verifying background task scheduling and status tracking.

#### Local AI & Forensics (F-18 to F-28) — 55 Tests
- **F-18 (Laplacian Blur)**: 5 tests verifying focus sharpness variance ($\sigma^2_{Lap} \ge 80.0$).
- **F-19 (Exposure / Luminance)**: 5 tests verifying histogram clipping for under/over-exposure.
- **F-20 (Resolution Bounds)**: 5 tests verifying minimum $800 \times 600$ resolution and aspect ratio constraints.
- **F-21 (EXIF Consistency)**: 5 tests verifying capture timestamp vs EXIF `DateTimeOriginal` delta ($\le 3600\text{ s}$).
- **F-22 (Exact Deduplication)**: 5 tests verifying bit-exact SHA-256 duplicate flagging.
- **F-23 (Perceptual Deduplication)**: 5 tests verifying 64-bit DCT pHash and gradient dHash Hamming distances ($\le 10$).
- **F-24 (Crop Lifecycle Stage)**: 5 tests verifying MobileNetV3-Small neural classification across `SOWING`, `CROP_GROWTH`, `HARVEST`, `STORAGE`.
- **F-25 (Model Registry)**: 5 tests verifying model tiers, weights checksums, and dataset provenance metadata.
- **F-26 (Unvalidated Heuristic Guards)**: 5 tests verifying that unvalidated heuristics never autonomously reject evidence.
- **F-27 (Structured AI Schema)**: 5 tests verifying explainable JSON assessment output complying with Interface Contract 2.
- **F-28 (Never-Autonomous-Reject Rule)**: 5 tests verifying invariant that AI routes anomalies to `PENDING_REVIEW` without autonomous rejections.

#### Mobile Platform & Client Architecture (F-29 to F-39) — 55 Tests
- **F-29 (Multilingual Onboarding)**: 5 tests verifying Telugu, Hindi, and English locale catalogs and fallback resolution.
- **F-30 (Farmer Auth UI)**: 5 tests verifying registration, login, and token storage logic.
- **F-31 (GPS Acquisition)**: 5 tests verifying WGS84 GPS coordinate validation and accuracy bounds.
- **F-32 (Boundary Polygon)**: 5 tests verifying non-self-intersecting closed farm polygons.
- **F-33 (Camera vs File Selection)**: 5 tests verifying separation of camera capture and gallery document picking.
- **F-34 (Lifecycle Stage Selection)**: 5 tests verifying validation of all 5 stages (`SOWING`, `INPUT_APPLICATION`, `CROP_GROWTH`, `HARVEST`, `STORAGE`).
- **F-35 (Keystore P-256 Signing)**: 5 tests verifying client-side envelope signing.
- **F-36 (SQLite Offline Queue)**: 5 tests verifying persistent queue insertion, status tracking, and queue recovery after crash.
- **F-37 (Sync State Machine)**: 5 tests verifying state transitions (`QUEUED` $\to$ `SYNCING` $\to$ `DURABLY_ACKED` $\to$ `FAILED`).
- **F-38 (Delayed Upload Legitimacy)**: 5 tests verifying that offline-delayed uploads with valid sequence and signatures are never marked fraudulent.
- **F-39 (Farmer Notifications)**: 5 tests verifying delivery of reviewer decisions to the farmer client.

#### Review, Ledger & Verification (F-40 to F-45) — 30 Tests
- **F-40 (Reviewer Console)**: 5 tests verifying reviewer authentication and pending queue retrieval.
- **F-41 (Signal Visualizer)**: 5 tests verifying quality, duplicate, category, and forensic signal cards.
- **F-42 (Decision Engine)**: 5 tests verifying `APPROVE`, `REJECT`, and `REQUEST_RETAKE` decision transitions.
- **F-43 (Merkle Batching & Ledger)**: 5 tests verifying periodic Merkle batch creation, root persistence, and Authority checkpoint signing.
- **F-44 (Public Tokens)**: 5 tests verifying 256-bit unguessable public verification tokens.
- **F-45 (Privacy-Preserving Public Verify)**: 5 tests verifying zero PII and zero GPS coordinate leakage on public verification endpoints.

---

### 4.2 Tier 2: Boundary & Corner Cases — 35 Tests
Boundary testing validates system resilience against extreme inputs:
- **`test_b01_crypto_boundaries.py`**: Empty strings, Unicode control characters, extreme DER lengths, large integers.
- **`test_b02_merkle_boundaries.py`**: Odd leaf counts ($N = 1, 3, 5, 17, 35, 1024$), single leaf proofs, leaf index bounds.
- **`test_b03_spatial_boundaries.py`**: North/South poles, anti-meridian crossing, degenerate collinear polygons, zero-area parcels.
- **`test_b04_image_boundaries.py`**: $1 \times 1$ pixel images, extreme aspect ratios ($100:1$), pitch black (all 0s), pure white (all 255s).
- **`test_b05_sequence_boundaries.py`**: Sequence numbers $0, 1, 2^{31}-1, 2^{63}-1$, gaps in sequence, duplicate sequence injection.
- **`test_b06_offline_boundaries.py`**: 30-day offline delay, simulated power cuts during synchronization, partial multipart payloads.
- **`test_b07_review_verify_boundaries.py`**: Tampered Merkle proofs, expired tokens, revoked device keys.

---

### 4.3 Tier 3: Cross-Feature Interactions — 25 Tests
Pairwise testing validates contract adherence between independent subsystems:
- **`test_i01_camera_offline_sync.py`**: Camera capture $\times$ SQLite offline queue $\times$ durable backend acknowledgment.
- **`test_i02_ai_flags_reviewer_flow.py`**: Blurry photo detection $\times$ AI assessment record $\times$ reviewer retake request workflow.
- **`test_i03_review_merkle_batching.py`**: Reviewer approval decision $\times$ Merkle batch inclusion $\times$ signed Authority checkpoint.
- **`test_i04_duplicate_sequence_rejection.py`**: Replay attack injection $\times$ monotonic sequence enforcer $\times$ tamper-evident audit log.
- **`test_i05_public_verify_checkpoint_sync.py`**: Public token resolution $\times$ client-side WebCrypto proof recomputation $\times$ zero-PII verification.

---

### 4.4 Tier 4: Real-World Workloads & Hardware Scenarios — 8 Tests

#### Multi-Actor User Journeys (4 Passed)
1. **`test_rw01_full_telugu_farmer_lifecycle.py`**:
   - A farmer in Adilabad registers a 4-hectare cotton farm using the Telugu interface.
   - Captures 5 photos across the full lifecycle (`SOWING`, `INPUT_APPLICATION`, `CROP_GROWTH`, `HARVEST`, `STORAGE`).
   - All 5 photos are queued offline, synchronized to the backend, evaluated by local AI, approved by a reviewer, committed into a Merkle batch, and verified via public token.
2. **`test_rw02_blurry_retake_workflow.py`**:
   - A farmer captures a low-light blurry crop photo during dusk.
   - Deterministic CV flags focus sharpness ($\sigma^2_{Lap} = 28.4 < 80.0$).
   - AI routes evidence to `PENDING_REVIEW` with an advisory flag.
   - Reviewer issues `REQUEST_RETAKE` with instructions in Telugu.
   - Farmer resubmits a sharp photo, which passes AI evaluation and is approved.
3. **`test_rw03_offline_delayed_monsoon_sync.py`**:
   - Heavy monsoon floods knock out rural cellular connectivity for 14 days.
   - Farmer captures evidence daily; 14 envelopes accumulate in local SQLite.
   - When connectivity restores, all 14 records sync with valid sequence numbers and original timestamps.
   - Backend evaluates delayed upload legitimacy rule: confirms valid monotonic sequence and authentic device signature, classifies records as `LEGITIMATE_OFFLINE_DELAY`, and proceeds without false fraud flags.
4. **`test_rw04_multi_device_farm_audit.py`**:
   - Two authorized family devices concurrently submit evidence for the same farm parcel.
   - Backend sequence enforcers maintain independent sequence counters per device while cross-referencing farm spatial boundaries.

#### Physical Android Hardware Tests (4 Skipped Honestly)
Located in `tests_e2e/tier4_real_world/test_physical_device_hardware.py`:
- `test_physical_camera_capture`: Launches real Android camera intent and validates image bytes.
- `test_physical_file_picker_selection`: Launches real Android document picker and selects a JPEG.
- `test_physical_android_keystore_p256_signing`: Verifies hardware-backed Android Keystore key generation.
- `test_physical_offline_network_toggle_queue`: Toggles airplane mode via ADB, captures photo, restores network, verifies sync.
- **Audit Finding**: In the current headless CI / development workstation environment without an attached USB handset, these 4 tests automatically detect that `adb devices` returns no connected hardware and **skip with explicit justification**:
  ```
  Skipped: No physical Android device connected via ADB
  ```
  This adheres strictly to Non-Negotiable Rule 12 ("Do not count mocked tests as physical-device tests. Do not claim complete physical validation if no physical Android device was tested.").

---

## 5. Synthetic Fixture Architecture

All test fixtures (`tests_e2e/fixtures/`) generate genuine in-memory assets:
- **`image_generator.py`**: Generates real JPEG and PNG binary files using Pillow and OpenCV with calibrated optical characteristics (Laplacian blur kernel, gamma-adjusted exposure, 64-bit DCT pHash pairs).
- **`crypto_fixtures.py`**: Directly invokes production `crypto.rfc8785`, `crypto.ecdsa_p256`, and `crypto.merkle` modules.
- **`spatial_fixtures.py`**: Generates geometrically valid WGS84 coordinates and non-self-intersecting farm polygons.
- **`envelope_fixtures.py`**: Constructs canonical evidence envelopes conforming to Interface Contract 1.

---

## 6. CLI Test Runner Specification & Verification Commands

The test runner `tests_e2e/test_runner.py` provides standalone execution with exit codes and machine-readable JSON output:

### 1. Execute All 4 Tiers (Default)
```powershell
python tests_e2e/test_runner.py --tier 1,2,3,4
```
*Expected Output*: `289 passed, 4 skipped in ~4.5s (Exit Code: 0)`

### 2. Execute Strictly by Category
```powershell
python tests_e2e/test_runner.py --type unit          # 180 passed
python tests_e2e/test_runner.py --type integration   # 80 passed
python tests_e2e/test_runner.py --type e2e           # 29 passed, 4 skipped
```

### 3. Execute Software-Only Mode
```powershell
python tests_e2e/test_runner.py --device mock
```
*Expected Output*: `289 passed, 0 skipped, 100% pass rate (Exit Code: 0)`

### 4. Generate Machine-Readable JSON Report
```powershell
python tests_e2e/test_runner.py --report test_report_full.json
```
*Expected Output*: Writes complete execution breakdown to `test_report_full.json`.
