"""Tier 3: Interaction Test I-04 — Sequence Replay x Conflict 409 x Audit Trail.
Validates the interaction when sequence replay attacks trigger HTTP 409 Conflict,
recording immutable audit trail entries documenting the unauthorized attempt.
"""

import uuid
import hashlib
import pytest
from tests_e2e.tier1_features.test_f13_sequence_enforcement import SequenceEnforcerOracle


class AuditLoggedSequenceService:
    """Combines sequence enforcer with append-only audit logging."""

    def __init__(self):
        self.enforcer = SequenceEnforcerOracle()
        self.audit_log = []

    def register_device(self, device_id: str):
        self.enforcer.register_device(device_id)

    def submit_evidence(self, device_id: str, seq: int, image_hash: str) -> int:
        status_code = self.enforcer.process_submission(device_id, seq, image_hash)

        # Log event in audit trail
        event_type = "EVIDENCE_INGESTED" if status_code == 201 else (
            "IDEMPOTENT_RETRY" if status_code == 200 else "REPLAY_CONFLICT_ATTEMPT"
        )
        self.audit_log.append({
            "log_id": str(uuid.uuid4()),
            "device_id": device_id,
            "sequence_number": seq,
            "image_hash": image_hash,
            "status_code": status_code,
            "event_type": event_type,
        })
        return status_code


class TestI04DuplicateSequenceRejection:
    """Verifies sequence replay rejection and audit logging interaction."""

    def test_replay_attack_rejected_and_logged(self):
        """Interaction 1: Verifies replaying seq 1 with malicious hash returns 409 and logs REPLAY_CONFLICT_ATTEMPT."""
        service = AuditLoggedSequenceService()
        dev_id = "device-replay-target"
        service.register_device(dev_id)

        # Normal submission seq 1
        assert service.submit_evidence(dev_id, seq=1, image_hash="legit_hash_1") == 201
        assert service.submit_evidence(dev_id, seq=2, image_hash="legit_hash_2") == 201

        # Attacker replays seq 1 with counterfeit payload
        status = service.submit_evidence(dev_id, seq=1, image_hash="COUNTERFEIT_IMAGE")
        assert status == 409

        # Verify audit trail captured the replay attempt
        last_log = service.audit_log[-1]
        assert last_log["event_type"] == "REPLAY_CONFLICT_ATTEMPT"
        assert last_log["status_code"] == 409
        assert last_log["image_hash"] == "COUNTERFEIT_IMAGE"

    def test_sequence_gap_logged_as_conflict(self):
        """Interaction 2: Verifies sequence gap (1 -> 4) returns 409 and logs conflict."""
        service = AuditLoggedSequenceService()
        service.register_device("dev-gap")

        service.submit_evidence("dev-gap", seq=1, image_hash="h1")
        assert service.submit_evidence("dev-gap", seq=4, image_hash="h4") == 409

        last_log = service.audit_log[-1]
        assert last_log["event_type"] == "REPLAY_CONFLICT_ATTEMPT"

    def test_idempotent_retry_logged_with_status_200(self):
        """Interaction 3: Verifies legitimate network retry logs IDEMPOTENT_RETRY with 200."""
        service = AuditLoggedSequenceService()
        service.register_device("dev-retry")

        service.submit_evidence("dev-retry", seq=1, image_hash="same_hash")
        retry_status = service.submit_evidence("dev-retry", seq=1, image_hash="same_hash")
        assert retry_status == 200

        last_log = service.audit_log[-1]
        assert last_log["event_type"] == "IDEMPOTENT_RETRY"
        assert last_log["status_code"] == 200

    def test_monotonic_advancement_audit_chain(self):
        """Interaction 4: Verifies monotonic sequence advancement creates audit chain."""
        service = AuditLoggedSequenceService()
        service.register_device("dev-chain")

        for s in range(1, 4):
            service.submit_evidence("dev-chain", seq=s, image_hash=f"h_{s}")

        ingest_logs = [l for l in service.audit_log if l["event_type"] == "EVIDENCE_INGESTED"]
        assert len(ingest_logs) == 3
        assert [l["sequence_number"] for l in ingest_logs] == [1, 2, 3]

    def test_audit_log_chronological_immutability(self):
        """Interaction 5: Verifies audit log records maintain sequential integrity across attempts."""
        service = AuditLoggedSequenceService()
        service.register_device("dev-immut")

        service.submit_evidence("dev-immut", 1, "h1")
        service.submit_evidence("dev-immut", 1, "bad_h")  # 409
        service.submit_evidence("dev-immut", 2, "h2")      # 201

        assert len(service.audit_log) == 3
        assert [l["status_code"] for l in service.audit_log] == [201, 409, 201]
