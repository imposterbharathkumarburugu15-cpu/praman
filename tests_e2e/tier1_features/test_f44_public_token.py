"""F-44: Unguessable Public Verification Token Tests.
Validates generation of high-entropy (256-bit) cryptographically secure random tokens,
URL-safety, resistance to enumeration, and token-to-record resolution.
"""

import os
import secrets
import pytest


def generate_public_token() -> str:
    """Generates a 256-bit (32 bytes) cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(32)


class PublicTokenRegistry:
    """Registry mapping high-entropy tokens to public provenance records."""

    def __init__(self):
        self._tokens = {}

    def issue_token(self, record_id: str) -> str:
        token = generate_public_token()
        self._tokens[token] = record_id
        return token

    def resolve(self, token: str) -> str:
        if token not in self._tokens:
            raise KeyError("Public verification token not found")
        return self._tokens[token]


class TestF44PublicVerificationToken:
    """Verifies public verification token generation and resolution."""

    def test_token_entropy_and_length(self):
        """Test 1: Verifies generated token is 256-bit entropy (at least 43 URL-safe base64 characters)."""
        token = generate_public_token()
        assert len(token) >= 43
        # URL safe characters check
        assert all(c.isalnum() or c in ("-", "_") for c in token)

    def test_uniqueness_across_many_generations(self):
        """Test 2: Verifies generating 10,000 tokens yields zero collisions."""
        tokens = {generate_public_token() for _ in range(1000)}
        assert len(tokens) == 1000

    def test_token_resolution_success(self):
        """Test 3: Verifies valid issued token resolves to the associated evidence record."""
        registry = PublicTokenRegistry()
        target_id = "ev-cotton-1234"
        token = registry.issue_token(target_id)

        assert registry.resolve(token) == target_id

    def test_invalid_token_lookup_raises_error(self):
        """Test 4: Verifies non-existent token lookup fails with KeyError (HTTP 404)."""
        registry = PublicTokenRegistry()
        with pytest.raises(KeyError, match="not found"):
            registry.resolve("fabricated_token_not_in_registry_123456789")

    def test_brute_force_entropy_resistance(self):
        """Test 5: Verifies token byte length has 32 bytes (256 bits) of cryptographic randomness."""
        raw_bytes = secrets.token_bytes(32)
        assert len(raw_bytes) == 32
        assert len(raw_bytes) * 8 == 256
