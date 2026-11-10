"""Canonical Evidence Envelope data models and cryptographic serialization.

Conforms to PRAMAN Specification Contract 1:
- Binding: image SHA-256, capture metadata, GPS coordinates, device ID, sequence number, schema version.
- Serialization: RFC 8785 (JCS) JSON canonicalization.
- Signing: P-256 ECDSA over SHA-256 digest of canonical envelope bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Literal, Union

from cryptography.hazmat.primitives.asymmetric import ec

from crypto.ecdsa_p256 import sign as ec_sign, verify as ec_verify
from crypto.rfc8785 import canonicalize, canonicalize_str

VALID_LIFECYCLE_STAGES = (
    "SOWING",
    "INPUT_APPLICATION",
    "CROP_GROWTH",
    "HARVEST",
    "STORAGE",
)

VALID_CAPTURE_SOURCES = ("CAMERA", "FILE_UPLOAD")


@dataclass
class EvidenceMetadata:
    """Capture metadata for agricultural evidence."""

    capture_source: Literal["CAMERA", "FILE_UPLOAD"]
    capture_timestamp: str  # ISO 8601 UTC timestamp, e.g. 2026-11-09T14:30:00Z
    gps_accuracy: float  # Horizontal accuracy in meters (> 0.0)
    latitude: float  # WGS84 latitude [-90.0, +90.0]
    longitude: float  # WGS84 longitude [-180.0, +180.0]

    def __post_init__(self):
        if self.capture_source not in VALID_CAPTURE_SOURCES:
            raise ValueError(
                f"Invalid capture_source '{self.capture_source}'. Must be one of {VALID_CAPTURE_SOURCES}"
            )
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError(f"Latitude {self.latitude} out of bounds [-90.0, 90.0]")
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValueError(
                f"Longitude {self.longitude} out of bounds [-180.0, 180.0]"
            )
        if self.gps_accuracy <= 0.0:
            raise ValueError(f"gps_accuracy must be > 0.0, got {self.gps_accuracy}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capture_source": self.capture_source,
            "capture_timestamp": self.capture_timestamp,
            "gps_accuracy": float(self.gps_accuracy),
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceMetadata:
        return cls(
            capture_source=data["capture_source"],
            capture_timestamp=data["capture_timestamp"],
            gps_accuracy=float(data["gps_accuracy"]),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
        )


@dataclass
class EvidenceEnvelope:
    """Canonical Evidence Envelope binding physical and logical evidence attributes."""

    device_id: str
    evidence_id: str
    farm_id: str
    image_hash: str  # 64 lowercase hex characters
    lifecycle_stage: Literal[
        "SOWING", "INPUT_APPLICATION", "CROP_GROWTH", "HARVEST", "STORAGE"
    ]
    metadata: EvidenceMetadata
    schema_version: str = "1.0"
    sequence_number: int = 1

    def __post_init__(self):
        if self.lifecycle_stage not in VALID_LIFECYCLE_STAGES:
            raise ValueError(
                f"Invalid lifecycle_stage '{self.lifecycle_stage}'. Must be one of {VALID_LIFECYCLE_STAGES}"
            )
        if self.sequence_number < 1:
            raise ValueError(
                f"sequence_number must be >= 1, got {self.sequence_number}"
            )
        if self.schema_version != "1.0":
            raise ValueError(
                f"Unsupported schema_version '{self.schema_version}'. Expected '1.0'"
            )
        # Validate image hash format (64 hex characters)
        if not re.fullmatch(r"^[0-9a-f]{64}$", self.image_hash.lower()):
            raise ValueError(
                f"image_hash must be a 64-character lowercase hex string, got '{self.image_hash}'"
            )
        # Ensure metadata is an EvidenceMetadata instance
        if isinstance(self.metadata, dict):
            self.metadata = EvidenceMetadata.from_dict(self.metadata)

    def to_dict(self) -> Dict[str, Any]:
        """Convert envelope to dictionary with nested metadata."""
        return {
            "device_id": str(self.device_id),
            "evidence_id": str(self.evidence_id),
            "farm_id": str(self.farm_id),
            "image_hash": str(self.image_hash).lower(),
            "lifecycle_stage": self.lifecycle_stage,
            "metadata": self.metadata.to_dict(),
            "schema_version": self.schema_version,
            "sequence_number": int(self.sequence_number),
        }

    def to_canonical_bytes(self) -> bytes:
        """Serialize envelope into RFC 8785 canonical UTF-8 bytes."""
        return canonicalize(self.to_dict())

    def to_canonical_str(self) -> str:
        """Serialize envelope into RFC 8785 canonical UTF-8 string."""
        return canonicalize_str(self.to_dict())

    def to_canonical_sha256(self) -> str:
        """Compute SHA-256 hex digest of the canonical envelope bytes."""
        return hashlib.sha256(self.to_canonical_bytes()).hexdigest()

    def to_canonical_sha256_bytes(self) -> bytes:
        """Compute raw 32-byte SHA-256 digest of the canonical envelope bytes."""
        return hashlib.sha256(self.to_canonical_bytes()).digest()

    def to_merkle_leaf_hash(self) -> bytes:
        """Compute domain-separated Merkle leaf hash: SHA-256(0x00 || canonical_bytes)."""
        return hashlib.sha256(b"\x00" + self.to_canonical_bytes()).digest()

    def to_merkle_leaf_hash_hex(self) -> str:
        """Compute 64-hex domain-separated Merkle leaf hash."""
        return self.to_merkle_leaf_hash().hex()

    def sign(
        self,
        private_key: ec.EllipticCurvePrivateKey,
        sig_format: Literal["der", "p1363"] = "der",
    ) -> bytes:
        """Sign the canonical envelope bytes using the device's P-256 private key.

        Enforces low-s normalization.
        """
        return ec_sign(private_key, self.to_canonical_bytes(), sig_format=sig_format)

    def verify_signature(
        self,
        public_key: Union[ec.EllipticCurvePublicKey, str, bytes],
        signature: Union[bytes, str],
    ) -> bool:
        """Verify a P-256 ECDSA signature over the canonical envelope bytes."""
        return ec_verify(public_key, signature, self.to_canonical_bytes())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceEnvelope:
        """Create an EvidenceEnvelope instance from a dictionary."""
        meta = data.get("metadata", {})
        if isinstance(meta, dict):
            metadata_obj = EvidenceMetadata.from_dict(meta)
        elif isinstance(meta, EvidenceMetadata):
            metadata_obj = meta
        else:
            raise TypeError(f"Invalid metadata type: {type(meta)}")

        return cls(
            device_id=str(data["device_id"]),
            evidence_id=str(data["evidence_id"]),
            farm_id=str(data["farm_id"]),
            image_hash=str(data["image_hash"]).lower(),
            lifecycle_stage=data["lifecycle_stage"],
            metadata=metadata_obj,
            schema_version=data.get("schema_version", "1.0"),
            sequence_number=int(data.get("sequence_number", 1)),
        )

    @classmethod
    def from_json(cls, json_data: Union[str, bytes]) -> EvidenceEnvelope:
        """Parse an EvidenceEnvelope from JSON string or UTF-8 bytes."""
        if isinstance(json_data, bytes):
            json_data = json_data.decode("utf-8")
        parsed = json.loads(json_data)
        return cls.from_dict(parsed)
