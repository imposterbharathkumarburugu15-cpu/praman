"""Mathematical test vectors for PRAMAN cryptographic layer.

Verifies exact bit-for-bit values against the specification documents.
"""

from __future__ import annotations

from crypto.ecdsa_p256 import load_public_key, verify
from crypto.envelope import EvidenceEnvelope
from crypto.merkle import MerkleTree, leaf_hash, verify_merkle_proof


class TestCanonicalVectors:
    """Exact value assertions for the 4 canonical test vectors from PROJECT.md & explorer reports."""

    LEAF_0_PAYLOAD = b"evidence_envelope_1"
    LEAF_1_PAYLOAD = b"evidence_envelope_2"
    LEAF_2_PAYLOAD = b"evidence_envelope_3"

    EXPECTED_L0_HASH = (
        "35bcc2f603818ea42e4213a4c9fb85db54fc6d5d40f45f517fcaf04b8f21e969"
    )
    EXPECTED_L1_HASH = (
        "0e8b4e899adba19850ff846bd49fde7cf8307d57721d414ec9d0720ab8a25d7f"
    )
    EXPECTED_L2_HASH = (
        "fc0e16c3f4c21535f95fdf143e9d882493db18b7d4909e32be252b7959c7645e"
    )

    EXPECTED_ROOT_2 = "d2338166dc37c5477a662f2700e0ac1bf58959b3ab9b442be01e0a529dac051e"
    EXPECTED_ROOT_3 = "de3e56028a272050e81d4bd6a1118946e8b1a9e53651301ff39dde8f1e287118"

    def test_vector_1_single_leaf(self):
        """Canonical Vector 1: 1 leaf tree produces exact root and empty proof."""
        tree = MerkleTree([self.LEAF_0_PAYLOAD])
        assert leaf_hash(self.LEAF_0_PAYLOAD).hex() == self.EXPECTED_L0_HASH
        assert tree.root_hex == self.EXPECTED_L0_HASH

        proof = tree.get_proof(0)
        assert proof == []
        assert verify_merkle_proof(self.LEAF_0_PAYLOAD, proof, tree.root) is True

    def test_vector_2_two_leaves(self):
        """Canonical Vector 2: 2 leaves balanced tree produces exact root and proofs."""
        tree = MerkleTree([self.LEAF_0_PAYLOAD, self.LEAF_1_PAYLOAD])

        assert leaf_hash(self.LEAF_0_PAYLOAD).hex() == self.EXPECTED_L0_HASH
        assert leaf_hash(self.LEAF_1_PAYLOAD).hex() == self.EXPECTED_L1_HASH
        assert tree.root_hex == self.EXPECTED_ROOT_2

        # Proof for Leaf 0
        p0 = tree.get_proof(0)
        assert len(p0) == 1
        assert p0[0] == {"position": "right", "hash": self.EXPECTED_L1_HASH}
        assert (
            verify_merkle_proof(self.LEAF_0_PAYLOAD, p0, self.EXPECTED_ROOT_2) is True
        )

        # Proof for Leaf 1
        p1 = tree.get_proof(1)
        assert len(p1) == 1
        assert p1[0] == {"position": "left", "hash": self.EXPECTED_L0_HASH}
        assert (
            verify_merkle_proof(self.LEAF_1_PAYLOAD, p1, self.EXPECTED_ROOT_2) is True
        )

    def test_vector_3_three_leaves_odd_promotion(self):
        """Canonical Vector 3: 3 leaves tree with odd-node promotion produces exact root and proofs."""
        tree = MerkleTree(
            [self.LEAF_0_PAYLOAD, self.LEAF_1_PAYLOAD, self.LEAF_2_PAYLOAD]
        )

        assert leaf_hash(self.LEAF_2_PAYLOAD).hex() == self.EXPECTED_L2_HASH
        assert tree.root_hex == self.EXPECTED_ROOT_3

        # Promoted leaf 2 has exactly 1 step
        p2 = tree.get_proof(2)
        assert len(p2) == 1
        assert p2[0] == {"position": "left", "hash": self.EXPECTED_ROOT_2}
        assert (
            verify_merkle_proof(self.LEAF_2_PAYLOAD, p2, self.EXPECTED_ROOT_3) is True
        )

        # Leaf 0 and 1 have 2 steps
        p0 = tree.get_proof(0)
        assert len(p0) == 2
        assert p0[0] == {"position": "right", "hash": self.EXPECTED_L1_HASH}
        assert p0[1] == {"position": "right", "hash": self.EXPECTED_L2_HASH}
        assert (
            verify_merkle_proof(self.LEAF_0_PAYLOAD, p0, self.EXPECTED_ROOT_3) is True
        )

        p1 = tree.get_proof(1)
        assert len(p1) == 2
        assert p1[0] == {"position": "left", "hash": self.EXPECTED_L0_HASH}
        assert p1[1] == {"position": "right", "hash": self.EXPECTED_L2_HASH}
        assert (
            verify_merkle_proof(self.LEAF_1_PAYLOAD, p1, self.EXPECTED_ROOT_3) is True
        )

    def test_vector_4_tampered_leaves(self):
        """Canonical Vector 4: Tampered variations strictly rejected."""
        tree = MerkleTree(
            [self.LEAF_0_PAYLOAD, self.LEAF_1_PAYLOAD, self.LEAF_2_PAYLOAD]
        )
        proof_0 = tree.get_proof(0)

        # 1. Tampered payload
        tampered_payload = b"evidence_envelope_1_tampered"
        assert (
            verify_merkle_proof(tampered_payload, proof_0, self.EXPECTED_ROOT_3)
            is False
        )

        # 2. Tampered sibling hash
        tampered_proof = [dict(s) for s in proof_0]
        tampered_proof[0]["hash"] = "ff" * 32
        assert (
            verify_merkle_proof(
                self.LEAF_0_PAYLOAD, tampered_proof, self.EXPECTED_ROOT_3
            )
            is False
        )

        # 3. Tampered position
        inverted_proof = [dict(s) for s in proof_0]
        inverted_proof[0]["position"] = "left"
        assert (
            verify_merkle_proof(
                self.LEAF_0_PAYLOAD, inverted_proof, self.EXPECTED_ROOT_3
            )
            is False
        )

        # 4. Tampered root
        fake_root = "00" * 32
        assert verify_merkle_proof(self.LEAF_0_PAYLOAD, proof_0, fake_root) is False

    def test_contract_1_normative_envelope(self, contract1_envelope_dict):
        """Verifies bit-for-bit exact SHA-256 digests for Contract 1 envelope."""
        env = EvidenceEnvelope.from_dict(contract1_envelope_dict)
        canonical_bytes = env.to_canonical_bytes()
        assert len(canonical_bytes) == 454

        expected_env_sha = (
            "4ae6016abc79b01e20841a7614d8bfc9b045c39113dd4cad1da070969a0679c7"
        )
        assert env.to_canonical_sha256() == expected_env_sha

        expected_leaf_hash = (
            "9cd6c507a6ee7936744d31212a5fac6f808a1b041ea923b2bf33d31022af04f0"
        )
        assert env.to_merkle_leaf_hash_hex() == expected_leaf_hash

    def test_known_keypair_and_signature_vector(self, contract1_envelope_dict):
        """Verifies deterministic P-256 public key and signature vector from explorer_m1_2."""
        spki_pem = (
            "-----BEGIN PUBLIC KEY-----\n"
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE2M0S6lxn8vigDBEkiT7c+mdUxNbO\n"
            "3mvhO98ilcgQqX+lqJ0tKjYMDKmk1sfJ7Uso0+GZ1mJ/LmltaJwxClsPSA==\n"
            "-----END PUBLIC KEY-----\n"
        )
        pub_key = load_public_key(spki_pem)

        der_b64_sig = "MEQCIG1gt2O+ZEZepEg2e49+76Hz7SGVH2iQCuaTETDvLB5tAiBi8O0PpmY3nXWl1CoGXZQQyL8k7iRP4l0jpEG6dxnLig=="
        env = EvidenceEnvelope.from_dict(contract1_envelope_dict)

        # Verify signature over canonical envelope bytes
        assert verify(pub_key, der_b64_sig, env.to_canonical_bytes()) is True
