import os
import hashlib
import tempfile
from pathlib import Path
from typing import Optional, Union
from backend.app.core.config import settings


class ContentAddressableStorage:
    """Content-addressable local file storage with atomic writes, deduplication,
    and bit-rot corruption detection.
    """

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        self.base_dir = str(base_dir or settings.STORAGE_DIR)
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_path(self, sha256_hash: str, ext: Optional[str] = None) -> str:
        shard1 = sha256_hash[:2]
        shard2 = sha256_hash[2:4]
        filename = f"{sha256_hash}.{ext.lstrip('.')}" if ext else sha256_hash
        return os.path.join(self.base_dir, shard1, shard2, filename)

    def _find_file_path(self, sha256_hash: str) -> Optional[str]:
        """Locates file by hash across possible sharded paths and extensions."""
        shard1 = sha256_hash[:2]
        shard2 = sha256_hash[2:4]

        # 1. Check exact 2-level path without extension
        p1 = os.path.join(self.base_dir, shard1, shard2, sha256_hash)
        if os.path.exists(p1):
            return p1

        # 2. Check 2-level directory for matching stem
        dir2 = os.path.join(self.base_dir, shard1, shard2)
        if os.path.exists(dir2):
            for entry in os.listdir(dir2):
                if entry == sha256_hash or entry.startswith(f"{sha256_hash}."):
                    return os.path.join(dir2, entry)

        # 3. Check 1-level directory data/evidence/<sha256[:2]>/<sha256>
        dir1 = os.path.join(self.base_dir, shard1)
        if os.path.exists(dir1):
            p_direct = os.path.join(dir1, sha256_hash)
            if os.path.exists(p_direct):
                return p_direct
            for entry in os.listdir(dir1):
                if entry == sha256_hash or entry.startswith(f"{sha256_hash}."):
                    return os.path.join(dir1, entry)

        return None

    def store(self, content_bytes: bytes, ext: Optional[str] = None) -> str:
        """Stores content atomically using temp file and os.replace with fsync.
        
        Returns:
            sha256 hash of the stored content.
        """
        sha256 = hashlib.sha256(content_bytes).hexdigest()
        target_path = self._get_path(sha256, ext)
        target_dir = os.path.dirname(target_path)
        os.makedirs(target_dir, exist_ok=True)

        # Deduplication check: if file already exists with identical content, skip write
        if os.path.exists(target_path):
            try:
                with open(target_path, "rb") as f:
                    if hashlib.sha256(f.read()).hexdigest() == sha256:
                        return sha256
            except Exception:
                pass  # Rewrite if existing file cannot be read

        # Atomic write: write to temp file, fsync, and replace
        temp_fd, temp_path = tempfile.mkstemp(prefix=f".tmp_{sha256[:8]}_", dir=target_dir)
        try:
            with os.fdopen(temp_fd, "wb") as f:
                f.write(content_bytes)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, target_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

        return sha256

    def retrieve(self, sha256_hash: str) -> bytes:
        """Retrieves and integrity-checks bytes. Raises FileNotFoundError or IOError."""
        file_path = self._find_file_path(sha256_hash)
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"Content {sha256_hash} not found")

        with open(file_path, "rb") as f:
            data = f.read()

        # Bit rot / corruption detection
        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash != sha256_hash:
            raise IOError("Content corrupted in storage")

        return data

    def exists(self, sha256_hash: str) -> bool:
        """Checks if content exists in storage."""
        if not sha256_hash:
            return False
        path = self._find_file_path(sha256_hash)
        return path is not None and os.path.exists(path)


content_storage = ContentAddressableStorage()
