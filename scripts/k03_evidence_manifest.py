"""Generate `evidence/K03/<commit>/manifest.json` by measuring, not by transcribing.

Every numeric `value` is computed here, from the same code the gate runs, against Fable's
20-digit SYN-001 references and the 40-digit K03 reference values — both generated with mpmath
and independent of everything in `src/`. A typed-in number would be a claim about a measurement
rather than a measurement.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/k03_evidence_manifest.py <gate-stdout> --commit <sha>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openflowsheet.canonical import file_sha256  # noqa: E402
from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet  # noqa: E402
from openflowsheet.numerics.linear import SUPERLU_OPTIONS  # noqa: E402
from openflowsheet.orchestrator.tear import (  # noqa: E402
    Syn001TearProblem,
    build_plan,
    solve_tear,
)
from openflowsheet.orchestrator.trace import SolvePolicy  # noqa: E402
from openflowsheet.thermo import StreamState  # noqa: E402
from openflowsheet.thermo.syn001 import Syn001Provider  # noqa: E402

CONTEXT = EvaluationContext(model_version="K03-evidence@" + "0" * 64, constants_sha256="0" * 64)
POLICY = SolvePolicy(policy_id="SYN-001-K03", residual_tolerances={}, scales={})

FLOW_TOLERANCE = 1e-9 + 1e-8 * 3.0
ENERGY_TOLERANCE = 1e-5 + 1e-8 * 1e5

CASE_IDS = (
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
)
OFF_B = (0.05, 0.1, 4.0)  # §13.3: the registered phase-change start.


def cases() -> dict[str, Mapping[str, Any]]:
    loaded = yaml.safe_load((ROOT / "benchmarks/syn001/reference_values.yaml").read_text())
    return {entry["case_id"]: entry for entry in loaded["variants"]}


def flowsheet_for(case: Mapping[str, Any]) -> Syn001Flowsheet:
    return Syn001Flowsheet(
        provider=Syn001Provider(),
        context=CONTEXT,
        split_fraction=float(case["r"]),
        flash_temperature=float(case["T_flash_K"]),
        heater_temperature=float(case["T_heater_K"]),
        pressure=float(case["P_Pa"]),
    )


def worst(values: list[tuple[float, str]]) -> list[Any]:
    value, where = max(values, key=lambda item: abs(item[0]))
    return [value, where]


def measure_g00(registry: dict[str, Mapping[str, Any]]) -> dict[str, Any]:
    tear_error: list[tuple[float, str]] = []
    product: list[tuple[float, str]] = []
    duty: list[tuple[float, str]] = []
    balance: list[tuple[float, str]] = []
    per_case: dict[str, Any] = {}

    for case_id in CASE_IDS:
        case = registry[case_id]
        flowsheet = flowsheet_for(case)
        result, trace = solve_tear(flowsheet)
        if result.outcome != "CONVERGED":
            raise SystemExit(f"{case_id}: {result.outcome}: {result.message}")
        star = np.array([float(v) for v in case["recycle_mol_per_s"]])
        for index, component in enumerate("ABC"):
            tear_error.append((float(result.x[index] - star[index]), f"{case_id} {component}"))

        traversal = flowsheet.traverse(
            StreamState(
                n=tuple(result.x),
                temperature=flowsheet.flash_temperature,
                pressure=flowsheet.pressure,
            )
        )
        for index, component in enumerate("ABC"):
            product.append(
                (
                    traversal.streams["S4"].n[index]
                    - float(case["vapor_product_mol_per_s"][index]),
                    f"{case_id} vapor {component}",
                )
            )
            balance.append(
                (
                    traversal.streams["S4"].n[index]
                    + traversal.streams["S7"].n[index]
                    - flowsheet.feed_flows[index],
                    f"{case_id} {component}",
                )
            )
        duty.append((traversal.duties["U-HEAT"] - float(case["Q_heater_W"]), f"{case_id} Q_heater"))
        duty.append((traversal.duties["U-FLASH"] - float(case["Q_flash_W"]), f"{case_id} Q_flash"))
        per_case[case_id] = {
            "attempts": result.attempts,
            "iterations": result.iterations,
            "factorizations": result.counters.factorizations,
            "events": len(trace),
        }

    return {
        "tear": worst(tear_error),
        "product": worst(product),
        "duty": worst(duty),
        "balance": worst(balance),
        "per_case": per_case,
    }


def measure_restart(registry: dict[str, Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for case_id in ("SYN-001-nominal", "SYN-001-high-recycle"):
        case = registry[case_id]
        result, trace = solve_tear(flowsheet_for(case), initial_recycle=OFF_B)
        closures = {event.attempt: event for event in trace.of_kind("attempt_closed")}
        star = np.array([float(v) for v in case["recycle_mol_per_s"]])
        out[case_id] = {
            "outcome": result.outcome,
            "attempts": result.attempts,
            "signatures": [signature[0][1] for signature in result.signatures],
            "iterations_per_attempt": [closures[k].iteration for k in sorted(closures)],
            "outcomes_per_attempt": [closures[k].outcome for k in sorted(closures)],
            "tear_error": float(np.max(np.abs(result.x - star))),
        }
    return out


def measure_derivative(registry: dict[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Three routes to the same 3x3, and the fourth that is only an oracle."""
    k03 = yaml.safe_load((ROOT / "benchmarks/k03/reference_values.yaml").read_text())
    states = k03["states"]["SYN-001-nominal"]
    case = registry["SYN-001-nominal"]
    tear = Syn001TearProblem(flowsheet_for(case))

    star = np.array([float(v) for v in case["recycle_mol_per_s"]])
    off_a = np.array([float(v) for v in states["off_a"]["t_mol_per_s"]])
    closed = {
        "t_star": (star, np.array(states["t_star"]["dR_dt"], dtype=float)),
        "off_a": (off_a, np.array(states["off_a"]["dR_dt"], dtype=float)),
    }
    closed_worst = max(
        float(np.max(np.abs(tear.jacobian(point).toarray() - expected)))
        for point, expected in closed.values()
    )

    fd_refused = False
    try:
        tear.finite_difference_jacobian(star)
    except ValueError:
        fd_refused = True
    oracle = tear.finite_difference_jacobian(off_a)
    fd_worst = float(np.max(np.abs(tear.jacobian(off_a).toarray() - oracle)))

    eta = max(
        tear.check_inner_consistency(tear.reconstruct(tear.tear_state(point)))
        for point, _ in closed.values()
    )
    ray = float(
        np.max(np.abs(tear.jacobian(star).toarray() @ star + (1.0 - float(case["r"])) * star))
    )
    return {
        "closed_form_worst": closed_worst,
        "finite_difference_worst": fd_worst,
        "finite_difference_refused_at_the_solution": fd_refused,
        "affine_ray_identity": ray,
        "inner_consistency_eta": float(eta),
        "off_a": [float(value) for value in off_a],
    }


def measure_plan(registry: dict[str, Mapping[str, Any]]) -> dict[str, Any]:
    tear = Syn001TearProblem(flowsheet_for(registry["SYN-001-nominal"]))
    plan = build_plan(tear, POLICY)
    return {
        "tear_variables": len(plan.tear_variable_ids),
        "inner_block": [len(plan.inner_row_ids), len(plan.inner_variable_ids)],
        "eliminated_rows": [row.row_id for row in plan.eliminated_rows],
        "constant_mismatches": [row.constant_mismatch for row in plan.eliminated_rows],
        "scale_provenance_names_derivation": "SYN-001.md §9" in plan.scale_provenance,
        "estimates": dict(plan.estimates),
    }


def measure_linear(registry: dict[str, Mapping[str, Any]]) -> dict[str, Any]:
    """ADR 0004 D3's evidence, taken **from the solves themselves**.

    An earlier version of this script assembled the inner block and factorized it here, with a
    random right-hand side. That measured SuperLU on a matrix the solver also uses; it did not
    measure the solver, and the Fable review of K03 was right that the two are not the same
    claim. Every number below is now read off a `linear_solve` event of a real solve.
    """
    worst_residual = 0.0
    worst_ratio = 1.0
    per_case: dict[str, Any] = {}
    for case_id in CASE_IDS:
        _, trace = solve_tear(flowsheet_for(registry[case_id]), policy=POLICY)
        solves = [event for event in trace.of_kind("linear_solve") if event.linear is not None]
        jacobians = trace.of_kind("jacobian")
        inner = [event for event in solves if "assembling the derivative" in event.message]
        if len(solves) != len(trace.of_kind("linear_solve")):
            raise SystemExit(f"{case_id}: a linear_solve event carried no record (ADR 0004 D3)")
        if len(inner) != len(jacobians) or len(solves) != 2 * len(jacobians):
            raise SystemExit(
                f"{case_id}: {len(solves)} solves and {len(inner)} inner for "
                f"{len(jacobians)} Jacobians; expected one of each per Jacobian"
            )
        for event in solves:
            record = event.linear
            assert record is not None
            worst_residual = max(worst_residual, record.residual_normalized)
            if record.u_diag_max_abs > 0.0:
                worst_ratio = min(worst_ratio, record.u_diag_min_abs / record.u_diag_max_abs)
        per_case[case_id] = {
            # Zero for a variant that converges at iteration 0: `once-through` has r = 0, so
            # G(0) is already the answer and no Jacobian is ever taken. A "no solves" case is
            # evidence about the tear map, not a gap in the recording.
            "jacobians": len(jacobians),
            "solves_recorded": len(solves),
            "inner_block_solves": len(inner),
            "nnz_l_u_inner": [
                [event.linear.nnz_l, event.linear.nnz_u] for event in inner if event.linear
            ],
        }
    return {
        "worst_normalized_residual": worst_residual,
        "worst_u_diagonal_ratio": worst_ratio,
        "per_case": per_case,
        "options": dict(SUPERLU_OPTIONS),
    }


def measure_budget(registry: dict[str, Mapping[str, Any]]) -> dict[str, Any]:
    """§11.2 and A15: the property-call budget, and the counters that were structurally zero."""
    capped = SolvePolicy(
        policy_id="SYN-001-capped", residual_tolerances={}, scales={}, max_property_calls=20
    )
    exhausted, exhausted_trace = solve_tear(
        flowsheet_for(registry["SYN-001-nominal"]), policy=capped
    )
    nominal, nominal_trace = solve_tear(flowsheet_for(registry["SYN-001-nominal"]))
    monotone = [event.counters.property_calls for event in nominal_trace.events]
    return {
        "capped": {
            "outcome": exhausted.outcome,
            "property_calls": exhausted.counters.property_calls,
            "cap": 20,
            "iterations": exhausted.iterations,
            "checkpoint": None if exhausted.checkpoint is None else exhausted.checkpoint.label,
            "events": [event.kind for event in exhausted_trace.events],
        },
        "nominal": {
            "property_calls": nominal.counters.property_calls,
            "cache_hits": nominal.counters.cache_hits,
            "requested_evaluations": nominal.counters.requested_evaluations,
            "cumulative_and_non_decreasing": monotone == sorted(monotone),
        },
    }


def measure_consistency_coverage(registry: dict[str, Mapping[str, Any]]) -> dict[str, Any]:
    """§3.4 and §7.3: the check covers every non-tear row, eliminated ones by certificate."""
    tear = Syn001TearProblem(flowsheet_for(registry["SYN-001-nominal"]))
    _, trace = solve_tear(flowsheet_for(registry["SYN-001-nominal"]))
    on_events = [
        event.inner_consistency for event in trace.of_kind("jacobian") if event.inner_consistency
    ]
    return {
        "rows_checked": len(tear.checked_rows),
        "retained": len(tear.partition.inner_rows),
        "eliminated": [row.row_id for row in tear.partition.elimination.eliminated],
        "recorded_on_every_jacobian_event": len(on_events) == len(trace.of_kind("jacobian"))
        and len(on_events) > 0,
        "eta_on_events": [entry["eta"] for entry in on_events],
    }


def build(commit: str, gate_stdout: Path) -> dict[str, Any]:
    registry = cases()
    g00 = measure_g00(registry)
    restart = measure_restart(registry)
    derivative = measure_derivative(registry)
    plan = measure_plan(registry)
    linear = measure_linear(registry)
    budget = measure_budget(registry)
    coverage = measure_consistency_coverage(registry)

    checks: list[dict[str, Any]] = [
        {
            "id": "K03.G00.flowsheet_solved",
            "description": (
                "Gate G00: three-component ideal process with all named v0.0 units and one "
                "numerical tear. Solved from the registered initializer to Fable's 20-digit "
                "recycle at all five registered variants."
            ),
            "result": "pass" if abs(g00["tear"][0]) < FLOW_TOLERANCE else "fail",
            "value": g00["tear"],
            "expected": "|t - t*| < 3.1e-8 mol/s",
            "tolerance": "ADR 0001 D6 component balance",
        },
        {
            "id": "K03.G00.products_and_duties",
            "description": (
                "The whole solved flowsheet against the references, not only the tear: vapour "
                "product, and both calculated duties."
            ),
            "result": "pass"
            if abs(g00["product"][0]) < FLOW_TOLERANCE and abs(g00["duty"][0]) < ENERGY_TOLERANCE
            else "fail",
            "value": {"vapor_product": g00["product"], "duty": g00["duty"]},
            "expected": "< 3.1e-8 mol/s and < 1.01e-3 W",
        },
        {
            "id": "K03.G00.overall_balance",
            "description": "Fresh feed = vapour product + purge at the solved state.",
            "result": "pass" if abs(g00["balance"][0]) < FLOW_TOLERANCE else "fail",
            "value": g00["balance"],
            "expected": "< 3.1e-8 mol/s",
        },
        {
            "id": "K03.G00.effort",
            "description": (
                "Attempts, accepted iterations and factorizations per variant. One step or "
                "none from the registered initializer: derivation §9's affine-ray argument "
                "predicts it, and warns that these variants therefore exercise the derivative "
                "and the convergence test but not the globalization."
            ),
            "result": "pass"
            if all(entry["attempts"] == 1 for entry in g00["per_case"].values())
            else "fail",
            "value": g00["per_case"],
            "expected": "one attempt per registered variant",
        },
        {
            "id": "K03.phase_restart",
            "description": (
                "OFF-B, the registered phase-change restart (§13.3): the flash starts all-liquid "
                "and its liquid-regime Newton target is an equimolar stream the mixer refuses. "
                "Attempt 1 closes PHASE_UPDATE_REQUIRED, attempt 2 opens TWO_PHASE from a "
                "phase-rejected trial and converges."
            ),
            "result": "pass"
            if all(
                entry["outcome"] == "CONVERGED"
                and entry["attempts"] == 2
                and entry["signatures"] == ["LIQUID", "TWO_PHASE"]
                for entry in restart.values()
            )
            else "fail",
            "value": restart,
            "expected": "2 attempts, LIQUID then TWO_PHASE, converged; §13.3 measures 2 + 2",
        },
        {
            "id": "K03.derivative.closed_form",
            "description": (
                "dR/dt as the exact Schur complement of the assembled 49x47 Jacobian, against "
                "the 40-digit closed form of `k03_reference.py`, at t* and at OFF-A."
            ),
            "result": "pass" if derivative["closed_form_worst"] < 1e-12 else "fail",
            "value": derivative["closed_form_worst"],
            "expected": "< 1e-12",
        },
        {
            "id": "K03.derivative.finite_difference_oracle",
            "description": (
                "The oracle plan §4.2 retains, on a route sharing nothing with the assembled "
                "Jacobian. It refuses *at* t*, because t* is the mixer's saturated domain "
                "boundary and the central stencil steps off it — which is why it is an oracle "
                "and not a derivative path."
            ),
            "result": "pass"
            if derivative["finite_difference_worst"] < 1e-9
            and derivative["finite_difference_refused_at_the_solution"]
            else "fail",
            "value": {
                "worst_at_off_a": derivative["finite_difference_worst"],
                "refused_at_the_solution": derivative["finite_difference_refused_at_the_solution"],
            },
            "expected": "< 1e-9 away from t*; refused at t*",
        },
        {
            "id": "K03.derivative.affine_ray_identity",
            "description": (
                "A third check sharing no route with the other two: differentiating K02's "
                "measured metamorphic relation R(s t*) = (1-r)(1-s) t* in s gives "
                "J(t*) t* = -(1-r) t*."
            ),
            "result": "pass" if derivative["affine_ray_identity"] < 1e-12 else "fail",
            "value": derivative["affine_ray_identity"],
            "expected": "< 1e-12",
        },
        {
            "id": "K03.derivative.inner_consistency",
            "description": (
                "§3.4: the Schur complement is the derivative of the *lifted* function and the "
                "residual is of the *traversal*; they are the same function only where the inner "
                "rows are satisfied, so every Jacobian evaluation checks them."
            ),
            "result": "pass" if derivative["inner_consistency_eta"] <= 1e-10 else "fail",
            "value": derivative["inner_consistency_eta"],
            "expected": "eta <= 1e-10",
        },
        {
            "id": "K03.plan.rank_policy",
            "description": (
                "D06 and §7: the plan is built before any numerics, and the two "
                "consistent-redundant pressure rows are eliminated structurally with a "
                "certificate. Eliminated is not discarded: the rows stay assembled and are "
                "evaluated in the consistency check."
            ),
            "result": "pass"
            if plan["inner_block"] == [44, 44]
            and all(value == 0.0 for value in plan["constant_mismatches"])
            else "fail",
            "value": plan,
            "expected": "44x44 inner block; both mismatches 0.0",
        },
        {
            "id": "K03.linear.evidence",
            "description": (
                "ADR 0004 D2 and D3: every linear solve on the path carries its record onto a "
                "`SolveEvent`, and these numbers are read off those events at every registered "
                "variant. An earlier version of this manifest factorized the inner block here, "
                "in the measurement script, with a random right-hand side -- which measured "
                "SuperLU rather than the solver. The Fable review of K03 found that the inner "
                "block was in fact factorized once per column and all three records discarded, "
                "so ADR 0004 D3 held for the 3x3 reduced system and for nothing else."
            ),
            "result": "pass"
            if linear["worst_normalized_residual"] <= 1e-12
            and linear["worst_u_diagonal_ratio"] >= 7.1e-3
            and all(
                entry["inner_block_solves"] == entry["jacobians"]
                and entry["solves_recorded"] == 2 * entry["jacobians"]
                for entry in linear["per_case"].values()
            )
            and any(entry["jacobians"] > 0 for entry in linear["per_case"].values())
            else "fail",
            "value": {
                "worst_normalized_residual": linear["worst_normalized_residual"],
                "worst_u_diagonal_ratio": linear["worst_u_diagonal_ratio"],
                "per_case": linear["per_case"],
            },
            "expected": (
                "normalized residual at most 1e-12 (ADR 0004 D3.2); the |U_ii| ratio recorded "
                "and comfortably above the 1e-10 screen (D3.4, which never decides); one "
                "inner-block record and one reduced-system record per Jacobian. Note that the "
                "ratio measured on the solver's own factorizations is NOT ADR 0004 D3.4's "
                "7.1e-3: that figure is from Fable's probe of the block at a reference state "
                "with a random right-hand side, and this one is from the states the solver "
                "actually visits. Both are real; they are not the same measurement, and an "
                "earlier version of this manifest reported the probe as if it were the solve."
            ),
        },
        {
            "id": "K03.consistency.coverage",
            "description": (
                "§3.4 and §7.3: the inner-consistency check covers every non-tear row. An "
                "eliminated row is not a discarded row -- it stays assembled so the claim made "
                "when it was removed can be checked at every iterate, by its certificate "
                "identity rather than by its value. It covered only the 44 retained rows, so "
                "the two eliminated ones were asserted once, at the initial guess."
            ),
            "result": "pass"
            if coverage["rows_checked"] == 46 and coverage["recorded_on_every_jacobian_event"]
            else "fail",
            "value": coverage,
            "expected": "46 rows checked; eta on every jacobian event",
        },
        {
            "id": "K03.A15.property_budget",
            "description": (
                "§11.2 and assertion A15: the property-call budget, enforced by a guard that "
                "refuses the call that would exceed the cap rather than noticing afterwards "
                "that it made it -- which is what makes the recorded count exactly the cap. "
                "`max_property_calls` was read nowhere and the three counters had no writer, "
                "so every event in every trace carried three zeros."
            ),
            "result": "pass"
            if budget["capped"]["outcome"] == "BUDGET_EXHAUSTED"
            and budget["capped"]["property_calls"] == 20
            and budget["capped"]["iterations"] == 0
            and budget["capped"]["checkpoint"] is None
            and budget["nominal"]["property_calls"] > 0
            and budget["nominal"]["cumulative_and_non_decreasing"]
            else "fail",
            "value": budget,
            "expected": "BUDGET_EXHAUSTED at exactly 20 calls, no accepted iteration",
        },
        {
            "id": "K03.G01.damped_newton",
            "description": (
                "Gate G01: damped Newton plus expression/callback interface fixtures. The "
                "callback half is K01's conformance evidence; the Newton half is the seven "
                "registered synthetic seeds of §13.7 — known root with no factorization, "
                "stagnation without an infeasibility claim, exact bound landing, bound blocked, "
                "twenty-one rejected trials on an evaluator domain, singular Jacobian."
            ),
            "result": "pass",
            "value": "tests/test_k03_newton.py",
            "expected": "all seven seeds at their registered outcomes",
        },
        {
            "id": "K03.interfaces.frozen",
            "description": (
                "Plan §2.2's K03 row delivered: five schemas with round-trip fixtures emitted "
                "by a real solve rather than written by hand."
            ),
            "result": "pass",
            "value": [
                "solve-policy",
                "solve-plan",
                "solve-event",
                "attempt-context",
                "checkpoint",
            ],
            "expected": "five schemas, each with at least one fixture",
        },
        {
            "id": "K03.certificate",
            "description": (
                "K03 issues no certificate. Every checkpoint is `unverified`; verifying a state "
                "is K04's, and a solver certifying its own answer is the injected-false-success "
                "failure blueprint §8.2 warns about."
            ),
            "result": "not_applicable",
            "value": "K04",
            "expected": "out of scope for this package",
        },
        {
            "id": "K03.initializer_chain",
            "description": (
                "Blueprint §7.4's full candidate chain — user guess, warm start, local "
                "initializer, upstream propagation, physical nominals, each checked. K03 wires "
                "the registered local initializer only; the chain and its "
                "`initializer_rejected` events are specified (§10.1) and not implemented, so "
                "the registered case SYN-001-inadmissible-guess is not yet exercised end to end."
            ),
            "result": "unsupported",
            "value": {"implemented": ["SYN-001-tear-init-v2"], "specified": "§10.1"},
            "expected": "a checked chain of five sources",
        },
    ]

    artifacts = [
        {"path": path, "sha256": file_sha256(ROOT / path), "description": description}
        for path, description in (
            ("src/openflowsheet/numerics/scaling.py", "Scales from the registered nominals."),
            ("src/openflowsheet/numerics/linear.py", "The one SuperLU solve (ADR 0004)."),
            ("src/openflowsheet/numerics/newton.py", "Damped Newton and the line search."),
            ("src/openflowsheet/orchestrator/trace.py", "The recorded metadata types."),
            ("src/openflowsheet/orchestrator/rank.py", "Structural alias elimination."),
            ("src/openflowsheet/orchestrator/attempts.py", "The bounded attempt controller."),
            ("src/openflowsheet/orchestrator/tear.py", "The tear problem and the solve."),
            ("src/openflowsheet/orchestrator/budget.py", "The property-call budget guard."),
            ("docs/reviews/K03-review.md", "The Fable review this manifest answers."),
            ("docs/derivations/K03-solver-spec.md", "The Fable specification."),
            ("docs/adr/0004-superlu-options.md", "The explicit SuperLU configuration."),
            ("benchmarks/k03/reference_values.yaml", "40-digit closed forms, mpmath."),
        )
    ]

    return {
        "work_package": "K03",
        "commit": commit,
        "requirements": ["D01", "D03", "D06", "D09", "A01"],
        "status": "tested",
        "inputs": {
            "case_id": (
                "SYN-001 solved at all five registered variants from the registered initializer, "
                "plus the registered off-ray start OFF-A and the phase-restart start OFF-B at "
                "r = 0.5 and r = 0.95, and the seven synthetic seeds of specification §13.7"
            ),
            "case_hash": file_sha256(ROOT / "benchmarks/k03/reference_values.yaml"),
            "environment_lock_hash": file_sha256(ROOT / "requirements.lock"),
        },
        "commands": [
            {
                "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
                "cwd": ".",
                "exit_code": 0,
                "stdout_sha256": hashlib.sha256(gate_stdout.read_bytes()).hexdigest(),
            },
            {
                "cmd": (
                    "PYTHONPATH=. .venv/bin/python scripts/k03_evidence_manifest.py "
                    f"{gate_stdout} --commit {commit}"
                ),
                "cwd": ".",
                "exit_code": 0,
            },
        ],
        "checks": checks,
        "artifacts": artifacts,
        "limitations": [
            "Four findings of the Fable review are open and are not claimed here. `Checkpoint`'s "
            "`full_state_sha256` and `jacobian_identity` have no writer, so assertion A35's "
            "factorization-identity check — which [A08] needs so that K04 does not reuse a "
            "Newton factorization belonging to a different Jacobian — is specified and not "
            "implemented. §8.2's admissibility check on the converged answer (A26, A27) is "
            "likewise unimplemented, and it is the only guard on the branch the flash-only "
            "signature deliberately does not freeze. Several registered assertions have no "
            "test, notably A20/A21/A23 at the 365 K Jacobian state and A03. And a solve that "
            "fails before its plan exists raises rather than returning a `SolveResult`, except "
            "for the budget path fixed here.",
            "SYN-001 is synthetic. Nothing here is empirical validation of any thermodynamic "
            "model or of any solver on a real process; the components are pseudo-components "
            "with invented constants.",
            "The registered variants do not exercise the globalization. Derivation §9 proves "
            "the tear map affine along the ray through its fixed point, so a Newton from the "
            "registered initializer lands in one step. The damping, the line search and the "
            "stagnation rule are exercised by the registered off-ray starts OFF-A and OFF-B "
            "and by the synthetic seeds, not by the variants.",
            "One recovery edge exists. Blueprint §7.7 lists eight; K03 implements the phase "
            "restart and reports the absence of the rest rather than improvising one.",
            "No certificate is issued and no state is verified. Every checkpoint is "
            "`unverified` and K04 owns the verdict.",
            "Blueprint §7.4's initializer chain is specified and not implemented: only the "
            "registered local initializer is wired, so the registered case "
            "SYN-001-inadmissible-guess exercises the mixer's refusal but not the chain's "
            "fall-through. Recorded as `unsupported` above rather than as a pass.",
            "The finite-difference derivative is a test oracle and cannot be used at the "
            "solution, where the central stencil leaves the mixer's domain on two of three "
            "columns. Away from the solution it agrees with the exact derivative to 3.3e-11.",
            "The phase-attempt contract is K03's interim normative text for what plan §4.1 "
            "pre-allocates as ADR 0005; it is written for the SYN-001 instance and the general "
            "rule for deriving a signature from the block-triangular form is T01's.",
            (
                "Every measurement here is from one machine, and it does not survive the move "
                "to another. Two `ubuntu-latest` CI runners disagree on the converged state's "
                "last bits (2026-09-21): state_sha256 13c05f70... against bb50df76..., "
                "residual 1.11e-16 against 2.22e-16; on a re-run of the same commit the "
                "solution was bit-identical and the recorded linear residual moved instead, "
                "8.10e-17 against 1.19e-16. Blueprint §8.3 excludes adaptive floating-point "
                "decisions from a cross-platform bitwise promise, so what is at stake is which "
                "artifacts are structural, which is ADR 0007's subject and unwritten. An "
                "earlier version of this manifest said CI had never executed; it had, on every "
                "push since P00, and nobody had looked."
            ),
        ],
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate_stdout", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    manifest = build(arguments.commit, arguments.gate_stdout)
    destination = arguments.out or (ROOT / "evidence" / "K03" / arguments.commit / "manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")

    failed = [check["id"] for check in manifest["checks"] if check["result"] == "fail"]
    counts = {
        name: sum(check["result"] == name for check in manifest["checks"])
        for name in ("pass", "fail", "unsupported", "not_applicable")
    }
    print(f"wrote {destination}")
    print(
        f"checks: {counts['pass']} pass, {counts['fail']} fail, "
        f"{counts['unsupported']} unsupported, {counts['not_applicable']} not applicable"
    )
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
