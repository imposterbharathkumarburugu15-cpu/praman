"""Deterministic domain-separated Merkle Tree with odd-node promotion and inclusion proofs.

Features:
- RFC 6962-style domain separation:
    Leaf hash:          H_leaf = SHA-256(0x00 || data)
    Internal node hash: H_node = SHA-256(0x01 || left || right)
- Odd-node promotion:
    When a level has an odd count of nodes (2k + 1), the trailing node is promoted
    directly to the next level without duplication and without rehashing.
    This guarantees immunity against the Bitcoin CVE-2012-2459 duplication attack.
- Compact inclusion proof generation and independent verification.
- Supports variable-depth audit paths for promoted nodes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Union

LEAF_PREFIX: bytes = b"\x00"
NODE_PREFIX: bytes = b"\x01"


def leaf_hash(data: bytes) -> bytes:
    """Compute domain-separated leaf hash: SHA-256(0x00 || data)."""
    return hashlib.sha256(LEAF_PREFIX + data).digest()


def leaf_hash_hex(data: bytes) -> str:
    """Compute 64-hex domain-separated leaf hash."""
    return leaf_hash(data).hex()


def node_hash(left: bytes, right: bytes) -> bytes:
    """Compute domain-separated internal node hash: SHA-256(0x01 || left || right)."""
    if len(left) != 32 or len(right) != 32:
        raise ValueError(
            f"Node hash inputs must be 32 bytes each, got left={len(left)}, right={len(right)}"
        )
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def node_hash_hex(left: bytes, right: bytes) -> str:
    """Compute 64-hex domain-separated internal node hash."""
    return node_hash(left, right).hex()


@dataclass
class InclusionProofStep:
    """A single step in a Merkle inclusion proof."""

    position: Literal["left", "right"]
    hash: str  # 64-character lowercase hex string

    def to_dict(self) -> Dict[str, str]:
        return {"position": self.position, "hash": self.hash.lower()}


class MerkleTree:
    """Deterministic domain-separated Merkle Tree with odd-node promotion."""

    def __init__(self, leaves_data: Optional[List[bytes]] = None):
        """Construct tree from a list of binary leaf payloads.

        Args:
            leaves_data: List of leaf byte payloads (e.g. canonical envelope bytes).
        """
        self.raw_leaves: List[bytes] = list(leaves_data or [])
        self.levels: List[List[bytes]] = []
        self._build_tree()

    # Static method aliases for consistency with E2E test oracle
    hash_leaf = staticmethod(leaf_hash)
    hash_internal_node = staticmethod(node_hash)

    def _build_tree(self) -> None:
        """Construct tree levels from leaf hashes using odd-node promotion."""
        if not self.raw_leaves:
            self.levels = [[]]
            return

        # Level 0: Leaf hashes with 0x00 domain separation
        current_level = [leaf_hash(leaf) for leaf in self.raw_leaves]
        self.levels = [current_level]

        while len(current_level) > 1:
            next_level: List[bytes] = []
            i = 0
            n = len(current_level)
            while i < n:
                if i + 1 < n:
                    # Pair nodes with 0x01 domain separation
                    parent = node_hash(current_level[i], current_level[i + 1])
                    next_level.append(parent)
                    i += 2
                else:
                    # Odd-node promotion: promote trailing node without duplication or hashing
                    next_level.append(current_level[i])
                    i += 1
            self.levels.append(next_level)
            current_level = next_level

    @property
    def root(self) -> Optional[bytes]:
        """Return 32-byte binary Merkle root or None if tree is empty."""
        if not self.levels or not self.levels[-1]:
            return None
        return self.levels[-1][0]

    @property
    def root_hex(self) -> Optional[str]:
        """Return 64-character lowercase hex Merkle root or None if tree is empty."""
        r = self.root
        return r.hex() if r is not None else None

    @property
    def leaf_count(self) -> int:
        """Return number of leaves."""
        return len(self.raw_leaves)

    def get_proof(self, leaf_index: int) -> List[Dict[str, str]]:
        """Generate a compact Merkle inclusion proof for the leaf at `leaf_index`.

        Omits sibling steps for odd trailing nodes promoted without pairing.

        Args:
            leaf_index: Zero-based leaf index.

        Returns:
            List[Dict[str, str]]: Ordered audit path steps, e.g.:
            [{"position": "right", "hash": "abc..."}, {"position": "left", "hash": "def..."}]

        Raises:
            IndexError: If leaf_index is out of bounds.
        """
        if leaf_index < 0 or leaf_index >= len(self.raw_leaves):
            raise IndexError(
                f"Leaf index {leaf_index} out of bounds [0, {len(self.raw_leaves)})"
            )

        proof: List[Dict[str, str]] = []
        idx = leaf_index

        # Traverse from level 0 up to the level just below root
        for lvl in range(len(self.levels) - 1):
            level_nodes = self.levels[lvl]
            if idx % 2 == 0:
                # Left node in pair: sibling is to the right if it exists
                if idx + 1 < len(level_nodes):
                    proof.append(
                        {"position": "right", "hash": level_nodes[idx + 1].hex()}
                    )
                else:
                    # Node was promoted without pairing at this level; omit sibling step
                    pass
            else:
                # Right node in pair: sibling is to the left
                proof.append({"position": "left", "hash": level_nodes[idx - 1].hex()})
            # Promoted/paired node's index at next level
            idx = idx // 2

        return proof

    # Compatibility alias
    get_inclusion_proof = get_proof

    def verify_leaf(self, leaf_index: int) -> bool:
        """Self-verify that the leaf at `leaf_index` satisfies its inclusion proof."""
        if self.root is None:
            return False
        proof = self.get_proof(leaf_index)
        leaf_data = self.raw_leaves[leaf_index]
        return verify_merkle_proof(leaf_data, proof, self.root)

    @classmethod
    def verify_inclusion_proof(
        cls,
        leaf_data: bytes,
        proof: List[Dict[str, str]],
        expected_root: Union[bytes, str],
    ) -> bool:
        """Classmethod alias for independent proof verification."""
        return verify_merkle_proof(leaf_data, proof, expected_root)


def verify_merkle_proof(
    leaf_data: bytes,
    proof: List[Dict[str, str]],
    expected_root: Union[bytes, str],
) -> bool:
    """Verify a Merkle inclusion proof independently against expected root.

    Recomputes the root starting from SHA-256(0x00 || leaf_data) and applying
    each step with 0x01 domain-separated internal node hashing.

    Args:
        leaf_data: The original leaf byte payload.
        proof: List of proof step dictionaries with 'position' ('left'|'right') and 'hash'.
        expected_root: Expected 32-byte binary or 64-hex Merkle root.

    Returns:
        bool: True if computed root matches expected_root, False otherwise.
    """
    try:
        current_hash = leaf_hash(leaf_data)

        for step in proof:
            sibling_hex = step["hash"]
            sibling_hash = (
                bytes.fromhex(sibling_hex)
                if isinstance(sibling_hex, str)
                else sibling_hex
            )
            if len(sibling_hash) != 32:
                return False

            position = step["position"]
            if position == "right":
                current_hash = node_hash(current_hash, sibling_hash)
            elif position == "left":
                current_hash = node_hash(sibling_hash, current_hash)
            else:
                raise ValueError(f"Invalid position in proof: {position}")

        expected_bytes: bytes
        if isinstance(expected_root, str):
            expected_bytes = bytes.fromhex(expected_root)
        else:
            expected_bytes = bytes(expected_root)

        return current_hash == expected_bytes
    except (ValueError, TypeError, KeyError):
        return False
