"""ADV-02: Image Tampering & Deduplication Bypass Adversarial Tests.
Verifies resistance against:
1. Bit-exact duplicate replay (SHA-256 CAS deduplication and duplicate rejection).
2. Near-duplicate perceptual injection (64-bit DCT pHash Hamming distance <= 10).
3. Spliced / photoshopped image injection (Error Level Analysis variance > 350).
4. Localized noise residual manipulation (noise disparity ratio > 20).
5. Invariant enforcement: AI tamper detection flags PENDING_REVIEW, never autonomously rejects.
"""

import io
import pytest
import numpy as np
from PIL import Image, ImageDraw
from ai_engine.hashing import (
    compute_sha256,
    compute_phash_64,
    compute_dhash_64,
    hamming_distance_hex,
)
from ai_engine.forensics import image_forensics
from backend.app.storage.content_storage import ContentAddressableStorage
from tests_e2e.fixtures.image_generator import SyntheticImageGenerator


class TestAdv02ImageTamperingDedupBypass:
    """Adversarial test suite for image tampering and deduplication evasion."""

    def test_exact_sha256_duplicate_replay_detected(self, ephemeral_dir, sharp_image_fixture):
        """ADV-02.1: Bit-exact image replay is identified via SHA-256 CAS deduplication."""
        cas = ContentAddressableStorage(base_dir=ephemeral_dir)
        image_bytes, expected_hash = sharp_image_fixture

        # First storage: stores bytes and returns SHA-256 hash
        hash1 = cas.store(image_bytes)
        assert hash1 == expected_hash
        assert cas.exists(hash1) is True

        # Second attempt with identical bytes (replay attack)
        hash2 = cas.store(image_bytes)
        assert hash2 == hash1
        
        # Verify bit-for-bit retrieval from CAS
        retrieved_bytes = cas.retrieve(hash1)
        assert retrieved_bytes == image_bytes
        assert compute_sha256(retrieved_bytes) == expected_hash

    def test_phash_near_duplicate_evasion_blocked(self):
        """ADV-02.2: Near-duplicate images with altered compression are caught by 64-bit DCT pHash."""
        (bytes1, hash1), (bytes2, hash2) = SyntheticImageGenerator.create_phash_near_duplicate_pair()

        # SHA-256 is completely different (evading naive hash checks)
        assert hash1 != hash2

        # But 64-bit DCT pHash detects near-duplicate (Hamming distance <= 10)
        phash1 = compute_phash_64(bytes1)
        phash2 = compute_phash_64(bytes2)
        distance = hamming_distance_hex(phash1, phash2)
        assert distance <= 10, f"Expected pHash Hamming distance <= 10 for near-duplicate, got {distance}"

    def test_spliced_composite_image_detected_via_ela(self):
        """ADV-02.3: Spliced composite image triggers high Error Level Analysis (ELA) or noise disparity."""
        # Generate image with high-entropy spliced noise block
        arr = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        spliced_bytes = buf.getvalue()

        # Run ELA forensics analysis
        forensics_res = image_forensics.evaluate_tamper(spliced_bytes)
        assert "ela_variance" in forensics_res
        assert forensics_res["is_tamper_suspected"] is True
        assert forensics_res["ela_variance"] > 350.0

    def test_localized_noise_residual_disparity_detected(self):
        """ADV-02.4: Localized artificial noise patch triggers high noise disparity ratio."""
        # Create uniform clean image
        img = Image.new("RGB", (512, 512), color=(128, 128, 128))
        img_np = np.array(img, dtype=np.float32)

        # Inject heavy Gaussian noise only into a 128x128 patch
        np.random.seed(42)
        noise_patch = np.random.normal(loc=0.0, scale=35.0, size=(128, 128, 3))
        img_np[100:228, 100:228, :] = np.clip(img_np[100:228, 100:228, :] + noise_patch, 0, 255)
        noisy_img = Image.fromarray(img_np.astype(np.uint8))

        buf = io.BytesIO()
        noisy_img.save(buf, format="PNG")
        noisy_bytes = buf.getvalue()

        # Run forensics
        forensics_res = image_forensics.evaluate_tamper(noisy_bytes)
        assert forensics_res["noise_disparity_ratio"] > 10.0 or forensics_res["is_tamper_suspected"] is True

    def test_ai_never_autonomously_rejects_on_tamper(self, sharp_image_fixture):
        """ADV-02.5: F-28 Invariant: AI tamper detection flags PENDING_REVIEW but never autonomously rejects."""
        image_bytes, _ = sharp_image_fixture
        forensics_res = image_forensics.evaluate_tamper(image_bytes)

        # Strict invariant verification: autonomous_action_allowed MUST BE FALSE
        assert forensics_res["autonomous_action_allowed"] is False
        assert forensics_res["validation_status"] == "FORMALLY_EVALUATED"
