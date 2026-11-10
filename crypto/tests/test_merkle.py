"""Tests for Deterministic Domain-Separated Merkle Tree with odd-node promotion."""

from __future__ import annotations

import hashlib
import pytest

from crypto.merkle import (
    MerkleTree,
    leaf_hash,
    node_hash,
    verify_merkle_proof,
)


class TestMerkleTreeEngine:
    """Verifies domain separation, odd-node promotion, and inclusion proofs."""

    def test_domain_separation_prefixes(self):
        """0x00 leaf and 0x01 internal node prefixes are strictly enforced."""
        data = b"evidence_payload"
        assert leaf_hash(data) == hashlib.sha256(b"\x00" + data).digest()

        left = hashlib.sha256(b"left").digest()
        right = hashlib.sha256(b"right").digest()
        assert node_hash(left, right) == hashlib.sha256(b"\x01" + left + right).digest()

    def test_node_hash_validates_input_lengths(self):
        """node_hash requires exactly 32-byte child hashes."""
        with pytest.raises(ValueError, match="32 bytes"):
            node_hash(b"short", hashlib.sha256(b"right").digest())

        with pytest.raises(ValueError, match="32 bytes"):
            node_hash(hashlib.sha256(b"left").digest(), b"short")

    def test_single_leaf_tree(self):
        """Tree with 1 leaf: root equals leaf hash, proof is empty."""
        leaf = b"single_leaf_data"
        tree = MerkleTree([leaf])

        assert tree.leaf_count == 1
        assert tree.root == leaf_hash(leaf)
        assert tree.root_hex == leaf_hash(leaf).hex()

        proof = tree.get_proof(0)
        assert proof == []
        assert verify_merkle_proof(leaf, proof, tree.root) is True

    def test_two_leaf_balanced_tree(self):
        """Balanced 2-leaf tree: root = H(0x01 || H(0x00||L0) || H(0x00||L1))."""
        l0, l1 = b"leaf_0", b"leaf_1"
        tree = MerkleTree([l0, l1])

        h0 = leaf_hash(l0)
        h1 = leaf_hash(l1)
        expected_root = node_hash(h0, h1)

        assert tree.root == expected_root

        # Proofs for both leaves
        p0 = tree.get_proof(0)
        assert len(p0) == 1
        assert p0[0]["position"] == "right"
        assert p0[0]["hash"] == h1.hex()
        assert verify_merkle_proof(l0, p0, tree.root) is True

        p1 = tree.get_proof(1)
        assert len(p1) == 1
        assert p1[0]["position"] == "left"
        assert p1[0]["hash"] == h0.hex()
        assert verify_merkle_proof(l1, p1, tree.root) is True

    def test_three_leaves_odd_promotion(self):
        """3-leaf tree promotes leaf 2 directly to level 1 without duplication."""
        l0, l1, l2 = b"leaf_0", b"leaf_1", b"leaf_2"
        tree = MerkleTree([l0, l1, l2])

        h0 = leaf_hash(l0)
        h1 = leaf_hash(l1)
        h2 = leaf_hash(l2)

        n01 = node_hash(h0, h1)
        expected_root = node_hash(n01, h2)
        assert tree.root == expected_root

        # Leaf 0 proof: right sibling h1, then right sibling h2
        p0 = tree.get_proof(0)
        assert len(p0) == 2
        assert p0[0] == {"position": "right", "hash": h1.hex()}
        assert p0[1] == {"position": "right", "hash": h2.hex()}
        assert verify_merkle_proof(l0, p0, tree.root) is True

        # Leaf 1 proof: left sibling h0, then right sibling h2
        p1 = tree.get_proof(1)
        assert len(p1) == 2
        assert p1[0] == {"position": "left", "hash": h0.hex()}
        assert p1[1] == {"position": "right", "hash": h2.hex()}
        assert verify_merkle_proof(l1, p1, tree.root) is True

        # Leaf 2 proof: promoted! Sibling step at level 0 omitted; level 1 sibling is n01 (left)
        p2 = tree.get_proof(2)
        assert len(p2) == 1
        assert p2[0] == {"position": "left", "hash": n01.hex()}
        assert verify_merkle_proof(l2, p2, tree.root) is True

    def test_cve_2012_2459_prevention(self):
        """Immunity to Bitcoin CVE-2012-2459: tree([A, B, C]) != tree([A, B, C, C])."""
        a, b, c = b"leaf_a", b"leaf_b", b"leaf_c"
        tree_odd = MerkleTree([a, b, c])
        tree_dup = MerkleTree([a, b, c, c])

        assert tree_odd.root != tree_dup.root

    def test_five_leaves_multi_level_promotion(self):
        """5-leaf tree handles promotions across multiple levels."""
        leaves = [f"leaf_{i}".encode("utf-8") for i in range(5)]
        tree = MerkleTree(leaves)

        assert tree.leaf_count == 5
        for i in range(5):
            assert tree.verify_leaf(i) is True

    def test_empty_tree(self):
        """Empty tree initializes safely with None root."""
        tree = MerkleTree([])
        assert tree.root is None
        assert tree.root_hex is None
        assert tree.leaf_count == 0

    def test_out_of_bounds_index(self):
        """Invalid leaf indices raise IndexError."""
        tree = MerkleTree([b"a", b"b"])
        with pytest.raises(IndexError):
            tree.get_proof(2)
        with pytest.raises(IndexError):
            tree.get_proof(-1)

    def test_proof_verification_rejections(self):
        """Tampered leaf, tampered sibling, inverted direction, and tampered root are rejected."""
        leaves = [b"ev_1", b"ev_2", b"ev_3"]
        tree = MerkleTree(leaves)
        proof = tree.get_proof(0)

        # 1. Tampered leaf data
        assert verify_merkle_proof(b"tampered_ev_1", proof, tree.root) is False

        # 2. Tampered sibling hash
        tampered_proof = [dict(s) for s in proof]
        tampered_proof[0]["hash"] = "0" * 64
        assert verify_merkle_proof(leaves[0], tampered_proof, tree.root) is False

        # 3. Inverted sibling position
        inverted_proof = [dict(s) for s in proof]
        inverted_proof[0]["position"] = "left"  # was right
        assert verify_merkle_proof(leaves[0], inverted_proof, tree.root) is False

        # 4. Tampered root
        fake_root = b"\xff" * 32
        assert verify_merkle_proof(leaves[0], proof, fake_root) is False

    def test_second_preimage_resistance(self):
        """Internal node preimages (0x01 || L || R) cannot be verified as leaves."""
        l0, l1 = b"leaf_0", b"leaf_1"
        tree = MerkleTree([l0, l1])
        h0 = leaf_hash(l0)
        h1 = leaf_hash(l1)

        # Adversary crafts leaf payload = 0x01 || h0 || h1
        fake_leaf = b"\x01" + h0 + h1
        # In a 1-leaf tree, root = H(0x00 || fake_leaf)
        # In the 2-leaf tree, root = H(0x01 || h0 || h1)
        # Because of 0x00 prefix on leaves, these cannot collide
        fake_leaf_hash = leaf_hash(fake_leaf)
        assert fake_leaf_hash != tree.root
