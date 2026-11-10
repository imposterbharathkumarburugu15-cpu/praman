# PRAMAN Threat Model & Security Architecture

## 1. Executive Summary & Security Objectives

PRAMAN establishes trusted provenance and evidence intelligence for agricultural practices in challenging rural operating environments. Operating in field conditions introduces distinct attack surfaces ranging from adversarial network attackers and compromised mobile operating systems to rural connectivity delays, replay attacks, and privacy leakage risks.

### Core Security Objectives:
1. **Authenticity & Non-Repudiation**: Evidence cannot be submitted or altered without the genuine private key of an enrolled, active device.
2. **Replay & Injection Resistance**: Adversaries cannot replay valid historical captures, intercept and reuse submissions, or inject duplicate proofs.
3. **Cryptographic Ledger Integrity**: Ledger batching must be immune to second-preimage attacks and leaf duplication exploits (CVE-2012-2459).
4. **Fairness to Smallholder Farmers**: The system must never reject or penalize legitimate rural farmers experiencing unavoidable network blackouts (e.g., monsoon floods).
5. **Human Safeguards Over AI**: Flawed or automated AI heuristics must never autonomously deprive farmers of accreditation or financial access.
6. **Consumer Privacy & Farm Protection**: Public provenance checks must enable cryptographic verification without exposing farmer identities or precise satellite coordinates to land grabbers or bad actors.

---

## 2. Threat Vector Analysis & Countermeasures

| Threat Vector | Severity | Attack Mechanism | PRAMAN Defensive Countermeasure |
|---|---|---|---|
| **Sequence Replay Attack** | **CRITICAL** | Intercepting a valid signed envelope and resubmitting it to claim duplicate subsidies or falsify agricultural progress. | **Row-Level Sequence Enforcement**: Per-device strictly monotonic sequence counter ($S = S_{\text{last}} + 1$) locked via database `SELECT ... FOR UPDATE` and unique constraint `uq_device_sequence`. Replays with differing hashes or out-of-order numbers are rejected with `HTTP 409 Conflict`. Idempotent retries (identical hash) return cached receipts (`HTTP 200 OK`). |
| **ECDSA Signature Malleability** | **HIGH** | Modifying an existing valid signature $(r, s)$ to $(r, n - s)$ to alter the signature byte representation without invalidating mathematical verification. | **Strict Low-$s$ Normalization**: The verification engine enforces $s \le \lfloor n/2 \rfloor$ for secp256r1. If $s > \lfloor n/2 \rfloor$, the signature is rejected with `SignatureMalleabilityError`. Both ASN.1 DER and IEEE P1363 formats enforce strict length and trailing-byte rejection. |
| **Merkle Leaf Duplication (CVE-2012-2459)** | **CRITICAL** | In a naive Merkle tree where odd nodes are duplicated ($H(A \parallel A)$), an attacker can forge a 64-leaf tree from a 65-leaf tree by substituting an internal node hash as an unverified leaf. | **Odd-Node Promotion Convention**: Unpaired trailing nodes at odd-sized levels are never duplicated; they are promoted directly to the next level unchanged: $L_{next} = \text{promote}(N_{last})$. Verified across test vectors from 1 to 35 leaves. |
| **Second-Preimage Attack on Merkle Tree** | **HIGH** | Supplying an internal node $(L \parallel R)$ as a leaf node to produce an identical root hash. | **Cryptographic Domain Separation**: 1-byte domain prefixes separate leaf and internal node hashing: $H_{\text{leaf}} = \text{SHA-256}(0\text{x}00 \parallel \text{data})$ and $H_{\text{node}} = \text{SHA-256}(0\text{x}01 \parallel L \parallel R)$. |
| **False Classification of Monsoon Offline Delay** | **HIGH** | Classifying delayed submissions (14 to 60+ days) from flood-isolated regions as fraudulent replay or expired evidence. | **Delay Legitimacy Evaluator**: Capture timestamp is cryptographically bound inside the envelope signed at acquisition time. Offline synchronization delays are classified as legitimate field conditions (`IS_LEGITIMATE_DELAY: True`) and routed to normal verification rather than fraud blacklists. |
| **Spatial Spoofing & Degenerate Boundaries** | **MEDIUM** | Submitting self-intersecting "bowtie" polygons, collinear lines, or out-of-bounds coordinates to manipulate land subsidies. | **Pure-Python Spatial Validator**: Enforces WGS84 coordinate bounds ($\text{lat} \in [-90, 90], \text{lon} \in [-180, 180]$), minimum 3 vertices, ring closure normalization, Shoelace formula non-zero area check, and line segment cross-product intersection detection. |
| **Farmer PII & Exact GPS Leakage** | **CRITICAL** | Public QR verification exposing farmer phone numbers, names, or exact parcel coordinates, leading to harassment or predatory surveillance. | **Sanitized Public Verification Projection**: The public verification endpoint programmatically scrubs all PII and fine-grained GPS coordinates, returning only coarse regional indicators (e.g., "Adilabad, Telangana"), crop type, timestamp, Merkle proof, and trusted authority checkpoint. Payload is validated against forbidden key denylists before serialization. |
| **Autonomous AI Denial of Livelihood** | **HIGH** | Computer vision model misclassifying a legitimate crop or blurry photo and permanently rejecting a farmer's evidence. | **Never-Autonomous-Reject Rule**: The local AI engine is restricted to triage and advisory duties. Low-scoring, blurry, or overexposed images are routed to human reviewers (`PENDING_REVIEW`) with clear diagnostic explanation cards. |
| **Untrusted AI Manipulation Detection Claims** | **MEDIUM** | Marketing experimental or unvalidated synthetic/AI-generated image detectors as infallible fraud blockers. | **4-Tier Model Registry Governance**: Explicitly separates `deterministic`, `pretrained`, `custom`, and `heuristic` tiers. Experimental manipulation detectors are explicitly marked `UNVALIDATED` with recorded failure modes and zero fabricated confidence metrics. |

---

## 3. Cryptographic Attack Surface & Formal Proofs

### 3.1 Low-$s$ Invariant Proof
For any valid ECDSA signature $(r, s)$ on curve $y^2 = x^3 - 3x + b \pmod p$ with base point order $n$:
Since $(-k) \cdot G = -(k \cdot G)$, the pair $(r, n - s \pmod n)$ is also a valid signature for the same hash $e$.
To eliminate third-party malleability:
$$\text{Reject if } s > \frac{n - 1}{2}$$
In PRAMAN's `crypto/ecdsa_p256.py`:
```python
SECP256R1_ORDER = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
HALF_ORDER = SECP256R1_ORDER // 2

if s > HALF_ORDER:
    raise SignatureMalleabilityError("Signature has high-s value (malleable); must be <= half curve order")
```

### 3.2 Odd-Node Promotion Algorithm
To prevent CVE-2012-2459:
```
Given level nodes [N_0, N_1, N_2] (length = 3):
- Pair (N_0, N_1) -> P_0 = SHA-256(0x01 || N_0 || N_1)
- Node N_2 has no pair:
    DO NOT COMPUTE SHA-256(0x01 || N_2 || N_2)  <-- VULNERABLE
    INSTEAD PROMOTE: P_1 = N_2                  <-- SECURE
Next level = [P_0, P_1]
```

---

## 4. Operational Security & Physical Device Protection

1. **Hardware-Backed Keystore**:
   - Private keys are generated inside the Android Keystore system (`KeyGenParameterSpec.Builder(alias, PURPOSE_SIGN)`).
   - Private key material is marked non-exportable (`setUserAuthenticationRequired(false)`, `setDigests(DIGEST_SHA256)`).
2. **Server-Side Key Revocation**:
   - If a device is reported lost or stolen, an administrator invokes `PATCH /api/v1/devices/{device_id}/status` with `status: REVOKED`.
   - Any subsequent evidence ingestion signed by the revoked device key is immediately rejected with `HTTP 400 Bad Request`.
3. **Database Audit Immutability**:
   - The `audit_log` table cannot be altered or purged by database administrators without dropping triggers, providing tamper-evident forensic guarantees.

