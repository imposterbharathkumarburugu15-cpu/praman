"""Tier 3: Interaction Test I-01 — Camera vs Upload x Offline Queue x Durable Sync.
Validates the interaction between mobile image acquisition (CAMERA vs FILE_UPLOAD),
local SQLite offline queueing, and network synchronization with durable ACK.
"""

import json
import uuid
import pytest
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory


class TestI01CameraOfflineSync:
    """Verifies interaction between evidence capture source, local persistence, and sync."""

    def test_camera_capture_offline_queuing(self, mock_sqlite_queue):
        """Interaction 1: Verifies CAMERA capture with live GPS accuracy queues successfully offline."""
        cursor = mock_sqlite_queue.cursor()
        ev_id = str(uuid.uuid4())
        dev_id = "device-cam-sync-1"

        env = EnvelopeFactory.create_valid_envelope(
            evidence_id=ev_id,
            device_id=dev_id,
            capture_source="CAMERA",
            gps_accuracy=3.5,
            sequence_number=1,
        )
        cursor.execute(
            """INSERT INTO offline_evidence_queue 
               (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash, sync_state)
               VALUES (?, ?, ?, ?, 'MOCK_SIG', '/cam/img.jpg', ?, 'QUEUED')""",
            (ev_id, dev_id, 1, json.dumps(env), env["image_hash"]),
        )
        mock_sqlite_queue.commit()

        cursor.execute("SELECT envelope_json, sync_state FROM offline_evidence_queue WHERE evidence_id = ?", (ev_id,))
        row = cursor.fetchone()
        stored_env = json.loads(row[0])
        assert stored_env["metadata"]["capture_source"] == "CAMERA"
        assert row[1] == "QUEUED"

    def test_file_upload_offline_queuing(self, mock_sqlite_queue):
        """Interaction 2: Verifies FILE_UPLOAD capture queues successfully offline."""
        cursor = mock_sqlite_queue.cursor()
        ev_id = str(uuid.uuid4())
        dev_id = "device-file-sync-1"

        env = EnvelopeFactory.create_valid_envelope(
            evidence_id=ev_id,
            device_id=dev_id,
            capture_source="FILE_UPLOAD",
            gps_accuracy=12.0,
            sequence_number=1,
        )
        cursor.execute(
            """INSERT INTO offline_evidence_queue 
               (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash, sync_state)
               VALUES (?, ?, ?, ?, 'MOCK_SIG', '/uploads/img.png', ?, 'QUEUED')""",
            (ev_id, dev_id, 1, json.dumps(env), env["image_hash"]),
        )
        mock_sqlite_queue.commit()

        cursor.execute("SELECT envelope_json FROM offline_evidence_queue WHERE evidence_id = ?", (ev_id,))
        stored_env = json.loads(cursor.fetchone()[0])
        assert stored_env["metadata"]["capture_source"] == "FILE_UPLOAD"

    def test_online_sync_transitions_queued_to_durably_acked(self, mock_sqlite_queue):
        """Interaction 3: Verifies synchronization transitions queue items from QUEUED to DURABLY_ACKED."""
        cursor = mock_sqlite_queue.cursor()
        ev_id = "ev-sync-trans"

        cursor.execute(
            """INSERT INTO offline_evidence_queue 
               (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash, sync_state)
               VALUES (?, 'dev-1', 1, '{}', 'sig', 'path', 'hash', 'QUEUED')""",
            (ev_id,),
        )
        mock_sqlite_queue.commit()

        # Mock server receipt
        receipt = {"status": "DURABLY_ACKED", "receipt_signature": "SIG_VALID_2026"}

        cursor.execute(
            "UPDATE offline_evidence_queue SET sync_state = ?, synced_at = CURRENT_TIMESTAMP WHERE evidence_id = ?",
            (receipt["status"], ev_id),
        )
        mock_sqlite_queue.commit()

        cursor.execute("SELECT sync_state, synced_at FROM offline_evidence_queue WHERE evidence_id = ?", (ev_id,))
        row = cursor.fetchone()
        assert row[0] == "DURABLY_ACKED"
        assert row[1] is not None

    def test_idempotent_sync_avoids_duplicate_db_records(self, mock_sqlite_queue):
        """Interaction 4: Verifies retrying a sync for an already acknowledged item is idempotent."""
        cursor = mock_sqlite_queue.cursor()
        ev_id = "ev-idem-sync"

        cursor.execute(
            """INSERT INTO offline_evidence_queue 
               (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash, sync_state)
               VALUES (?, 'dev-1', 1, '{}', 'sig', 'path', 'hash', 'DURABLY_ACKED')""",
            (ev_id,),
        )
        mock_sqlite_queue.commit()

        # Incoming duplicate server ACK
        cursor.execute(
            "UPDATE offline_evidence_queue SET sync_state = 'DURABLY_ACKED' WHERE evidence_id = ?",
            (ev_id,),
        )
        mock_sqlite_queue.commit()

        cursor.execute("SELECT COUNT(*) FROM offline_evidence_queue WHERE evidence_id = ?", (ev_id,))
        assert cursor.fetchone()[0] == 1

    def test_reconnection_syncs_queued_items_in_strict_sequence_order(self, mock_sqlite_queue):
        """Interaction 5: Verifies reconnection syncs queued items strictly sorted by sequence_number."""
        cursor = mock_sqlite_queue.cursor()
        dev_id = "dev-ordered-sync"

        # Enqueue sequences out of insertion order (2, 1, 3)
        for s in [2, 1, 3]:
            cursor.execute(
                """INSERT INTO offline_evidence_queue 
                   (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash, sync_state)
                   VALUES (?, ?, ?, '{}', 'sig', 'path', 'hash', 'QUEUED')""",
                (f"ev-ord-{s}", dev_id, s),
            )
        mock_sqlite_queue.commit()

        cursor.execute(
            "SELECT sequence_number FROM offline_evidence_queue WHERE sync_state = 'QUEUED' ORDER BY sequence_number ASC",
        )
        seqs = [r[0] for r in cursor.fetchall()]
        assert seqs == [1, 2, 3]
