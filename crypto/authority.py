"""NIST P-256 Authority Checkpoint key management and signing.

Features:
- Loads Authority P-256 private key from data/keys/authority_checkpoint_key.pem
  or AUTHORITY_KEY_PEM environment variable.
- Automatically generates and persists a valid NIST P-256 keypair if not present.
- Canonicalizes checkpoint payloads via RFC 8785 (JCS).
- Signs checkpoints with NIST P-256 ECDSA over SHA-256 with strict low-s normalization.
- Verifies checkpoint signatures against the Authority public key.
"""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from cryptography.hazmat.primitives.asymmetric import ec

from crypto.ecdsa_p256 import (
    generate_keypair,
    load_private_key,
    load_public_key,
    private_key_to_pem,
    public_key_to_pem,
    sign,
    verify,
)
from crypto.rfc8785 import canonicalize

# Key persistence path: data/keys/authority_checkpoint_key.pem
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_AUTHORITY_KEY_PATH = _PROJECT_ROOT / "data" / "keys" / "authority_checkpoint_key.pem"

_AUTHORITY_PRIVATE_KEY: Optional[ec.EllipticCurvePrivateKey] = None
_AUTHORITY_PUBLIC_KEY: Optional[ec.EllipticCurvePublicKey] = None
_AUTHORITY_PUB_PEM: Optional[str] = None


def get_authority_keypair(
    force_reload: bool = False,
) -> Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    """Loads the Authority keypair from env var, persisted file, or generates and persists once."""
    global _AUTHORITY_PRIVATE_KEY, _AUTHORITY_PUBLIC_KEY, _AUTHORITY_PUB_PEM

    if _AUTHORITY_PRIVATE_KEY is not None and not force_reload:
        return _AUTHORITY_PRIVATE_KEY, _AUTHORITY_PUBLIC_KEY

    # 1. Check environment variable
    env_pem = os.getenv("AUTHORITY_KEY_PEM")
    if env_pem and env_pem.strip():
        priv = load_private_key(env_pem.strip())
        pub = priv.public_key()
        _AUTHORITY_PRIVATE_KEY = priv
        _AUTHORITY_PUBLIC_KEY = pub
        _AUTHORITY_PUB_PEM = public_key_to_pem(pub)
        return priv, pub

    # 2. Check key file path
    key_path_str = os.getenv("AUTHORITY_KEY_PATH")
    key_path = Path(key_path_str) if key_path_str else _DEFAULT_AUTHORITY_KEY_PATH

    if key_path.exists():
        pem_data = key_path.read_text(encoding="utf-8")
        priv = load_private_key(pem_data.strip())
        pub = priv.public_key()
    else:
        # Generate new NIST P-256 keypair and persist to disk
        priv, pub = generate_keypair()
        pem_data = private_key_to_pem(priv)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(pem_data, encoding="utf-8")

    _AUTHORITY_PRIVATE_KEY = priv
    _AUTHORITY_PUBLIC_KEY = pub
    _AUTHORITY_PUB_PEM = public_key_to_pem(pub)
    return priv, pub


def get_authority_public_key_pem() -> str:
    """Return SubjectPublicKeyInfo PEM string of Authority public key."""
    global _AUTHORITY_PUB_PEM
    if _AUTHORITY_PUB_PEM is None:
        get_authority_keypair()
    return _AUTHORITY_PUB_PEM


def get_authority_private_key() -> ec.EllipticCurvePrivateKey:
    """Return Authority P-256 private key."""
    priv, _ = get_authority_keypair()
    return priv


def sign_checkpoint(
    checkpoint_dict: Dict[str, Any],
    private_key: Optional[ec.EllipticCurvePrivateKey] = None,
) -> str:
    """Signs a checkpoint payload over RFC 8785 canonical bytes with P-256 ECDSA.

    Strips 'signature' field if present to ensure the signature binds solely
    to the canonical data payload. Enforces strict low-s normalization.

    Args:
        checkpoint_dict: Checkpoint attributes dictionary.
        private_key: Optional private key (defaults to Authority private key).

    Returns:
        str: Base64-encoded NIST P-256 signature.
    """
    if private_key is None:
        private_key = get_authority_private_key()

    # Strip signature field if present to sign canonical content
    signing_dict = {k: v for k, v in checkpoint_dict.items() if k != "signature"}
    canonical_bytes = canonicalize(signing_dict)
    der_signature = sign(private_key, canonical_bytes, sig_format="der")
    return base64.b64encode(der_signature).decode("utf-8")


def verify_checkpoint_signature(
    checkpoint_dict: Dict[str, Any],
    signature_b64: Optional[str] = None,
    authority_pub_pem: Optional[Union[str, bytes, ec.EllipticCurvePublicKey]] = None,
) -> bool:
    """Verifies a P-256 ECDSA checkpoint signature over RFC 8785 canonical bytes.

    Args:
        checkpoint_dict: Checkpoint payload dictionary.
        signature_b64: Base64-encoded signature (if None, read from checkpoint_dict['signature']).
        authority_pub_pem: Optional public key or PEM (defaults to loaded Authority public key).

    Returns:
        bool: True if signature is cryptographically valid and not tampered, False otherwise.
    """
    if signature_b64 is None:
        signature_b64 = checkpoint_dict.get("signature")

    if not signature_b64:
        return False

    if authority_pub_pem is None:
        authority_pub_pem = get_authority_public_key_pem()

    signing_dict = {k: v for k, v in checkpoint_dict.items() if k != "signature"}
    canonical_bytes = canonicalize(signing_dict)

    try:
        return verify(
            public_key=authority_pub_pem,
            signature=signature_b64,
            data=canonical_bytes,
            enforce_low_s_check=True,
        )
    except Exception:
        return False


def create_signed_checkpoint(
    checkpoint_id: str,
    merkle_root: str,
    leaf_count: int,
    timestamp: Optional[str] = None,
    authority_id: str = "praman-root-authority-1",
    batch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Constructs and signs an authority checkpoint adhering to Interface Contract 4."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    checkpoint: Dict[str, Any] = {
        "checkpoint_id": checkpoint_id,
        "merkle_root": merkle_root,
        "leaf_count": leaf_count,
        "timestamp": timestamp,
        "authority_id": authority_id,
    }
    if batch_id is not None:
        checkpoint["batch_id"] = batch_id

    signature = sign_checkpoint(checkpoint)
    checkpoint["signature"] = signature
    return checkpoint
