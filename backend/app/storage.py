from __future__ import annotations

import hashlib
from pathlib import Path


class LocalObjectStorage:
    """Small S3-compatible boundary for deployments that mount a persistent volume.

    The API deliberately exposes only object keys, so an S3/Blob adapter can replace
    this implementation without changing routes or repository records.
    """

    def __init__(self, root: Path | None) -> None:
        self.root = root
        if root:
            root.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self.root is not None

    def put(self, attachment_id: str, content: bytes) -> tuple[str, str]:
        if not self.root:
            raise RuntimeError("Object storage is disabled")
        checksum = hashlib.sha256(content).hexdigest()
        key = f"{attachment_id[:2]}/{attachment_id}"
        target = (self.root / key).resolve()
        if self.root.resolve() not in target.parents:
            raise ValueError("Invalid object key")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return key, checksum

    def get(self, key: str) -> bytes:
        if not self.root:
            raise FileNotFoundError(key)
        target = (self.root / key).resolve()
        if self.root.resolve() not in target.parents or not target.is_file():
            raise FileNotFoundError(key)
        return target.read_bytes()

    def delete(self, key: str) -> None:
        if not self.root:
            return
        target = (self.root / key).resolve()
        if self.root.resolve() in target.parents:
            target.unlink(missing_ok=True)
