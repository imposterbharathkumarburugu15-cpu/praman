"""F-03: Evidence Envelope Schema & Serialization Tests.
Validates the canonical evidence envelope structure binding image SHA-256,
device identity, sequence number, lifecycle stage, and capture metadata.
"""

import hashlib
import pytest
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory, VALID_LIFECYCLE_STAGES
from tests_e2e.fixtures.crypto_fixtures import rfc8785_canonicalize


class TestF03EvidenceEnvelope:
    """Verifies evidence envelope schema conformity and serialization invariants."""

    def test_valid_envelope_structure(self, sample_envelope):
        """Test 1: Verifies all mandatory top-level fields are present and typed correctly."""
        required_keys = {
            "device_id",
            "evidence_id",
            "farm_id",
            "image_hash",
            "lifecycle_stage",
            "metadata",
            "schema_version",
            "sequence_number",
        }
        assert required_keys.issubset(sample_envelope.keys())
        assert sample_envelope["schema_version"] == "1.0"
        assert isinstance(sample_envelope["sequence_number"], int)
        assert len(sample_envelope["image_hash"]) == 64

    def test_metadata_structure_and_constraints(self, sample_envelope):
        """Test 2: Verifies nested metadata contains capture source, timestamp, and coordinates."""
        metadata = sample_envelope["metadata"]
        assert "capture_source" in metadata
        assert metadata["capture_source"] in ("CAMERA", "FILE_UPLOAD")
        assert "capture_timestamp" in metadata
        assert -90.0 <= metadata["latitude"] <= 90.0
        assert -180.0 <= metadata["longitude"] <= 180.0
        assert metadata["gps_accuracy"] > 0

    def test_lifecycle_stage_enumeration(self):
        """Test 3: Verifies all defined agricultural lifecycle stages are supported."""
        for stage in VALID_LIFECYCLE_STAGES:
            env = EnvelopeFactory.create_valid_envelope(lifecycle_stage=stage)
            assert env["lifecycle_stage"] == stage
            canonical = rfc8785_canonicalize(env)
            assert stage.encode("utf-8") in canonical

    def test_hash_binding_integrity(self):
        """Test 4: Verifies image SHA-256 hash in envelope is bound to canonical representation."""
        fake_image_bytes = b"MOCK_JPEG_PAYLOAD_FOR_HASH_TEST"
        actual_hash = hashlib.sha256(fake_image_bytes).hexdigest()

        env = EnvelopeFactory.create_valid_envelope(image_hash=actual_hash)
        canonical = rfc8785_canonicalize(env)
        envelope_digest = hashlib.sha256(canonical).hexdigest()

        assert actual_hash.encode("utf-8") in canonical
        assert len(envelope_digest) == 64

    def test_canonical_serialization_determinism(self):
        """Test 5: Verifies identical envelope data yields byte-for-byte identical canonical serialization."""
        env1 = EnvelopeFactory.create_valid_envelope(
            device_id="d1",
            evidence_id="e1",
            farm_id="f1",
            sequence_number=10,
            capture_timestamp="2026-11-09T14:00:00Z",
        )
        env2 = dict(env1)

        c1 = rfc8785_canonicalize(env1)
        c2 = rfc8785_canonicalize(env2)
        assert c1 == c2
