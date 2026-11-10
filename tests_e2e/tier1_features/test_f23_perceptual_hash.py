"""F-23: Perceptual & Difference Hashing (pHash/dHash) Tests.
Validates zero-dependency 64-bit DCT perceptual hashing and gradient dHash,
Hamming distance matching, and near-duplicate detection under resize/compression.
"""

import pytest
from tests_e2e.fixtures.image_generator import (
    SyntheticImageGenerator,
    compute_phash_64,
    compute_dhash_64,
    hamming_distance_hex,
)


class TestF23PerceptualHash:
    """Verifies perceptual and difference hashing mechanics."""

    def test_phash_format_and_length(self, sharp_image_fixture):
        """Test 1: Verifies pHash produces a 64-bit value represented as 16 hexadecimal characters."""
        raw_bytes, _ = sharp_image_fixture
        phash = compute_phash_64(raw_bytes)
        assert len(phash) == 16
        # Verify valid hex
        int(phash, 16)

    def test_dhash_format_and_length(self, sharp_image_fixture):
        """Test 2: Verifies dHash produces a 64-bit value represented as 16 hexadecimal characters."""
        raw_bytes, _ = sharp_image_fixture
        dhash = compute_dhash_64(raw_bytes)
        assert len(dhash) == 16
        int(dhash, 16)

    def test_near_duplicate_low_hamming_distance(self):
        """Test 3: Verifies visually identical images under slight resize/compression have Hamming distance <= 10."""
        (img1_bytes, _), (img2_bytes, _) = SyntheticImageGenerator.create_phash_pair()

        p1 = compute_phash_64(img1_bytes)
        p2 = compute_phash_64(img2_bytes)
        dist = hamming_distance_hex(p1, p2)

        assert dist <= 10, f"Expected near-duplicate Hamming distance <= 10, got {dist}"

    def test_distinct_images_high_hamming_distance(self, sharp_image_fixture, dark_image_fixture):
        """Test 4: Verifies completely different images have high Hamming distance (> 15)."""
        p1 = compute_phash_64(sharp_image_fixture[0])
        p2 = compute_phash_64(dark_image_fixture[0])
        dist = hamming_distance_hex(p1, p2)

        assert dist > 15, f"Expected distinct images Hamming distance > 15, got {dist}"

    def test_identical_image_zero_hamming_distance(self, sharp_image_fixture):
        """Test 5: Verifies identical image bytes yield Hamming distance of exactly 0."""
        raw = sharp_image_fixture[0]
        p1 = compute_phash_64(raw)
        p2 = compute_phash_64(raw)
        assert hamming_distance_hex(p1, p2) == 0
