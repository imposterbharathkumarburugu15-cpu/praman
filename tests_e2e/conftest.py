"""Shared pytest fixtures for PRAMAN E2E test suite.
Provides cryptographic keys, synthetic image fixtures, canonical envelopes,
and temporary storage environments.
"""

import os
import shutil
import tempfile
import sqlite3
import pytest
from typing import Generator, Dict, Any, Tuple, List
from cryptography.hazmat.primitives.asymmetric import ec

from tests_e2e.fixtures.crypto_fixtures import (
    generate_p256_keypair,
    ReferenceMerkleTree,
)
from tests_e2e.fixtures.image_generator import SyntheticImageGenerator
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory


@pytest.fixture(scope="session")
def primary_device_keypair() -> Tuple[ec.EllipticCurvePrivateKey, str, bytes]:
    """Generates a primary mock P-256 device keypair for the test session."""
    return generate_p256_keypair()


@pytest.fixture(scope="session")
def secondary_device_keypair() -> Tuple[ec.EllipticCurvePrivateKey, str, bytes]:
    """Generates a secondary mock P-256 device keypair (e.g. for unauthorized or multi-device tests)."""
    return generate_p256_keypair()


@pytest.fixture
def ephemeral_dir() -> Generator[str, None, None]:
    """Yields a temporary directory cleaned up after each test."""
    temp_dir = tempfile.mkdtemp(prefix="praman_e2e_")
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_sqlite_queue(ephemeral_dir: str) -> Generator[sqlite3.Connection, None, None]:
    """Provides an SQLite database connection modeling the mobile offline queue table."""
    db_path = os.path.join(ephemeral_dir, "mobile_offline_queue.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE offline_evidence_queue (
            evidence_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            sequence_number INTEGER NOT NULL,
            envelope_json TEXT NOT NULL,
            signature_b64 TEXT NOT NULL,
            image_path TEXT NOT NULL,
            image_hash TEXT NOT NULL,
            sync_state TEXT NOT NULL DEFAULT 'QUEUED',
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced_at TIMESTAMP NULL
        );
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sharp_image_fixture() -> Tuple[bytes, str]:
    """Generates a high-quality sharp crop image."""
    return SyntheticImageGenerator.create_sharp_crop_image(1920, 1080)


@pytest.fixture
def blurry_image_fixture() -> Tuple[bytes, str]:
    """Generates an intentionally blurry image with low Laplacian variance."""
    return SyntheticImageGenerator.create_blurry_image(1920, 1080, blur_radius=25)


@pytest.fixture
def dark_image_fixture() -> Tuple[bytes, str]:
    """Generates an underexposed dark image."""
    return SyntheticImageGenerator.create_underexposed_image(1920, 1080)


@pytest.fixture
def blown_image_fixture() -> Tuple[bytes, str]:
    """Generates an overexposed washed out image."""
    return SyntheticImageGenerator.create_overexposed_image(1920, 1080)


@pytest.fixture
def sample_envelope() -> Dict[str, Any]:
    """Generates a valid evidence envelope."""
    return EnvelopeFactory.create_valid_envelope()


def pytest_collection_modifyitems(config, items):
    """Dynamically applies categorizations to collected pytest items for filtering."""
    for item in items:
        clean_id = item.nodeid.replace("\\", "/")

        # 1. Device Execution Mode Markers
        if "physical_device" in clean_id:
            item.add_marker(pytest.mark.physical_device)
        else:
            item.add_marker(pytest.mark.mock_device)

        # 2. Test Pyramid / Type Markers
        if "tier4_real_world" in clean_id or "tier3_interactions" in clean_id or "tier5_adversarial" in clean_id:
            item.add_marker(pytest.mark.e2e)
        elif any(f in clean_id for f in [
            "test_f08", "test_f09", "test_f10", "test_f11", "test_f12",
            "test_f13", "test_f14", "test_f15", "test_f16", "test_f17",
            "test_f40", "test_f41", "test_f42", "test_f43", "test_f44", "test_f45"
        ]):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)

        # 3. Security / Boundary Marker
        if "tier2_boundaries" in clean_id or "tier5_adversarial" in clean_id:
            item.add_marker(pytest.mark.security)
