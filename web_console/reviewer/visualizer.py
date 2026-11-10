from typing import Dict, Any


def build_reviewer_inspection_view(
    evidence_envelope: Dict[str, Any],
    is_signature_valid: bool,
    ai_assessment: Dict[str, Any],
) -> Dict[str, Any]:
    """Builds the comprehensive reviewer visualizer card data model."""
    q = ai_assessment["quality"]
    d = ai_assessment["duplicate"]

    if q["blur_score"] >= 100.0:
        blur_status = "PASS"
    elif q["blur_score"] >= 50.0:
        blur_status = "WARNING"
    else:
        blur_status = "FAIL"

    return {
        "evidence_id": evidence_envelope["evidence_id"],
        "crypto_badge": {
            "is_valid": is_signature_valid,
            "device_id": evidence_envelope["device_id"],
            "sequence_number": evidence_envelope["sequence_number"],
            "status_label": "VERIFIED_ECDSA" if is_signature_valid else "INVALID_SIGNATURE",
        },
        "quality_card": {
            "blur_status": blur_status,
            "blur_score": q["blur_score"],
            "exposure_valid": q["is_exposure_valid"],
            "resolution": f"{q['width']}x{q['height']}",
        },
        "duplicate_card": {
            "is_duplicate": d["is_duplicate"],
            "nearest_phash_distance": d["nearest_phash_distance"],
            "duplicate_warning": d["is_duplicate"] or d["nearest_phash_distance"] <= 10,
        },
    }

