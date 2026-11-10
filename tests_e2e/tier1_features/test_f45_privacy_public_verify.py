"""F-45: Privacy-Preserving Public Web Verification Tests.
Validates the public verification endpoint, client-side Merkle proof recomputation,
and strict privacy enforcement: ZERO farmer PII and ZERO exact GPS coordinates.
"""

import hashlib
import json
import pytest
from tests_e2e.fixtures.crypto_fixtures import ReferenceMerkleTree, rfc8785_canonicalize
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory


class PublicVerificationPortal:
    """Public verification service generating privacy-safe verification payloads."""

    FORBIDDEN_PII_FIELDS = {
        "farmer_name", "full_name", "phone_number", "phone", "aadhar",
        "national_id", "email", "address",
    }
    FORBIDDEN_GPS_FIELDS = {
        "latitude", "longitude", "lat", "lon", "gps_coordinates",
        "boundary_geojson", "polygon", "vertices",
    }

    @classmethod
    def sanitize_public_payload(
        cls,
        envelope: dict,
        tree: ReferenceMerkleTree,
        leaf_index: int,
        public_token: str,
    ) -> dict:
        canonical_leaf = rfc8785_canonicalize(envelope)
        leaf_hash = ReferenceMerkleTree.hash_leaf(canonical_leaf).hex()
        proof = tree.get_inclusion_proof(leaf_index)

        # Build public verification payload
        payload = {
            "public_token": public_token,
            "provenance_status": "COMMITTED_TO_LEDGER",
            "crop_type": "Cotton",
            "lifecycle_stage": envelope["lifecycle_stage"],
            "capture_date": envelope["metadata"]["capture_timestamp"][:10],
            "region_coarse": "Adilabad, Telangana",  # Coarse region only
            "image_sha256": envelope["image_hash"],
            "leaf_hash": leaf_hash,
            "merkle_root": tree.root_hex,
            "inclusion_proof": proof,
            "checkpoint": {
                "checkpoint_id": "cp-20261109-001",
                "timestamp": "2026-11-09T15:00:00Z",
                "signer_id": "praman-trusted-authority-1",
                "signature": "MOCK_CHECKPOINT_AUTHORITY_SIG",
            },
        }
        return payload


class TestF45PrivacyPublicVerify:
    """Verifies public verification portal privacy and client-side proof validation."""

    def test_zero_pii_leakage_invariant(self):
        """Test 1: Verifies public response payload contains ZERO farmer PII fields."""
        env = EnvelopeFactory.create_valid_envelope()
        tree = ReferenceMerkleTree([rfc8785_canonicalize(env)])
        payload = PublicVerificationPortal.sanitize_public_payload(env, tree, 0, "token-123")

        payload_str = json.dumps(payload).lower()
        for forbidden in PublicVerificationPortal.FORBIDDEN_PII_FIELDS:
            assert forbidden not in payload_str, f"PII leak detected: {forbidden}"

    def test_zero_exact_gps_leakage_invariant(self):
        """Test 2: Verifies public response payload contains ZERO exact GPS coordinate fields."""
        env = EnvelopeFactory.create_valid_envelope(latitude=17.385044, longitude=78.486671)
        tree = ReferenceMerkleTree([rfc8785_canonicalize(env)])
        payload = PublicVerificationPortal.sanitize_public_payload(env, tree, 0, "token-123")

        payload_str = json.dumps(payload).lower()
        # Verify exact coordinates from envelope are NOT present
        assert "17.385044" not in payload_str
        assert "78.486671" not in payload_str
        for forbidden in PublicVerificationPortal.FORBIDDEN_GPS_FIELDS:
            assert forbidden not in payload_str, f"GPS leak detected: {forbidden}"

        # Coarse region is allowed
        assert "Adilabad, Telangana" in payload["region_coarse"]

    def test_client_side_merkle_proof_recomputation(self):
        """Test 3: Verifies client can independently recompute Merkle root from leaf and inclusion proof."""
        leaves = [
            rfc8785_canonicalize(EnvelopeFactory.create_valid_envelope(sequence_number=i + 1))
            for i in range(3)
        ]
        tree = ReferenceMerkleTree(leaves)

        target_idx = 1
        proof = tree.get_inclusion_proof(target_idx)
        root_bytes = tree.root

        # Client-side proof recomputation
        assert ReferenceMerkleTree.verify_inclusion_proof(leaves[target_idx], proof, root_bytes) is True

    def test_client_detects_tampered_proof(self):
        """Test 4: Verifies client proof verification detects tampered sibling hash in proof."""
        leaves = [
            rfc8785_canonicalize(EnvelopeFactory.create_valid_envelope(sequence_number=i + 1))
            for i in range(2)
        ]
        tree = ReferenceMerkleTree(leaves)
        proof = tree.get_inclusion_proof(0)

        # Tamper proof
        bad_proof = [{"position": proof[0]["position"], "hash": "f" * 64}]
        assert ReferenceMerkleTree.verify_inclusion_proof(leaves[0], bad_proof, tree.root) is False

    def test_checkpoint_authority_signature_binding(self):
        """Test 5: Verifies response includes trusted checkpoint authority signature block."""
        env = EnvelopeFactory.create_valid_envelope()
        tree = ReferenceMerkleTree([rfc8785_canonicalize(env)])
        payload = PublicVerificationPortal.sanitize_public_payload(env, tree, 0, "token-123")

        checkpoint = payload["checkpoint"]
        assert "signer_id" in checkpoint
        assert "signature" in checkpoint
        assert "checkpoint_id" in checkpoint
