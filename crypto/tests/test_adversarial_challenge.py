"""Adversarial Challenge and Stress-Test Suite for PRAMAN Cryptography Engine.

Executed by: challenger_m1_1 (Empirical Challenger)
Target: crypto/ (rfc8785.py, ecdsa_p256.py, envelope.py, merkle.py)

Challenge Vectors:
1. Signature Malleability & high-s rejection with SignatureMalleabilityError
2. Corrupted, truncated, trailing, and malformed DER bytes fuzzing
3. RFC 8785 JSON Canonicalization Scheme fuzzing (surrogates, floats, control chars, nesting)
4. Merkle Tree second-preimage, odd-node promotion, and proof manipulation attacks
5. Evidence Envelope boundary value and tampering stress tests
"""

import base64
import copy
import hashlib
import json
import math
import os
import random
import sys
import pytest
from typing import Any, Dict, List

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

from crypto.ecdsa_p256 import (
    P256_ORDER,
    HALF_P256_ORDER,
    CryptographicError,
    SignatureMalleabilityError,
    InvalidSignatureFormatError,
    generate_keypair,
    public_key_to_pem,
    public_key_to_der,
    public_key_to_raw,
    load_public_key,
    load_private_key,
    private_key_to_pem,
    sign,
    verify,
    extract_rs,
    enforce_low_s,
    normalize_low_s,
    der_to_p1363,
    p1363_to_der,
)
from crypto.rfc8785 import (
    canonicalize,
    canonicalize_str,
    canonical_sha256,
    canonical_sha256_bytes,
)
from crypto.envelope import (
    EvidenceEnvelope,
    EvidenceMetadata,
    VALID_LIFECYCLE_STAGES,
    VALID_CAPTURE_SOURCES,
)
from crypto.merkle import (
    MerkleTree,
    leaf_hash,
    leaf_hash_hex,
    node_hash,
    node_hash_hex,
    verify_merkle_proof,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def keypair():
    priv, pub = generate_keypair()
    return priv, pub


@pytest.fixture
def valid_envelope_dict() -> Dict[str, Any]:
    return {
        "device_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "evidence_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "farm_id": "b1b11b11-1111-1111-1111-111111111111",
        "image_hash": "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
        "lifecycle_stage": "CROP_GROWTH",
        "metadata": {
            "capture_source": "CAMERA",
            "capture_timestamp": "2026-11-09T14:30:00Z",
            "gps_accuracy": 3.5,
            "latitude": 17.385044,
            "longitude": 78.486671,
        },
        "schema_version": "1.0",
        "sequence_number": 42,
    }


# =====================================================================
# Suite 1: Signature Malleability & High-s Enforcement
# =====================================================================

class TestSignatureMalleabilityChallenge:
    """Adversarial stress-testing of ECDSA P-256 signature malleability defenses."""

    def test_high_s_der_raises_malleability_error(self, keypair):
        """High-s DER signature MUST strictly raise SignatureMalleabilityError."""
        priv, pub = keypair
        payload = b"Adversarial payload testing high-s rejection in DER"

        # Sign producing low-s
        der_sig = sign(priv, payload, sig_format="der")
        r, s = decode_dss_signature(der_sig)
        assert s <= HALF_P256_ORDER

        # Malleate to high-s
        s_malleated = P256_ORDER - s
        assert s_malleated > HALF_P256_ORDER
        malleated_der = encode_dss_signature(r, s_malleated)

        # 1. enforce_low_s must raise SignatureMalleabilityError
        with pytest.raises(SignatureMalleabilityError) as exc_info:
            enforce_low_s(malleated_der)
        assert "Malleable signature detected" in str(exc_info.value)

        # 2. verify with enforce_low_s_check=True (default) MUST raise SignatureMalleabilityError
        with pytest.raises(SignatureMalleabilityError):
            verify(pub, malleated_der, payload, enforce_low_s_check=True)

        # 3. verify with enforce_low_s_check=False validates mathematically (proves it was a valid ECDSA point)
        assert verify(pub, malleated_der, payload, enforce_low_s_check=False) is True

    def test_high_s_p1363_raises_malleability_error(self, keypair):
        """High-s IEEE P1363 (64 bytes) signature MUST strictly raise SignatureMalleabilityError."""
        priv, pub = keypair
        payload = b"Adversarial payload testing high-s rejection in IEEE P1363"

        p1363_sig = sign(priv, payload, sig_format="p1363")
        r = int.from_bytes(p1363_sig[:32], byteorder="big")
        s = int.from_bytes(p1363_sig[32:], byteorder="big")
        assert s <= HALF_P256_ORDER

        # Invert s
        s_high = P256_ORDER - s
        p1363_high = r.to_bytes(32, byteorder="big") + s_high.to_bytes(32, byteorder="big")

        with pytest.raises(SignatureMalleabilityError):
            enforce_low_s(p1363_high)

        with pytest.raises(SignatureMalleabilityError):
            verify(pub, p1363_high, payload, enforce_low_s_check=True)

    def test_high_s_base64_raises_malleability_error(self, keypair):
        """High-s signature passed as Base64 string MUST raise SignatureMalleabilityError."""
        priv, pub = keypair
        payload = b"Base64 high-s malleability test"
        der_sig = sign(priv, payload, sig_format="der")
        r, s = decode_dss_signature(der_sig)
        malleated_der = encode_dss_signature(r, P256_ORDER - s)
        b64_malleated = base64.b64encode(malleated_der).decode("ascii")

        with pytest.raises(SignatureMalleabilityError):
            enforce_low_s(b64_malleated)

        with pytest.raises(SignatureMalleabilityError):
            verify(pub, b64_malleated, payload)

    def test_evidence_envelope_verify_signature_bubbles_malleability_error(self, keypair, valid_envelope_dict):
        """EvidenceEnvelope.verify_signature MUST bubble SignatureMalleabilityError."""
        priv, pub = keypair
        env = EvidenceEnvelope.from_dict(valid_envelope_dict)
        valid_der = env.sign(priv, sig_format="der")

        # Verify valid signature succeeds
        assert env.verify_signature(pub, valid_der) is True

        # Invert to high-s
        r, s = decode_dss_signature(valid_der)
        malleated_der = encode_dss_signature(r, P256_ORDER - s)

        # verify_signature MUST raise SignatureMalleabilityError, not silently return False
        with pytest.raises(SignatureMalleabilityError):
            env.verify_signature(pub, malleated_der)

    def test_scalar_order_boundary_conditions(self):
        """Test exact boundary points of half-order, zero, and n."""
        # 1. Exact half order: s = floor(n / 2)
        valid_s = HALF_P256_ORDER
        valid_der = encode_dss_signature(1, valid_s)
        # Should NOT raise SignatureMalleabilityError
        enforce_low_s(valid_der)

        # 2. First high-s scalar: s = floor(n / 2) + 1
        first_high_s = HALF_P256_ORDER + 1
        der_first_high = encode_dss_signature(1, first_high_s)
        with pytest.raises(SignatureMalleabilityError):
            enforce_low_s(der_first_high)

        # 3. Maximum valid curve scalar: s = n - 1
        max_high_s = P256_ORDER - 1
        der_max_high = encode_dss_signature(1, max_high_s)
        with pytest.raises(SignatureMalleabilityError):
            enforce_low_s(der_max_high)

        # 4. Out of bounds scalar: s = n
        der_s_n = encode_dss_signature(1, P256_ORDER)
        with pytest.raises(CryptographicError) as exc_info:
            enforce_low_s(der_s_n)
        assert "out of curve range" in str(exc_info.value)

        # 5. Out of bounds scalar: s = 0
        der_s_zero = encode_dss_signature(1, 0)
        with pytest.raises(CryptographicError):
            enforce_low_s(der_s_zero)

        # 6. Out of bounds scalar: r = 0
        der_r_zero = encode_dss_signature(0, 100)
        with pytest.raises(CryptographicError):
            enforce_low_s(der_r_zero)

        # 7. Out of bounds scalar: r = n
        der_r_n = encode_dss_signature(P256_ORDER, 100)
        with pytest.raises(CryptographicError):
            enforce_low_s(der_r_n)

    def test_randomized_malleability_stress_100_samples(self, keypair):
        """Stress-test 100 freshly generated signatures, verifying low-s and high-s inversion behavior."""
        priv, pub = keypair
        rng = random.Random(42)

        for i in range(100):
            payload = f"random_stress_payload_{i}_{rng.getrandbits(128)}".encode("utf-8")
            der_sig = sign(priv, payload)
            r, s = decode_dss_signature(der_sig)
            assert s <= HALF_P256_ORDER, f"Sign() returned high-s on iteration {i}"

            # Invert
            high_s = P256_ORDER - s
            der_high = encode_dss_signature(r, high_s)

            # High-s MUST raise SignatureMalleabilityError
            with pytest.raises(SignatureMalleabilityError):
                verify(pub, der_high, payload)

            # Normalization MUST rescue it back to valid low-s
            der_normalized = normalize_low_s(der_high)
            assert verify(pub, der_normalized, payload) is True


# =====================================================================
# Suite 2: Corrupted DER Bytes & Fuzzing
# =====================================================================

class TestCorruptedDERChallenge:
    """Adversarial stress-testing against corrupted, truncated, and malformed DER structures."""

    def test_truncated_der_bytes_matrix(self, keypair):
        """Every truncated prefix of a valid DER signature MUST return False or raise InvalidSignatureFormatError/SignatureMalleabilityError."""
        priv, pub = keypair
        payload = b"Truncation test message"
        valid_der = sign(priv, payload)
        assert len(valid_der) >= 70

        for trunc_len in range(len(valid_der)):
            truncated = valid_der[:trunc_len]
            # verify() must never verify (return True). It must either return False or raise SignatureMalleabilityError (if parsed as 64-byte P1363 with high-s)
            try:
                assert verify(pub, truncated, payload) is False, f"Truncated length {trunc_len} verified!"
            except SignatureMalleabilityError:
                assert len(truncated) == 64

            # der_to_p1363 strictly expects valid ASN.1 DER; any truncation MUST raise InvalidSignatureFormatError
            with pytest.raises(InvalidSignatureFormatError):
                der_to_p1363(truncated)

            # extract_rs parses 64-byte as P1363, all other truncated lengths must raise InvalidSignatureFormatError
            if len(truncated) != 64:
                with pytest.raises(InvalidSignatureFormatError):
                    extract_rs(truncated)
            else:
                r, s = extract_rs(truncated)
                assert isinstance(r, int) and isinstance(s, int)

    def test_trailing_garbage_rejection(self, keypair):
        """Appended trailing bytes to a valid DER signature MUST be rejected."""
        priv, pub = keypair
        payload = b"Trailing garbage test payload"
        valid_der = sign(priv, payload)

        trailing_vectors = [
            valid_der + b"\x00",
            valid_der + b"\xff",
            valid_der + b"\x00" * 16,
            valid_der + b"TRAILING_EXCESS_BYTES_PARSER_DIFFERENTIAL",
            valid_der + valid_der,  # Concatenated signature attack
        ]

        for tampered in trailing_vectors:
            assert verify(pub, tampered, payload) is False
            with pytest.raises(InvalidSignatureFormatError):
                extract_rs(tampered)
            with pytest.raises(InvalidSignatureFormatError):
                der_to_p1363(tampered)

    def test_bit_flip_der_fuzzing(self, keypair):
        """Fuzz 200 random single-byte corruptions in valid DER: MUST never return True."""
        priv, pub = keypair
        payload = b"Bit-flip fuzzing payload"
        valid_der = bytearray(sign(priv, payload))
        rng = random.Random(1337)

        for _ in range(200):
            corrupted = bytearray(valid_der)
            pos = rng.randint(0, len(corrupted) - 1)
            flip_mask = 1 << rng.randint(0, 7)
            corrupted[pos] ^= flip_mask

            corrupted_bytes = bytes(corrupted)
            try:
                result = verify(pub, corrupted_bytes, payload)
                # If it didn't raise malleability, it MUST be False
                assert result is False
            except SignatureMalleabilityError:
                # If bit flip happened to produce a high-s scalar, malleability error is valid
                pass

    def test_malformed_asn1_tags(self, keypair):
        """Corrupt ASN.1 tags (0x30 SEQUENCE, 0x02 INTEGER) with invalid identifiers."""
        priv, pub = keypair
        payload = b"Malformed ASN.1 tags test"
        valid_der = sign(priv, payload)

        # 1. Invalid sequence tag
        for bad_tag in [0x00, 0x02, 0x04, 0x31, 0x7F, 0xFF]:
            corrupted = bytes([bad_tag]) + valid_der[1:]
            assert verify(pub, corrupted, payload) is False

        # 2. Corrupt r-tag (byte at index 2)
        corrupted_r_tag = valid_der[:2] + b"\x03" + valid_der[3:]
        assert verify(pub, corrupted_r_tag, payload) is False

    def test_degenerate_byte_payloads(self, keypair):
        """Test completely degenerate signature payloads."""
        priv, pub = keypair
        payload = b"Degenerate byte test"

        degenerate_inputs = [
            b"",
            b"\x00",
            b"\x00" * 8,
            b"\x00" * 64,
            b"\x00" * 72,
            b"\xff" * 64,
            b"\xff" * 72,
            b"not a signature",
            b"30" * 35,  # ASCII hex instead of binary
            b"\x30\x00",  # Zero length sequence
            b"\x30\x02\x02\x00",
            b"\x30\x82\xff\xff",  # Huge declared length
        ]

        for bad in degenerate_inputs:
            assert verify(pub, bad, payload) is False


# =====================================================================
# Suite 3: RFC 8785 Canonicalization Fuzzing
# =====================================================================

class TestRFC8785FuzzingChallenge:
    """Adversarial stress-testing of RFC 8785 JSON Canonicalization Scheme."""

    def test_utf16_surrogate_pair_vs_bmp_sorting(self):
        """UTF-16 code unit ordering: Non-BMP character (surrogate pair) MUST sort before U+FFFF."""
        # Non-BMP character U+10000 (surrogate pair D800 DC00 in UTF-16)
        # BMP character U+FFFF (represented as FFFF in UTF-16)
        # In UTF-16 code units: 0xD800 < 0xFFFF, so U+10000 MUST sort BEFORE U+FFFF.
        # In UTF-8 / Unicode code-point sorting: U+FFFF (3 bytes) < U+10000 (4 bytes), which is WRONG for RFC 8785!
        data = {
            "\uffff": "high BMP",
            "\U00010000": "first non-BMP",
        }
        canonical = canonicalize_str(data)
        # "\U00010000" must precede "\uffff"
        expected = '{"\U00010000":"first non-BMP","\uffff":"high BMP"}'
        assert canonical == expected

    def test_emoji_and_mathematical_surrogates_sorting(self):
        """Complex surrogate pair keys sorting against basic multilingual plane."""
        data = {
            "z": 1,
            "\U0001F600": 2,  # Grinning face 😀 (surrogate pair D83D DE00)
            "\U0001D400": 3,  # Mathematical Bold A 𝐀 (surrogate pair D835 DC00)
            "a": 4,
            "\u4e16": 5,      # CJK character 世 (4E16)
            "\uffee": 6,      # Halfwidth character (FFEE)
        }
        # In UTF-16 code units:
        # 'a' = 0x0061
        # 'z' = 0x007A
        # '\u4e16' = 0x4E16
        # '\U0001D400' = 0xD835, 0xDC00
        # '\U0001F600' = 0xD83D, 0xDE00
        # '\uffee' = 0xFFEE
        expected_order = ['"a":4', '"z":1', '"\u4e16":5', '"\U0001D400":3', '"\U0001F600":2', '"\uffee":6']
        canonical = canonicalize_str(data)
        assert canonical == "{" + ",".join(expected_order) + "}"

    def test_float_ecmascript_formatting_edge_cases(self):
        """ECMAScript float serialization rules in RFC 8785."""
        # 1. 0.0 and -0.0 both serialize to "0"
        assert canonicalize_str(0.0) == "0"
        assert canonicalize_str(-0.0) == "0"

        # 2. Integer-valued floats must not have trailing decimals
        assert canonicalize_str(1.0) == "1"
        assert canonicalize_str(-42.0) == "-42"
        assert canonicalize_str(100000000000.0) == "100000000000"

        # 3. Rejection of NaN and Infs
        for invalid in [float("nan"), float("inf"), float("-inf")]:
            with pytest.raises(ValueError) as exc:
                canonicalize(invalid)
            assert "NaN and Infinity are not valid" in str(exc.value)

            with pytest.raises(ValueError):
                canonicalize({"val": invalid})

            with pytest.raises(ValueError):
                canonicalize([1, 2, invalid])

    def test_control_character_escaping_strictness(self):
        """Control characters U+0000 through U+001F must be escaped; '/' must NOT be escaped."""
        payload = {
            "controls": "\u0000\u0001\u001f\b\f\n\r\t",
            "url": "http://example.com/api/v1/test?query=foo/bar",
            "quotes": 'Double "quote" and backslash \\',
        }
        canonical = canonicalize_str(payload)

        # Slash must NOT be escaped as \/
        assert "\\/" not in canonical
        assert "http://example.com/api/v1/test?query=foo/bar" in canonical

        # Control characters escaped
        assert "\\u0000" in canonical
        assert "\\u0001" in canonical
        assert "\\u001f" in canonical

    def test_deep_nesting_stress(self):
        """Stress-test deep nesting (depth 100)."""
        curr = "leaf_value"
        for i in range(100):
            curr = {f"k_{99-i}": curr}

        canonical = canonicalize_str(curr)
        assert canonical.startswith('{"k_0":')
        assert "leaf_value" in canonical

        # Deterministic SHA-256
        h1 = canonical_sha256(curr)
        h2 = canonical_sha256(curr)
        assert h1 == h2

    def test_permutation_invariance_100_keys(self):
        """Verify that any permutation of 100 dictionary keys yields identical canonical bytes."""
        keys = [f"key_{i:04d}" for i in range(100)]
        values = [i * 1.5 for i in range(100)]
        base_dict = dict(zip(keys, values))

        expected_canonical = canonicalize(base_dict)
        expected_hash = hashlib.sha256(expected_canonical).hexdigest()

        rng = random.Random(42)
        for _ in range(25):
            shuffled_keys = list(keys)
            rng.shuffle(shuffled_keys)
            shuffled_dict = {k: base_dict[k] for k in shuffled_keys}

            assert canonicalize(shuffled_dict) == expected_canonical
            assert canonical_sha256(shuffled_dict) == expected_hash


# =====================================================================
# Suite 4: Merkle Tree Adversarial Resistance
# =====================================================================

class TestMerkleAdversarialChallenge:
    """Stress-testing Merkle Tree odd-node promotion and second-preimage defenses."""

    def test_cve_2012_2459_leaf_duplication_attack(self):
        """An odd leaf duplicated at the end MUST produce a different root (Bitcoin CVE-2012-2459)."""
        # Test across multiple leaf configurations: 1, 3, 5, 7 leaves
        for count in [1, 3, 5, 7, 9]:
            leaves_orig = [f"evidence_payload_{i}".encode("utf-8") for i in range(count)]
            leaves_duplicated = leaves_orig + [leaves_orig[-1]]

            tree_orig = MerkleTree(leaves_orig)
            tree_dup = MerkleTree(leaves_duplicated)

            assert tree_orig.root != tree_dup.root, (
                f"CVE-2012-2459 VULNERABILITY! Root collision for count={count}: "
                f"{tree_orig.root_hex} == {tree_dup.root_hex}"
            )

    def test_domain_separation_second_preimage_resistance(self):
        """Leaf hash (0x00 prefix) cannot collide with internal node hash (0x01 prefix)."""
        # Craft a 64-byte payload consisting of left_hash || right_hash
        left = hashlib.sha256(b"left_node").digest()
        right = hashlib.sha256(b"right_node").digest()

        h_node = node_hash(left, right)
        h_leaf = leaf_hash(left + right)

        assert h_node != h_leaf, "Domain separation failure! 0x00 and 0x01 collided!"

    def test_all_tree_sizes_up_to_35_leaves_inclusion_proofs(self):
        """Every leaf in trees of sizes 1 to 35 MUST generate a valid verifying proof."""
        for n in range(1, 36):
            leaves = [f"leaf_data_{i}".encode("utf-8") for i in range(n)]
            tree = MerkleTree(leaves)
            assert tree.leaf_count == n
            assert tree.root is not None

            for i in range(n):
                assert tree.verify_leaf(i) is True, f"Inclusion proof verification failed for tree size {n}, leaf {i}"

    def test_proof_tampering_attacks(self):
        """Tampering with proof position, hash, or steps MUST invalidate the proof."""
        leaves = [b"leaf_0", b"leaf_1", b"leaf_2", b"leaf_3", b"leaf_4"]
        tree = MerkleTree(leaves)

        for leaf_idx in range(len(leaves)):
            proof = tree.get_proof(leaf_idx)
            if not proof:
                continue

            # 1. Flip position from left to right or right to left
            tampered_pos_proof = copy.deepcopy(proof)
            tampered_pos_proof[0]["position"] = (
                "left" if tampered_pos_proof[0]["position"] == "right" else "right"
            )
            assert verify_merkle_proof(leaves[leaf_idx], tampered_pos_proof, tree.root) is False

            # 2. Corrupt sibling hash
            tampered_hash_proof = copy.deepcopy(proof)
            orig_hex = tampered_hash_proof[0]["hash"]
            tampered_hex = ("0" if orig_hex[0] != "0" else "1") + orig_hex[1:]
            tampered_hash_proof[0]["hash"] = tampered_hex
            assert verify_merkle_proof(leaves[leaf_idx], tampered_hash_proof, tree.root) is False

            # 3. Truncate proof steps
            if len(proof) > 1:
                assert verify_merkle_proof(leaves[leaf_idx], proof[:-1], tree.root) is False

            # 4. Append bogus step
            bogus_step = {"position": "left", "hash": "00" * 32}
            assert verify_merkle_proof(leaves[leaf_idx], proof + [bogus_step], tree.root) is False


# =====================================================================
# Suite 5: Evidence Envelope Boundary & Schema Attacks
# =====================================================================

class TestEnvelopeAdversarialChallenge:
    """Stress-testing evidence envelope constraints and tamper detection."""

    def test_latitude_longitude_boundary_rejections(self, valid_envelope_dict):
        """Coordinates outside valid WGS84 bounds must raise ValueError."""
        invalid_coords = [
            (-90.000001, 0.0),
            (90.000001, 0.0),
            (0.0, -180.000001),
            (0.0, 180.000001),
            (100.0, 50.0),
            (-100.0, 50.0),
        ]
        for lat, lon in invalid_coords:
            d = copy.deepcopy(valid_envelope_dict)
            d["metadata"]["latitude"] = lat
            d["metadata"]["longitude"] = lon
            with pytest.raises(ValueError):
                EvidenceEnvelope.from_dict(d)

    def test_gps_accuracy_zero_or_negative_rejection(self, valid_envelope_dict):
        """GPS accuracy <= 0.0 must raise ValueError."""
        for bad_acc in [0.0, -0.001, -10.0]:
            d = copy.deepcopy(valid_envelope_dict)
            d["metadata"]["gps_accuracy"] = bad_acc
            with pytest.raises(ValueError):
                EvidenceEnvelope.from_dict(d)

    def test_sequence_number_zero_or_negative_rejection(self, valid_envelope_dict):
        """Sequence number < 1 must raise ValueError."""
        for bad_seq in [0, -1, -999]:
            d = copy.deepcopy(valid_envelope_dict)
            d["sequence_number"] = bad_seq
            with pytest.raises(ValueError):
                EvidenceEnvelope.from_dict(d)

    def test_image_hash_invalid_hex_rejection(self, valid_envelope_dict):
        """Image hash must be exactly 64 lowercase hex characters."""
        bad_hashes = [
            "",
            "a" * 63,
            "a" * 65,
            "A" * 64,  # from_dict normalizes lowercase, but let's test non-hex
            "g" * 64,  # Non-hex characters
            "a" * 63 + "z",
        ]
        for bh in bad_hashes:
            d = copy.deepcopy(valid_envelope_dict)
            d["image_hash"] = bh
            if bh.lower() == "a" * 64:
                continue
            with pytest.raises(ValueError):
                EvidenceEnvelope.from_dict(d)

    def test_lifecycle_stage_tampering_rejection(self, valid_envelope_dict):
        """Unsupported lifecycle stage must raise ValueError."""
        for bad_stage in ["INVALID_STAGE", "PLANTING", "WEEDING", "PROCESSED", ""]:
            d = copy.deepcopy(valid_envelope_dict)
            d["lifecycle_stage"] = bad_stage
            with pytest.raises(ValueError):
                EvidenceEnvelope.from_dict(d)
