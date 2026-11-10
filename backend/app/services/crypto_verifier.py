import base64
import hashlib
import json
from typing import Dict, Any, Tuple
from crypto.rfc8785 import canonicalize
from crypto.ecdsa_p256 import verify, SignatureMalleabilityError, CryptographicError


class CryptoVerifier:
    @staticmethod
    def verify_envelope_and_image(
        envelope: Dict[str, Any],
        signature_b64: str,
        image_bytes: bytes,
        public_key_pem: str,
    ) -> Tuple[bool, str]:
        """Validates image hash and cryptographic envelope signature.
        
        Returns:
            (is_valid, error_message)
        """
        # 1. Verify image binary SHA-256 matches envelope image_hash
        actual_image_hash = hashlib.sha256(image_bytes).hexdigest()
        expected_image_hash = envelope.get("image_hash")
        if actual_image_hash.lower() != str(expected_image_hash).lower():
            return False, f"Image hash mismatch: expected {expected_image_hash}, got {actual_image_hash}"

        # 2. Canonicalize envelope according to RFC 8785
        try:
            canonical_bytes = canonicalize(envelope)
        except Exception as e:
            return False, f"RFC 8785 canonicalization failed: {e}"

        # 3. Decode base64 signature
        try:
            signature_bytes = base64.b64decode(signature_b64)
        except Exception as e:
            return False, f"Base64 signature decoding failed: {e}"

        # 4. Verify P-256 ECDSA signature with low-s enforcement
        try:
            is_valid = verify(public_key_pem, signature_bytes, canonical_bytes)
            if not is_valid:
                return False, "Cryptographic signature verification failed"
        except SignatureMalleabilityError as e:
            return False, f"Signature malleability error: {e}"
        except CryptographicError as e:
            return False, f"Cryptographic verification error: {e}"
        except Exception as e:
            return False, f"Signature verification exception: {e}"

        return True, ""

