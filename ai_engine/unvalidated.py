from typing import Dict, Any, Optional


class ManipulationDetectorGovernance:
    """Governance oracle ensuring manipulation heuristics remain unvalidated."""

    def evaluate_tamper_heuristic(self, image_features: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        features = image_features or {}
        has_potential_splice = features.get("noise_discrepancy", False)

        return {
            "detector_id": "ela_splice_heuristic_v1",
            "validation_status": "UNVALIDATED",
            "is_tamper_suspected": has_potential_splice,
            "confidence_metric": None,  # Must NOT fabricate artificial confidence
            "governance_note": "Unvalidated heuristic. Intended for human reviewer advisory only.",
            "autonomous_action_allowed": False,
        }

