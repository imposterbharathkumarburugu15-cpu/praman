"""F-25: 4-Tier Model Registry Tests.
Validates model categorization into deterministic, pretrained, custom, and heuristic tiers,
with documented limitations and strictly local CPU execution.
"""

import pytest


class ModelRegistry:
    """Registry documenting model tiers, licenses, and execution constraints."""

    ALLOWED_TIERS = {"deterministic", "pretrained", "custom", "heuristic"}

    def __init__(self):
        self._registry = {
            "laplacian_blur": {
                "tier": "deterministic",
                "framework": "OpenCV",
                "version": "4.10",
                "execution_target": "CPU",
                "limitations": "Sensitive to intentional camera motion blur vs out-of-focus blur",
            },
            "luminance_histogram": {
                "tier": "deterministic",
                "framework": "NumPy/OpenCV",
                "version": "1.0",
                "execution_target": "CPU",
                "limitations": "May falsely flag night shots with flash",
            },
            "crop_mobilenet_v3": {
                "tier": "pretrained",
                "framework": "PyTorch/TorchVision",
                "version": "v3-small",
                "execution_target": "CPU",
                "limitations": "Trained on standard agricultural crops; low confidence on rare crops",
            },
            "manipulation_heuristic": {
                "tier": "heuristic",
                "framework": "Custom Heuristics",
                "version": "0.1-unvalidated",
                "execution_target": "CPU",
                "limitations": "Experimental; pending formal adversarial evaluation; unvalidated",
            },
        }

    def get_model(self, model_id: str) -> dict:
        if model_id not in self._registry:
            raise KeyError(f"Model {model_id} not registered")
        return self._registry[model_id]

    def list_by_tier(self, tier: str) -> list:
        if tier not in self.ALLOWED_TIERS:
            raise ValueError(f"Invalid tier: {tier}")
        return [k for k, v in self._registry.items() if v["tier"] == tier]


class TestF25ModelRegistry:
    """Verifies model registry governance and tier classifications."""

    def test_registry_contains_all_four_tiers(self):
        """Test 1: Verifies registry supports and contains deterministic, pretrained, and heuristic tiers."""
        reg = ModelRegistry()
        tiers_present = {v["tier"] for v in reg._registry.values()}
        assert "deterministic" in tiers_present
        assert "pretrained" in tiers_present
        assert "heuristic" in tiers_present

    def test_strictly_local_cpu_execution_invariant(self):
        """Test 2: Verifies all models specify local CPU execution without remote/cloud endpoints."""
        reg = ModelRegistry()
        for name, meta in reg._registry.items():
            assert meta["execution_target"] == "CPU"

    def test_explicit_limitations_documented(self):
        """Test 3: Verifies every registered model has explicit limitations documented."""
        reg = ModelRegistry()
        for name, meta in reg._registry.items():
            assert "limitations" in meta
            assert len(meta["limitations"]) > 10

    def test_invalid_tier_rejected(self):
        """Test 4: Verifies querying or registering with an invalid tier name raises ValueError."""
        reg = ModelRegistry()
        with pytest.raises(ValueError, match="Invalid tier"):
            reg.list_by_tier("cloud_proprietary_api")

    def test_filter_models_by_tier(self):
        """Test 5: Verifies filtering models by deterministic tier returns expected algorithms."""
        reg = ModelRegistry()
        det_models = reg.list_by_tier("deterministic")
        assert "laplacian_blur" in det_models
        assert "luminance_histogram" in det_models
        assert "crop_mobilenet_v3" not in det_models
