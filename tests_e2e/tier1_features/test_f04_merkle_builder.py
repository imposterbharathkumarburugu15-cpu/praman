"""F-04: Domain-Separated Merkle Tree Builder Tests.
Validates RFC 6962-style domain separation (0x00 leaf / 0x01 internal node),
deterministic root generation, and leaf ordering invariants.
"""

import hashlib
import pytest
from tests_e2e.fixtures.crypto_fixtures import ReferenceMerkleTree


class TestF04MerkleTreeBuilder:
    """Verifies domain-separated Merkle tree building mechanics."""

    def test_domain_separation_prefixes(self):
        """Test 1: Verifies 0x00 leaf prefix and 0x01 internal node prefix are strictly enforced."""
        leaf_data = b"sample_leaf_bytes"
        expected_leaf_hash = hashlib.sha256(b"\x00" + leaf_data).digest()
        assert ReferenceMerkleTree.hash_leaf(leaf_data) == expected_leaf_hash

        left = hashlib.sha256(b"left").digest()
        right = hashlib.sha256(b"right").digest()
        expected_node_hash = hashlib.sha256(b"\x01" + left + right).digest()
        assert ReferenceMerkleTree.hash_internal_node(left, right) == expected_node_hash

    def test_single_leaf_tree(self):
        """Test 2: Verifies tree with 1 leaf: root equals leaf hash."""
        leaf = b"single_evidence_record"
        tree = ReferenceMerkleTree([leaf])
        expected_root = hashlib.sha256(b"\x00" + leaf).digest()
        assert tree.root == expected_root

    def test_two_leaf_balanced_tree(self):
        """Test 3: Verifies balanced 2-leaf tree: root = H(0x01 || H(0x00||L1) || H(0x00||L2))."""
        l1, l2 = b"leaf_one", b"leaf_two"
        tree = ReferenceMerkleTree([l1, l2])

        h1 = hashlib.sha256(b"\x00" + l1).digest()
        h2 = hashlib.sha256(b"\x00" + l2).digest()
        expected_root = hashlib.sha256(b"\x01" + h1 + h2).digest()

        assert tree.root == expected_root

    def test_empty_tree_root(self):
        """Test 4: Verifies an empty tree initializes safely with None root."""
        tree = ReferenceMerkleTree([])
        assert tree.root is None
        assert tree.root_hex is None

    def test_leaf_order_sensitivity(self):
        """Test 5: Verifies that changing leaf order produces a completely different root hash."""
        leaves_a = [b"record_1", b"record_2", b"record_3", b"record_4"]
        leaves_b = [b"record_2", b"record_1", b"record_3", b"record_4"]

        tree_a = ReferenceMerkleTree(leaves_a)
        tree_b = ReferenceMerkleTree(leaves_b)

        assert tree_a.root != tree_b.root
