"""Generate the T04 round-trip fixtures from real solves. Register R-015; ADR 0010 D7.

Every document here is emitted by a real plan run or region solve of a registered case: nothing
is hand-assembled, so a fixture tests the code and not its author's reading of the schema. The
files are T04's own (`t04_*.json`) and sit beside K03's and K04's in the schema directories;
`tests/test_t04_schemas.py` validates them and compares them with what the code emits today.

- `solve_policy`: the registered policy under `eo_core: ptc`.
- `solve_event`: HOM-05's recovery region solve (`homotopy_step`, `homotopy_level`) and the r = 0.5
  registered initializer's region solve under PTC (`pseudo_step`, `pseudo_step_next`, `ser_ratio`,
  `bound_blocked` rejections, the polish).
- `attempt_context`: HOM-05's homotopy attempt (`core: homotopy`, `continuation`) and the PTC
  restart attempt (`core: ptc`).
- `checkpoint`: HOM-04's stall checkpoint (`continuation_lambda: 909/1024`, `partial`).
- `solution_certificate`: HOM-01 (PHS-05) certified on the bound declaration (T04 §4.8), with the
  recovery's `continuation` provenance item.
- `failure_bundle`: HOM-04's `HOMOTOPY_STALLED` region bundle with its one inferred cause.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/t04_schema_fixtures.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openflowsheet.application.binding import Binding, bind_revision  # noqa: E402
from openflowsheet.graph.analysis import analyse  # noqa: E402
from openflowsheet.graph.trace import trace_declaration  # noqa: E402
from openflowsheet.orchestrator.execution import (  # noqa: E402
    ExecutionPlan,
    build_execution_plan,
    declaration_identity,
    specification_regions,
)
from openflowsheet.orchestrator.executor import PlanResult, execute_plan  # noqa: E402
from openflowsheet.orchestrator.trace import (  # noqa: E402
    GlobalizationPolicy,
    RecyclePolicy,
    SolvePolicy,
)
from openflowsheet.verify.certificate import verify_bound  # noqa: E402
from openflowsheet.verify.failure import region_bundle  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "schemas"

#: The fixtures this generator owns, by path under `FIXTURE_DIR` — static, so that K03's and K04's
#: guards can tell T04's files from stale ones without running T04's solves. `documents()` emits
#: exactly these (`tests/test_t04_schemas.py`).
FIXTURE_NAMES: tuple[str, ...] = (
    "solve_policy/valid/t04_ptc.json",
    "solve_event/valid/t04_hom05_recovery_trace.json",
    "solve_event/valid/t04_ptc_nominal_region_trace.json",
    "attempt_context/valid/t04_hom05_homotopy.json",
    "attempt_context/valid/t04_ptc_restart.json",
    "checkpoint/valid/t04_hom04_stall.json",
    "solution_certificate/valid/t04_hom01_bound_verified.json",
    "failure_bundle/valid/t04_hom04_homotopy_stalled.json",
)
CASES = ROOT / "benchmarks" / "syn001" / "cases"

#: The registered cases' revisions and policy overrides (T04 §9.1; `ref.hom.*.policy_overrides`).
HOM = {
    "HOM-01": ("SYN-001-A02-355-dew-guess", {}),
    "HOM-04": ("SYN-001-A02-340-two-phase-guess", {"max_attempts": 1}),
    "HOM-05": ("SYN-001-A02-360", {"max_iterations_per_attempt": 1}),
}


def revision(case_id: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((CASES / f"{case_id}.yaml").read_text())
    return loaded


def plan_run(document: dict[str, Any], policy: SolvePolicy) -> tuple[ExecutionPlan, PlanResult]:
    """A revision through binding, structural analysis, the execution plan and the executor."""
    binding = bind_revision(document)
    if not isinstance(binding, Binding):
        raise SystemExit(f"{document['revision_id']} does not bind")
    spec = binding.spec
    model_version, constants = declaration_identity(spec)
    identity = {
        "row_units": binding.row_units,
        "specification_ids": binding.specification_ids,
        "model_version": model_version,
        "constants_sha256": constants,
    }
    declaration = trace_declaration(spec, **identity)  # type: ignore[arg-type]
    report = analyse(spec, binding.graph, **identity)  # type: ignore[arg-type]
    regions = (
        specification_regions(
            declaration,
            binding.graph,
            report,
            freed=binding.freed,
            promoted=binding.promoted,
            missing_guesses=binding.missing_guesses,
        )
        if binding.freed
        else ()
    )
    plan = build_execution_plan(
        spec=spec,
        declaration=declaration,
        graph=binding.graph,
        report=report,
        manifests={unit.unit_id: unit.manifest() for unit in binding.flowsheet.units()},
        policy=policy,
        specifications=regions,
    )
    return plan, execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=spec, policy=policy)


def policy(case_id: str, **overrides: Any) -> SolvePolicy:
    return SolvePolicy(policy_id=f"T04-{case_id}", residual_tolerances={}, scales={}, **overrides)


def region_step(result: PlanResult) -> Any:
    (step,) = [step for step in result.steps if step.kind == "solve_eo"]
    return step


def region_events(result: PlanResult, index: int) -> list[dict[str, Any]]:
    """The plan trace's events of one step, from its `region_opened` to its `region_closed`."""
    return [event.as_document() for event in result.trace.events if event.step_index == index]


def documents() -> dict[str, Any]:
    """Every T04 fixture, keyed by its path under `tests/fixtures/schemas/`."""
    ptc = policy(
        "ptc",
        recycle=RecyclePolicy(method="eo"),
        globalization=GlobalizationPolicy(eo_core="ptc", eo_recovery="none"),
    )
    _, nominal = plan_run(revision("SYN-001-nominal"), ptc)
    ptc_step = region_step(nominal)
    if nominal.outcome != "CONVERGED" or len(ptc_step.detail.attempts) != 2:
        raise SystemExit(f"the nominal PTC run ended {nominal.outcome}")

    runs = {
        case: plan_run(revision(name), policy(case, **extra)) for case, (name, extra) in HOM.items()
    }
    hom01, hom04, hom05 = (region_step(runs[case][1]) for case in ("HOM-01", "HOM-04", "HOM-05"))
    for case, step, outcome in (
        ("HOM-01", hom01, "CONVERGED"),
        ("HOM-04", hom04, "HOMOTOPY_STALLED"),
        ("HOM-05", hom05, "CONVERGED"),
    ):
        if step.outcome != outcome or step.eo_recovery != "taken":
            raise SystemExit(f"{case} ended {step.outcome} / edge 3 {step.eo_recovery}")

    hom01_plan = region_plan(runs["HOM-01"][0])
    certificate = verify_bound(
        bind_revision(revision(HOM["HOM-01"][0])),
        revision(HOM["HOM-01"][0]),
        hom01.detail,
        solve_plan=hom01_plan,
    )
    if certificate.verification_status != "VERIFIED":
        raise SystemExit(f"HOM-01 certified {certificate.verification_status}")
    hom04_result = runs["HOM-04"][1]
    bundle = region_bundle(hom04.detail, hom04_result.trace, step_index=hom04.index)

    return {
        "solve_policy/valid/t04_ptc.json": ptc.as_document(),
        "solve_event/valid/t04_hom05_recovery_trace.json": region_events(
            runs["HOM-05"][1], hom05.index
        ),
        "solve_event/valid/t04_ptc_nominal_region_trace.json": region_events(
            nominal, ptc_step.index
        ),
        "attempt_context/valid/t04_hom05_homotopy.json": hom05.detail.contexts[0].as_document(),
        "attempt_context/valid/t04_ptc_restart.json": ptc_step.detail.contexts[1].as_document(),
        "checkpoint/valid/t04_hom04_stall.json": hom04.detail.checkpoint.as_document(),
        "solution_certificate/valid/t04_hom01_bound_verified.json": certificate.as_document(),
        "failure_bundle/valid/t04_hom04_homotopy_stalled.json": bundle.as_document(),
    }


def region_plan(plan: ExecutionPlan) -> Any:
    (step,) = [step for step in plan.steps if step.kind == "solve_eo"]
    return step.solve_plan


def serialize(document: Any) -> str:
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
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
        print("all T04 fixtures match what the code emits")
        return 0
    print(
        f"{'rewrote' if arguments.write else 'differ (rerun with --write)'}: {', '.join(differing)}"
    )
    return 0 if arguments.write else 1


if __name__ == "__main__":
    raise SystemExit(main())
