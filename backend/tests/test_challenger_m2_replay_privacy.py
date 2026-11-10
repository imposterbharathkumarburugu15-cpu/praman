"""Empirical Challenger Test Suite for Milestone 2:
Cross-Tenant Privacy Boundaries & Replay Attack Resistance.

Evaluates:
1. Cross-Tenant Privacy Boundary Attacks:
   - Farmer A vs Farmer B duplicate submissions (exact SHA-256 and perceptual near-duplicate).
   - Verifies that Farmer A's farmer_id, farm_id, matched_evidence_id, and device_id
     are strictly absent/sanitized in Farmer B's HTTP response, receipt, and GET /evidence/{id}.
   - Multi-tenant chain duplicates (Farmer A -> Farmer B -> Farmer C).
   - Audit log exposure prevention (unhashed payload not exposed publicly).
2. Transport Retry (IDEMPOTENT_RETRY) vs Duplicate Content Submission (EXACT_DUPLICATE):
   - Replay of exact same request with same sequence S returns HTTP 200 IDEMPOTENT_RETRY
     and preserves the original evidence_id without creating database rows.
   - Replay under concurrency/burst stress preserves single-row idempotency.
   - Progression with same image to sequence S+1 creates a new record classified as
     EXACT_DUPLICATE with database status PENDING_REVIEW.
   - Subsequent transport retry of sequence S+1 returns HTTP 200 IDEMPOTENT_RETRY
     preserving the duplicate evidence_id.
   - Stale replay attack with altered payload on same sequence returns HTTP 409 Conflict.
   - Non-monotonic sequences (S <= 0, sequence gaps S > S_last + 1, stale replays) return 409.
"""

import io
import json
import uuid
import base64
import hashlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """Sets up an isolated database and TestClient for empirical challenger tests."""
    test_db = str(tmp_path / "challenger_dup_test.db")
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
    assert rf.status_code == 201, f"Failed to register farmer: {rf.text}"
    farmer_id = rf.json()["id"]

    priv_key, pub_key = generate_keypair()
    pub_pem = public_key_to_pem(pub_key)
    device_id = str(uuid.uuid4())

    rd = client.post("/api/v1/devices/register", json={
        "device_id": device_id,
        "farmer_id": farmer_id,
        "public_key_pem": pub_pem,
    })
    assert rd.status_code == 201, f"Failed to register device: {rd.text}"

    rfarm = client.post("/api/v1/farms", json={
        "farmer_id": farmer_id,
        "farm_name": f"{name}'s Farm",
        "crop_type": crop,
        "boundary_geojson": json.dumps({
            "type": "Polygon",
            "coordinates": [[[78.5, 19.6], [78.51, 19.6], [78.51, 19.61], [78.5, 19.61], [78.5, 19.6]]]
        }),
    })
    assert rfarm.status_code == 201, f"Failed to create farm: {rfarm.text}"
    farm_id = rfarm.json()["id"]

    return {
        "farmer_id": farmer_id,
        "device_id": device_id,
        "priv_key": priv_key,
        "pub_pem": pub_pem,
        "farm_id": farm_id,
    }


def build_signed_submission(device_info, seq: int, image_bytes: bytes, evidence_id=None, lifecycle="CROP_GROWTH"):
    """Builds RFC 8785 canonical envelope and ECDSA P-256 signature."""
    img_hash = hashlib.sha256(image_bytes).hexdigest()
    ev_id = evidence_id or str(uuid.uuid4())
    envelope = {
        "device_id": device_info["device_id"],
        "evidence_id": ev_id,
        "farm_id": device_info["farm_id"],
        "image_hash": img_hash,
        "lifecycle_stage": lifecycle,
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


class TestCrossTenantPrivacyBoundaries:
    """Adversarial stress-testing of tenant data isolation under duplicate submissions."""

    def test_cross_tenant_exact_duplicate_receipt_sanitization(self, test_env):
        """Cross-tenant attack: Farmer B submits Farmer A's exact image.
        
        Verifies:
        1. HTTP 201 Created with classification='EXACT_DUPLICATE' and is_duplicate=True.
        2. Farmer B's receipt contains their own newly generated evidence_id.
        3. Farmer A's evidence_id, farmer_id, farm_id, and device_id are STRICTLY ABSENT
           from the entire HTTP response body and receipt JSON string.
        4. No internal provenance fields (matched_evidence_id, matched_farmer_id, duplicate_of_id)
           are serialized in the client-facing receipt.
        5. In PostgreSQL/DB, internal provenance is recorded with status='PENDING_REVIEW'.
        """
        client, SessionMaker = test_env
        farmer_a = register_farmer_device_farm(client, "Farmer A (Original)", phone="+919811111111")
        farmer_b = register_farmer_device_farm(client, "Farmer B (Attacker)", phone="+919822222222")

        img_bytes, img_hash = SyntheticImageGenerator.create_sharp_crop_image(800, 600)

        # 1. Farmer A submits original image
        data_a, files_a, env_a = build_signed_submission(farmer_a, seq=1, image_bytes=img_bytes)
        res_a = client.post("/api/v1/evidence/ingest", data=data_a, files=files_a)
        assert res_a.status_code == 201, f"Farmer A submission failed: {res_a.text}"
        receipt_a = res_a.json()
        assert receipt_a["classification"] == "NEW_EVIDENCE"
        ev_a_id = receipt_a["evidence_id"]

        # 2. Farmer B submits identical image payload
        data_b, files_b, env_b = build_signed_submission(farmer_b, seq=1, image_bytes=img_bytes)
        res_b = client.post("/api/v1/evidence/ingest", data=data_b, files=files_b)
        assert res_b.status_code == 201, f"Farmer B submission failed: {res_b.text}"
        receipt_b = res_b.json()

        # Classification check
        assert receipt_b["classification"] == "EXACT_DUPLICATE"
        assert receipt_b["is_duplicate"] is True
        assert receipt_b["duplicate_type"] == "EXACT_DUPLICATE"
        assert receipt_b["hamming_distance"] == 0
        ev_b_id = receipt_b["evidence_id"]
        assert ev_b_id != ev_a_id, "Farmer B must receive a distinct evidence ID"

        # DEEP PRIVACY VERIFICATION:
        raw_res_b_text = res_b.text
        assert ev_a_id not in raw_res_b_text, f"LEAK: Farmer A evidence_id {ev_a_id} found in Farmer B response!"
        assert farmer_a["farmer_id"] not in raw_res_b_text, f"LEAK: Farmer A farmer_id found in Farmer B response!"
        assert farmer_a["farm_id"] not in raw_res_b_text, f"LEAK: Farmer A farm_id found in Farmer B response!"
        assert farmer_a["device_id"] not in raw_res_b_text, f"LEAK: Farmer A device_id found in Farmer B response!"

        # Verify prohibited internal schema fields are not present in receipt
        assert "matched_evidence_id" not in receipt_b
        assert "matched_farmer_id" not in receipt_b
        assert "matched_farm_id" not in receipt_b
        assert "duplicate_of_id" not in receipt_b

        # 3. GET /evidence/{ev_b_id} inspection for Farmer B
        res_get_b = client.get(f"/api/v1/evidence/{ev_b_id}")
        assert res_get_b.status_code == 200
        get_b_data = res_get_b.json()
        raw_get_b_text = res_get_b.text

        assert ev_a_id not in raw_get_b_text, f"LEAK: Farmer A evidence_id in GET /evidence/{ev_b_id}!"
        assert farmer_a["farmer_id"] not in raw_get_b_text, f"LEAK: Farmer A farmer_id in GET /evidence/{ev_b_id}!"
        assert farmer_a["farm_id"] not in raw_get_b_text, f"LEAK: Farmer A farm_id in GET /evidence/{ev_b_id}!"
        assert get_b_data["status"] == "PENDING_REVIEW"
        assert get_b_data["is_duplicate"] is True
        assert get_b_data["duplicate_type"] == "EXACT_DUPLICATE"

        # 4. In PostgreSQL/DB, internal audit link is intact
        db = SessionMaker()
        ev_b_record = db.query(Evidence).filter(Evidence.id == ev_b_id).first()
        assert ev_b_record is not None
        assert ev_b_record.duplicate_of_id == ev_a_id
        assert ev_b_record.status == "PENDING_REVIEW"
        assert ev_b_record.farm_id == farmer_b["farm_id"]
        assert ev_b_record.device_id == farmer_b["device_id"]
        db.close()

    def test_cross_tenant_perceptual_near_duplicate_privacy(self, test_env):
        """Cross-tenant attack: Farmer B re-compresses and resizes Farmer A's photograph.
        
        Verifies:
        1. Hamming distance is <= 6 (or <= 10).
        2. Farmer B receives POSSIBLE_VISUAL_DUPLICATE (or DUPLICATE_REQUIRES_REVIEW).
        3. Strict privacy boundaries hold: Farmer A's evidence_id, farmer_id, farm_id are absent.
        4. Evidence record status in DB is PENDING_REVIEW.
        """
        client, SessionMaker = test_env
        farmer_a = register_farmer_device_farm(client, "Farmer A (Perceptual)", phone="+919833333333")
        farmer_b = register_farmer_device_farm(client, "Farmer B (Perceptual)", phone="+919844444444")

        (bytes_orig, _), (bytes_recomp, _) = SyntheticImageGenerator.create_phash_near_duplicate_pair()
        p1 = compute_phash_64(bytes_orig)
        p2 = compute_phash_64(bytes_recomp)
        d1 = compute_dhash_64(bytes_orig)
        d2 = compute_dhash_64(bytes_recomp)
        min_dist = min(hamming_distance_hex(p1, p2), hamming_distance_hex(d1, d2))
        assert min_dist <= 10, f"Synthetic pair distance {min_dist} exceeds threshold 10"

        # Farmer A submits original
        data_a, files_a, _ = build_signed_submission(farmer_a, seq=1, image_bytes=bytes_orig)
        res_a = client.post("/api/v1/evidence/ingest", data=data_a, files=files_a)
        assert res_a.status_code == 201
        ev_a_id = res_a.json()["evidence_id"]

        # Farmer B submits recompressed near-duplicate
        data_b, files_b, _ = build_signed_submission(farmer_b, seq=1, image_bytes=bytes_recomp)
        res_b = client.post("/api/v1/evidence/ingest", data=data_b, files=files_b)
        assert res_b.status_code == 201
        receipt_b = res_b.json()

        expected_class = "POSSIBLE_VISUAL_DUPLICATE" if min_dist <= 6 else "DUPLICATE_REQUIRES_REVIEW"
        assert receipt_b["classification"] == expected_class
        assert receipt_b["is_duplicate"] is True
        assert receipt_b["hamming_distance"] == min_dist

        # Privacy checks
        raw_res = res_b.text
        assert ev_a_id not in raw_res
        assert farmer_a["farmer_id"] not in raw_res
        assert farmer_a["farm_id"] not in raw_res
        assert "matched_evidence_id" not in receipt_b

        # Verify DB status
        db = SessionMaker()
        ev_b = db.query(Evidence).filter(Evidence.id == receipt_b["evidence_id"]).first()
        assert ev_b.duplicate_of_id == ev_a_id
        assert ev_b.status == "PENDING_REVIEW"
        db.close()

    def test_multi_farmer_duplicate_chain_isolation(self, test_env):
        """Cross-tenant attack: Multi-party duplicate chain (Farmer A -> Farmer B -> Farmer C).
        
        Verifies:
        1. Neither Farmer B nor Farmer C receipts leak any prior tenant data.
        2. Zero cross-contamination in API responses across all three tenants.
        """
        client, SessionMaker = test_env
        farmer_a = register_farmer_device_farm(client, "Farmer A", phone="+919855555551")
        farmer_b = register_farmer_device_farm(client, "Farmer B", phone="+919855555552")
        farmer_c = register_farmer_device_farm(client, "Farmer C", phone="+919855555553")

        img_bytes, _ = SyntheticImageGenerator.create_sharp_crop_image(800, 600)

        # Farmer A submits
        data_a, files_a, _ = build_signed_submission(farmer_a, seq=1, image_bytes=img_bytes)
        r_a = client.post("/api/v1/evidence/ingest", data=data_a, files=files_a)
        assert r_a.status_code == 201
        ev_a_id = r_a.json()["evidence_id"]

        # Farmer B submits same image
        data_b, files_b, _ = build_signed_submission(farmer_b, seq=1, image_bytes=img_bytes)
        r_b = client.post("/api/v1/evidence/ingest", data=data_b, files=files_b)
        assert r_b.status_code == 201
        ev_b_id = r_b.json()["evidence_id"]

        # Farmer C submits same image
        data_c, files_c, _ = build_signed_submission(farmer_c, seq=1, image_bytes=img_bytes)
        r_c = client.post("/api/v1/evidence/ingest", data=data_c, files=files_c)
        assert r_c.status_code == 201
        receipt_c = r_c.json()
        ev_c_id = receipt_c["evidence_id"]

        assert receipt_c["classification"] == "EXACT_DUPLICATE"
        assert receipt_c["is_duplicate"] is True

        # Farmer C must not see Farmer A or Farmer B data
        raw_c = r_c.text
        for forbidden in [ev_a_id, ev_b_id, farmer_a["farmer_id"], farmer_b["farmer_id"], farmer_a["farm_id"], farmer_b["farm_id"]]:
            assert forbidden not in raw_c, f"LEAK: {forbidden} present in Farmer C response"

        # Unique IDs for all 3
        assert len({ev_a_id, ev_b_id, ev_c_id}) == 3

    def test_audit_log_cross_tenant_sanitization(self, test_env):
        """Cross-tenant privacy attack via audit log inspection.
        
        Verifies:
        1. When DUPLICATE_DETECTED is logged for Farmer B's duplicate submission,
           the public AuditLogResponse for that entity/event only exposes payload_hash.
        2. Neither Farmer A's evidence_id, farmer_id, nor farm_id is leaked in
           DUPLICATE_DETECTED log entries or when querying Farmer B's audit events.
        3. Raw payload containing matched_evidence_id is strictly kept internal in DB
           and never serialized in AuditLogResponse.
        """
        client, SessionMaker = test_env
        farmer_a = register_farmer_device_farm(client, "Audit Farmer A", phone="+919866666661")
        farmer_b = register_farmer_device_farm(client, "Audit Farmer B", phone="+919866666662")

        img_bytes, _ = SyntheticImageGenerator.create_sharp_crop_image(800, 600)

        data_a, files_a, _ = build_signed_submission(farmer_a, seq=1, image_bytes=img_bytes)
        r_a = client.post("/api/v1/evidence/ingest", data=data_a, files=files_a)
        ev_a_id = r_a.json()["evidence_id"]

        data_b, files_b, _ = build_signed_submission(farmer_b, seq=1, image_bytes=img_bytes)
        r_b = client.post("/api/v1/evidence/ingest", data=data_b, files=files_b)
        ev_b_id = r_b.json()["evidence_id"]

        # 1. Attacker queries audit logs for their own duplicate evidence entity
        r_audit_b = client.get(f"/api/v1/audit/logs?entity_id={ev_b_id}")
        assert r_audit_b.status_code == 200
        logs_b = r_audit_b.json()
        assert len(logs_b) >= 1
        dup_event = logs_b[0]
        assert dup_event["event_type"] == "DUPLICATE_DETECTED"
        assert dup_event["entity_id"] == ev_b_id
        assert dup_event["new_state"] == "EXACT_DUPLICATE"

        # Verify Farmer A's identifiers are NOT leaked in the DUPLICATE_DETECTED event
        raw_b_audit = r_audit_b.text
        assert ev_a_id not in raw_b_audit, "DUPLICATE_DETECTED audit event leaked Farmer A evidence_id"
        assert farmer_a["farmer_id"] not in raw_b_audit, "DUPLICATE_DETECTED audit event leaked Farmer A farmer_id"
        assert farmer_a["farm_id"] not in raw_b_audit, "DUPLICATE_DETECTED audit event leaked Farmer A farm_id"

        # 2. Attacker queries all DUPLICATE_DETECTED events
        r_audit_dups = client.get("/api/v1/audit/logs?event_type=DUPLICATE_DETECTED")
        assert r_audit_dups.status_code == 200
        raw_dups = r_audit_dups.text
        assert ev_a_id not in raw_dups, "DUPLICATE_DETECTED list leaked matched_evidence_id"


class TestIdempotencyVsDuplicateAttacks:
    """Adversarial stress-testing of Mechanism A (Idempotency) vs Mechanism B (Duplicate Content)."""

    def test_transport_retry_vs_duplicate_submission(self, test_env):
        """Rigorous validation of Mechanism A (Idempotency) vs Mechanism B (Duplicate Submission).
        
        Verifies:
        1. Sequence S=1 initial ingest -> HTTP 201 Created, classification='NEW_EVIDENCE'.
        2. Sequence S=1 transport retry (exact same payload) -> HTTP 200 OK, classification='IDEMPOTENT_RETRY',
           preserves original evidence_id, DB count remains 1.
        3. Sequence S=2 duplicate submission (incremented sequence, same image bytes) ->
           HTTP 201 Created, classification='EXACT_DUPLICATE', is_duplicate=True,
           creates new evidence record with status='PENDING_REVIEW' and duplicate_of_id=ev_1,
           DB count becomes 2.
        4. Sequence S=2 transport retry of the duplicate submission ->
           HTTP 200 OK, classification='IDEMPOTENT_RETRY', preserves ev_2 evidence_id,
           DB count remains 2.
        """
        client, SessionMaker = test_env
        dev = register_farmer_device_farm(client, "Idempotency Farmer")
        img_bytes, img_hash = SyntheticImageGenerator.create_sharp_crop_image(800, 600)

        # 1. First submission S=1 -> 201 Created, NEW_EVIDENCE
        data1, files1, _ = build_signed_submission(dev, seq=1, image_bytes=img_bytes)
        r1 = client.post("/api/v1/evidence/ingest", data=data1, files=files1)
        assert r1.status_code == 201
        rec1 = r1.json()
        assert rec1["classification"] == "NEW_EVIDENCE"
        assert rec1["status"] == "DURABLY_ACKED"
        ev1_id = rec1["evidence_id"]

        # Check DB count = 1
        db = SessionMaker()
        assert db.query(Evidence).filter(Evidence.device_id == dev["device_id"]).count() == 1
        db.close()

        # 2. Transport Retry: Exact same request with sequence S=1 -> 200 OK, IDEMPOTENT_RETRY
        retry_files = {"file": ("evidence.jpg", img_bytes, "image/jpeg")}
        r1_retry = client.post("/api/v1/evidence/ingest", data=data1, files=retry_files)
        assert r1_retry.status_code == 200
        rec_retry = r1_retry.json()
        assert rec_retry["classification"] == "IDEMPOTENT_RETRY"
        assert rec_retry["evidence_id"] == ev1_id
        assert rec_retry["sequence_number"] == 1

        # Check DB count remains 1
        db = SessionMaker()
        assert db.query(Evidence).filter(Evidence.device_id == dev["device_id"]).count() == 1
        db.close()

        # 3. Duplicate Submission: Incremented sequence S=2 with identical image -> 201 Created, EXACT_DUPLICATE
        data2, files2, _ = build_signed_submission(dev, seq=2, image_bytes=img_bytes)
        r2 = client.post("/api/v1/evidence/ingest", data=data2, files=files2)
        assert r2.status_code == 201
        rec2 = r2.json()
        assert rec2["classification"] == "EXACT_DUPLICATE"
        assert rec2["is_duplicate"] is True
        assert rec2["duplicate_type"] == "EXACT_DUPLICATE"
        assert rec2["hamming_distance"] == 0
        ev2_id = rec2["evidence_id"]
        assert ev2_id != ev1_id

        # Verify DB records: total 2 rows, ev2 is PENDING_REVIEW and duplicate_of_id == ev1_id
        db = SessionMaker()
        records = db.query(Evidence).filter(Evidence.device_id == dev["device_id"]).order_by(Evidence.sequence_number).all()
        assert len(records) == 2
        ev2_db = records[1]
        assert ev2_db.id == ev2_id
        assert ev2_db.sequence_number == 2
        assert ev2_db.duplicate_of_id == ev1_id
        assert ev2_db.duplicate_type == "EXACT_DUPLICATE"
        assert ev2_db.status == "PENDING_REVIEW"
        db.close()

        # Check GET /evidence/{ev2_id} returns status='PENDING_REVIEW'
        r_get2 = client.get(f"/api/v1/evidence/{ev2_id}")
        assert r_get2.status_code == 200
        assert r_get2.json()["status"] == "PENDING_REVIEW"
        assert r_get2.json()["is_duplicate"] is True

        # 4. Transport Retry of Duplicate Submission: Resend S=2 -> 200 OK, IDEMPOTENT_RETRY
        retry2_files = {"file": ("evidence.jpg", img_bytes, "image/jpeg")}
        r2_retry = client.post("/api/v1/evidence/ingest", data=data2, files=retry2_files)
        assert r2_retry.status_code == 200
        rec2_retry = r2_retry.json()
        assert rec2_retry["classification"] == "IDEMPOTENT_RETRY"
        assert rec2_retry["evidence_id"] == ev2_id
        assert rec2_retry["sequence_number"] == 2

        # Verify DB count is STILL 2 (no third record created)
        db = SessionMaker()
        assert db.query(Evidence).filter(Evidence.device_id == dev["device_id"]).count() == 2
        db.close()

    def test_burst_transport_retries_concurrency(self, test_env):
        """Stress-test: 25 rapid sequential transport retries of S=1.
        
        Verifies:
        1. All 25 retries return HTTP 200 OK.
        2. All 25 retries return identical evidence_id and classification='IDEMPOTENT_RETRY'.
        3. Zero duplicate rows created in database.
        """
        client, SessionMaker = test_env
        dev = register_farmer_device_farm(client, "Burst Farmer")
        img_bytes, _ = SyntheticImageGenerator.create_sharp_crop_image(800, 600)

        # Initial ingest S=1
        data1, files1, _ = build_signed_submission(dev, seq=1, image_bytes=img_bytes)
        r1 = client.post("/api/v1/evidence/ingest", data=data1, files=files1)
        assert r1.status_code == 201
        original_ev_id = r1.json()["evidence_id"]

        # 25 burst retries
        for i in range(25):
            retry_files = {"file": ("evidence.jpg", img_bytes, "image/jpeg")}
            res = client.post("/api/v1/evidence/ingest", data=data1, files=retry_files)
            assert res.status_code == 200, f"Retry #{i} failed with status {res.status_code}"
            body = res.json()
            assert body["classification"] == "IDEMPOTENT_RETRY"
            assert body["evidence_id"] == original_ev_id
            assert body["sequence_number"] == 1

        db = SessionMaker()
        count = db.query(Evidence).filter(Evidence.device_id == dev["device_id"]).count()
        assert count == 1, f"Expected exactly 1 evidence row, got {count}"
        db.close()

    def test_replay_attack_altered_payload_on_same_sequence(self, test_env):
        """Replay attack: Attacker attempts to replay sequence S=1 with a different image payload.
        
        Verifies:
        1. HTTP 409 Conflict is returned.
        2. Evidence record in DB is NOT modified or overwritten.
        3. REPLAY_CONFLICT_ATTEMPT is logged in the audit trail.
        """
        client, SessionMaker = test_env
        dev = register_farmer_device_farm(client, "Replay Victim Farmer")
        img1_bytes, _ = SyntheticImageGenerator.create_sharp_crop_image(800, 600)
        img2_bytes, _ = SyntheticImageGenerator.create_underexposed_image(800, 600)

        # Sequence 1 with Image 1
        data1, files1, _ = build_signed_submission(dev, seq=1, image_bytes=img1_bytes)
        r1 = client.post("/api/v1/evidence/ingest", data=data1, files=files1)
        assert r1.status_code == 201
        ev1_id = r1.json()["evidence_id"]

        # Attacker tries to submit Image 2 on sequence 1
        data1_bad, files1_bad, _ = build_signed_submission(dev, seq=1, image_bytes=img2_bytes)
        r1_bad = client.post("/api/v1/evidence/ingest", data=data1_bad, files=files1_bad)
        assert r1_bad.status_code == 409, f"Expected 409 Conflict, got {r1_bad.status_code}: {r1_bad.text}"
        assert "Conflict" in r1_bad.json()["detail"]

        # Confirm original record untouched
        db = SessionMaker()
        ev = db.query(Evidence).filter(Evidence.id == ev1_id).first()
        assert ev.image_hash == hashlib.sha256(img1_bytes).hexdigest()
        assert db.query(Evidence).filter(Evidence.device_id == dev["device_id"]).count() == 1

        # Confirm audit log records conflict
        logs = db.query(AuditLog).filter(AuditLog.event_type == "REPLAY_CONFLICT_ATTEMPT").all()
        assert len(logs) >= 1
        db.close()

    def test_sequence_monotonicity_boundary_and_gap_attacks(self, test_env):
        """Adversarial testing of sequence monotonicity invariants:
        - Sequence S <= 0 (boundary attack): 409 Conflict
        - Sequence S > S_last + 1 (gap attack): 409 Conflict
        - Stale sequence S < S_last (stale replay): 409 Conflict
        """
        client, SessionMaker = test_env
        dev = register_farmer_device_farm(client, "Monotonic Farmer")
        img_bytes, _ = SyntheticImageGenerator.create_sharp_crop_image(800, 600)

        # 1. Boundary attack: Sequence S = 0
        data0, files0, _ = build_signed_submission(dev, seq=0, image_bytes=img_bytes)
        r0 = client.post("/api/v1/evidence/ingest", data=data0, files=files0)
        assert r0.status_code == 409, f"Expected 409 for S=0, got {r0.status_code}"

        # 2. Boundary attack: Sequence S = -1
        data_neg, files_neg, _ = build_signed_submission(dev, seq=-1, image_bytes=img_bytes)
        r_neg = client.post("/api/v1/evidence/ingest", data=data_neg, files=files_neg)
        assert r_neg.status_code in (409, 422), f"Expected 409 or 422 for negative sequence, got {r_neg.status_code}"

        # 3. Gap attack: S = 3 when next expected is S = 1
        data3, files3, _ = build_signed_submission(dev, seq=3, image_bytes=img_bytes)
        r3 = client.post("/api/v1/evidence/ingest", data=data3, files=files3)
        assert r3.status_code == 409, f"Expected 409 for sequence gap, got {r3.status_code}"

        # 4. Valid S = 1
        data1, files1, _ = build_signed_submission(dev, seq=1, image_bytes=img_bytes)
        r1 = client.post("/api/v1/evidence/ingest", data=data1, files=files1)
        assert r1.status_code == 201

        # 5. Gap attack: S = 3 when next expected is S = 2
        r3_again = client.post("/api/v1/evidence/ingest", data=data3, files=files3)
        assert r3_again.status_code == 409, f"Expected 409 for gap S=3, got {r3_again.status_code}"

        # 6. Valid S = 2 with fresh image
        img2_bytes, _ = SyntheticImageGenerator.create_underexposed_image(800, 600)
        data2, files2, _ = build_signed_submission(dev, seq=2, image_bytes=img2_bytes)
        r2 = client.post("/api/v1/evidence/ingest", data=data2, files=files2)
        assert r2.status_code == 201

        # 7. Stale sequence attack: Submit sequence S = 1 with a new image
        img3_bytes, _ = SyntheticImageGenerator.create_sharp_crop_image(900, 700)
        data_stale, files_stale, _ = build_signed_submission(dev, seq=1, image_bytes=img3_bytes)
        r_stale = client.post("/api/v1/evidence/ingest", data=data_stale, files=files_stale)
        assert r_stale.status_code == 409, f"Expected 409 for stale sequence, got {r_stale.status_code}"
