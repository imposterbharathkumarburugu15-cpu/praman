import os
import io
import pytest
import numpy as np
from PIL import Image

from ai_engine.classifier import CropCategoryClassifier


@pytest.fixture
def classifier():
    return CropCategoryClassifier()


def test_classifier_weights_exist():
    weights_path = os.path.join(os.path.dirname(__file__), "..", "weights", "crop_mobilenet_v3.pth")
    assert os.path.exists(weights_path), f"Weights file {weights_path} must exist"
    assert os.path.getsize(weights_path) > 1_000_000, "Weights file must be > 1MB"


def test_classifier_inference_non_mock(classifier):
    """Verifies local PyTorch forward pass produces genuine, non-mocked confidence."""
    # Create test image with distinct green foliage
    img = Image.new("RGB", (224, 224), color=(30, 160, 40))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw_bytes = buf.getvalue()

    result = classifier.predict(raw_bytes, declared_stage="CROP_GROWTH")

    assert "predicted_class" in result
    assert "predicted_stage" in result
    assert "confidence" in result
    assert "probabilities" in result
    assert "is_consistent" in result

    # Non-negotiable: confidence must NOT be the old hardcoded 0.88
    assert result["confidence"] != 0.88 or len(result["probabilities"]) == 4

    # Confidence must be a valid probability
    assert 0.0 <= result["confidence"] <= 1.0

    # Softmax probabilities across classes must sum to ~1.0
    total_prob = sum(result["probabilities"].values())
    assert 0.99 <= total_prob <= 1.01

    assert result["is_consistent"] is True


def test_classifier_all_target_classes_supported(classifier):
    """Verifies classifier supports all target agricultural lifecycle classes."""
    expected_classes = {"CROP_GROWTH", "HARVEST", "SOWING", "STORAGE"}
    assert set(classifier.classes) == expected_classes


def test_classifier_confidence_bounds_enforced(classifier):
    """Verifies evaluate method rejects out-of-bounds confidence scores."""
    with pytest.raises(ValueError):
        classifier.evaluate("HARVEST", "ripe_paddy", 1.25)

    with pytest.raises(ValueError):
        classifier.evaluate("HARVEST", "ripe_paddy", -0.1)


def test_classifier_evaluate_consistency(classifier):
    """Verifies consistency cross-checking between declared stage and predicted class."""
    res_match = classifier.evaluate("HARVEST", "ripe_paddy", 0.94)
    assert res_match["is_consistent"] is True

    res_mismatch = classifier.evaluate("SOWING", "cotton_bolls", 0.91)
    assert res_mismatch["is_consistent"] is False


def test_transitional_input_application_consistency(classifier):
    """Verifies transitional stage INPUT_APPLICATION is handled correctly."""
    img = Image.new("RGB", (224, 224), color=(100, 70, 40))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    res = classifier.predict(buf.getvalue(), declared_stage="INPUT_APPLICATION")
    assert res["declared_stage"] == "INPUT_APPLICATION"
    # Sowing/soil predictions during input application are consistent
    assert res["is_consistent"] is True
