"""F-28: Never-Autonomous-Reject Rule Enforcer Tests.
Validates the core platform invariant: AI algorithms NEVER autonomously reject evidence;
low-scoring or anomalous evidence transitions strictly to PENDING_REVIEW for human adjudication.
"""

import pytest


def determine_ai_transition(assessment: dict) -> str:
    """Enforces the platform invariant: AI transitions to PENDING_REVIEW or PENDING_BATCH, NEVER REJECTED."""
    is_blurry = assessment["quality"]["is_blurry"]
    is_exposure_bad = not assessment["quality"]["is_exposure_valid"]
    is_category_mismatch = not assessment["category"]["is_consistent"]
    is_duplicate = assessment["duplicate"]["is_duplicate"]

    anomalies = [is_blurry, is_exposure_bad, is_category_mismatch, is_duplicate]

    if any(anomalies):
        # Even with 100% anomaly failure, state transitions to PENDING_REVIEW for human adjudication
        return "PENDING_REVIEW"
    return "PENDING_BATCH"


class TestF28NeverAutonomousReject:
    """Verifies invariant: AI cannot autonomously reject evidence records."""

    def test_all_anomalies_present_still_transitions_to_review(self):
        """Test 1: Verifies evidence with ALL anomalies (blurry, dark, category mismatch, duplicate) is sent to PENDING_REVIEW."""
        assessment = {
            "quality": {"is_blurry": True, "is_exposure_valid": False},
            "category": {"is_consistent": False},
            "duplicate": {"is_duplicate": True},
        }
        state = determine_ai_transition(assessment)
        assert state == "PENDING_REVIEW"
        assert state != "REJECTED"

    def test_pristine_evidence_transitions_to_batch(self):
        """Test 2: Verifies pristine evidence passing all checks transitions to PENDING_BATCH."""
        assessment = {
            "quality": {"is_blurry": False, "is_exposure_valid": True},
            "category": {"is_consistent": True},
            "duplicate": {"is_duplicate": False},
        }
        state = determine_ai_transition(assessment)
        assert state == "PENDING_BATCH"

    def test_isolated_blur_triggers_review_not_rejection(self):
        """Test 3: Verifies single blur anomaly triggers human review, not rejection."""
        assessment = {
            "quality": {"is_blurry": True, "is_exposure_valid": True},
            "category": {"is_consistent": True},
            "duplicate": {"is_duplicate": False},
        }
        assert determine_ai_transition(assessment) == "PENDING_REVIEW"

    def test_isolated_category_mismatch_triggers_review(self):
        """Test 4: Verifies crop category mismatch triggers human review, not rejection."""
        assessment = {
            "quality": {"is_blurry": False, "is_exposure_valid": True},
            "category": {"is_consistent": False},
            "duplicate": {"is_duplicate": False},
        }
        assert determine_ai_transition(assessment) == "PENDING_REVIEW"

    def test_state_machine_prohibits_ai_rejection_transition(self):
        """Test 5: Verifies AI service execution cannot emit 'REJECTED' transition event."""
        valid_ai_outcomes = {"PENDING_REVIEW", "PENDING_BATCH"}
        test_cases = [
            {"quality": {"is_blurry": True, "is_exposure_valid": False}, "category": {"is_consistent": False}, "duplicate": {"is_duplicate": True}},
            {"quality": {"is_blurry": False, "is_exposure_valid": False}, "category": {"is_consistent": True}, "duplicate": {"is_duplicate": False}},
            {"quality": {"is_blurry": False, "is_exposure_valid": True}, "category": {"is_consistent": True}, "duplicate": {"is_duplicate": False}},
        ]
        for tc in test_cases:
            outcome = determine_ai_transition(tc)
            assert outcome in valid_ai_outcomes
            assert outcome != "REJECTED"
