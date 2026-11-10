"""F-40: Authenticated Reviewer Web Console Tests.
Validates reviewer RBAC authentication, retrieval of pending review queues,
filtering, and reviewer access control.
"""

import uuid
import pytest


class ReviewerConsoleService:
    """Service providing reviewer queue and authentication logic."""

    def __init__(self):
        self.queue = []
        self.reviewers = {"rev-alice": "token-alice-123", "rev-bob": "token-bob-456"}

    def authenticate(self, auth_token: str) -> str:
        for reviewer_id, token in self.reviewers.items():
            if token == auth_token:
                return reviewer_id
        raise PermissionError("Unauthorized: Invalid reviewer credentials")

    def get_pending_queue(self, auth_token: str, filter_crop: str = None) -> list:
        self.authenticate(auth_token)
        items = [i for i in self.queue if i["status"] == "PENDING_REVIEW"]
        if filter_crop:
            items = [i for i in items if i["crop_type"] == filter_crop]
        return items


class TestF40ReviewerConsole:
    """Verifies reviewer console authentication and queue access."""

    def test_authenticated_reviewer_access(self):
        """Test 1: Verifies authenticated reviewer can fetch pending review queue."""
        service = ReviewerConsoleService()
        service.queue.append({
            "evidence_id": "ev-1",
            "status": "PENDING_REVIEW",
            "crop_type": "Cotton",
            "flag_reason": "LOW_BLUR_SCORE",
        })

        queue = service.get_pending_queue("token-alice-123")
        assert len(queue) == 1
        assert queue[0]["evidence_id"] == "ev-1"

    def test_unauthenticated_request_rejected(self):
        """Test 2: Verifies unauthenticated request is denied with PermissionError."""
        service = ReviewerConsoleService()
        with pytest.raises(PermissionError, match="Unauthorized"):
            service.get_pending_queue("invalid-token")

    def test_filter_queue_by_crop_type(self):
        """Test 3: Verifies reviewer can filter pending queue by crop type."""
        service = ReviewerConsoleService()
        service.queue.extend([
            {"evidence_id": "e1", "status": "PENDING_REVIEW", "crop_type": "Cotton"},
            {"evidence_id": "e2", "status": "PENDING_REVIEW", "crop_type": "Paddy"},
            {"evidence_id": "e3", "status": "PENDING_REVIEW", "crop_type": "Cotton"},
        ])

        cotton_items = service.get_pending_queue("token-alice-123", filter_crop="Cotton")
        assert len(cotton_items) == 2
        assert all(i["crop_type"] == "Cotton" for i in cotton_items)

    def test_empty_pending_queue(self):
        """Test 4: Verifies empty queue returns empty list when all evidence is processed."""
        service = ReviewerConsoleService()
        queue = service.get_pending_queue("token-bob-456")
        assert queue == []

    def test_only_pending_review_status_listed(self):
        """Test 5: Verifies already approved or batched items are not displayed in the pending queue."""
        service = ReviewerConsoleService()
        service.queue.extend([
            {"evidence_id": "e1", "status": "APPROVED", "crop_type": "Cotton"},
            {"evidence_id": "e2", "status": "PENDING_REVIEW", "crop_type": "Cotton"},
            {"evidence_id": "e3", "status": "COMMITTED_TO_LEDGER", "crop_type": "Cotton"},
        ])

        pending = service.get_pending_queue("token-alice-123")
        assert len(pending) == 1
        assert pending[0]["evidence_id"] == "e2"
