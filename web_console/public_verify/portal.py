import json
from typing import Dict, Any, Set, Optional
from crypto.rfc8785 import canonicalize
from crypto.merkle import MerkleTree, leaf_hash_hex, verify_merkle_proof
from crypto.authority import sign_checkpoint, verify_checkpoint_signature, get_authority_public_key_pem


class PublicVerificationPortal:
    """Public verification service generating privacy-safe verification payloads."""

    FORBIDDEN_PII_FIELDS: Set[str] = {
        "farmer_name", "full_name", "phone_number", "phone", "aadhar",
        "national_id", "email", "address",
    }
    FORBIDDEN_GPS_FIELDS: Set[str] = {
        "latitude", "longitude", "lat", "lon", "gps_coordinates",
        "boundary_geojson", "polygon", "vertices",
    }

    @classmethod
    def sanitize_public_payload(
        cls,
        envelope: Dict[str, Any],
        tree: MerkleTree,
        leaf_index: int,
        public_token: str,
        crop_type: str = "Cotton",
        coarse_region: str = "Adilabad, Telangana",
        checkpoint_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        canonical_leaf = canonicalize(envelope)
        leaf_hash = leaf_hash_hex(canonical_leaf)
        proof = tree.get_inclusion_proof(leaf_index)

        meta = envelope.get("metadata", {})
        capture_date = (meta.get("capture_timestamp") or "2026-11-09")[:10]

        cp_id = checkpoint_id or f"cp-{capture_date.replace('-', '')}-001"
        checkpoint_data = {
            "checkpoint_id": cp_id,
            "timestamp": f"{capture_date}T15:00:00Z",
            "signer_id": "praman-trusted-authority-1",
            "authority_id": "praman-trusted-authority-1",
            "merkle_root": tree.root_hex,
            "leaf_count": tree.leaf_count,
        }
        # Genuine NIST P-256 Authority Signature over RFC 8785 canonical bytes
        checkpoint_sig = sign_checkpoint(checkpoint_data)
        checkpoint_data["signature"] = checkpoint_sig

        payload = {
            "public_token": public_token,
            "provenance_status": "COMMITTED_TO_LEDGER",
            "crop_type": crop_type,
            "lifecycle_stage": envelope["lifecycle_stage"],
            "capture_date": capture_date,
            "region_coarse": coarse_region,
            "image_sha256": envelope["image_hash"],
            "leaf_hash": leaf_hash,
            "merkle_root": tree.root_hex,
            "inclusion_proof": [step.to_dict() if hasattr(step, "to_dict") else step for step in proof],
            "checkpoint": checkpoint_data,
        }

        # Verification check: Ensure zero leakage
        serialized = json.dumps(payload).lower()
        for field in cls.FORBIDDEN_PII_FIELDS:
            if field in serialized:
                raise ValueError(f"CRITICAL: PII field '{field}' detected in public verification payload")
        for field in cls.FORBIDDEN_GPS_FIELDS:
            if field in serialized:
                raise ValueError(f"CRITICAL: GPS field '{field}' detected in public verification payload")

        return payload

    @classmethod
    def verify_public_payload(
        cls,
        payload: Dict[str, Any],
        envelope: Optional[Dict[str, Any]] = None,
        authority_pub_pem: Optional[str] = None,
    ) -> bool:
        """Independently verifies the genuine authority checkpoint signature and Merkle inclusion proof."""
        checkpoint = payload.get("checkpoint")
        if not checkpoint or not checkpoint.get("signature"):
            return False

        # 1. Verify Authority checkpoint signature
        is_sig_valid = verify_checkpoint_signature(
            checkpoint_dict=checkpoint,
            signature_b64=checkpoint["signature"],
            authority_pub_pem=authority_pub_pem,
        )
        if not is_sig_valid:
            return False

        # 2. Checkpoint root must match payload root
        if checkpoint.get("merkle_root") != payload.get("merkle_root"):
            return False

        # 3. If envelope is provided, verify inclusion proof against root
        if envelope is not None:
            canonical_leaf = canonicalize(envelope)
            is_proof_valid = verify_merkle_proof(
                leaf_data=canonical_leaf,
                proof=payload.get("inclusion_proof", []),
                expected_root=payload["merkle_root"],
            )
            if not is_proof_valid:
                return False

        return True
