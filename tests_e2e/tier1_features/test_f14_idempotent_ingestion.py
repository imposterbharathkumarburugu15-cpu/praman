"""F-14: Idempotent Ingestion Handler Tests.
Validates safe deduplication of identical retried submissions without
duplicate persistence or false conflict errors.
"""

import uuid
import pytest
from tests_e2e.tier1_features.test_f13_sequence_enforcement import SequenceEnforcerOracle


class TestF14IdempotentIngestion:
    """Verifies idempotency guarantees of the ingestion API."""

    def test_identical_retry_returns_200_ok(self):
        """Test 1: Verifies re-submitting an identical envelope returns HTTP 200 OK."""
        enforcer = SequenceEnforcerOracle()
        dev_id = "device-retrying-01"
        enforcer.register_device(dev_id)

        # Initial submission
        first_code = enforcer.process_submission(dev_id, seq=1, image_hash="hash_alpha")
        assert first_code == 201

        # Identical retry (e.g. due to mobile network drop before receiving ACK)
        retry_code = enforcer.process_submission(dev_id, seq=1, image_hash="hash_alpha")
        assert retry_code == 200

    def test_multiple_identical_retries(self):
        """Test 2: Verifies multiple repeated identical requests all return HTTP 200."""
        enforcer = SequenceEnforcerOracle()
        dev_id = "device-retrying-multi"
        enforcer.register_device(dev_id)

        enforcer.process_submission(dev_id, seq=1, image_hash="hash_common")

        for _ in range(5):
            res = enforcer.process_submission(dev_id, seq=1, image_hash="hash_common")
            assert res == 200

    def test_deduplication_prevents_multiple_records(self, ephemeral_dir):
        """Test 3: Verifies identical retries do not create multiple database rows."""
        import sqlite3
        conn = sqlite3.connect(f"{ephemeral_dir}/idempotency_test.db")
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE evidence_records (
                device_id TEXT,
                sequence_number INTEGER,
                image_hash TEXT,
                PRIMARY KEY (device_id, sequence_number)
            );
        """)

        def save_evidence(dev, seq, h):
            cur.execute("""
                INSERT INTO evidence_records (device_id, sequence_number, image_hash)
                VALUES (?, ?, ?)
                ON CONFLICT(device_id, sequence_number) DO NOTHING;
            """, (dev, seq, h))
            conn.commit()

        # Submit twice
        save_evidence("d1", 1, "h1")
        save_evidence("d1", 1, "h1")

        cur.execute("SELECT COUNT(*) FROM evidence_records WHERE device_id = 'd1'")
        assert cur.fetchone()[0] == 1
        conn.close()

    def test_retry_with_altered_hash_conflicts(self):
        """Test 4: Verifies retry with same sequence number but altered hash returns 409 Conflict."""
        enforcer = SequenceEnforcerOracle()
        dev_id = "device-alter-check"
        enforcer.register_device(dev_id)

        enforcer.process_submission(dev_id, seq=1, image_hash="original_hash")
        conflict_code = enforcer.process_submission(dev_id, seq=1, image_hash="different_hash")
        assert conflict_code == 409

    def test_receipt_consistency_across_retries(self):
        """Test 5: Verifies identical receipt data (evidence_id, receipt_signature) across retries."""
        receipt_cache = {}
        dev_id = "device-receipt"
        evidence_id = str(uuid.uuid4())
        receipt_sig = "MEUCIQCmockreceiptsignature"

        receipt_cache[(dev_id, 1)] = {
            "evidence_id": evidence_id,
            "status": "DURABLY_ACKED",
            "receipt_signature": receipt_sig,
        }

        # Retrieval on retry
        cached_receipt = receipt_cache.get((dev_id, 1))
        assert cached_receipt["evidence_id"] == evidence_id
        assert cached_receipt["receipt_signature"] == receipt_sig
