"""ADV-03: Cryptographic Anti-Malleability & Signature Adversarial Tests.
Verifies resistance against:
1. High-s ECDSA malleability attacks (s' = n - s) raising SignatureMalleabilityError.
2. Signature payload bit-flip tampering (1 bit altered in canonical envelope).
3. Signature DER byte bit-flip tampering.
4. Public key substitution attacks (Device Key B signs, claims Device Key A).
5. Automatic low-s normalization recovery and idempotent canonicalization.
"""

import base64
import hashlib
import json
import uuid
import pytest
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)
from crypto.ecdsa_p256 import (
    generate_keypair,
    public_key_to_pem,
    sign,
    verify,
    enforce_low_s,
    normalize_low_s,
    P256_ORDER,
    HALF_P256_ORDER,
    SignatureMalleabilityError,
    InvalidSignatureFormatError,
)
from crypto.rfc8785 import canonicalize
from backend.app.services.crypto_verifier import CryptoVerifier
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory


class TestAdv03CryptoMalleabilitySignatures:
    """Adversarial test suite for ECDSA signature security and malleability resistance."""

    def test_high_s_malleability_attack_rejected_by_crypto(self):
        """ADV-03.1: Attacker constructs high-s signature (s' = n - s); verify strict rejection."""
        priv_key, pub_key = generate_keypair()
        message = b"Canonical Evidence Envelope Bytes"

        # Generate standard low-s signature
        der_sig = sign(priv_key, message, sig_format="der")
        r, s = decode_dss_signature(der_sig)
        assert s <= HALF_P256_ORDER, "Original signature must have s in low-s range"

        # Attacker crafts high-s malleable signature: s' = n - s
        high_s = P256_ORDER - s
        assert high_s > HALF_P256_ORDER, "Crafted s' must exceed curve half-order"
        malleable_der_sig = encode_dss_signature(r, high_s)

        # enforce_low_s MUST raise SignatureMalleabilityError
        with pytest.raises(SignatureMalleabilityError, match="Malleable signature detected"):
            enforce_low_s(malleable_der_sig)

        # verify with enforce_low_s_check=True MUST raise SignatureMalleabilityError
        with pytest.raises(SignatureMalleabilityError):
            verify(pub_key, malleable_der_sig, message, enforce_low_s_check=True)

    def test_high_s_signature_rejected_by_backend_crypto_verifier(self, sharp_image_fixture):
        """ADV-03.2: Backend CryptoVerifier rejects malleable high-s signature on evidence ingest."""
        priv_key, pub_key = generate_keypair()
        pub_pem = public_key_to_pem(pub_key)
        image_bytes, image_hash = sharp_image_fixture

        envelope = EnvelopeFactory.create_valid_envelope(
            device_id=str(uuid.uuid4()),
            image_hash=image_hash,
            sequence_number=1,
        )
        canonical_bytes = canonicalize(envelope)

        # Legitimate low-s signature
        valid_der = sign(priv_key, canonical_bytes, sig_format="der")
        r, s = decode_dss_signature(valid_der)

        # Forge high-s signature
        high_s = P256_ORDER - s
        malleable_der = encode_dss_signature(r, high_s)
        malleable_b64 = base64.b64encode(malleable_der).decode("utf-8")

        # Verify backend CryptoVerifier cleanly rejects it
        is_valid, err_msg = CryptoVerifier.verify_envelope_and_image(
            envelope=envelope,
            signature_b64=malleable_b64,
            image_bytes=image_bytes,
            public_key_pem=pub_pem,
        )
        assert is_valid is False
        assert "Signature malleability error" in err_msg

    def test_payload_bit_flip_tampering_rejected(self, sharp_image_fixture):
        """ADV-03.3: 1-bit tampering in canonical payload instantly invalidates ECDSA signature."""
        priv_key, pub_key = generate_keypair()
        image_bytes, image_hash = sharp_image_fixture

        envelope = EnvelopeFactory.create_valid_envelope(
            device_id=str(uuid.uuid4()),
            image_hash=image_hash,
            sequence_number=1,
        )
        canonical_bytes = canonicalize(envelope)
        valid_sig = sign(priv_key, canonical_bytes)

        # Adversary flips 1 bit in canonical payload
        tampered_bytes = bytearray(canonical_bytes)
        tampered_bytes[0] ^= 0x01  # Flip least significant bit of first byte

        # Signature verification MUST return False
        assert verify(pub_key, valid_sig, bytes(tampered_bytes)) is False

    def test_signature_der_byte_tampering_rejected(self):
        """ADV-03.4: 1-byte alteration in DER signature fails verification or raises format error."""
        priv_key, pub_key = generate_keypair()
        payload = b"Sample Evidence Payload"
        valid_sig = sign(priv_key, payload)

        # Tamper with an internal byte in signature
        tampered_sig = bytearray(valid_sig)
        tampered_sig[len(tampered_sig) // 2] ^= 0xFF

        is_valid = verify(pub_key, bytes(tampered_sig), payload)
        assert is_valid is False

    def test_public_key_substitution_attack_rejected(self, sharp_image_fixture):
        """ADV-03.5: Envelope signed with Device Key B cannot verify against registered Device Key A."""
        priv_a, pub_a = generate_keypair()
        priv_b, pub_b = generate_keypair()
        pub_a_pem = public_key_to_pem(pub_a)

        image_bytes, image_hash = sharp_image_fixture
        envelope = EnvelopeFactory.create_valid_envelope(
            device_id="device-A",
            image_hash=image_hash,
        )
        canonical_bytes = canonicalize(envelope)

        # Rogue device B signs the envelope
        sig_b = sign(priv_b, canonical_bytes)
        sig_b_b64 = base64.b64encode(sig_b).decode("utf-8")

        # Ingestion attempts to verify against Device A's registered public key
        is_valid, err_msg = CryptoVerifier.verify_envelope_and_image(
            envelope=envelope,
            signature_b64=sig_b_b64,
            image_bytes=image_bytes,
            public_key_pem=pub_a_pem,
        )
        assert is_valid is False
        assert "Cryptographic signature verification failed" in err_msg

    def test_low_s_normalization_recovers_canonical_signature(self):
        """ADV-03.6: normalize_low_s converts malleable high-s signature to valid low-s form."""
        priv_key, pub_key = generate_keypair()
        payload = b"Recovery Test Message"
        valid_der = sign(priv_key, payload)
        r, s = decode_dss_signature(valid_der)

        # Create high-s
        high_s = P256_ORDER - s
        malleable_der = encode_dss_signature(r, high_s)

        # Normalize back
        recovered_der = normalize_low_s(malleable_der)
        rec_r, rec_s = decode_dss_signature(recovered_der)

        assert rec_r == r
        assert rec_s == s
        assert rec_s <= HALF_P256_ORDER
        assert verify(pub_key, recovered_der, payload) is True
