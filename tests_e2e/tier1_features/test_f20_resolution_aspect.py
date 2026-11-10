"""F-20: Image Resolution & Aspect Ratio Validator Tests.
Validates minimum resolution bounds (e.g. 800x600) and aspect ratio checks
to prevent unusable or degenerate evidence submissions.
"""

import io
from PIL import Image
import pytest
from tests_e2e.fixtures.image_generator import SyntheticImageGenerator


def validate_image_dimensions(
    image_bytes: bytes,
    min_width: int = 800,
    min_height: int = 600,
    max_aspect_ratio: float = 3.0,
    min_aspect_ratio: float = 0.33,
) -> dict:
    """Extracts dimensions and validates resolution and aspect ratio constraints."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        w, h = img.size
        aspect = w / h
        is_res_valid = w >= min_width and h >= min_height
        is_aspect_valid = min_aspect_ratio <= aspect <= max_aspect_ratio
        return {
            "width": w,
            "height": h,
            "aspect_ratio": round(aspect, 3),
            "is_resolution_valid": is_res_valid,
            "is_aspect_ratio_valid": is_aspect_valid,
            "is_valid": is_res_valid and is_aspect_valid,
        }


class TestF20ResolutionAspectValidator:
    """Verifies image resolution and aspect ratio validation."""

    def test_standard_high_res_image_valid(self, sharp_image_fixture):
        """Test 1: Verifies 1920x1080 (16:9) image passes resolution and aspect ratio checks."""
        res = validate_image_dimensions(sharp_image_fixture[0])
        assert res["width"] == 1920
        assert res["height"] == 1080
        assert res["is_resolution_valid"] is True
        assert res["is_aspect_ratio_valid"] is True
        assert res["is_valid"] is True

    def test_sub_resolution_thumbnail_rejected(self):
        """Test 2: Verifies low resolution image (e.g. 320x240) fails minimum resolution check."""
        raw, _ = SyntheticImageGenerator.create_extreme_dimension_image(320, 240)
        res = validate_image_dimensions(raw)
        assert res["is_resolution_valid"] is False
        assert res["is_valid"] is False

    def test_extreme_horizontal_aspect_ratio_rejected(self):
        """Test 3: Verifies extreme aspect ratio (e.g. 2000x200, 10:1 ratio) fails aspect check."""
        raw, _ = SyntheticImageGenerator.create_extreme_dimension_image(2000, 200)
        res = validate_image_dimensions(raw)
        assert res["aspect_ratio"] == 10.0
        assert res["is_aspect_ratio_valid"] is False
        assert res["is_valid"] is False

    def test_extreme_vertical_aspect_ratio_rejected(self):
        """Test 4: Verifies extreme vertical aspect ratio (e.g. 200x2000, 0.1 ratio) fails aspect check."""
        raw, _ = SyntheticImageGenerator.create_extreme_dimension_image(200, 2000)
        res = validate_image_dimensions(raw)
        assert res["aspect_ratio"] == 0.1
        assert res["is_aspect_ratio_valid"] is False
        assert res["is_valid"] is False

    def test_single_pixel_degenerate_image_rejected(self):
        """Test 5: Verifies 1x1 single pixel image is completely rejected."""
        raw, _ = SyntheticImageGenerator.create_extreme_dimension_image(1, 1)
        res = validate_image_dimensions(raw)
        assert res["width"] == 1
        assert res["height"] == 1
        assert res["is_valid"] is False
