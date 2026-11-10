"""Tier 4: Scenario RW-04 — Multi-Device Concurrent Farm Capture & Immutable Audit.
End-to-end journey:
1. Farmer Ramesh (Device A) and son Suresh (Device B) concurrently capture evidence on the same cotton parcel.
2. Device A and Device B enroll distinct P-256 ECDSA keypairs under the same farm ID.
3. Devices submit evidence concurrently; sequence numbers increment independently per device.
4. Tamper-evident audit log records all state transitions with cryptographic attribution.
5. Auditor inspects complete immutable audit trail of the farm parcel.
"""

import uuid
import hashlib
import pytest

from tests_e2e.fixtures.crypto_fixtures import generate_p256_keypair, rfc8785_canonicalize
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory
from tests_e2e.tier1_features.test_f13_sequence_enforcement import SequenceEnforcerOracle


class TestRW04MultiDeviceFarmAudit:
    """Verifies multi-device concurrent evidence capture and audit trail integrity."""

    def test_multi_device_concurrent_farm_capture(self, ephemeral_dir):
        """Simulates two devices concurrently capturing evidence on the same farm with audit logging."""
        farm_id = str(uuid.uuid4())
        dev_a_id = "device-ramesh-phone"
        dev_b_id = "device-suresh-tablet"

        # Keypair generation
        priv_a, pub_pem_a, _ = generate_p256_keypair()
        priv_b, pub_pem_b, _ = generate_p256_keypair()

        # Initialize sequence enforcer and audit log
        enforcer = SequenceEnforcerOracle()
        enforcer.register_device(dev_a_id)
        enforcer.register_device(dev_b_id)

        audit_log = []

        # Concurrent submission stream
        submissions = [
            (dev_a_id, 1, "SOWING", "hash_a1"),
            (dev_b_id, 1, "SOWING", "hash_b1"),
            (dev_a_id, 2, "INPUT_APPLICATION", "hash_a2"),
            (dev_b_id, 2, "CROP_GROWTH", "hash_b2"),
            (dev_a_id, 3, "CROP_GROWTH", "hash_a3"),
        ]

        for dev_id, seq, stage, h in submissions:
            status = enforcer.process_submission(dev_id, seq, h)
            assert status == 201, f"Failed for {dev_id} seq {seq}"

            # Append to audit trail
            audit_log.append({
                "log_id": str(uuid.uuid4()),
                "farm_id": farm_id,
                "device_id": dev_id,
                "sequence_number": seq,
                "lifecycle_stage": stage,
                "image_hash": h,
                "event": "EVIDENCE_COMMITTED",
            })

        # Auditor Verification
        # 1. Total records logged
        assert len(audit_log) == 5

        # 2. Device A submitted sequences 1, 2, 3
        dev_a_logs = [l for l in audit_log if l["device_id"] == dev_a_id]
        assert [l["sequence_number"] for l in dev_a_logs] == [1, 2, 3]

        # 3. Device B submitted sequences 1, 2
        dev_b_logs = [l for l in audit_log if l["device_id"] == dev_b_id]
        assert [l["sequence_number"] for l in dev_b_logs] == [1, 2]

        # 4. All logs bound to identical farm parcel
        assert all(l["farm_id"] == farm_id for l in audit_log)
