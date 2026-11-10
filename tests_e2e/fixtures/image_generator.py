"""Synthetic image generator for PRAMAN E2E testing.
Generates genuine JPEG and PNG images in-memory to test:
- Laplacian blur detection
- Under-exposure and over-exposure detection
- Image resolution and aspect ratio validation
- EXIF metadata consistency
- Exact SHA-256 duplicate detection
- Perceptual & difference hashing (pHash, dHash)
"""

import io
import hashlib
from typing import Tuple, Dict, Any, Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import cv2

# Import genuine computer vision and hashing algorithms from ai_engine
from ai_engine.quality import (
    compute_laplacian_variance,
    compute_luminance_clipping,
    validate_image_dimensions,
    inspect_exif,
)
from ai_engine.hashing import (
    compute_sha256,
    compute_phash_64,
    compute_dhash_64,
    hamming_distance_hex,
)


class SyntheticImageGenerator:
    """In-memory generator of synthetic image fixtures with deterministic visual properties."""

    @staticmethod
    def create_sharp_crop_image(
        width: int = 1920,
        height: int = 1080,
        format: str = "JPEG",
    ) -> Tuple[bytes, str]:
        """Creates a high-contrast, sharp synthetic crop field image.
        
        Laplacian variance is typically > 200.
        Returns: (image_bytes, sha256_hex)
        """
        img = Image.new("RGB", (width, height), color=(34, 139, 34))  # Forest green
        draw = ImageDraw.Draw(img)
        
        # Draw high-frequency textured patterns: rows, stalks, leaves, high contrast grids
        step_x = max(10, width // 40)
        step_y = max(10, height // 30)
        
        for x in range(0, width, step_x):
            # Alternating stalks and soil
            draw.line([(x, 0), (x, height)], fill=(139, 69, 19), width=3)
            for y in range(0, height, step_y):
                draw.polygon(
                    [(x, y), (x + step_x // 2, y + step_y // 2), (x, y + step_y)],
                    fill=(50, 205, 50),
                )
                draw.rectangle(
                    [x + 2, y + 2, x + 6, y + 6],
                    fill=(255, 255, 0),
                )

        buffer = io.BytesIO()
        img.save(buffer, format=format, quality=95)
        raw_bytes = buffer.getvalue()
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        return raw_bytes, sha256

    @staticmethod
    def create_blurry_image(
        width: int = 1920,
        height: int = 1080,
        blur_radius: int = 25,
        format: str = "JPEG",
    ) -> Tuple[bytes, str]:
        """Creates an intentionally blurred image with low Laplacian variance (< 50)."""
        raw_sharp, _ = SyntheticImageGenerator.create_sharp_crop_image(width, height, format="PNG")
        sharp_img = Image.open(io.BytesIO(raw_sharp))
        blurred = sharp_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        buf = io.BytesIO()
        blurred.save(buf, format=format, quality=90)
        raw = buf.getvalue()
        return raw, hashlib.sha256(raw).hexdigest()

    @staticmethod
    def create_underexposed_image(
        width: int = 1920,
        height: int = 1080,
        format: str = "JPEG",
    ) -> Tuple[bytes, str]:
        """Creates an underexposed dark image (mean luminance < 20)."""
        img = Image.new("RGB", (width, height), color=(8, 12, 8))
        draw = ImageDraw.Draw(img)
        draw.line([(0, 0), (width, height)], fill=(20, 25, 20), width=2)
        buf = io.BytesIO()
        img.save(buf, format=format, quality=90)
        raw = buf.getvalue()
        return raw, hashlib.sha256(raw).hexdigest()

    @staticmethod
    def create_overexposed_image(
        width: int = 1920,
        height: int = 1080,
        format: str = "JPEG",
    ) -> Tuple[bytes, str]:
        """Creates an overexposed washed out image (mean luminance > 240)."""
        img = Image.new("RGB", (width, height), color=(250, 252, 250))
        draw = ImageDraw.Draw(img)
        draw.line([(0, 0), (width, height)], fill=(240, 245, 240), width=2)
        buf = io.BytesIO()
        img.save(buf, format=format, quality=90)
        raw = buf.getvalue()
        return raw, hashlib.sha256(raw).hexdigest()

    @staticmethod
    def create_phash_near_duplicate_pair() -> Tuple[Tuple[bytes, str], Tuple[bytes, str]]:
        """Creates two visually similar images with different SHA-256 but Hamming distance <= 10."""
        base_raw, _ = SyntheticImageGenerator.create_sharp_crop_image(800, 600, format="PNG")
        img1 = Image.open(io.BytesIO(base_raw))
        
        # Save same visual scene under two different JPEG compression quality levels
        buf1 = io.BytesIO()
        img1.save(buf1, format="JPEG", quality=95)
        raw1 = buf1.getvalue()
        hash1 = hashlib.sha256(raw1).hexdigest()

        buf2 = io.BytesIO()
        img1.save(buf2, format="JPEG", quality=85)
        raw2 = buf2.getvalue()
        hash2 = hashlib.sha256(raw2).hexdigest()

        return (raw1, hash1), (raw2, hash2)

    create_phash_pair = create_phash_near_duplicate_pair

    @staticmethod
    def create_extreme_dimension_image(
        width: int,
        height: int,
        format: str = "PNG",
    ) -> Tuple[bytes, str]:
        """Creates an image with specific dimensions (e.g. 1x1, 100:1 aspect ratio)."""
        img = Image.new("RGB", (width, height), color=(128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format=format)
        raw = buf.getvalue()
        return raw, hashlib.sha256(raw).hexdigest()
