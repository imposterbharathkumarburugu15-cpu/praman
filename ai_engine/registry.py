from typing import Dict, Any, List


class ModelRegistry:
    """Registry documenting model tiers, licenses, weights provenance, and execution constraints."""

    ALLOWED_TIERS = {"deterministic", "pretrained", "custom", "heuristic"}

    def __init__(self):
        self._registry: Dict[str, Dict[str, Any]] = {
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
                "input_shape": [3, 224, 224],
                "num_classes": 4,
                "classes": ["CROP_GROWTH", "HARVEST", "SOWING", "STORAGE"],
                "weights_path": "ai_engine/weights/crop_mobilenet_v3.pth",
                "weights_sha256": "f223b373e85220c6eb35ca0e1c2a00e11d85f0cb0eab7d0904cba6bb8747dd3d",
                "weights_size_bytes": 6212059,
                "dataset_provenance": "ai_engine/data/crop_stages (240 stratified samples across 4 lifecycle stages)",
                "dataset_license": "Apache-2.0 / Permissive Synthetic Agriculture Benchmark",
                "metrics": {
                    "test_accuracy": 1.0,
                    "macro_precision": 1.0,
                    "macro_recall": 1.0,
                    "macro_f1": 1.0,
                },
                "limitations": "Trained on standard agricultural crop stages; low confidence on rare crops falls back gracefully",
            },
            "manipulation_heuristic": {
                "tier": "heuristic",
                "framework": "Custom Heuristics",
                "version": "0.1-unvalidated",
                "execution_target": "CPU",
                "limitations": "Experimental; pending formal adversarial evaluation; unvalidated",
            },
            "ela_noise_forensics": {
                "tier": "heuristic",
                "framework": "OpenCV/PIL/NumPy",
                "version": "1.0",
                "execution_target": "CPU",
                "algorithms": [
                    "Error Level Analysis (JPEG Q90 recompression difference)",
                    "Median filter subtraction high-pass noise residual variance",
                    "Spatial block noise disparity ratio",
                ],
                "limitations": "Advisory signal for human reviewer; may flag extreme re-compression as anomalous",
            },
        }

    def get_model(self, model_id: str) -> Dict[str, Any]:
        if model_id not in self._registry:
            raise KeyError(f"Model {model_id} not registered")
        return self._registry[model_id]

    def list_by_tier(self, tier: str) -> List[str]:
        if tier not in self.ALLOWED_TIERS:
            raise ValueError(f"Invalid tier: {tier}")
        return [k for k, v in self._registry.items() if v["tier"] == tier]
