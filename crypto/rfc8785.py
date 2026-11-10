"""RFC 8785 JSON Canonicalization Scheme (JCS) implementation.

Conforms to RFC 8785:
- Object property keys sorted lexicographically by UTF-16 code units.
- Numbers formatted per ECMAScript specification (no trailing zeroes for integers,
  negative zero serialized as '0', exponential notation with lowercase 'e').
- Whitespace removed between tokens.
- Minimal string escaping (only quotes, backslash, and control characters U+0000..U+001F).
- Forward slash '/' is NOT escaped.
- Output encoded in UTF-8 without Byte Order Mark (BOM).
- Rejects NaN, Infinity, -Infinity.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, is_dataclass
from typing import Any

try:
    import rfc8785

    _HAS_RFC8785_LIB = True
except ImportError:
    _HAS_RFC8785_LIB = False


def _to_json_compatible(obj: Any) -> Any:
    """Recursively convert custom objects (dataclasses, pydantic models, objects with to_dict)

    into JSON-serializable primitives (dict, list, int, float, str, bool, None).
    """
    if obj is None:
        return None
    if isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(
                f"NaN and Infinity are not valid in JSON / RFC 8785: {obj}"
            )
        if obj == 0.0:
            return 0.0  # Normalized to 0 by serializer
        return obj
    if is_dataclass(obj) and not isinstance(obj, type):
        return _to_json_compatible(asdict(obj))
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return _to_json_compatible(obj.to_dict())
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        return _to_json_compatible(obj.model_dump())
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        return _to_json_compatible(obj.dict())
    if isinstance(obj, dict):
        return {str(k): _to_json_compatible(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_compatible(x) for x in obj]
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _utf16_key_sort(key: str) -> bytes:
    """Sort key for RFC 8785: UTF-16 code units represented as big-endian bytes."""
    return key.encode("utf-16-be")


def canonicalize(obj: Any) -> bytes:
    """Canonicalize a Python data structure into RFC 8785 canonical UTF-8 bytes.

    Args:
        obj: The object to canonicalize (dict, list, primitive, dataclass, etc.).

    Returns:
        bytes: Canonical UTF-8 encoded bytes without BOM.

    Raises:
        ValueError: If NaN, Infinity, or -Infinity is encountered.
        TypeError: If an unhandled data type is encountered.
    """
    normalized = _to_json_compatible(obj)

    if _HAS_RFC8785_LIB:
        try:
            return rfc8785.dumps(normalized)
        except rfc8785.FloatDomainError as err:
            raise ValueError(
                f"NaN and Infinity are not valid in JSON / RFC 8785: {err}"
            ) from err

    # Pure Python fallback implementation conforming strictly to RFC 8785
    return _pure_rfc8785_canonicalize(normalized)


def _pure_rfc8785_canonicalize(val: Any) -> bytes:
    """Pure Python implementation of RFC 8785 JCS when external library is unavailable."""

    def serialize_value(v: Any) -> str:
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            if isinstance(v, float):
                if math.isnan(v) or math.isinf(v):
                    raise ValueError(
                        f"NaN and Infinity are not valid in JSON / RFC 8785: {v}"
                    )
                if v == 0.0:
                    return "0"
                if v.is_integer() and abs(v) < 1e21:
                    return str(int(v))
                import json

                s = json.dumps(v)
                return s.replace("E", "e")
            return str(v)
        if isinstance(v, str):
            import json

            # json.dumps minimal escaping with ensure_ascii=False
            return json.dumps(v, ensure_ascii=False)
        if isinstance(v, list):
            elements = [serialize_value(x) for x in v]
            return "[" + ",".join(elements) + "]"
        if isinstance(v, dict):
            # Sort keys by UTF-16 code units (encode to UTF-16BE bytes for accurate code unit comparison)
            sorted_keys = sorted(v.keys(), key=_utf16_key_sort)
            items = []
            import json

            for k in sorted_keys:
                key_str = json.dumps(k, ensure_ascii=False)
                val_str = serialize_value(v[k])
                items.append(f"{key_str}:{val_str}")
            return "{" + ",".join(items) + "}"
        raise TypeError(f"Type {type(v)} not serializable in RFC 8785 JCS")

    return serialize_value(val).encode("utf-8")


def canonicalize_str(obj: Any) -> str:
    """Canonicalize an object into an RFC 8785 canonical UTF-8 string."""
    return canonicalize(obj).decode("utf-8")


def canonical_sha256(obj: Any) -> str:
    """Return the lowercase 64-character hex SHA-256 digest of the canonicalized object."""
    return hashlib.sha256(canonicalize(obj)).hexdigest()


def canonical_sha256_bytes(obj: Any) -> bytes:
    """Return the raw 32-byte SHA-256 digest of the canonicalized object."""
    return hashlib.sha256(canonicalize(obj)).digest()
