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
"""

from __future__ import annotations

import ast
from pathlib import Path

import openflowsheet

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
