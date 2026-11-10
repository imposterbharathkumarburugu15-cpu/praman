"""ADV-05: Merkle Tree & Authority Checkpoint Tampering Adversarial Tests.
Verifies resistance against:
1. CVE-2012-2459 Duplicate Leaf Injection (odd-node promotion prevents 64-byte collision attacks).
2. Domain Separation Preimage Collisions (0x00 leaf prefix vs 0x01 node prefix).
3. Inclusion proof tampering (altered sibling hashes, inverted step positions).
4. Inclusion proof truncation and dummy step inflation.
5. Authority checkpoint payload tampering (merkle_root, timestamp, leaf_count alterations).
6. Rogue checkpoint authority key substitution attacks.
"""

import copy
import hashlib
import pytest
from crypto.merkle import (
    MerkleTree,
    leaf_hash,
    node_hash,
    verify_merkle_proof,
)
from crypto.authority import (
    create_signed_checkpoint,
    verify_checkpoint_signature,
    get_authority_public_key_pem,
    sign_checkpoint,
)
from crypto.ecdsa_p256 import generate_keypair, public_key_to_pem


class TestAdv05MerkleCheckpointTampering:
    """Adversarial test suite for Merkle trees, proofs, and authority checkpoints."""

    def test_cve_2012_2459_duplicate_leaf_attack_blocked_by_odd_node_promotion(self):
        """ADV-05.1: Odd-node promotion prevents Bitcoin CVE-2012-2459 duplicate leaf collision."""
        leaf1 = b"Evidence Payload 1"
        leaf2 = b"Evidence Payload 2"
        leaf3 = b"Evidence Payload 3"

        # 3-leaf tree with odd-node promotion: leaf3 is promoted directly
        tree_odd = MerkleTree([leaf1, leaf2, leaf3])

        # Adversary constructs a 4-leaf tree duplicating leaf3 to create an artificial power of 2
        tree_duplicated = MerkleTree([leaf1, leaf2, leaf3, leaf3])

        # In vulnerable implementations (like early Bitcoin), both trees produced the identical root!
        # In PRAMAN, odd-node promotion ensures roots are completely DIFFERENT:
        assert tree_odd.root_hex != tree_duplicated.root_hex, (
            "VULNERABILITY: 3-leaf tree and duplicated 4-leaf tree collided on root hash!"
        )

        # Inclusion proof for leaf3 in tree_odd must NOT verify against tree_duplicated root
        proof_odd = tree_odd.get_inclusion_proof(2)
        assert verify_merkle_proof(leaf3, proof_odd, tree_duplicated.root_hex) is False

    def test_domain_separation_prevents_internal_node_preimage_collision(self):
        """ADV-05.2: Domain separation prefix (0x00 vs 0x01) prevents leaf/node collision attacks."""
        left = hashlib.sha256(b"left").digest()
        right = hashlib.sha256(b"right").digest()

        # Legitimate internal node hash: SHA-256(0x01 || left || right)
        legit_internal_node = node_hash(left, right)

        # Adversary injects a leaf whose data payload is exactly (left || right)
        colliding_leaf_payload = left + right
        attacker_leaf_hash = leaf_hash(colliding_leaf_payload)

        # Domain separation guarantees these hashes are completely distinct
        assert legit_internal_node != attacker_leaf_hash, (
            "VULNERABILITY: Internal node hash collided with raw concatenated leaf hash!"
        )

    def test_tampered_proof_sibling_hash_fails_verification(self):
        """ADV-05.3: 1-bit alteration in an inclusion proof sibling hash is rejected."""
        leaves = [b"ev_A", b"ev_B", b"ev_C", b"ev_D"]
        tree = MerkleTree(leaves)

        proof = tree.get_inclusion_proof(0)
        assert len(proof) > 0

        # Verify legitimate proof passes
        assert verify_merkle_proof(leaves[0], proof, tree.root_hex) is True

        # Adversary tampers with the sibling hash in the first step
        tampered_proof = copy.deepcopy(proof)
        first_hash = bytearray.fromhex(tampered_proof[0]["hash"])
        first_hash[0] ^= 0x01  # Flip 1 bit
        tampered_proof[0]["hash"] = first_hash.hex()

        assert verify_merkle_proof(leaves[0], tampered_proof, tree.root_hex) is False

    def test_tampered_proof_position_fails_verification(self):
        """ADV-05.4: Inverting proof step position (left -> right) is rejected."""
        leaves = [b"leaf_alpha", b"leaf_beta", b"leaf_gamma", b"leaf_delta"]
        tree = MerkleTree(leaves)

        proof = tree.get_inclusion_proof(1)  # leaf_beta (right sibling to leaf_alpha)
        assert verify_merkle_proof(leaves[1], proof, tree.root_hex) is True

        # Invert step position
        tampered_proof = copy.deepcopy(proof)
        orig_pos = tampered_proof[0]["position"]
        tampered_proof[0]["position"] = "right" if orig_pos == "left" else "left"

        assert verify_merkle_proof(leaves[1], tampered_proof, tree.root_hex) is False

    def test_truncated_and_padded_proof_steps_fail_verification(self):
        """ADV-05.5: Truncating proof steps or appending spurious dummy steps is rejected."""
        leaves = [b"leaf_1", b"leaf_2", b"leaf_3", b"leaf_4", b"leaf_5"]
        tree = MerkleTree(leaves)
        proof = tree.get_inclusion_proof(0)

        # Truncated proof
        truncated_proof = proof[:-1]
        assert verify_merkle_proof(leaves[0], truncated_proof, tree.root_hex) is False

        # Spurious inflated proof step
        padded_proof = copy.deepcopy(proof)
        padded_proof.append({"position": "left", "hash": "00" * 32})
        assert verify_merkle_proof(leaves[0], padded_proof, tree.root_hex) is False

    def test_authority_checkpoint_payload_tampering_fails_signature(self):
        """ADV-05.6: Any alteration to merkle_root, timestamp, or leaf_count invalidates checkpoint signature."""
        checkpoint = create_signed_checkpoint(
            checkpoint_id="cp-test-001",
            merkle_root="aa" * 32,
            leaf_count=42,
            authority_id="praman-root-authority-1",
        )
        assert verify_checkpoint_signature(checkpoint) is True

        # Tamper 1: Alter merkle_root
        cp_tampered_root = copy.deepcopy(checkpoint)
        cp_tampered_root["merkle_root"] = "bb" * 32
        assert verify_checkpoint_signature(cp_tampered_root) is False

        # Tamper 2: Alter timestamp
        cp_tampered_time = copy.deepcopy(checkpoint)
        cp_tampered_time["timestamp"] = "2020-01-01T00:00:00Z"
        assert verify_checkpoint_signature(cp_tampered_time) is False

        # Tamper 3: Alter leaf_count
        cp_tampered_count = copy.deepcopy(checkpoint)
        cp_tampered_count["leaf_count"] = 999
        assert verify_checkpoint_signature(cp_tampered_count) is False

    def test_rogue_authority_key_substitution_rejected(self):
        """ADV-05.7: Checkpoint signed with rogue private key fails verification against trusted authority public key."""
        rogue_priv, rogue_pub = generate_keypair()
        checkpoint = {
            "checkpoint_id": "cp-rogue-001",
            "merkle_root": "cc" * 32,
            "leaf_count": 10,
            "timestamp": "2026-11-09T18:00:00Z",
            "authority_id": "praman-root-authority-1",
        }
        # Rogue signs with own key
        rogue_sig = sign_checkpoint(checkpoint, private_key=rogue_priv)
        checkpoint["signature"] = rogue_sig

        # Verified against genuine Authority Public Key
        trusted_pub_pem = get_authority_public_key_pem()
        assert verify_checkpoint_signature(checkpoint, authority_pub_pem=trusted_pub_pem) is False
