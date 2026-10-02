"""T07's revision corpus: W0.2's 50 revisions (`docs/t07-measurements.md` §W0.2). Not collected.

The six T05b builders the T06 corpus solves (`test_t06_w5_corpus.BUILDERS`), then every file under
`benchmarks/t06/cases/`, `benchmarks/t05/cases/` and `benchmarks/syn001/cases/`, keyed as W0.4's
probe keys them (the builder's fixture id, else the file's stem). Each entry is a factory, so
every caller gets its own copy.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import yaml
from test_t06_w5_corpus import BUILDERS

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_DIRECTORIES = ("benchmarks/t06/cases", "benchmarks/t05/cases", "benchmarks/syn001/cases")
Document = dict[str, Any]


def _load(path: Path) -> Document:
    loaded: Document = yaml.safe_load(path.read_text("utf-8"))
    return loaded


def _corpus() -> dict[str, Callable[[], Document]]:
    corpus: dict[str, Callable[[], Document]] = dict(BUILDERS)
    for directory in CASE_DIRECTORIES:
        for path in sorted((REPO_ROOT / directory).glob("*.yaml")):
            corpus[path.stem] = partial(_load, path)
    return corpus


#: Name -> a factory of a fresh copy of the revision document.
CORPUS: dict[str, Callable[[], Document]] = _corpus()
#: The T02 A02 files: the legacy binder's cross-unit specification with a GUESS (W0.2, flag E7).
A02_FILES: tuple[str, ...] = tuple(name for name in CORPUS if name.startswith("SYN-001-A02-"))
