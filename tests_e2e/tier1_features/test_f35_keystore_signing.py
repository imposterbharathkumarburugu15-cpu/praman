"""F-35: On-Device P-256 Keystore Signing Tests.
Validates simulated Android Keystore hardware-backed P-256 key generation,
private key isolation, and RFC 8785 envelope signing.
"""

import pytest
from tests_e2e.fixtures.crypto_fixtures import (
    generate_p256_keypair,
    sign_p256_der,
    verify_p256_der,
    rfc8785_canonicalize,
)
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory


class SimulatedAndroidKeystore:
    """Simulates Android Keystore P-256 hardware security module."""

    def __init__(self):
        self._keys = {}

    def generate_key_pair(self, alias: str) -> str:
        priv, pub_pem, _ = generate_p256_keypair()
        self._keys[alias] = {"priv": priv, "pub_pem": pub_pem}
        return pub_pem

    def sign(self, alias: str, data: bytes) -> bytes:
        if alias not in self._keys:
            raise KeyError(f"Key alias {alias} not found in Keystore")
        priv = self._keys[alias]["priv"]
        return sign_p256_der(priv, data)

    def get_public_key(self, alias: str) -> str:
        if alias not in self._keys:
            raise KeyError(f"Key alias {alias} not found in Keystore")
        return self._keys[alias]["pub_pem"]


class TestF35KeystoreSigning:
    """Verifies mobile keystore signing contracts and isolation."""

    def test_keystore_generates_p256_key(self):
        """Test 1: Verifies Keystore generates a P-256 keypair identified by alias."""
        keystore = SimulatedAndroidKeystore()
        pub_pem = keystore.generate_key_pair("praman_device_key")
        assert "BEGIN PUBLIC KEY" in pub_pem

    def test_on_device_envelope_signing(self):
        """Test 2: Verifies signing RFC 8785 canonical envelope produces verifiable DER signature."""
        keystore = SimulatedAndroidKeystore()
        pub_pem = keystore.generate_key_pair("praman_device_key")

        envelope = EnvelopeFactory.create_valid_envelope()
        canonical_bytes = rfc8785_canonicalize(envelope)

        signature = keystore.sign("praman_device_key", canonical_bytes)
        assert len(signature) > 0
        assert verify_p256_der(pub_pem, signature, canonical_bytes) is True

    def test_missing_alias_raises_error(self):
        """Test 3: Verifies attempting to sign with non-existent alias raises KeyError."""
        keystore = SimulatedAndroidKeystore()
        with pytest.raises(KeyError, match="not found in Keystore"):
            keystore.sign("non_existent_key", b"test_payload")

    def test_signature_deterministic_length(self):
        """Test 4: Verifies ASN.1 DER signature adheres to standard length range (68-74 bytes)."""
        keystore = SimulatedAndroidKeystore()
        keystore.generate_key_pair("key_len_check")
        sig = keystore.sign("key_len_check", b"PAYLOAD")
        assert 68 <= len(sig) <= 74

    def test_multiple_aliases_isolated(self):
        """Test 5: Verifies multiple key aliases within keystore do not collide."""
        keystore = SimulatedAndroidKeystore()
        k1 = keystore.generate_key_pair("alias_1")
        k2 = keystore.generate_key_pair("alias_2")

        assert k1 != k2
        data = b"SHARED_PAYLOAD"
        sig1 = keystore.sign("alias_1", data)

        assert verify_p256_der(k1, sig1, data) is True
        assert verify_p256_der(k2, sig1, data) is False
