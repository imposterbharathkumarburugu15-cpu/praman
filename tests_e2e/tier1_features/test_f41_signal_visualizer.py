"""F-41: Cryptographic & AI Signal Visualizer Tests.
Validates the data model powering reviewer UI cards:
cryptographic badges, blur/exposure indicators, and duplicate match comparisons.
"""

import pytest


def build_reviewer_inspection_view(
    evidence_envelope: dict,
    is_signature_valid: bool,
    ai_assessment: dict,
) -> dict:
    """Builds the comprehensive reviewer visualizer model."""
    q = ai_assessment["quality"]
    d = ai_assessment["duplicate"]

    # Blur badge logic
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


class TestF41SignalVisualizer:
    """Verifies reviewer signal visualizer data structures."""

    def test_pristine_evidence_visualizer_cards(self):
        """Test 1: Verifies all green pass badges for authentic high-quality evidence."""
        envelope = {"evidence_id": "ev-1", "device_id": "dev-1", "sequence_number": 5}
        ai_assessment = {
            "quality": {"blur_score": 145.0, "is_exposure_valid": True, "width": 1920, "height": 1080},
            "duplicate": {"is_duplicate": False, "nearest_phash_distance": 28},
        }

        view = build_reviewer_inspection_view(envelope, True, ai_assessment)
        assert view["crypto_badge"]["status_label"] == "VERIFIED_ECDSA"
        assert view["quality_card"]["blur_status"] == "PASS"
        assert view["duplicate_card"]["duplicate_warning"] is False

    def test_blurry_evidence_visualizer_flag(self):
        """Test 2: Verifies low blur score produces FAIL blur_status."""
        envelope = {"evidence_id": "ev-2", "device_id": "dev-1", "sequence_number": 6}
        ai_assessment = {
            "quality": {"blur_score": 32.0, "is_exposure_valid": True, "width": 1920, "height": 1080},
            "duplicate": {"is_duplicate": False, "nearest_phash_distance": 30},
        }

        view = build_reviewer_inspection_view(envelope, True, ai_assessment)
        assert view["quality_card"]["blur_status"] == "FAIL"

    def test_tampered_crypto_badge(self):
        """Test 3: Verifies invalid signature produces INVALID_SIGNATURE badge."""
        envelope = {"evidence_id": "ev-3", "device_id": "dev-1", "sequence_number": 7}
        ai_assessment = {
            "quality": {"blur_score": 120.0, "is_exposure_valid": True, "width": 1920, "height": 1080},
            "duplicate": {"is_duplicate": False, "nearest_phash_distance": 25},
        }

        view = build_reviewer_inspection_view(envelope, False, ai_assessment)
        assert view["crypto_badge"]["status_label"] == "INVALID_SIGNATURE"
        assert view["crypto_badge"]["is_valid"] is False

    def test_near_duplicate_visualizer_warning(self):
        """Test 4: Verifies low pHash distance triggers duplicate warning flag."""
        envelope = {"evidence_id": "ev-4", "device_id": "dev-1", "sequence_number": 8}
        ai_assessment = {
            "quality": {"blur_score": 120.0, "is_exposure_valid": True, "width": 1920, "height": 1080},
            "duplicate": {"is_duplicate": False, "nearest_phash_distance": 4},
        }

        view = build_reviewer_inspection_view(envelope, True, ai_assessment)
        assert view["duplicate_card"]["duplicate_warning"] is True

    def test_borderline_blur_status_warning(self):
        """Test 5: Verifies borderline blur score (between 50 and 100) produces WARNING badge."""
        envelope = {"evidence_id": "ev-5", "device_id": "dev-1", "sequence_number": 9}
        ai_assessment = {
            "quality": {"blur_score": 75.0, "is_exposure_valid": True, "width": 1920, "height": 1080},
            "duplicate": {"is_duplicate": False, "nearest_phash_distance": 30},
        }

        view = build_reviewer_inspection_view(envelope, True, ai_assessment)
        assert view["quality_card"]["blur_status"] == "WARNING"
