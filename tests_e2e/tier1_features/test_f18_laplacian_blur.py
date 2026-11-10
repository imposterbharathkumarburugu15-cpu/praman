"""F-18: Laplacian Blur Quality Detector Tests.
Validates OpenCV Laplacian variance computation, sharpness thresholds,
and detection of blurred agricultural images.
"""

import pytest
from tests_e2e.fixtures.image_generator import (
    SyntheticImageGenerator,
    compute_laplacian_variance,
)


class TestF18LaplacianBlurDetector:
    """Verifies image blur detection using Laplacian variance."""

    def test_sharp_image_high_variance(self, sharp_image_fixture):
        """Test 1: Verifies sharp image yields Laplacian variance above the blur threshold (score > 100)."""
        raw_bytes, _ = sharp_image_fixture
        score = compute_laplacian_variance(raw_bytes)
        assert score > 100.0, f"Expected sharp image variance > 100, got {score}"

    def test_blurry_image_low_variance(self, blurry_image_fixture):
        """Test 2: Verifies blurred image yields Laplacian variance below threshold (score < 50)."""
        raw_bytes, _ = blurry_image_fixture
        score = compute_laplacian_variance(raw_bytes)
        assert score < 50.0, f"Expected blurry image variance < 50, got {score}"

    def test_configurable_threshold_decision(self, sharp_image_fixture, blurry_image_fixture):
        """Test 3: Verifies classification respects configurable threshold parameter."""
        threshold = 80.0
        sharp_bytes, _ = sharp_image_fixture
        blurry_bytes, _ = blurry_image_fixture

        def is_blurry(img_bytes, thresh=80.0):
            return compute_laplacian_variance(img_bytes) < thresh

        assert is_blurry(sharp_bytes, threshold) is False
        assert is_blurry(blurry_bytes, threshold) is True

    def test_graded_blur_monotonicity(self):
        """Test 4: Verifies Laplacian variance decreases monotonically as Gaussian blur radius increases."""
        radii = [0, 5, 25]
        scores = []
        base_raw, _ = SyntheticImageGenerator.create_sharp_crop_image(800, 600, format="PNG")
        scores.append(compute_laplacian_variance(base_raw))

        for r in [5, 25]:
            img_bytes, _ = SyntheticImageGenerator.create_blurry_image(800, 600, blur_radius=r, format="PNG")
            scores.append(compute_laplacian_variance(img_bytes))

        # Check strictly descending: sharp (radius 0) > light blur (radius 5) > heavy blur (radius 25)
        assert scores[0] > scores[1] > scores[2]

    def test_empty_or_corrupt_image_bytes_raises(self):
        """Test 5: Verifies unreadable or truncated byte buffer raises ValueError."""
        with pytest.raises(ValueError, match="Could not decode"):
            compute_laplacian_variance(b"TRUNCATED_NOT_AN_IMAGE")
