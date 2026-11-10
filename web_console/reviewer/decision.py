from datetime import datetime, timezone
import uuid
from typing import Dict, Any


class ReviewDecisionEngine:
    """Decision engine executing attributable reviewer actions."""

    ALLOWED_ACTIONS = {"APPROVE", "REJECT", "REQUEST_RETAKE"}

    def record_decision(
        self,
        evidence_id: str,
        reviewer_id: str,
        action: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        if action not in self.ALLOWED_ACTIONS:
            raise ValueError(f"Invalid review action: {action}")

        # Mandatory notes for adverse decisions
        if action in ("REJECT", "REQUEST_RETAKE") and len(notes.strip()) < 5:
            raise ValueError(f"Action {action} requires explanatory notes")

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

