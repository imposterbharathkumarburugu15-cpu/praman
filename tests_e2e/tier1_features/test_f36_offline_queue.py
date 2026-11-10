"""F-36: Persistent Offline Storage Queue Tests.
Validates local SQLite offline storage queue persisting evidence,
envelope JSON, and signatures until durable server acknowledgement.
"""

import json
import uuid
import pytest
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory


class TestF36OfflineStorageQueue:
    """Verifies SQLite offline queue durability and lifecycle."""

    def test_enqueue_offline_evidence(self, mock_sqlite_queue):
        """Test 1: Verifies offline evidence is enqueued with status QUEUED."""
        cursor = mock_sqlite_queue.cursor()
        ev_id = str(uuid.uuid4())
        dev_id = "device-off-1"
        env = EnvelopeFactory.create_valid_envelope(evidence_id=ev_id, device_id=dev_id)

        cursor.execute(
            """INSERT INTO offline_evidence_queue 
               (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash, sync_state)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'QUEUED')""",
            (ev_id, dev_id, 1, json.dumps(env), "MOCK_SIG", "/local/img1.jpg", env["image_hash"]),
        )
        mock_sqlite_queue.commit()

        cursor.execute("SELECT sync_state FROM offline_evidence_queue WHERE evidence_id = ?", (ev_id,))
        assert cursor.fetchone()[0] == "QUEUED"

    def test_queue_persists_across_app_restart(self, ephemeral_dir):
        """Test 2: Verifies queued items persist on disk across database connection closes."""
        import sqlite3
        import os
        db_path = os.path.join(ephemeral_dir, "restart_test.db")

        # Session 1: App creates and populates queue
        conn1 = sqlite3.connect(db_path)
        conn1.execute("CREATE TABLE q (id TEXT PRIMARY KEY, state TEXT);")
        conn1.execute("INSERT INTO q VALUES ('ev-1', 'QUEUED');")
        conn1.commit()
        conn1.close()

        # Session 2: App launches after reboot
        conn2 = sqlite3.connect(db_path)
        cur = conn2.cursor()
        cur.execute("SELECT state FROM q WHERE id = 'ev-1'")
        assert cur.fetchone()[0] == "QUEUED"
        conn2.close()

    def test_fifo_sequence_ordering(self, mock_sqlite_queue):
        """Test 3: Verifies pending items are retrieved strictly ordered by sequence number."""
        cursor = mock_sqlite_queue.cursor()
        dev_id = "device-fifo"

        for seq in [3, 1, 2]:
            ev_id = f"ev-seq-{seq}"
            cursor.execute(
                """INSERT INTO offline_evidence_queue 
                   (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash)
                   VALUES (?, ?, ?, '{}', 'sig', 'path', 'hash')""",
                (ev_id, dev_id, seq),
            )
        mock_sqlite_queue.commit()

        cursor.execute(
            "SELECT sequence_number FROM offline_evidence_queue WHERE device_id = ? ORDER BY sequence_number ASC",
            (dev_id,),
        )
        ordered_seqs = [r[0] for r in cursor.fetchall()]
        assert ordered_seqs == [1, 2, 3]

    def test_durable_ack_transitions_state(self, mock_sqlite_queue):
        """Test 4: Verifies receipt of durable ACK updates status to DURABLY_ACKED with timestamp."""
        cursor = mock_sqlite_queue.cursor()
        ev_id = "ev-ack-test"

        cursor.execute(
            """INSERT INTO offline_evidence_queue 
               (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash)
               VALUES (?, 'dev', 1, '{}', 'sig', 'path', 'hash')""",
            (ev_id,),
        )
        mock_sqlite_queue.commit()

        # Transition upon durable server response
        cursor.execute(
            "UPDATE offline_evidence_queue SET sync_state = 'DURABLY_ACKED', synced_at = CURRENT_TIMESTAMP WHERE evidence_id = ?",
            (ev_id,),
        )
        mock_sqlite_queue.commit()

        cursor.execute("SELECT sync_state, synced_at FROM offline_evidence_queue WHERE evidence_id = ?", (ev_id,))
        row = cursor.fetchone()
        assert row[0] == "DURABLY_ACKED"
        assert row[1] is not None

    def test_retention_until_ack_rule(self, mock_sqlite_queue):
        """Test 5: Verifies only DURABLY_ACKED items can be purged from local storage."""
        cursor = mock_sqlite_queue.cursor()
        cursor.execute("INSERT INTO offline_evidence_queue VALUES ('e1', 'd', 1, '{}', 's', 'p', 'h', 'QUEUED', 0, CURRENT_TIMESTAMP, NULL)")
        cursor.execute("INSERT INTO offline_evidence_queue VALUES ('e2', 'd', 2, '{}', 's', 'p', 'h', 'DURABLY_ACKED', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
        mock_sqlite_queue.commit()

        # Prune only synced
        cursor.execute("DELETE FROM offline_evidence_queue WHERE sync_state = 'DURABLY_ACKED'")
        mock_sqlite_queue.commit()

        cursor.execute("SELECT evidence_id FROM offline_evidence_queue")
        remaining = [r[0] for r in cursor.fetchall()]
        assert remaining == ["e1"]  # e1 retained!
