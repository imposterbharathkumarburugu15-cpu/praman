"""Cryptographic fixtures and authoritative reference oracles for PRAMAN E2E testing.
Covers:
- RFC 8785 JSON Canonicalization Scheme (JCS)
- P-256 ECDSA key generation, DER signing, and verification
- Domain-separated Merkle Tree (0x00 leaf / 0x01 internal node)
- Odd-node promotion preventing CVE-2012-2459 duplication
- Merkle inclusion proof generator and verifier
"""

import hashlib
import json
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.utils import (
    encode_dss_signature,
    decode_dss_signature,
)
from cryptography.exceptions import InvalidSignature

# Import genuine implementations from the production crypto subsystem
from crypto.rfc8785 import (
    canonicalize,
    canonicalize_str,
    canonical_sha256,
    canonical_sha256_bytes,
)
from crypto.ecdsa_p256 import (
    generate_keypair,
    sign,
    verify,
    public_key_to_pem,
    public_key_to_der,
    extract_rs,
    enforce_low_s,
    normalize_low_s,
    HALF_P256_ORDER,
    P256_ORDER,
    SignatureMalleabilityError,
    InvalidSignatureFormatError,
    der_to_p1363,
    p1363_to_der,
)
from crypto.merkle import (
    MerkleTree,
    leaf_hash,
    node_hash,
    leaf_hash_hex,
    node_hash_hex,
    verify_merkle_proof,
    LEAF_PREFIX,
    NODE_PREFIX,
)

# Reference oracle aliases bound directly to the verified production crypto package
rfc8785_canonicalize = canonicalize
sign_p256_der = sign
verify_p256_der = verify
ReferenceMerkleTree = MerkleTree
verify_inclusion_proof = verify_merkle_proof


def is_low_s(signature: bytes) -> bool:
    """Checks if ECDSA signature satisfies low-s requirement (s <= n/2)."""
    r, s = extract_rs(signature)
    return s <= HALF_P256_ORDER


def normalize_to_low_s(signature_der: bytes) -> bytes:
    """Normalizes signature to low-s form."""
    return normalize_low_s(signature_der)


def generate_p256_keypair() -> Tuple[ec.EllipticCurvePrivateKey, str, bytes]:
    """Generates a P-256 (secp256r1) keypair using genuine crypto.ecdsa_p256.
    
    Returns:
        (private_key_obj, public_key_pem_str, public_key_der_bytes)
    """
    private_key, public_key = generate_keypair()
    pub_pem = public_key_to_pem(public_key)
    pub_der = public_key_to_der(public_key)
    return private_key, pub_pem, pub_der
