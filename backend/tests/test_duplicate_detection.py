"""Comprehensive Tests for PRAMAN Duplicate Content Detection and Idempotency.

Covers ORIGINAL_REQUEST.md §4:
1. Idempotency vs Duplicate Detection:
   - Identical network retries (S == S_last with matching image hash) -> HTTP 200 IDEMPOTENT_RETRY
   - Sequential re-uploads (S = S_last + 1 with identical bytes) -> HTTP 201 EXACT_DUPLICATE
2. Perceptual duplicate detection:
   - Same visual scene with recompression/resizing (Hamming distance <= 6) -> POSSIBLE_VISUAL_DUPLICATE
   - Visually similar scenes (Hamming distance 7..10) -> DUPLICATE_REQUIRES_REVIEW
   - Distinct scenes (Hamming distance > 10) -> NEW_EVIDENCE
3. Cross-Farmer Privacy Boundary:
   - Receipts for duplicate submissions MUST NEVER expose another farmer's identity,
     farm ID, or private evidence IDs.
4. Database provenance and Audit Trail:
   - Duplicate relationship recorded in DB (duplicate_of_id, duplicate_type, hamming_distance)
   - Status transitions to PENDING_REVIEW for duplicates
   - DUPLICATE_DETECTED and IDEMPOTENT_RETRY audit logs recorded
5. Background AI Dispatcher integration:
   - Historical hashes and pHashes queried from DB and passed to AIEvaluator
   - AIAssessment record persisted without schema errors
"""

import io
import json
import uuid
import base64
import hashlib
from datetime import datetime, timezone
from PIL import Image

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.models.farmer import Farmer
from backend.app.models.device import Device
from backend.app.models.farm import Farm
from backend.app.models.evidence import Evidence
from backend.app.models.audit_log import AuditLog
from backend.app.models.ai_assessment import AIAssessment
from backend.app.services.duplicate_service import DuplicateService, DuplicateOutcome
from backend.app.services.ai_dispatcher import ai_dispatcher
from crypto.ecdsa_p256 import generate_keypair, public_key_to_pem, sign
from crypto.rfc8785 import canonicalize
from tests_e2e.fixtures.image_generator import SyntheticImageGenerator
from ai_engine.hashing import (
    compute_sha256,
    compute_phash_64,
    compute_dhash_64,
    hamming_distance_hex,
)


@pytest.fixture
def test_env(tmp_path):
    """Sets up an isolated database and TestClient for duplicate detection tests."""
    test_db = str(tmp_path / "dup_test.db")
    engine = create_engine(f"sqlite:///{test_db}", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    ai_dispatcher.set_session_factory(TestingSession)
    client = TestClient(app)

    yield client, TestingSession

    app.dependency_overrides.clear()
    ai_dispatcher.set_session_factory(None)
    engine.dispose()


def register_farmer_device_farm(client, name="Test Farmer", phone=None, crop="Cotton"):
    """Helper to enroll a farmer, active device, and registered farm."""
    phone_number = phone or f"+9198{uuid.uuid4().int % 100000000:08d}"
    rf = client.post("/api/v1/farmers", json={
        "full_name": name,
        "phone_number": phone_number,
        "language_pref": "en",
    })
    assert rf.status_code == 201
    farmer_id = rf.json()["id"]

    priv_key, pub_key = generate_keypair()
    pub_pem = public_key_to_pem(pub_key)
    device_id = str(uuid.uuid4())

    rd = client.post("/api/v1/devices/register", json={
        "device_id": device_id,
        "farmer_id": farmer_id,
        "public_key_pem": pub_pem,
    })
    assert rd.status_code == 201

    rfarm = client.post("/api/v1/farms", json={
        "farmer_id": farmer_id,
        "farm_name": f"{name}'s Farm",
        "crop_type": crop,
        "boundary_geojson": json.dumps({
            "type": "Polygon",
            "coordinates": [[[78.5, 19.6], [78.51, 19.6], [78.51, 19.61], [78.5, 19.61], [78.5, 19.6]]]
        }),
    })
    assert rfarm.status_code == 201
    farm_id = rfarm.json()["id"]

    return {
        "farmer_id": farmer_id,
        "device_id": device_id,
        "priv_key": priv_key,
        "pub_pem": pub_pem,
        "farm_id": farm_id,
    }


def build_signed_submission(device_info, seq: int, image_bytes: bytes, evidence_id=None):
    """Builds RFC 8785 canonical envelope and ECDSA P-256 signature."""
    img_hash = hashlib.sha256(image_bytes).hexdigest()
    ev_id = evidence_id or str(uuid.uuid4())
    envelope = {
        "device_id": device_info["device_id"],
        "evidence_id": ev_id,
        "farm_id": device_info["farm_id"],
        "image_hash": img_hash,
        "lifecycle_stage": "CROP_GROWTH",
        "metadata": {
            "capture_source": "CAMERA",
            "capture_timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_accuracy": 4.5,
            "latitude": 19.605,
            "longitude": 78.505,
        },
        "schema_version": "1.0",
        "sequence_number": seq,
    }
    canonical_bytes = canonicalize(envelope)
    sig_der = sign(device_info["priv_key"], canonical_bytes)
    sig_b64 = base64.b64encode(sig_der).decode("utf-8")

    files = {"file": ("evidence.jpg", image_bytes, "image/jpeg")}
    data = {"envelope": json.dumps(envelope), "signature": sig_b64}
    return data, files, envelope


class TestDuplicateContentDetection:
    """Tests all duplicate detection and idempotency requirements from ORIGINAL_REQUEST.md §4."""

    def test_idempotent_retry_preserves_original_evidence_id(self, test_env):
        """Mechanism A: Exact network retry (S == S_last) returns existing result with classification=IDEMPOTENT_RETRY."""
        client, SessionMaker = test_env
        dev = register_farmer_device_farm(client, "Ramesh")
        img_bytes, _ = SyntheticImageGenerator.create_sharp_crop_image(800, 600)

        data1, files1, _ = build_signed_submission(dev, seq=1, image_bytes=img_bytes)

        # 1. Initial submission -> 201 Created
        r1 = client.post("/api/v1/evidence/ingest", data=data1, files=files1)
        assert r1.status_code == 201
        receipt1 = r1.json()
        assert receipt1["classification"] == "NEW_EVIDENCE"
        assert receipt1["status"] == "DURABLY_ACKED"
        original_ev_id = receipt1["evidence_id"]

        # 2. Network retry with identical request -> 200 OK
        retry_files = {"file": ("evidence.jpg", img_bytes, "image/jpeg")}
        r1_retry = client.post("/api/v1/evidence/ingest", data=data1, files=retry_files)
        assert r1_retry.status_code == 200
        receipt_retry = r1_retry.json()
        assert receipt_retry["classification"] == "IDEMPOTENT_RETRY"
        assert receipt_retry["status"] == "DURABLY_ACKED"
        assert receipt_retry["evidence_id"] == original_ev_id
        assert receipt_retry["sequence_number"] == 1

        # Confirm exactly 1 record in evidence table
        db = SessionMaker()
        count = db.query(Evidence).filter(Evidence.device_id == dev["device_id"]).count()
        assert count == 1
        db.close()

    def test_exact_duplicate_sequential_upload_detected(self, test_env):
        """Mechanism B: Sequential re-upload of identical image (S = 2) detected as EXACT_DUPLICATE."""
        client, SessionMaker = test_env
        dev = register_farmer_device_farm(client, "Suresh")
        img_bytes, img_hash = SyntheticImageGenerator.create_sharp_crop_image(800, 600)

        # Sequence 1: New image
        data1, files1, _ = build_signed_submission(dev, seq=1, image_bytes=img_bytes)
        r1 = client.post("/api/v1/evidence/ingest", data=data1, files=files1)
        assert r1.status_code == 201
        assert r1.json()["classification"] == "NEW_EVIDENCE"
        ev1_id = r1.json()["evidence_id"]

        # Sequence 2: Submitting identical image with advanced sequence number
        data2, files2, _ = build_signed_submission(dev, seq=2, image_bytes=img_bytes)
        r2 = client.post("/api/v1/evidence/ingest", data=data2, files=files2)
        assert r2.status_code == 201
        receipt2 = r2.json()
        assert receipt2["classification"] == "EXACT_DUPLICATE"
        assert receipt2["is_duplicate"] is True
        assert receipt2["duplicate_type"] == "EXACT_DUPLICATE"
        assert receipt2["hamming_distance"] == 0

        # Verify DB records duplicate relationship
        db = SessionMaker()
        ev2 = db.query(Evidence).filter(Evidence.id == receipt2["evidence_id"]).first()
        assert ev2 is not None
        assert ev2.duplicate_of_id == ev1_id
        assert ev2.duplicate_type == "EXACT_DUPLICATE"
        assert ev2.hamming_distance == 0
        assert ev2.status == "PENDING_REVIEW"
        db.close()

    def test_cross_farmer_duplicate_and_privacy_safeguard(self, test_env):
        """Cross-farmer duplicate detection MUST NOT leak Farmer A's evidence_id, farm_id, or farmer_id to Farmer B."""
        client, SessionMaker = test_env
        farmer_a = register_farmer_device_farm(client, "Farmer Ramesh", phone="+919811111111")
        farmer_b = register_farmer_device_farm(client, "Farmer Suresh", phone="+919822222222")

        img_bytes, img_hash = SyntheticImageGenerator.create_sharp_crop_image(800, 600)

        # Farmer A submits the original image
        data_a, files_a, _ = build_signed_submission(farmer_a, seq=1, image_bytes=img_bytes)
        r_a = client.post("/api/v1/evidence/ingest", data=data_a, files=files_a)
        assert r_a.status_code == 201
        receipt_a = r_a.json()
        evidence_a_id = receipt_a["evidence_id"]

        # Farmer B submits the exact same image
        data_b, files_b, _ = build_signed_submission(farmer_b, seq=1, image_bytes=img_bytes)
        r_b = client.post("/api/v1/evidence/ingest", data=data_b, files=files_b)
        assert r_b.status_code == 201
        receipt_b = r_b.json()

        # Outcome is EXACT_DUPLICATE
        assert receipt_b["classification"] == "EXACT_DUPLICATE"
        assert receipt_b["is_duplicate"] is True

        # STRICT PRIVACY INVARIANTS:
        # 1. Receipt must NOT contain Farmer A's evidence_id
        assert receipt_b["evidence_id"] != evidence_a_id
        receipt_b_str = json.dumps(receipt_b)
        assert evidence_a_id not in receipt_b_str
        assert farmer_a["farmer_id"] not in receipt_b_str
        assert farmer_a["farm_id"] not in receipt_b_str

        # 2. GET /evidence/{id} for Farmer B must NOT leak Farmer A's data
        r_get_b = client.get(f"/api/v1/evidence/{receipt_b['evidence_id']}")
        assert r_get_b.status_code == 200
        get_b_str = json.dumps(r_get_b.json())
        assert evidence_a_id not in get_b_str
        assert farmer_a["farmer_id"] not in get_b_str
        assert farmer_a["farm_id"] not in get_b_str

        # 3. In the database, the provenance link is stored securely for reviewers
        db = SessionMaker()
        ev_b = db.query(Evidence).filter(Evidence.id == receipt_b["evidence_id"]).first()
        assert ev_b.duplicate_of_id == evidence_a_id
        assert ev_b.status == "PENDING_REVIEW"
        db.close()

    def test_perceptual_near_duplicate_recompressed(self, test_env):
        """Verifies that recompressing the same image yields POSSIBLE_VISUAL_DUPLICATE (distance <= 6) or DUPLICATE_REQUIRES_REVIEW (7..10)."""
        client, SessionMaker = test_env
        dev = register_farmer_device_farm(client, "Visual Farmer")

        (bytes_orig, _), (bytes_recomp, _) = SyntheticImageGenerator.create_phash_near_duplicate_pair()
        p1 = compute_phash_64(bytes_orig)
        p2 = compute_phash_64(bytes_recomp)
        d1 = compute_dhash_64(bytes_orig)
        d2 = compute_dhash_64(bytes_recomp)
        min_dist = min(hamming_distance_hex(p1, p2), hamming_distance_hex(d1, d2))
        assert min_dist <= 10, f"Expected perceptual similarity <= 10, got {min_dist}"

        # Submit original -> NEW_EVIDENCE
        data1, files1, _ = build_signed_submission(dev, seq=1, image_bytes=bytes_orig)
        r1 = client.post("/api/v1/evidence/ingest", data=data1, files=files1)
        assert r1.status_code == 201
        assert r1.json()["classification"] == "NEW_EVIDENCE"

        # Submit recompressed -> POSSIBLE_VISUAL_DUPLICATE or DUPLICATE_REQUIRES_REVIEW
        data2, files2, _ = build_signed_submission(dev, seq=2, image_bytes=bytes_recomp)
        r2 = client.post("/api/v1/evidence/ingest", data=data2, files=files2)
        assert r2.status_code == 201
        receipt2 = r2.json()

        expected_class = "POSSIBLE_VISUAL_DUPLICATE" if min_dist <= 6 else "DUPLICATE_REQUIRES_REVIEW"
        assert receipt2["classification"] == expected_class
        assert receipt2["is_duplicate"] is True
        assert receipt2["hamming_distance"] == min_dist

    def test_distinct_images_classified_as_new_evidence(self, test_env):
        """Verifies completely distinct image scenes yield NEW_EVIDENCE (Hamming distance > 10)."""
        client, SessionMaker = test_env
        dev = register_farmer_device_farm(client, "Diverse Farmer")

        sharp_bytes, _ = SyntheticImageGenerator.create_sharp_crop_image(800, 600)
        dark_bytes, _ = SyntheticImageGenerator.create_underexposed_image(800, 600)

        # Submit image 1
        data1, files1, _ = build_signed_submission(dev, seq=1, image_bytes=sharp_bytes)
        r1 = client.post("/api/v1/evidence/ingest", data=data1, files=files1)
        assert r1.status_code == 201
        assert r1.json()["classification"] == "NEW_EVIDENCE"

        # Submit distinct image 2
        data2, files2, _ = build_signed_submission(dev, seq=2, image_bytes=dark_bytes)
        r2 = client.post("/api/v1/evidence/ingest", data=data2, files=files2)
        assert r2.status_code == 201
        assert r2.json()["classification"] == "NEW_EVIDENCE"
        assert r2.json()["is_duplicate"] is False

    def test_audit_logging_of_duplicate_and_idempotent_events(self, test_env):
        """Verifies DUPLICATE_DETECTED and IDEMPOTENT_RETRY events are immutably logged."""
        client, SessionMaker = test_env
        dev = register_farmer_device_farm(client, "Audit Farmer")
        img_bytes, _ = SyntheticImageGenerator.create_sharp_crop_image(800, 600)

        data1, files1, _ = build_signed_submission(dev, seq=1, image_bytes=img_bytes)

        # 1. Ingest sequence 1
        client.post("/api/v1/evidence/ingest", data=data1, files=files1)

        # 2. Idempotent retry of sequence 1
        retry_files = {"file": ("evidence.jpg", img_bytes, "image/jpeg")}
        client.post("/api/v1/evidence/ingest", data=data1, files=retry_files)

        # 3. Duplicate re-upload on sequence 2
        data2, files2, _ = build_signed_submission(dev, seq=2, image_bytes=img_bytes)
        client.post("/api/v1/evidence/ingest", data=data2, files=files2)

        # Verify audit logs
        db = SessionMaker()
        audit_events = [l.event_type for l in db.query(AuditLog).all()]
        assert "EVIDENCE_INGESTED" in audit_events
        assert "IDEMPOTENT_RETRY" in audit_events
        assert "DUPLICATE_DETECTED" in audit_events
        db.close()

    def test_background_ai_dispatcher_with_historical_hashes(self, test_env):
        """Verifies background AI dispatcher queries historical hashes from DB and sets duplicate flags."""
        client, SessionMaker = test_env
        dev = register_farmer_device_farm(client, "Dispatcher Farmer")
        img_bytes, img_hash = SyntheticImageGenerator.create_sharp_crop_image(850, 650)


        # Submit image 1
        data1, files1, _ = build_signed_submission(dev, seq=1, image_bytes=img_bytes)
        r1 = client.post("/api/v1/evidence/ingest", data=data1, files=files1)
        task_id_1 = r1.json()["task_id"]

        # Process task 1 in dispatcher (wait for worker thread or execute next task)
        import time
        t1_state = None
        for _ in range(30):
            t1_state = ai_dispatcher.get_task_status(task_id_1)
            if t1_state and t1_state.get("status") == "COMPLETED":
                break
            ai_dispatcher.process_next_task()
            time.sleep(0.1)

        assert t1_state is not None
        assert t1_state["status"] == "COMPLETED"
        assert t1_state["assessment"]["duplicate"]["is_duplicate"] is False

        # Submit exact same image as sequence 2
        data2, files2, _ = build_signed_submission(dev, seq=2, image_bytes=img_bytes)
        r2 = client.post("/api/v1/evidence/ingest", data=data2, files=files2)
        task_id_2 = r2.json()["task_id"]

        # Process task 2 in dispatcher
        t2_state = None
        for _ in range(30):
            t2_state = ai_dispatcher.get_task_status(task_id_2)
            if t2_state and t2_state.get("status") == "COMPLETED":
                break
            ai_dispatcher.process_next_task()
            time.sleep(0.1)

        assert t2_state is not None
        assert t2_state["status"] == "COMPLETED"

        assert t2_state["assessment"]["duplicate"]["is_duplicate"] is True
        assert t2_state["assessment"]["duplicate"]["exact_sha256_match"] is True
        assert t2_state["assessment"]["governance"]["recommended_action"] == "FLAG_FOR_REVIEW"
        assert t2_state["assessment"]["governance"]["state_transition"] == "PENDING_REVIEW"

        # Verify AIAssessment was persisted in DB
        db = SessionMaker()
        assess_2 = db.query(AIAssessment).filter(AIAssessment.evidence_id == r2.json()["evidence_id"]).first()
        assert assess_2 is not None
        assert assess_2.is_duplicate is True
        assert assess_2.sha256 == img_hash.lower()
        db.close()
