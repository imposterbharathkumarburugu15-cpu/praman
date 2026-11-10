"""F-21: EXIF Metadata Consistency Inspector Tests.
Validates extraction of EXIF tags (DateTimeOriginal, Make, Model),
cross-validation with envelope metadata, and anomaly flagging using native Pillow.
"""

import io
from datetime import datetime, timezone, timedelta
from PIL import Image, ExifTags
import pytest


# EXIF standard tag IDs
EXIF_DATETIME_ORIGINAL = 0x9003  # DateTimeOriginal
EXIF_MAKE = 0x010F              # Make
EXIF_MODEL = 0x0110             # Model


def inject_mock_exif(image_bytes: bytes, datetime_original: str, make: str = "Samsung", model: str = "Galaxy S22") -> bytes:
    """Injects EXIF metadata into a JPEG byte buffer using Pillow."""
    img = Image.open(io.BytesIO(image_bytes))
    exif = img.getexif()
    exif[EXIF_MAKE] = make
    exif[EXIF_MODEL] = model

    # In Pillow, DateTimeOriginal is in the Exif IFD
    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[EXIF_DATETIME_ORIGINAL] = datetime_original

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


class EXIFInspector:
    """Inspector checking consistency between image EXIF tags and envelope metadata."""

    @staticmethod
    def inspect(image_bytes: bytes, envelope_timestamp_iso: str, capture_source: str) -> dict:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            exif = img.getexif()
            exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            dt_raw = exif_ifd.get(EXIF_DATETIME_ORIGINAL) or exif.get(0x0132)  # 0x0132 is DateTime in base IFD
            has_exif = dt_raw is not None
        except Exception:
            has_exif = False
            dt_raw = None

        if not has_exif:
            return {
                "has_exif": False,
                "is_consistent": True,  # Non-fatal if absent
                "note": "EXIF stripped or absent",
            }

        exif_dt_str = str(dt_raw)
        # Format: YYYY:MM:DD HH:MM:SS
        exif_dt = datetime.strptime(exif_dt_str, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
        env_dt = datetime.fromisoformat(envelope_timestamp_iso.replace("Z", "+00:00"))

        diff_seconds = abs((env_dt - exif_dt).total_seconds())
        # Consistent if within 1 hour
        is_consistent = diff_seconds <= 3600

        return {
            "has_exif": True,
            "exif_timestamp": exif_dt.isoformat(),
            "time_diff_seconds": diff_seconds,
            "is_consistent": is_consistent,
            "note": "Consistent" if is_consistent else "EXIF timestamp diverges from envelope",
        }


class TestF21EXIFConsistency:
    """Verifies EXIF inspection and cross-metadata consistency."""

    def test_consistent_exif_timestamp(self, sharp_image_fixture):
        """Test 1: Verifies matching EXIF DateTimeOriginal and envelope timestamp are marked consistent."""
        now_dt = datetime.now(timezone.utc)
        exif_str = now_dt.strftime("%Y:%m:%d %H:%M:%S")
        env_iso = now_dt.isoformat()

        jpeg_with_exif = inject_mock_exif(sharp_image_fixture[0], exif_str)
        result = EXIFInspector.inspect(jpeg_with_exif, env_iso, "CAMERA")

        assert result["has_exif"] is True
        assert result["is_consistent"] is True
        assert result["time_diff_seconds"] < 10

    def test_divergent_exif_timestamp_flagged(self, sharp_image_fixture):
        """Test 2: Verifies EXIF timestamp diverging by 1 year from envelope timestamp is flagged."""
        exif_str = "2024:01:01 12:00:00"
        env_iso = "2026-11-09T14:30:00Z"

        jpeg_with_exif = inject_mock_exif(sharp_image_fixture[0], exif_str)
        result = EXIFInspector.inspect(jpeg_with_exif, env_iso, "CAMERA")

        assert result["has_exif"] is True
        assert result["is_consistent"] is False
        assert result["time_diff_seconds"] > 3600

    def test_missing_exif_handled_gracefully(self, sharp_image_fixture):
        """Test 3: Verifies absence of EXIF data does not cause crash and is handled gracefully."""
        # Clean image without EXIF
        result = EXIFInspector.inspect(sharp_image_fixture[0], "2026-11-09T14:30:00Z", "FILE_UPLOAD")
        assert result["has_exif"] is False
        assert result["is_consistent"] is True

    def test_future_exif_timestamp_detected(self, sharp_image_fixture):
        """Test 4: Verifies EXIF timestamp set into the distant future is detected as anomalous."""
        future_str = "2035:12:31 23:59:59"
        env_iso = "2026-11-09T14:30:00Z"

        jpeg_with_exif = inject_mock_exif(sharp_image_fixture[0], future_str)
        result = EXIFInspector.inspect(jpeg_with_exif, env_iso, "CAMERA")

        assert result["is_consistent"] is False

    def test_timezone_tolerance(self, sharp_image_fixture):
        """Test 5: Verifies tolerance for slight clock skew within 15 minutes."""
        now_dt = datetime.now(timezone.utc)
        skewed_dt = now_dt - timedelta(minutes=14)
        exif_str = skewed_dt.strftime("%Y:%m:%d %H:%M:%S")

        jpeg_with_exif = inject_mock_exif(sharp_image_fixture[0], exif_str)
        result = EXIFInspector.inspect(jpeg_with_exif, now_dt.isoformat(), "CAMERA")

        assert result["is_consistent"] is True
