"""X02 G0 (design note `docs/design/X02-warm-starts.md` §7 G0; ADR 0070 D5): every recorded
experiment request under `benchmarks/m02/`, `benchmarks/m05/records/` and `benchmarks/m07/journey/`
recomputes to its recorded `experiment_key`, with 0 differences. X02 adds `start` to a warm
request only when a start was used and keeps `REQUEST_VERSION`, so a cold request — every
request recorded before X02 — is byte-identical and its key cannot move (I1).

A request is any JSON object, at any depth of a recorded `.json` file, whose `schema_version` is
`REQUEST_VERSION` and which carries an `experiment_key`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from conftest import REPO_ROOT

from openflowsheet.adapters.experiments.request import REQUEST_VERSION, experiment_key

ROOTS = (
    REPO_ROOT / "benchmarks" / "m02",
    REPO_ROOT / "benchmarks" / "m05" / "records",
    REPO_ROOT / "benchmarks" / "m07" / "journey",
)


def _requests(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if node.get("schema_version") == REQUEST_VERSION and "experiment_key" in node:
            yield node
        for value in node.values():
            yield from _requests(value)
    elif isinstance(node, list):
        for value in node:
            yield from _requests(value)


def recorded_requests() -> list[tuple[Path, dict[str, Any]]]:
    found: list[tuple[Path, dict[str, Any]]] = []
    for root in ROOTS:
        for path in sorted(root.rglob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            found += [(path, request) for request in _requests(document)]
    return found


def test_g0_every_recorded_experiment_key_recomputes() -> None:
    found = recorded_requests()
    assert found, "no recorded request: the gate would pass vacuously"
    differences = [
        f"{path.relative_to(REPO_ROOT)}: {request['experiment_key']}"
        for path, request in found
        if experiment_key(request) != request["experiment_key"]
    ]
    assert differences == [], differences
    # None of them is warm: X02 records none before WO-5's campaign.
    assert not any("start" in request for _, request in found)


def test_g0_the_check_has_a_control() -> None:
    """A changed request member moves the key, so the comparison above can fail."""
    _, request = recorded_requests()[0]
    edited = {**request, "start": {"kind": "profile", "profile_sha256": "0" * 64}}
    assert experiment_key(edited) != request["experiment_key"]
