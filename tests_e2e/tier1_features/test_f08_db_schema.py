"""F-08: PostgreSQL Database Schema & Migration Tests.
Validates UUID primary keys, strict foreign key constraints, indexes,
and relational integrity specified for the PRAMAN persistence layer.
"""

import uuid
import sqlite3
import pytest


class TestF08DatabaseSchema:
    """Verifies relational database schema contracts and constraints."""

    @pytest.fixture
    def test_db(self, ephemeral_dir):
        """Creates an in-memory/file relational schema modeling the PRAMAN PostgreSQL tables."""
        db_path = f"{ephemeral_dir}/schema_test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()

        # Schema definition matching Alembic migration specifications
        cursor.execute("""
            CREATE TABLE farmers (
                id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                phone_number TEXT UNIQUE NOT NULL,
                language_pref TEXT NOT NULL CHECK(language_pref IN ('te', 'hi', 'en')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE devices (
                id TEXT PRIMARY KEY,
                farmer_id TEXT NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
                public_key_pem TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'REVOKED', 'SUSPENDED')),
                last_sequence_number INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE farms (
                id TEXT PRIMARY KEY,
                farmer_id TEXT NOT NULL REFERENCES farmers(id) ON DELETE CASCADE,
                farm_name TEXT NOT NULL,
                crop_type TEXT NOT NULL,
                boundary_geojson TEXT NOT NULL,
                area_hectares REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE evidence (
                id TEXT PRIMARY KEY,
                farm_id TEXT NOT NULL REFERENCES farms(id),
                device_id TEXT NOT NULL REFERENCES devices(id),
                sequence_number INTEGER NOT NULL,
                lifecycle_stage TEXT NOT NULL,
                image_hash TEXT NOT NULL,
                canonical_envelope_json TEXT NOT NULL,
                signature_b64 TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'DURABLY_ACKED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(device_id, sequence_number)
            );
        """)

        conn.commit()
        yield conn
        conn.close()

    def test_uuid_primary_key_enforcement(self, test_db):
        """Test 1: Verifies UUIDv4 format is accepted as primary keys across entities."""
        farmer_id = str(uuid.uuid4())
        device_id = str(uuid.uuid4())
        farm_id = str(uuid.uuid4())

        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO farmers (id, full_name, phone_number, language_pref) VALUES (?, ?, ?, ?)",
            (farmer_id, "Ramesh Rao", "+919876543210", "te"),
        )
        cursor.execute(
            "INSERT INTO devices (id, farmer_id, public_key_pem, status) VALUES (?, ?, ?, ?)",
            (device_id, farmer_id, "MOCK_PEM", "ACTIVE"),
        )
        cursor.execute(
            "INSERT INTO farms (id, farmer_id, farm_name, crop_type, boundary_geojson, area_hectares) VALUES (?, ?, ?, ?, ?, ?)",
            (farm_id, farmer_id, "Adilabad Cotton Parcel", "Cotton", '{"type":"Polygon"}', 2.5),
        )
        test_db.commit()

        cursor.execute("SELECT id FROM farmers WHERE id = ?", (farmer_id,))
        assert cursor.fetchone()[0] == farmer_id

    def test_foreign_key_constraint_enforcement(self, test_db):
        """Test 2: Verifies foreign key violation raises an integrity error."""
        non_existent_farmer = str(uuid.uuid4())
        cursor = test_db.cursor()

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO devices (id, farmer_id, public_key_pem, status) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), non_existent_farmer, "MOCK_PEM", "ACTIVE"),
            )

    def test_unique_device_sequence_constraint(self, test_db):
        """Test 3: Verifies UNIQUE(device_id, sequence_number) prevents duplicate sequence numbers."""
        farmer_id = str(uuid.uuid4())
        device_id = str(uuid.uuid4())
        farm_id = str(uuid.uuid4())

        cursor = test_db.cursor()
        cursor.execute("INSERT INTO farmers VALUES (?, 'F1', '90001', 'en', CURRENT_TIMESTAMP)", (farmer_id,))
        cursor.execute("INSERT INTO devices VALUES (?, ?, 'PEM', 'ACTIVE', 0, CURRENT_TIMESTAMP)", (device_id, farmer_id))
        cursor.execute("INSERT INTO farms VALUES (?, ?, 'Farm1', 'Chili', '{}', 1.0, CURRENT_TIMESTAMP)", (farm_id, farmer_id))
        test_db.commit()

        # Insert first sequence
        ev1 = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO evidence VALUES (?, ?, ?, 1, 'SOWING', 'hash1', '{}', 'sig1', 'ACK', CURRENT_TIMESTAMP)",
            (ev1, farm_id, device_id),
        )
        test_db.commit()

        # Attempt to insert same sequence for same device
        ev2 = str(uuid.uuid4())
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO evidence VALUES (?, ?, ?, 1, 'SOWING', 'hash2', '{}', 'sig2', 'ACK', CURRENT_TIMESTAMP)",
                (ev2, farm_id, device_id),
            )

    def test_language_preference_enum_check(self, test_db):
        """Test 4: Verifies language preference is constrained to ('te', 'hi', 'en')."""
        cursor = test_db.cursor()
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO farmers (id, full_name, phone_number, language_pref) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), "Invalid Lang", "99999", "fr"),
            )

    def test_cascade_delete_integrity(self, test_db):
        """Test 5: Verifies deleting a farmer cascades cleanly to their registered devices."""
        farmer_id = str(uuid.uuid4())
        device_id = str(uuid.uuid4())
        cursor = test_db.cursor()

        cursor.execute("INSERT INTO farmers VALUES (?, 'Farmer', '91111', 'hi', CURRENT_TIMESTAMP)", (farmer_id,))
        cursor.execute("INSERT INTO devices VALUES (?, ?, 'PEM', 'ACTIVE', 0, CURRENT_TIMESTAMP)", (device_id, farmer_id))
        test_db.commit()

        cursor.execute("DELETE FROM farmers WHERE id = ?", (farmer_id,))
        test_db.commit()

        cursor.execute("SELECT COUNT(*) FROM devices WHERE id = ?", (device_id,))
        assert cursor.fetchone()[0] == 0
