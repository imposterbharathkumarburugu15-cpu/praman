/**
 * NIST P-256 (secp256r1) ECDSA wire format conversions, low-s enforcement,
 * and Web Crypto verification for TypeScript / React Native / Browser.
 */

// NIST P-256 curve order n
export const P256_ORDER =
  0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551n;

// Half order threshold: floor(n / 2)
export const HALF_P256_ORDER = P256_ORDER / 2n;

// Standard 26-byte SPKI header prefix for NIST P-256 public keys
export const P256_SPKI_PREFIX = new Uint8Array([
  0x30, 0x59, 0x30, 0x13, 0x06, 0x07, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02,
  0x01, 0x06, 0x08, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07, 0x03,
  0x42, 0x00,
]);

/**
 * Convert an ASN.1 DER signature to 64-byte raw IEEE P1363 (r || s).
 */
export function derToP1363(der: Uint8Array): Uint8Array {
  if (der.length < 8 || der[0] !== 0x30) {
    throw new Error("Invalid ASN.1 DER signature header");
  }

  let offset = 1;
  let seqLen = der[offset++];
  if ((seqLen & 0x80) !== 0) {
    const bytesCount = seqLen & 0x7f;
    seqLen = 0;
    for (let i = 0; i < bytesCount; i++) {
      seqLen = (seqLen << 8) | der[offset++];
    }
  }

  // Parse r INTEGER
  if (der[offset++] !== 0x02) {
    throw new Error("Expected ASN.1 INTEGER tag for r");
  }
  const rLen = der[offset++];
  let rBytes = der.subarray(offset, offset + rLen);
  offset += rLen;
  if (rBytes.length > 32) {
    if (rBytes.length === 33 && rBytes[0] === 0x00) {
      rBytes = rBytes.subarray(1);
    } else {
      throw new Error(`Invalid r integer length: ${rBytes.length}`);
    }
  }

  // Parse s INTEGER
  if (der[offset++] !== 0x02) {
    throw new Error("Expected ASN.1 INTEGER tag for s");
  }
  const sLen = der[offset++];
  let sBytes = der.subarray(offset, offset + sLen);
  offset += sLen;
  if (sBytes.length > 32) {
    if (sBytes.length === 33 && sBytes[0] === 0x00) {
      sBytes = sBytes.subarray(1);
    } else {
      throw new Error(`Invalid s integer length: ${sBytes.length}`);
    }
  }

  const p1363 = new Uint8Array(64);
  p1363.set(rBytes, 32 - rBytes.length);
  p1363.set(sBytes, 64 - sBytes.length);
  return p1363;
}

/**
 * Convert 64-byte raw IEEE P1363 signature (r || s) to ASN.1 DER.
 */
export function p1363ToDer(p1363: Uint8Array): Uint8Array {
  if (p1363.length !== 64) {
    throw new Error(`Invalid IEEE P1363 signature length: expected 64, got ${p1363.length}`);
  }

  function encodeInteger(bytes: Uint8Array): Uint8Array {
    let start = 0;
    while (start < bytes.length - 1 && bytes[start] === 0x00) {
      start++;
    }
    let trimmed = bytes.subarray(start);
    if ((trimmed[0] & 0x80) !== 0) {
      const padded = new Uint8Array(trimmed.length + 1);
      padded[0] = 0x00;
      padded.set(trimmed, 1);
      trimmed = padded;
    }
    const result = new Uint8Array(trimmed.length + 2);
    result[0] = 0x02; // INTEGER tag
    result[1] = trimmed.length;
    result.set(trimmed, 2);
    return result;
  }

  const rEnc = encodeInteger(p1363.subarray(0, 32));
  const sEnc = encodeInteger(p1363.subarray(32, 64));
  const totalLen = rEnc.length + sEnc.length;

  const der = new Uint8Array(totalLen + 2);
  der[0] = 0x30; // SEQUENCE tag
  der[1] = totalLen;
  der.set(rEnc, 2);
  der.set(sEnc, 2 + rEnc.length);
  return der;
}

/**
 * Extract scalar s from IEEE P1363 signature as BigInt.
 */
export function extractS(p1363Sig: Uint8Array): bigint {
  if (p1363Sig.length !== 64) {
    throw new Error(`Expected 64-byte P1363 signature, got ${p1363Sig.length}`);
  }
  const sBytes = p1363Sig.subarray(32, 64);
  let s = 0n;
  for (let i = 0; i < 32; i++) {
    s = (s << 8n) | BigInt(sBytes[i]);
  }
  return s;
}

/**
 * Check if signature s is low-s (s <= n // 2).
 */
export function isLowS(p1363Sig: Uint8Array): boolean {
  const s = extractS(p1363Sig);
  return s <= HALF_P256_ORDER;
}

/**
 * Normalize P1363 signature to low-s form.
 */
export function normalizeLowS(p1363Sig: Uint8Array): Uint8Array {
  const s = extractS(p1363Sig);
  if (s <= HALF_P256_ORDER) {
    return p1363Sig;
  }
  const lowS = P256_ORDER - s;
  const result = new Uint8Array(p1363Sig);
  for (let i = 31; i >= 0; i--) {
    result[32 + i] = Number((lowS >> BigInt((31 - i) * 8)) & 0xffn);
  }
  return result;
}

/**
 * Convert 65-byte raw uncompressed EC point (0x04 || X || Y) to 91-byte SubjectPublicKeyInfo (SPKI) DER.
 */
export function rawPointToSpki(rawPoint: Uint8Array): Uint8Array {
  if (rawPoint.length !== 65 || rawPoint[0] !== 0x04) {
    throw new Error("Invalid raw uncompressed P-256 public key point (expected 65 bytes starting with 0x04)");
  }
  const spki = new Uint8Array(P256_SPKI_PREFIX.length + rawPoint.length);
  spki.set(P256_SPKI_PREFIX, 0);
  spki.set(rawPoint, P256_SPKI_PREFIX.length);
  return spki;
}

/**
 * Convert 91-byte SPKI DER public key to 65-byte raw uncompressed point.
 */
export function spkiToRawPoint(spki: Uint8Array): Uint8Array {
  if (spki.length !== 91) {
    throw new Error(`Expected 91-byte SPKI DER public key, got ${spki.length}`);
  }
  return spki.subarray(26);
}

/**
 * Verify a P-256 ECDSA signature over SHA-256(data) using Web Crypto API.
 */
export async function verifyP256Signature(
  publicKey: Uint8Array, // 91-byte SPKI or 65-byte raw uncompressed point
  signature: Uint8Array, // ASN.1 DER or 64-byte IEEE P1363
  data: Uint8Array
): Promise<boolean> {
  try {
    let p1363Sig = signature;
    if (signature.length !== 64 && signature[0] === 0x30) {
      p1363Sig = derToP1363(signature);
    }
    if (p1363Sig.length !== 64) {
      return false;
    }

    const subtle =
      typeof crypto !== "undefined" && crypto.subtle
        ? crypto.subtle
        : // eslint-disable-next-line @typescript-eslint/no-require-imports
          require("crypto").webcrypto.subtle;

    let cryptoKey: CryptoKey;
    if (publicKey.length === 65 && publicKey[0] === 0x04) {
      cryptoKey = await subtle.importKey(
        "raw",
        publicKey,
        { name: "ECDSA", namedCurve: "P-256" },
        false,
        ["verify"]
      );
    } else {
      cryptoKey = await subtle.importKey(
        "spki",
        publicKey,
        { name: "ECDSA", namedCurve: "P-256" },
        false,
        ["verify"]
      );
    }

    return await subtle.verify(
      { name: "ECDSA", hash: { name: "SHA-256" } },
      cryptoKey,
      p1363Sig,
      data
    );
  } catch {
    return false;
  }
}
