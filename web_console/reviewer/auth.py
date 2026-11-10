from typing import Dict


class ReviewerAuthService:
    def __init__(self):
        self.reviewers: Dict[str, str] = {
            "rev-alice": "token-alice-123",
            "rev-bob": "token-bob-456",
        }

    def authenticate(self, auth_token: str) -> str:
        for reviewer_id, token in self.reviewers.items():
            if token == auth_token:
                return reviewer_id
        raise PermissionError("Unauthorized: Invalid reviewer credentials")

