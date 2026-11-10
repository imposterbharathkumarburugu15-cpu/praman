"""F-22: Exact Hash Duplicate Detection Tests.
Validates SHA-256 exact match lookups across historical evidence records
to detect identical image re-use and replay across farms and farmers.
Backed by genuine SQLAlchemy database models and queries.
"""

import hashlib
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.services.duplicate_service import DuplicateDetectionRepository


@pytest.fixture
def db_session():
    """Provides an isolated database session with genuine SQLite tables."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class TestF22ExactHashDedup:
    """Verifies SHA-256 exact duplicate detection against real DB."""

    def test_new_unique_image_not_duplicate(self, db_session, sharp_image_fixture):
        """Test 1: Verifies previously unseen image hash is classified as not duplicate."""
        repo = DuplicateDetectionRepository(db=db_session)
        _, img_hash = sharp_image_fixture

        res = repo.check_duplicate(img_hash)
        assert res["is_duplicate"] is False
        assert res["matched_evidence_id"] is None

    def test_exact_duplicate_detected(self, db_session, sharp_image_fixture):
        """Test 2: Verifies re-uploading identical image hash is identified as duplicate."""
        repo = DuplicateDetectionRepository(db=db_session)
        _, img_hash = sharp_image_fixture
        original_ev_id = str(uuid.uuid4())
        farmer_a = str(uuid.uuid4())

        repo.register(img_hash, original_ev_id, farmer_a)

        res = repo.check_duplicate(img_hash)
        assert res["is_duplicate"] is True
        assert res["matched_evidence_id"] == original_ev_id

    def test_cross_farmer_replay_detection(self, db_session, sharp_image_fixture):
        """Test 3: Verifies detecting when Farmer B submits an image originally submitted by Farmer A."""
        repo = DuplicateDetectionRepository(db=db_session)
        _, img_hash = sharp_image_fixture
        farmer_a = "farmer-ramesh"
        farmer_b = "farmer-suresh"

        repo.register(img_hash, "ev-101", farmer_a)

        res = repo.check_duplicate(img_hash)
        assert res["is_duplicate"] is True
        assert res["matched_farmer_id"] == farmer_a
        assert res["matched_farmer_id"] != farmer_b

    def test_multiple_independent_hashes(self, db_session):
        """Test 4: Verifies multiple unique hashes can be registered without false collisions."""
        repo = DuplicateDetectionRepository(db=db_session)
        hashes = [hashlib.sha256(f"unique_image_{i}".encode()).hexdigest() for i in range(10)]

        for i, h in enumerate(hashes):
            repo.register(h, f"ev-{i}", f"farmer-{i}")

        for i, h in enumerate(hashes):
            res = repo.check_duplicate(h)
            assert res["is_duplicate"] is True
            assert res["matched_evidence_id"] == f"ev-{i}"

    def test_single_byte_mutation_breaks_exact_match(self, db_session, sharp_image_fixture):
        """Test 5: Verifies that even 1 altered byte in image breaks exact SHA-256 match."""
        repo = DuplicateDetectionRepository(db=db_session)
        img_bytes, img_hash = sharp_image_fixture
        repo.register(img_hash, "ev-base", "farmer-base")

        # Mutate 1 byte
        mutated_bytes = bytearray(img_bytes)
        mutated_bytes[50] = (mutated_bytes[50] + 1) % 256
        mutated_hash = hashlib.sha256(mutated_bytes).hexdigest()

        res = repo.check_duplicate(mutated_hash)
        assert res["is_duplicate"] is False
