"""F-43: Merkle Ledger Batching & Anchor Engine Tests.
Validates periodic batching of approved evidence records into Merkle trees,
root calculation, local anchor log creation, and ledger status transitions.
"""

import hashlib
import uuid
from datetime import datetime, timezone
import pytest
from tests_e2e.fixtures.crypto_fixtures import ReferenceMerkleTree, rfc8785_canonicalize
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory


class MerkleBatchEngine:
    """Batching engine committing approved evidence to ledger anchor records."""

    def __init__(self):
        self.ledger_anchors = []

    def commit_batch(self, approved_envelopes: list) -> dict:
        if not approved_envelopes:
            raise ValueError("Cannot anchor an empty batch")

        # Compute canonical leaf bytes
        canonical_leaves = [rfc8785_canonicalize(env) for env in approved_envelopes]
        tree = ReferenceMerkleTree(canonical_leaves)

        batch_id = f"batch-{uuid.uuid4()}"
        anchor = {
            "batch_id": batch_id,
            "merkle_root": tree.root_hex,
            "leaf_count": len(approved_envelopes),
            "evidence_ids": [env["evidence_id"] for env in approved_envelopes],
            "anchored_at": datetime.now(timezone.utc).isoformat(),
            "status": "COMMITTED_TO_LEDGER",
        }
        self.ledger_anchors.append(anchor)
        return {"anchor": anchor, "tree": tree}


class TestF43MerkleBatchAnchor:
    """Verifies Merkle batching and local ledger anchoring."""

    def test_commit_single_record_batch(self):
        """Test 1: Verifies anchoring a batch with 1 approved record."""
        engine = MerkleBatchEngine()
        env = EnvelopeFactory.create_valid_envelope()

        res = engine.commit_batch([env])
        anchor = res["anchor"]
        assert anchor["leaf_count"] == 1
        assert anchor["status"] == "COMMITTED_TO_LEDGER"
        assert len(anchor["merkle_root"]) == 64

    def test_commit_multi_record_batch(self):
        """Test 2: Verifies anchoring a batch with 4 records builds valid tree with 4 leaves."""
        engine = MerkleBatchEngine()
        envelopes = [
            EnvelopeFactory.create_valid_envelope(sequence_number=i + 1)
            for i in range(4)
        ]

        res = engine.commit_batch(envelopes)
        tree = res["tree"]
        assert len(tree.raw_leaves) == 4
        assert res["anchor"]["leaf_count"] == 4

    def test_empty_batch_rejected(self):
        """Test 3: Verifies attempting to anchor an empty batch raises ValueError."""
        engine = MerkleBatchEngine()
        with pytest.raises(ValueError, match="Cannot anchor an empty batch"):
            engine.commit_batch([])

    def test_batch_root_matches_inclusion_proof_root(self):
        """Test 4: Verifies generated inclusion proof against the anchor's root."""
        engine = MerkleBatchEngine()
        envelopes = [
            EnvelopeFactory.create_valid_envelope(sequence_number=i + 1)
            for i in range(3)  # Odd leaf count
        ]

        res = engine.commit_batch(envelopes)
        tree = res["tree"]
        root_bytes = bytes.fromhex(res["anchor"]["merkle_root"])

        for idx, env in enumerate(envelopes):
            canonical = rfc8785_canonicalize(env)
            proof = tree.get_inclusion_proof(idx)
            assert ReferenceMerkleTree.verify_inclusion_proof(canonical, proof, root_bytes) is True

    def test_ledger_anchor_append_log(self):
        """Test 5: Verifies successive batches append sequentially to local ledger logs."""
        engine = MerkleBatchEngine()
        b1 = engine.commit_batch([EnvelopeFactory.create_valid_envelope()])
        b2 = engine.commit_batch([EnvelopeFactory.create_valid_envelope()])

        assert len(engine.ledger_anchors) == 2
        assert engine.ledger_anchors[0]["batch_id"] != engine.ledger_anchors[1]["batch_id"]
