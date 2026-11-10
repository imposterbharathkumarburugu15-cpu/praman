/**
 * Deterministic domain-separated Merkle Tree with odd-node promotion
 * and inclusion proof generator/verifier in TypeScript / Web Crypto.
 */

import type { InclusionProofStep } from "./types.ts";

export const LEAF_PREFIX = new Uint8Array([0x00]);
export const NODE_PREFIX = new Uint8Array([0x01]);

function getSubtle(): SubtleCrypto {
  if (typeof crypto !== "undefined" && crypto.subtle) {
    return crypto.subtle;
  }
  // Node.js fallback
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require("crypto").webcrypto.subtle;
}

export function hexToBytes(hex: string): Uint8Array {
  const cleanHex = hex.trim().toLowerCase();
  if (cleanHex.length % 2 !== 0) {
    throw new Error(`Invalid hex string length: ${cleanHex.length}`);
  }
  const bytes = new Uint8Array(cleanHex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(cleanHex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Compute domain-separated leaf hash: SHA-256(0x00 || data).
 */
export async function leafHash(data: Uint8Array): Promise<Uint8Array> {
  const subtle = getSubtle();
  const buf = new Uint8Array(1 + data.length);
  buf[0] = 0x00;
  buf.set(data, 1);
  const digest = await subtle.digest("SHA-256", buf);
  return new Uint8Array(digest);
}

export async function leafHashHex(data: Uint8Array): Promise<string> {
  const hash = await leafHash(data);
  return bytesToHex(hash);
}

/**
 * Compute domain-separated internal node hash: SHA-256(0x01 || left || right).
 */
export async function nodeHash(left: Uint8Array, right: Uint8Array): Promise<Uint8Array> {
  if (left.length !== 32 || right.length !== 32) {
    throw new Error(`Node hash inputs must be 32 bytes each, got left=${left.length}, right=${right.length}`);
  }
  const subtle = getSubtle();
  const buf = new Uint8Array(65);
  buf[0] = 0x01;
  buf.set(left, 1);
  buf.set(right, 33);
  const digest = await subtle.digest("SHA-256", buf);
  return new Uint8Array(digest);
}

export async function nodeHashHex(left: Uint8Array, right: Uint8Array): Promise<string> {
  const hash = await nodeHash(left, right);
  return bytesToHex(hash);
}

export class MerkleTree {
  public readonly rawLeaves: Uint8Array[];
  public levels: Uint8Array[][] = [];
  public root: Uint8Array | null = null;
  public rootHex: string | null = null;

  constructor(leaves: Uint8Array[]) {
    this.rawLeaves = [...leaves];
  }

  public async build(): Promise<void> {
    if (this.rawLeaves.length === 0) {
      this.levels = [[]];
      this.root = null;
      this.rootHex = null;
      return;
    }

    // Level 0: leaf hashes
    const level0: Uint8Array[] = [];
    for (const leaf of this.rawLeaves) {
      level0.push(await leafHash(leaf));
    }
    this.levels = [level0];

    let currentLevel = level0;
    while (currentLevel.length > 1) {
      const nextLevel: Uint8Array[] = [];
      let i = 0;
      const n = currentLevel.length;
      while (i < n) {
        if (i + 1 < n) {
          const parent = await nodeHash(currentLevel[i], currentLevel[i + 1]);
          nextLevel.push(parent);
          i += 2;
        } else {
          // Odd-node promotion: promote trailing node without duplication
          nextLevel.push(currentLevel[i]);
          i += 1;
        }
      }
      this.levels.push(nextLevel);
      currentLevel = nextLevel;
    }

    this.root = this.levels[this.levels.length - 1][0];
    this.rootHex = bytesToHex(this.root);
  }

  public getProof(leafIndex: number): InclusionProofStep[] {
    if (leafIndex < 0 || leafIndex >= this.rawLeaves.length) {
      throw new RangeError(`Leaf index ${leafIndex} out of bounds [0, ${this.rawLeaves.length})`);
    }

    const proof: InclusionProofStep[] = [];
    let idx = leafIndex;

    for (let lvl = 0; lvl < this.levels.length - 1; lvl++) {
      const levelNodes = this.levels[lvl];
      if (idx % 2 === 0) {
        if (idx + 1 < levelNodes.length) {
          proof.push({
            position: "right",
            hash: bytesToHex(levelNodes[idx + 1]),
          });
        }
        // If node was promoted without pairing, omit sibling step
      } else {
        proof.push({
          position: "left",
          hash: bytesToHex(levelNodes[idx - 1]),
        });
      }
      idx = Math.floor(idx / 2);
    }

    return proof;
  }

  public async verifyLeaf(leafIndex: number): Promise<boolean> {
    if (!this.rootHex) return false;
    const proof = this.getProof(leafIndex);
    return verifyMerkleProof(this.rawLeaves[leafIndex], proof, this.rootHex);
  }
}

/**
 * Independently verify a Merkle inclusion proof against an expected root hex.
 */
export async function verifyMerkleProof(
  leafData: Uint8Array,
  proof: InclusionProofStep[],
  expectedRootHex: string
): Promise<boolean> {
  try {
    let currentHash = await leafHash(leafData);

    for (const step of proof) {
      const siblingHash = hexToBytes(step.hash);
      if (siblingHash.length !== 32) {
        return false;
      }
      if (step.position === "right") {
        currentHash = await nodeHash(currentHash, siblingHash);
      } else if (step.position === "left") {
        currentHash = await nodeHash(siblingHash, currentHash);
      } else {
        throw new Error(`Invalid proof position: ${step.position}`);
      }
    }

    const expectedBytes = hexToBytes(expectedRootHex);
    if (currentHash.length !== expectedBytes.length) {
      return false;
    }
    for (let i = 0; i < currentHash.length; i++) {
      if (currentHash[i] !== expectedBytes[i]) {
        return false;
      }
    }
    return true;
  } catch {
    return false;
  }
}
