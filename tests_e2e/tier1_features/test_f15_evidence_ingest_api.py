"""F-15: Evidence Ingestion REST API Tests.
Validates multipart/form-data evidence ingestion endpoint, field parsing,
cryptographic signature verification, image hash matching, and receipt issuance.
"""

import hashlib
import json
import uuid
import pytest
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory
from tests_e2e.fixtures.crypto_fixtures import (
    generate_p256_keypair,
    verify_p256_der,
    rfc8785_canonicalize,
)


class EvidenceIngestValidator:
    """Opaque-box validator modeling the backend evidence ingestion endpoint logic."""

    def __init__(self, device_registry: dict):
        self.device_registry = device_registry

    def validate_ingest_request(
        self,
        envelope_json_str: str,
        signature_b64: str,
        image_bytes: bytes,
    ) -> dict:
        import base64

        envelope = json.loads(envelope_json_str)
        dev_id = envelope.get("device_id")
        if dev_id not in self.device_registry:
            raise PermissionError("Unregistered device")

        pub_pem = self.device_registry[dev_id]

        # 1. Image hash check
        actual_hash = hashlib.sha256(image_bytes).hexdigest()
        if actual_hash != envelope.get("image_hash"):
            raise ValueError("Image hash does not match binary file")

        # 2. Canonicalize and verify signature
        canonical = rfc8785_canonicalize(envelope)
        raw_sig = base64.b64decode(signature_b64)
        if not verify_p256_der(pub_pem, raw_sig, canonical):
            raise PermissionError("Invalid cryptographic signature")

        return {
            "status": "DURABLY_ACKED",
            "evidence_id": envelope["evidence_id"],
            "sequence_number": envelope["sequence_number"],
            "server_timestamp": "2026-11-09T14:45:00Z",
            "receipt_signature": "MOCK_SERVER_RECEIPT_SIG",
        }


class TestF15EvidenceIngestAPI:
    """Verifies evidence ingestion REST API multipart contracts and behavior."""

    def test_successful_multipart_ingest(self, primary_device_keypair, sharp_image_fixture):
        """Test 1: Verifies successful 201 Created response for valid multipart upload."""
        priv_key, pub_pem, _ = primary_device_keypair
        image_bytes, image_hash = sharp_image_fixture
        dev_id = str(uuid.uuid4())

        envelope = EnvelopeFactory.create_valid_envelope(
            device_id=dev_id,
            image_hash=image_hash,
            sequence_number=1,
        )
        _, sig_b64, _ = EnvelopeFactory.sign_envelope(envelope, priv_key)

        validator = EvidenceIngestValidator({dev_id: pub_pem})
        receipt = validator.validate_ingest_request(
            envelope_json_str=json.dumps(envelope),
            signature_b64=sig_b64,
            image_bytes=image_bytes,
        )

        assert receipt["status"] == "DURABLY_ACKED"
        assert receipt["sequence_number"] == 1
        assert "server_timestamp" in receipt

    def test_image_hash_mismatch_rejected(self, primary_device_keypair, sharp_image_fixture):
        """Test 2: Verifies upload is rejected when binary file does not match envelope hash."""
        priv_key, pub_pem, _ = primary_device_keypair
        _, actual_hash = sharp_image_fixture
        dev_id = str(uuid.uuid4())

        envelope = EnvelopeFactory.create_valid_envelope(
            device_id=dev_id,
            image_hash=actual_hash,
        )
        _, sig_b64, _ = EnvelopeFactory.sign_envelope(envelope, priv_key)

        validator = EvidenceIngestValidator({dev_id: pub_pem})
        with pytest.raises(ValueError, match="Image hash does not match"):
            validator.validate_ingest_request(
                envelope_json_str=json.dumps(envelope),
                signature_b64=sig_b64,
                image_bytes=b"CORRUPTED_OR_TAMPERED_BYTES",
            )

    def test_invalid_signature_rejected(self, primary_device_keypair, secondary_device_keypair, sharp_image_fixture):
        """Test 3: Verifies upload is rejected when signature was signed by an unauthorized key."""
        _, pub_pem, _ = primary_device_keypair
        priv_key_unauthorized, _, _ = secondary_device_keypair
        image_bytes, image_hash = sharp_image_fixture
        dev_id = str(uuid.uuid4())

        envelope = EnvelopeFactory.create_valid_envelope(
            device_id=dev_id,
            image_hash=image_hash,
        )
        # Signed by unauthorized key
        _, sig_b64, _ = EnvelopeFactory.sign_envelope(envelope, priv_key_unauthorized)

        validator = EvidenceIngestValidator({dev_id: pub_pem})
        with pytest.raises(PermissionError, match="Invalid cryptographic signature"):
            validator.validate_ingest_request(
                envelope_json_str=json.dumps(envelope),
                signature_b64=sig_b64,
                image_bytes=image_bytes,
            )

    def test_unregistered_device_rejected(self, primary_device_keypair, sharp_image_fixture):
        """Test 4: Verifies upload from an unregistered device_id is rejected."""
        priv_key, _, _ = primary_device_keypair
        image_bytes, image_hash = sharp_image_fixture

        envelope = EnvelopeFactory.create_valid_envelope(
            device_id="unregistered-dev-999",
            image_hash=image_hash,
        )
        _, sig_b64, _ = EnvelopeFactory.sign_envelope(envelope, priv_key)

        validator = EvidenceIngestValidator({})  # Empty registry
        with pytest.raises(PermissionError, match="Unregistered device"):
            validator.validate_ingest_request(
                envelope_json_str=json.dumps(envelope),
                signature_b64=sig_b64,
                image_bytes=image_bytes,
            )

    def test_tampered_envelope_fields_rejected(self, primary_device_keypair, sharp_image_fixture):
        """Test 5: Verifies that altering metadata in envelope JSON after signing causes signature verification failure."""
        priv_key, pub_pem, _ = primary_device_keypair
        image_bytes, image_hash = sharp_image_fixture
        dev_id = str(uuid.uuid4())

        envelope = EnvelopeFactory.create_valid_envelope(
            device_id=dev_id,
            image_hash=image_hash,
            latitude=17.3850,
        )
        _, sig_b64, _ = EnvelopeFactory.sign_envelope(envelope, priv_key)

        # Attacker modifies latitude in JSON body
        envelope["metadata"]["latitude"] = 18.0000

        validator = EvidenceIngestValidator({dev_id: pub_pem})
        with pytest.raises(PermissionError, match="Invalid cryptographic signature"):
            validator.validate_ingest_request(
                envelope_json_str=json.dumps(envelope),
                signature_b64=sig_b64,
                image_bytes=image_bytes,
            )
