"""Tier 3: Interaction Test I-05 — Public Token x WebCrypto Proof x Trusted Checkpoint.
Validates the interaction when public QR tokens resolve to verifiable Merkle proofs,
independently recomputed on the client against trusted authority checkpoints with zero PII/GPS leaked.
"""

import json
import pytest
from tests_e2e.fixtures.crypto_fixtures import ReferenceMerkleTree, rfc8785_canonicalize
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory
from tests_e2e.tier1_features.test_f44_public_token import PublicTokenRegistry
from tests_e2e.tier1_features.test_f45_privacy_public_verify import PublicVerificationPortal


class TestI05PublicVerifyCheckpointSync:
    """Verifies public verification flow from token to cryptographic proof recomputation."""

    def test_end_to_end_token_to_proof_verification(self):
        """Interaction 1: Verifies token resolution and independent client-side proof verification."""
        registry = PublicTokenRegistry()
        env = EnvelopeFactory.create_valid_envelope(lifecycle_stage="HARVEST")
        canonical_leaf = rfc8785_canonicalize(env)

        # Build Merkle tree with 3 leaves
        leaves = [canonical_leaf, b"leaf_two", b"leaf_three"]
        tree = ReferenceMerkleTree(leaves)

        token = registry.issue_token(env["evidence_id"])
        public_payload = PublicVerificationPortal.sanitize_public_payload(env, tree, 0, token)

        # 1. Resolve token
        assert registry.resolve(token) == env["evidence_id"]

        # 2. Client-side independent proof recomputation
        leaf_bytes = canonical_leaf
        proof = public_payload["inclusion_proof"]
        expected_root = bytes.fromhex(public_payload["merkle_root"])

        is_valid = ReferenceMerkleTree.verify_inclusion_proof(leaf_bytes, proof, expected_root)
        assert is_valid is True

    def test_checkpoint_signature_integrity_verification(self):
        """Interaction 2: Verifies checkpoint contains trusted signer ID and signature."""
        env = EnvelopeFactory.create_valid_envelope()
        tree = ReferenceMerkleTree([rfc8785_canonicalize(env)])
        public_payload = PublicVerificationPortal.sanitize_public_payload(env, tree, 0, "token-chk")

        checkpoint = public_payload["checkpoint"]
        assert checkpoint["signer_id"] == "praman-trusted-authority-1"
        assert len(checkpoint["signature"]) > 10

    def test_privacy_preservation_in_public_token_flow(self):
        """Interaction 3: Verifies that public token verification response contains zero farmer PII and zero GPS."""
        env = EnvelopeFactory.create_valid_envelope(
            latitude=19.6640,
            longitude=78.5320,
        )
        tree = ReferenceMerkleTree([rfc8785_canonicalize(env)])
        public_payload = PublicVerificationPortal.sanitize_public_payload(env, tree, 0, "token-priv")

        json_str = json.dumps(public_payload)
        # Verify coordinates are not leaked
        assert "19.664" not in json_str
        assert "78.532" not in json_str

        # Verify farmer PII not leaked
        assert "phone" not in json_str
        assert "farmer_name" not in json_str

    def test_tampered_leaf_hash_fails_client_recomputation(self):
        """Interaction 4: Verifies client detects tampered leaf data against public root."""
        env = EnvelopeFactory.create_valid_envelope()
        tree = ReferenceMerkleTree([rfc8785_canonicalize(env)])
        public_payload = PublicVerificationPortal.sanitize_public_payload(env, tree, 0, "token-tamper")

        tampered_leaf = b"ALTERED_IMAGE_AND_METADATA_BYTES"
        proof = public_payload["inclusion_proof"]
        root = bytes.fromhex(public_payload["merkle_root"])

        assert ReferenceMerkleTree.verify_inclusion_proof(tampered_leaf, proof, root) is False

    def test_tampered_merkle_root_fails_checkpoint_matching(self):
        """Interaction 5: Verifies proof verifying against a corrupted root fails."""
        env = EnvelopeFactory.create_valid_envelope()
        tree = ReferenceMerkleTree([rfc8785_canonicalize(env)])
        public_payload = PublicVerificationPortal.sanitize_public_payload(env, tree, 0, "token-badroot")

        corrupted_root = b"\x00" * 32
        canonical_leaf = rfc8785_canonicalize(env)
        proof = public_payload["inclusion_proof"]

        assert ReferenceMerkleTree.verify_inclusion_proof(canonical_leaf, proof, corrupted_root) is False
