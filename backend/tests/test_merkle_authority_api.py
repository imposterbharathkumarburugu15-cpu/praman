"""Comprehensive integration and cryptographic tests for Merkle Batching and Authority Checkpoints."""

import json
import uuid
import base64
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
from backend.app.models.merkle_batch import MerkleBatch
from backend.app.services.merkle_service import MerkleService
from crypto.authority import (
    get_authority_keypair,
    get_authority_public_key_pem,
    sign_checkpoint,
    verify_checkpoint_signature,
    create_signed_checkpoint,
)
from crypto.rfc8785 import canonicalize
from crypto.merkle import MerkleTree, leaf_hash_hex, verify_merkle_proof
from web_console.public_verify.portal import PublicVerificationPortal
from web_console.ledger.merkle_anchor import MerkleBatchEngine


@pytest.fixture(scope="function")
def test_client(tmp_path):
    test_db_path = str(tmp_path / "test_merkle_authority.db")
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


def seed_evidence_item(
    db_session,
    status="APPROVED",
    lifecycle_stage="CROP_GROWTH",
    crop_type="Cotton",
    seq=1,
) -> Evidence:
    """Helper to seed farmer, device, farm, and an evidence record."""
    farmer = Farmer(
        id=str(uuid.uuid4()),
        full_name=f"Farmer {uuid.uuid4().hex[:6]}",
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
        last_sequence_number=seq,
    )
    db_session.add(device)
    db_session.flush()

    farm = Farm(
        id=str(uuid.uuid4()),
        farmer_id=farmer.id,
        farm_name=f"Farm {uuid.uuid4().hex[:6]}",
        crop_type=crop_type,
        boundary_geojson='{"type":"Polygon","coordinates":[[[78.48,17.38],[78.49,17.38],[78.49,17.39],[78.48,17.39],[78.48,17.38]]]}',
        area_hectares=3.0,
    )
    db_session.add(farm)
    db_session.flush()

    evidence_id = str(uuid.uuid4())
    img_hash = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"[:64]
    envelope = {
        "device_id": device.id,
        "evidence_id": evidence_id,
        "farm_id": farm.id,
        "image_hash": img_hash,
        "lifecycle_stage": lifecycle_stage,
        "metadata": {
            "capture_source": "CAMERA",
            "capture_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gps_accuracy": 3.5,
            "latitude": 17.385044,
            "longitude": 78.486671,
        },
        "schema_version": "1.0",
        "sequence_number": seq,
    }
    canonical_json = canonicalize(envelope).decode("utf-8")

    evidence = Evidence(
        id=evidence_id,
        farm_id=farm.id,
        device_id=device.id,
        sequence_number=seq,
        lifecycle_stage=lifecycle_stage,
        image_hash=img_hash,
        canonical_envelope_json=canonical_json,
        signature_b64="dGVzdF9zaWduYXR1cmU=",
        status=status,
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)
    return evidence


# 1. Authority Key & Checkpoint Signing Tests
def test_authority_key_management_and_signature_verification():
    pub_pem = get_authority_public_key_pem()
    assert "-----BEGIN PUBLIC KEY-----" in pub_pem

    checkpoint = {
        "checkpoint_id": "cp-20261109-unit-1",
        "batch_id": "batch-unit-1",
        "merkle_root": "f" * 64,
        "leaf_count": 7,
        "timestamp": "2026-11-09T18:00:00Z",
        "authority_id": "praman-root-authority-1",
    }
    sig = sign_checkpoint(checkpoint)
    assert isinstance(sig, str) and len(sig) > 40

    # Valid verification
    assert verify_checkpoint_signature(checkpoint, sig) is True

    # Tampered root fails
    tampered_root = {**checkpoint, "merkle_root": "0" * 64}
    assert verify_checkpoint_signature(tampered_root, sig) is False

    # Tampered leaf_count fails
    tampered_leaf = {**checkpoint, "leaf_count": 8}
    assert verify_checkpoint_signature(tampered_leaf, sig) is False


# 2. Merkle Batch Trigger Endpoint Tests
def test_merkle_batch_api_empty_approved_returns_400(test_client):
    client, _ = test_client
    res = client.post("/api/v1/merkle/batch", json={})
    assert res.status_code == 400
    assert "no unbatched approved evidence" in res.json()["detail"].lower()


def test_merkle_batch_api_single_item(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    ev = seed_evidence_item(db, status="APPROVED")
    res = client.post("/api/v1/merkle/batch", json={})
    assert res.status_code == 201

    data = res.json()
    assert "batch_id" in data
    assert data["leaf_count"] == 1
    assert data["evidence_ids"] == [ev.id]
    assert data["status"] == "COMMITTED_TO_LEDGER"

    # Single leaf root must match leaf hash
    env = json.loads(ev.canonical_envelope_json)
    expected_leaf_hash = leaf_hash_hex(canonicalize(env))
    assert data["merkle_root"] == expected_leaf_hash

    # Checkpoint signature must be cryptographically valid
    checkpoint = data["checkpoint"]
    assert verify_checkpoint_signature(checkpoint, data["checkpoint_signature"]) is True

    # DB evidence status must be updated
    db.expire_all()
    ev_updated = db.query(Evidence).filter(Evidence.id == ev.id).first()
    assert ev_updated.status == "COMMITTED_TO_LEDGER"


def test_merkle_batch_api_multi_item_odd_promotion(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    ev1 = seed_evidence_item(db, status="APPROVED", seq=1)
    ev2 = seed_evidence_item(db, status="APPROVED", seq=2)
    ev3 = seed_evidence_item(db, status="APPROVED", seq=3)

    res = client.post("/api/v1/merkle/batch", json={})
    assert res.status_code == 201

    data = res.json()
    assert data["leaf_count"] == 3
    assert set(data["evidence_ids"]) == {ev1.id, ev2.id, ev3.id}

    # Verify root against independent MerkleTree computation
    ordered_records = [
        db.query(Evidence).filter(Evidence.id == eid).first()
        for eid in data["evidence_ids"]
    ]
    leaves = [canonicalize(json.loads(r.canonical_envelope_json)) for r in ordered_records]
    expected_tree = MerkleTree(leaves)
    assert data["merkle_root"] == expected_tree.root_hex

    # Verify signature
    assert verify_checkpoint_signature(data["checkpoint"]) is True


def test_merkle_batch_api_explicit_evidence_ids(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    ev1 = seed_evidence_item(db, status="APPROVED")
    ev2 = seed_evidence_item(db, status="APPROVED")
    ev3 = seed_evidence_item(db, status="APPROVED")

    # Batch only ev1 and ev3
    req_body = {"evidence_ids": [ev1.id, ev3.id]}
    res = client.post("/api/v1/merkle/batch", json=req_body)
    assert res.status_code == 201
    data = res.json()
    assert data["leaf_count"] == 2
    assert data["evidence_ids"] == [ev1.id, ev3.id]

    # Re-batching already committed evidence fails
    res_rebatch = client.post("/api/v1/merkle/batch", json={"evidence_ids": [ev1.id]})
    assert res_rebatch.status_code == 400
    assert "already committed" in res_rebatch.json()["detail"].lower()

    # ev2 should still be unbatched
    unbatched = MerkleService.get_unbatched_approved_evidence(db)
    assert len(unbatched) == 1
    assert unbatched[0].id == ev2.id


# 3. Batch Listing & Retrieval Tests
def test_get_merkle_batches_list_and_detail(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    # Create 2 batches
    seed_evidence_item(db, status="APPROVED")
    client.post("/api/v1/merkle/batch", json={})

    seed_evidence_item(db, status="APPROVED")
    res_b2 = client.post("/api/v1/merkle/batch", json={})
    batch_2_id = res_b2.json()["batch_id"]

    # List batches
    res_list = client.get("/api/v1/merkle/batches")
    assert res_list.status_code == 200
    batches = res_list.json()
    assert len(batches) == 2

    # Pagination
    res_page = client.get("/api/v1/merkle/batches?skip=0&limit=1")
    assert res_page.status_code == 200
    assert len(res_page.json()) == 1

    # Get specific batch
    res_detail = client.get(f"/api/v1/merkle/batches/{batch_2_id}")
    assert res_detail.status_code == 200
    assert res_detail.json()["batch_id"] == batch_2_id


# 4. Merkle Inclusion Proof & Independent Verification Tests
def test_get_evidence_inclusion_proof_and_independent_validation(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    # Create a batch with 4 items
    ev_items = [seed_evidence_item(db, status="APPROVED", seq=i+1) for i in range(4)]
    res_batch = client.post("/api/v1/merkle/batch", json={})
    assert res_batch.status_code == 201
    batch_data = res_batch.json()
    root_hex = batch_data["merkle_root"]

    # Test inclusion proof for each evidence item
    for ev in ev_items:
        res_proof = client.get(f"/api/v1/merkle/proof/{ev.id}")
        assert res_proof.status_code == 200
        proof_data = res_proof.json()

        assert proof_data["evidence_id"] == ev.id
        assert proof_data["merkle_root"] == root_hex
        assert proof_data["status"] == "COMMITTED_TO_LEDGER"

        # Independent proof verification
        canonical_leaf = canonicalize(json.loads(ev.canonical_envelope_json))
        assert proof_data["leaf_hash"] == leaf_hash_hex(canonical_leaf)

        is_valid = verify_merkle_proof(
            leaf_data=canonical_leaf,
            proof=proof_data["inclusion_proof"],
            expected_root=root_hex,
        )
        assert is_valid is True

        # Tampered leaf payload fails
        tampered_leaf = canonical_leaf + b"tamper"
        assert verify_merkle_proof(tampered_leaf, proof_data["inclusion_proof"], root_hex) is False

        # Tampered root fails
        assert verify_merkle_proof(canonical_leaf, proof_data["inclusion_proof"], "0" * 64) is False

        # Embedded checkpoint is genuinely signed
        assert verify_checkpoint_signature(proof_data["checkpoint"]) is True


def test_get_evidence_inclusion_proof_404_cases(test_client):
    client, SessionLocal = test_client
    db = SessionLocal()

    # 1. Nonexistent evidence
    res_nonexistent = client.get("/api/v1/merkle/proof/nonexistent-id")
    assert res_nonexistent.status_code == 404

    # 2. Existing evidence, not yet batched
    ev = seed_evidence_item(db, status="APPROVED")
    res_unbatched = client.get(f"/api/v1/merkle/proof/{ev.id}")
    assert res_unbatched.status_code == 404
    assert "not found" in res_unbatched.json()["detail"].lower()


# 5. Authority Key Endpoint Test
def test_authority_key_endpoint(test_client):
    client, _ = test_client
    res = client.get("/api/v1/merkle/authority-key")
    assert res.status_code == 200
    data = res.json()
    assert data["authority_id"] == "praman-root-authority-1"
    assert data["algorithm"] == "ECDSA-SHA256-P256"
    assert data["public_key_pem"] == get_authority_public_key_pem()


# 6. Web Console Integration & Genuine Signature Verification
def test_web_console_portal_genuine_signature_verification():
    envelope = {
        "device_id": str(uuid.uuid4()),
        "evidence_id": str(uuid.uuid4()),
        "farm_id": str(uuid.uuid4()),
        "image_hash": "c" * 64,
        "lifecycle_stage": "HARVEST",
        "metadata": {
            "capture_source": "CAMERA",
            "capture_timestamp": "2026-11-09T14:00:00Z",
            "gps_accuracy": 4.0,
            "latitude": 17.385044,
            "longitude": 78.486671,
        },
        "schema_version": "1.0",
        "sequence_number": 1,
    }
    canonical_leaf = canonicalize(envelope)
    tree = MerkleTree([canonical_leaf])

    payload = PublicVerificationPortal.sanitize_public_payload(
        envelope=envelope,
        tree=tree,
        leaf_index=0,
        public_token="test-token-123",
    )

    # Ensure mock signature string is completely eliminated
    assert payload["checkpoint"]["signature"] != "MOCK_CHECKPOINT_AUTHORITY_SIG"
    assert len(payload["checkpoint"]["signature"]) > 40

    # Genuine verification passes
    is_valid = PublicVerificationPortal.verify_public_payload(payload=payload, envelope=envelope)
    assert is_valid is True

    # Tampered envelope fails
    tampered_envelope = {**envelope, "lifecycle_stage": "SOWING"}
    assert PublicVerificationPortal.verify_public_payload(payload=payload, envelope=tampered_envelope) is False


def test_web_console_ledger_anchor_genuine_signature_verification():
    envelopes = [
        {
            "device_id": str(uuid.uuid4()),
            "evidence_id": str(uuid.uuid4()),
            "farm_id": str(uuid.uuid4()),
            "image_hash": f"{i}" * 64,
            "lifecycle_stage": "SOWING",
            "metadata": {
                "capture_source": "CAMERA",
                "capture_timestamp": "2026-11-09T10:00:00Z",
                "gps_accuracy": 5.0,
                "latitude": 17.385044,
                "longitude": 78.486671,
            },
            "schema_version": "1.0",
            "sequence_number": 1,
        }
        for i in range(3)
    ]

    engine = MerkleBatchEngine()
    result = engine.commit_batch(envelopes)
    anchor = result["anchor"]

    assert anchor["status"] == "COMMITTED_TO_LEDGER"
    assert anchor["checkpoint_signature"] != "MOCK_CHECKPOINT_AUTHORITY_SIG"

    # Genuine verification passes
    assert engine.verify_anchor(anchor) is True

    # Tampered anchor fails
    tampered_anchor = {**anchor, "merkle_root": "0" * 64}
    assert engine.verify_anchor(tampered_anchor) is False

    # Proof retrieval for individual items
    proof_item = engine.get_proof_for_evidence(anchor["batch_id"], envelopes[0]["evidence_id"])
    assert proof_item is not None
    assert proof_item["leaf_index"] == 0
    assert len(proof_item["inclusion_proof"]) >= 1


# 7. Merkle Service Audit Method
def test_merkle_service_verify_batch_audit(test_client):
    _, SessionLocal = test_client
    db = SessionLocal()

    ev1 = seed_evidence_item(db, status="APPROVED", seq=1)
    ev2 = seed_evidence_item(db, status="APPROVED", seq=2)

    batch_res = MerkleService.create_batch(db)
    batch_id = batch_res["batch_id"]

    audit = MerkleService.verify_batch(db, batch_id)
    assert audit["valid"] is True
    assert audit["merkle_root_matches"] is True
    assert audit["signature_valid"] is True
    assert audit["leaf_count"] == 2
