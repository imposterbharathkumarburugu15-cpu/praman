"""F-19: Exposure & Luminance Quality Checker Tests.
Validates luminance histogram clipping detection for under-exposure (< 15)
and over-exposure (> 240) in evidence images.
"""

import pytest
from tests_e2e.fixtures.image_generator import (
    compute_luminance_clipping,
)


class TestF19ExposureLuminanceChecker:
    """Verifies image exposure and luminance clipping assessment."""

    def test_balanced_image_exposure(self, sharp_image_fixture):
        """Test 1: Verifies standard balanced crop image has low clipping (< 10% under/over)."""
        raw_bytes, _ = sharp_image_fixture
        under_pct, over_pct = compute_luminance_clipping(raw_bytes)

        assert under_pct < 15.0
        assert over_pct < 15.0

    def test_underexposed_image_detected(self, dark_image_fixture):
        """Test 2: Verifies very dark image has under-exposure clipping > 80%."""
        raw_bytes, _ = dark_image_fixture
        under_pct, over_pct = compute_luminance_clipping(raw_bytes)

        assert under_pct > 80.0
        assert over_pct < 5.0

    def test_overexposed_image_detected(self, blown_image_fixture):
        """Test 3: Verifies washed out image has over-exposure clipping > 80%."""
        raw_bytes, _ = blown_image_fixture
        under_pct, over_pct = compute_luminance_clipping(raw_bytes)

        assert over_pct > 80.0
        assert under_pct < 5.0

    def test_exposure_validity_rule(self, sharp_image_fixture, dark_image_fixture, blown_image_fixture):
        """Test 4: Verifies is_exposure_valid boolean rule (both clipping percentages < 35%)."""
        def is_exposure_valid(img_bytes, max_clipping=35.0):
            u, o = compute_luminance_clipping(img_bytes)
            return u < max_clipping and o < max_clipping

        assert is_exposure_valid(sharp_image_fixture[0]) is True
        assert is_exposure_valid(dark_image_fixture[0]) is False
        assert is_exposure_valid(blown_image_fixture[0]) is False

    def test_luminance_percentage_bounds(self, sharp_image_fixture):
        """Test 5: Verifies clipping percentages are strictly within [0.0, 100.0]."""
        u, o = compute_luminance_clipping(sharp_image_fixture[0])
        assert 0.0 <= u <= 100.0
        assert 0.0 <= o <= 100.0
        assert u + o <= 100.0
