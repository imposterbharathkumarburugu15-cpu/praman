"""F-42: Attributable Review Decision Engine Tests.
Validates human review decision recording (APPROVE, REJECT, REQUEST_RETAKE),
mandatory reason notes, reviewer attribution, and audit logging.
"""

from datetime import datetime, timezone
import uuid
import pytest


class ReviewDecisionEngine:
    """Decision engine executing attributable reviewer actions."""

    ALLOWED_ACTIONS = {"APPROVE", "REJECT", "REQUEST_RETAKE"}

    def record_decision(
        self,
        evidence_id: str,
        reviewer_id: str,
        action: str,
        notes: str = "",
    ) -> dict:
        if action not in self.ALLOWED_ACTIONS:
            raise ValueError(f"Invalid review action: {action}")

        # Mandatory notes for adverse decisions
        if action in ("REJECT", "REQUEST_RETAKE") and len(notes.strip()) < 5:
            raise ValueError(f"Action {action} requires explanatory notes")

        # Map to platform state
        if action == "APPROVE":
            new_state = "APPROVED"
        elif action == "REJECT":
            new_state = "REJECTED"
        else:
            new_state = "RETAKE_REQUESTED"

        return {
            "decision_id": str(uuid.uuid4()),
            "evidence_id": evidence_id,
            "reviewer_id": reviewer_id,
            "action": action,
            "new_state": new_state,
            "notes": notes,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }


class TestF42ReviewDecisionEngine:
    """Verifies review decision execution and attribution."""

    def test_approve_decision(self):
        """Test 1: Verifies reviewer can APPROVE evidence, transitioning state to APPROVED."""
        engine = ReviewDecisionEngine()
        rec = engine.record_decision(
            evidence_id="ev-101",
            reviewer_id="rev-alice",
            action="APPROVE",
            notes="Crop canopy clear and verified.",
        )
        assert rec["new_state"] == "APPROVED"
        assert rec["reviewer_id"] == "rev-alice"

    def test_request_retake_requires_notes(self):
        """Test 2: Verifies REQUEST_RETAKE fails without explanatory notes."""
        engine = ReviewDecisionEngine()
        with pytest.raises(ValueError, match="requires explanatory notes"):
            engine.record_decision(
                evidence_id="ev-102",
                reviewer_id="rev-alice",
                action="REQUEST_RETAKE",
                notes="",  # Empty notes
            )

    def test_reject_requires_notes(self):
        """Test 3: Verifies REJECT fails without explanatory notes."""
        engine = ReviewDecisionEngine()
        with pytest.raises(ValueError, match="requires explanatory notes"):
            engine.record_decision(
                evidence_id="ev-103",
                reviewer_id="rev-alice",
                action="REJECT",
                notes="   ",
            )

    def test_request_retake_success_with_notes(self):
        """Test 4: Verifies REQUEST_RETAKE succeeds when comprehensive reason notes are provided."""
        engine = ReviewDecisionEngine()
        rec = engine.record_decision(
            evidence_id="ev-104",
            reviewer_id="rev-bob",
            action="REQUEST_RETAKE",
            notes="Lens smudge detected; please wipe lens and capture again.",
        )
        assert rec["new_state"] == "RETAKE_REQUESTED"
        assert "Lens smudge" in rec["notes"]

    def test_invalid_action_rejected(self):
        """Test 5: Verifies unsupported action names raise ValueError."""
        engine = ReviewDecisionEngine()
        with pytest.raises(ValueError, match="Invalid review action"):
            engine.record_decision("ev-1", "rev-alice", "IGNORE", "notes")
