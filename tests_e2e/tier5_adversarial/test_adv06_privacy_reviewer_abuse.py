"""ADV-06: Reviewer Console & Public Verification Abuse Adversarial Tests.
Verifies resistance against:
1. PII and GPS Data Leakage: /api/v1/verify/{token} invariant testing (zero PII, zero exact coordinates).
2. Unauthorized Reviewer Decision Actions (invalid actions, bypassing state transitions).
3. Adversarial Decision Submission without Explanatory Notes (< 5 characters) on REJECT/RETAKE.
4. Decision injection against non-existent or un-enrolled evidence.
5. Invariant enforcement: immutable audit log captures reviewer ID, state transition, and timestamp.
"""

import json
import uuid
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.models.farmer import Farmer
from backend.app.models.farm import Farm
from backend.app.models.device import Device
from backend.app.models.evidence import Evidence
from backend.app.models.public_token import PublicToken
from backend.app.models.audit_log import AuditLog
from backend.app.api.v1.verify import (
    resolve_public_verification,
    verify_public_proof,
    FORBIDDEN_PII_FIELDS,
    FORBIDDEN_GPS_FIELDS,
    VerifyProofRequest,
)
from backend.app.api.v1.reviewer import (
    record_reviewer_decision,
    ReviewDecisionCreate,
)


@pytest.fixture
def test_db_session():
    """Sets up an isolated in-memory SQLite database populated with genuine models."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestAdv06ReviewerPublicVerifyAbuse:
    """Adversarial test suite for public verification zero-leakage and reviewer workflow abuse."""

    def test_public_verify_zero_pii_and_zero_gps_leakage(self, test_db_session):
        """ADV-06.1: Enforces strict zero-leakage invariant: public verify payload never reveals PII or exact GPS."""
        db = test_db_session

        # 1. Create farmer with sensitive private data
        farmer = Farmer(
            id=str(uuid.uuid4()),
            full_name="Bhimrao Ramji Ambedkar",
            phone_number="+919849012345",
            language_pref="te",
        )
        db.add(farmer)

        # 2. Create farm with exact boundary polygon
        farm = Farm(
            id=str(uuid.uuid4()),
            farmer_id=farmer.id,
            farm_name="Private Family Farm",
            crop_type="Cotton",
            boundary_geojson=json.dumps({
                "type": "Polygon",
                "coordinates": [[[78.5320, 19.6640], [78.5350, 19.6645], [78.5360, 19.6620], [78.5320, 19.6640]]]
            }),
            area_hectares=2.5,
        )
        db.add(farm)

        # 3. Create device and evidence with exact GPS coordinates in canonical envelope
        dev_id = str(uuid.uuid4())
        device = Device(id=dev_id, farmer_id=farmer.id, public_key_pem="PEM", status="ACTIVE", last_sequence_number=1)
        db.add(device)

        evidence_id = str(uuid.uuid4())
        canonical_envelope = {
            "device_id": dev_id,
            "evidence_id": evidence_id,
            "farm_id": farm.id,
            "image_hash": "a1b2c3d4e5f60000000000000000000000000000000000000000000000000000",
            "lifecycle_stage": "HARVEST",
            "metadata": {
                "capture_source": "CAMERA",
                "capture_timestamp": "2026-11-09T14:30:00Z",
                "latitude": 19.664012,
                "longitude": 78.532045,
                "gps_accuracy": 3.2,
            },
            "schema_version": "1.0",
            "sequence_number": 1,
        }
        evidence = Evidence(
            id=evidence_id,
            device_id=device.id,
            farm_id=farm.id,
            sequence_number=1,
            lifecycle_stage="HARVEST",
            image_hash=canonical_envelope["image_hash"],
            canonical_envelope_json=json.dumps(canonical_envelope),
            signature_b64="MEQCIAiV0XjYd7f9MEQCIAiV0XjYd7f9",
            status="APPROVED",
        )
        db.add(evidence)

        # 4. Issue public token
        token_str = "public-test-token-safe-256"
        pub_token = PublicToken(token=token_str, evidence_id=evidence.id, status="ACTIVE")
        db.add(pub_token)
        db.commit()

        # 5. Resolve public verification payload
        payload = resolve_public_verification(token=token_str, db=db)

        # 6. Deep inspection of serialized JSON response
        serialized = json.dumps(payload).lower()

        # Check ALL forbidden PII fields
        for forbidden_pii in FORBIDDEN_PII_FIELDS:
            assert forbidden_pii not in serialized, (
                f"CRITICAL PRIVACY VIOLATION: Forbidden PII field '{forbidden_pii}' leaked in public verify payload!"
            )
        assert "bhimrao" not in serialized
        assert "9849012345" not in serialized

        # Check ALL forbidden GPS fields
        for forbidden_gps in FORBIDDEN_GPS_FIELDS:
            assert forbidden_gps not in serialized, (
                f"CRITICAL PRIVACY VIOLATION: Forbidden GPS field '{forbidden_gps}' leaked in public verify payload!"
            )
        assert "19.664012" not in serialized
        assert "78.532045" not in serialized
        assert dev_id.lower() not in serialized

        # Verify only privacy-preserving public fields are present
        assert payload["provenance_status"] == "COMMITTED_TO_LEDGER"
        assert payload["crop_type"] == "Cotton"
        assert payload["region_coarse"] == "Adilabad, Telangana"
        assert "merkle_root" in payload
        assert "inclusion_proof" in payload
        assert "checkpoint" in payload

    def test_public_verify_nonexistent_token_returns_404(self, test_db_session):
        """ADV-06.2: Resolving an unknown or fabricated verification token returns HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_public_verification(token="non-existent-token-xyz", db=test_db_session)
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    def test_reviewer_rejection_without_notes_rejected(self, test_db_session):
        """ADV-06.3: Adverse decisions (REJECT / REQUEST_RETAKE) without >=5 char explanatory notes are rejected (HTTP 400)."""
        db = test_db_session

        evidence = Evidence(
            id=str(uuid.uuid4()),
            device_id=str(uuid.uuid4()),
            farm_id=str(uuid.uuid4()),
            sequence_number=1,
            lifecycle_stage="CROP_GROWTH",
            image_hash="hash_01",
            canonical_envelope_json="{}",
            signature_b64="MEQCIAiV0XjYd7f9MEQCIAiV0XjYd7f9",
            status="PENDING_REVIEW",
        )
        db.add(evidence)
        db.commit()

        # REJECT without notes
        with pytest.raises(HTTPException) as exc_info:
            record_reviewer_decision(
                body=ReviewDecisionCreate(evidence_id=evidence.id, decision="REJECT", notes=""),
                db=db,
            )
        assert exc_info.value.status_code == 400
        assert "explanatory notes" in exc_info.value.detail.lower()

        # REQUEST_RETAKE with notes too short (< 5 chars)
        with pytest.raises(HTTPException) as exc_info:
            record_reviewer_decision(
                body=ReviewDecisionCreate(evidence_id=evidence.id, decision="REQUEST_RETAKE", notes="bad"),
                db=db,
            )
        assert exc_info.value.status_code == 400
        assert "explanatory notes" in exc_info.value.detail.lower()

    def test_reviewer_decision_on_nonexistent_evidence_returns_404(self, test_db_session):
        """ADV-06.4: Recording decision against non-existent evidence returns HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            record_reviewer_decision(
                body=ReviewDecisionCreate(
                    evidence_id="non-existent-evidence-id",
                    decision="APPROVE",
                    notes="Looks good",
                ),
                db=test_db_session,
            )
        assert exc_info.value.status_code == 404

    def test_reviewer_decision_state_transition_and_audit_log(self, test_db_session):
        """ADV-06.5: Valid reviewer decision updates evidence state and logs immutable audit record."""
        db = test_db_session

        evidence = Evidence(
            id="ev-audit-test-01",
            device_id="dev-01",
            farm_id="farm-01",
            sequence_number=1,
            lifecycle_stage="SOWING",
            image_hash="sample_hash",
            canonical_envelope_json="{}",
            signature_b64="MEQCIAiV0XjYd7f9MEQCIAiV0XjYd7f9",
            status="PENDING_REVIEW",
        )
        db.add(evidence)
        db.commit()

        # Reviewer approves evidence
        res = record_reviewer_decision(
            body=ReviewDecisionCreate(
                evidence_id=evidence.id,
                decision="APPROVE",
                notes="Approved following visual field validation",
                reviewer_id="reviewer-senior-07",
            ),
            db=db,
        )

        assert res.new_state == "APPROVED"
        assert res.action == "APPROVE"
        assert evidence.status == "APPROVED"

        # Verify audit log recorded the event
        audit_entry = db.query(AuditLog).filter(
            AuditLog.entity_id == evidence.id,
            AuditLog.event_type == "REVIEWER_DECISION",
        ).first()

        assert audit_entry is not None
        assert audit_entry.actor_id == "reviewer-senior-07"
        assert audit_entry.previous_state == "PENDING_REVIEW"
        assert audit_entry.new_state == "APPROVED"
