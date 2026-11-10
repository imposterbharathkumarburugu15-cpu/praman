# PRAMAN Cryptographic Attack & Security Resilience Report

**Scope**: P-256 ECDSA, RFC 8785 Canonicalization, Merkle Tree Ingestion, and Checkpoint Security  
**Audit Date**: November 9, 2026  
**Test Suites**: `crypto/tests/`, `tests_e2e/tier1_features/`, `tests_e2e/tier2_boundaries/`, `tests_e2e/tier3_interactions/`  

---

## 1. Adversarial Test Inventory & Execution Summary

| Attack Vector | Simulated Fault / Mutation | Expected Outcome | Verified Result | Status |
|---|---|---|---|:---:|
| **A-01: Image Tampering** | Bit-flip in image bytes after envelope generation | Signature mismatch or SHA-256 digest divergence | Server raises `400 Bad Request: Image digest mismatch` | **PASS** |
| **A-02: Metadata Tampering** | Modified timestamp / farm_id / coordinates in JSON | Envelope hash diverges from signed hash | ECDSA verification fails (`InvalidSignature`) | **PASS** |
| **A-03: Sequence Replay** | Re-submitting identical signed envelope | Monotonic sequence violation | Server returns `409 Conflict` (or cached `200` on exact idempotency key) | **PASS** |
| **A-04: Sequence Gap / Downgrade** | Submitting sequence $N+2$ or $N-1$ | Sequence non-monotonicity | Out-of-order sequence rejected with `409 Conflict` | **PASS** |
| **A-05: High-$s$ Signature Malleability** | Inverting signature $s$ to $n - s$ | Malleable signature check | Rejected: strict enforcement $s \le \lfloor n/2 \rfloor$ | **PASS** |
| **A-06: Trailing Garbage in ASN.1 DER** | Appending extra bytes to DER signature | ASN.1 strict parsing error | Rejected: non-canonical DER length | **PASS** |
| **A-07: Merkle Second-Preimage Attack** | Crafting interior 64-byte node as leaf | Domain separation violation | Prevented by domain prefixes (`0x00` leaf, `0x01` internal) | **PASS** |
| **A-08: Odd-Node Duplication (CVE-2012-2459)** | Duplicating last node when leaf count is odd | Merkle root collision | Prevented by **odd-node promotion** (single node promoted directly) | **PASS** |
| **A-09: Tampered Inclusion Proof** | Modifying sibling hash in Merkle proof path | Root mismatch during client recalculation | Proof verification returns `False` | **PASS** |
| **A-10: Forged Checkpoint Root** | Replacing Merkle root with rogue root | Checkpoint signature verification failure | Checkpoint rejected: ECDSA signature invalid under ledger authority key | **PASS** |

---

## 2. In-Depth Technical Verification

### 2.1 RFC 8785 JSON Canonicalization (JCS)
- **UTF-16 Code Point Ordering**: Keys are strictly sorted by Unicode code point values.
- **Whitespace Stripping**: Zero insignificant whitespace outside strings.
- **Number Formatting**: Floats adhere strictly to ECMAScript standard (`78.48667` is not serialized with trailing exponential noise).

### 2.2 Merkle Tree Engine Security Invariants
- **Domain Separation**:
  $$\text{Leaf Hash} = H(0\text{x}00 \mathbin{\Vert} \text{Leaf Data})$$
  $$\text{Node Hash} = H(0\text{x}01 \mathbin{\Vert} \text{Left Child} \mathbin{\Vert} \text{Right Child})$$
- **Odd Node Promotion**:
  Whenever the layer has an odd count of nodes, the unmatched node is promoted to the next tier without duplication:
  $$\text{Promoted Node} = \text{Node}$$
  This mathematically eliminates Bitcoin-style Merkle malleability (CVE-2012-2459).

### 2.3 Proof Verification & Independence
- Proof recalculation runs independently on the client without contacting the server.
- WebCrypto API or pure-Python recalculation confirms matching root hash bit-for-bit against the authenticated checkpoint.

---

## Verdict: VALIDATED WITHIN TESTED SCOPE
All 10 simulated cryptographic attacks were rejected with exact expected failure modes. Zero cryptographic bypasses found.

