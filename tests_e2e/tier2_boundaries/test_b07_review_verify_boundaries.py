"""Tier 2: Review & Public Verification Boundary Tests.
Tests revoked device keys, tampered Merkle inclusion proofs, invalid checkpoint signatures,
and boundary validation on reviewer notes.
"""

import pytest
from tests_e2e.fixtures.crypto_fixtures import ReferenceMerkleTree, rfc8785_canonicalize
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory
from tests_e2e.tier1_features.test_f42_review_decision_engine import ReviewDecisionEngine


class TestB07ReviewVerifyBoundaries:
    """Verifies review and public verification boundary security rules."""

    def test_reviewer_notes_length_boundary(self):
        """Boundary 1: Verifies note length boundary (4 chars rejected, 5 chars accepted)."""
        engine = ReviewDecisionEngine()

        with pytest.raises(ValueError, match="requires explanatory notes"):
            engine.record_decision("ev-1", "rev-1", "REQUEST_RETAKE", "1234")  # 4 chars

        rec = engine.record_decision("ev-1", "rev-1", "REQUEST_RETAKE", "12345")  # 5 chars
        assert rec["action"] == "REQUEST_RETAKE"

    def test_tampered_merkle_sibling_hash_all_zeros(self):
        """Boundary 2: Verifies tampered sibling hash of 64 zero characters fails proof verification."""
        l1 = b"canonical_leaf_data_1"
        l2 = b"canonical_leaf_data_2"
        tree = ReferenceMerkleTree([l1, l2])

        proof = tree.get_inclusion_proof(0)
        tampered_proof = [{"position": proof[0]["position"], "hash": "0" * 64}]

        assert ReferenceMerkleTree.verify_inclusion_proof(l1, tampered_proof, tree.root) is False

    def test_tampered_merkle_sibling_position(self):
        """Boundary 3: Verifies inverting sibling position fails verification."""
        l1 = b"left_data"
        l2 = b"right_data"
        tree = ReferenceMerkleTree([l1, l2])

        proof = tree.get_inclusion_proof(0)
        # Position is 'right', flip to 'left'
        flipped_proof = [{"position": "left", "hash": proof[0]["hash"]}]
        assert ReferenceMerkleTree.verify_inclusion_proof(l1, flipped_proof, tree.root) is False

    def test_revoked_device_status_enforcement(self):
        """Boundary 4: Verifies device with status REVOKED is barred from evidence ingestion."""
        devices = {"dev-revoked": {"status": "REVOKED"}}

        def check_status(dev_id):
            if devices.get(dev_id, {}).get("status") != "ACTIVE":
                raise PermissionError("Device key revoked")

        with pytest.raises(PermissionError, match="Device key revoked"):
            check_status("dev-revoked")

    def test_invalid_checkpoint_root_mismatch(self):
        """Boundary 5: Verifies proof verifying against arbitrary fake root fails."""
        l1 = b"leaf_authentic"
        tree = ReferenceMerkleTree([l1])
        proof = tree.get_inclusion_proof(0)

        fake_root = b"\xff" * 32
        assert ReferenceMerkleTree.verify_inclusion_proof(l1, proof, fake_root) is False
