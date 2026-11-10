"""Empirical Cryptographic Stress & Fuzz Harness (10,000 Iterations).

Executed by: challenger_m1_1 (Empirical Challenger)
"""

import hashlib
import random
import sys

from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

from crypto.ecdsa_p256 import (
    HALF_P256_ORDER,
    P256_ORDER,
    CryptographicError,
    InvalidSignatureFormatError,
    SignatureMalleabilityError,
    enforce_low_s,
    generate_keypair,
    normalize_low_s,
    sign,
    verify,
)
from crypto.merkle import MerkleTree, leaf_hash, node_hash, verify_merkle_proof
from crypto.rfc8785 import canonical_sha256, canonicalize, canonicalize_str


def main():
    print("=== STARTING DEEP CRYPTOGRAPHIC FUZZING (10,000 ITERATIONS) ===")

    priv, pub = generate_keypair()
    rng = random.Random(1337)

    # 1. High-s Malleability Fuzzing (1,000 runs)
    print("[1/4] Fuzzing high-s malleability across 1,000 random signatures...")
    for i in range(1000):
        msg = rng.randbytes(rng.randint(1, 256))
        der = sign(priv, msg)
        r, s = decode_dss_signature(der)
        if s > HALF_P256_ORDER:
            print(f"CRITICAL: sign() produced high-s at iteration {i}!")
            sys.exit(1)

        # Invert to high-s
        high_s = P256_ORDER - s
        der_high = encode_dss_signature(r, high_s)

        try:
            verify(pub, der_high, msg)
            print(f"CRITICAL: verify() accepted high-s at iteration {i}!")
            sys.exit(1)
        except SignatureMalleabilityError:
            pass  # Expected
        except Exception as e:
            print(f"UNEXPECTED EXCEPTION at iteration {i}: {type(e)} {e}")
            sys.exit(1)

    print("  -> 1,000/1,000 high-s signatures correctly raised SignatureMalleabilityError.")

    # 2. Corrupted DER Fuzzing (3,000 runs)
    print("[2/4] Fuzzing corrupted DER bytes across 3,000 mutations...")
    base_der = sign(priv, b"Fuzzing baseline payload")
    for i in range(3000):
        mutated = bytearray(base_der)
        mutation_type = rng.choice(
            ["bit_flip", "byte_replace", "truncate", "append_garbage", "insert_bytes"]
        )

        if mutation_type == "bit_flip":
            pos = rng.randint(0, len(mutated) - 1)
            mutated[pos] ^= 1 << rng.randint(0, 7)
        elif mutation_type == "byte_replace":
            pos = rng.randint(0, len(mutated) - 1)
            mutated[pos] ^= rng.randint(1, 255)
        elif mutation_type == "truncate":
            cut = rng.randint(0, len(mutated) - 1)
            mutated = mutated[:cut]
        elif mutation_type == "append_garbage":
            mutated.extend(rng.randbytes(rng.randint(1, 32)))
        elif mutation_type == "insert_bytes":
            pos = rng.randint(0, len(mutated) - 1)
            mutated[pos:pos] = rng.randbytes(rng.randint(1, 8))

        try:
            res = verify(pub, bytes(mutated), b"Fuzzing baseline payload")
            if res is True:
                print(f"CRITICAL: verify() verified corrupted DER at iteration {i}!")
                sys.exit(1)
        except SignatureMalleabilityError:
            pass  # If mutation happened to create a valid curve point with s > n/2
        except Exception as e:
            print(f"CRITICAL: unhandled exception in verify() at iteration {i}: {type(e)} {e}")
            sys.exit(1)

    print("  -> 3,000/3,000 corrupted DER mutations safely rejected without crashes.")

    # 3. RFC 8785 Canonicalization Fuzzing (3,000 runs)
    print("[3/4] Fuzzing RFC 8785 canonicalizer across 3,000 complex structures...")

    def gen_val(depth=0):
        if depth > 4:
            return rng.choice([None, True, False, rng.randint(-1000, 1000), "leaf"])
        t = rng.choice(
            ["null", "bool", "int", "float", "str", "surrogate", "list", "dict"]
        )
        if t == "null":
            return None
        if t == "bool":
            return rng.choice([True, False])
        if t == "int":
            return rng.randint(-1000000, 1000000)
        if t == "float":
            f = rng.uniform(-1000, 1000)
            return round(f, 4)
        if t == "str":
            return "".join(
                chr(rng.randint(32, 126)) for _ in range(rng.randint(0, 20))
            )
        if t == "surrogate":
            return chr(rng.randint(0x10000, 0x10FFFF))
        if t == "list":
            return [gen_val(depth + 1) for _ in range(rng.randint(0, 3))]
        if t == "dict":
            res = {}
            for _ in range(rng.randint(0, 4)):
                k_prefix = f"k_{rng.randint(0, 50)}"
                k_suffix = chr(rng.randint(0x10000, 0x10200)) if rng.random() > 0.5 else ""
                res[f"{k_prefix}_{k_suffix}"] = gen_val(depth + 1)
            return res

    for i in range(3000):
        struct = gen_val()
        b1 = canonicalize(struct)
        b2 = canonicalize(struct)
        if b1 != b2:
            print(f"CRITICAL: RFC 8785 determinism violated at iteration {i}!")
            sys.exit(1)

    print("  -> 3,000/3,000 RFC 8785 fuzzing runs 100% deterministic.")

    # 4. Merkle Tree Fuzzing (3,000 trees)
    print("[4/4] Fuzzing Merkle Tree odd-node promotion & proof verification across 3,000 trees...")
    for i in range(3000):
        n_leaves = rng.randint(1, 40)
        leaves = [rng.randbytes(rng.randint(1, 64)) for _ in range(n_leaves)]
        tree = MerkleTree(leaves)

        # Check CVE-2012-2459: if odd, duplicating last leaf must change root
        if n_leaves % 2 == 1:
            dup_tree = MerkleTree(leaves + [leaves[-1]])
            if tree.root == dup_tree.root:
                print(f"CRITICAL: CVE-2012-2459 collision at iteration {i}!")
                sys.exit(1)

        # Check all inclusion proofs in this tree
        for l_idx in range(n_leaves):
            proof = tree.get_proof(l_idx)
            if not verify_merkle_proof(leaves[l_idx], proof, tree.root):
                print(f"CRITICAL: Merkle proof failed at iteration {i}, leaf {l_idx}!")
                sys.exit(1)

    print("  -> 3,000/3,000 Merkle tree fuzzing runs 100% verified.")
    print("=== DEEP CRYPTOGRAPHIC FUZZING COMPLETE: ALL 10,000 CHECKS PASSED ===")


if __name__ == "__main__":
    main()
