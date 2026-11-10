"""F-27: Explainable Structured AI Output Schema Tests.
Validates the unified JSON assessment record schema containing quality,
duplicate, category, and governance sections per Interface Contract R4.
"""

import json
import uuid
import pytest


def validate_ai_assessment_schema(record: dict) -> bool:
    """Validates assessment record against interface contract schema."""
    assert "evidence_id" in record
    assert "quality" in record
    assert "duplicate" in record
    assert "category" in record
    assert "governance" in record

    q = record["quality"]
    assert isinstance(q["blur_score"], (int, float))
    assert isinstance(q["is_blurry"], bool)
    assert isinstance(q["exposure_under_pct"], (int, float))
    assert isinstance(q["exposure_over_pct"], (int, float))
    assert isinstance(q["is_exposure_valid"], bool)
    assert isinstance(q["width"], int)
    assert isinstance(q["height"], int)
    assert isinstance(q["is_resolution_valid"], bool)
    assert isinstance(q["exif_consistent"], bool)

    d = record["duplicate"]
    assert isinstance(d["exact_sha256_match"], bool)
    assert isinstance(d["phash"], str)
    assert isinstance(d["nearest_phash_distance"], int)
    assert isinstance(d["is_duplicate"], bool)

    c = record["category"]
    assert isinstance(c["declared_stage"], str)
    assert isinstance(c["predicted_class"], str)
    assert 0.0 <= c["confidence"] <= 1.0
    assert isinstance(c["is_consistent"], bool)

    g = record["governance"]
    assert isinstance(g["model_tiers_used"], list)
    assert g["manipulation_detector_status"] in ("UNVALIDATED", "FORMALLY_EVALUATED")
    assert isinstance(g["review_recommended"], bool)
    assert g["recommended_action"] in ("APPROVE", "FLAG_FOR_REVIEW")
    assert g["recommended_action"] != "REJECT"

    return True


class TestF27StructuredAISchema:
    """Verifies schema conformance of AI assessment records."""

    def test_nominal_assessment_record_schema(self):
        """Test 1: Verifies schema conformance for an approved, high-quality evidence item."""
        record = {
            "evidence_id": str(uuid.uuid4()),
            "quality": {
                "blur_score": 142.5,
                "is_blurry": False,
                "exposure_under_pct": 1.2,
                "exposure_over_pct": 0.4,
                "is_exposure_valid": True,
                "width": 1920,
                "height": 1080,
                "is_resolution_valid": True,
                "exif_consistent": True,
            },
            "duplicate": {
                "exact_sha256_match": False,
                "phash": "9768689768979796",
                "nearest_phash_distance": 28,
                "is_duplicate": False,
            },
            "category": {
                "declared_stage": "CROP_GROWTH",
                "predicted_class": "maize_field",
                "confidence": 0.88,
                "is_consistent": True,
            },
            "governance": {
                "model_tiers_used": ["deterministic", "pretrained", "heuristic"],
                "manipulation_detector_status": "UNVALIDATED",
                "review_recommended": False,
                "recommended_action": "APPROVE",
            },
        }
        assert validate_ai_assessment_schema(record) is True

    def test_flagged_for_review_assessment_record_schema(self):
        """Test 2: Verifies schema conformance for an anomalous image flagged for review."""
        record = {
            "evidence_id": str(uuid.uuid4()),
            "quality": {
                "blur_score": 24.1,
                "is_blurry": True,
                "exposure_under_pct": 0.5,
                "exposure_over_pct": 0.2,
                "is_exposure_valid": True,
                "width": 1920,
                "height": 1080,
                "is_resolution_valid": True,
                "exif_consistent": True,
            },
            "duplicate": {
                "exact_sha256_match": False,
                "phash": "0123456789abcdef",
                "nearest_phash_distance": 20,
                "is_duplicate": False,
            },
            "category": {
                "declared_stage": "HARVEST",
                "predicted_class": "unclear_field",
                "confidence": 0.45,
                "is_consistent": False,
            },
            "governance": {
                "model_tiers_used": ["deterministic", "heuristic"],
                "manipulation_detector_status": "UNVALIDATED",
                "review_recommended": True,
                "recommended_action": "FLAG_FOR_REVIEW",
            },
        }
        assert validate_ai_assessment_schema(record) is True

    def test_prohibition_of_reject_recommended_action(self):
        """Test 3: Verifies recommended_action 'REJECT' violates schema contract."""
        record = {
            "evidence_id": str(uuid.uuid4()),
            "quality": {"blur_score": 10.0, "is_blurry": True, "exposure_under_pct": 0.0, "exposure_over_pct": 0.0, "is_exposure_valid": True, "width": 800, "height": 600, "is_resolution_valid": True, "exif_consistent": True},
            "duplicate": {"exact_sha256_match": False, "phash": "0000000000000000", "nearest_phash_distance": 30, "is_duplicate": False},
            "category": {"declared_stage": "SOWING", "predicted_class": "unknown", "confidence": 0.1, "is_consistent": False},
            "governance": {
                "model_tiers_used": ["deterministic"],
                "manipulation_detector_status": "UNVALIDATED",
                "review_recommended": True,
                "recommended_action": "REJECT",  # Prohibited!
            },
        }
        with pytest.raises(AssertionError):
            validate_ai_assessment_schema(record)

    def test_missing_quality_key_fails_validation(self):
        """Test 4: Verifies omission of required top-level key fails validation."""
        record = {"evidence_id": str(uuid.uuid4())}
        with pytest.raises(AssertionError):
            validate_ai_assessment_schema(record)

    def test_json_roundtrip_fidelity(self):
        """Test 5: Verifies assessment record serializes to JSON and deserializes identically."""
        original = {
            "evidence_id": "test-id",
            "quality": {"blur_score": 110.2, "is_blurry": False, "exposure_under_pct": 2.0, "exposure_over_pct": 1.0, "is_exposure_valid": True, "width": 1280, "height": 720, "is_resolution_valid": True, "exif_consistent": True},
            "duplicate": {"exact_sha256_match": False, "phash": "1234567890abcdef", "nearest_phash_distance": 25, "is_duplicate": False},
            "category": {"declared_stage": "SOWING", "predicted_class": "plowed_field", "confidence": 0.9, "is_consistent": True},
            "governance": {"model_tiers_used": ["deterministic", "pretrained"], "manipulation_detector_status": "UNVALIDATED", "review_recommended": False, "recommended_action": "APPROVE"},
        }
        json_str = json.dumps(original)
        reloaded = json.loads(json_str)
        assert reloaded == original
