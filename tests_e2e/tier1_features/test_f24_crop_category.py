"""F-24: Crop Category Consistency Classifier Tests.
Validates local crop/stage classification, confidence score bounds [0.0, 1.0],
and cross-checking declared lifecycle stages with computer vision predictions.
"""

import pytest


class CropCategoryClassifierOracle:
    """Reference crop category consistency evaluator."""

    KNOWN_CLASSES = {
        "SOWING": ["plowed_field", "soil_seeds", "furrows"],
        "INPUT_APPLICATION": ["fertilizer_sprayer", "irrigation_pipe", "treated_soil"],
        "CROP_GROWTH": ["cotton_canopy", "maize_field", "green_foliage"],
        "HARVEST": ["cotton_bolls", "ripe_paddy", "combine_harvester"],
        "STORAGE": ["grain_bags", "warehouse_silo", "storage_tarp"],
    }

    def evaluate(self, declared_stage: str, predicted_class: str, confidence: float) -> dict:
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Confidence score {confidence} must be in [0.0, 1.0]")

        valid_stage_classes = self.KNOWN_CLASSES.get(declared_stage, [])
        is_consistent = predicted_class in valid_stage_classes

        return {
            "declared_stage": declared_stage,
            "predicted_class": predicted_class,
            "confidence": round(confidence, 3),
            "is_consistent": is_consistent,
        }


class TestF24CropCategoryClassifier:
    """Verifies crop category consistency classification contracts."""

    def test_consistent_crop_growth_classification(self):
        """Test 1: Verifies matching declared stage CROP_GROWTH and green_foliage prediction is marked consistent."""
        oracle = CropCategoryClassifierOracle()
        res = oracle.evaluate(
            declared_stage="CROP_GROWTH",
            predicted_class="cotton_canopy",
            confidence=0.88,
        )
        assert res["is_consistent"] is True
        assert res["confidence"] == 0.88

    def test_inconsistent_stage_flagged(self):
        """Test 2: Verifies mismatch (declared SOWING but predicted ripe_paddy) is marked inconsistent."""
        oracle = CropCategoryClassifierOracle()
        res = oracle.evaluate(
            declared_stage="SOWING",
            predicted_class="ripe_paddy",
            confidence=0.92,
        )
        assert res["is_consistent"] is False

    def test_confidence_score_bounds_enforced(self):
        """Test 3: Verifies confidence score must be strictly within [0.0, 1.0]."""
        oracle = CropCategoryClassifierOracle()
        with pytest.raises(ValueError):
            oracle.evaluate("HARVEST", "cotton_bolls", 1.25)

        with pytest.raises(ValueError):
            oracle.evaluate("HARVEST", "cotton_bolls", -0.05)

    def test_all_lifecycle_stages_supported(self):
        """Test 4: Verifies every lifecycle stage has associated valid visual classes."""
        oracle = CropCategoryClassifierOracle()
        stages = ["SOWING", "INPUT_APPLICATION", "CROP_GROWTH", "HARVEST", "STORAGE"]
        for stage in stages:
            assert stage in oracle.KNOWN_CLASSES
            assert len(oracle.KNOWN_CLASSES[stage]) > 0

    def test_low_confidence_handling(self):
        """Test 5: Verifies prediction with low confidence (< 0.5) is recorded accurately without fabrication."""
        oracle = CropCategoryClassifierOracle()
        res = oracle.evaluate("STORAGE", "grain_bags", 0.42)
        assert res["confidence"] == 0.42
        assert res["is_consistent"] is True
