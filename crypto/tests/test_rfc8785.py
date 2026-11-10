"""Tests for RFC 8785 JSON Canonicalization Scheme (JCS)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from crypto.rfc8785 import (
    canonical_sha256,
    canonical_sha256_bytes,
    canonicalize,
    canonicalize_str,
)


class TestRFC8785Canonicalization:
    """Verifies RFC 8785 JCS canonicalization compliance."""

    def test_lexicographical_key_sorting(self):
        """Keys must be sorted strictly by UTF-16 code units across all nesting levels."""
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
        canonical = canonicalize(obj)
        expected = (
            b'{"a":2,"b":[3,2,1],"nested":{"alpha":"one","beta":"two",'
            b'"gamma":{"deep_a":false,"deep_z":true}},"z":1}'
        )
        assert canonical == expected

    def test_utf16_code_unit_sorting_surrogate_pairs(self):
        """Test non-BMP characters (surrogate pairs) sort before U+FFFF per UTF-16 code units."""
        # In UTF-16: U+1F600 emoji has surrogate pair 0xD83D, 0xDE00.
        # 0xD83D is numerically less than 0xFFFF.
        obj = {
            "\uffff": "high_bmp",
            "\U0001f600": "emoji_grinning",
            "10": "ten",
            "2": "two",
            "": "empty_key",
        }
        canonical = canonicalize_str(obj)
        # Expected order: "" < "10" < "2" < "\U0001f600" (0xD83D) < "\uffff" (0xFFFF)
        assert canonical.startswith('{"":"empty_key","10":"ten","2":"two"')
        assert (
            canonical
            == '{"":"empty_key","10":"ten","2":"two","😀":"emoji_grinning","\uffff":"high_bmp"}'
        )

    def test_ecmascript_number_formatting(self):
        """Verify ECMAScript number formatting rules."""
        obj = {
            "int_val": 42,
            "zero": 0,
            "neg_zero": -0.0,
            "float_int": 100.0,
            "pi": 3.14159,
            "small": 0.000001,
        }
        canonical = canonicalize(obj)
        assert b'"int_val":42' in canonical
        assert b'"zero":0' in canonical
        assert b'"neg_zero":0' in canonical
        assert b'"float_int":100' in canonical
        assert b'"pi":3.14159' in canonical

    def test_unicode_and_multilingual_handling(self):
        """Verify handling of non-ASCII UTF-8 characters (Telugu, Hindi) without escaping."""
        obj = {
            "hindi": "प्रमाण",
            "telugu": "ప్రమాణ్",
            "english": "PRAMAN",
            "slash": "path/to/resource",
            "quotes": 'Hello "World"',
            "newline": "Line1\nLine2",
        }
        canonical = canonicalize(obj)
        assert "ప్రమాణ్".encode("utf-8") in canonical
        assert "प्रमाण".encode("utf-8") in canonical
        # Slashes must NOT be escaped
        assert b"path/to/resource" in canonical
        assert b"path\\/to\\/resource" not in canonical
        # Quotes and newlines must be escaped
        assert b'\\"World\\"' in canonical
        assert b"\\n" in canonical

    def test_invalid_numbers_rejection(self):
        """Reject NaN, Infinity, and -Infinity as required by RFC 8785 and RFC 8259."""
        with pytest.raises(ValueError, match="NaN and Infinity"):
            canonicalize({"bad": float("nan")})

        with pytest.raises(ValueError, match="NaN and Infinity"):
            canonicalize({"bad": float("inf")})

        with pytest.raises(ValueError, match="NaN and Infinity"):
            canonicalize({"bad": float("-inf")})

    def test_determinism_across_permutations(self):
        """Dictionary insertion order permutations yield byte-for-byte identical output."""
        perm1 = {"c": 3, "a": 1, "b": 2, "d": [None, True, False]}
        perm2 = {"a": 1, "d": [None, True, False], "b": 2, "c": 3}
        perm3 = {"d": [None, True, False], "c": 3, "b": 2, "a": 1}

        res1 = canonicalize(perm1)
        res2 = canonicalize(perm2)
        res3 = canonicalize(perm3)

        assert res1 == res2 == res3
        assert res1 == b'{"a":1,"b":2,"c":3,"d":[null,true,false]}'

    def test_canonical_sha256_digests(self):
        """Verify canonical SHA-256 string and byte digest functions."""
        data = {"hello": "world"}
        hex_digest = canonical_sha256(data)
        byte_digest = canonical_sha256_bytes(data)

        assert len(hex_digest) == 64
        assert len(byte_digest) == 32
        assert bytes.fromhex(hex_digest) == byte_digest

    def test_dataclass_serialization(self):
        """Verify dataclasses serialize seamlessly."""

        @dataclass
        class SubItem:
            y: int
            x: int

        @dataclass
        class RootItem:
            sub: SubItem
            name: str

        item = RootItem(sub=SubItem(y=20, x=10), name="test")
        canonical = canonicalize_str(item)
        assert canonical == '{"name":"test","sub":{"x":10,"y":20}}'
