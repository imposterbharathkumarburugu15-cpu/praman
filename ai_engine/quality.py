import io
from typing import Tuple, Dict, Any
from datetime import datetime, timezone
import numpy as np
import cv2
from PIL import Image, ExifTags

EXIF_DATETIME_ORIGINAL = 0x9003


def compute_laplacian_variance(image_bytes: bytes) -> float:
    """Computes Laplacian variance (sharpness score) of an image using OpenCV."""
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Could not decode image bytes")
    laplacian = cv2.Laplacian(img, cv2.CV_64F)
    return float(laplacian.var())


def compute_luminance_clipping(image_bytes: bytes) -> Tuple[float, float]:
    """Computes percentage of under-exposed (< 15) and over-exposed (> 240) pixels."""
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Could not decode image bytes")
    total_pixels = img.size
    under_count = np.sum(img < 15)
    over_count = np.sum(img > 240)
    under_pct = float(under_count / total_pixels) * 100.0
    over_pct = float(over_count / total_pixels) * 100.0
    return under_pct, over_pct


def validate_image_dimensions(
    image_bytes: bytes,
    min_width: int = 800,
    min_height: int = 600,
    max_aspect_ratio: float = 3.0,
    min_aspect_ratio: float = 0.33,
) -> Dict[str, Any]:
    """Validates resolution and aspect ratio constraints."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        w, h = img.size
        aspect = w / h if h != 0 else 0.0
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


def inspect_exif(image_bytes: bytes, envelope_timestamp_iso: str) -> Dict[str, Any]:
    """Inspects EXIF timestamp and compares with envelope timestamp."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif = img.getexif()
        exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
        dt_raw = exif_ifd.get(EXIF_DATETIME_ORIGINAL) or exif.get(0x0132)
        has_exif = dt_raw is not None
    except Exception:
        has_exif = False
        dt_raw = None

    if not has_exif:
        return {
            "has_exif": False,
            "is_consistent": True,  # Absence of EXIF is non-fatal
            "note": "EXIF stripped or absent",
        }

    try:
        exif_dt_str = str(dt_raw)
        exif_dt = datetime.strptime(exif_dt_str, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
        env_dt = datetime.fromisoformat(envelope_timestamp_iso.replace("Z", "+00:00"))
        diff_seconds = abs((env_dt - exif_dt).total_seconds())
        is_consistent = diff_seconds <= 3600
        return {
            "has_exif": True,
            "exif_timestamp": exif_dt.isoformat(),
            "time_diff_seconds": diff_seconds,
            "is_consistent": is_consistent,
            "note": "Consistent" if is_consistent else "EXIF timestamp diverges from envelope",
        }
    except Exception:
        return {
            "has_exif": True,
            "is_consistent": True,
            "note": "Unparseable EXIF timestamp format",
        }

