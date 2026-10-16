"""M02's registered C1 corpus (design note §14.3 C1 (a), §14.4 D5; register R-280). Not collected.

The revisions on the C1 basis that the registry-coverage tests read beside T07's corpus
(`t07_corpus.CORPUS`, which stays W0.2's 50 SYN-001 revisions): the loop `C1-LOOP-M02-v1` with
the stand-in (WO-9), G7 (a)'s flash at F1, the heater and the mixer in their WO-8.2 minimal
flowsheets, and the real reactor between a feed and a sink (WO-9; binding never executes it).
Since W27 Amendment 3 (§22.4, R-302) it also holds M04's `c1.reactor_surrogate` between a feed
and a sink (`benchmarks/m04/c1-surrogate.json`), which binds through `surrogates`, the corpus's
resolver of committed fixture manifests; every corpus test passes it to the binder. Together they
bind an instance of each of the nine `c1.*` models, so every coverage test that asks for a bound
instance of each builder is met by a registered revision, never by an exemption or a skip.
Each file is canonical JSON under `benchmarks/m02/` or `benchmarks/m04/`; `tests/test_m02_join.py`
and `tests/test_m04_wo7_surrogate_unit.py` check that each equals the builder its provenance names.
Each entry is a factory, so every caller gets a copy.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path
from typing import Any

from openflowsheet.canonical import document_sha256

REPO_ROOT = Path(__file__).resolve().parents[1]
Document = dict[str, Any]

#: Revision id -> its registered file.
FILES: dict[str, Path] = {
    "C1-LOOP-M02-v1": REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json",
    "C1-FLASH-F1-M02-v1": REPO_ROOT / "benchmarks" / "m02" / "c1-flash-f1.json",
    "C1-HEATER-M02-v1": REPO_ROOT / "benchmarks" / "m02" / "c1-heater.json",
    "C1-MIXER-M02-v1": REPO_ROOT / "benchmarks" / "m02" / "c1-mixer.json",
    "C1-REACTOR-M02-v1": REPO_ROOT / "benchmarks" / "m02" / "c1-reactor.json",
    # W27 Amendment 3 §22.4 (R-302): M04's surrogate of the reactor, bound through `surrogates`.
    "C1-SURROGATE-M04-v1": REPO_ROOT / "benchmarks" / "m04" / "c1-surrogate.json",
}


def _load(path: Path) -> Document:
    loaded: Document = json.loads(path.read_text(encoding="utf-8"))
    return loaded


#: Revision id -> a factory of a fresh copy of the revision document.
C1_CORPUS: dict[str, Callable[[], Document]] = {
    name: partial(_load, path) for name, path in FILES.items()
}


#: W27 Amendment 3 §22.4 (R-302; M04 build decision E5): the committed fixture SurrogateManifests
#: the corpus resolves, and nothing else. Its one entry is the A19 manifest M04's WO-7 tests bind.
SURROGATE_MANIFESTS: tuple[Path, ...] = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "schemas"
    / "surrogate_manifest"
    / "valid"
    / "a19_smooth_prefix.json",
)
_BY_SHA256: dict[str, Document] = {
    document_sha256(manifest): manifest for manifest in map(_load, SURROGATE_MANIFESTS)
}


def surrogates(reference: str) -> Mapping[str, Any] | None:
    """The corpus's `SurrogateResolver`: the committed fixture manifest whose canonical SHA-256 is
    `reference`, else `None`. Every corpus test passes it to the binder, so a corpus revision
    with a `c1.reactor_surrogate` instance binds there; one that does not bind is a failure."""
    return _BY_SHA256.get(reference)
