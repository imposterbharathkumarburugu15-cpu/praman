import pytest
from tests_e2e.fixtures.image_generator import (
    SyntheticImageGenerator,
    compute_laplacian_variance,
    compute_luminance_clipping,
    compute_phash_64,
    hamming_distance_hex,
)
from ai_engine.evaluator import ai_evaluator
from ai_engine.classifier import CropCategoryClassifier
from ai_engine.registry import ModelRegistry
from ai_engine.unvalidated import ManipulationDetectorGovernance


@pytest.fixture
def sharp_image():
    return SyntheticImageGenerator.create_sharp_crop_image(1920, 1080)


@pytest.fixture
def blurry_image():
    return SyntheticImageGenerator.create_blurry_image(1920, 1080, blur_radius=25)


def test_ai_quality_evaluator_sharp(sharp_image):
    raw_bytes, image_hash = sharp_image
    envelope = {
        "lifecycle_stage": "CROP_GROWTH",
        "metadata": {
            "capture_timestamp": "2026-11-09T14:00:00Z",
        }
    }
    res = ai_evaluator.evaluate_evidence("ev-101", raw_bytes, envelope)
    assert res["quality"]["is_blurry"] is False
    assert res["quality"]["is_exposure_valid"] is True
    assert res["quality"]["is_resolution_valid"] is True
    assert res["category"]["is_consistent"] is True
    assert res["governance"]["recommended_action"] == "APPROVE"
    assert res["governance"]["state_transition"] == "PENDING_BATCH"


def test_ai_quality_evaluator_blurry_never_rejects(blurry_image):
    raw_bytes, image_hash = blurry_image
    envelope = {
        "lifecycle_stage": "CROP_GROWTH",
        "metadata": {
            "capture_timestamp": "2026-11-09T14:00:00Z",
        }
    }
    res = ai_evaluator.evaluate_evidence("ev-102", raw_bytes, envelope)
    assert res["quality"]["is_blurry"] is True
    # Invariant: Never autonomous reject!
    assert res["governance"]["recommended_action"] == "FLAG_FOR_REVIEW"
    assert res["governance"]["state_transition"] == "PENDING_REVIEW"
    assert res["governance"]["recommended_action"] != "REJECT"


def test_duplicate_detection_flags_for_review(sharp_image):
    raw_bytes, image_hash = sharp_image
    envelope = {"lifecycle_stage": "HARVEST"}
    res = ai_evaluator.evaluate_evidence("ev-103", raw_bytes, envelope, known_hashes=[image_hash])
    assert res["duplicate"]["is_duplicate"] is True
    assert res["governance"]["recommended_action"] == "FLAG_FOR_REVIEW"


def test_model_registry_tiers():
    registry = ModelRegistry()
    assert "deterministic" in registry.ALLOWED_TIERS
    assert "pretrained" in registry.ALLOWED_TIERS
    assert "heuristic" in registry.ALLOWED_TIERS
    det_models = registry.list_by_tier("deterministic")
    assert len(det_models) >= 2


def test_unvalidated_manipulation_governance():
    gov = ManipulationDetectorGovernance()
    res = gov.evaluate_tamper_heuristic({"noise_discrepancy": True})
    assert res["validation_status"] == "UNVALIDATED"
    assert res["confidence_metric"] is None
    assert res["autonomous_action_allowed"] is False
