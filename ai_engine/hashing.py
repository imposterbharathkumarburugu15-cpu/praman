import hashlib
import numpy as np
import cv2


def compute_sha256(content_bytes: bytes) -> str:
    """Computes exact SHA-256 hash."""
    return hashlib.sha256(content_bytes).hexdigest()


def compute_phash_64(image_bytes: bytes) -> str:
    """Computes 64-bit DCT perceptual hash (pHash) as 16-hex-digit string."""
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Could not decode image bytes")
    resized = cv2.resize(img, (32, 32), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))
    dct_low = dct[0:8, 0:8]
    med = np.median(dct_low)
    bits = (dct_low > med).flatten()
    val = 0
    for b in bits:
        val = (val << 1) | int(b)
    return f"{val:016x}"


def compute_dhash_64(image_bytes: bytes) -> str:
    """Computes 64-bit difference hash (dHash) as 16-hex-digit string."""
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Could not decode image bytes")
    resized = cv2.resize(img, (9, 8), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    bits = diff.flatten()
    val = 0
    for b in bits:
        val = (val << 1) | int(b)
    return f"{val:016x}"


def hamming_distance_hex(hash1_hex: str, hash2_hex: str) -> int:
    """Calculates bitwise Hamming distance between two hex hash strings."""
    v1 = int(hash1_hex, 16)
    v2 = int(hash2_hex, 16)
    return bin(v1 ^ v2).count("1")


def safe_compute_phash_64(image_bytes: bytes) -> str | None:
    """Safely computes 64-bit DCT pHash, returning None if bytes cannot be decoded as image."""
    try:
        return compute_phash_64(image_bytes)
    except Exception:
        return None


def safe_compute_dhash_64(image_bytes: bytes) -> str | None:
    """Safely computes 64-bit dHash, returning None if bytes cannot be decoded as image."""
    try:
        return compute_dhash_64(image_bytes)
    except Exception:
        return None


def safe_compute_all_hashes(image_bytes: bytes) -> dict[str, str | None]:
    """Computes SHA-256, 64-bit pHash, and 64-bit dHash from image bytes."""
    return {
        "sha256": compute_sha256(image_bytes),
        "phash": safe_compute_phash_64(image_bytes),
        "dhash": safe_compute_dhash_64(image_bytes),
    }


