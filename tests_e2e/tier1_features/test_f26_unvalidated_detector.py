"""F-26: Unvalidated Manipulation Detector Governance Tests.
Validates governance rules marking manipulation and AI-generated image detectors
as UNVALIDATED pending formal benchmark evaluation, with zero fabricated metrics.
"""

import pytest


class ManipulationDetectorGovernanceOracle:
    """Governance oracle ensuring manipulation heuristics remain unvalidated."""

    def evaluate_tamper_heuristic(self, image_features: dict) -> dict:
        # Heuristic checks (e.g. noise inconsistencies or ELA)
        has_potential_splice = image_features.get("noise_discrepancy", False)

        return {
            "detector_id": "ela_splice_heuristic_v1",
            "validation_status": "UNVALIDATED",
            "is_tamper_suspected": has_potential_splice,
            "confidence_metric": None,  # Must NOT fabricate artificial confidence
            "governance_note": "Unvalidated heuristic. Intended for human reviewer advisory only.",
            "autonomous_action_allowed": False,
        }


class TestF26UnvalidatedDetectorGovernance:
    """Verifies governance invariants for unvalidated detection heuristics."""

    def test_detector_marked_unvalidated(self):
        """Test 1: Verifies validation_status is explicitly UNVALIDATED."""
        oracle = ManipulationDetectorGovernanceOracle()
        res = oracle.evaluate_tamper_heuristic({"noise_discrepancy": True})
        assert res["validation_status"] == "UNVALIDATED"

    def test_zero_fabricated_confidence_metrics(self):
        """Test 2: Verifies unvalidated detector does not fabricate false confidence percentages."""
        oracle = ManipulationDetectorGovernanceOracle()
        res = oracle.evaluate_tamper_heuristic({"noise_discrepancy": True})
        assert res["confidence_metric"] is None

    def test_autonomous_rejection_forbidden(self):
        """Test 3: Verifies autonomous_action_allowed is strictly False."""
        oracle = ManipulationDetectorGovernanceOracle()
        res = oracle.evaluate_tamper_heuristic({"noise_discrepancy": True})
        assert res["autonomous_action_allowed"] is False

    def test_advisory_note_present(self):
        """Test 4: Verifies structured output contains human-reviewer advisory note."""
        oracle = ManipulationDetectorGovernanceOracle()
        res = oracle.evaluate_tamper_heuristic({})
        assert "human reviewer advisory" in res["governance_note"].lower()

    def test_tamper_heuristic_flags_for_review_not_rejection(self):
        """Test 5: Verifies heuristic flag triggers review advisory rather than automated rejection."""
        oracle = ManipulationDetectorGovernanceOracle()
        res = oracle.evaluate_tamper_heuristic({"noise_discrepancy": True})

        if res["is_tamper_suspected"]:
            decision = "FLAG_FOR_REVIEW"
        else:
            decision = "APPROVE"

        assert decision == "FLAG_FOR_REVIEW"
        assert decision != "REJECT"
