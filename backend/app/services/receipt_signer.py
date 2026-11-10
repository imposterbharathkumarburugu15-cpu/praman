import os
import base64
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import ec
from crypto.ecdsa_p256 import (
    generate_keypair,
    sign,
    load_private_key,
    private_key_to_pem,
    public_key_to_pem,
)
from crypto.rfc8785 import canonicalize

# Key persistence path: data/keys/server_receipt_key.pem
_DEFAULT_KEY_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "keys" / "server_receipt_key.pem"
)

_SERVER_PRIVATE_KEY: Optional[ec.EllipticCurvePrivateKey] = None
_SERVER_PUBLIC_KEY: Optional[ec.EllipticCurvePublicKey] = None
_SERVER_PUB_PEM: Optional[str] = None


def get_server_keypair(
    force_reload: bool = False,
) -> Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    """Loads the server keypair from env var, or persisted file, or generates and persists once."""
    global _SERVER_PRIVATE_KEY, _SERVER_PUBLIC_KEY, _SERVER_PUB_PEM
    if _SERVER_PRIVATE_KEY is not None and not force_reload:
        return _SERVER_PRIVATE_KEY, _SERVER_PUBLIC_KEY

    # 1. Check environment variable
    env_pem = os.getenv("SERVER_RECEIPT_KEY_PEM")
    if env_pem and env_pem.strip():
        priv = load_private_key(env_pem.strip())
        pub = priv.public_key()
        _SERVER_PRIVATE_KEY = priv
        _SERVER_PUBLIC_KEY = pub
        _SERVER_PUB_PEM = public_key_to_pem(pub)
        return priv, pub

    # 2. Check key file path
    key_path_str = os.getenv("SERVER_RECEIPT_KEY_PATH")
    key_path = Path(key_path_str) if key_path_str else _DEFAULT_KEY_PATH

    if key_path.exists():
        pem_data = key_path.read_text(encoding="utf-8")
        priv = load_private_key(pem_data.strip())
        pub = priv.public_key()
    else:
        # Generate new keypair and persist to disk
        priv, pub = generate_keypair()
        pem_data = private_key_to_pem(priv)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(pem_data, encoding="utf-8")

    _SERVER_PRIVATE_KEY = priv
    _SERVER_PUBLIC_KEY = pub
    _SERVER_PUB_PEM = public_key_to_pem(pub)
    return priv, pub


# Initialize upon module import
get_server_keypair()


def get_server_public_key_pem() -> str:
    global _SERVER_PUB_PEM
    if _SERVER_PUB_PEM is None:
        get_server_keypair()
    return _SERVER_PUB_PEM


def get_server_private_key() -> ec.EllipticCurvePrivateKey:
    priv, _ = get_server_keypair()
    return priv


def sign_server_receipt(
    evidence_id: str,
    device_id: str,
    sequence_number: int,
    image_hash: str,
    server_timestamp: str,
) -> str:
    """Signs server durable receipt payload over RFC 8785 canonical bytes."""
    priv, _ = get_server_keypair()
    receipt_payload = {
        "device_id": str(device_id),
        "evidence_id": str(evidence_id),
        "image_hash": str(image_hash),
        "sequence_number": int(sequence_number),
        "server_timestamp": str(server_timestamp),
        "status": "DURABLY_ACKED",
    }
    canonical_bytes = canonicalize(receipt_payload)
    der_signature = sign(priv, canonical_bytes)
    return base64.b64encode(der_signature).decode("utf-8")


def sign_authority_checkpoint(checkpoint_dict: Dict[str, Any]) -> str:
    """Signs an authority checkpoint payload over RFC 8785 canonical bytes using Authority key."""
    from crypto.authority import sign_checkpoint
    return sign_checkpoint(checkpoint_dict)
