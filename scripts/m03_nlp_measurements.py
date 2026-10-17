"""M03 WO-8's measurements of the gray-box adapter: spec §14 Q-F2 and Q-F4.

- **Q-F2** (Ipopt with L-BFGS on NLP-1): per start, Ipopt's return status, iterations and final
  unscaled infeasibilities, and on the re-solved simulation at the returned decisions the decision
  error against the reference optimum, the objective error, V2's gross-error distance, the
  constraint value `ĝ`, the smallest regime margin, the multiplier's relative error against μ* and
  the reduced stationarity residual — each beside the tolerance A35/A36 registers for it, with the
  ratio of the two (how many times inside the tolerance the measurement lies). Spec §14 Q-F2: a
  ratio below 10 stops the work order and the design lane amends §8 before the assertion is judged.
- **Q-F4** (PyNumero's evaluation-error path): a domain error injected into the real property
  block (`LnKBlock`, raising `DomainError` above a temperature, only while Ipopt runs) at a trial
  point's residual, at an accepted point's Jacobian, and at the start, with what Ipopt and the
  classification made of each.

Wall times are not recorded, so the output is byte-reproducible under `OMP_NUM_THREADS=1` (WO-8's
measurement: MUMPS/OpenBLAS under LLVM OpenMP differ run to run in the last bits otherwise), which
this script therefore requires. Only the audited environment of `docs/m03-ipopt-audit.md` runs it.
The committed record is nevertheless compared for structure and margin, not bytes
(`m03_fixture_compare.measurement_differences`; M03 review F1).

The adapter (and with it Pyomo and cyipopt) is imported only when measuring, so the default gate can
import this module for its constants.

Usage:
    OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=<env>/share/pyomo PYTHONPATH=src \\
        <env>/bin/python scripts/m03_nlp_measurements.py [--write]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from m03_support import flowsheet, nlp_formulation, number, reference  # noqa: E402

from openflowsheet.compile.spec import DomainError  # noqa: E402
from openflowsheet.models.syn001 import blocks  # noqa: E402
from openflowsheet.studies.nlp.closure import (  # noqa: E402
    IPOPT_OPTIONS,
    IPOPT_STATUS_NAMES,
    classify_starts,
    optimization_readiness,
)
from openflowsheet.studies.sensitivity import TAU_REGIME  # noqa: E402

if TYPE_CHECKING:
    from openflowsheet.studies.nlp.greybox import StartRun

OUT = ROOT / "benchmarks" / "m03" / "nlp-measurements.json"
FORMAT = "m03-nlp-measurements-v1"
#: The tolerances A35/A36 register (spec §11), by measured quantity: (tolerance, sense), where an
#: `upper` tolerance bounds the measurement from above and a `lower` one from below.
TOLERANCES: dict[str, tuple[float, str]] = {
    "decision_error_scaled": (1e-6, "upper"),  # A35
    "objective_error": (1e-5, "upper"),  # A35
    "v2_scaled_difference": (1e-6, "upper"),  # A36 V2
    "constraint_abs": (1e-6, "upper"),  # A36 V3 |ĝ| (active)
    "constraint_violation": (1e-8, "upper"),  # A36 V3 ĝ ≥ −1e-8
    "regime_margin_min": (TAU_REGIME, "lower"),  # A36 V4
    "multiplier_relative_error": (1e-4, "upper"),  # A36 V5
    "stationarity_residual": (1e-6, "upper"),  # A36 V5
    # Ipopt's own termination tolerances (spec §8.4), against its final unscaled measures.
    "ipopt_primal_infeasibility": (float(IPOPT_OPTIONS["constr_viol_tol"]), "upper"),
    "ipopt_dual_infeasibility": (float(IPOPT_OPTIONS["dual_inf_tol"]), "upper"),
    "ipopt_complementarity": (float(IPOPT_OPTIONS["compl_inf_tol"]), "upper"),
}
#: Spec §14 Q-F2: a measurement closer than this factor to its tolerance stops the work order.
MARGIN_FACTOR = 10.0
#: Q-F4's injected domains (K): NLP-1 from start 0 tries a flash at 365.60 K on its second
#: iteration and accepts it, and its optimum is at 361.50 K (the run without injection).
QF4_CASES: dict[str, dict[str, float | None]] = {
    "residual_at_a_trial_point": {"values_above": 365.0, "jacobian_above": None},
    "jacobian_at_an_accepted_point": {"values_above": None, "jacobian_above": 362.9},
    "residual_at_the_start": {"values_above": 355.0, "jacobian_above": None},
}


@contextlib.contextmanager
def injected_domain(
    values_above: float | None = None, jacobian_above: float | None = None
) -> Iterator[None]:
    """`LnKBlock` refuses a temperature above the given limits with the provider's own
    `DomainError`, only while Ipopt runs (so readiness and the V1 re-solve are untouched)."""
    from pyomo.contrib.pynumero.interfaces.cyipopt_interface import CyIpoptProblemInterface

    active = [False]
    values, jacobian = blocks.LnKBlock.values, blocks.LnKBlock.jacobian
    solve = CyIpoptProblemInterface.solve

    def refusing(method: Any, limit: float | None) -> Any:
        def call(self: Any, inputs: Any) -> Any:
            if active[0] and limit is not None and float(inputs[0]) > limit:
                raise DomainError(f"injected: T = {float(inputs[0])!r} K > {limit} K")
            return method(self, inputs)

        return call

    def solving(self: Any, *args: Any, **kwargs: Any) -> Any:
        active[0] = True
        try:
            return solve(self, *args, **kwargs)
        finally:
            active[0] = False

    blocks.LnKBlock.values = refusing(values, values_above)  # type: ignore[method-assign]
    blocks.LnKBlock.jacobian = refusing(jacobian, jacobian_above)  # type: ignore[method-assign]
    CyIpoptProblemInterface.solve = solving
    try:
        yield
    finally:
        blocks.LnKBlock.values = values  # type: ignore[method-assign]
        blocks.LnKBlock.jacobian = jacobian  # type: ignore[method-assign]
        CyIpoptProblemInterface.solve = solve


def _ratio(value: float, tolerance: float, sense: str) -> float | None:
    """How many times inside its tolerance a measurement lies (`None`: unboundedly)."""
    if sense == "lower":
        return value / tolerance
    return tolerance / value if value > 0.0 else None


def _start_measures(run: StartRun) -> dict[str, Any]:
    formulation = nlp_formulation()
    optimum = reference()["nlp"]["NLP-1"]["reference_optimum"]
    verification = run.verification
    assert run.final_decisions is not None and verification is not None
    assert verification.kkt is not None and verification.objective is not None
    checks = {item.check: item.detail for item in verification.checks}
    (constraint,) = verification.constraint_values.values()
    (multiplier,) = verification.kkt.multipliers.values()
    mu_star = number(optimum["multiplier_recovery_scaled"])
    final = run.ipopt_final or {}
    measured = {
        "decision_error_scaled": max(
            abs(value - number(optimum[decision.parameter_id])) / decision.scale
            for decision, value in zip(formulation.decisions, run.final_decisions, strict=True)
        ),
        "objective_error": abs(verification.objective - number(optimum["objective"])),
        "v2_scaled_difference": checks["V2"]["scaled_difference_inf"],
        "constraint_abs": abs(constraint),
        "constraint_violation": max(0.0, -constraint),
        "regime_margin_min": min(split["margin"] for split in checks["V4"]["splits"]),
        "multiplier_relative_error": abs(multiplier - mu_star) / mu_star,
        "stationarity_residual": verification.kkt.stationarity_residual,
        "ipopt_primal_infeasibility": final["primal_infeasibility"],
        "ipopt_dual_infeasibility": final["dual_infeasibility"],
        "ipopt_complementarity": final["complementarity"],
    }
    return {
        "start": list(run.start),
        "ipopt_status": run.ipopt_status,
        "ipopt_status_name": IPOPT_STATUS_NAMES.get(run.ipopt_status or 0),
        "iterations": run.iterations,
        "evaluations": run.evaluations,
        "final_decisions": list(run.final_decisions),
        "measured": {
            name: {
                "value": value,
                "tolerance": TOLERANCES[name][0],
                "sense": TOLERANCES[name][1],
                "ratio": _ratio(value, *TOLERANCES[name]),
            }
            for name, value in measured.items()
        },
    }


def measure() -> dict[str, Any]:
    from openflowsheet.studies.nlp import greybox

    if os.environ.get("OMP_NUM_THREADS") != "1":
        raise SystemExit("the measurements need OMP_NUM_THREADS=1 (module docstring)")
    sheet, formulation = flowsheet({}), nlp_formulation()
    readiness = optimization_readiness(formulation, sheet)
    if readiness.status != "READY_FOR_OPTIMIZATION":
        raise SystemExit(f"NLP-1 is not ready: {[r.as_document() for r in readiness.reasons]}")
    runs = [
        greybox.solve_start(sheet, formulation, start, index)
        for index, start in enumerate(readiness.starts)
    ]
    starts = [_start_measures(run) for run in runs]
    closest = min(
        (
            (item["ratio"], name, index)
            for index, start in enumerate(starts)
            for name, item in start["measured"].items()
            if item["ratio"] is not None
        ),
    )
    q_f4 = {}
    for case, limits in QF4_CASES.items():
        with injected_domain(**limits):
            run = greybox.solve_start(sheet, formulation, readiness.starts[0], 0)
        (classification,) = classify_starts([run.evidence()]).classifications
        q_f4[case] = {
            "injected": {key: value for key, value in limits.items() if value is not None},
            "ipopt_status": run.ipopt_status,
            "ipopt_status_name": IPOPT_STATUS_NAMES.get(run.ipopt_status or 0),
            "iterations": run.iterations,
            "evaluations": run.evaluations,
            "final_decisions": list(run.final_decisions) if run.final_decisions else None,
            "checks": (
                {item.check: item.outcome for item in run.verification.checks}
                if run.verification is not None
                else {}
            ),
            "classification": classification,
            "detail": run.detail,
        }
    return {
        "format": FORMAT,
        "environment": {
            "omp_num_threads": os.environ["OMP_NUM_THREADS"],
            "ipopt": greybox.ipopt_version(),
            "options": dict(IPOPT_OPTIONS),
        },
        "q_f2": {
            "problem": "NLP-1",
            "margin_factor": MARGIN_FACTOR,
            "starts": starts,
            "closest": {
                "ratio": closest[0],
                "quantity": closest[1],
                "start": closest[2],
            },
            "within_margin_factor": sorted(
                f"start {index}: {name}"
                for index, start in enumerate(starts)
                for name, item in start["measured"].items()
                if item["ratio"] is not None and item["ratio"] < MARGIN_FACTOR
            ),
        },
        "q_f4": q_f4,
    }


def serialize(document: Any) -> str:
    return json.dumps(document, indent=1, sort_keys=True, allow_nan=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    text = serialize(measure())
    if arguments.write:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT}")
        return 0
    from m03_fixture_compare import measurement_differences  # noqa: PLC0415

    found = (
        measurement_differences(json.loads(text), json.loads(OUT.read_text(encoding="utf-8")))
        if OUT.exists()
        else [f"{OUT} does not exist"]
    )
    if not found:
        print(f"{OUT.name} reproduced")
        return 0
    print(f"{OUT.name} differs from what the adapter measures now (rerun with --write):")
    print("\n".join(f"  {line}" for line in found))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
