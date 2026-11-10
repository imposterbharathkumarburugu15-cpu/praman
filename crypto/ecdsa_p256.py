"""NIST P-256 (secp256r1) ECDSA key management, signing, verification, and format conversion.

Features:
- P-256 keypair generation, public key export/import (PEM, DER, Raw 65-byte uncompressed point).
- Lossless bidirectional conversion between ASN.1 DER and IEEE P1363 (64 bytes).
- Mandatory low-s enforcement raising SignatureMalleabilityError for malleable signatures (s > n // 2).
- Base64 encoding/decoding convenience methods.
- ECDSA over SHA-256.
"""

from __future__ import annotations

import base64
from typing import Literal, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

# NIST P-256 (secp256r1) curve group order n
P256_ORDER: int = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551

# Curve half-order threshold for low-s canonicalization: floor(n / 2)
HALF_P256_ORDER: int = (
    0x7FFFFFFF800000007FFFFFFFFFFFFFFFDE737D56D38BCF4279DCE5617E3192A8
)


class CryptographicError(Exception):
    """Base exception for all cryptographic errors."""


class SignatureMalleabilityError(CryptographicError):
    """Raised when an ECDSA signature has s > n // 2 (high-s malleability)."""


class InvalidSignatureFormatError(CryptographicError):
    """Raised when signature bytes do not conform to ASN.1 DER or IEEE P1363."""


def generate_keypair() -> Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    """Generate a fresh NIST P-256 (secp256r1) keypair."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()


def public_key_to_pem(public_key: ec.EllipticCurvePublicKey) -> str:
    """Export public key as SubjectPublicKeyInfo PEM string."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def public_key_to_der(public_key: ec.EllipticCurvePublicKey) -> bytes:
    """Export public key as SubjectPublicKeyInfo DER binary bytes (91 bytes)."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def public_key_to_raw(public_key: ec.EllipticCurvePublicKey) -> bytes:
    """Export public key as 65-byte uncompressed point (0x04 || X || Y)."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )


def load_public_key(
    key_data: Union[str, bytes, ec.EllipticCurvePublicKey],
) -> ec.EllipticCurvePublicKey:
    """Load a P-256 public key from PEM string/bytes, DER SPKI bytes, or 65-byte raw uncompressed point.

    Raises:
        CryptographicError: If key data is invalid or unrecognized.
    """
    if isinstance(key_data, ec.EllipticCurvePublicKey):
        return key_data

    if isinstance(key_data, str):
        key_str = key_data.strip()
        if key_str.startswith("-----BEGIN"):
            return serialization.load_pem_public_key(key_str.encode("utf-8"))
        # Attempt hex decoding if string
        try:
            raw_bytes = bytes.fromhex(key_str)
            return load_public_key(raw_bytes)
        except ValueError:
            pass
        # Attempt base64 decoding
        try:
            b64_bytes = base64.b64decode(key_str)
            return load_public_key(b64_bytes)
        except Exception as err:
            raise CryptographicError(
                f"Failed to parse public key string: {err}"
            ) from err

    if isinstance(key_data, (bytes, bytearray)):
        b = bytes(key_data)
        # Check for 65-byte raw uncompressed point (0x04 || X || Y)
        if len(b) == 65 and b[0] == 0x04:
            try:
                return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b)
            except Exception as err:
                raise CryptographicError(
                    f"Failed to parse raw EC point: {err}"
                ) from err
        # Check for PEM format in bytes
        if b.startswith(b"-----BEGIN"):
            try:
                return serialization.load_pem_public_key(b)
            except Exception as err:
                raise CryptographicError(
                    f"Failed to parse PEM public key: {err}"
                ) from err
        # Default to DER format
        try:
            return serialization.load_der_public_key(b)
        except Exception as err:
            raise CryptographicError(f"Failed to parse DER public key: {err}") from err

    raise TypeError(f"Unsupported key_data type: {type(key_data).__name__}")


def private_key_to_pem(private_key: ec.EllipticCurvePrivateKey) -> str:
    """Export private key as PKCS#8 PEM string."""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def load_private_key(
    key_data: Union[str, bytes, ec.EllipticCurvePrivateKey],
) -> ec.EllipticCurvePrivateKey:
    """Load a P-256 private key from PEM string or bytes."""
    if isinstance(key_data, ec.EllipticCurvePrivateKey):
        return key_data
    if isinstance(key_data, str):
        key_data = key_data.encode("utf-8")
    return serialization.load_pem_private_key(key_data, password=None)


def der_to_p1363(der_sig: bytes) -> bytes:
    """Convert an ASN.1 DER signature to 64-byte raw IEEE P1363 (r || s).

    Raises:
        InvalidSignatureFormatError: If DER signature cannot be decoded.
    """
    try:
        r, s = decode_dss_signature(der_sig)
    except Exception as err:
        raise InvalidSignatureFormatError(
            f"Invalid ASN.1 DER signature: {err}"
        ) from err

    r_bytes = r.to_bytes(32, byteorder="big")
    s_bytes = s.to_bytes(32, byteorder="big")
    return r_bytes + s_bytes


def p1363_to_der(p1363_sig: bytes) -> bytes:
    """Convert 64-byte raw IEEE P1363 signature (r || s) to ASN.1 DER.

    Raises:
        InvalidSignatureFormatError: If input is not exactly 64 bytes.
    """
    if len(p1363_sig) != 64:
        raise InvalidSignatureFormatError(
            f"IEEE P1363 signature must be exactly 64 bytes, got {len(p1363_sig)}"
        )
    r = int.from_bytes(p1363_sig[:32], byteorder="big")
    s = int.from_bytes(p1363_sig[32:], byteorder="big")
    return encode_dss_signature(r, s)


def extract_rs(signature: Union[bytes, str]) -> Tuple[int, int]:
    """Extract (r, s) scalar integers from DER, IEEE P1363, or Base64 string.

    Raises:
        InvalidSignatureFormatError: If signature format is unrecognized.
    """
    sig_bytes: bytes
    if isinstance(signature, str):
        sig_str = signature.strip()
        try:
            sig_bytes = base64.b64decode(sig_str)
        except Exception:
            try:
                sig_bytes = bytes.fromhex(sig_str)
            except Exception as err:
                raise InvalidSignatureFormatError(
                    f"Cannot decode signature string: {err}"
                ) from err
    else:
        sig_bytes = bytes(signature)

    if len(sig_bytes) == 64:
        r = int.from_bytes(sig_bytes[:32], byteorder="big")
        s = int.from_bytes(sig_bytes[32:], byteorder="big")
        return r, s

    if len(sig_bytes) >= 8 and sig_bytes[0] == 0x30:
        try:
            return decode_dss_signature(sig_bytes)
        except Exception as err:
            raise InvalidSignatureFormatError(
                f"Failed to parse DER signature: {err}"
            ) from err

    raise InvalidSignatureFormatError(
        f"Unrecognized signature format (length {len(sig_bytes)})"
    )


def enforce_low_s(signature: Union[bytes, str]) -> None:
    """Enforce that signature s is in low-s form (s <= n // 2).

    Raises:
        SignatureMalleabilityError: If s > HALF_P256_ORDER.
        InvalidSignatureFormatError: If signature is malformed.
        CryptographicError: If r or s are out of bounds [1, n-1].
    """
    r, s = extract_rs(signature)
    if not (1 <= r < P256_ORDER and 1 <= s < P256_ORDER):
        raise CryptographicError(
            f"Signature scalars out of curve range: r={hex(r)}, s={hex(s)}"
        )
    if s > HALF_P256_ORDER:
        raise SignatureMalleabilityError(
            f"Malleable signature detected: s ({hex(s)}) exceeds curve half-order ({hex(HALF_P256_ORDER)})"
        )


def normalize_low_s(der_sig: bytes) -> bytes:
    """Normalize ASN.1 DER signature so that s is in low-s form (s <= n // 2).

    If s > n // 2, returns DER signature with (r, n - s).
    """
    r, s = decode_dss_signature(der_sig)
    if s > HALF_P256_ORDER:
        s = P256_ORDER - s
        return encode_dss_signature(r, s)
    return der_sig


def sign(
    private_key: ec.EllipticCurvePrivateKey,
    data: bytes,
    sig_format: Literal["der", "p1363"] = "der",
) -> bytes:
    """Sign data using P-256 ECDSA over SHA-256, strictly enforcing low-s normalization.

    Args:
        private_key: The signer's P-256 private key.
        data: The binary data payload to sign.
        sig_format: Output format, either "der" (ASN.1 DER) or "p1363" (raw 64 bytes).

    Returns:
        bytes: The signature in requested format.
    """
    raw_der = private_key.sign(data, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(raw_der)
    if s > HALF_P256_ORDER:
        s = P256_ORDER - s

    if sig_format == "p1363":
        return r.to_bytes(32, byteorder="big") + s.to_bytes(32, byteorder="big")
    return encode_dss_signature(r, s)


def verify(
    public_key: Union[ec.EllipticCurvePublicKey, str, bytes],
    signature: Union[bytes, str],
    data: bytes,
    enforce_low_s_check: bool = True,
) -> bool:
    """Verify an ECDSA P-256 signature over SHA-256(data).

    Supports signatures in ASN.1 DER, IEEE P1363 (64 bytes), or Base64 string format.

    Args:
        public_key: Public key as cryptography object, PEM string, DER bytes, or raw point.
        signature: Signature as DER bytes, P1363 bytes, or Base64 string.
        data: The signed data payload.
        enforce_low_s_check: If True, raises SignatureMalleabilityError when s > n // 2.

    Returns:
        bool: True if signature is cryptographically valid, False if invalid or tampered.

    Raises:
        SignatureMalleabilityError: If enforce_low_s_check is True and s > n // 2.
    """
    try:
        pub_obj = load_public_key(public_key)
    except Exception:
        return False

    if enforce_low_s_check:
        # Note: enforce_low_s will raise SignatureMalleabilityError if s is high.
        # This exception is NOT caught here so caller can handle malleability rejection.
        try:
            enforce_low_s(signature)
        except (InvalidSignatureFormatError, CryptographicError) as err:
            if isinstance(err, SignatureMalleabilityError):
                raise
            return False

    # Convert signature to ASN.1 DER for cryptography library verification
    sig_der: bytes
    try:
        r, s = extract_rs(signature)
        sig_der = encode_dss_signature(r, s)
    except Exception:
        return False

    try:
        pub_obj.verify(sig_der, data, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
