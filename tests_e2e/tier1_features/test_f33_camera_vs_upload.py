"""F-33: Camera vs File-Upload Evidence Capture Tests.
Validates capture source differentiation (CAMERA vs FILE_UPLOAD),
mandatory metadata per source, and MIME type validation.
"""

import pytest


def validate_capture_payload(source: str, mime_type: str, metadata: dict) -> bool:
    """Validates capture metadata per capture source."""
    if source not in ("CAMERA", "FILE_UPLOAD"):
        raise ValueError(f"Invalid capture source: {source}")

    if mime_type not in ("image/jpeg", "image/png"):
        raise ValueError(f"Unsupported MIME type: {mime_type}. Only JPEG and PNG allowed.")

    if source == "CAMERA":
        # CAMERA requires live GPS accuracy
        if metadata.get("gps_accuracy") is None or metadata["gps_accuracy"] <= 0:
            raise ValueError("CAMERA capture requires positive gps_accuracy")

    return True


class TestF33CameraVsUpload:
    """Verifies CAMERA vs FILE_UPLOAD capture behavior and validation."""

    def test_camera_capture_valid(self):
        """Test 1: Verifies CAMERA capture with live GPS metadata and JPEG MIME type is valid."""
        meta = {"gps_accuracy": 3.2, "latitude": 17.385, "longitude": 78.486}
        assert validate_capture_payload("CAMERA", "image/jpeg", meta) is True

    def test_file_upload_png_valid(self):
        """Test 2: Verifies FILE_UPLOAD capture with PNG image is valid."""
        meta = {"gps_accuracy": 10.0, "latitude": 17.385, "longitude": 78.486}
        assert validate_capture_payload("FILE_UPLOAD", "image/png", meta) is True

    def test_camera_missing_gps_rejected(self):
        """Test 3: Verifies CAMERA capture missing live GPS accuracy is rejected."""
        meta = {"latitude": 17.385, "longitude": 78.486}  # Missing gps_accuracy
        with pytest.raises(ValueError, match="CAMERA capture requires positive gps_accuracy"):
            validate_capture_payload("CAMERA", "image/jpeg", meta)

    def test_unsupported_mime_type_rejected(self):
        """Test 4: Verifies unsupported format (e.g. GIF or WebP) is rejected."""
        meta = {"gps_accuracy": 5.0}
        with pytest.raises(ValueError, match="Unsupported MIME type"):
            validate_capture_payload("CAMERA", "image/gif", meta)

        with pytest.raises(ValueError, match="Unsupported MIME type"):
            validate_capture_payload("FILE_UPLOAD", "image/webp", meta)

    def test_invalid_source_rejected(self):
        """Test 5: Verifies invalid source type (e.g. URL_SCRAPE) is rejected."""
        meta = {"gps_accuracy": 5.0}
        with pytest.raises(ValueError, match="Invalid capture source"):
            validate_capture_payload("URL_SCRAPE", "image/jpeg", meta)
