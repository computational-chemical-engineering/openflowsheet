"""Atomic file writes, below every layer that writes records (M02 design note §14 B4, R-237).

`atomic_write_bytes` was `application.store`'s; it moved here so that `adapters` can write its
records without importing `application`, which sits above it. `application.store` re-exports it,
so its existing callers do not change.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

__all__ = ["atomic_write_bytes"]


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write a temporary file beside `path`, `fsync` it, rename it over `path`, `fsync` the dir."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
