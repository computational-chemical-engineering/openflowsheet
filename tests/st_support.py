"""ST test support: note §11's corpus, solved once per process, and test-local state edits.

The corpus is F0's RC bundle set and basis cases (`scripts/corpus_identity.py`'s `run_corpus`,
TH-C1 among them), solved exactly as F0 solves them into a temporary directory removed at exit.
`coolprop-heos-v1` joins it (TH-C2) only where the optional extra is installed. A state edit
rebuilds `solution-state.json` and points the certificate's `target_state_sha256` at it, so the
edited pair passes `build`'s precondition (Q1.A14: every test-local state is paired with a
certificate whose `target_state_sha256` matches).
"""

from __future__ import annotations

import atexit
import copy
import importlib.util
import json
import shutil
import sys
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from typing import Any

from openflowsheet.application import stream_table
from openflowsheet.application.revision_binding import provider_for
from openflowsheet.models.revision_flowsheet import component_basis
from openflowsheet.run import solution_state
from openflowsheet.run.bundle import ARTIFACT_DIR, MANIFEST_NAME

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import corpus_identity as f0  # noqa: E402

V030_BUNDLES = ROOT / "tests" / "fixtures" / "f0" / "v0.3.0-bundles"
COOLPROP = importlib.util.find_spec("CoolProp") is not None
#: The CoolProp case of the basis set (note §11), solved only where the extra is installed.
COOLPROP_CASE = ("s11-th", "TH-C2")


def _runs() -> list[tuple[str, str]]:
    runs = list(f0.run_corpus())
    if COOLPROP:
        runs.append(COOLPROP_CASE)
    return runs


@cache
def corpus() -> dict[str, Path]:
    """`<set>/<name>` -> the bundle directory of every corpus run, in F0's order."""
    root = Path(tempfile.mkdtemp(prefix="st-corpus-"))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    bundles: dict[str, Path] = {}
    with f0.pinned_threads():
        for index, (run_set, name) in enumerate(_runs()):
            directory = root / f"{index:03d}"
            f0.solve(run_set, name, directory)
            bundles[f"{run_set}/{name}"] = directory
    return bundles


@cache
def _outcomes() -> dict[str, dict[str, Any] | stream_table.StreamTableError]:
    outcomes: dict[str, dict[str, Any] | stream_table.StreamTableError] = {}
    for name, directory in corpus().items():
        try:
            outcomes[name] = stream_table.from_bundle(directory)
        except stream_table.StreamTableError as error:
            outcomes[name] = error
    return outcomes


def documents() -> dict[str, dict[str, Any]]:
    """Every corpus document (a fresh deep copy), by run."""
    return {
        name: copy.deepcopy(outcome)
        for name, outcome in _outcomes().items()
        if isinstance(outcome, dict)
    }


def document(run: str) -> dict[str, Any]:
    outcome = _outcomes()[run]
    assert isinstance(outcome, dict), outcome
    return copy.deepcopy(outcome)


def refusals() -> dict[str, stream_table.StreamTableError]:
    return {
        name: outcome
        for name, outcome in _outcomes().items()
        if isinstance(outcome, stream_table.StreamTableError)
    }


@dataclass(frozen=True)
class Members:
    """A bundle's four members, as `build` takes them."""

    revision: dict[str, Any]
    state: dict[str, Any]
    certificate: dict[str, Any]
    manifest: dict[str, Any]

    @property
    def variables(self) -> dict[str, float]:
        return {name: float(value) for name, value in self.state["variables"].items()}


def read_members(directory: Path) -> Members:
    def artifact(name: str) -> dict[str, Any]:
        document: dict[str, Any] = json.loads(
            (directory / ARTIFACT_DIR / name).read_text(encoding="utf-8")
        )
        return document

    return Members(
        revision=artifact("revision.json"),
        state=artifact("solution-state.json"),
        certificate=artifact("solution-certificate.json"),
        manifest=json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8")),
    )


def members(run: str) -> Members:
    return read_members(corpus()[run])


def with_state(source: Members, updates: Mapping[str, float]) -> Members:
    """`source` with the named state variables set, the state document rebuilt and the
    certificate's `target_state_sha256` pointed at it."""
    variables = source.variables
    unknown = sorted(set(updates) - set(variables))
    assert not unknown, f"not state variables: {unknown}"
    variables.update(updates)
    ids = list(source.state["variable_ids"])
    state = solution_state.document(ids, [variables[name] for name in ids])
    certificate = copy.deepcopy(source.certificate)
    certificate["target_state_sha256"] = state["state_sha256"]
    return replace(source, state=state, certificate=certificate)


def with_rows(source: Members, rows: list[dict[str, Any]]) -> Members:
    certificate = copy.deepcopy(source.certificate)
    certificate["checks"] = [*certificate["checks"], *rows]
    return replace(source, certificate=certificate)


def fresh_provider(source: Members) -> Any:
    provider = provider_for(component_basis(source.revision))
    assert not hasattr(provider, "kind"), provider
    return provider


def build(source: Members, provider: Any = None) -> dict[str, Any]:
    return stream_table.build(
        source.revision,
        source.state,
        source.certificate,
        source.manifest,
        provider=provider if provider is not None else fresh_provider(source),
        source={"job_id": None, "bundle_id": None},
    )


class Recording:
    """A provider wrapper recording every call, in order: `(method, request, result)`."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls: list[tuple[str, Any, Any]] = []

    def describe(self) -> Any:
        return self.inner.describe()

    def evaluate_phase(self, request: Any, context: Any) -> Any:
        result = self.inner.evaluate_phase(request, context)
        self.calls.append(("evaluate_phase", request, result))
        return result

    def flash(self, request: Any, context: Any) -> Any:
        result = self.inner.flash(request, context)
        self.calls.append(("flash", request, result))
        return result


def stream(document: Mapping[str, Any], name: str) -> dict[str, Any]:
    (found,) = [entry for entry in document["streams"] if entry["id"] == name]
    return dict(found)


def substream(document: Mapping[str, Any], name: str) -> dict[str, Any]:
    (only,) = stream(document, name)["substreams"]
    return dict(only)


def unit(document: Mapping[str, Any], name: str) -> dict[str, Any]:
    (found,) = [entry for entry in document["energy"]["units"] if entry["id"] == name]
    return dict(found)


def families(entry: Mapping[str, Any]) -> list[str]:
    return [phase["id"]["family"] for phase in entry["phases"]]


def substreams(document: Mapping[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for entry in document["streams"]:
        for sub in entry["substreams"]:
            yield entry["id"], sub
