"""Merkle Ledger and Authority Checkpoint API endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.merkle_service import MerkleService
from crypto.authority import get_authority_public_key_pem, verify_checkpoint_signature
from crypto.merkle import verify_merkle_proof

router = APIRouter(prefix="/merkle", tags=["Merkle Ledger"])


# Schemas
class CreateBatchRequest(BaseModel):
    evidence_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional explicit list of approved evidence IDs to batch. If omitted, all unbatched approved evidence will be batched.",
    )
    authority_id: Optional[str] = Field(
        default="praman-root-authority-1",
        description="Authority identifier signing the checkpoint.",
    )


class CheckpointResponse(BaseModel):
    checkpoint_id: str
    batch_id: Optional[str] = None
    merkle_root: str
    leaf_count: int
    timestamp: str
    authority_id: str
    signature: str


class CreateBatchResponse(BaseModel):
    batch_id: str
    merkle_root: str
    leaf_count: int
    evidence_ids: List[str]
    checkpoint_id: str
    checkpoint_signature: str
    checkpoint: Dict[str, Any]
    status: str
    created_at: str


class BatchSummaryResponse(BaseModel):
    batch_id: str
    merkle_root: str
    leaf_count: int
    evidence_ids: List[str]
    status: str
    checkpoint_id: Optional[str] = None
    checkpoint_signature: Optional[str] = None
    created_at: str


class InclusionProofResponse(BaseModel):
    evidence_id: str
    batch_id: str
    leaf_index: int
    leaf_hash: str
    merkle_root: str
    inclusion_proof: List[Dict[str, str]]
    checkpoint: Dict[str, Any]
    status: str


class AuthorityKeyResponse(BaseModel):
    authority_id: str
    algorithm: str
    public_key_pem: str


# Endpoints
@router.post(
    "/batch",
    response_model=CreateBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Aggregate approved evidence into a signed Merkle checkpoint",
)
def create_merkle_batch(
    body: Optional[CreateBatchRequest] = None,
    db: Session = Depends(get_db),
):
    """Batches approved evidence records into a domain-separated Merkle tree,

    signs the checkpoint with the Authority NIST P-256 key, and persists
    the batch into PostgreSQL.
    """
    req_evidence_ids = body.evidence_ids if body else None
    authority_id = (body.authority_id if body and body.authority_id else "praman-root-authority-1")

    try:
        result = MerkleService.create_batch(
            db=db,
            evidence_ids=req_evidence_ids,
            authority_id=authority_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    batch_rec = result["batch"]
    created_at_str = (
        batch_rec.created_at.isoformat()
        if batch_rec.created_at
        else datetime.now(timezone.utc).isoformat()
    )

    return CreateBatchResponse(
        batch_id=result["batch_id"],
        merkle_root=result["merkle_root"],
        leaf_count=result["leaf_count"],
        evidence_ids=result["evidence_ids"],
        checkpoint_id=result["checkpoint_id"],
        checkpoint_signature=result["checkpoint_signature"],
        checkpoint=result["checkpoint"],
        status=result["status"],
        created_at=created_at_str,
    )


@router.get(
    "/batches",
    response_model=List[BatchSummaryResponse],
    summary="List historical Merkle batches and checkpoints",
)
def list_merkle_batches(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Returns historical Merkle batches with their roots, leaf counts, and signatures."""
    batches = MerkleService.list_batches(db, skip=skip, limit=limit)
    response_items = []
    for b in batches:
        try:
            ids = json.loads(b.evidence_ids_json)
        except Exception:
            ids = []
        c_at = b.created_at.isoformat() if b.created_at else datetime.now(timezone.utc).isoformat()
        response_items.append(
            BatchSummaryResponse(
                batch_id=b.id,
                merkle_root=b.merkle_root,
                leaf_count=b.leaf_count,
                evidence_ids=ids,
                status=b.status,
                checkpoint_id=b.checkpoint_id,
                checkpoint_signature=b.checkpoint_signature,
                created_at=c_at,
            )
        )
    return response_items


@router.get(
    "/batches/{batch_id}",
    response_model=BatchSummaryResponse,
    summary="Get details of a specific Merkle batch",
)
def get_merkle_batch(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Fetch a single Merkle batch by its ID."""
    batch = MerkleService.get_batch(db, batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Merkle batch with id '{batch_id}' not found",
        )
    try:
        ids = json.loads(batch.evidence_ids_json)
    except Exception:
        ids = []
    c_at = batch.created_at.isoformat() if batch.created_at else datetime.now(timezone.utc).isoformat()
    return BatchSummaryResponse(
        batch_id=batch.id,
        merkle_root=batch.merkle_root,
        leaf_count=batch.leaf_count,
        evidence_ids=ids,
        status=batch.status,
        checkpoint_id=batch.checkpoint_id,
        checkpoint_signature=batch.checkpoint_signature,
        created_at=c_at,
    )


@router.get(
    "/proof/{evidence_id}",
    response_model=InclusionProofResponse,
    summary="Get Merkle inclusion proof for a specific evidence item",
)
def get_evidence_merkle_proof(
    evidence_id: str,
    db: Session = Depends(get_db),
):
    """Returns the RFC 6962 domain-separated Merkle inclusion proof

    for a given evidence item along with the authenticated checkpoint.
    """
    proof_data = MerkleService.get_evidence_inclusion_proof(db, evidence_id)
    if not proof_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inclusion proof for evidence '{evidence_id}' not found (item may not be batched yet)",
        )

    return InclusionProofResponse(
        evidence_id=proof_data["evidence_id"],
        batch_id=proof_data["batch_id"],
        leaf_index=proof_data["leaf_index"],
        leaf_hash=proof_data["leaf_hash"],
        merkle_root=proof_data["merkle_root"],
        inclusion_proof=proof_data["inclusion_proof"],
        checkpoint=proof_data["checkpoint"],
        status=proof_data["status"],
    )


@router.get(
    "/authority-key",
    response_model=AuthorityKeyResponse,
    summary="Retrieve the Authority public key for independent checkpoint verification",
)
def get_authority_key():
    """Returns the SubjectPublicKeyInfo PEM string of the Authority checkpoint signing key."""
    pem = get_authority_public_key_pem()
    return AuthorityKeyResponse(
        authority_id="praman-root-authority-1",
        algorithm="ECDSA-SHA256-P256",
        public_key_pem=pem,
    )
