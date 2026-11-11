"""The registry snapshot and `registry_sha256` (ADR 0060 D10).

```
registry_sha256 = sha256(canonical_json([[kind, id, version, descriptor_sha256, self_sha256]
                                         for every registered descriptor,
                                         sorted by (kind, id, version key)]))
```

It is the identity of what is loaded. It excludes evidence fields, distribution versions and
quarantine records, so it is identical across runs and platforms for the same code and
descriptors, and a review never moves it. The snapshot document
(`schemas/registry-snapshot.schema.json`) is §2.7.3's registry snapshot; F8 records it in
`Environment` (non-structural).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Final

from openflowsheet.canonical import canonical_json
from openflowsheet.registry.descriptor import Registered
from openflowsheet.registry.tokens import Coded

SNAPSHOT_FORMAT: Final = "openflowsheet-registry-snapshot-v1"


@dataclass(frozen=True)
class Quarantine:
    """D7: one quarantined extension package and its one typed reason."""

    distribution: str
    distribution_version: str
    entry_point: str
    reason: Coded

    def as_document(self) -> dict[str, Any]:
        return {
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
            "entry_point": self.entry_point,
            "code": self.reason.code,
            "params": dict(self.reason.params),
        }


def _ordered(descriptors: Iterable[Registered]) -> list[Registered]:
    return sorted(descriptors, key=Registered.sort_key)


def registry_sha256(descriptors: Iterable[Registered]) -> str:
    """D10's identity of a set of registered descriptors."""
    rows = [
        [entry.kind, entry.id, entry.version, entry.descriptor_sha256, entry.self_sha256]
        for entry in _ordered(descriptors)
    ]
    return hashlib.sha256(canonical_json(rows)).hexdigest()


def snapshot_document(
    descriptors: Iterable[Registered], quarantined: Iterable[Quarantine]
) -> dict[str, Any]:
    """D10's snapshot document: `extensions` sorted by (kind, id, version key), `quarantined`
    sorted by their rows' canonical JSON bytes."""
    ordered = _ordered(descriptors)
    return {
        "snapshot_format": SNAPSHOT_FORMAT,
        "registry_sha256": registry_sha256(ordered),
        "extensions": [entry.snapshot_row() for entry in ordered],
        "quarantined": sorted((record.as_document() for record in quarantined), key=canonical_json),
    }
