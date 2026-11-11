"""The self-hash of an extension's implementation set (ADR 0060 D3).

```
lf(b)          = b.replace(b"\\r\\n", b"\\n")
file_sha(p)    = sha256(lf(bytes of <import root>/p)).hexdigest()
self_sha256    = sha256(canonical_json([[p, file_sha(p)] for p in modules sorted by UTF-8 bytes]))
```

The registry computes it; an author never declares it. An empty set hashes `[]`. A module path
that does not resolve to a regular file is `self_hash_unavailable(<id>, <path>)`, which
quarantines an extension's package and fails the build for a built-in; zip imports and namespace
packages are therefore unsupported in 0.5. CRLF line endings hash as LF, so a checkout's line
endings never move the hash.

A v2 method's `implementation_sha256` is `implementation_sha256(descriptor_sha256, self_sha256)`
below, so F4 does not define a second formula. Legacy providers keep their own single-file
`implementation_sha256` in `describe()`; neither value replaces it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from openflowsheet.canonical import canonical_json


class SelfHashUnavailableError(Exception):
    """A module path of an implementation set is not a regular file below the import root."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.path = path


def lf(data: bytes) -> bytes:
    """D3's line-ending normalisation: every CRLF pair becomes LF; nothing else changes."""
    return data.replace(b"\r\n", b"\n")


def file_sha(root: Path | None, path: str) -> str:
    """SHA-256 of the LF-normalised bytes of `<root>/<path>` (`path` POSIX, relative). No root
    (a namespace package or a zip import, D3) resolves no path. A file the process cannot read
    (`OSError`) is unavailable too (F1 review SF-2)."""
    target = None if root is None else root.joinpath(*path.split("/"))
    try:
        if target is None or not target.is_file():
            raise SelfHashUnavailableError(path)
        data = target.read_bytes()
    except OSError:
        raise SelfHashUnavailableError(path) from None
    return hashlib.sha256(lf(data)).hexdigest()


def self_sha256(root: Path | None, modules: Iterable[str]) -> str:
    """D3's `self_sha256` of an implementation set below the import root `root`."""
    ordered = sorted(set(modules), key=lambda path: path.encode("utf-8"))
    return hashlib.sha256(
        canonical_json([[path, file_sha(root, path)] for path in ordered])
    ).hexdigest()


def implementation_sha256(descriptor_sha256: str, self_sha: str) -> str:
    """D3: a v2 method's `implementation_sha256`, `sha256(canonical_json([descriptor, self]))`."""
    return hashlib.sha256(canonical_json([descriptor_sha256, self_sha])).hexdigest()
