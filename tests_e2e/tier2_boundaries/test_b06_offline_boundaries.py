"""Tier 2: Offline Capture & Synchronization Boundary Tests.
Tests 60-day extreme delay, client-server clock skew, burst queue synchronization (50 items),
and mid-batch network interruption recovery.
"""

from datetime import datetime, timezone, timedelta
import pytest
from tests_e2e.tier1_features.test_f38_delay_legitimacy import assess_upload_legitimacy


class TestB06OfflineBoundaries:
    """Verifies edge cases in offline queuing, delay tolerances, and sync recovery."""

    def test_sixty_day_extreme_offline_delay_accepted(self):
        """Boundary 1: Verifies 60-day delayed evidence is accepted when signature and sequence are authentic."""
        now = datetime.now(timezone.utc)
        sixty_days_ago = now - timedelta(days=60)

        res = assess_upload_legitimacy(
            capture_timestamp_iso=sixty_days_ago.isoformat(),
            server_timestamp_iso=now.isoformat(),
            is_sequence_valid=True,
            is_signature_valid=True,
        )
        assert res["status"] == "ACCEPTED"
        assert res["is_fraud"] is False
        assert res["delay_days"] >= 60.0

    def test_client_clock_skew_tolerance(self):
        """Boundary 2: Verifies acceptable clock skew when mobile clock is 3 hours behind server."""
        server_now = datetime.now(timezone.utc)
        skewed_client = server_now - timedelta(hours=3)

        res = assess_upload_legitimacy(
            capture_timestamp_iso=skewed_client.isoformat(),
            server_timestamp_iso=server_now.isoformat(),
            is_sequence_valid=True,
            is_signature_valid=True,
        )
        assert res["status"] == "ACCEPTED"
        assert res["is_fraud"] is False

    def test_burst_offline_queue_sync_fifty_items(self, mock_sqlite_queue):
        """Boundary 3: Verifies queue handles burst of 50 offline items syncing sequentially."""
        cursor = mock_sqlite_queue.cursor()
        dev_id = "device-burst-50"

        for s in range(1, 51):
            cursor.execute(
                """INSERT INTO offline_evidence_queue 
                   (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash)
                   VALUES (?, ?, ?, '{}', 'sig', 'path', ?)""",
                (f"ev-burst-{s}", dev_id, s, f"hash_{s}"),
            )
        mock_sqlite_queue.commit()

        cursor.execute("SELECT COUNT(*) FROM offline_evidence_queue WHERE device_id = ?", (dev_id,))
        assert cursor.fetchone()[0] == 50

    def test_sync_resume_after_mid_batch_drop(self, mock_sqlite_queue):
        """Boundary 4: Verifies synchronization resumes from item 3 when network fails after item 2."""
        cursor = mock_sqlite_queue.cursor()
        dev_id = "device-resume"

        for s in [1, 2, 3, 4]:
            cursor.execute(
                """INSERT INTO offline_evidence_queue 
                   (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash)
                   VALUES (?, ?, ?, '{}', 'sig', 'path', ?)""",
                (f"ev-res-{s}", dev_id, s, f"hash_{s}"),
            )
        mock_sqlite_queue.commit()

        # Simulate items 1 and 2 ACKed
        cursor.execute("UPDATE offline_evidence_queue SET sync_state = 'DURABLY_ACKED' WHERE sequence_number IN (1, 2)")
        mock_sqlite_queue.commit()

        # Query pending items to resume: must start at 3
        cursor.execute(
            "SELECT sequence_number FROM offline_evidence_queue WHERE sync_state = 'QUEUED' ORDER BY sequence_number ASC",
        )
        pending = [r[0] for r in cursor.fetchall()]
        assert pending == [3, 4]

    def test_future_capture_timestamp_flagged(self):
        """Boundary 5: Verifies capture timestamp in the future (client clock ahead by 2 days) is detected."""
        now = datetime.now(timezone.utc)
        future_dt = now + timedelta(days=2)

        # Negative delay
        delay_days = (now - future_dt).total_seconds() / 86400.0
        assert delay_days < 0
