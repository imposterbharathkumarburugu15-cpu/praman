"""F-06: Merkle Inclusion Proof Generation Tests.
Validates generation of compact audit paths with cryptographic direction and hash metadata.
"""

import pytest
from tests_e2e.fixtures.crypto_fixtures import ReferenceMerkleTree


class TestF06ProofGeneration:
    """Verifies Merkle inclusion proof audit path generation."""

    def test_single_leaf_proof_is_empty(self):
        """Test 1: In a 1-leaf tree, proof path is empty because leaf IS the root."""
        tree = ReferenceMerkleTree([b"only_leaf"])
        proof = tree.get_inclusion_proof(0)
        assert proof == []

    def test_two_leaf_proof_directions(self):
        """Test 2: Verifies complementary directions for 2 leaves (left leaf needs right sibling, right leaf needs left sibling)."""
        tree = ReferenceMerkleTree([b"leaf_0", b"leaf_1"])

        proof_0 = tree.get_inclusion_proof(0)
        assert len(proof_0) == 1
        assert proof_0[0]["position"] == "right"
        assert proof_0[0]["hash"] == ReferenceMerkleTree.hash_leaf(b"leaf_1").hex()

        proof_1 = tree.get_inclusion_proof(1)
        assert len(proof_1) == 1
        assert proof_1[0]["position"] == "left"
        assert proof_1[0]["hash"] == ReferenceMerkleTree.hash_leaf(b"leaf_0").hex()

    def test_promoted_leaf_audit_path(self):
        """Test 3: Verifies proof path for a promoted odd leaf in a 3-leaf tree."""
        l0, l1, l2 = b"leaf_0", b"leaf_1", b"leaf_2"
        tree = ReferenceMerkleTree([l0, l1, l2])

        proof_2 = tree.get_inclusion_proof(2)
        # Promoted node has no sibling at level 0, sibling at level 1 is node01 (to its left)
        assert len(proof_2) == 1
        assert proof_2[0]["position"] == "left"

        h0 = ReferenceMerkleTree.hash_leaf(l0)
        h1 = ReferenceMerkleTree.hash_leaf(l1)
        node01 = ReferenceMerkleTree.hash_internal_node(h0, h1)
        assert proof_2[0]["hash"] == node01.hex()

    def test_four_leaf_proof_depth(self):
        """Test 4: Verifies proof length equals log2(N) in a balanced tree."""
        leaves = [b"a", b"b", b"c", b"d"]
        tree = ReferenceMerkleTree(leaves)

        for i in range(4):
            proof = tree.get_inclusion_proof(i)
            assert len(proof) == 2  # Depth is 2 for 4 leaves

    def test_out_of_bounds_leaf_index_raises(self):
        """Test 5: Verifies negative or excessive leaf indices raise IndexError."""
        tree = ReferenceMerkleTree([b"x", b"y"])
        with pytest.raises(IndexError):
            tree.get_inclusion_proof(2)

        with pytest.raises(IndexError):
            tree.get_inclusion_proof(-1)
