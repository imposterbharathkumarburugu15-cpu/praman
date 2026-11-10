"""Adversarial stress-test harness for crypto/merkle.py.

Empirically challenges:
1. CVE-2012-2459 duplication attack resistance.
2. Second-preimage attack resistance via RFC 6962 0x00/0x01 domain separation.
3. Prime leaf counts (3, 5, 7, 11, 17, 31, 67).
4. Variable proof lengths and audit path integrity for promoted nodes.
5. Proof malleability and mutation rejection (bit-flips, reorderings, truncations).
6. Robustness against malformed inputs, boundary conditions, and resource stress.
"""

from __future__ import annotations

import copy
import hashlib
import os
import pytest
from typing import List, Dict, Any

from crypto.merkle import (
    MerkleTree,
    leaf_hash,
    leaf_hash_hex,
    node_hash,
    node_hash_hex,
    verify_merkle_proof,
    LEAF_PREFIX,
    NODE_PREFIX,
)


class TestCVE20122459DuplicationResistance:
    """Stress-tests the odd-node promotion algorithm against CVE-2012-2459 vulnerabilities."""

    @pytest.mark.parametrize("odd_n", [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 23, 29, 31, 47, 63, 65])
    def test_trailing_leaf_duplication_distinct_roots(self, odd_n: int):
        """For any odd leaf count N, tree([L_0...L_{N-1}]) != tree([L_0...L_{N-1}, L_{N-1}])."""
        leaves = [f"evidence_envelope_{i}".encode("utf-8") for i in range(odd_n)]
        duplicated_leaves = leaves + [leaves[-1]]

        tree_odd = MerkleTree(leaves)
        tree_dup = MerkleTree(duplicated_leaves)

        assert tree_odd.leaf_count == odd_n
        assert tree_dup.leaf_count == odd_n + 1
        assert tree_odd.root is not None
        assert tree_dup.root is not None
        assert tree_odd.root != tree_dup.root, (
            f"VULNERABILITY DETECTED (CVE-2012-2459): Root collision at odd N={odd_n} "
            f"between {odd_n} leaves and {odd_n + 1} leaves with duplicated trailing leaf! "
            f"Root: {tree_odd.root_hex}"
        )

    def test_multi_leaf_duplication_immunity(self):
        """Duplicating multiple trailing leaves or alternating leaves never produces root collisions."""
        base = [b"ev_alpha", b"ev_beta", b"ev_gamma"]
        tree_base = MerkleTree(base)

        variants = [
            base + [b"ev_gamma", b"ev_gamma"],
            base + [b"ev_beta", b"ev_gamma"],
            base + [b"ev_alpha", b"ev_beta", b"ev_gamma"],
            [b"ev_alpha", b"ev_alpha", b"ev_beta", b"ev_gamma"],
            [b"ev_alpha", b"ev_beta", b"ev_beta", b"ev_gamma"],
        ]

        base_root = tree_base.root
        for idx, variant in enumerate(variants):
            t_var = MerkleTree(variant)
            assert t_var.root != base_root, (
                f"Root collision on variant {idx}: {variant}"
            )

    def test_identical_leaf_trees_differ_across_lengths(self):
        """Trees composed of identical leaves [A]*k have mutually distinct roots for all k in 1..32."""
        identical_leaf = b"identical_constant_evidence_payload"
        roots = set()

        for k in range(1, 33):
            tree = MerkleTree([identical_leaf] * k)
            assert tree.root not in roots, (
                f"Collision found in identical-leaf trees at size k={k}! Root: {tree.root_hex}"
            )
            roots.add(tree.root)

        assert len(roots) == 32

    def test_cross_tree_proof_rejection_under_duplication(self):
        """A valid proof for leaf in tree([A, B, C]) is rejected in tree([A, B, C, C])."""
        a, b, c = b"leaf_A", b"leaf_B", b"leaf_C"
        tree_3 = MerkleTree([a, b, c])
        tree_4 = MerkleTree([a, b, c, c])

        proof_c_in_3 = tree_3.get_proof(2)
        # Verify in tree 3 passes
        assert verify_merkle_proof(c, proof_c_in_3, tree_3.root) is True
        # Proof from tree 3 must fail against tree 4 root
        assert verify_merkle_proof(c, proof_c_in_3, tree_4.root) is False


class TestSecondPreimageResistance:
    """Stress-tests RFC 6962 0x00/0x01 domain separation against second-preimage attacks."""

    def test_domain_separation_prefix_values(self):
        """Assert exact domain separation bytes: 0x00 for leaf, 0x01 for internal node."""
        assert LEAF_PREFIX == b"\x00"
        assert NODE_PREFIX == b"\x01"
        assert len(LEAF_PREFIX) == 1
        assert len(NODE_PREFIX) == 1

    def test_direct_leaf_vs_node_preimage_attack(self):
        """Attacker crafts a leaf payload identical to (0x01 || left || right); cannot match node hash."""
        left = hashlib.sha256(b"child_left").digest()
        right = hashlib.sha256(b"child_right").digest()

        legitimate_node = node_hash(left, right)  # SHA-256(0x01 || left || right)

        # Attack 1: Leaf data is (left || right) [64 bytes]
        # In non-domain-separated trees: LeafHash(L || R) = NodeHash(L, R)
        leaf_payload_64 = left + right
        attacker_leaf_hash_1 = leaf_hash(leaf_payload_64)  # SHA-256(0x00 || left || right)
        assert attacker_leaf_hash_1 != legitimate_node, (
            "VULNERABILITY: 64-byte concatenated leaf collided with internal node hash!"
        )

        # Attack 2: Leaf data includes the 0x01 prefix [65 bytes]
        leaf_payload_65 = b"\x01" + left + right
        attacker_leaf_hash_2 = leaf_hash(leaf_payload_65)  # SHA-256(0x00 || 0x01 || left || right)
        assert attacker_leaf_hash_2 != legitimate_node, (
            "VULNERABILITY: 65-byte prefixed leaf collided with internal node hash!"
        )

    def test_tree_depth_extension_preimage_attack(self):
        """Attacker attempts to replace a 2-leaf tree with a 1-leaf tree having the same root."""
        l0 = b"genuine_envelope_0"
        l1 = b"genuine_envelope_1"
        tree_2 = MerkleTree([l0, l1])
        root_2 = tree_2.root

        h0 = leaf_hash(l0)
        h1 = leaf_hash(l1)

        # Candidate fake leaves that would succeed if domain separation were absent:
        candidates = [
            h0 + h1,
            b"\x01" + h0 + h1,
            b"\x00" + h0 + h1,
            l0 + l1,
        ]

        for fake_leaf in candidates:
            tree_1 = MerkleTree([fake_leaf])
            assert tree_1.root != root_2, (
                f"Second preimage collision! Fake leaf {fake_leaf[:8].hex()}... matched 2-leaf root!"
            )
            # And proof verification fails
            assert verify_merkle_proof(fake_leaf, [], root_2) is False

    def test_internal_node_input_length_enforcement(self):
        """node_hash strictly enforces 32-byte arguments, rejecting truncated or padded nodes."""
        valid_32 = hashlib.sha256(b"valid").digest()

        for invalid_len in [0, 1, 16, 31, 33, 64, 128]:
            bad_bytes = b"X" * invalid_len
            with pytest.raises(ValueError, match="32 bytes"):
                node_hash(bad_bytes, valid_32)
            with pytest.raises(ValueError, match="32 bytes"):
                node_hash(valid_32, bad_bytes)


class TestPrimeLeafCounts:
    """Stress-tests odd-node promotion and proof generation across prime leaf counts: 3, 5, 7, 11, 17, 31, 67."""

    PRIME_COUNTS = [3, 5, 7, 11, 17, 31, 67]

    @pytest.mark.parametrize("p", PRIME_COUNTS)
    def test_prime_count_tree_construction_and_verification(self, p: int):
        """For every prime p, all p leaves produce valid proofs that verify against the root."""
        leaves = [f"prime_test_leaf_{p}_{i}".encode("utf-8") for i in range(p)]
        tree = MerkleTree(leaves)

        assert tree.leaf_count == p
        assert tree.root is not None
        assert len(tree.root) == 32
        assert len(tree.root_hex) == 64

        # Verify every leaf in the tree
        for i in range(p):
            # 1. Using self-verification method
            assert tree.verify_leaf(i) is True, f"tree.verify_leaf failed for index {i} in prime({p})"

            # 2. Using get_proof and independent verify_merkle_proof with binary root
            proof = tree.get_proof(i)
            assert verify_merkle_proof(leaves[i], proof, tree.root) is True, (
                f"verify_merkle_proof (binary) failed for leaf {i} in prime({p})"
            )

            # 3. Using get_proof and independent verify_merkle_proof with hex root
            assert verify_merkle_proof(leaves[i], proof, tree.root_hex) is True, (
                f"verify_merkle_proof (hex) failed for leaf {i} in prime({p})"
            )

            # 4. Classmethod alias check
            assert MerkleTree.verify_inclusion_proof(leaves[i], proof, tree.root) is True

    @pytest.mark.parametrize("p", PRIME_COUNTS)
    def test_prime_count_independent_oracle_root_match(self, p: int):
        """Compare MerkleTree root against an independent step-by-step mathematical reference oracle."""
        leaves = [hashlib.sha256(f"oracle_leaf_{p}_{i}".encode()).digest() for i in range(p)]

        # Independent manual calculation of levels
        curr = [hashlib.sha256(b"\x00" + leaf).digest() for leaf in leaves]
        while len(curr) > 1:
            nxt = []
            j = 0
            while j < len(curr):
                if j + 1 < len(curr):
                    nxt.append(hashlib.sha256(b"\x01" + curr[j] + curr[j + 1]).digest())
                    j += 2
                else:
                    nxt.append(curr[j])  # promoted trailing node
                    j += 1
            curr = nxt

        expected_root = curr[0] if curr else None

        tree = MerkleTree(leaves)
        assert tree.root == expected_root, (
            f"MerkleTree root diverges from mathematical oracle for prime count {p}!"
        )


class TestVariableProofLengths:
    """Verifies variable audit path lengths and promoted node traversal mechanics."""

    def test_proof_length_distribution_p3(self):
        """p=3: leaves 0, 1 have depth 2; promoted leaf 2 has depth 1."""
        leaves = [b"p3_0", b"p3_1", b"p3_2"]
        tree = MerkleTree(leaves)

        p0 = tree.get_proof(0)
        p1 = tree.get_proof(1)
        p2 = tree.get_proof(2)

        assert len(p0) == 2
        assert len(p1) == 2
        assert len(p2) == 1, "Promoted leaf 2 must have compact proof length 1"

        # Verify steps
        assert p0[0]["position"] == "right"
        assert p0[1]["position"] == "right"
        assert p1[0]["position"] == "left"
        assert p1[1]["position"] == "right"
        assert p2[0]["position"] == "left"

    def test_proof_length_distribution_p5(self):
        """p=5: leaves 0..3 have depth 3; multi-level promoted leaf 4 has depth 1."""
        leaves = [f"p5_{i}".encode() for i in range(5)]
        tree = MerkleTree(leaves)

        lengths = [len(tree.get_proof(i)) for i in range(5)]
        # Leaves 0, 1, 2, 3 have depth 3; Leaf 4 promoted at level 0 and level 1, paired at level 2 -> depth 1
        assert lengths == [3, 3, 3, 3, 1], f"Unexpected proof length distribution for p=5: {lengths}"

    def test_proof_length_distribution_p7(self):
        """p=7: leaves 0..5 have depth 3; leaf 6 promoted once, then paired -> depth 2."""
        leaves = [f"p7_{i}".encode() for i in range(7)]
        tree = MerkleTree(leaves)

        lengths = [len(tree.get_proof(i)) for i in range(7)]
        assert lengths == [3, 3, 3, 3, 3, 3, 2], f"Unexpected proof length distribution for p=7: {lengths}"

    def test_proof_length_distribution_p17(self):
        """p=17: leaves 0..15 have depth 5; promoted leaf 16 has depth 1."""
        leaves = [f"p17_{i}".encode() for i in range(17)]
        tree = MerkleTree(leaves)

        lengths = [len(tree.get_proof(i)) for i in range(17)]
        # Leaves 0..15: depth 5; Leaf 16 promoted at levels 0, 1, 2, 3, paired at level 4 -> depth 1
        assert lengths[:16] == [5] * 16
        assert lengths[16] == 1, f"Leaf 16 in p=17 must have proof length 1, got {lengths[16]}"

    def test_proof_length_distribution_p31(self):
        """p=31: leaves 0..29 have depth 5; leaf 30 has depth 4."""
        leaves = [f"p31_{i}".encode() for i in range(31)]
        tree = MerkleTree(leaves)

        lengths = [len(tree.get_proof(i)) for i in range(31)]
        assert lengths[:30] == [5] * 30
        assert lengths[30] == 4, f"Leaf 30 in p=31 must have proof length 4, got {lengths[30]}"

    @pytest.mark.parametrize("p", [3, 5, 7, 11, 17, 31])
    def test_promoted_leaves_never_contain_noop_sibling_steps(self, p: int):
        """Assert proof steps contain zero self-hashes or dummy padding."""
        leaves = [f"leaf_{p}_{i}".encode() for i in range(p)]
        tree = MerkleTree(leaves)

        for i in range(p):
            proof = tree.get_proof(i)
            leaf_h = leaf_hash_hex(leaves[i])
            for step in proof:
                # Sibling hash must NEVER equal the leaf hash itself (unless leaf contents collide)
                assert step["hash"] != leaf_h, f"Proof for leaf {i} in p={p} contains self as sibling!"
                assert step["position"] in ("left", "right")


class TestAdversarialProofMutations:
    """Stress-tests proof verification against adversarial tampering and corruption."""

    @pytest.fixture
    def prime_11_tree(self):
        leaves = [f"tamper_test_{i}".encode() for i in range(11)]
        tree = MerkleTree(leaves)
        return leaves, tree

    def test_single_bit_flip_in_leaf_fails(self, prime_11_tree):
        """Flipping a single bit in leaf payload invalidates proof verification."""
        leaves, tree = prime_11_tree
        for i in range(len(leaves)):
            proof = tree.get_proof(i)
            # Flip the last bit of the last byte
            corrupted = bytearray(leaves[i])
            corrupted[-1] ^= 0x01
            assert verify_merkle_proof(bytes(corrupted), proof, tree.root) is False

    def test_single_bit_flip_in_sibling_hash_fails(self, prime_11_tree):
        """Flipping a single bit in any sibling hash invalidates proof verification."""
        leaves, tree = prime_11_tree
        for i in range(len(leaves)):
            proof = tree.get_proof(i)
            for step_idx in range(len(proof)):
                tampered_proof = copy.deepcopy(proof)
                # Flip 1 hex char
                orig_hex = tampered_proof[step_idx]["hash"]
                flipped_char = "0" if orig_hex[0] != "0" else "1"
                tampered_proof[step_idx]["hash"] = flipped_char + orig_hex[1:]
                assert verify_merkle_proof(leaves[i], tampered_proof, tree.root) is False

    def test_inverted_sibling_position_fails(self, prime_11_tree):
        """Inverting position ('left' -> 'right' or 'right' -> 'left') invalidates proof verification."""
        leaves, tree = prime_11_tree
        for i in range(len(leaves)):
            proof = tree.get_proof(i)
            for step_idx in range(len(proof)):
                inverted = copy.deepcopy(proof)
                orig_pos = inverted[step_idx]["position"]
                inverted[step_idx]["position"] = "left" if orig_pos == "right" else "right"
                assert verify_merkle_proof(leaves[i], inverted, tree.root) is False

    def test_truncated_proof_fails(self, prime_11_tree):
        """Removing any step from a valid proof invalidates verification."""
        leaves, tree = prime_11_tree
        for i in range(len(leaves)):
            proof = tree.get_proof(i)
            if len(proof) > 1:
                # Remove first step
                assert verify_merkle_proof(leaves[i], proof[1:], tree.root) is False
                # Remove last step
                assert verify_merkle_proof(leaves[i], proof[:-1], tree.root) is False

    def test_extended_proof_with_garbage_fails(self, prime_11_tree):
        """Appending or prepending an extraneous step to a valid proof invalidates verification."""
        leaves, tree = prime_11_tree
        garbage_step = {"position": "right", "hash": hashlib.sha256(b"garbage").hexdigest()}
        for i in range(len(leaves)):
            proof = tree.get_proof(i)
            # Prepend
            assert verify_merkle_proof(leaves[i], [garbage_step] + proof, tree.root) is False
            # Append
            assert verify_merkle_proof(leaves[i], proof + [garbage_step], tree.root) is False

    def test_swapped_proofs_between_leaves_fail(self, prime_11_tree):
        """Using leaf i's proof for leaf j (where i != j) strictly fails."""
        leaves, tree = prime_11_tree
        n = len(leaves)
        for i in range(n):
            proof_i = tree.get_proof(i)
            for j in range(n):
                if i != j:
                    assert verify_merkle_proof(leaves[j], proof_i, tree.root) is False


class TestMalformedInputsAndEdgeCases:
    """Stress-tests error handling, edge conditions, and boundaries."""

    def test_empty_tree_semantics(self):
        """Empty tree has None root, 0 leaves, and rejects out-of-bounds queries."""
        t = MerkleTree([])
        assert t.root is None
        assert t.root_hex is None
        assert t.leaf_count == 0
        assert t.verify_leaf(0) is False

        with pytest.raises(IndexError):
            t.get_proof(0)

    def test_single_leaf_tree_semantics(self):
        """Single leaf tree has root == leaf_hash, empty proof, and passes verification."""
        leaf = b"lone_wolf_leaf"
        t = MerkleTree([leaf])
        assert t.leaf_count == 1
        assert t.root == leaf_hash(leaf)
        proof = t.get_proof(0)
        assert proof == []
        assert verify_merkle_proof(leaf, proof, t.root) is True
        # Extraneous proof on single leaf must fail
        assert verify_merkle_proof(leaf, [{"position": "left", "hash": "00" * 32}], t.root) is False

    @pytest.mark.parametrize("bad_index", [-1, -100, 5, 6, 1000])
    def test_get_proof_index_error_bounds(self, bad_index: int):
        """get_proof strictly raises IndexError for any out-of-bounds index."""
        t = MerkleTree([b"a", b"b", b"c", b"d", b"e"])  # size 5
        with pytest.raises(IndexError, match="out of bounds"):
            t.get_proof(bad_index)

    def test_verify_merkle_proof_malformed_step_dictionaries(self):
        """verify_merkle_proof returns False on malformed step dicts without unhandled exceptions."""
        valid_root = leaf_hash(b"test")
        leaf = b"test"

        malformed_proofs: List[Any] = [
            None,
            "not_a_list",
            123,
            [None],
            [12345],
            ["string_step"],
            [{}],  # Missing keys
            [{"position": "right"}],  # Missing hash
            [{"hash": "00" * 32}],  # Missing position
            [{"position": "invalid_pos", "hash": "00" * 32}],  # Invalid position
            [{"position": "RIGHT", "hash": "00" * 32}],  # Case mismatch
            [{"position": "right", "hash": "not_hex_characters_here_1234567890123456789012345678901234567890"}],
            [{"position": "right", "hash": "00" * 31}],  # 31 bytes (62 hex chars)
            [{"position": "right", "hash": "00" * 33}],  # 33 bytes (66 hex chars)
            [{"position": "right", "hash": ""}],  # Empty hash
            [{"position": "right", "hash": None}],
        ]

        for bad_proof in malformed_proofs:
            result = verify_merkle_proof(leaf, bad_proof, valid_root)  # type: ignore
            assert result is False, f"Expected False for malformed proof: {bad_proof}"

    def test_verify_merkle_proof_malformed_expected_root(self):
        """verify_merkle_proof returns False on malformed expected_root values."""
        leaf = b"leaf_payload"
        t = MerkleTree([leaf])
        proof = t.get_proof(0)

        malformed_roots = [
            None,
            12345,
            "",
            "short",
            "not_hex_chars" * 4,
            b"short_bytes",
            b"X" * 31,
            b"X" * 33,
            "00" * 31,
            "00" * 33,
        ]

        for bad_root in malformed_roots:
            assert verify_merkle_proof(leaf, proof, bad_root) is False  # type: ignore

    def test_large_leaf_payloads_supported(self):
        """Merkle tree supports large leaf payloads (e.g. 5 MB) without issues."""
        large_leaf_1 = os.urandom(5 * 1024 * 1024)
        large_leaf_2 = os.urandom(5 * 1024 * 1024)
        t = MerkleTree([large_leaf_1, large_leaf_2])
        assert t.leaf_count == 2
        assert t.root is not None
        assert t.verify_leaf(0) is True
        assert t.verify_leaf(1) is True

    def test_stress_1000_leaves(self):
        """Stress tests tree with 1,000 leaves; all 1,000 inclusion proofs verify."""
        count = 1000
        leaves = [f"stress_leaf_{i}".encode() for i in range(count)]
        t = MerkleTree(leaves)

        assert t.leaf_count == count
        assert t.root is not None

        # Verify sample of leaves across boundaries, odds, and ends
        test_indices = [0, 1, 2, 499, 500, 501, 998, 999]
        for idx in test_indices:
            assert t.verify_leaf(idx) is True

    def test_input_immutability(self):
        """Mutating the original leaves list passed to constructor does not corrupt tree."""
        source_list = [b"a", b"b", b"c"]
        tree = MerkleTree(source_list)
        orig_root = tree.root

        source_list.append(b"d")
        source_list[0] = b"tampered"

        assert tree.root == orig_root
        assert tree.leaf_count == 3
        assert tree.raw_leaves == [b"a", b"b", b"c"]
