"""Hashing utilities."""

import hashlib
from pathlib import Path


def md5_hash(content: str | bytes) -> str:
    """Compute MD5 hash of content.

    Args:
        content: String or bytes to hash

    Returns:
        Hex-encoded MD5 hash
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.md5(content).hexdigest()


def sha256_hash(content: str | bytes) -> str:
    """Compute SHA-256 hash of content.

    Args:
        content: String or bytes to hash

    Returns:
        Hex-encoded SHA-256 hash
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


async def md5_hash_file(file_path: Path) -> str:
    """Compute MD5 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        Hex-encoded MD5 hash
    """
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()
