import secrets
from typing import Dict


def generate_public_token() -> str:
    """Generates a 256-bit (32 bytes) cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(32)


class PublicTokenRegistry:
    """Registry mapping high-entropy tokens to public provenance records."""

    def __init__(self):
        self._tokens: Dict[str, str] = {}

    def issue_token(self, record_id: str) -> str:
        token = generate_public_token()
        self._tokens[token] = record_id
        return token

    def resolve(self, token: str) -> str:
        if token not in self._tokens:
            raise KeyError("Public verification token not found")
        return self._tokens[token]

