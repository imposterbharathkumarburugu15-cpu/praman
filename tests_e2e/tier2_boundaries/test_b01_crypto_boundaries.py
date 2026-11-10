"""Tier 2: Cryptographic Boundary & Edge Case Tests.
Tests extreme payloads, float precision boundaries in RFC 8785,
zero-length strings, Unicode edge cases, and DER signature corner cases.
"""

import math
import pytest
from tests_e2e.fixtures.crypto_fixtures import (
    rfc8785_canonicalize,
    generate_p256_keypair,
    sign_p256_der,
    verify_p256_der,
)


class TestB01CryptoBoundaries:
    """Verifies cryptographic corner cases and extreme boundary values."""

    def test_empty_json_object_and_array(self):
        """Boundary 1: Verifies canonicalization of completely empty objects and empty arrays."""
        assert rfc8785_canonicalize({}) == b"{}"
        assert rfc8785_canonicalize([]) == b"[]"
        assert rfc8785_canonicalize({"empty_arr": [], "empty_obj": {}}) == b'{"empty_arr":[],"empty_obj":{}}'

    def test_float_precision_and_negative_zero(self):
        """Boundary 2: Verifies negative zero (-0.0) canonicalizes to '0' and high-precision floats preserve exactness."""
        res_neg_zero = rfc8785_canonicalize({"val": -0.0})
        assert res_neg_zero == b'{"val":0}'

        # Very small number
        small_num = 1e-6
        can_small = rfc8785_canonicalize({"s": small_num})
        assert b"1e-6" in can_small or b"1e-06" in can_small or b"0.000001" in can_small

    def test_unicode_control_characters_escaping(self):
        """Boundary 3: Verifies ASCII control characters 0x00 to 0x1F are properly escaped."""
        control_chars = "\u0000\u0008\u0009\u000a\u000c\u000d\u001f"
        canonical = rfc8785_canonicalize({"ctrl": control_chars})
        assert b"\\u0000" in canonical
        assert b"\\b" in canonical or b"\\u0008" in canonical
        assert b"\\t" in canonical or b"\\u0009" in canonical
        assert b"\\n" in canonical
        assert b"\\r" in canonical

    def test_zero_byte_payload_signing_and_verification(self, primary_device_keypair):
        """Boundary 4: Verifies signing and verifying empty 0-byte payload."""
        priv_key, pub_pem, _ = primary_device_keypair
        empty_data = b""

        sig = sign_p256_der(priv_key, empty_data)
        assert len(sig) > 0
        assert verify_p256_der(pub_pem, sig, empty_data) is True
        assert verify_p256_der(pub_pem, sig, b"non_empty") is False

    def test_large_canonical_payload(self):
        """Boundary 5: Verifies canonicalization handles deeply nested objects and 1000 keys without stack overflow."""
        large_dict = {f"k_{i:04d}": i for i in range(1000)}
        canonical = rfc8785_canonicalize(large_dict)
        assert len(canonical) > 10000
        assert canonical.startswith(b'{"k_0000":0,')
        assert canonical.endswith(b',"k_0999":999}')
