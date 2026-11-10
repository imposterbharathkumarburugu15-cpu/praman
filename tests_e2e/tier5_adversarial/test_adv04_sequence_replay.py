"""ADV-04: Monotonic Sequence, Replay & Clock Skew Adversarial Tests.
Verifies resistance against:
1. Sequence gap injection (S = 5 when expected S = 1) returning HTTP 409 Conflict.
2. Stale sequence replay (S <= S_last) returning HTTP 409 Conflict.
3. Poisoned replay attack (same sequence with altered counterfeit image/envelope hash) returning HTTP 409 Conflict.
4. Idempotent legitimate replay (identical sequence & identical hash) returning HTTP 200 OK without incrementing sequence counter.
5. Future clock skew injection (> 5 minutes into the future) returning status REJECTED / HTTP 400.
6. Legitimate offline delay (14-30 days past) classified as LEGITIMATE_OFFLINE_DELAY, never fraud (F-38 invariant).
7. Device sequence isolation under multi-device interleaved attacks.
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.database import Base
from backend.app.models.device import Device
from backend.app.models.evidence import Evidence
from backend.app.services.sequence_service import SequenceService
from backend.app.services.delay_evaluator import assess_upload_legitimacy


@pytest.fixture
def in_memory_db():
    """Provides an isolated in-memory SQLite database session for sequence testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestAdv04SequenceReplayClockSkew:
    """Adversarial test suite for sequence ordering, replay attacks, and clock skew."""

    def test_sequence_gap_injection_rejected_with_409(self, in_memory_db):
        """ADV-04.1: Adversary skips sequences (e.g. sends seq 5 on fresh device); verify 409 Conflict."""
        dev = Device(id="dev-gap-target", farmer_id=str(uuid.uuid4()), public_key_pem="PEM", status="ACTIVE", last_sequence_number=0)
        in_memory_db.add(dev)
        in_memory_db.commit()

        # Attacker injects sequence 5
        is_ok, code, msg, _ = SequenceService.evaluate_sequence(
            db=in_memory_db,
            device_id=dev.id,
            sequence_number=5,
            image_hash="hash_5",
        )
        assert is_ok is False
        assert code == 409
        assert "Sequence gap detected" in msg

    def test_stale_sequence_replay_rejected_with_409(self, in_memory_db):
        """ADV-04.2: Adversary replays past sequence number S=1 after device has progressed to S=3."""
        dev = Device(id="dev-stale-target", farmer_id=str(uuid.uuid4()), public_key_pem="PEM", status="ACTIVE", last_sequence_number=3)
        in_memory_db.add(dev)
        in_memory_db.commit()

        # Attacker attempts to submit sequence 1
        is_ok, code, msg, _ = SequenceService.evaluate_sequence(
            db=in_memory_db,
            device_id=dev.id,
            sequence_number=1,
            image_hash="counterfeit_payload",
        )
        assert is_ok is False
        assert code == 409
        assert "stale" in msg.lower() or "conflict" in msg.lower()

    def test_poisoned_replay_with_different_payload_returns_409(self, in_memory_db):
        """ADV-04.3: Adversary resends current sequence number S=1 with counterfeit image hash."""
        dev = Device(id="dev-poison-target", farmer_id=str(uuid.uuid4()), public_key_pem="PEM", status="ACTIVE", last_sequence_number=1)
        in_memory_db.add(dev)
        
        # Genuine evidence already recorded for seq 1
        ev = Evidence(
            id=str(uuid.uuid4()),
            device_id=dev.id,
            farm_id=str(uuid.uuid4()),
            sequence_number=1,
            lifecycle_stage="SOWING",
            image_hash="genuine_sha256_hash",
            canonical_envelope_json='{"device_id":"dev-poison-target","sequence_number":1}',
            signature_b64="MEQCIAiV0XjYd7f9...",
            status="DURABLY_ACKED",
        )
        in_memory_db.add(ev)
        in_memory_db.commit()

        # Attacker attempts replay of seq=1 with MALICIOUS payload
        is_ok, code, msg, _ = SequenceService.evaluate_sequence(
            db=in_memory_db,
            device_id=dev.id,
            sequence_number=1,
            image_hash="MALICIOUS_COUNTERFEIT_IMAGE_HASH",
        )
        assert is_ok is False
        assert code == 409
        assert "differing payload" in msg.lower()

    def test_idempotent_retry_returns_200_ok(self, in_memory_db):
        """ADV-04.4: Legitimate network retry with identical sequence and identical payload returns 200 OK."""
        dev = Device(id="dev-idempotent-target", farmer_id=str(uuid.uuid4()), public_key_pem="PEM", status="ACTIVE", last_sequence_number=1)
        in_memory_db.add(dev)

        genuine_hash = "64charhex_genuine_hash_000000000000000000000000000000000000000000"
        canonical_json = '{"device_id":"dev-idempotent-target","sequence_number":1}'
        ev = Evidence(
            id="ev-original-123",
            device_id=dev.id,
            farm_id=str(uuid.uuid4()),
            sequence_number=1,
            lifecycle_stage="SOWING",
            image_hash=genuine_hash,
            canonical_envelope_json=canonical_json,
            signature_b64="MEQCIAiV0XjYd7f9...",
            status="DURABLY_ACKED",
        )
        in_memory_db.add(ev)
        in_memory_db.commit()

        # Mobile client resends exact same submission due to network drop
        is_ok, code, msg, existing = SequenceService.evaluate_sequence(
            db=in_memory_db,
            device_id=dev.id,
            sequence_number=1,
            image_hash=genuine_hash,
        )
        assert is_ok is True
        assert code == 200
        assert existing is not None
        assert existing.id == "ev-original-123"

    def test_future_clock_skew_rejected(self):
        """ADV-04.5: Capture timestamp > 5 minutes in future is rejected as FUTURE_TIMESTAMP_DETECTED."""
        now = datetime.now(timezone.utc)
        future_ts = (now + timedelta(minutes=15)).isoformat()
        server_ts = now.isoformat()

        res = assess_upload_legitimacy(
            capture_timestamp_iso=future_ts,
            server_timestamp_iso=server_ts,
            is_sequence_valid=True,
            is_signature_valid=True,
        )
        assert res["status"] == "REJECTED"
        assert res["reason"] == "FUTURE_TIMESTAMP_DETECTED"
        assert res["is_fraud"] is True

    def test_offline_delay_legitimacy_rule_f38(self):
        """ADV-04.6: F-38 Invariant: 21-day delayed upload during monsoon is NOT fraud when sequence & signature are valid."""
        now = datetime.now(timezone.utc)
        past_ts = (now - timedelta(days=21)).isoformat()
        server_ts = now.isoformat()

        res = assess_upload_legitimacy(
            capture_timestamp_iso=past_ts,
            server_timestamp_iso=server_ts,
            is_sequence_valid=True,
            is_signature_valid=True,
        )
        assert res["status"] == "ACCEPTED"
        assert res["is_fraud"] is False
        assert res["classification"] == "LEGITIMATE_OFFLINE_DELAY"
        assert res["delay_days"] >= 20.0

    def test_multi_device_sequence_isolation(self, in_memory_db):
        """ADV-04.7: Interleaved submissions from different devices maintain independent sequence tracking."""
        dev_a = Device(id="dev-A", farmer_id=str(uuid.uuid4()), public_key_pem="PEMA", status="ACTIVE", last_sequence_number=0)
        dev_b = Device(id="dev-B", farmer_id=str(uuid.uuid4()), public_key_pem="PEMB", status="ACTIVE", last_sequence_number=0)
        in_memory_db.add_all([dev_a, dev_b])
        in_memory_db.commit()

        # Dev A sends seq 1 -> accepted
        ok_a1, code_a1, _, _ = SequenceService.evaluate_sequence(in_memory_db, dev_a.id, 1, "ha1")
        assert ok_a1 and code_a1 == 201
        dev_a.last_sequence_number = 1

        # Dev B sends seq 1 -> accepted (isolated counter)
        ok_b1, code_b1, _, _ = SequenceService.evaluate_sequence(in_memory_db, dev_b.id, 1, "hb1")
        assert ok_b1 and code_b1 == 201
        dev_b.last_sequence_number = 1

        # Dev A sends seq 2 -> accepted
        ok_a2, code_a2, _, _ = SequenceService.evaluate_sequence(in_memory_db, dev_a.id, 2, "ha2")
        assert ok_a2 and code_a2 == 201
