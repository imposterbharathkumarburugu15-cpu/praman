"""Canonical evidence envelope fixtures and generators for PRAMAN E2E testing.
Adheres strictly to RFC 8785 canonical serialization and the Interface Contract.
"""

import uuid
import base64
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric import ec

from crypto.envelope import (
    EvidenceEnvelope,
    EvidenceMetadata,
    VALID_LIFECYCLE_STAGES,
    VALID_CAPTURE_SOURCES,
)
from crypto.rfc8785 import canonicalize
from crypto.ecdsa_p256 import sign


class EnvelopeFactory:
    """Factory for building valid and deliberately mutated evidence envelopes."""

    @staticmethod
    def create_valid_envelope(
        device_id: Optional[str] = None,
        evidence_id: Optional[str] = None,
        farm_id: Optional[str] = None,
        image_hash: str = "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
        lifecycle_stage: str = "CROP_GROWTH",
        sequence_number: int = 1,
        capture_source: str = "CAMERA",
        latitude: float = 17.385044,
        longitude: float = 78.486671,
        gps_accuracy: float = 3.5,
        capture_timestamp: Optional[str] = None,
        schema_version: str = "1.0",
    ) -> Dict[str, Any]:
        """Creates a schema-compliant evidence envelope dictionary backed by EvidenceEnvelope."""
        if capture_timestamp is None:
            capture_timestamp = datetime.now(timezone.utc).isoformat()

        env_obj = EvidenceEnvelope(
            schema_version=schema_version,
            evidence_id=evidence_id or str(uuid.uuid4()),
            device_id=device_id or str(uuid.uuid4()),
            farm_id=farm_id or str(uuid.uuid4()),
            sequence_number=sequence_number,
            lifecycle_stage=lifecycle_stage,
            image_hash=image_hash,
            metadata=EvidenceMetadata(
                capture_source=capture_source,
                capture_timestamp=capture_timestamp,
                gps_accuracy=gps_accuracy,
                latitude=latitude,
                longitude=longitude,
            ),
        )
        return env_obj.to_dict()

    @staticmethod
    def sign_envelope(
        envelope: Dict[str, Any],
        private_key: ec.EllipticCurvePrivateKey,
    ) -> Tuple[bytes, str, bytes]:
        """Canonicalizes envelope via RFC 8785 and signs it with P-256 ECDSA.
        
        Returns:
            (canonical_bytes, base64_der_signature, raw_der_signature)
        """
        canonical_bytes = canonicalize(envelope)
        raw_sig = sign(private_key, canonical_bytes)
        b64_sig = base64.b64encode(raw_sig).decode("utf-8")
        return canonical_bytes, b64_sig, raw_sig
