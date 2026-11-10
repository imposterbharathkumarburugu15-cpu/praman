"""Merkle Ledger Batching Service.

Features:
- Queries all approved evidence records not yet batched into a Merkle tree.
- Constructs domain-separated Merkle trees with odd-node promotion (RFC 6962 + CVE-2012-2459 immunity).
- Computes Merkle root and compact inclusion proofs for every leaf.
- Generates and signs authenticated checkpoints using the Authority NIST P-256 keypair.
- Persists batches into PostgreSQL merkle_batches table and transitions evidence to COMMITTED_TO_LEDGER.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from backend.app.models.evidence import Evidence
from backend.app.models.merkle_batch import MerkleBatch
from crypto.authority import (
    create_signed_checkpoint,
    get_authority_public_key_pem,
    sign_checkpoint,
    verify_checkpoint_signature,
)
from crypto.merkle import MerkleTree, leaf_hash_hex, verify_merkle_proof
from crypto.rfc8785 import canonicalize


class MerkleService:
    """Service orchestrating Merkle tree construction, checkpoint signing, and batch persistence."""

    @staticmethod
    def checkpoint_id_to_iso_timestamp(checkpoint_id: Optional[str]) -> str:
        """Extracts or reconstructs the canonical ISO timestamp from a checkpoint_id (e.g. cp-20261109184549-<uuid>)."""
        if checkpoint_id and checkpoint_id.startswith("cp-"):
            parts = checkpoint_id[3:].split("-")
            ts_part = parts[0]
            if len(ts_part) == 14 and ts_part.isdigit():
                return f"{ts_part[:4]}-{ts_part[4:6]}-{ts_part[6:8]}T{ts_part[8:10]}:{ts_part[10:12]}:{ts_part[12:14]}Z"
            if len(ts_part) == 8 and ts_part.isdigit():
                return f"{ts_part[:4]}-{ts_part[4:6]}-{ts_part[6:8]}T12:00:00Z"
        return "2026-11-09T18:00:00Z"

    @staticmethod
    def get_batched_evidence_ids(db: Session) -> Set[str]:
        """Collect all evidence IDs that have already been incorporated into Merkle batches."""
        batches = db.query(MerkleBatch).all()
        batched_ids: Set[str] = set()
        for batch in batches:
            try:
                ids = json.loads(batch.evidence_ids_json)
                if isinstance(ids, list):
                    batched_ids.update(str(x) for x in ids)
            except Exception:
                continue
        return batched_ids

    @classmethod
    def get_unbatched_approved_evidence(cls, db: Session) -> List[Evidence]:
        """Query all evidence records with status APPROVED that are not yet part of any Merkle batch."""
        batched_ids = cls.get_batched_evidence_ids(db)
        approved_items = (
            db.query(Evidence)
            .filter(Evidence.status == "APPROVED")
            .order_by(Evidence.created_at.asc(), Evidence.id.asc())
            .all()
        )
        return [ev for ev in approved_items if ev.id not in batched_ids]

    @classmethod
    def create_batch(
        cls,
        db: Session,
        evidence_ids: Optional[List[str]] = None,
        authority_id: str = "praman-root-authority-1",
    ) -> Dict[str, Any]:
        """Aggregates approved unbatched evidence records into a domain-separated Merkle batch.

        Args:
            db: SQLAlchemy session.
            evidence_ids: Optional explicit list of approved evidence IDs to batch.
            authority_id: Authority identifier signing the checkpoint.

        Returns:
            Dict containing batch model, batch_id, merkle_root, checkpoint, and inclusion proofs.

        Raises:
            ValueError: If no eligible evidence records exist or if specified evidence is invalid.
        """
        if evidence_ids is not None:
            if not evidence_ids:
                raise ValueError("Specified evidence_ids list cannot be empty")
            batched_ids = cls.get_batched_evidence_ids(db)
            evidence_records = (
                db.query(Evidence)
                .filter(Evidence.id.in_(evidence_ids))
                .all()
            )
            # Reorder to match input evidence_ids list
            ev_map = {ev.id: ev for ev in evidence_records}
            ordered_records = []
            for eid in evidence_ids:
                if eid not in ev_map:
                    raise ValueError(f"Evidence with id '{eid}' not found")
                ev = ev_map[eid]
                if ev.status not in ("APPROVED", "COMMITTED_TO_LEDGER"):
                    raise ValueError(f"Evidence '{eid}' must be APPROVED before batching (current status: {ev.status})")
                if eid in batched_ids:
                    raise ValueError(f"Evidence '{eid}' is already committed to an existing Merkle batch")
                ordered_records.append(ev)
            evidence_records = ordered_records
        else:
            evidence_records = cls.get_unbatched_approved_evidence(db)

        if not evidence_records:
            raise ValueError("No unbatched approved evidence available for Merkle batch creation")

        # Extract canonical leaves from evidence envelopes
        canonical_leaves: List[bytes] = []
        for ev in evidence_records:
            try:
                env_dict = json.loads(ev.canonical_envelope_json)
                canonical_leaf = canonicalize(env_dict)
                canonical_leaves.append(canonical_leaf)
            except Exception as e:
                raise ValueError(f"Corrupt canonical envelope JSON in evidence {ev.id}: {e}")

        # Construct domain-separated Merkle tree with odd-node promotion
        tree = MerkleTree(canonical_leaves)
        root_hex = tree.root_hex
        if not root_hex:
            raise ValueError("Failed to calculate Merkle root for batch")

        # Generate batch ID and checkpoint ID
        batch_id = f"batch-{uuid.uuid4()}"
        timestamp_now = datetime.now(timezone.utc)
        ts_str = timestamp_now.strftime("%Y%m%d%H%M%S")
        checkpoint_id = f"cp-{ts_str}-{uuid.uuid4().hex[:8]}"
        iso_timestamp = cls.checkpoint_id_to_iso_timestamp(checkpoint_id)

        # Construct and sign authority checkpoint
        checkpoint = create_signed_checkpoint(
            checkpoint_id=checkpoint_id,
            merkle_root=root_hex,
            leaf_count=len(canonical_leaves),
            timestamp=iso_timestamp,
            authority_id=authority_id,
            batch_id=batch_id,
        )

        # Persist MerkleBatch record
        evidence_id_list = [ev.id for ev in evidence_records]
        batch_record = MerkleBatch(
            id=batch_id,
            merkle_root=root_hex,
            leaf_count=len(canonical_leaves),
            evidence_ids_json=json.dumps(evidence_id_list),
            status="COMMITTED_TO_LEDGER",
            checkpoint_id=checkpoint_id,
            checkpoint_signature=checkpoint["signature"],
        )
        db.add(batch_record)

        # Transition batched evidence items to COMMITTED_TO_LEDGER
        for ev in evidence_records:
            ev.status = "COMMITTED_TO_LEDGER"

        db.commit()
        db.refresh(batch_record)

        # Generate inclusion proofs for every leaf
        proofs: Dict[str, Any] = {}
        for idx, ev in enumerate(evidence_records):
            proof_steps = tree.get_inclusion_proof(idx)
            leaf_h = leaf_hash_hex(canonical_leaves[idx])
            proofs[ev.id] = {
                "evidence_id": ev.id,
                "batch_id": batch_id,
                "leaf_index": idx,
                "leaf_hash": leaf_h,
                "merkle_root": root_hex,
                "inclusion_proof": [step.to_dict() if hasattr(step, "to_dict") else step for step in proof_steps],
                "checkpoint": checkpoint,
            }

        return {
            "batch": batch_record,
            "batch_id": batch_id,
            "merkle_root": root_hex,
            "leaf_count": len(canonical_leaves),
            "evidence_ids": evidence_id_list,
            "checkpoint_id": checkpoint_id,
            "checkpoint_signature": checkpoint["signature"],
            "checkpoint": checkpoint,
            "tree": tree,
            "proofs": proofs,
            "status": "COMMITTED_TO_LEDGER",
        }

    @staticmethod
    def list_batches(db: Session, skip: int = 0, limit: int = 100) -> List[MerkleBatch]:
        """List historical Merkle batches ordered by creation time descending."""
        return (
            db.query(MerkleBatch)
            .order_by(MerkleBatch.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_batch(db: Session, batch_id: str) -> Optional[MerkleBatch]:
        """Fetch a MerkleBatch record by its ID."""
        return db.query(MerkleBatch).filter(MerkleBatch.id == batch_id).first()

    @classmethod
    def get_evidence_inclusion_proof(
        cls,
        db: Session,
        evidence_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Computes and returns the inclusion proof for a given evidence item in its batch."""
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            return None

        # Find batch containing this evidence item
        batch = (
            db.query(MerkleBatch)
            .filter(MerkleBatch.evidence_ids_json.contains(evidence_id))
            .first()
        )
        if not batch:
            return None

        try:
            batch_evidence_ids: List[str] = json.loads(batch.evidence_ids_json)
        except Exception:
            return None

        if evidence_id not in batch_evidence_ids:
            return None

        # Fetch all evidence records in original batch order
        records = (
            db.query(Evidence)
            .filter(Evidence.id.in_(batch_evidence_ids))
            .all()
        )
        rec_map = {r.id: r for r in records}
        canonical_leaves: List[bytes] = []
        for eid in batch_evidence_ids:
            if eid not in rec_map:
                return None
            env_dict = json.loads(rec_map[eid].canonical_envelope_json)
            canonical_leaves.append(canonicalize(env_dict))

        tree = MerkleTree(canonical_leaves)
        leaf_index = batch_evidence_ids.index(evidence_id)
        proof = tree.get_inclusion_proof(leaf_index)
        canonical_target = canonical_leaves[leaf_index]

        iso_timestamp = cls.checkpoint_id_to_iso_timestamp(batch.checkpoint_id)
        checkpoint = {
            "checkpoint_id": batch.checkpoint_id,
            "batch_id": batch.id,
            "merkle_root": batch.merkle_root,
            "leaf_count": batch.leaf_count,
            "timestamp": iso_timestamp,
            "authority_id": "praman-root-authority-1",
            "signature": batch.checkpoint_signature,
        }

        return {
            "evidence_id": evidence_id,
            "batch_id": batch.id,
            "leaf_index": leaf_index,
            "leaf_hash": leaf_hash_hex(canonical_target),
            "merkle_root": batch.merkle_root,
            "inclusion_proof": [step.to_dict() if hasattr(step, "to_dict") else step for step in proof],
            "checkpoint": checkpoint,
            "status": batch.status,
        }

    @classmethod
    def verify_batch(cls, db: Session, batch_id: str) -> Dict[str, Any]:
        """Performs full independent cryptographic audit of a persisted MerkleBatch."""
        batch = cls.get_batch(db, batch_id)
        if not batch:
            return {"valid": False, "error": f"Batch '{batch_id}' not found"}

        try:
            eids: List[str] = json.loads(batch.evidence_ids_json)
        except Exception as e:
            return {"valid": False, "error": f"Invalid evidence IDs JSON: {e}"}

        records = db.query(Evidence).filter(Evidence.id.in_(eids)).all()
        rec_map = {r.id: r for r in records}
        leaves: List[bytes] = []
        for eid in eids:
            if eid not in rec_map:
                return {"valid": False, "error": f"Missing evidence record {eid}"}
            leaves.append(canonicalize(json.loads(rec_map[eid].canonical_envelope_json)))

        tree = MerkleTree(leaves)
        root_matches = (tree.root_hex == batch.merkle_root)

        iso_timestamp = cls.checkpoint_id_to_iso_timestamp(batch.checkpoint_id)
        checkpoint = {
            "checkpoint_id": batch.checkpoint_id,
            "batch_id": batch.id,
            "merkle_root": batch.merkle_root,
            "leaf_count": batch.leaf_count,
            "timestamp": iso_timestamp,
            "authority_id": "praman-root-authority-1",
        }
        sig_valid = verify_checkpoint_signature(
            checkpoint_dict=checkpoint,
            signature_b64=batch.checkpoint_signature,
        )

        return {
            "valid": root_matches and sig_valid,
            "batch_id": batch.id,
            "merkle_root_matches": root_matches,
            "computed_root": tree.root_hex,
            "persisted_root": batch.merkle_root,
            "signature_valid": sig_valid,
            "leaf_count": len(leaves),
        }
