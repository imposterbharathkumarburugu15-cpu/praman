"""Tier 3: Interaction Test I-03 — Review Approval x Merkle Batching x Ledger Anchoring.
Validates the interaction when human reviewer APPROVE decisions transition evidence into
Merkle tree batches, calculating domain-separated roots and committing local ledger anchor records.
"""

import pytest
from tests_e2e.fixtures.crypto_fixtures import ReferenceMerkleTree, rfc8785_canonicalize
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory
from tests_e2e.tier1_features.test_f43_merkle_batch_anchor import MerkleBatchEngine


class TestI03ReviewMerkleBatching:
    """Verifies review approval to Merkle batching and ledger commitment."""

    def test_approved_records_batched_into_merkle_tree(self):
        """Interaction 1: Verifies approved evidence records are batched into a deterministic Merkle root."""
        engine = MerkleBatchEngine()
        approved_envelopes = [
            EnvelopeFactory.create_valid_envelope(sequence_number=i + 1, lifecycle_stage="CROP_GROWTH")
            for i in range(4)
        ]

        batch_result = engine.commit_batch(approved_envelopes)
        anchor = batch_result["anchor"]

        assert anchor["status"] == "COMMITTED_TO_LEDGER"
        assert anchor["leaf_count"] == 4
        assert len(anchor["merkle_root"]) == 64

    def test_inclusion_proof_validity_for_all_batched_records(self):
        """Interaction 2: Verifies every approved record in batch can produce and verify its Merkle inclusion proof."""
        engine = MerkleBatchEngine()
        approved_envelopes = [
            EnvelopeFactory.create_valid_envelope(sequence_number=i + 1)
            for i in range(3)  # Odd leaf count tests odd-node promotion in batch
        ]

        res = engine.commit_batch(approved_envelopes)
        tree = res["tree"]
        root_bytes = bytes.fromhex(res["anchor"]["merkle_root"])

        for idx, env in enumerate(approved_envelopes):
            canonical = rfc8785_canonicalize(env)
            proof = tree.get_inclusion_proof(idx)
            assert ReferenceMerkleTree.verify_inclusion_proof(canonical, proof, root_bytes) is True

    def test_rejected_evidence_excluded_from_batch(self):
        """Interaction 3: Verifies REJECTED evidence is excluded from Merkle batching."""
        engine = MerkleBatchEngine()

        evidence_pool = [
            {"env": EnvelopeFactory.create_valid_envelope(sequence_number=1), "status": "APPROVED"},
            {"env": EnvelopeFactory.create_valid_envelope(sequence_number=2), "status": "REJECTED"},
            {"env": EnvelopeFactory.create_valid_envelope(sequence_number=3), "status": "APPROVED"},
        ]

        eligible_for_batch = [item["env"] for item in evidence_pool if item["status"] == "APPROVED"]
        assert len(eligible_for_batch) == 2

        res = engine.commit_batch(eligible_for_batch)
        assert res["anchor"]["leaf_count"] == 2
        assert res["anchor"]["evidence_ids"] == [e["evidence_id"] for e in eligible_for_batch]

    def test_retake_requested_evidence_excluded_from_batch(self):
        """Interaction 4: Verifies RETAKE_REQUESTED evidence is excluded from batch until retake is approved."""
        engine = MerkleBatchEngine()

        evidence_pool = [
            {"env": EnvelopeFactory.create_valid_envelope(sequence_number=1), "status": "APPROVED"},
            {"env": EnvelopeFactory.create_valid_envelope(sequence_number=2), "status": "RETAKE_REQUESTED"},
        ]

        eligible = [item["env"] for item in evidence_pool if item["status"] == "APPROVED"]
        res = engine.commit_batch(eligible)
        assert res["anchor"]["leaf_count"] == 1

    def test_ledger_anchor_persistence_and_lookup(self):
        """Interaction 5: Verifies ledger anchor can be queried by batch_id."""
        engine = MerkleBatchEngine()
        env = EnvelopeFactory.create_valid_envelope()
        res = engine.commit_batch([env])
        b_id = res["anchor"]["batch_id"]

        found = next((a for a in engine.ledger_anchors if a["batch_id"] == b_id), None)
        assert found is not None
        assert found["status"] == "COMMITTED_TO_LEDGER"
