"""Unit and adversarial tests for crypto/authority.py."""

import base64
import pytest
from crypto.authority import (
    get_authority_keypair,
    get_authority_public_key_pem,
    sign_checkpoint,
    verify_checkpoint_signature,
    create_signed_checkpoint,
)
from crypto.ecdsa_p256 import generate_keypair, public_key_to_pem, SignatureMalleabilityError, P256_ORDER, extract_rs
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature


class TestAuthorityCheckpointSignatures:
    """Test suite validating NIST P-256 Authority key management and checkpoint signing."""

    def test_authority_key_loading_and_pem_export(self):
        priv, pub = get_authority_keypair()
        assert priv is not None
        assert pub is not None

        pem = get_authority_public_key_pem()
        assert "-----BEGIN PUBLIC KEY-----" in pem
        assert "-----END PUBLIC KEY-----" in pem

    def test_sign_and_verify_valid_checkpoint(self):
        checkpoint = {
            "checkpoint_id": "cp-20261109-001",
            "batch_id": "batch-test-1",
            "merkle_root": "a" * 64,
            "leaf_count": 5,
            "timestamp": "2026-11-09T18:00:00Z",
            "authority_id": "praman-root-authority-1",
        }
        sig_b64 = sign_checkpoint(checkpoint)
        assert isinstance(sig_b64, str)
        assert len(sig_b64) > 40

        # Verify signature
        is_valid = verify_checkpoint_signature(checkpoint, sig_b64)
        assert is_valid is True

        # Verify with signature embedded in dict
        checkpoint_with_sig = {**checkpoint, "signature": sig_b64}
        assert verify_checkpoint_signature(checkpoint_with_sig) is True

    def test_checkpoint_tamper_detection(self):
        checkpoint = {
            "checkpoint_id": "cp-20261109-002",
            "batch_id": "batch-test-2",
            "merkle_root": "b" * 64,
            "leaf_count": 10,
            "timestamp": "2026-11-09T18:05:00Z",
            "authority_id": "praman-root-authority-1",
        }
        sig_b64 = sign_checkpoint(checkpoint)

        # Mutate merkle_root
        tampered_root = {**checkpoint, "merkle_root": "c" * 64}
        assert verify_checkpoint_signature(tampered_root, sig_b64) is False

        # Mutate leaf_count
        tampered_count = {**checkpoint, "leaf_count": 11}
        assert verify_checkpoint_signature(tampered_count, sig_b64) is False

        # Mutate timestamp
        tampered_time = {**checkpoint, "timestamp": "2026-11-09T18:05:01Z"}
        assert verify_checkpoint_signature(tampered_time, sig_b64) is False

        # Mutate checkpoint_id
        tampered_id = {**checkpoint, "checkpoint_id": "cp-20261109-999"}
        assert verify_checkpoint_signature(tampered_id, sig_b64) is False

    def test_cross_keypair_rejection(self):
        checkpoint = {
            "checkpoint_id": "cp-20261109-003",
            "merkle_root": "d" * 64,
            "leaf_count": 3,
            "timestamp": "2026-11-09T18:10:00Z",
            "authority_id": "praman-root-authority-1",
        }
        sig_b64 = sign_checkpoint(checkpoint)

        # Generate a distinct rogue keypair
        _, rogue_pub = generate_keypair()
        rogue_pem = public_key_to_pem(rogue_pub)

        assert verify_checkpoint_signature(checkpoint, sig_b64, authority_pub_pem=rogue_pem) is False

    def test_create_signed_checkpoint_helper(self):
        cp = create_signed_checkpoint(
            checkpoint_id="cp-helper-test",
            merkle_root="e" * 64,
            leaf_count=42,
            timestamp="2026-11-09T18:15:00Z",
            authority_id="praman-root-authority-1",
            batch_id="batch-helper-1",
        )
        assert cp["checkpoint_id"] == "cp-helper-test"
        assert cp["merkle_root"] == "e" * 64
        assert cp["leaf_count"] == 42
        assert "signature" in cp
        assert verify_checkpoint_signature(cp) is True
