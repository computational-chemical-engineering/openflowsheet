"""R-235's companion (M02 design note §14 B2): nothing in an `experiment` job's body can reach a
solver start, a warm start or a coupling iterate.

T07 Q26 (`tests/test_t07_q26.py`) allows one numeric array in a request by name — `submit_job`'s
`body/inlet/n` — with the scalars `body/inlet/T`, `body/inlet/P` and `body/n_tubes`, because they
are the experiment's definition (a model input), not a solver state. This module proves the property
that makes the allowance safe, the analogue of ADR 0020 D7's W14 path test:

- **Static.** The layers that start or seed a solve — `numerics`, `orchestrator` (the coupling
  driver included, §4.3: it builds its requests from its own inner solutions), `compile`, `graph`,
  `verify`, `run` — import none of the modules that hold, parse or carry a job body (the request
  types, the job model and runner, the operations and the application object) nor the experiment
  adapters, so they cannot be handed the body or its records; and the experiment adapters import
  no solver entry point, so the body cannot be handed on from there. (Three solver-side modules
  import `application`'s binder and policy modules, which hold no request body.)
- **Dynamic.** An `experiment` job runs to `completed` with every solve entry point the job
  runner holds — route selection and binding, policy resolution, the revision session, the warm
  start's candidate search, reproduction — replaced by a tripwire that none trips; and what it
  leaves in the project is experiment records only, so no later solve's warm start
  (`store-latest-verified-lineage-v1`, which reads `solution_state` artifacts) can find it.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS

import openflowsheet
from openflowsheet.adapters import variants
from openflowsheet.application.jobs import runner as job_runner
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.models.c1 import COMPONENTS

PACKAGE = Path(openflowsheet.__file__).resolve().parent
#: The layers that start, seed or iterate a solve.
SOLVER_LAYERS = ("numerics", "orchestrator", "compile", "graph", "verify", "run")
#: What they must never import: where a job body is defined, parsed and executed, and the
#: experiment records.
BODY_READERS = (
    "openflowsheet.application.types",
    "openflowsheet.application.jobs",
    "openflowsheet.application.operations",
    "openflowsheet.application.local",
    "openflowsheet.application.bindings",
    "openflowsheet.application.cli",
    "openflowsheet.adapters.experiments",
)
#: The solver entry points: a start (`numerics`, `orchestrator.attempts`, `orchestrator.executor`,
#: `orchestrator.homotopy`), a warm start (`orchestrator.warm_start`), a run (`run`).
SOLVER_ENTRIES = (
    "openflowsheet.numerics",
    "openflowsheet.orchestrator.attempts",
    "openflowsheet.orchestrator.executor",
    "openflowsheet.orchestrator.homotopy",
    "openflowsheet.orchestrator.revision",
    "openflowsheet.orchestrator.warm_start",
    "openflowsheet.run",
)


def _imports(path: Path) -> set[str]:
    """Every absolute module `path` imports, anywhere in it (lazy imports included)."""
    package = ".".join(("openflowsheet", *path.relative_to(PACKAGE).parts[:-1]))
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                stem = ".".join(parts[: len(parts) - node.level + 1])
                found.add(f"{stem}.{node.module}" if node.module else stem)
            else:
                found.add(node.module or "")
    return found


def _under(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)


def test_no_solver_layer_can_be_handed_an_experiment_body() -> None:
    offending = {
        str(path.relative_to(PACKAGE)): sorted(n for n in _imports(path) if _under(n, BODY_READERS))
        for layer in SOLVER_LAYERS
        for path in sorted((PACKAGE / layer).rglob("*.py"))
    }
    assert {name: found for name, found in offending.items() if found} == {}


def test_the_experiment_adapters_reach_no_solver_entry_point() -> None:
    offending = {
        str(path.relative_to(PACKAGE)): sorted(
            n for n in _imports(path) if _under(n, SOLVER_ENTRIES)
        )
        for path in sorted((PACKAGE / "adapters").rglob("*.py"))
    }
    assert {name: found for name, found in offending.items() if found} == {}


#: What the job runner holds that starts, seeds or replays a solve.
SOLVE_ENTRIES = (
    "select_route",
    "bind_route",
    "resolve_policies",
    "run_revision_session",
    "warm_start_candidate",
    "reproduce_bundle",
)


def test_an_experiment_job_reaches_no_solve_and_leaves_only_experiment_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tripped: list[str] = []

    def tripwire(name: str) -> Any:
        def call(*_: Any, **__: Any) -> Any:
            tripped.append(name)
            raise AssertionError(f"an experiment job reached {name}")

        return call

    for name in SOLVE_ENTRIES:
        monkeypatch.setattr(job_runner, name, tripwire(name))
    standin = variants.registered_variant("standin-x025-v1")
    total = 0.007146961299302104 * 1000.0
    body = {
        "model": {
            "id": standin.model_id,
            "version": standin.variant_id,
            "artifact_ref": standin.sha256,
        },
        "inlet": {
            "components": list(COMPONENTS),
            "n": [
                total * y
                for y in (0.6975, 0.2325, 0.03, 0.017142857142857144, 0.022857142857142857)
            ],
            "T": 673.15,
            "P": 1.0e7,
        },
        "n_tubes": 1000.0,
    }
    with LocalApplication.create(tmp_path / "project") as app:
        request = {"operation": "experiment", "idempotency_key": "isolated", "body": body}
        job = dispatch(app, "submit_job", request)["job"]
        assert (job["status"], tripped) == ("completed", [])
        with app.store.reading() as connection:
            found = {row[0] for row in connection.execute("SELECT DISTINCT kind FROM artifacts")}
        assert found == {"experiment_request", "experiment_attempt", "experiment_result"}
        assert not (app.files_root / "jobs" / job["job_id"]).exists()
        # Not vacuous: a solve under the same tripwires trips the first one on its path.
        with app.store.reading() as connection:
            head = app.store.head(connection)
        edits = [
            {"operation": "set", "path": [key], "value": value}
            for key, value in CORPUS["SYN-001-nominal"]().items()
        ]
        committed = dispatch(
            app,
            "commit_change",
            {"edits": edits, "expected_revision": head, "idempotency_key": "c"},
        )
        solve = {
            "operation": "solve",
            "idempotency_key": "tripped",
            "body": {"revision_id": committed["revision_id"]},
        }
        solved = dispatch(app, "submit_job", solve)["job"]
        assert solved["status"] == "failed" and tripped and tripped[0] in SOLVE_ENTRIES
