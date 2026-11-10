# PRAMAN File Selection, Persistent Offline Queue & Multipart Synchronization Test Report

**Document ID**: PRAMAN-TEST-UPLOAD-SYNC-2026-M5  
**Report Date**: 2026-11-09T19:44:00Z  
**Classification**: Mobile Subsystem Engineering & Network Synchronization Verification  
**Target Modules**:  
- `mobile/android/app/src/main/java/org/praman/farmer/MainActivity.java`  
- `mobile/android/app/src/main/java/org/praman/farmer/storage/EvidenceDbHelper.java`  
- `mobile/android/app/src/main/java/org/praman/farmer/storage/EvidenceRecord.java`  
- `mobile/android/app/src/main/java/org/praman/farmer/storage/NativeStorageBridge.java`  
- `mobile/android/app/src/main/java/org/praman/farmer/sync/EvidenceSyncEngine.java`  
**Status**: Fully Implemented, Tested, and Verified  

---

## 1. Executive Summary & Scope

In rural agricultural settings, continuous internet connectivity is rare. Farmers routinely document evidence across remote plots where cellular reception is weak or nonexistent. Consequently, the PRAMAN platform relies on a dual-capability architecture:
1. **Persistent Offline Storage**: Evidence captured in the field must be durably committed to local database storage immediately upon capture, surviving application kill, OS low-memory termination, and device reboot.
2. **Real Network Synchronization**: When internet connectivity is restored, the synchronization engine must transmit the raw, bit-for-bit image file alongside the RFC 8785 canonical envelope and NIST P-256 signature to the backend via HTTP `multipart/form-data`, gracefully handling transient drops and server retries.

The prototype baseline suffered from two fatal defects:
- Queued records were stored in a transient JavaScript heap array (`this.queue = [];`), resulting in 100% data loss whenever the app was closed.
- Synchronization was entirely simulated via a JavaScript `setTimeout` timer that marked evidence "DURABLY_ACKED" without generating any network packets.

During Milestone M1, this prototype was replaced with native Android components: a modern photo picker with stream caching, an ACID-compliant SQLite database (`EvidenceDbHelper.java`), and a robust multipart HTTP sync engine (`EvidenceSyncEngine.java`). This report details the implementation, architecture, and verification results.

---

## 2. Android Photo & File Picker Architecture

```
[ Farmer taps "Choose from Gallery" ]
                │
                ▼
[ MainActivity.launchFilePicker() ]
                │
                ├─► Android 13+ (API 33+): MediaStore.ACTION_PICK_IMAGES (image/*)
                │                          (Zero storage permission prompts)
                │
                ├─► Android 7-12 (API 24-32): Intent.ACTION_OPEN_DOCUMENT (CATEGORY_OPENABLE)
                │
                └─► Legacy Fallback: Intent.ACTION_GET_CONTENT (Chooser fallback)
                │
                ▼
[ System Photo Picker Activity ]
                │
                ├─► Selected: Uri content://media/picker/...
                │
                ▼
[ onActivityResult() -> copyUriToLocalFileAsync(Uri) ]
                │
                ├─► Open InputStream via getContentResolver().openInputStream(uri)
                ├─► Stream 16KB chunked transfer into private file:
                │   DIRECTORY_PICTURES/PRAMAN_PICK_yyyyMMdd_HHmmss.jpg
                ├─► Execute processPhotoFileAsync(destFile, "FILE_UPLOAD")
                │
                ▼
[ WebView Callback: window.app.onNativePhotoCaptured(...) ]
```

### 2.1 Modern Android 13+ Photo Picker (`MediaStore.ACTION_PICK_IMAGES`)
On Android 13 (API 33) and Android 14 (API 34), requesting broad media permissions (`READ_EXTERNAL_STORAGE` or `READ_MEDIA_IMAGES`) degrades user trust. PRAMAN leverages the modern system photo picker:
```java
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
    // Android 13+ Modern Photo Picker
    intent = new Intent(MediaStore.ACTION_PICK_IMAGES);
    intent.setType("image/*");
} else {
    // Android 7-12 Document / Content Picker
    intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
    intent.addCategory(Intent.CATEGORY_OPENABLE);
    intent.setType("image/*");
}
```
*Key Advantage*: The system photo picker executes in a system process and grants fine-grained, single-URI read access without requiring runtime storage permission dialogs.

### 2.2 Content URI Stream Caching (`copyUriToLocalFileAsync`)
Android content URIs (`content://...`) have ephemeral security grants that expire when the activity finishes or the app process is terminated. If an evidence item remains in the offline queue for hours or days, reading the original content URI later causes `SecurityException: Permission Denial`.

To ensure permanent offline durability, `copyUriToLocalFileAsync` (lines 269–300) immediately reads the input stream and writes it to the app's private external storage directory:
```java
File storageDir = getExternalFilesDir(Environment.DIRECTORY_PICTURES);
File destFile = new File(storageDir, "PRAMAN_PICK_" + timeStamp + ".jpg");

try (InputStream is = getContentResolver().openInputStream(uri);
     OutputStream os = new FileOutputStream(destFile)) {
    byte[] buffer = new byte[16384]; // 16 KB chunked buffer
    int read;
    while ((read = is.read(buffer)) != -1) {
        os.write(buffer, 0, read);
    }
    os.flush();
}
```
*Result*: The raw bytes of the chosen photograph are cached on disk as an independent file, guaranteeing that offline evidence submission remains valid even across device reboots.

---

## 3. Persistent Offline Queue Architecture (`EvidenceDbHelper.java`)

### 3.1 Database Schema & Indexing
The offline queue is backed by an Android SQLite database (`praman_evidence.db`) with schema defined in `EvidenceDbHelper.java`:

```sql
CREATE TABLE offline_evidence (
    evidence_id TEXT PRIMARY KEY,
    device_id TEXT,
    farm_id TEXT,
    sequence_number INTEGER,
    lifecycle_stage TEXT,
    capture_source TEXT,
    raw_file_path TEXT,
    image_hash TEXT,
    envelope_json TEXT,
    signature_b64 TEXT,
    status TEXT,
    retry_count INTEGER DEFAULT 0,
    server_receipt TEXT,
    error_message TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX idx_sequence ON offline_evidence (sequence_number);
CREATE INDEX idx_status ON offline_evidence (status);
```

### 3.2 Monotonic Sequence Enforcement
Each device enrolled in PRAMAN maintains a strictly increasing monotonic sequence counter (`sequence_number`). The backend rejects any out-of-order sequence gaps or duplicate replays (`409 Conflict`).
- `NativeStorageBridge.getNextSequenceNumber()` queries `MAX(sequence_number) + 1` from the SQLite table.
- Monotonic sequence numbers are locked inside the RFC 8785 canonical envelope and signed by the hardware Keystore prior to queue insertion.

### 3.3 State Machine & Lifecycle Transitions
Evidence records in `offline_evidence` transition through four well-defined states:
```
           [ Evidence Captured & Signed ]
                         │
                         ▼
                    ┌─────────┐
                    │ QUEUED  │
                    └────┬────┘
                         │ triggerSync()
                         ▼
                    ┌─────────┐
         ┌─────────►│ SYNCING │
         │          └────┬────┘
         │               │
  Retry  │     ┌─────────┴─────────┐
  Backoff│     │                   │
         │     ▼ HTTP 200/201      ▼ HTTP Error / Timeout
     ┌───┴────┐              ┌─────────┐
     │ FAILED │              │ SYNCED  │ (Durable receipt persisted)
     └────────┘              └─────────┘
```

### 3.4 Crash Resilience Verification
Because SQLite operations execute with atomic transaction commits:
- Application force-stop via Android Settings or task killer preserves all `QUEUED` records.
- Device reboot preserves all records and index pointers.
- Upon app launch, `NativeStorageBridge.getPendingQueue()` reads all un-synced items and restores the farmer's queue display.

---

## 4. Real Multipart HTTP Network Synchronization Engine

### 4.1 Sync Engine Design (`EvidenceSyncEngine.java`)
The sync engine replaces the simulated timer with an asynchronous HTTP engine executing on a dedicated single-threaded executor:
- **Target Endpoint**: `POST {backendBaseUrl}/api/v1/evidence/ingest`
- **Default Base URL**: `http://10.0.2.2:8000` (configurable via UI to any server IP or domain)
- **Timeouts**: Connect timeout 15s; read timeout 30s.

### 4.2 RFC 7578 Multipart/Form-Data Framing
The HTTP POST payload is assembled using a cryptographically unique boundary delimiter:
```
--===PramanBoundary<uuid>===
Content-Disposition: form-data; name="envelope"
Content-Type: application/json; charset=UTF-8

{"device_id":"...","evidence_id":"...","farm_id":"...","image_hash":"...","lifecycle_stage":"CROP_GROWTH","metadata":{...},"schema_version":"1.0","sequence_number":1}
--===PramanBoundary<uuid>===
Content-Disposition: form-data; name="signature"
Content-Type: text/plain; charset=UTF-8

MEQCIBaX0/x9o8Qe6v2A6s...
--===PramanBoundary<uuid>===
Content-Disposition: form-data; name="file"; filename="PRAMAN_20261109_180000.jpg"
Content-Type: image/jpeg
Content-Transfer-Encoding: binary

<raw binary bytes streamed from disk in 16KB blocks>
--===PramanBoundary<uuid>===--
```

### 4.3 Streaming Binary Transfer
The raw photo file is read directly from `record.getRawFilePath()` using a 16KB buffer and written to `conn.getOutputStream()`. The entire file is never loaded into a single contiguous byte array in RAM, preventing heap exhaustion during uploads.

### 4.4 Server Response Handling & Idempotency
1. **HTTP 201 Created**:
   - The backend validates the hash, signature, and sequence number, stores the raw image in Content-Addressable Storage (CAS), and returns a server receipt signed with the server's private key.
   - The sync engine transitions the record status to `SYNCED`, stores the server receipt JSON, and notifies the UI via `SyncListener.onItemSynced(evidenceId, true, receipt)`.
2. **HTTP 200 OK (Idempotent Retry)**:
   - If a previous transmission succeeded but the network dropped before the client received the response, retransmitting the identical record returns HTTP 200 with the original receipt.
   - The client records this as `SYNCED` without error.
3. **HTTP 400 / 409 / Network Drop**:
   - If an error occurs, `retry_count` is incremented, `status` is set to `FAILED`, the server error message is stored, and the engine logs the diagnostic.
   - The engine automatically applies exponential backoff for subsequent sync triggers.

---

## 5. Verification & Test Suite Execution

### 5.1 Android Serialization Unit Test
In `mobile/android/app/src/test/java/org/praman/farmer/EvidenceUnitTest.java`:
```java
@Test
public void testEvidenceRecordSerialization() throws Exception {
    EvidenceRecord record = new EvidenceRecord();
    record.setEvidenceId("ev_test_123");
    record.setDeviceId("dev_uuid_456");
    record.setFarmId("farm_uuid_789");
    record.setSequenceNumber(5);
    record.setLifecycleStage("CROP_GROWTH");
    record.setCaptureSource("CAMERA");
    record.setRawFilePath("/data/user/0/org.praman.farmer/files/photo.jpg");
    record.setImageHash("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    record.setEnvelopeJson("{\"schema_version\":\"1.0\"}");
    record.setSignatureB64("MEQCIBaX0/x9o8Qe6v2A6s==");
    record.setStatus("QUEUED");
    record.setRetryCount(1);
    record.setCreatedAt("2026-11-09T18:00:00Z");

    JSONObject json = record.toJson();
    EvidenceRecord restored = EvidenceRecord.fromJson(json);
    assertEquals(record.getEvidenceId(), restored.getEvidenceId());
    assertEquals(record.getSequenceNumber(), restored.getSequenceNumber());
    assertEquals(record.getStatus(), restored.getStatus());
}
```
- **Execution Result**: PASSED (`testEvidenceRecordSerialization` completed in 0.011s).

### 5.2 Subsystem Integration Tests (`backend/tests/`)
The backend ingestion endpoint `/api/v1/evidence/ingest` was verified against real multipart payloads:
```powershell
python -m pytest backend/tests/test_evidence_ingest_flow.py -v
```
- **Tests Passing**:
  - `test_valid_evidence_ingestion_multipart`: 201 Created, CAS file created, receipt returned.
  - `test_idempotent_retry_ingestion`: 200 OK returned on identical re-upload.
  - `test_sequence_gap_rejected`: 409 Conflict returned when sequence jumps from 1 to 3.
  - `test_tampered_image_hash_rejected`: 400 Bad Request returned on hash mismatch.
  - `test_tampered_signature_rejected`: 400 Bad Request returned on invalid ECDSA signature.

### 5.3 E2E Feature Tests (`tests_e2e/tier1_features/`)
The following automated feature tests were executed via `tests_e2e/test_runner.py`:
- `test_f04_photo_picker_android.py`: PASSED (verifies modern picker fallback semantics).
- `test_f05_mime_type_validation.py`: PASSED (verifies JPEG/PNG validation and rejection of invalid file types).
- `test_f06_offline_queue_durability.py`: PASSED (verifies queue recovery after simulated process kill).
- `test_f07_idempotent_network_sync.py`: PASSED (verifies idempotent duplicate handling).
- `test_f08_network_retry_backoff.py`: PASSED (verifies retry counter and backoff).

---

## 6. Upload & Sync Subsystem Conclusion

The PRAMAN File Upload and Synchronization Subsystem is completely functional and verified:
- Modern Android 13+ Photo Picker (`MediaStore.ACTION_PICK_IMAGES`) provides privacy-safe photo selection with fallback to document open.
- Stream caching (`copyUriToLocalFileAsync`) guarantees raw image file durability independently of transient URI grants.
- Persistent SQLite queue (`EvidenceDbHelper.java`) provides complete crash and reboot resilience.
- Multipart HTTP sync engine (`EvidenceSyncEngine.java`) transmits genuine envelope, signature, and raw binary bytes with idempotent retry protection.
- The simulated `setTimeout` and in-memory array mocks have been 100% eliminated.
