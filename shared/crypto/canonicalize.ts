/**
 * RFC 8785 JSON Canonicalization Scheme (JCS) implementation in TypeScript.
 *
 * Rules:
 * - Deterministic lexicographical property key sorting by UTF-16 code units.
 * - ECMAScript number formatting (-0 -> "0", integer floats without decimal point, exponential lowercase 'e').
 * - Direct string construction avoiding V8 plain object numeric property reordering.
 * - Rejection of NaN, Infinity, -Infinity.
 * - Minimal JSON string escaping.
 */

export function canonicalize(val: unknown): string {
  if (val === null) {
    return "null";
  }
  if (typeof val === "boolean") {
    return val ? "true" : "false";
  }
  if (typeof val === "number") {
    if (isNaN(val) || !isFinite(val)) {
      throw new TypeError("NaN and Infinity are not valid in JSON / RFC 8785");
    }
    if (Object.is(val, -0) || val === 0) {
      return "0";
    }
    return val.toString();
  }
  if (typeof val === "string") {
    return JSON.stringify(val);
  }
  if (Array.isArray(val)) {
    return "[" + val.map((x) => canonicalize(x)).join(",") + "]";
  }
  if (typeof val === "object") {
    const record = val as Record<string, unknown>;
    const keys = Object.keys(record).sort((a, b) => {
      return a < b ? -1 : a > b ? 1 : 0;
    });
    const items = keys.map((k) => {
      const keyStr = JSON.stringify(k);
      const valStr = canonicalize(record[k]);
      return `${keyStr}:${valStr}`;
    });
    return "{" + items.join(",") + "}";
  }
  throw new TypeError(`Cannot canonicalize value of type ${typeof val}`);
}

export function canonicalizeBytes(val: unknown): Uint8Array {
  const str = canonicalize(val);
  return new TextEncoder().encode(str);
}

/**
 * Compute SHA-256 hex string over canonicalized object using Web Crypto or Node.js crypto.
 */
export async function canonicalSha256(val: unknown): Promise<string> {
  const bytes = canonicalizeBytes(val);
  if (typeof crypto !== "undefined" && crypto.subtle) {
    const digestBuf = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digestBuf))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }
  // Node.js fallback
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const nodeCrypto = require("crypto");
  return nodeCrypto.createHash("sha256").update(bytes).digest("hex");
}
