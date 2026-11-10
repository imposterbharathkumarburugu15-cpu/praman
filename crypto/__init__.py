"""PRAMAN Shared Cryptographic Library.

Modules:
- rfc8785: RFC 8785 JSON Canonicalization Scheme (JCS).
- ecdsa_p256: NIST P-256 ECDSA key generation, signing, and verification with low-s anti-malleability.
- envelope: Canonical Evidence Envelope schema, serialization, and signature binding.
- merkle: Deterministic domain-separated Merkle Tree with odd-node promotion and inclusion proofs.
"""

from crypto.ecdsa_p256 import (
    HALF_P256_ORDER,
    P256_ORDER,
    CryptographicError,
    InvalidSignatureFormatError,
    SignatureMalleabilityError,
    der_to_p1363,
    enforce_low_s,
    extract_rs,
    generate_keypair,
    load_private_key,
    load_public_key,
    normalize_low_s,
    p1363_to_der,
    private_key_to_pem,
    public_key_to_der,
    public_key_to_pem,
    public_key_to_raw,
    sign,
    verify,
)
from crypto.envelope import (
    VALID_CAPTURE_SOURCES,
    VALID_LIFECYCLE_STAGES,
    EvidenceEnvelope,
    EvidenceMetadata,
)
from crypto.merkle import (
    LEAF_PREFIX,
    NODE_PREFIX,
    InclusionProofStep,
    MerkleTree,
    leaf_hash,
    leaf_hash_hex,
    node_hash,
    node_hash_hex,
    verify_merkle_proof,
)
from crypto.rfc8785 import (
    canonical_sha256,
    canonical_sha256_bytes,
    canonicalize,
    canonicalize_str,
)

__all__ = [
    # RFC 8785
    "canonicalize",
    "canonicalize_str",
    "canonical_sha256",
    "canonical_sha256_bytes",
    # ECDSA P-256
    "P256_ORDER",
    "HALF_P256_ORDER",
    "CryptographicError",
    "SignatureMalleabilityError",
    "InvalidSignatureFormatError",
    "generate_keypair",
    "public_key_to_pem",
    "public_key_to_der",
    "public_key_to_raw",
    "load_public_key",
    "private_key_to_pem",
    "load_private_key",
    "der_to_p1363",
    "p1363_to_der",
    "extract_rs",
    "enforce_low_s",
    "normalize_low_s",
    "sign",
    "verify",
    # Envelope
    "VALID_LIFECYCLE_STAGES",
    "VALID_CAPTURE_SOURCES",
    "EvidenceMetadata",
    "EvidenceEnvelope",
    # Merkle
    "LEAF_PREFIX",
    "NODE_PREFIX",
    "InclusionProofStep",
    "MerkleTree",
    "leaf_hash",
    "leaf_hash_hex",
    "node_hash",
    "node_hash_hex",
    "verify_merkle_proof",
]
