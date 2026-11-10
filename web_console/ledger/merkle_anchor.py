import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from crypto.rfc8785 import canonicalize
from crypto.merkle import MerkleTree, leaf_hash_hex, verify_merkle_proof
from crypto.authority import sign_checkpoint, verify_checkpoint_signature, create_signed_checkpoint


class MerkleBatchEngine:
    """Batching engine committing approved evidence to ledger anchor records with genuine Authority signatures."""

    def __init__(self):
        self.ledger_anchors: List[Dict[str, Any]] = []
        self._trees: Dict[str, MerkleTree] = {}
        self._batch_envelopes: Dict[str, List[Dict[str, Any]]] = {}

    def commit_batch(
        self,
        approved_envelopes: List[Dict[str, Any]],
        authority_id: str = "praman-root-authority-1",
    ) -> Dict[str, Any]:
        if not approved_envelopes:
            raise ValueError("Cannot anchor an empty batch")

        # Canonical RFC 8785 bytes for each envelope
        canonical_leaves = [canonicalize(env) for env in approved_envelopes]
        tree = MerkleTree(canonical_leaves)

        batch_id = f"batch-{uuid.uuid4()}"
        timestamp_now = datetime.now(timezone.utc)
        ts_str = timestamp_now.strftime("%Y%m%d%H%M%S")
        iso_timestamp = f"{ts_str[:4]}-{ts_str[4:6]}-{ts_str[6:8]}T{ts_str[8:10]}:{ts_str[10:12]}:{ts_str[12:14]}Z"
        checkpoint_id = f"cp-{ts_str}-{uuid.uuid4().hex[:8]}"

        # Construct and sign checkpoint using genuine Authority P-256 key
        checkpoint = create_signed_checkpoint(
            checkpoint_id=checkpoint_id,
            merkle_root=tree.root_hex or "",
            leaf_count=len(approved_envelopes),
            timestamp=iso_timestamp,
            authority_id=authority_id,
            batch_id=batch_id,
        )

        anchor = {
            "batch_id": batch_id,
            "merkle_root": tree.root_hex,
            "leaf_count": len(approved_envelopes),
            "evidence_ids": [env["evidence_id"] for env in approved_envelopes],
            "anchored_at": iso_timestamp,
            "status": "COMMITTED_TO_LEDGER",
            "checkpoint_id": checkpoint_id,
            "checkpoint_signature": checkpoint["signature"],
            "checkpoint": checkpoint,
        }
        self.ledger_anchors.append(anchor)
        self._trees[batch_id] = tree
        self._batch_envelopes[batch_id] = approved_envelopes

        return {"anchor": anchor, "tree": tree, "checkpoint": checkpoint}

    def verify_anchor(
        self,
        anchor: Dict[str, Any],
        authority_pub_pem: Optional[str] = None,
    ) -> bool:
        """Verifies the genuine authority checkpoint signature bound to a ledger anchor."""
        checkpoint = anchor.get("checkpoint")
        if checkpoint:
            # Cross-check anchor fields against signed checkpoint fields
            if anchor.get("merkle_root") != checkpoint.get("merkle_root"):
                return False
            if anchor.get("batch_id") != checkpoint.get("batch_id"):
                return False
            if anchor.get("leaf_count") != checkpoint.get("leaf_count"):
                return False
            if anchor.get("checkpoint_id") != checkpoint.get("checkpoint_id"):
                return False
            signing_dict = checkpoint
        else:
            # Reconstruct checkpoint dict from anchor fields
            signing_dict = {
                "checkpoint_id": anchor.get("checkpoint_id"),
                "batch_id": anchor.get("batch_id"),
                "merkle_root": anchor.get("merkle_root"),
                "leaf_count": anchor.get("leaf_count"),
                "timestamp": anchor.get("anchored_at"),
                "authority_id": "praman-root-authority-1",
            }

        sig = anchor.get("checkpoint_signature") or (checkpoint.get("signature") if checkpoint else None)
        if not sig:
            return False

        return verify_checkpoint_signature(
            checkpoint_dict=signing_dict,
            signature_b64=sig,
            authority_pub_pem=authority_pub_pem,
        )

    def get_proof_for_evidence(
        self,
        batch_id: str,
        evidence_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Returns the Merkle inclusion proof for a specific evidence item in a committed batch."""
        if batch_id not in self._trees or batch_id not in self._batch_envelopes:
            return None

        tree = self._trees[batch_id]
        envelopes = self._batch_envelopes[batch_id]

        idx = -1
        for i, env in enumerate(envelopes):
            if env.get("evidence_id") == evidence_id:
                idx = i
                break
        if idx == -1:
            return None

        proof = tree.get_inclusion_proof(idx)
        canonical_leaf = canonicalize(envelopes[idx])
        return {
            "evidence_id": evidence_id,
            "batch_id": batch_id,
            "leaf_index": idx,
            "leaf_hash": leaf_hash_hex(canonical_leaf),
            "merkle_root": tree.root_hex,
            "inclusion_proof": [step.to_dict() if hasattr(step, "to_dict") else step for step in proof],
        }
