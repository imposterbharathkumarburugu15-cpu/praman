"""Shared fixtures and test data for crypto unit test suite."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from crypto.ecdsa_p256 import generate_keypair
from crypto.envelope import EvidenceEnvelope, EvidenceMetadata


@pytest.fixture
def keypair():
    """Returns a fresh (private_key, public_key) P-256 pair."""
    return generate_keypair()


@pytest.fixture
def secondary_keypair():
    """Returns a second fresh (private_key, public_key) P-256 pair."""
    return generate_keypair()


@pytest.fixture
def sample_metadata() -> EvidenceMetadata:
    """Returns a valid EvidenceMetadata instance."""
    return EvidenceMetadata(
        capture_source="CAMERA",
        capture_timestamp="2026-11-09T14:30:00Z",
        gps_accuracy=3.5,
        latitude=17.385044,
        longitude=78.486671,
    )


@pytest.fixture
def contract1_envelope_dict():
    """Normative Contract 1 envelope dictionary from PROJECT.md."""
    return {
        "device_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "evidence_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "farm_id": "b1b11b11-1111-1111-1111-111111111111",
        "image_hash": "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
        "lifecycle_stage": "CROP_GROWTH",
        "metadata": {
            "capture_source": "CAMERA",
            "capture_timestamp": "2026-11-09T14:30:00Z",
            "gps_accuracy": 3.5,
            "latitude": 17.385044,
            "longitude": 78.486671,
        },
        "schema_version": "1.0",
        "sequence_number": 42,
    }


@pytest.fixture
def sample_envelope(contract1_envelope_dict) -> EvidenceEnvelope:
    """Returns a valid EvidenceEnvelope instance built from Contract 1 data."""
    return EvidenceEnvelope.from_dict(contract1_envelope_dict)
