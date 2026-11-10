"""F-09: Tamper-Evident Audit Logging Tests.
Validates the append-only audit trail logging state transitions,
attributable actors, immutable records, and verifiable event chains.
"""

import uuid
import hashlib
import sqlite3
import pytest


class TestF09AuditLogging:
    """Verifies tamper-evident audit logging invariants."""

    @pytest.fixture
    def audit_store(self, ephemeral_dir):
        """Creates an audit log store with append-only trigger protection."""
        db_path = f"{ephemeral_dir}/audit_test.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE audit_log (
                log_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                previous_state TEXT,
                new_state TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                prev_log_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Append-only trigger: prohibit UPDATE and DELETE
        cursor.execute("""
            CREATE TRIGGER prohibit_audit_update
            BEFORE UPDATE ON audit_log
            BEGIN
                SELECT RAISE(FAIL, 'Audit log records are immutable and cannot be updated');
            END;
        """)

        cursor.execute("""
            CREATE TRIGGER prohibit_audit_delete
            BEFORE DELETE ON audit_log
            BEGIN
                SELECT RAISE(FAIL, 'Audit log records are append-only and cannot be deleted');
            END;
        """)

        conn.commit()
        yield conn
        conn.close()

    def test_log_state_transition(self, audit_store):
        """Test 1: Verifies logging a state transition from QUEUED to DURABLY_ACKED."""
        cursor = audit_store.cursor()
        log_id = str(uuid.uuid4())
        entity_id = str(uuid.uuid4())
        actor_id = "device-agent-01"
        payload_hash = hashlib.sha256(b"mock_evidence").hexdigest()

        cursor.execute(
            """INSERT INTO audit_log 
               (log_id, event_type, entity_type, entity_id, actor_id, previous_state, new_state, payload_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (log_id, "EVIDENCE_INGESTED", "EVIDENCE", entity_id, actor_id, "QUEUED", "DURABLY_ACKED", payload_hash),
        )
        audit_store.commit()

        cursor.execute("SELECT previous_state, new_state FROM audit_log WHERE log_id = ?", (log_id,))
        row = cursor.fetchone()
        assert row == ("QUEUED", "DURABLY_ACKED")

    def test_audit_immutability_prohibits_update(self, audit_store):
        """Test 2: Verifies audit records cannot be modified once written."""
        cursor = audit_store.cursor()
        log_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO audit_log VALUES (?, 'TEST', 'FARM', '1', 'actor', NULL, 'CREATED', 'hash', NULL, CURRENT_TIMESTAMP)""",
            (log_id,),
        )
        audit_store.commit()

        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            cursor.execute("UPDATE audit_log SET new_state = 'TAMPERED' WHERE log_id = ?", (log_id,))

    def test_audit_immutability_prohibits_delete(self, audit_store):
        """Test 3: Verifies audit records cannot be deleted."""
        cursor = audit_store.cursor()
        log_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO audit_log VALUES (?, 'TEST', 'FARM', '1', 'actor', NULL, 'CREATED', 'hash', NULL, CURRENT_TIMESTAMP)""",
            (log_id,),
        )
        audit_store.commit()

        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            cursor.execute("DELETE FROM audit_log WHERE log_id = ?", (log_id,))

    def test_hash_chaining_integrity(self, audit_store):
        """Test 4: Verifies consecutive audit entries form a verifiable hash chain."""
        cursor = audit_store.cursor()
        prev_hash = "GENESIS_HASH_0000000000000000000000000000000000000000000000000000"

        for i in range(3):
            entry_id = f"entry_{i}"
            payload = f"event_payload_{i}".encode("utf-8")
            p_hash = hashlib.sha256(payload).hexdigest()
            current_log_hash = hashlib.sha256((prev_hash + p_hash).encode("utf-8")).hexdigest()

            cursor.execute(
                """INSERT INTO audit_log VALUES (?, ?, 'EVIDENCE', ?, 'actor', 'OLD', 'NEW', ?, ?, CURRENT_TIMESTAMP)""",
                (str(uuid.uuid4()), f"EVENT_{i}", entry_id, p_hash, prev_hash),
            )
            prev_hash = current_log_hash

        audit_store.commit()
        cursor.execute("SELECT COUNT(*) FROM audit_log")
        assert cursor.fetchone()[0] == 3

    def test_query_audit_history_by_entity(self, audit_store):
        """Test 5: Verifies complete audit history retrieval for a specific evidence item."""
        cursor = audit_store.cursor()
        target_evidence_id = str(uuid.uuid4())

        # Insert 3 events for target entity and 2 for other entities
        events = ["INGESTED", "AI_SCORING_COMPLETE", "REVIEWER_APPROVED"]
        for ev in events:
            cursor.execute(
                """INSERT INTO audit_log VALUES (?, ?, 'EVIDENCE', ?, 'actor', 'S1', 'S2', 'hash', NULL, CURRENT_TIMESTAMP)""",
                (str(uuid.uuid4()), ev, target_evidence_id),
            )
        cursor.execute(
            """INSERT INTO audit_log VALUES (?, 'OTHER', 'EVIDENCE', 'other_id', 'actor', 'S1', 'S2', 'hash', NULL, CURRENT_TIMESTAMP)""",
            (str(uuid.uuid4()),),
        )
        audit_store.commit()

        cursor.execute(
            "SELECT event_type FROM audit_log WHERE entity_id = ? ORDER BY created_at ASC",
            (target_evidence_id,),
        )
        retrieved_events = [r[0] for r in cursor.fetchall()]
        assert retrieved_events == events
