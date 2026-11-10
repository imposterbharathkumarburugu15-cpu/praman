# PRAMAN Cryptographic Specification

## 1. Overview & Primitives

PRAMAN implements a deterministic, zero-trust cryptographic pipeline ensuring data provenance, tamper detection, and auditability from mobile capture to public verification.

### Core Cryptographic Primitives:
- **Hash Function**: SHA-256 (FIPS 180-4), 256-bit output.
- **Canonicalization**: RFC 8785 JSON Canonicalization Scheme (JCS).
- **Digital Signatures**: ECDSA over curve NIST P-256 (secp256r1 / prime256v1) with SHA-256.
- **Signature Encodings**:
  - ASN.1 DER (X.690 / RFC 3279).
  - IEEE P1363 / ANSI X9.62 (fixed 64-byte $r \parallel s$).
- **Merkle Ledger**: Domain-separated binary Merkle tree with odd-node promotion convention preventing CVE-2012-2459.

---

## 2. RFC 8785 JSON Canonicalization Scheme (JCS)

To ensure that cryptographic signatures and hashes over JSON payloads are strictly deterministic and invariant across Python, TypeScript/JavaScript, and mobile environments, PRAMAN enforces RFC 8785 rules.

### Canonicalization Algorithm:
1. **Whitespace Elimination**: All structural whitespace between tokens, brackets, and separators is stripped (`separators=(',', ':')`).
2. **Deterministic Object Key Sorting**:
   - Keys are sorted by their UTF-16 code unit values in lexicographical order.
   - For supplementary characters (e.g., emoji outside BMP), sorting corresponds to comparing surrogate pairs bit-for-bit.
3. **ECMAScript Number Formatting (IEEE 754-2008 Double Precision)**:
   - Integers are rendered without decimal points or exponent notation (e.g., `42`).
   - Negative zero (`-0`) is normalized to positive zero (`0`).
   - Fractional numbers omit insignificant trailing zeros (e.g., `17.385000` $\to$ `17.385`).
4. **String Escaping**:
   - Only quotation mark (`"`), backslash (`\`), and control characters (U+0000 through U+001F) are escaped.
   - All other unicode characters (including Telugu, Hindi, and Greek scripts) are emitted verbatim as UTF-8 bytes without `\uXXXX` escaping.

---

## 3. P-256 ECDSA Digital Signatures & Low-$s$ Invariant

PRAMAN uses NIST P-256 with curve parameter domain:
$$\begin{aligned}
p &= 2^{256} - 2^{224} + 2^{192} + 2^{96} - 1 \\
n &= \text{0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551} \\
\lfloor n/2 \rfloor &= \text{0x7FFFFFFF800000007FFFFFFFFFFFFFFFDE737D56D38BCE4279DC65617E3192A8}
\end{aligned}$$

### Low-$s$ Normalization & Malleability Rejection:
For every signature $(r, s)$:
1. Range validation: $1 \le r \le n - 1$ and $1 \le s \le n - 1$.
2. **Low-$s$ constraint**:
   $$s \le \lfloor n/2 \rfloor$$
3. If signing produces $s > \lfloor n/2 \rfloor$, the signer normalizes:
   $$s \leftarrow n - s$$
4. The backend verifier strictly rejects any incoming signature where $s > \lfloor n/2 \rfloor$ with a `SignatureMalleabilityError`.

### Signature Formats:
- **ASN.1 DER**:
  ```
  SEQUENCE {
      INTEGER r
      INTEGER s
  }
  ```
  Strict DER requires:
  - Minimum length representation of integers (no unnecessary leading zero bytes except to ensure positive sign).
  - Exact sequence length match; zero trailing garbage bytes allowed.
- **IEEE P1363 (Raw 64 bytes)**:
  - Exactly 64 bytes consisting of big-endian 32-byte integer $r$ concatenated with big-endian 32-byte integer $s$.

---

## 4. Evidence Envelope Specification

The canonical evidence envelope binds the cryptographic hash of the raw image to spatial, temporal, and sequence metadata.

```json
{
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
    "longitude": 78.486671
  },
  "schema_version": "1.0",
  "sequence_number": 42
}
```

### Signature Verification Workflow:
1. Parse the incoming JSON envelope.
2. Produce canonical UTF-8 bytes: $B = \text{canonicalize}(E)$.
3. Compute message digest: $D = \text{SHA-256}(B)$.
4. Extract P-256 public key corresponding to `device_id`.
5. Verify low-$s$ constraint on signature $(r, s)$.
6. Verify ECDSA signature $(r, s)$ against digest $D$ with public key.
7. Verify binary image SHA-256 matches `image_hash`.

---

## 5. Domain-Separated Merkle Tree & Audit Proofs

### 5.1 Domain Separation Formulae
To prevent second-preimage attacks where an internal node's preimage is submitted as a leaf:
$$\begin{aligned}
H_{\text{leaf}}(L) &= \text{SHA-256}(0\text{x}00 \parallel L) \\
H_{\text{node}}(Left, Right) &= \text{SHA-256}(0\text{x}01 \parallel Left \parallel Right)
\end{aligned}$$

### 5.2 Odd-Node Promotion Algorithm
To prevent CVE-2012-2459 (Bitcoin leaf duplication vulnerability):
```python
def build_next_level(nodes: List[bytes]) -> List[bytes]:
    next_level = []
    n = len(nodes)
    for i in range(0, n - 1, 2):
        parent = sha256(b"\x01" + nodes[i] + nodes[i+1]).digest()
        next_level.append(parent)
    if n % 2 == 1:
        # Promote odd trailing node without pairing or duplication
        next_level.append(nodes[-1])
    return next_level
```

### 5.3 Inclusion Proof Verification
An inclusion proof consists of the target leaf data and an ordered list of sibling audit steps:
```json
[
  {"position": "right", "hash": "1a2b3c..."},
  {"position": "left", "hash": "4d5e6f..."}
]
```

Algorithm:
1. Compute starting accumulator: $H = \text{SHA-256}(0\text{x}00 \parallel \text{canonical\_leaf\_bytes})$.
2. For each step $(pos, sibling)$:
   - If $pos = \text{"right"}$: $H \leftarrow \text{SHA-256}(0\text{x}01 \parallel H \parallel sibling)$.
   - If $pos = \text{"left"}$: $H \leftarrow \text{SHA-256}(0\text{x}01 \parallel sibling \parallel H)$.
3. Assert that final $H$ matches expected `merkle_root`.

---

## 6. Official Canonical Test Vectors

The following test vectors are implemented in `crypto/tests/test_vectors.py` and must pass in all target environments:

### Vector 1: Single Leaf ($N=1$)
- **Leaf Data**: `b"evidence-1"`
- **Leaf Hash**: `SHA-256(0x00 || b"evidence-1")` = `64-char hex`
- **Root Hash**: Identical to leaf hash. Proof: `[]` (empty list).

### Vector 2: Two Leaves ($N=2$)
- **Leaf 0 Data**: `b"evidence-1"`
- **Leaf 1 Data**: `b"evidence-2"`
- **Internal Node**: `SHA-256(0x01 || H0 || H1)`
- **Root Hash**: Value of internal node.

### Vector 3: Three Leaves (Odd Promotion $N=3$)
- **Leaf 0, 1, 2**: $H_0, H_1, H_2$
- **Level 1**: $P_0 = \text{SHA-256}(0\text{x}01 \parallel H_0 \parallel H_1)$, $P_1 = H_2$ (promoted).
- **Level 2 (Root)**: $\text{SHA-256}(0\text{x}01 \parallel P_0 \parallel P_1)$.

### Vector 4: Four Leaves ($N=4$)
- Balanced 2-level binary tree.

