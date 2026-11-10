"""Tests for NIST P-256 ECDSA key management, signing, and verification."""

from __future__ import annotations

import base64
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

from crypto.ecdsa_p256 import (
    HALF_P256_ORDER,
    P256_ORDER,
    InvalidSignatureFormatError,
    SignatureMalleabilityError,
    der_to_p1363,
    enforce_low_s,
    extract_rs,
    generate_keypair,
    load_public_key,
    normalize_low_s,
    p1363_to_der,
    public_key_to_der,
    public_key_to_pem,
    public_key_to_raw,
    sign,
    verify,
)


class TestECDSAP256Engine:
    """Verifies P-256 ECDSA cryptographic operations and anti-malleability."""

    def test_keypair_curve_and_formats(self, keypair):
        """Keypair is on SECP256R1 curve; exports and imports cleanly via PEM, DER, and raw point."""
        priv, pub = keypair
        assert isinstance(priv.curve, ec.SECP256R1)
        assert priv.key_size == 256

        # PEM format
        pem_str = public_key_to_pem(pub)
        assert "BEGIN PUBLIC KEY" in pem_str
        pub_from_pem = load_public_key(pem_str)
        assert pub_from_pem.public_numbers() == pub.public_numbers()

        # DER format
        der_bytes = public_key_to_der(pub)
        assert len(der_bytes) == 91
        pub_from_der = load_public_key(der_bytes)
        assert pub_from_der.public_numbers() == pub.public_numbers()

        # Raw uncompressed point format (65 bytes: 0x04 || X || Y)
        raw_bytes = public_key_to_raw(pub)
        assert len(raw_bytes) == 65
        assert raw_bytes[0] == 0x04
        pub_from_raw = load_public_key(raw_bytes)
        assert pub_from_raw.public_numbers() == pub.public_numbers()

    def test_sign_and_verify_der(self, keypair):
        """Sign and verify using ASN.1 DER format."""
        priv, pub = keypair
        payload = b"PRAMAN-DEVICE-ATTESTATION-PAYLOAD"

        sig_der = sign(priv, payload, sig_format="der")
        assert len(sig_der) in range(68, 74)
        assert verify(pub, sig_der, payload) is True

    def test_sign_and_verify_p1363(self, keypair):
        """Sign and verify using IEEE P1363 (64 bytes) format."""
        priv, pub = keypair
        payload = b"PRAMAN-P1363-PAYLOAD"

        sig_p1363 = sign(priv, payload, sig_format="p1363")
        assert len(sig_p1363) == 64
        assert verify(pub, sig_p1363, payload) is True

    def test_lossless_der_p1363_conversion(self, keypair):
        """Bidirectional conversion between ASN.1 DER and IEEE P1363 is lossless."""
        priv, pub = keypair
        payload = b"ROUNDTRIP-CONVERSION-TEST"

        sig_der = sign(priv, payload, sig_format="der")
        sig_p1363 = der_to_p1363(sig_der)
        assert len(sig_p1363) == 64

        sig_der_recovered = p1363_to_der(sig_p1363)
        assert sig_der_recovered == sig_der

        # Both representations verify successfully
        assert verify(pub, sig_der, payload) is True
        assert verify(pub, sig_p1363, payload) is True
        assert verify(pub, sig_der_recovered, payload) is True

    def test_low_s_normalization_in_signing(self, keypair):
        """Signer always outputs low-s signatures (s <= n // 2)."""
        priv, _ = keypair
        for i in range(10):
            sig = sign(priv, f"msg_{i}".encode("utf-8"))
            r, s = extract_rs(sig)
            assert s <= HALF_P256_ORDER

    def test_high_s_malleability_rejection(self, keypair):
        """Verifying a malleable high-s signature (s > n // 2) raises SignatureMalleabilityError."""
        priv, pub = keypair
        payload = b"MALLEABILITY-TEST-MESSAGE"

        sig_der = sign(priv, payload, sig_format="der")
        r, s = extract_rs(sig_der)
        assert s <= HALF_P256_ORDER

        # Create high-s malleable variant: s_high = n - s
        s_high = P256_ORDER - s
        assert s_high > HALF_P256_ORDER

        sig_high_der = encode_dss_signature(r, s_high)
        sig_high_p1363 = r.to_bytes(32, "big") + s_high.to_bytes(32, "big")

        # enforce_low_s must raise SignatureMalleabilityError
        with pytest.raises(SignatureMalleabilityError):
            enforce_low_s(sig_high_der)

        with pytest.raises(SignatureMalleabilityError):
            enforce_low_s(sig_high_p1363)

        # verify with enforce_low_s_check=True must raise SignatureMalleabilityError
        with pytest.raises(SignatureMalleabilityError):
            verify(pub, sig_high_der, payload, enforce_low_s_check=True)

        with pytest.raises(SignatureMalleabilityError):
            verify(pub, sig_high_p1363, payload, enforce_low_s_check=True)

        # normalize_low_s recovers valid low-s signature
        normalized_der = normalize_low_s(sig_high_der)
        assert verify(pub, normalized_der, payload) is True

    def test_tampered_payload_rejection(self, keypair):
        """Single bit modification in payload invalidates signature."""
        priv, pub = keypair
        payload = b"ORIGINAL_PAYLOAD"
        sig = sign(priv, payload)

        assert verify(pub, sig, b"ORIGINAL_PAYLOAE") is False
        assert verify(pub, sig, b"") is False

    def test_cross_keypair_rejection(self, keypair, secondary_keypair):
        """Signature by Key A is strictly rejected by Key B."""
        priv_a, pub_a = keypair
        _, pub_b = secondary_keypair
        payload = b"AUTHENTIC_DATA"

        sig_a = sign(priv_a, payload)
        assert verify(pub_a, sig_a, payload) is True
        assert verify(pub_b, sig_a, payload) is False

    def test_base64_signature_support(self, keypair):
        """Verify signatures passed as Base64 strings."""
        priv, pub = keypair
        payload = b"BASE64-TEST-PAYLOAD"
        sig_der = sign(priv, payload)
        sig_b64 = base64.b64encode(sig_der).decode("ascii")

        assert verify(pub, sig_b64, payload) is True

    def test_malformed_signature_bytes_rejection(self, keypair):
        """Malformed, empty, or truncated signature bytes are safely rejected."""
        _, pub = keypair
        payload = b"PAYLOAD"

        assert verify(pub, b"", payload) is False
        assert verify(pub, b"\x00" * 64, payload) is False
        assert verify(pub, b"NOT_A_VALID_SIGNATURE", payload) is False
        assert verify(pub, b"\x30\x05\x02\x01\x00\x02\x01", payload) is False

    def test_invalid_p1363_length_raises(self):
        """Passing wrong length to p1363_to_der raises InvalidSignatureFormatError."""
        with pytest.raises(InvalidSignatureFormatError):
            p1363_to_der(b"too_short")
