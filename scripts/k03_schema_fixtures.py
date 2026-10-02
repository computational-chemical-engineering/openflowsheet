"""Generate the plan §2.2 K03 round-trip fixtures from real solves.

A fixture written by hand tests the author's reading of the schema; a fixture emitted by the
code tests the code. This module is the single source of all five, and
`tests/test_k03_schemas.py` calls `documents()` and compares — so a change in what the code
emits is a test failure rather than a stale file nobody regenerates.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/k03_schema_fixtures.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet  # noqa: E402
from openflowsheet.orchestrator.tear import (  # noqa: E402
    Syn001TearProblem,
    build_plan,
    solve_tear,
)
from openflowsheet.orchestrator.trace import SolvePolicy  # noqa: E402
from openflowsheet.thermo.syn001 import Syn001Provider  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "schemas"

#: §13.3's registered phase-change start: the flash opens all-liquid and the attempt restarts.
OFF_B = (0.05, 0.1, 4.0)

CONTEXT = EvaluationContext(model_version="K03-fixtures@" + "0" * 64, constants_sha256="0" * 64)

POLICY = SolvePolicy(
    policy_id="SYN-001-K03",
    residual_tolerances={
        "molar_flow": {"absolute": 1e-9, "relative": 1e-8, "scale": 3.0},
        "heat_rate": {"absolute": 1e-5, "relative": 1e-8, "scale": 1e5},
        "temperature": {"absolute": 1e-6, "relative": 0.0, "scale": 100.0},
        "pressure": {"absolute": 1e-2, "relative": 0.0, "scale": 1e5},
    },
    scales={"molar_flow": 3.0, "temperature": 100.0, "pressure": 1e5, "heat_rate": 1e5},
)


def flowsheet() -> Syn001Flowsheet:
    return Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT)


def documents() -> dict[str, Any]:
    """Every K03 fixture, keyed by its path under `tests/fixtures/schemas/`."""
    nominal, nominal_trace = solve_tear(flowsheet(), policy=POLICY)
    restart, restart_trace = solve_tear(flowsheet(), policy=POLICY, initial_recycle=OFF_B)

    if nominal.checkpoint is None:
        raise SystemExit("the nominal solve produced no checkpoint")
    if len(restart.contexts) != 2:
        raise SystemExit(
            f"the OFF-B solve opened {len(restart.contexts)} attempts, not the registered 2"
        )

    return {
        "solve_policy/valid/syn001_k03.json": POLICY.as_document(),
        "solve_plan/valid/syn001_nominal.json": build_plan(
            Syn001TearProblem(flowsheet()), POLICY
        ).as_document(),
        "solve_event/valid/syn001_nominal_trace.json": [
            event.as_document() for event in nominal_trace.events
        ],
        "solve_event/valid/syn001_off_b_restart_trace.json": [
            event.as_document() for event in restart_trace.events
        ],
        # The second attempt: the one opened `phase_update` from a rejected trial, which is the
        # only context that carries an `opened_from` checkpoint.
        "attempt_context/valid/syn001_restart.json": restart.contexts[1].as_document(),
        "checkpoint/valid/syn001_candidate_root.json": nominal.checkpoint.as_document(),
    }


def serialize(document: Any) -> str:
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="overwrite the committed fixtures")
    arguments = parser.parse_args()

    differing = []
    for name, document in documents().items():
        path = FIXTURE_DIR / name
        text = serialize(document)
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            differing.append(name)
            if arguments.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    if not differing:
        print("all fixtures match what the code emits")
        return 0
    verb = "rewrote" if arguments.write else "differ (rerun with --write)"
    print(f"{verb}: {', '.join(differing)}")
    return 0 if arguments.write else 1


if __name__ == "__main__":
    raise SystemExit(main())
