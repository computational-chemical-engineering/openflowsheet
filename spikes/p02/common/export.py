"""Canonical CSC assembly, state hashes and JSON export (specification §10.1, §10.4)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

#: SYN-001 constants, in the order hashed by `constants_sha256` (specification §10.4).
CONSTANTS: Final[tuple[float, ...]] = (
    8.31446261815324,  # R
    300.0,  # T_r
    100000.0,  # P_r
    100.0,  # c_p
    320.0,
    360.0,
    400.0,  # T_b
    25000.0,
    30000.0,
    35000.0,  # L
    1e-4,
    1e-4,
    1e-4,  # v
)


def normalize_zero(value: float) -> float:
    """Return +0.0 for either signed zero (ADR 0001 D1.5)."""
    return 0.0 if value == 0.0 else value


def _hash_doubles(values: Sequence[float]) -> str:
    text = ",".join(f"{normalize_zero(float(value)):.17g}" for value in values)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def state_sha256(x: Mapping[str, float], order: Sequence[str]) -> str:
    """SHA-256 of the state's doubles in variable order (specification §10.4)."""
    return _hash_doubles([x[name] for name in order])


def constants_sha256() -> str:
    """SHA-256 of the SYN-001 constants."""
    return _hash_doubles(CONSTANTS)


@dataclass(frozen=True)
class CanonicalCsc:
    """A sparse matrix in the canonical CSC form the judge compares (specification §10.4)."""

    row_ids: tuple[str, ...]
    col_ids: tuple[str, ...]
    indptr: tuple[int, ...]
    indices: tuple[int, ...]
    data: tuple[float, ...]

    @property
    def nnz(self) -> int:
        return len(self.data)

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": "csc",
            "row_ids": list(self.row_ids),
            "col_ids": list(self.col_ids),
            "indptr": list(self.indptr),
            "indices": list(self.indices),
            "data": [normalize_zero(value) for value in self.data],
            "nnz": self.nnz,
        }

    def entries(self) -> dict[str, float]:
        """The stored entries keyed `"<row>|<col>"`."""
        result: dict[str, float] = {}
        for column, col_id in enumerate(self.col_ids):
            for k in range(self.indptr[column], self.indptr[column + 1]):
                result[f"{self.row_ids[self.indices[k]]}|{col_id}"] = self.data[k]
        return result


def canonical_csc(
    entries: Mapping[tuple[str, str], float],
    row_ids: Sequence[str],
    col_ids: Sequence[str],
) -> CanonicalCsc:
    """Build the canonical CSC of `entries`, keyed by name, in the given row and column order.

    Stored entries are exactly the keys of `entries` — including any that are numerically zero,
    which the specification requires to stay in the pattern (A11). Nothing is pruned here.
    """
    row_index = {name: index for index, name in enumerate(row_ids)}
    indptr = [0]
    indices: list[int] = []
    data: list[float] = []
    for col_id in col_ids:
        column = sorted(
            ((row_index[row], value) for (row, col), value in entries.items() if col == col_id),
            key=lambda item: item[0],
        )
        for row, value in column:
            indices.append(row)
            data.append(normalize_zero(float(value)))
        indptr.append(len(indices))
    return CanonicalCsc(tuple(row_ids), tuple(col_ids), tuple(indptr), tuple(indices), tuple(data))


def write_json(path: Path, payload: Any) -> Path:
    """Write `payload` as indented JSON with full float precision, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=False, allow_nan=False)
        handle.write("\n")
    return path
