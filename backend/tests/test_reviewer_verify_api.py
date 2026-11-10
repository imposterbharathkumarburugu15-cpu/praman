import json
import uuid
import base64
import os
from datetime import datetime, timezone
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
from backend.app.models.ai_assessment import AIAssessment
from backend.app.models.review_decision import ReviewDecision
from backend.app.models.public_token import PublicToken
from backend.app.models.audit_log import AuditLog
from backend.app.services.receipt_signer import (
    get_server_public_key_pem,
    get_server_keypair,
    sign_server_receipt,
    sign_authority_checkpoint,
)
from crypto.ecdsa_p256 import verify, load_public_key
from crypto.rfc8785 import canonicalize
from crypto.merkle import MerkleTree, leaf_hash_hex, verify_merkle_proof


@pytest.fixture(scope="function")
def test_client(tmp_path):
    test_db_path = str(tmp_path / "test_reviewer_verify.db")
    test_engine = create_engine(f"sqlite:///{test_db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client, TestingSessionLocal
    app.dependency_overrides.clear()


def create_sample_evidence(db_session, status="PENDING_REVIEW", crop_type="Cotton"):
    """Helper to seed farmer, device, farm, and evidence in DB."""
    farmer = Farmer(
        id=str(uuid.uuid4()),
        full_name="Ramesh Patel",
        phone_number=f"+91{uuid.uuid4().int % 10000000000:010d}",
        language_pref="te",
    )
    db_session.add(farmer)
    db_session.flush()

    device = Device(
        id=str(uuid.uuid4()),
        farmer_id=farmer.id,
        public_key_pem="-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE\n-----END PUBLIC KEY-----",
        status="ACTIVE",
        last_sequence_number=1,
    )
    db_session.add(device)
    db_session.flush()

    farm = Farm(
        id=str(uuid.uuid4()),
        farmer_id=farmer.id,
        farm_name="Green Acres",
        crop_type=crop_type,
        boundary_geojson='{"type":"Polygon","coordinates":[[[78.48,17.38],[78.49,17.38],[78.49,17.39],[78.48,17.39],[78.48,17.38]]]}',
        area_hectares=2.5,
    )
    db_session.add(farm)
    db_session.flush()

    evidence_id = str(uuid.uuid4())
    envelope = {
        "device_id": device.id,
        "evidence_id": evidence_id,
        "farm_id": farm.id,
        "image_hash": "a" * 64,
        "lifecycle_stage": "CROP_GROWTH",
        "metadata": {
            "capture_source": "CAMERA",
            "capture_timestamp": "2026-11-09T10:30:00Z",
            "gps_accuracy": 4.5,
            "latitude": 17.385044,
            "longitude": 78.486671,
        },
        "schema_version": "1.0",
        "sequence_number": 1,
    }
    canonical_json = canonicalize(envelope).decode("utf-8")

    evidence = Evidence(
        id=evidence_id,
        farm_id=farm.id,
        device_id=device.id,
        sequence_number=1,
        lifecycle_stage="CROP_GROWTH",
        image_hash="a" * 64,
        canonical_envelope_json=canonical_json,
        signature_b64="c2lnbmF0dXJl",
        status=status,
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)
    return evidence


# 1. Reviewer Queue & Filtering Tests
def test_reviewer_queue_empty(test_client):
    client, _ = test_client
    res = client.get("/api/v1/reviewer/queue")
    assert res.status_code == 200
    assert res.json() == []


def test_reviewer_queue_filtering_and_status(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    # Create Cotton pending evidence
    ev_cotton = create_sample_evidence(db, status="PENDING_REVIEW", crop_type="Cotton")
    # Create Paddy pending evidence
    ev_paddy = create_sample_evidence(db, status="PENDING_REVIEW", crop_type="Paddy")
    # Create Approved evidence (should not appear in pending queue)
    ev_approved = create_sample_evidence(db, status="APPROVED", crop_type="Cotton")

    # Fetch all pending
    res = client.get("/api/v1/reviewer/queue")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    item_ids = [item["evidence_id"] for item in items]
    assert ev_cotton.id in item_ids
    assert ev_paddy.id in item_ids
    assert ev_approved.id not in item_ids

    # Filter by Cotton
    res_cotton = client.get("/api/v1/reviewer/queue?filter_crop=Cotton")
    assert res_cotton.status_code == 200
    items_cotton = res_cotton.json()
    assert len(items_cotton) == 1
    assert items_cotton[0]["evidence_id"] == ev_cotton.id
    assert items_cotton[0]["crop_type"] == "Cotton"

    # Filter by Paddy
    res_paddy = client.get("/api/v1/reviewer/queue?filter_crop=Paddy")
    assert res_paddy.status_code == 200
    items_paddy = res_paddy.json()
    assert len(items_paddy) == 1
    assert items_paddy[0]["evidence_id"] == ev_paddy.id
    assert items_paddy[0]["crop_type"] == "Paddy"


def test_reviewer_queue_with_ai_assessment(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    ev = create_sample_evidence(db, status="PENDING_REVIEW", crop_type="Cotton")

    # Add AI assessment flagging blur
    ai = AIAssessment(
        id=str(uuid.uuid4()),
        evidence_id=ev.id,
        blur_score=32.5,
        is_blurry=True,
        exposure_under_pct=0.0,
        exposure_over_pct=0.0,
        is_exposure_valid=True,
        width=1920,
        height=1080,
        is_resolution_valid=True,
        sha256="a" * 64,
        phash="1234567890abcdef",
        nearest_phash_distance=30,
        is_duplicate=False,
        predicted_crop_class="cotton",
        crop_confidence=0.91,
        is_crop_consistent=True,
        recommendation="PENDING_REVIEW",
        assessment_json="{}",
    )
    db.add(ai)
    db.commit()

    res = client.get("/api/v1/reviewer/queue")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["flag_reason"] == "LOW_BLUR_SCORE"
    assert items[0]["ai_assessment"] is not None
    assert items[0]["ai_assessment"]["blur_score"] == 32.5
    assert items[0]["ai_assessment"]["is_blurry"] is True


# 2. Reviewer Decision Tests
def test_reviewer_decision_approve(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    ev = create_sample_evidence(db, status="PENDING_REVIEW")

    decision_payload = {
        "evidence_id": ev.id,
        "decision": "APPROVE",
        "notes": "Verified clear canopy shot.",
        "reviewer_id": "rev-sarah",
    }
    res = client.post("/api/v1/reviewer/decision", json=decision_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "APPROVE"
    assert data["new_state"] == "APPROVED"
    assert data["reviewer_id"] == "rev-sarah"

    # Confirm evidence status in DB
    db.expire_all()
    updated_ev = db.query(Evidence).filter(Evidence.id == ev.id).first()
    assert updated_ev.status == "APPROVED"

    # Confirm ReviewDecision in DB
    dec = db.query(ReviewDecision).filter(ReviewDecision.evidence_id == ev.id).first()
    assert dec is not None
    assert dec.action == "APPROVE"
    assert dec.new_state == "APPROVED"

    # Confirm AuditLog in DB
    audit = db.query(AuditLog).filter(
        AuditLog.entity_id == ev.id,
        AuditLog.event_type == "REVIEWER_DECISION",
    ).first()
    assert audit is not None
    assert audit.new_state == "APPROVED"
    assert audit.previous_state == "PENDING_REVIEW"


def test_reviewer_decision_reject_requires_explanatory_notes(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    ev = create_sample_evidence(db, status="PENDING_REVIEW")

    # Reject without notes -> 400
    res = client.post(
        "/api/v1/reviewer/decision",
        json={"evidence_id": ev.id, "decision": "REJECT", "notes": ""},
    )
    assert res.status_code == 400
    assert "explanatory notes" in res.json()["detail"]

    # Reject with short notes -> 400
    res = client.post(
        "/api/v1/reviewer/decision",
        json={"evidence_id": ev.id, "decision": "REJECT", "notes": "bad"},
    )
    assert res.status_code == 400

    # Reject with valid notes -> 200
    res = client.post(
        "/api/v1/reviewer/decision",
        json={
            "evidence_id": ev.id,
            "decision": "REJECT",
            "notes": "Image appears to be downloaded from internet stock photo.",
            "reviewer_id": "rev-alex",
        },
    )
    assert res.status_code == 200
    assert res.json()["new_state"] == "REJECTED"

    db.expire_all()
    updated = db.query(Evidence).filter(Evidence.id == ev.id).first()
    assert updated.status == "REJECTED"


def test_reviewer_decision_request_retake(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    ev = create_sample_evidence(db, status="PENDING_REVIEW")

    res = client.post(
        "/api/v1/reviewer/decision",
        json={
            "evidence_id": ev.id,
            "decision": "REQUEST_RETAKE",
            "notes": "Lens had excessive blur; please capture under daylight.",
            "reviewer_id": "rev-dan",
        },
    )
    assert res.status_code == 200
    assert res.json()["new_state"] == "RETAKE_REQUESTED"

    # Query decisions endpoint
    res_decisions = client.get(f"/api/v1/reviewer/decisions/{ev.id}")
    assert res_decisions.status_code == 200
    dec_list = res_decisions.json()
    assert len(dec_list) == 1
    assert dec_list[0]["action"] == "REQUEST_RETAKE"


def test_reviewer_decision_nonexistent_evidence(test_client):
    client, _ = test_client
    res = client.post(
        "/api/v1/reviewer/decision",
        json={"evidence_id": "nonexistent-id", "decision": "APPROVE"},
    )
    assert res.status_code == 404


def test_reviewer_inspection_view(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    ev = create_sample_evidence(db, status="PENDING_REVIEW")
    res = client.get(f"/api/v1/reviewer/inspection/{ev.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_id"] == ev.id
    assert "crypto_badge" in data
    assert "quality_card" in data
    assert "duplicate_card" in data


# 3. Public Verification Endpoint Tests
def test_public_token_issuance_and_resolution(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    ev = create_sample_evidence(db, status="APPROVED")

    # Issue token
    res_token = client.post("/api/v1/verify/tokens", json={"evidence_id": ev.id})
    assert res_token.status_code == 201
    token_data = res_token.json()
    token = token_data["token"]
    assert len(token) >= 43

    # Idempotent re-issuance returns same token
    res_idempotent = client.post("/api/v1/verify/tokens", json={"evidence_id": ev.id})
    assert res_idempotent.status_code == 201
    assert res_idempotent.json()["token"] == token

    # Resolve token
    res_verify = client.get(f"/api/v1/verify/{token}")
    assert res_verify.status_code == 200
    payload = res_verify.json()
    assert payload["public_token"] == token
    assert payload["provenance_status"] == "COMMITTED_TO_LEDGER"
    assert payload["crop_type"] == "Cotton"
    assert payload["lifecycle_stage"] == "CROP_GROWTH"
    assert payload["image_sha256"] == ev.image_hash
    assert len(payload["merkle_root"]) == 64
    assert len(payload["leaf_hash"]) == 64
    assert "checkpoint" in payload
    assert payload["checkpoint"]["signer_id"] == "praman-trusted-authority-1"
    assert len(payload["checkpoint"]["signature"]) > 20


def test_public_verification_zero_pii_and_zero_gps_invariants(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    ev = create_sample_evidence(db, status="APPROVED")
    res_token = client.post("/api/v1/verify/tokens", json={"evidence_id": ev.id})
    token = res_token.json()["token"]

    res_verify = client.get(f"/api/v1/verify/{token}")
    assert res_verify.status_code == 200
    payload_str = json.dumps(res_verify.json()).lower()

    # Zero PII check
    for pii in ["farmer_name", "full_name", "phone_number", "aadhar", "national_id", "email", "address", "ramesh"]:
        assert pii not in payload_str, f"PII leakage detected: {pii}"

    # Zero GPS check
    for gps in ["latitude", "longitude", "17.385044", "78.486671", "boundary_geojson", "polygon"]:
        assert gps not in payload_str, f"GPS leakage detected: {gps}"

    # Coarse region check
    assert "adilabad, telangana" in payload_str


def test_public_verification_invalid_token_404(test_client):
    client, _ = test_client
    res = client.get("/api/v1/verify/fabricated_invalid_token_123456789")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_public_proof_verification_endpoint(test_client):
    client, _ = test_client

    envelope = {
        "device_id": str(uuid.uuid4()),
        "evidence_id": str(uuid.uuid4()),
        "farm_id": str(uuid.uuid4()),
        "image_hash": "b" * 64,
        "lifecycle_stage": "HARVEST",
        "metadata": {"capture_source": "CAMERA", "capture_timestamp": "2026-11-09T12:00:00Z"},
        "schema_version": "1.0",
        "sequence_number": 1,
    }
    canonical_leaf = canonicalize(envelope)
    tree = MerkleTree([canonical_leaf])
    proof = tree.get_inclusion_proof(0)

    # Valid proof
    verify_req = {
        "envelope": envelope,
        "inclusion_proof": proof,
        "expected_root": tree.root_hex,
    }
    res = client.post("/api/v1/verify/proof", json=verify_req)
    assert res.status_code == 200
    assert res.json()["valid"] is True

    # Tampered root
    verify_req["expected_root"] = "0" * 64
    res_tampered = client.post("/api/v1/verify/proof", json=verify_req)
    assert res_tampered.status_code == 200
    assert res_tampered.json()["valid"] is False


# 4. Receipt Signing Key Persistence Tests
def test_receipt_signing_key_persistence():
    pub_pem_1 = get_server_public_key_pem()
    assert "-----BEGIN PUBLIC KEY-----" in pub_pem_1

    # Reload keypair and ensure it produces the exact same key
    priv_2, pub_2 = get_server_keypair(force_reload=True)
    pub_pem_2 = get_server_public_key_pem()
    assert pub_pem_1 == pub_pem_2

    # Verify receipt signature validity
    sig_b64 = sign_server_receipt(
        evidence_id="ev-test-1",
        device_id="dev-test-1",
        sequence_number=1,
        image_hash="c" * 64,
        server_timestamp="2026-11-09T18:00:00Z",
    )
    sig_der = base64.b64decode(sig_b64)
    expected_payload = {
        "device_id": "dev-test-1",
        "evidence_id": "ev-test-1",
        "image_hash": "c" * 64,
        "sequence_number": 1,
        "server_timestamp": "2026-11-09T18:00:00Z",
        "status": "DURABLY_ACKED",
    }
    canonical_bytes = canonicalize(expected_payload)
    pub_key = load_public_key(pub_pem_1)
    assert verify(pub_key, sig_der, canonical_bytes) is True
