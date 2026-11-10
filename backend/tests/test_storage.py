import os
import hashlib
import pytest
from backend.app.storage.content_storage import ContentAddressableStorage


def test_store_and_retrieve_exact_bytes(tmp_path):
    storage = ContentAddressableStorage(tmp_path)
    content = b"PRISTINE_EVIDENCE_IMAGE_PAYLOAD_BYTES_01"
    expected_hash = hashlib.sha256(content).hexdigest()

    saved_hash = storage.store(content)
    assert saved_hash == expected_hash

    retrieved = storage.retrieve(saved_hash)
    assert retrieved == content


def test_sharded_path_structure(tmp_path):
    storage = ContentAddressableStorage(tmp_path)
    content = b"TEST_STORAGE_PATH_SHARDING"
    h = hashlib.sha256(content).hexdigest()

    storage.store(content)
    expected_shard_path = os.path.join(tmp_path, h[:2], h[2:4], h)
    assert os.path.exists(expected_shard_path)


def test_deduplication(tmp_path):
    storage = ContentAddressableStorage(tmp_path)
    content = b"DEDUPLICATE_IDENTICAL_FILE"

    h1 = storage.store(content)
    h2 = storage.store(content)
    assert h1 == h2

    # Retrieval works seamlessly
    assert storage.retrieve(h1) == content


def test_bit_rot_corruption_detection(tmp_path):
    storage = ContentAddressableStorage(tmp_path)
    content = b"INTEGRITY_PROTECTED_DATA"
    h = storage.store(content)

    # Tamper with the file on disk
    file_path = storage._find_file_path(h)
    assert file_path is not None
    with open(file_path, "wb") as f:
        f.write(b"CORRUPTED_TAMPERED_BYTES")

    with pytest.raises(IOError, match="Content corrupted in storage"):
        storage.retrieve(h)


def test_missing_content_raises_not_found(tmp_path):
    storage = ContentAddressableStorage(tmp_path)
    missing_hash = "a" * 64
    assert storage.exists(missing_hash) is False
    with pytest.raises(FileNotFoundError):
        storage.retrieve(missing_hash)
