"""Tier 4: Scenario RW-03 — 14-Day Monsoon Offline Capture & Delayed Sync.
End-to-end journey:
1. Severe monsoon rains knock out local cell towers for 14 days in remote rural Telangana.
2. Farmer continues capturing evidence daily, accumulating 8 records (sequences 1 to 8) in SQLite queue.
3. On day 15, farmer travels to mandal headquarters; connectivity is restored.
4. Mobile sync state machine executes batch upload of all 8 items in sequence.
5. Invariant check: Legitimate 14-day delayed uploads are NEVER classified as fraud.
6. Monotonic sequence enforcer validates 1..8 and issues durable ACKs.
"""

from datetime import datetime, timezone, timedelta
import json
import uuid
import pytest

from tests_e2e.fixtures.crypto_fixtures import (
    generate_p256_keypair,
    sign_p256_der,
    verify_p256_der,
    rfc8785_canonicalize,
)
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory
from tests_e2e.tier1_features.test_f13_sequence_enforcement import SequenceEnforcerOracle
from tests_e2e.tier1_features.test_f38_delay_legitimacy import assess_upload_legitimacy


class TestRW03OfflineDelayedMonsoonSync:
    """Verifies long-duration offline queueing, sequential upload, and delay legitimacy."""

    def test_fourteen_day_monsoon_batch_sync(self, mock_sqlite_queue):
        """Simulates 14 days of offline capture followed by full batch synchronization."""
        cursor = mock_sqlite_queue.cursor()
        device_id = "device-monsoon-farmer"
        priv_key, pub_pem, _ = generate_p256_keypair()

        server_now = datetime.now(timezone.utc)
        envelopes = []

        # --- Step 1: Simulate 8 captures across 14 offline days ---
        for day_offset in range(14, 6, -1):
            seq = 15 - day_offset
            capture_time = server_now - timedelta(days=day_offset, hours=2)
            ev_id = f"ev-monsoon-{seq}"

            env = EnvelopeFactory.create_valid_envelope(
                device_id=device_id,
                evidence_id=ev_id,
                sequence_number=seq,
                capture_timestamp=capture_time.isoformat(),
            )
            canonical = rfc8785_canonicalize(env)
            sig_der = sign_p256_der(priv_key, canonical)

            # Store in mobile SQLite queue
            cursor.execute(
                """INSERT INTO offline_evidence_queue 
                   (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash, sync_state)
                   VALUES (?, ?, ?, ?, 'SIG', '/path', ?, 'QUEUED')""",
                (ev_id, device_id, seq, json.dumps(env), env["image_hash"]),
            )
            envelopes.append((env, canonical, sig_der))

        mock_sqlite_queue.commit()
        cursor.execute("SELECT COUNT(*) FROM offline_evidence_queue WHERE device_id = ?", (device_id,))
        assert cursor.fetchone()[0] == 8

        # --- Step 2: Day 15 Connectivity Restored & Server Verification ---
        sequence_enforcer = SequenceEnforcerOracle()
        sequence_enforcer.register_device(device_id)

        # Retrieve pending queue sorted by sequence
        cursor.execute(
            "SELECT evidence_id, sequence_number, envelope_json FROM offline_evidence_queue WHERE sync_state = 'QUEUED' ORDER BY sequence_number ASC",
        )
        queued_items = cursor.fetchall()
        assert len(queued_items) == 8

        # Server processes each item in order
        for row in queued_items:
            ev_id, seq, env_json = row
            env = json.loads(env_json)

            # 1. Monotonic sequence verification
            status_code = sequence_enforcer.process_submission(device_id, seq, env["image_hash"])
            assert status_code == 201, f"Failed at sequence {seq}"

            # 2. Invariant verification: Delay legitimacy check
            legitimacy = assess_upload_legitimacy(
                capture_timestamp_iso=env["metadata"]["capture_timestamp"],
                server_timestamp_iso=server_now.isoformat(),
                is_sequence_valid=True,
                is_signature_valid=True,
            )
            assert legitimacy["is_fraud"] is False
            assert legitimacy["status"] == "ACCEPTED"
            assert legitimacy["classification"] == "LEGITIMATE_OFFLINE_DELAY"
            assert legitimacy["delay_days"] >= 7.0

            # 3. Durable ACK transition
            cursor.execute(
                "UPDATE offline_evidence_queue SET sync_state = 'DURABLY_ACKED', synced_at = CURRENT_TIMESTAMP WHERE evidence_id = ?",
                (ev_id,),
            )

        mock_sqlite_queue.commit()
        cursor.execute("SELECT COUNT(*) FROM offline_evidence_queue WHERE sync_state = 'DURABLY_ACKED'")
        assert cursor.fetchone()[0] == 8
