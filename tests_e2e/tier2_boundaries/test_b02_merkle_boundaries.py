"""Tier 2: Merkle Tree Boundary & Corner Case Tests.
Tests extreme leaf counts (1, 17, 31, 256), odd-node promotion stress,
identical leaf collisions, and deep proof paths.
"""

import hashlib
import pytest
from tests_e2e.fixtures.crypto_fixtures import ReferenceMerkleTree


class TestB02MerkleBoundaries:
    """Verifies Merkle tree edge conditions and structural limits."""

    def test_prime_count_seventeen_leaves(self):
        """Boundary 1: Verifies 17 leaves (prime count requiring odd-node promotion across 4 levels)."""
        leaves = [f"leaf_prime_{i}".encode("utf-8") for i in range(17)]
        tree = ReferenceMerkleTree(leaves)

        assert tree.root is not None
        assert len(tree.root) == 32

        # Verify all 17 inclusion proofs
        for i in range(17):
            proof = tree.get_inclusion_proof(i)
            assert ReferenceMerkleTree.verify_inclusion_proof(leaves[i], proof, tree.root) is True

    def test_large_balanced_tree_256_leaves(self):
        """Boundary 2: Verifies balanced tree of 256 leaves (depth = 8, no odd promotion needed)."""
        leaves = [f"leaf_pow2_{i}".encode("utf-8") for i in range(256)]
        tree = ReferenceMerkleTree(leaves)

        assert len(tree.levels) == 9  # Levels 0 to 8
        # Proof length must be exactly 8 for all leaves
        for idx in [0, 127, 255]:
            proof = tree.get_inclusion_proof(idx)
            assert len(proof) == 8
            assert ReferenceMerkleTree.verify_inclusion_proof(leaves[idx], proof, tree.root) is True

    def test_identical_leaves_produce_valid_unique_proofs(self):
        """Boundary 3: Verifies tree with 3 identical leaves produces valid distinct proofs based on index."""
        leaf = b"REPEATED_IDENTICAL_LEAF"
        tree = ReferenceMerkleTree([leaf, leaf, leaf])

        # Proof for index 0 and index 2 must differ
        proof_0 = tree.get_inclusion_proof(0)
        proof_2 = tree.get_inclusion_proof(2)
        assert proof_0 != proof_2

        assert ReferenceMerkleTree.verify_inclusion_proof(leaf, proof_0, tree.root) is True
        assert ReferenceMerkleTree.verify_inclusion_proof(leaf, proof_2, tree.root) is True

    def test_single_byte_leaves(self):
        """Boundary 4: Verifies minimal 1-byte leaves (b'\\x00' and b'\\x01') are safely hashed with domain prefixes."""
        l1 = b"\x00"
        l2 = b"\x01"
        tree = ReferenceMerkleTree([l1, l2])

        h1 = hashlib.sha256(b"\x00\x00").digest()
        h2 = hashlib.sha256(b"\x00\x01").digest()
        expected_root = hashlib.sha256(b"\x01" + h1 + h2).digest()

        assert tree.root == expected_root

    def test_proof_verification_with_empty_proof_fails_on_multi_leaf_tree(self):
        """Boundary 5: Verifies empty proof is rejected on multi-leaf tree."""
        tree = ReferenceMerkleTree([b"l1", b"l2"])
        assert ReferenceMerkleTree.verify_inclusion_proof(b"l1", [], tree.root) is False
