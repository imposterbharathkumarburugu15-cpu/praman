"""F-07: Merkle Inclusion Proof Verification Tests.
Validates independent verification of inclusion proofs against root hashes,
including the 4 canonical test vectors (1 leaf, 2 leaves, odd count, tampered).
"""

import pytest
from tests_e2e.fixtures.crypto_fixtures import ReferenceMerkleTree


class TestF07ProofVerification:
    """Verifies Merkle inclusion proof verification against expected root."""

    def test_canonical_vector_1_single_leaf(self):
        """Canonical Vector 1: Verifies 1-leaf inclusion proof against root."""
        leaf = b"CANONICAL_LEAF_1"
        tree = ReferenceMerkleTree([leaf])
        proof = tree.get_inclusion_proof(0)

        assert ReferenceMerkleTree.verify_inclusion_proof(leaf, proof, tree.root) is True

    def test_canonical_vector_2_two_leaves(self):
        """Canonical Vector 2: Verifies balanced 2-leaf inclusion proofs."""
        leaves = [b"CANONICAL_LEAF_A", b"CANONICAL_LEAF_B"]
        tree = ReferenceMerkleTree(leaves)

        for idx, leaf in enumerate(leaves):
            proof = tree.get_inclusion_proof(idx)
            assert ReferenceMerkleTree.verify_inclusion_proof(leaf, proof, tree.root) is True

    def test_canonical_vector_3_odd_count_leaves(self):
        """Canonical Vector 3: Verifies inclusion proofs for odd leaf counts (3 and 5 leaves)."""
        leaves_3 = [b"odd_leaf_1", b"odd_leaf_2", b"odd_leaf_3"]
        tree_3 = ReferenceMerkleTree(leaves_3)
        for idx, leaf in enumerate(leaves_3):
            proof = tree_3.get_inclusion_proof(idx)
            assert ReferenceMerkleTree.verify_inclusion_proof(leaf, proof, tree_3.root) is True

        leaves_5 = [f"odd_5_{i}".encode("utf-8") for i in range(5)]
        tree_5 = ReferenceMerkleTree(leaves_5)
        for idx, leaf in enumerate(leaves_5):
            proof = tree_5.get_inclusion_proof(idx)
            assert ReferenceMerkleTree.verify_inclusion_proof(leaf, proof, tree_5.root) is True

    def test_canonical_vector_4_tampered_leaf_rejection(self):
        """Canonical Vector 4: Verifies rejection when leaf data or sibling hash is tampered."""
        leaves = [b"authentic_1", b"authentic_2", b"authentic_3"]
        tree = ReferenceMerkleTree(leaves)
        proof = tree.get_inclusion_proof(1)

        # Tampered leaf data
        assert ReferenceMerkleTree.verify_inclusion_proof(b"tampered_1", proof, tree.root) is False

        # Tampered proof sibling
        tampered_proof = [dict(step) for step in proof]
        tampered_proof[0]["hash"] = "0" * 64
        assert ReferenceMerkleTree.verify_inclusion_proof(leaves[1], tampered_proof, tree.root) is False

    def test_position_inversion_rejection(self):
        """Test 5: Verifies that inverting sibling position ('left' -> 'right') fails verification."""
        leaves = [b"pos_leaf_0", b"pos_leaf_1"]
        tree = ReferenceMerkleTree(leaves)
        proof_0 = tree.get_inclusion_proof(0)

        inverted_proof = [{"position": "left", "hash": proof_0[0]["hash"]}]
        assert ReferenceMerkleTree.verify_inclusion_proof(leaves[0], inverted_proof, tree.root) is False
