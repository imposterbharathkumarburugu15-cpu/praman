"""F-01: RFC 8785 JSON Canonicalization Scheme (JCS) Tests.
Validates key sorting, ECMAScript number formatting, compact serialization, and UTF-8 encoding.
"""

import math
import pytest
from tests_e2e.fixtures.crypto_fixtures import rfc8785_canonicalize


class TestF01RFC8785Canonicalization:
    """Verifies compliance with RFC 8785 JSON Canonicalization Scheme."""

    def test_lexicographical_key_sorting(self):
        """Test 1: Verifies keys are sorted strictly by UTF-16 code units across nested structures."""
        obj = {
            "z": 1,
            "a": 2,
            "nested": {
                "beta": "two",
                "alpha": "one",
                "gamma": {"deep_z": True, "deep_a": False},
            },
            "b": [3, 2, 1],
        }
        canonical = rfc8785_canonicalize(obj)
        expected = b'{"a":2,"b":[3,2,1],"nested":{"alpha":"one","beta":"two","gamma":{"deep_a":false,"deep_z":true}},"z":1}'
        assert canonical == expected

    def test_ecmascript_number_formatting(self):
        """Test 2: Verifies ECMAScript number formatting rules (no leading plus, integer format, floats)."""
        obj = {
            "int_val": 42,
            "zero": 0,
            "float_int": 100.0,
            "pi": 3.14159,
            "small": 0.000001,
        }
        canonical = rfc8785_canonicalize(obj)
        assert b'"int_val":42' in canonical
        assert b'"zero":0' in canonical
        assert b'"float_int":100' in canonical
        assert b'"pi":3.14159' in canonical

    def test_unicode_and_multilingual_handling(self):
        """Test 3: Verifies handling of non-ASCII UTF-8 characters (Telugu, Hindi, emojis) without unnecessary escaping."""
        obj = {
            "hindi": "प्रमाण",
            "telugu": "ప్రమాణ్",
            "english": "PRAMAN",
            "quotes": 'Hello "World"',
            "newline": "Line1\nLine2",
        }
        canonical = rfc8785_canonicalize(obj)
        # RFC 8785 outputs unescaped UTF-8 for valid unicode characters
        assert "ప్రమాణ్".encode("utf-8") in canonical
        assert "प्रमाण".encode("utf-8") in canonical
        assert b'\\"World\\"' in canonical
        assert b"\\n" in canonical

    def test_invalid_numbers_rejection(self):
        """Test 4: Verifies rejection of NaN and Infinity as mandated by RFC 8785 and RFC 8259."""
        with pytest.raises(ValueError, match="NaN and Infinity"):
            rfc8785_canonicalize({"bad": float("nan")})

        with pytest.raises(ValueError, match="NaN and Infinity"):
            rfc8785_canonicalize({"bad": float("inf")})

        with pytest.raises(ValueError, match="NaN and Infinity"):
            rfc8785_canonicalize({"bad": float("-inf")})

    def test_determinism_across_permutations(self):
        """Test 5: Verifies that dictionary insertion order permutations yield byte-for-byte identical output."""
        perm1 = {"c": 3, "a": 1, "b": 2, "d": [None, True, False]}
        perm2 = {"a": 1, "d": [None, True, False], "b": 2, "c": 3}
        perm3 = {"d": [None, True, False], "c": 3, "b": 2, "a": 1}

        res1 = rfc8785_canonicalize(perm1)
        res2 = rfc8785_canonicalize(perm2)
        res3 = rfc8785_canonicalize(perm3)

        assert res1 == res2 == res3
        assert res1 == b'{"a":1,"b":2,"c":3,"d":[null,true,false]}'
