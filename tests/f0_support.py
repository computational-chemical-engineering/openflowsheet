"""F0's archived outputs, for the guards that keep a policy value out of committed documents.

Ruling D15 (`docs/reviews/F0-review.md`, R-939): the three policy-literal guards
(`test_t05b_literal`, `test_t06_f4_literals`, `test_t06_w18_literal`) protect *registered input*
documents. The `artifacts/solve-policy.json` records of the 0.3.0 bundles that F0's M7 replays
(`tests/fixtures/f0/v0.3.0-bundles`) are archived *outputs* of a policy built in code; a replay
needs them as written. They are exempt only by registration: each is listed by path and SHA-256
in `benchmarks/f0/corpus.json` `archived_outputs` (written by `corpus_identity.py --record`), and a
guard skips a file only when both match. Every other file, in the bundles or elsewhere, is scanned.
"""

from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
REGISTRY: Final = REPO_ROOT / "benchmarks" / "f0" / "corpus.json"
#: The number of registered archived outputs, and so of files each guard exempts (R-939).
N_ARCHIVED_OUTPUTS: Final = 36


@cache
def archived_outputs() -> dict[str, str]:
    """Repository-relative POSIX path -> SHA-256 of each registered archived output."""
    registered: dict[str, str] = json.loads(REGISTRY.read_text(encoding="utf-8"))[
        "archived_outputs"
    ]
    return registered


def is_archived_output(path: Path) -> bool:
    """`path` is a registered archived output, by path *and* by its bytes' SHA-256."""
    expected = archived_outputs().get(path.relative_to(REPO_ROOT).as_posix())
    return expected is not None and hashlib.sha256(path.read_bytes()).hexdigest() == expected
