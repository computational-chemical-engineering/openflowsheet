"""Shared helpers for the M03 tests (specification `docs/derivations/M03-studies-spec.md`).

`reference()` is `benchmarks/m03/reference_values.json`, produced by the design lane's closed-form
generator `docs/derivations/scripts/m03_reference.py` (mpmath, 60 digits; it imports nothing from
`openflowsheet`). Its bytes are pinned to the SHA-256 the specification's header records, so a test
cannot be judged against a file the specification does not cite: regenerating the JSON is a
specification change, and the hash here moves with it or the loader refuses.

Every number in the file is a decimal string (20 significant digits, or the `repr` of a registered
binary64 input); `number()` is the one conversion, so no test parses one differently.
"""

from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
REFERENCE_PATH: Final = REPO_ROOT / "benchmarks" / "m03" / "reference_values.json"
#: The SHA-256 `docs/derivations/M03-studies-spec.md`'s header records for the JSON.
REFERENCE_SHA256: Final = "5f3fc150032157d31042f8b17ca5560e4c0e7233384a3eaade0404bde5915981"
GENERATOR_PATH: Final = REPO_ROOT / "docs" / "derivations" / "scripts" / "m03_reference.py"


@cache
def reference() -> dict[str, Any]:
    """The M03 reference values, refused unless the bytes are the specification's."""
    raw = REFERENCE_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != REFERENCE_SHA256:
        raise ValueError(
            f"{REFERENCE_PATH.relative_to(REPO_ROOT)} has SHA-256 {digest}, but the M03 "
            f"specification records {REFERENCE_SHA256}; the tests judge against the file the "
            "specification cites, or not at all"
        )
    loaded: dict[str, Any] = json.loads(raw)
    return loaded


def number(value: str | int | float) -> float:
    """A reference value as the nearest binary64 (the file's decimal strings, or a literal)."""
    return float(value)


def constant(name: str) -> float:
    """A registered constant of the specification (`constants` in the JSON), as binary64."""
    return number(reference()["constants"][name])
