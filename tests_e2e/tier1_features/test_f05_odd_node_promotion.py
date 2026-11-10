"""F-05: Odd-Node Promotion Algorithm Tests.
Validates the promotion of unpaired odd nodes at level boundaries,
explicitly preventing the CVE-2012-2459 leaf-duplication vulnerability.
"""

import hashlib
import pytest
from tests_e2e.fixtures.crypto_fixtures import ReferenceMerkleTree


class TestF05OddNodePromotion:
    """Verifies that odd trailing nodes are promoted without duplication."""

    def test_three_leaves_promotion_structure(self):
        """Test 1: Verifies 3-leaf tree promotes leaf 2 to level 1 without duplication."""
        l0, l1, l2 = b"leaf_0", b"leaf_1", b"leaf_2"
        tree = ReferenceMerkleTree([l0, l1, l2])

        h0 = ReferenceMerkleTree.hash_leaf(l0)
        h1 = ReferenceMerkleTree.hash_leaf(l1)
        h2 = ReferenceMerkleTree.hash_leaf(l2)

        # Level 1 has pair (h0, h1) -> node01, and promoted h2
        node01 = ReferenceMerkleTree.hash_internal_node(h0, h1)
        expected_root = ReferenceMerkleTree.hash_internal_node(node01, h2)

        assert tree.root == expected_root

    def test_cve_2012_2459_leaf_duplication_resistance(self):
        """Test 2: Verifies tree([A, B, C]) != tree([A, B, C, C]) (CVE-2012-2459 prevention)."""
        a, b, c = b"leaf_A", b"leaf_B", b"leaf_C"
        tree_odd = ReferenceMerkleTree([a, b, c])
        tree_duplicated = ReferenceMerkleTree([a, b, c, c])

        assert tree_odd.root != tree_duplicated.root

    def test_five_leaves_multi_level_promotion(self):
        """Test 3: Verifies 5-leaf tree handles promotions across multiple levels."""
        leaves = [f"leaf_{i}".encode("utf-8") for i in range(5)]
        tree = ReferenceMerkleTree(leaves)

        # Level 0 has 5 nodes (0,1,2,3,4)
        h = [ReferenceMerkleTree.hash_leaf(leaf) for leaf in leaves]
        # Level 1: pair(0,1), pair(2,3), promote(4) -> 3 nodes
        n01 = ReferenceMerkleTree.hash_internal_node(h[0], h[1])
        n23 = ReferenceMerkleTree.hash_internal_node(h[2], h[3])
        n4 = h[4]
        # Level 2: pair(n01, n23), promote(n4) -> 2 nodes
        n0123 = ReferenceMerkleTree.hash_internal_node(n01, n23)
        # Root: pair(n0123, n4)
        expected_root = ReferenceMerkleTree.hash_internal_node(n0123, n4)

        assert tree.root == expected_root

    def test_seven_leaves_odd_promotion(self):
        """Test 4: Verifies 7-leaf tree with multiple odd levels resolves correctly."""
        leaves = [f"node_{i}".encode("utf-8") for i in range(7)]
        tree = ReferenceMerkleTree(leaves)
        assert tree.root is not None
        assert len(tree.root) == 32

    def test_even_count_no_promotion_needed(self):
        """Test 5: Verifies that even node count (4 leaves) forms a strictly balanced binary tree."""
        leaves = [b"ev_1", b"ev_2", b"ev_3", b"ev_4"]
        tree = ReferenceMerkleTree(leaves)

        h = [ReferenceMerkleTree.hash_leaf(l) for l in leaves]
        n01 = ReferenceMerkleTree.hash_internal_node(h[0], h[1])
        n23 = ReferenceMerkleTree.hash_internal_node(h[2], h[3])
        expected_root = ReferenceMerkleTree.hash_internal_node(n01, n23)

        assert tree.root == expected_root
        assert len(tree.levels) == 3  # Level 0 (4), Level 1 (2), Level 2 (1)
