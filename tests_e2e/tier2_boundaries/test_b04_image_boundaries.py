"""Tier 2: Image Quality & Dimension Boundary Tests.
Tests 1x1 pixel images, 100% pure black (0 luminance), 100% pure white (255 luminance),
exact 800x600 resolution boundaries, and square (1:1) aspect ratios.
"""

import numpy as np
from PIL import Image
import io
import pytest
from tests_e2e.fixtures.image_generator import (
    compute_laplacian_variance,
    compute_luminance_clipping,
    SyntheticImageGenerator,
)
from tests_e2e.tier1_features.test_f20_resolution_aspect import validate_image_dimensions


class TestB04ImageBoundaries:
    """Verifies image quality and dimension boundary limits."""

    def test_pure_pitch_black_image_clipping(self):
        """Boundary 1: Verifies completely black image (all pixels = 0) has 100% under-exposure and 0 variance."""
        arr = np.zeros((600, 800, 3), dtype=np.uint8)
        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()

        under, over = compute_luminance_clipping(raw)
        assert under == 100.0
        assert over == 0.0
        assert compute_laplacian_variance(raw) == 0.0

    def test_pure_white_blown_image_clipping(self):
        """Boundary 2: Verifies completely white image (all pixels = 255) has 100% over-exposure."""
        arr = np.full((600, 800, 3), 255, dtype=np.uint8)
        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()

        under, over = compute_luminance_clipping(raw)
        assert under == 0.0
        assert over == 100.0
        assert compute_laplacian_variance(raw) == 0.0

    def test_exact_resolution_threshold_boundary(self):
        """Boundary 3: Verifies exact boundary values (800x600 passes, 799x600 fails, 800x599 fails)."""
        raw_exact, _ = SyntheticImageGenerator.create_extreme_dimension_image(800, 600)
        assert validate_image_dimensions(raw_exact)["is_resolution_valid"] is True

        raw_sub_w, _ = SyntheticImageGenerator.create_extreme_dimension_image(799, 600)
        assert validate_image_dimensions(raw_sub_w)["is_resolution_valid"] is False

        raw_sub_h, _ = SyntheticImageGenerator.create_extreme_dimension_image(800, 599)
        assert validate_image_dimensions(raw_sub_h)["is_resolution_valid"] is False

    def test_square_one_to_one_aspect_ratio(self):
        """Boundary 4: Verifies square aspect ratio (1:1, e.g. 1024x1024) is valid."""
        raw_square, _ = SyntheticImageGenerator.create_extreme_dimension_image(1024, 1024)
        res = validate_image_dimensions(raw_square)
        assert res["aspect_ratio"] == 1.0
        assert res["is_aspect_ratio_valid"] is True
        assert res["is_valid"] is True

    def test_one_by_one_pixel_fails_resolution(self):
        """Boundary 5: Verifies minimal 1x1 image fails resolution check."""
        raw_1x1, _ = SyntheticImageGenerator.create_extreme_dimension_image(1, 1)
        res = validate_image_dimensions(raw_1x1)
        assert res["is_resolution_valid"] is False
        assert res["is_valid"] is False
