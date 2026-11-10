"""Tests for Canonical Evidence Envelope schema, validation, and signing."""

from __future__ import annotations

import hashlib
import pytest

from crypto.envelope import (
    VALID_LIFECYCLE_STAGES,
    EvidenceEnvelope,
    EvidenceMetadata,
)


class TestEvidenceEnvelope:
    """Verifies Evidence Envelope schema conformity, validation, and cryptographic binding."""

    def test_valid_envelope_structure(self, sample_envelope):
        """All mandatory fields present and correctly formatted."""
        env_dict = sample_envelope.to_dict()
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
        assert required_keys.issubset(env_dict.keys())
        assert sample_envelope.schema_version == "1.0"
        assert sample_envelope.sequence_number == 42
        assert len(sample_envelope.image_hash) == 64

    def test_metadata_field_validation(self):
        """Metadata validates coordinate bounds and accuracy."""
        # Valid metadata
        meta = EvidenceMetadata(
            capture_source="CAMERA",
            capture_timestamp="2026-11-09T14:30:00Z",
            gps_accuracy=2.0,
            latitude=17.5,
            longitude=78.5,
        )
        assert meta.latitude == 17.5

        # Latitude out of bounds
        with pytest.raises(ValueError, match="Latitude"):
            EvidenceMetadata(
                capture_source="CAMERA",
                capture_timestamp="2026-11-09T14:30:00Z",
                gps_accuracy=2.0,
                latitude=95.0,
                longitude=78.5,
            )

        # Longitude out of bounds
        with pytest.raises(ValueError, match="Longitude"):
            EvidenceMetadata(
                capture_source="CAMERA",
                capture_timestamp="2026-11-09T14:30:00Z",
                gps_accuracy=2.0,
                latitude=17.5,
                longitude=185.0,
            )

        # Non-positive accuracy
        with pytest.raises(ValueError, match="gps_accuracy"):
            EvidenceMetadata(
                capture_source="CAMERA",
                capture_timestamp="2026-11-09T14:30:00Z",
                gps_accuracy=0.0,
                latitude=17.5,
                longitude=78.5,
            )

        # Invalid capture source
        with pytest.raises(ValueError, match="capture_source"):
            EvidenceMetadata(
                capture_source="SATELLITE",  # type: ignore
                capture_timestamp="2026-11-09T14:30:00Z",
                gps_accuracy=2.0,
                latitude=17.5,
                longitude=78.5,
            )

    def test_lifecycle_stages_supported(self, sample_metadata):
        """All 5 defined lifecycle stages are supported."""
        dummy_hash = "a" * 64
        for stage in VALID_LIFECYCLE_STAGES:
            env = EvidenceEnvelope(
                device_id="dev-1",
                evidence_id="ev-1",
                farm_id="farm-1",
                image_hash=dummy_hash,
                lifecycle_stage=stage,
                metadata=sample_metadata,
            )
            assert env.lifecycle_stage == stage

        with pytest.raises(ValueError, match="lifecycle_stage"):
            EvidenceEnvelope(
                device_id="dev-1",
                evidence_id="ev-1",
                farm_id="farm-1",
                image_hash=dummy_hash,
                lifecycle_stage="MARKETING",  # type: ignore
                metadata=sample_metadata,
            )

    def test_image_hash_validation(self, sample_metadata):
        """image_hash must be exactly 64 lowercase hexadecimal characters."""
        with pytest.raises(ValueError, match="image_hash"):
            EvidenceEnvelope(
                device_id="dev-1",
                evidence_id="ev-1",
                farm_id="farm-1",
                image_hash="not_a_valid_sha256_hash",
                lifecycle_stage="CROP_GROWTH",
                metadata=sample_metadata,
            )

    def test_sequence_number_validation(self, sample_metadata):
        """sequence_number must be >= 1."""
        with pytest.raises(ValueError, match="sequence_number"):
            EvidenceEnvelope(
                device_id="dev-1",
                evidence_id="ev-1",
                farm_id="farm-1",
                image_hash="b" * 64,
                lifecycle_stage="CROP_GROWTH",
                metadata=sample_metadata,
                sequence_number=0,
            )

    def test_canonical_serialization_determinism(self, sample_envelope):
        """Identical envelope produces deterministic canonical bytes and digest."""
        c1 = sample_envelope.to_canonical_bytes()
        c2 = sample_envelope.to_canonical_bytes()
        assert c1 == c2

        # Contract 1 normative hash
        expected_sha = (
            "4ae6016abc79b01e20841a7614d8bfc9b045c39113dd4cad1da070969a0679c7"
        )
        assert sample_envelope.to_canonical_sha256() == expected_sha

    def test_envelope_signing_and_verification(
        self, sample_envelope, keypair, secondary_keypair
    ):
        """Sign canonical envelope with device private key and verify with public key."""
        priv_a, pub_a = keypair
        _, pub_b = secondary_keypair

        sig = sample_envelope.sign(priv_a)
        assert sample_envelope.verify_signature(pub_a, sig) is True
        # Cross-key rejection
        assert sample_envelope.verify_signature(pub_b, sig) is False

    def test_field_tampering_invalidates_signature(self, sample_envelope, keypair):
        """Any modification to the envelope invalidates the signature."""
        priv, pub = keypair
        sig = sample_envelope.sign(priv)
        assert sample_envelope.verify_signature(pub, sig) is True

        # Tamper sequence number
        d = sample_envelope.to_dict()
        d["sequence_number"] = 43
        tampered_env = EvidenceEnvelope.from_dict(d)
        assert tampered_env.verify_signature(pub, sig) is False

        # Tamper GPS latitude
        d2 = sample_envelope.to_dict()
        d2["metadata"]["latitude"] = 17.385045
        tampered_env2 = EvidenceEnvelope.from_dict(d2)
        assert tampered_env2.verify_signature(pub, sig) is False

        # Tamper image hash
        d3 = sample_envelope.to_dict()
        d3["image_hash"] = "f" * 64
        tampered_env3 = EvidenceEnvelope.from_dict(d3)
        assert tampered_env3.verify_signature(pub, sig) is False

    def test_json_roundtrip(self, sample_envelope):
        """Serialization to/from JSON string maintains identical canonical bytes."""
        json_str = sample_envelope.to_canonical_str()
        restored = EvidenceEnvelope.from_json(json_str)
        assert restored.to_canonical_sha256() == sample_envelope.to_canonical_sha256()

    def test_merkle_leaf_hash(self, sample_envelope):
        """Merkle leaf hash equals SHA-256(0x00 || canonical_bytes)."""
        expected = hashlib.sha256(
            b"\x00" + sample_envelope.to_canonical_bytes()
        ).digest()
        assert sample_envelope.to_merkle_leaf_hash() == expected
        assert sample_envelope.to_merkle_leaf_hash_hex() == expected.hex()
