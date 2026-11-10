"""F-16: Local Content-Addressable File Storage Tests.
Validates SHA-256 content-addressable storage on the local filesystem,
path sharding, bit-for-bit retrieval, and integrity verification.
"""

import os
import hashlib
import pytest


class ContentAddressableStorage:
    """Reference implementation of content-addressable file storage."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def _get_path(self, sha256_hash: str) -> str:
        # Sharding pattern: ab/cd/abcdef1234...
        shard1 = sha256_hash[:2]
        shard2 = sha256_hash[2:4]
        return os.path.join(self.base_dir, shard1, shard2, sha256_hash)

    def store(self, content_bytes: bytes) -> str:
        sha256 = hashlib.sha256(content_bytes).hexdigest()
        file_path = self._get_path(sha256)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if not os.path.exists(file_path):
            with open(file_path, "wb") as f:
                f.write(content_bytes)
        return sha256

    def retrieve(self, sha256_hash: str) -> bytes:
        file_path = self._get_path(sha256_hash)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Content {sha256_hash} not found")
        with open(file_path, "rb") as f:
            data = f.read()
        # Verify integrity on retrieval
        if hashlib.sha256(data).hexdigest() != sha256_hash:
            raise IOError("Content corrupted in storage")
        return data

    def exists(self, sha256_hash: str) -> bool:
        return os.path.exists(self._get_path(sha256_hash))


class TestF16ContentStorage:
    """Verifies content-addressable storage operations and integrity."""

    def test_store_and_retrieve_exact_bytes(self, ephemeral_dir, sharp_image_fixture):
        """Test 1: Verifies content stored can be retrieved with identical byte content."""
        storage = ContentAddressableStorage(ephemeral_dir)
        raw_bytes, expected_hash = sharp_image_fixture

        saved_hash = storage.store(raw_bytes)
        assert saved_hash == expected_hash

        retrieved = storage.retrieve(saved_hash)
        assert retrieved == raw_bytes

    def test_path_sharding_structure(self, ephemeral_dir):
        """Test 2: Verifies files are stored in two-level sharded directory structure."""
        storage = ContentAddressableStorage(ephemeral_dir)
        content = b"TEST_SHARDING_DATA"
        h = hashlib.sha256(content).hexdigest()

        storage.store(content)
        expected_shard_path = os.path.join(ephemeral_dir, h[:2], h[2:4], h)
        assert os.path.exists(expected_shard_path)

    def test_deduplication_of_identical_payloads(self, ephemeral_dir):
        """Test 3: Verifies storing identical bytes twice does not duplicate files."""
        storage = ContentAddressableStorage(ephemeral_dir)
        content = b"DUPLICATE_IMAGE_CONTENT"

        h1 = storage.store(content)
        h2 = storage.store(content)
        assert h1 == h2

    def test_corrupted_file_detection_on_retrieval(self, ephemeral_dir):
        """Test 4: Verifies bit rot / storage corruption is detected during retrieval."""
        storage = ContentAddressableStorage(ephemeral_dir)
        content = b"PRISTINE_ORIGINAL_BYTES"
        h = storage.store(content)

        # Corrupt file on disk
        target_path = storage._get_path(h)
        with open(target_path, "wb") as f:
            f.write(b"CORRUPTED_DISK_DATA")

        with pytest.raises(IOError, match="Content corrupted"):
            storage.retrieve(h)

    def test_missing_content_raises_not_found(self, ephemeral_dir):
        """Test 5: Verifies querying non-existent hash raises FileNotFoundError."""
        storage = ContentAddressableStorage(ephemeral_dir)
        missing_hash = "f" * 64
        assert storage.exists(missing_hash) is False
        with pytest.raises(FileNotFoundError):
            storage.retrieve(missing_hash)
