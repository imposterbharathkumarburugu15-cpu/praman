"""Milestone M2 Empirical Image Stress & Duplicate Detection Challenge Test Suite.

Authored by Challenger M2 (Empirical Challenger / Critic / Specialist).
Empirically stress-tests:
1. Exact duplicates (byte identical payloads across sequences & devices) -> EXACT_DUPLICATE (dist=0)
2. JPEG recompression stress (q=95, q=80, q=50, q=20, q=10) -> POSSIBLE_VISUAL_DUPLICATE (dist<=6)
3. Geometric resizing stress (0.25x, 0.5x, 0.75x, 1.5x, 2.0x) -> POSSIBLE_VISUAL_DUPLICATE (dist<=6)
4. Cropping & watermarking stress (1%, 2%, 5% crops; text & corner patches) -> POSSIBLE_VISUAL_DUPLICATE / DUPLICATE_REQUIRES_REVIEW
5. Noise degradation stress (Gaussian noise, Salt & Pepper noise) -> POSSIBLE_VISUAL_DUPLICATE (dist<=6)
6. Boundary threshold verification (exact Hamming distances 0, 1, 6, 7, 10, 11, 64)
7. Entirely distinct images (sharp crop vs underexposed vs overexposed vs geometric vs uniform noise) -> NEW_EVIDENCE (dist>10)
8. Multi-candidate database indexing (verifying closest candidate selection across large DB)
9. Non-image & corrupted payload handling (safe hashing, graceful fallbacks)
10. Extreme dimension images (1x1, 8x8, 1000x2, 2x1000)
11. Exclude self-evidence ID parameter (avoid false self-matching on updates)
12. Strict Cross-Farmer Privacy boundary verification (receipt & API serialization)
"""

import io
import json
import uuid
import base64
import hashlib
from datetime import datetime, timezone
from typing import Tuple, List

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.models.farmer import Farmer
from backend.app.models.device import Device
from backend.app.models.farm import Farm
from backend.app.models.evidence import Evidence
from backend.app.models.audit_log import AuditLog
from backend.app.models.ai_assessment import AIAssessment
from backend.app.services.duplicate_service import (
    DuplicateService,
    DuplicateOutcome,
    DuplicateCheckResult,
    DuplicateDetectionRepository,
)
from backend.app.services.ai_dispatcher import ai_dispatcher
from crypto.ecdsa_p256 import generate_keypair, public_key_to_pem, sign
from crypto.rfc8785 import canonicalize
from tests_e2e.fixtures.image_generator import SyntheticImageGenerator
from ai_engine.hashing import (
    compute_sha256,
    compute_phash_64,
    compute_dhash_64,
    hamming_distance_hex,
    safe_compute_phash_64,
    safe_compute_dhash_64,
    safe_compute_all_hashes,
)


@pytest.fixture
def stress_db():
    """Isolated in-memory SQLite session for direct service stress tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = Session()

    # Pre-populate base farmer, farm, and device
    farmer = Farmer(
        id="stress-farmer-01",
        full_name="Stress Farmer A",
        phone_number="+919876543210",
        language_pref="en",
    )
    farm = Farm(
        id="stress-farm-01",
        farmer_id=farmer.id,
        farm_name="Empirical Test Farm",
        crop_type="Cotton",
        boundary_geojson='{"type":"Polygon","coordinates":[[[78.5,19.6],[78.51,19.6],[78.51,19.61],[78.5,19.61],[78.5,19.6]]]}',
    )
    device = Device(
        id="stress-device-01",
        farmer_id=farmer.id,
        public_key_pem="MOCK_PEM_01",
        status="ACTIVE",
        last_sequence_number=1,
    )
    session.add_all([farmer, farm, device])
    session.commit()

    try:
        yield session, farmer, farm, device
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def api_test_env(tmp_path):
    """Isolated database and TestClient for API endpoint stress tests."""
    db_file = str(tmp_path / "api_stress.db")
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    ai_dispatcher.set_session_factory(TestingSession)
    client = TestClient(app)

    yield client, TestingSession

    app.dependency_overrides.clear()
    ai_dispatcher.set_session_factory(None)
    engine.dispose()


def create_realistic_field_image(width=800, height=600) -> Image.Image:
    """Creates a synthetic image with continuous field textures, crops, and horizon."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for r in range(height):
        for c in range(width):
            arr[r, c, 0] = int(25 + 35 * (r / float(height)) + 12 * np.sin(c / 40.0))  # R
            arr[r, c, 1] = int(75 + 130 * (r / float(height)) + 25 * np.cos(r / 25.0)) # G
            arr[r, c, 2] = int(15 + 25 * (c / float(width)))                          # B
    return Image.fromarray(arr)


def image_to_jpeg_bytes(img: Image.Image, quality=95) -> bytes:
    """Converts a PIL image to JPEG bytes with specified quality."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def register_farmer_device_farm(client, name="Stress Farmer", phone=None, crop="Cotton"):
    """Helper to enroll farmer, active device, and registered farm via API."""
    phone_number = phone or f"+9198{uuid.uuid4().int % 100000000:08d}"
    rf = client.post("/api/v1/farmers", json={
        "full_name": name,
        "phone_number": phone_number,
        "language_pref": "en",
    })
    assert rf.status_code == 201
    farmer_id = rf.json()["id"]

    priv_key, pub_key = generate_keypair()
    pub_pem = public_key_to_pem(pub_key)
    device_id = str(uuid.uuid4())

    rd = client.post("/api/v1/devices/register", json={
        "device_id": device_id,
        "farmer_id": farmer_id,
        "public_key_pem": pub_pem,
    })
    assert rd.status_code == 201

    rfarm = client.post("/api/v1/farms", json={
        "farmer_id": farmer_id,
        "farm_name": f"{name}'s Farm",
        "crop_type": crop,
        "boundary_geojson": json.dumps({
            "type": "Polygon",
            "coordinates": [[[78.5, 19.6], [78.51, 19.6], [78.51, 19.61], [78.5, 19.61], [78.5, 19.6]]]
        }),
    })
    assert rfarm.status_code == 201
    farm_id = rfarm.json()["id"]

    return {
        "farmer_id": farmer_id,
        "device_id": device_id,
        "priv_key": priv_key,
        "pub_pem": pub_pem,
        "farm_id": farm_id,
    }


def build_signed_submission(device_info, seq: int, image_bytes: bytes, evidence_id=None):
    """Builds RFC 8785 canonical envelope and ECDSA P-256 signature."""
    img_hash = hashlib.sha256(image_bytes).hexdigest()
    ev_id = evidence_id or str(uuid.uuid4())
    envelope = {
        "device_id": device_info["device_id"],
        "evidence_id": ev_id,
        "farm_id": device_info["farm_id"],
        "image_hash": img_hash,
        "lifecycle_stage": "CROP_GROWTH",
        "metadata": {
            "capture_source": "CAMERA",
            "capture_timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_accuracy": 3.8,
            "latitude": 19.605,
            "longitude": 78.505,
        },
        "schema_version": "1.0",
        "sequence_number": seq,
    }
    canonical_bytes = canonicalize(envelope)
    sig_der = sign(device_info["priv_key"], canonical_bytes)
    sig_b64 = base64.b64encode(sig_der).decode("utf-8")

    files = {"file": ("evidence.jpg", image_bytes, "image/jpeg")}
    data = {"envelope": json.dumps(envelope), "signature": sig_b64}
    return data, files, envelope


class TestChallengerExactAndIdempotent:
    """Stress-tests exact byte duplicates and idempotency boundaries."""

    def test_exact_duplicate_byte_identical_detected(self, stress_db):
        """Stress: Byte-identical payload must yield EXACT_DUPLICATE with dist=0."""
        session, farmer, farm, device = stress_db
        base_img = create_realistic_field_image(800, 600)
        img_bytes = image_to_jpeg_bytes(base_img, quality=95)
        img_sha256 = compute_sha256(img_bytes)

        repo = DuplicateDetectionRepository(db=session)
        ev1 = repo.register(
            sha256_hash=img_sha256,
            evidence_id="ev-base-001",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(img_bytes),
            dhash=compute_dhash_64(img_bytes),
        )

        res = DuplicateService.evaluate_duplicate(session, img_bytes)
        assert res.classification == DuplicateOutcome.EXACT_DUPLICATE.value
        assert res.is_duplicate is True
        assert res.matched_evidence_id == "ev-base-001"
        assert res.hamming_distance == 0

    def test_same_image_different_filename_metadata(self, stress_db):
        """Stress: Same image submitted with different filenames/envelopes still yields EXACT_DUPLICATE."""
        session, farmer, farm, device = stress_db
        base_img = create_realistic_field_image(640, 480)
        img_bytes = image_to_jpeg_bytes(base_img, quality=90)
        img_sha256 = compute_sha256(img_bytes)

        repo = DuplicateDetectionRepository(db=session)
        repo.register(
            sha256_hash=img_sha256,
            evidence_id="ev-orig-file",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(img_bytes),
            dhash=compute_dhash_64(img_bytes),
        )

        # Evaluate duplicate directly
        res = DuplicateService.evaluate_duplicate(session, img_bytes)
        assert res.classification == "EXACT_DUPLICATE"
        assert res.is_duplicate is True
        assert res.matched_evidence_id == "ev-orig-file"


class TestChallengerRecompressionStress:
    """Stress-tests image recompression across multiple JPEG quality levels (q=95, 80, 50, 20, 10)."""

    @pytest.mark.parametrize("quality", [95, 80, 50, 20, 10])
    def test_recompression_quality_levels(self, stress_db, quality):
        """Stress: Recompressed versions of the same scene must maintain perceptual similarity <= 6."""
        session, farmer, farm, device = stress_db
        base_img = create_realistic_field_image(800, 600)
        orig_bytes = image_to_jpeg_bytes(base_img, quality=95)
        orig_sha = compute_sha256(orig_bytes)

        # Register original in database
        repo = DuplicateDetectionRepository(db=session)
        repo.register(
            sha256_hash=orig_sha,
            evidence_id="ev-orig-q95",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(orig_bytes),
            dhash=compute_dhash_64(orig_bytes),
        )

        # Create recompressed version
        recomp_bytes = image_to_jpeg_bytes(base_img, quality=quality)
        recomp_sha = compute_sha256(recomp_bytes)

        # If bytes are identical (e.g. q=95 re-save), it's exact duplicate
        res = DuplicateService.evaluate_duplicate(session, recomp_bytes)
        if recomp_sha == orig_sha:
            assert res.classification == DuplicateOutcome.EXACT_DUPLICATE.value
            assert res.hamming_distance == 0
        else:
            # Must be recognized as visual duplicate
            assert res.classification == DuplicateOutcome.POSSIBLE_VISUAL_DUPLICATE.value
            assert res.is_duplicate is True
            assert res.hamming_distance is not None
            assert res.hamming_distance <= 6
            assert res.matched_evidence_id == "ev-orig-q95"


class TestChallengerResizingStress:
    """Stress-tests geometric resizing (downscaling & upscaling: 0.25x, 0.5x, 0.75x, 1.5x, 2.0x)."""

    @pytest.mark.parametrize("scale", [0.25, 0.5, 0.75, 1.5, 2.0])
    def test_resizing_scale_factors(self, stress_db, scale):
        """Stress: Resized versions of the same scene must maintain perceptual similarity <= 6."""
        session, farmer, farm, device = stress_db
        base_img = create_realistic_field_image(800, 600)
        orig_bytes = image_to_jpeg_bytes(base_img, quality=95)

        repo = DuplicateDetectionRepository(db=session)
        repo.register(
            sha256_hash=compute_sha256(orig_bytes),
            evidence_id="ev-orig-scale",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(orig_bytes),
            dhash=compute_dhash_64(orig_bytes),
        )

        # Resize image
        new_w = int(800 * scale)
        new_h = int(600 * scale)
        resized_img = base_img.resize((new_w, new_h), Image.Resampling.BILINEAR)
        resized_bytes = image_to_jpeg_bytes(resized_img, quality=95)

        res = DuplicateService.evaluate_duplicate(session, resized_bytes)
        assert res.classification == DuplicateOutcome.POSSIBLE_VISUAL_DUPLICATE.value
        assert res.is_duplicate is True
        assert res.hamming_distance is not None
        assert res.hamming_distance <= 6
        assert res.matched_evidence_id == "ev-orig-scale"


class TestChallengerCroppingAndWatermarking:
    """Stress-tests slight cropping and watermarking."""

    def test_watermark_overlay_detection(self, stress_db):
        """Stress: Watermarked image (timestamp text, corner banner) remains POSSIBLE_VISUAL_DUPLICATE (dist <= 6)."""
        session, farmer, farm, device = stress_db
        base_img = create_realistic_field_image(800, 600)
        orig_bytes = image_to_jpeg_bytes(base_img, quality=95)

        repo = DuplicateDetectionRepository(db=session)
        repo.register(
            sha256_hash=compute_sha256(orig_bytes),
            evidence_id="ev-orig-wm",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(orig_bytes),
            dhash=compute_dhash_64(orig_bytes),
        )

        # Apply prominent watermark overlay
        wm_img = base_img.copy()
        draw = ImageDraw.Draw(wm_img)
        draw.rectangle([(20, 20), (220, 60)], fill=(255, 255, 255))
        draw.text((25, 25), "PRAMAN GPS: 19.6,78.5", fill=(0, 0, 0))
        wm_bytes = image_to_jpeg_bytes(wm_img, quality=95)

        res = DuplicateService.evaluate_duplicate(session, wm_bytes)
        assert res.classification == DuplicateOutcome.POSSIBLE_VISUAL_DUPLICATE.value
        assert res.is_duplicate is True
        assert res.hamming_distance is not None
        assert res.hamming_distance <= 6

    def test_minor_crop_detection(self, stress_db):
        """Stress: 1% to 2% boundary crop remains POSSIBLE_VISUAL_DUPLICATE (dist <= 6)."""
        session, farmer, farm, device = stress_db
        base_img = create_realistic_field_image(800, 600)
        orig_bytes = image_to_jpeg_bytes(base_img, quality=95)

        repo = DuplicateDetectionRepository(db=session)
        repo.register(
            sha256_hash=compute_sha256(orig_bytes),
            evidence_id="ev-orig-crop",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(orig_bytes),
            dhash=compute_dhash_64(orig_bytes),
        )

        # 1.5% crop
        crop_img = base_img.crop((12, 9, 788, 591))
        crop_bytes = image_to_jpeg_bytes(crop_img, quality=95)

        res = DuplicateService.evaluate_duplicate(session, crop_bytes)
        assert res.classification == DuplicateOutcome.POSSIBLE_VISUAL_DUPLICATE.value
        assert res.is_duplicate is True
        assert res.hamming_distance is not None
        assert res.hamming_distance <= 6

    def test_moderate_crop_yields_requires_review(self, stress_db):
        """Stress: 2.5% crop shifts distance into 7..10 range yielding DUPLICATE_REQUIRES_REVIEW."""
        session, farmer, farm, device = stress_db
        base_img = create_realistic_field_image(800, 600)
        orig_bytes = image_to_jpeg_bytes(base_img, quality=95)

        repo = DuplicateDetectionRepository(db=session)
        repo.register(
            sha256_hash=compute_sha256(orig_bytes),
            evidence_id="ev-orig-crop25",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(orig_bytes),
            dhash=compute_dhash_64(orig_bytes),
        )

        # 2.5% crop (20 px horizontal, 15 px vertical)
        crop25_img = base_img.crop((20, 15, 780, 585))
        crop25_bytes = image_to_jpeg_bytes(crop25_img, quality=95)

        res = DuplicateService.evaluate_duplicate(session, crop25_bytes)
        assert res.classification == DuplicateOutcome.DUPLICATE_REQUIRES_REVIEW.value
        assert res.is_duplicate is True
        assert res.hamming_distance is not None
        assert 7 <= res.hamming_distance <= 10

    def test_larger_crop_shifts_to_new_evidence(self, stress_db):
        """Stress: 5% or larger spatial crop shifts grid alignment such that dist > 10 (NEW_EVIDENCE)."""
        session, farmer, farm, device = stress_db
        base_img = create_realistic_field_image(800, 600)
        orig_bytes = image_to_jpeg_bytes(base_img, quality=95)

        repo = DuplicateDetectionRepository(db=session)
        repo.register(
            sha256_hash=compute_sha256(orig_bytes),
            evidence_id="ev-orig-crop5",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(orig_bytes),
            dhash=compute_dhash_64(orig_bytes),
        )

        # 5% crop (40 px horizontal, 30 px vertical)
        crop5_img = base_img.crop((40, 30, 760, 570))
        crop5_bytes = image_to_jpeg_bytes(crop5_img, quality=95)

        res = DuplicateService.evaluate_duplicate(session, crop5_bytes)
        assert res.classification == DuplicateOutcome.NEW_EVIDENCE.value
        assert res.is_duplicate is False
        assert res.hamming_distance is not None
        assert res.hamming_distance > 10


class TestChallengerNoiseDegradation:
    """Stress-tests additive noise (Gaussian & Salt-and-Pepper)."""

    def test_gaussian_noise_degradation(self, stress_db):
        """Stress: Gaussian noise on image sensor does not break duplicate detection."""
        session, farmer, farm, device = stress_db
        base_img = create_realistic_field_image(800, 600)
        orig_bytes = image_to_jpeg_bytes(base_img, quality=95)

        repo = DuplicateDetectionRepository(db=session)
        repo.register(
            sha256_hash=compute_sha256(orig_bytes),
            evidence_id="ev-orig-noise",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(orig_bytes),
            dhash=compute_dhash_64(orig_bytes),
        )

        # Add Gaussian noise
        arr = np.array(base_img).astype(np.float32)
        noise = np.random.normal(0, 15, arr.shape)
        noisy_arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        noisy_bytes = image_to_jpeg_bytes(Image.fromarray(noisy_arr), quality=95)

        res = DuplicateService.evaluate_duplicate(session, noisy_bytes)
        assert res.classification == DuplicateOutcome.POSSIBLE_VISUAL_DUPLICATE.value
        assert res.is_duplicate is True
        assert res.hamming_distance is not None
        assert res.hamming_distance <= 6

    def test_salt_and_pepper_noise(self, stress_db):
        """Stress: Sensor salt-and-pepper noise retains visual similarity."""
        session, farmer, farm, device = stress_db
        base_img = create_realistic_field_image(800, 600)
        orig_bytes = image_to_jpeg_bytes(base_img, quality=95)

        repo = DuplicateDetectionRepository(db=session)
        repo.register(
            sha256_hash=compute_sha256(orig_bytes),
            evidence_id="ev-orig-sp",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(orig_bytes),
            dhash=compute_dhash_64(orig_bytes),
        )

        arr = np.array(base_img).copy()
        # 1% salt and pepper
        mask_salt = np.random.random(arr.shape[:2]) < 0.01
        mask_pepper = np.random.random(arr.shape[:2]) < 0.01
        arr[mask_salt] = 255
        arr[mask_pepper] = 0
        sp_bytes = image_to_jpeg_bytes(Image.fromarray(arr), quality=95)

        res = DuplicateService.evaluate_duplicate(session, sp_bytes)
        assert res.classification == DuplicateOutcome.POSSIBLE_VISUAL_DUPLICATE.value
        assert res.is_duplicate is True
        assert res.hamming_distance is not None
        assert res.hamming_distance <= 6


class TestChallengerThresholdBoundaries:
    """Stress-tests the exact mathematical boundaries: dist in {0, 1, 6, 7, 10, 11, 64}."""

    @pytest.mark.parametrize(
        "target_dist, expected_classification, expected_is_dup",
        [
            (0, DuplicateOutcome.POSSIBLE_VISUAL_DUPLICATE.value, True),
            (1, DuplicateOutcome.POSSIBLE_VISUAL_DUPLICATE.value, True),
            (6, DuplicateOutcome.POSSIBLE_VISUAL_DUPLICATE.value, True),
            (7, DuplicateOutcome.DUPLICATE_REQUIRES_REVIEW.value, True),
            (10, DuplicateOutcome.DUPLICATE_REQUIRES_REVIEW.value, True),
            (11, DuplicateOutcome.NEW_EVIDENCE.value, False),
            (64, DuplicateOutcome.NEW_EVIDENCE.value, False),
        ],
    )
    def test_synthetic_exact_hamming_boundaries(
        self, stress_db, target_dist, expected_classification, expected_is_dup
    ):
        """Stress: Verifies exact classification transition at thresholds 0, 6, 7, 10, 11."""
        session, farmer, farm, device = stress_db

        # Base reference hash: all zeros
        base_hash_hex = "0000000000000000"

        # Construct target hash with exactly `target_dist` set bits
        if target_dist == 64:
            target_val = 0xFFFFFFFFFFFFFFFF
        else:
            target_val = (1 << target_dist) - 1
        target_hash_hex = f"{target_val:016x}"

        # Confirm bitwise Hamming distance
        assert hamming_distance_hex(base_hash_hex, target_hash_hex) == target_dist

        # Register reference evidence with base_hash_hex
        ref_ev = Evidence(
            id=f"ev-bound-ref-{target_dist}",
            farm_id=farm.id,
            device_id=device.id,
            sequence_number=100 + target_dist,
            lifecycle_stage="CROP_GROWTH",
            image_hash=f"refhash{target_dist:04d}" + "0" * 53,
            phash=base_hash_hex,
            dhash=base_hash_hex,
            canonical_envelope_json="{}",
            signature_b64="SIG",
            status="DURABLY_ACKED",
        )
        session.add(ref_ev)
        session.commit()

        # Build an image whose pHash/dHash will be tested against ref_ev
        # We test DuplicateDetectionRepository.check_perceptual directly
        repo = DuplicateDetectionRepository(db=session)
        res = repo.check_perceptual(target_hash_hex, threshold=10)

        assert res["classification"] == expected_classification
        assert res["is_duplicate"] == expected_is_dup
        if expected_is_dup:
            assert res["matched_evidence_id"] == ref_ev.id
            assert res["hamming_distance"] == target_dist


class TestChallengerCrossImageDiscrimination:
    """Stress-tests that different visual scenes are strictly classified as NEW_EVIDENCE."""

    def test_sharp_vs_underexposed_vs_overexposed_vs_geometric(self, stress_db):
        """Stress: Highly disparate scenes must never collide and must yield NEW_EVIDENCE."""
        session, farmer, farm, device = stress_db

        sharp_bytes, _ = SyntheticImageGenerator.create_sharp_crop_image(800, 600)
        dark_bytes, _ = SyntheticImageGenerator.create_underexposed_image(800, 600)
        bright_bytes, _ = SyntheticImageGenerator.create_overexposed_image(800, 600)

        # Geometric blue circle on red background
        geom_img = Image.new("RGB", (800, 600), color=(220, 20, 20))
        draw = ImageDraw.Draw(geom_img)
        draw.ellipse([(100, 100), (700, 500)], fill=(20, 20, 220))
        geom_bytes = image_to_jpeg_bytes(geom_img, quality=95)

        # Uniform random noise image
        noise_arr = np.random.randint(0, 256, (600, 800, 3), dtype=np.uint8)
        noise_bytes = image_to_jpeg_bytes(Image.fromarray(noise_arr), quality=95)

        images = [
            ("sharp", sharp_bytes),
            ("dark", dark_bytes),
            ("bright", bright_bytes),
            ("geometric", geom_bytes),
            ("random_noise", noise_bytes),
        ]

        # Register sharp image first
        repo = DuplicateDetectionRepository(db=session)
        repo.register(
            sha256_hash=compute_sha256(sharp_bytes),
            evidence_id="ev-sharp-baseline",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(sharp_bytes),
            dhash=compute_dhash_64(sharp_bytes),
        )

        # Evaluate the other 4 distinct images against sharp
        for name, img_b in images[1:]:
            res = DuplicateService.evaluate_duplicate(session, img_b)
            assert res.classification == DuplicateOutcome.NEW_EVIDENCE.value, f"Failed on {name}"
            assert res.is_duplicate is False, f"Failed on {name}"
            assert res.matched_evidence_id is None
            if res.hamming_distance is not None:
                assert res.hamming_distance > 10, f"Distance {res.hamming_distance} too small for {name}"


class TestChallengerMultiCandidateIndexing:
    """Stress-tests matching accuracy when the database contains numerous candidates."""

    def test_closest_candidate_selected_from_population(self, stress_db):
        """Stress: When multiple candidates exist in DB, system selects the closest candidate."""
        session, farmer, farm, device = stress_db
        repo = DuplicateDetectionRepository(db=session)

        # Populate DB with 10 diverse candidates
        for i in range(10):
            # Hex values spaced out
            val = (0x1111111111111111 * (i + 1)) & 0xFFFFFFFFFFFFFFFF
            h_hex = f"{val:016x}"
            ev = Evidence(
                id=f"ev-pop-{i}",
                farm_id=farm.id,
                device_id=device.id,
                sequence_number=200 + i,
                lifecycle_stage="CROP_GROWTH",
                image_hash=f"pophash{i:04d}" + "f" * 53,
                phash=h_hex,
                dhash=h_hex,
                canonical_envelope_json="{}",
                signature_b64="SIG",
                status="DURABLY_ACKED",
            )
            session.add(ev)
        session.commit()

        # Query candidate very close to ev-pop-3 (differing by only 2 bits)
        target_val = (0x1111111111111111 * 4) ^ 0x0000000000000003
        target_hex = f"{target_val:016x}"
        res = repo.check_perceptual(target_hex, threshold=10)

        assert res["is_duplicate"] is True
        assert res["matched_evidence_id"] == "ev-pop-3"
        assert res["hamming_distance"] == 2
        assert res["classification"] == DuplicateOutcome.POSSIBLE_VISUAL_DUPLICATE.value


class TestChallengerEdgeCasesAndRobustness:
    """Stress-tests non-image data, extreme dimensions, and self-exclusion."""

    def test_non_image_payload_handling(self, stress_db):
        """Stress: Corrupted or non-image bytes should not throw unhandled exceptions."""
        session, farmer, farm, device = stress_db
        raw_non_image = b"CORRUPTED_BINARY_HEADER_\x00\xff\xee\xdd_NOT_AN_IMAGE"

        # Verify safe hashing functions
        assert safe_compute_phash_64(raw_non_image) is None
        assert safe_compute_dhash_64(raw_non_image) is None
        all_h = safe_compute_all_hashes(raw_non_image)
        assert all_h["sha256"] == compute_sha256(raw_non_image)
        assert all_h["phash"] is None
        assert all_h["dhash"] is None

        # Direct evaluation -> NEW_EVIDENCE
        res = DuplicateService.evaluate_duplicate(session, raw_non_image)
        assert res.classification == DuplicateOutcome.NEW_EVIDENCE.value
        assert res.is_duplicate is False

    @pytest.mark.parametrize("dims", [(1, 1), (8, 8), (1000, 2), (2, 1000)])
    def test_extreme_dimension_images(self, stress_db, dims):
        """Stress: Extremely small or high aspect ratio images handle gracefully."""
        session, farmer, farm, device = stress_db
        w, h = dims
        raw_bytes, sha = SyntheticImageGenerator.create_extreme_dimension_image(w, h, format="PNG")

        phash = safe_compute_phash_64(raw_bytes)
        dhash = safe_compute_dhash_64(raw_bytes)
        assert phash is not None
        assert dhash is not None
        assert len(phash) == 16
        assert len(dhash) == 16

        res = DuplicateService.evaluate_duplicate(session, raw_bytes)
        assert res.classification == DuplicateOutcome.NEW_EVIDENCE.value

    def test_exclude_evidence_id_parameter(self, stress_db):
        """Stress: exclude_evidence_id prevents false self-match when re-evaluating evidence."""
        session, farmer, farm, device = stress_db
        base_img = create_realistic_field_image(400, 300)
        img_bytes = image_to_jpeg_bytes(base_img, quality=95)
        sha = compute_sha256(img_bytes)

        repo = DuplicateDetectionRepository(db=session)
        ev = repo.register(
            sha256_hash=sha,
            evidence_id="ev-self-test",
            farmer_id=farmer.id,
            farm_id=farm.id,
            phash=compute_phash_64(img_bytes),
            dhash=compute_dhash_64(img_bytes),
        )

        # Without exclusion: matches itself as EXACT_DUPLICATE
        res_no_ex = DuplicateService.evaluate_duplicate(session, img_bytes)
        assert res_no_ex.is_duplicate is True
        assert res_no_ex.matched_evidence_id == "ev-self-test"

        # With exclusion: skips itself, returns NEW_EVIDENCE
        res_ex = DuplicateService.evaluate_duplicate(session, img_bytes, exclude_evidence_id="ev-self-test")
        assert res_ex.is_duplicate is False
        assert res_ex.classification == DuplicateOutcome.NEW_EVIDENCE.value


class TestChallengerCrossFarmerPrivacyAndAPI:
    """Stress-tests API serialization and multi-tenant privacy boundaries."""

    def test_receipt_sanitization_removes_tenant_identifiers(self):
        """Stress: DuplicateCheckResult.to_sanitized_receipt_dict() MUST strip all tenant identifiers."""
        result = DuplicateCheckResult(
            classification="POSSIBLE_VISUAL_DUPLICATE",
            is_duplicate=True,
            matched_evidence_id="secret-evidence-xyz",
            matched_farmer_id="secret-farmer-abc",
            matched_farm_id="secret-farm-123",
            hamming_distance=4,
            sha256="abc" * 21 + "a",
            phash="1234567890abcdef",
            dhash="fedcba0987654321",
        )
        receipt_dict = result.to_sanitized_receipt_dict()

        # Assert no sensitive matched IDs exist in receipt dictionary
        assert "matched_evidence_id" not in receipt_dict
        assert "matched_farmer_id" not in receipt_dict
        assert "matched_farm_id" not in receipt_dict
        assert "secret-evidence-xyz" not in json.dumps(receipt_dict)
        assert "secret-farmer-abc" not in json.dumps(receipt_dict)
        assert "secret-farm-123" not in json.dumps(receipt_dict)

        # Verify allowed public receipt fields
        assert receipt_dict["classification"] == "POSSIBLE_VISUAL_DUPLICATE"
        assert receipt_dict["is_duplicate"] is True
        assert receipt_dict["duplicate_type"] == "POSSIBLE_VISUAL_DUPLICATE"
        assert receipt_dict["hamming_distance"] == 4

    def test_cross_farmer_replay_via_api_receipt_privacy(self, api_test_env):
        """Stress: E2E API ingestion by Farmer B of Farmer A's image strictly redacts Farmer A's info."""
        client, SessionMaker = api_test_env

        farmer_a = register_farmer_device_farm(client, "Victim Farmer", phone="+919810000001")
        farmer_b = register_farmer_device_farm(client, "Attacker Farmer", phone="+919820000002")

        base_img = create_realistic_field_image(800, 600)
        img_bytes = image_to_jpeg_bytes(base_img, quality=95)

        # Farmer A submits evidence
        data_a, files_a, _ = build_signed_submission(farmer_a, seq=1, image_bytes=img_bytes)
        ra = client.post("/api/v1/evidence/ingest", data=data_a, files=files_a)
        assert ra.status_code == 201
        ev_a_id = ra.json()["evidence_id"]

        # Farmer B submits exact same image
        data_b, files_b, _ = build_signed_submission(farmer_b, seq=1, image_bytes=img_bytes)
        rb = client.post("/api/v1/evidence/ingest", data=data_b, files=files_b)
        assert rb.status_code == 201
        receipt_b = rb.json()

        assert receipt_b["classification"] == "EXACT_DUPLICATE"
        assert receipt_b["is_duplicate"] is True

        # Ensure receipt_b does not contain any reference to Farmer A
        receipt_b_str = json.dumps(receipt_b)
        assert ev_a_id not in receipt_b_str
        assert farmer_a["farmer_id"] not in receipt_b_str
        assert farmer_a["farm_id"] not in receipt_b_str
        assert farmer_a["device_id"] not in receipt_b_str
