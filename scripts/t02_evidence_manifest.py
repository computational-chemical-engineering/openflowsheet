"""Generate `evidence/T02/<commit>/manifest.json` by measuring, not by transcribing. T02.

Every value recorded here is produced by running the code in this process and comparing it with
an independent expectation: `benchmarks/t02/reference_values.yaml` (Fable's closed forms and the
registered recycle policy restated at 40 digits by `docs/derivations/scripts/t02_reference.py`),
`benchmarks/syn001/reference_values.yaml` (P01's 20-digit values), or a closed form stated in the
check itself. Nothing is copied from the specification's prose: a manifest that quoted the document
it is evidence for would be evidence of nothing.

The registered assertions are `docs/derivations/T02-recycle-spec.md` §10's `A00`…`A36`, one check
each. The case builders — the manufactured maps, the SYN-001 flowsheets, the A02 revisions — are
imported from the package's tests so that the manifest and the gate run the same fixtures; the
measurements, and what they are compared with, are stated here.

Two halves cannot be measured on one machine: the cross-platform equality of A02 and A34, which
CI's `identity` job establishes. Pass `--identities DIR` (the two downloaded
`structural-identity-*` artifacts, each holding `identity.json` and `t02-floats.json`) and this
script applies the comparison the CI job applies; without it those checks are `unsupported`, never
`pass`. `--ci-run URL` names the workflow run and is recorded in `commands`.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/t02_evidence_manifest.py <gate-stdout> --commit <sha> \
        [--identities DIR] [--ci-run URL] [--out PATH]
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

# The registered fixtures, shared with the gate (see the module note).
import test_t02_a02 as a02_fixtures  # noqa: E402
import test_t02_executor as executor_fixtures  # noqa: E402
import test_t02_merge as merge_fixtures  # noqa: E402
import test_t02_plan as plan_fixtures  # noqa: E402
import test_t02_recycle as recycle_fixtures  # noqa: E402
import test_t02_region as region_fixtures  # noqa: E402

from openflowsheet.canonical import file_sha256  # noqa: E402
from openflowsheet.numerics.anderson import (  # noqa: E402
    RecyclePolicy,
    RecycleResult,
    solve_recycle,
)
from openflowsheet.orchestrator.trace import Trace  # noqa: E402

REFERENCE = ROOT / "benchmarks" / "t02" / "reference_values.yaml"
P01 = ROOT / "benchmarks" / "syn001" / "reference_values.yaml"
SPEC = ROOT / "docs" / "derivations" / "T02-recycle-spec.md"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "t02_reference.py"
CASES = ROOT / "benchmarks" / "syn001" / "cases"

VARIANTS = (
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
)
REC = ("REC-01", "REC-02", "REC-03", "REC-04", "REC-05")
A02_CASES = (
    "SYN-001-A02-360",
    "SYN-001-A02-365",
    "SYN-001-A02-355",
    "SYN-001-A02-360-liquid-guess",
    "SYN-001-A02-355-liquid-guess",
)
#: `τ_R`, and `τ̂ = τ_R / 3` at the registered tear scale (spec §10 conventions).
TAU = 3.1e-8
TAU_HAT = TAU / 3.0
#: §6.4: ten times each kind's residual tolerance.
FLOW, TEMPERATURE, DUTY = 3.1e-7, 1e-5, 1e-2
#: The assertion ids of spec §10, `A00`…`A36`.
ASSERTIONS = tuple(f"A{index:02d}" for index in range(37))


def check(
    identifier: str, description: str, result: str, value: Any, expected: Any
) -> dict[str, Any]:
    return {
        "id": identifier,
        "description": description,
        "result": result,
        "value": value,
        "expected": expected,
    }


def verdict(condition: bool) -> str:
    return "pass" if condition else "fail"


def measured(
    identifier: str,
    description: str,
    measure: Callable[[], tuple[bool, Any, Any]],
) -> dict[str, Any]:
    """Run one assertion's measurement. An exception is a failed measurement, recorded as such:
    a check that could not run did not pass, and hiding the error would hide the finding."""
    try:
        condition, value, expected = measure()
    except Exception as error:  # noqa: BLE001 - every failure is recorded, none is swallowed
        return check(
            identifier,
            description,
            "fail",
            {"error": f"{type(error).__name__}: {error}"},
            "the measurement runs to completion",
        )
    return check(identifier, description, verdict(condition), value, expected)


def number(value: Any) -> float:
    return float(value)


def plain(value: Any) -> Any:
    """A JSON-safe copy: numpy scalars and arrays as Python numbers, non-finite as strings."""
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [plain(item) for item in value]
    if isinstance(value, np.ndarray):
        return [plain(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    return value


def relative_off(found: float, expected: float) -> float:
    return abs(found - expected) / abs(expected) if expected != 0.0 else abs(found)


def worst_relative(
    found: Sequence[float], registered: Sequence[Any], through: int, floor: float = 0.0
) -> float:
    """The worst relative departure of a trajectory from the twin's, over `k = 0…through`, where
    the registered value exceeds `floor` (spec §5.9: below `1e-6` roundoff dominates)."""
    worst = 0.0
    for k in range(min(through + 1, len(registered))):
        expected = number(registered[k])
        if abs(expected) <= floor:
            continue
        worst = max(worst, relative_off(found[k], expected))
    return worst


def recycle_summary(result: RecycleResult) -> dict[str, Any]:
    return {
        "outcome": result.outcome,
        "iterations": result.iterations,
        "restarts": [(event.iteration, event.count, event.reason) for event in result.restarts],
        "stagnation_closures": list(result.stagnation_closures),
        "columns_dropped_condition": result.columns_dropped_condition,
        "columns_dropped_coefficient": result.columns_dropped_coefficient,
        "bound_landings": result.bound_landings,
        "invalid_trials": result.invalid_trials,
        "oscillation_detected_at": result.oscillation_detected_at,
        "anderson_steps": result.anderson_steps,
        "plain_steps": result.plain_steps,
        "residual_increases": result.residual_increases,
    }


# --------------------------------------------------------------------------------- the build


def build(
    commit: str,
    gate_stdout: Path,
    identities: Path | None,
    ci_run: str | None,
) -> dict[str, Any]:
    ref: dict[str, Any] = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))
    gate = _gate(gate_stdout)
    checks: list[dict[str, Any]] = []
    #: Every recycle result measured below, for A32's "every restart event" (spec §10).
    recycle_runs: dict[str, RecycleResult] = {}

    checks.append(
        measured(
            "T02.A00",
            "Generator self-check: `t02_reference.py --check` passes with 114 checks; the "
            "committed YAML's SHA-256 equals the one in the specification header; `--emit` twice "
            "gives identical bytes, equal to the committed file; the generator and its two "
            "sibling closed-form scripts import nothing from `openflowsheet` or `benchmarks` "
            "(every import statement, read from the syntax tree).",
            lambda: _a00(),
        )
    )
    checks.append(
        measured(
            "T02.A01",
            "Plan shape: at the five SYN-001 variants the `ExecutionPlan` equals "
            "`ref.syn001.plans['SYN-001-nominal (tear)']`, validates against "
            "`execution-plan.schema.json`, and every step's `solve_plan` against "
            "`solve-plan.schema.json` unchanged; the builder calls no analysis, compiler or "
            "provider (spied, zero calls), so the analysis runs once per plan — the caller's. "
            "NEST-1 (`tests/test_t02_plan.nest_structure`: the linear scalar flowsheet of "
            "`ref.cases_auxiliary.NEST-1.units`, each stream's columns owned by its producer), "
            "through the same builder: `[evaluate FEED, converge {A, B, C} tear [s4, s5]]` with "
            "tear variables `(s4.x, s5.x)` and tear rows `(B:s4, C:s5)`, schema-valid.",
            lambda: _a01(ref),
        )
    )
    checks.append(_a02(identities))
    checks.append(
        measured(
            "T02.A03",
            "Solver choice: `auto` resolves to `newton_tear` on SYN-001 and on NEST-1's units "
            "declaring `residuals/ad`, and to `anderson` when one loop unit declares "
            "`unavailable` (test double); the tear rows' and tear columns' scales are equal "
            "componentwise on every registered plan (the five SYN-001 variants and NEST-1). "
            "NEST-1's non-capable double: unit B declaring no residual derivative.",
            lambda: _a03(),
        )
    )
    anderson_syn001 = _syn001_anderson()
    checks.append(
        measured(
            "T02.A04",
            "SYN-001 under `anderson` from `t⁰`: iterations exactly 2 (nominal, high-recycle, "
            "310 K) and 0 (once-through, 420 K); `|t − t*|∞ ≤ τ_R`; no `restart` event, no column "
            "drop, no bound landing (every accepted step has α = 1) and no rejected trial; "
            "`depth_used` on the second step is 1.",
            lambda: _a04(anderson_syn001),
        )
    )
    checks.append(
        measured(
            "T02.A05",
            "SYN-001 under `anderson` from OFF-A `(0.1, 0.8, 1.2)` at the three 360 K variants "
            "(nominal, high-recycle, once-through): CONVERGED to `t*` within `τ_R`, iterations "
            "≤ 15, zero `invalid_trial` rejections, one attempt.",
            lambda: _a05(anderson_syn001),
        )
    )
    checks.append(
        measured(
            "T02.A06",
            "SYN-001 under `anderson` from OFF-B `(0.05, 0.1, 4.0)` at `r = 0.5`: CONVERGED to "
            "`t*` within `τ_R`; exactly 2 attempts with the flash LIQUID then TWO_PHASE (K03 "
            "§13.3's contract); at least one `invalid_trial` rejection, every one naming `U-MIX`; "
            "accepted iterations ≤ 40.",
            lambda: _a06(anderson_syn001),
        )
    )
    checks.append(
        measured(
            "T02.A07",
            "REC-01..05 linear (`γ = 0`) under the registered policy: iterations exactly 4 (the "
            "Krylov grade 3 plus one, registered); trajectory `k = 0..3` equals the 40-digit "
            "twin's to `1e-9` relative; zero restarts, column drops, landings and invalid trials; "
            "`|t − t*|∞ ≤ 1e-5 mol/s`.",
            lambda: _a07(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A08",
            "REC-01..05 with the tail (`γ = 0.1`): CONVERGED; trajectory `k = 0..5` equals the "
            "twin's to `1e-8` relative wherever the registered value exceeds `1e-6`; iterations "
            "in `[ref, ref + 2]`; REC-01..04 within `1e-5` of `t*`; REC-05 within `1e-4` of the "
            "registered second fixed point `S1` and farther than 1 from `t*`.",
            lambda: _a08(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A09",
            "REC-01 under `depth_max = 0`: `oscillation_detected` at iteration 3, "
            "`beta_substitution` 1 on the first three steps and 0.5 on every one after, CONVERGED "
            "at ≤ 60 iterations and at exactly the twin's count.",
            lambda: _a09(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A10",
            "REC-02 under `depth_max = 0`: the second accepted iterate is `(+0.0, "
            "1.7333333333333333, 2.924)` with `t_A` bit-exactly `+0.0` after a bound landing at "
            "`α_max = 14/15`; the closed-form unbounded iterate `t_A = −0.125` is the reason; "
            "`oscillation_detected` at 3; CONVERGED ≤ 60; zero `invalid_trial` rejections. Under "
            "Anderson (both `γ`): zero landings and zero invalid trials.",
            lambda: _a10(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A11",
            "REC-03 under `depth_max = 0`: `BUDGET_EXHAUSTED` at 200 with `‖f̂‖∞ > τ̂` (closed "
            "form `0.65 · 0.95²⁰⁰`); `ref.best_damping` is `ω* = 1`, rate 0.95; under Anderson "
            "4 (linear) and ≤ 9 (tail).",
            lambda: _a11(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A12",
            "REC-04 under `depth_max = 0` for 200 iterations: the oscillation flag never sets. "
            "Under Anderson: 4 (linear) and ≤ 9 (tail).",
            lambda: _a12(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A13",
            "REC-05 linear under Anderson: the residual at iterates 1 and 2 exceeds iterate 0's "
            "(`residual_increases ≥ 1`), no restart, no stagnation closure, no column drop, "
            "termination at exactly 4 — the assertion that a growth-based safeguard is absent.",
            lambda: _a13(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A14",
            "REC-05 with the tail under `depth_max = 0`: `RECYCLE_STAGNATION` at 20, closures "
            "`[10, 15, 20]`, two restarts; the merge edge then runs the region Newton from the "
            "best iterate and returns CONVERGED with `‖R‖∞ ≤ τ_R`. Which fixed point it lands on "
            "is recorded, not asserted (spec §12).",
            lambda: _a14(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A15",
            "RCY-DIV under `depth_max = 0`: `RECYCLE_STAGNATION` at 16, closures `[6, 11, 16]`, "
            "trajectory `0.4` at `k = 0` and the closed form `0.25 · 1.5^k / 3` for `k = 1..16` "
            "to `1e-12` relative; the merge converges in exactly 1 Newton iteration to `t*`; "
            "under Anderson exactly 4.",
            lambda: _a15(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A16",
            "RCY-STALL: `RECYCLE_STAGNATION` at 15, closures `[5, 10, 15]`, two restarts, 27 "
            "condition drops, zero Anderson steps; the merge ends "
            "`LINEAR_SOLVE_FAILED(exactly_singular)`; no certificate; no `INFEASIBLE` anywhere "
            "in the failure bundle.",
            lambda: _a16(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A17",
            "RCY-COEF: the `acceleration` event at `k = 1` has `depth_used = 0`, one coefficient "
            "drop, and the refused coefficient recorded on the drop equal to `1 000 001` to "
            "`1e-6` relative; 12 coefficient drops in all; closures `[5, 10, 15]`; the merge "
            "converges in exactly 1 iteration to `−1e6` to `1e-9` relative.",
            lambda: _a17(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A18",
            "NEST-1: T01's own tear analysis of the flowsheet reports `multi_edge_feedback_set`; "
            "the tear set T02's rule builds from T01's candidates is `[s4, s5]` with the "
            "registered rounds, candidates and boundary distances; Anderson converges in exactly "
            "2 iterations to `(5, 4)` within `1e-7`, product `s3 = 1` within `1e-7`; with "
            "`recycle.tear_streams = [s1, s5]` the plan tears `(s1.x, s5.x)` by rows "
            "`(A:s1, C:s5)` and reaches `(6, 4)` with the same product within `1e-7`. Both "
            "recycles are measured through the plan: `G(t)` is derived from each `converge` "
            "step's own `SolvePlan` partition (inner rows solved exactly for the inner variables "
            "from T01's traced affine coefficients, tear rows evaluated there), not written by "
            "hand.",
            lambda: _a18(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A19",
            "SCL-1 (REC-03 linear under scales `(1, 3, 9)`): trajectory `k = 0..3` equals the "
            "twin's to `1e-9` relative; iterate 2's residual differs from REC-03's unscaled one "
            "by more than `1e-2`; exactly 4 iterations; accepted `kappa_2 ≤ 1e7` and "
            "`gamma_inf ≤ 1e3` throughout.",
            lambda: _a19(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A20",
            "RCY-TRUNC (REC-01 linear, `depth_max = 2`): iterations in `[10, 20]` and more than "
            "4; trajectory `k = 0..5` to `1e-8` relative; `depth_used ≤ 2` on every event; the "
            "oscillation flag sets at 7 and `beta_substitution` stays 1 on every Anderson step.",
            lambda: _a20(ref, recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A21",
            "SYN-001 nominal under `eo` from `x(t⁰)`: CONVERGED in exactly 2 attempts; attempt 1 "
            "`(U-HEAT TWO_PHASE, U-FLASH TWO_PHASE)` closes `PHASE_UPDATE_REQUIRED("
            "phase_disappeared(U-HEAT, vapor, v))` at iteration ≤ 2 with `v` one of `S3.vap.A/B/C, "
            "S3.V`; attempt 2 `(U-HEAT LIQUID, U-FLASH TWO_PHASE)` converges in ≤ 5; the final "
            "state agrees with the tear solve (itself gated against P01) per kind within "
            "`3.1e-7 mol/s, 1e-5 K, 0.1 Pa, 1e-2 W`, and with P01's recycle and duties directly; "
            "`S3.V` and `S3.vap.*` exactly 0.0 (pinned).",
            lambda: _a21(),
        )
    )
    checks.append(
        measured(
            "T02.A22",
            "SYN-001 high-recycle and 310 K under `eo` from `x(t⁰)`: one attempt, ≤ 10 and ≤ 5 "
            "iterations; once-through and 420 K: iteration 0; every state within A21's "
            "tolerances of the tear solution; the high-recycle heater LIQUID from the start "
            "with `S3.V` exactly 0.0.",
            lambda: _a22(),
        )
    )
    checks.append(
        measured(
            "T02.A23",
            "Same function: the `eo` region started from the tear solve's reconstructed `x(t*)` "
            "converges at iteration 0 with `jacobian_calls = 0` and `factorizations = 0` at all "
            "five variants.",
            lambda: _a23(),
        )
    )
    checks.append(
        measured(
            "T02.A24",
            "EO-TRIV: once-through under `eo` with `S3`'s split forced all-liquid: one "
            "`initializer_candidate` event with message `projected(S3, all_liquid, TWO_PHASE)`, "
            "then one `initializer_accepted`; one attempt; iteration 0; the heater outlet vapour "
            "fraction equals P01's `0.10136872342672776` to `1e-12` relative.",
            lambda: _a24(),
        )
    )
    checks.append(
        measured(
            "T02.A25",
            "A02 plan: for `SYN-001-A02-360/-365/-355` the `ExecutionPlan` equals "
            "`ref.syn001.plans['SYN-001-A02-*']` — the `solve_eo` step with `tear_variable_ids = "
            "[]`, a 42 × 42 system whose rows are the four units' 44 rows minus the two "
            "certificates and whose columns are the 47 free columns minus `S1`'s five, "
            "`eliminated_rows` the two certificates, `signature_units (U-HEAT, U-FLASH)`, the "
            "registered specification, adjusted, target and removed rows — built without any "
            "evaluation.",
            lambda: _a25(ref),
        )
    )
    checks.append(
        measured(
            "T02.A26",
            "A02 DOF, against A26 as amended by the T02 review (2026-09-24). (a) `HEAT-T` "
            "retained → `STRUCTURAL_OVER_SPECIFICATION` at validation (STR-03 `FAIL`, status "
            "`INVALID`) naming the over-specified unit among `U-HEAT`/`U-FLASH` — which row the "
            "canonical matching leaves unmatched is T01's; the spec measured `U-FLASH` — with both "
            "`SPEC-heater-outlet-T` and the promotion row's `SPEC-flash-duty` among the candidate "
            "specifications, and no plan built. (b) `HEAT-T` removed and no promotion row → "
            "`STRUCTURAL_UNDER_SPECIFICATION` (STR-02 `FAIL`) with `S3.T` implicated; the status "
            "is `DRAFT` (register R-022's extension), recorded. (c) a synthetic region closed but "
            "non-square after certificates → `UNSUPPORTED_RANK_STRUCTURE` at plan construction. "
            "Zero compiler and provider calls in all three (validation runs T01's analysis by "
            "design, so the analysis is not spied here).",
            lambda: _a26(),
        )
    )
    checks.append(
        measured(
            "T02.A27",
            "CAP-1 (the A02-360 heater with `residuals` declared `unavailable`): "
            "`CAPABILITY_UNAVAILABLE` naming `U-HEAT`, `unavailable`, the four region units and "
            "`SPEC-flash-duty`; no `plan_built` event; zero residual, Jacobian and property "
            "calls; no attempt; the failure bundle's only suggested action is "
            "`provide_derivatives`, `U-HEAT` first among its implicated sources, no "
            "`report_defect`, and it validates; no `converge` step exists because no plan exists.",
            lambda: _a27(),
        )
    )
    a02_solves = _a02_solves()
    checks.append(
        measured(
            "T02.A28",
            "`SYN-001-A02-360`: CONVERGED in 1 attempt and ≤ 6 iterations; `S3.T` within "
            "`1e-5 K` of 360; `U-HEAT.Q` within `1e-2 W` of `Q_total = 56 338.069 446 743 527`; "
            "`U-FLASH.Q` within `1e-2 W` of 0; `S3.vap`, `S3.liq` within `3.1e-7 mol/s` of the "
            "360 K split; `S6.n` within `3.1e-7` of `t*`.",
            lambda: _a28_a29(ref, a02_solves, ("SYN-001-A02-360",)),
        )
    )
    checks.append(
        measured(
            "T02.A29",
            "`SYN-001-A02-365` and `-355`: as A28 with the 365 K and 355 K rows of the sweep. The "
            "spec's *measured* 4 iterations for -355 is 3 at this commit; the registered bound "
            "is ≤ 6 and the count is recorded.",
            lambda: _a28_a29(ref, a02_solves, ("SYN-001-A02-365", "SYN-001-A02-355")),
        )
    )
    checks.append(
        measured(
            "T02.A30",
            "`SYN-001-A02-355-liquid-guess`: attempt 1 (heater LIQUID) converges and closes "
            "`PHASE_UPDATE_REQUIRED(inadmissible(S3, all_liquid, Σ))` with `S3.T` within `1e-5 K` "
            "of the liquid-branch root `389.438 243 827 208 422 K` and `Σ` within `1e-9` relative "
            "of `2.495 993 838 622 898 6`; attempt 2 opens VAPOR; the solve ends "
            "`ACTIVE_SET_CYCLING` with no certificate and a checkpoint labelled `partial`.",
            lambda: _a30(ref, a02_solves),
        )
    )
    checks.append(
        measured(
            "T02.A31",
            "`SYN-001-A02-360-liquid-guess`: attempt 1 (LIQUID) ends `STAGNATION`, converted to "
            "`PHASE_UPDATE_REQUIRED(kernel_disagrees(U-HEAT, VAPOR))` with its best iterate's "
            "`S3.T ≥ 430 K`; attempt 2 (VAPOR) converted to LIQUID with `S3.T ≤ 290 K`; the solve "
            "ends `ACTIVE_SET_CYCLING`, no certificate, no `INFEASIBLE`.",
            lambda: _a31(a02_solves),
        )
    )
    checks.append(
        measured(
            "T02.A32",
            "Recovery edges: every `restart` of every recycle run in this manifest carries "
            "`reason = stagnation` and `count ≤ 2`; `region_on_merge` has the loop's "
            "`model_version` and `constants_sha256` and its rows (solved and eliminated) are "
            "exactly the loop units' rows, with no specification row; one merge at most per loop "
            "(one recycle closure then one region closure); MERGE-U, on the manufactured stall "
            "and on SYN-001 with the heater non-capable, ends with the recycle's own outcome, "
            '`merge_into_eo: unsupported(U-HEAT, "derivatives: unavailable")` on the closing '
            "message and in the failure bundle, and no residual call after the closure.",
            lambda: _a32(recycle_runs),
        )
    )
    checks.append(
        measured(
            "T02.A33",
            "Trace well-formedness with ADR 0009's kinds, on seven plan runs (nominal under "
            "auto/anderson/eo, A02-360, A02-355-liquid-guess, the SYN-001 merge, SYN-001 "
            "MERGE-U): dense increasing `sequence`; one `plan_built` with `step_count`; "
            "`unit_evaluated` and `region_opened`/`region_closed` bracket every step in plan "
            "order with every inner event stamped with its `step_index`; every `acceleration` "
            "event has `depth_used ≤ min(5, n)`, both drop counts, `beta_substitution ∈ {1, 0.5}` "
            "and `kappa_2`/`gamma_inf` non-null iff `depth_used ≥ 1`; every event validates "
            "against `solve-event.schema.json` and serializes with no non-finite number; the "
            "one `solve_closed` outcome equals the result's. Also the acceleration events of "
            "REC-01..05 at both `γ`. Property metering on `SYN-001-A02-360`: every call the "
            "SYN-001 provider class receives (counted at the class) appears on the trace — the "
            "`solve_closed` `property_calls` equals the independent count — and the region "
            "Newton's own calls are on the trace (review finding closed by 76b245d, a24ca16).",
            lambda: _a33(),
        )
    )
    checks.append(_a34(identities))
    checks.append(
        measured(
            "T02.A35",
            "K03 regression: the gate's pytest run passed with no failure, and K03's own test "
            "files `tests/test_k03_*.py`, run again here, pass (the tear path, `SolvePlan`, the "
            "Newton core and the phase contract unchanged); BND-02 (`R = x + 1`, `x ≥ 0`, "
            "`x⁰ = 0`) run through the tear path's attempt controller ends `BOUND_BLOCKED` at "
            "iteration 0 in one attempt — a bound block on a *tear* variable is not converted to "
            "a phase event.",
            lambda: _a35(gate),
        )
    )

    covered = [entry["id"] for entry in checks]
    registered = [f"T02.{identifier}" for identifier in ASSERTIONS]
    checks.append(
        check(
            "T02.A36",
            "This manifest carries one `checks[]` entry per assertion of spec §10, "
            "`T02.A00`…`T02.A36`, including every `unsupported`; `limitations` restates spec "
            "§12; `review` is unset (`pending` in both fields — no agent may set it); "
            "`commands` is the gate actually run "
            "here plus the named CI run on both architectures. Without `--ci-run` the "
            "two-architecture half of `commands` is absent and this check is `unsupported`.",
            (
                verdict(covered + ["T02.A36"] == registered)
                if ci_run
                else ("unsupported" if covered + ["T02.A36"] == registered else "fail")
            ),
            {
                "entries": len(covered) + 1,
                "ids_in_order": covered + ["T02.A36"] == registered,
                "ci_run": ci_run,
            },
            {"entries": len(registered), "ids_in_order": True, "ci_run": "a workflow run URL"},
        )
    )

    failed = [entry["id"] for entry in checks if entry["result"] == "fail"]
    commands = [
        {
            "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
            "cwd": ".",
            "exit_code": 0 if gate["passed"] else 1,
            "stdout_sha256": hashlib.sha256(gate_stdout.read_bytes()).hexdigest(),
        },
        {
            "cmd": "PATH=.venv/bin:$PATH .venv/bin/python "
            "docs/derivations/scripts/t02_reference.py --check",
            "cwd": ".",
            "exit_code": int(checks[0]["value"].get("check_exit_code", 1))
            if isinstance(checks[0]["value"], dict)
            else 1,
        },
        {
            "cmd": "PYTHONPATH=. .venv/bin/python scripts/t02_evidence_manifest.py "
            f"GATE_STDOUT --commit {commit}"
            + (f" --identities {identities.name}" if identities else "")
            + (f" --ci-run {ci_run}" if ci_run else ""),
            "cwd": ".",
            "exit_code": 1 if failed else 0,
        },
    ]
    if ci_run:
        # The `commands` schema has no field for a reference (K05's precedent): the run URL goes
        # in the command string, where a reader looking for how the pair was run will find it.
        commands.append(
            {
                "cmd": "GitHub Actions workflow `ci`, jobs `check` (ubuntu-latest, "
                f"ubuntu-24.04-arm) and `identity`: {ci_run}",
                "cwd": ".",
                "exit_code": 0,
            }
        )

    return {
        "work_package": "T02",
        "commit": commit,
        # The frozen schema takes D/A requirement ids only. V13 and V15 are verification items
        # of plan §5 and are carried in `docs/requirements.yaml`, which points back here.
        "requirements": ["D01", "D06", "A02"],
        "status": _status(checks),
        "inputs": {
            "case_id": "The five registered SYN-001 variants under auto, anderson and eo; the "
            "A02 family SYN-001-A02-360/-365/-355 and the two liquid-guess cases; CAP-1 and "
            "MERGE-U (test doubles); the manufactured recycles REC-01..05 at both gamma, RCY-DIV, "
            "RCY-STALL, RCY-COEF, SCL-1, RCY-TRUNC and NEST-1; judged against "
            f"benchmarks/t02/reference_values.yaml ({file_sha256(REFERENCE)}), "
            f"benchmarks/syn001/reference_values.yaml ({file_sha256(P01)}) and "
            f"docs/derivations/T02-recycle-spec.md ({file_sha256(SPEC)})",
            "case_hash": _case_hash(),
            "environment_lock_hash": file_sha256(ROOT / "requirements.lock"),
        },
        "commands": commands,
        "checks": checks,
        "artifacts": [],
        "limitations": _limitations(ci_run is not None, identities is not None),
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def _status(checks: Sequence[Mapping[str, Any]]) -> str:
    """`tested` when nothing failed. An `unsupported` check carries its reason in its own
    description (the CI halves without their artifacts), which is T01's and K05's rule; a
    `fail` anywhere leaves the package `implemented`, never `tested`."""
    return "implemented" if any(entry["result"] == "fail" for entry in checks) else "tested"


def _case_hash() -> str:
    """One digest over every registered revision this package ran, in name order."""
    digest = hashlib.sha256()
    for name in sorted((*VARIANTS, *A02_CASES)):
        digest.update((CASES / f"{name}.yaml").read_bytes())
    return digest.hexdigest()


def _gate(gate_stdout: Path) -> dict[str, Any]:
    text = gate_stdout.read_text(encoding="utf-8")
    counts = _pytest_counts(text)
    return {
        "passed": "=== check.sh: PASSED ===" in text,
        "pytest_passed": counts.get("passed", 0),
        "pytest_failed_or_errors": bool(
            counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
        ),
    }


def _pytest_counts(text: str) -> dict[str, int]:
    """The last pytest summary line (`3 failed, 1511 passed in 27.1s`), as counts by word."""
    lines = re.findall(r"^((?:\d+ [a-z]+(?:, )?)+) in [\d.]+s", text, flags=re.MULTILINE)
    if not lines:
        return {}
    return {word: int(count) for count, word in re.findall(r"(\d+) ([a-z]+)", lines[-1])}


# ----------------------------------------------------------------------------------- A00


def _a00() -> tuple[bool, Any, Any]:
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    counted = re.findall(r"^(\d+) checks passed", completed.stdout, flags=re.MULTILINE)
    digest = file_sha256(REFERENCE)
    header = SPEC.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    with tempfile.TemporaryDirectory() as scratch:
        first, second = Path(scratch) / "a.yaml", Path(scratch) / "b.yaml"
        for destination in (first, second):
            subprocess.run(  # noqa: S603
                [sys.executable, str(GENERATOR), "--emit", str(destination)],
                capture_output=True,
                cwd=ROOT,
                check=True,
            )
        twice = first.read_bytes() == second.read_bytes()
        committed = first.read_bytes() == REFERENCE.read_bytes()
    forbidden: list[str] = []
    for script in ("t02_reference.py", "syn001_reference.py", "k03_reference.py"):
        tree = ast.parse((GENERATOR.parent / script).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            forbidden += [
                f"{script}: {name}"
                for name in names
                if name.split(".")[0] in {"openflowsheet", "benchmarks"}
            ]
    value = {
        "check_exit_code": completed.returncode,
        "checks_passed": int(counted[-1]) if counted else None,
        "reference_sha256": digest,
        "digest_in_spec_header": digest in header,
        "emit_twice_identical": twice,
        "emit_equals_committed": committed,
        "forbidden_imports": forbidden,
    }
    expected = {
        "check_exit_code": 0,
        "checks_passed": 114,
        "digest_in_spec_header": True,
        "emit_twice_identical": True,
        "emit_equals_committed": True,
        "forbidden_imports": [],
    }
    return (
        all(value[key] == expected[key] for key in expected),
        value,
        expected,
    )


# ------------------------------------------------------------------------------ A01–A03


def _validators() -> dict[str, Any]:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (ROOT / "schemas").glob("*.schema.json")
    ]
    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document)) for document in documents
    )
    by_id = {document["$id"]: document for document in documents}
    base = "https://github.com/frankp/process-runtime/schemas/"
    return {
        name: Draft202012Validator(by_id[base + name], registry=registry)
        for name in ("execution-plan.schema.json", "solve-plan.schema.json")
    }


@contextlib.contextmanager
def _spied(*, analysis: bool = True) -> Iterator[dict[str, int]]:
    """Count every call to the compiler and the provider — and, with `analysis`, to the
    structural analysis — while inside; each raises, so a structural step that evaluated
    anything is a failed measurement, not a result. Validation runs the analysis by design
    (T01), so the A26 measurements spy on evaluation only."""
    import openflowsheet.compile.casadi_backend as backend
    import openflowsheet.graph.analysis as structural
    from openflowsheet.thermo.syn001 import Syn001Provider

    calls: dict[str, int] = {}
    targets: tuple[tuple[Any, str], ...] = (
        (backend, "compile_problem"),
        (Syn001Provider, "flash"),
        (Syn001Provider, "evaluate_phase"),
    )
    if analysis:
        targets += ((structural, "analyse"), (structural, "analyse_declaration"))
    saved = [(owner, name, getattr(owner, name)) for owner, name in targets]

    def spy(label: str) -> Callable[..., Any]:
        def refuse(*arguments: object, **keywords: object) -> Any:
            calls[label] = calls.get(label, 0) + 1
            raise AssertionError(f"a structural step called {label}")

        return refuse

    for owner, name in targets:
        setattr(owner, name, spy(f"{getattr(owner, '__name__', owner)}.{name}"))
    try:
        yield calls
    finally:
        for owner, name, original in saved:
            setattr(owner, name, original)


def _a01(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    validators = _validators()
    registered = plan_fixtures.strip(ref["syn001"]["plans"]["SYN-001-nominal (tear)"])
    per_variant: dict[str, Any] = {}
    for case_id in VARIANTS:
        plan = plan_fixtures.plan_for(case_id)
        schema_errors = len(
            list(validators["execution-plan.schema.json"].iter_errors(plan.as_document()))
        ) + sum(
            len(
                list(
                    validators["solve-plan.schema.json"].iter_errors(step.solve_plan.as_document())
                )
            )
            for step in plan.steps
            if step.solve_plan is not None
        )
        per_variant[case_id] = {
            "equals_registered": plan_fixtures.summary(plan) == registered,
            "schema_errors": schema_errors,
        }

    # The spy: build the nominal plan's inputs, then the plan itself with every analysis,
    # compiler and provider entry point refusing.
    from openflowsheet.application.binding import structural_inputs
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.graph.analysis import analyse
    from openflowsheet.graph.trace import trace_declaration
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.orchestrator.execution import build_execution_plan, declaration_identity
    from openflowsheet.orchestrator.trace import SolvePolicy
    from openflowsheet.thermo.syn001 import Syn001Provider

    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    spec, graph, row_units = structural_inputs(flowsheet)
    model_version, constants = declaration_identity(spec)
    declaration = trace_declaration(
        spec, row_units=row_units, model_version=model_version, constants_sha256=constants
    )
    report = analyse(
        spec, graph, row_units=row_units, model_version=model_version, constants_sha256=constants
    )
    with _spied() as calls:
        spied = build_execution_plan(
            spec=spec,
            declaration=declaration,
            graph=graph,
            report=report,
            manifests={unit.unit_id: unit.manifest() for unit in flowsheet.units()},
            policy=SolvePolicy(policy_id="T02", residual_tolerances={}, scales={}),
        )
    spy = {"calls_inside_builder": dict(calls), "kinds": [step.kind for step in spied.steps]}

    try:
        nest = plan_fixtures.nest_plan()
        nest_value: dict[str, Any] = {
            "steps": [
                {
                    "kind": step.kind,
                    "units": sorted(step.units),
                    "tear_streams": list(step.tear_streams),
                    "tear_variable_ids": list(step.solve_plan.tear_variable_ids)
                    if step.solve_plan is not None
                    else [],
                    "tear_row_ids": list(step.solve_plan.tear_row_ids)
                    if step.solve_plan is not None
                    else [],
                }
                for step in nest.steps
            ],
            "schema_errors": len(
                list(validators["execution-plan.schema.json"].iter_errors(nest.as_document()))
            ),
        }
    except Exception as error:  # noqa: BLE001 - recorded: the builder refused the registered case
        nest_value = {"error": f"{type(error).__name__}: {error}"}
    nest_expected = {
        "steps": [
            {
                "kind": "evaluate",
                "units": ["FEED"],
                "tear_streams": [],
                "tear_variable_ids": [],
                "tear_row_ids": [],
            },
            {
                "kind": "converge",
                "units": ["A", "B", "C"],
                "tear_streams": list(ref["cases_auxiliary"]["NEST-1"]["tear"]["tear_streams"]),
                "tear_variable_ids": ["s4.x", "s5.x"],
                "tear_row_ids": ["B:s4", "C:s5"],
            },
        ],
        "schema_errors": 0,
    }

    value = {"syn001": per_variant, "spy": spy, "NEST-1": nest_value}
    expected = {
        "syn001": dict.fromkeys(VARIANTS, {"equals_registered": True, "schema_errors": 0}),
        "spy": {"calls_inside_builder": {}, "kinds": ["evaluate", "converge"]},
        "NEST-1": nest_expected,
    }
    return value == expected, value, expected


def _a02(identities: Path | None) -> dict[str, Any]:
    description = (
        "R0: the plan's R0 projection (`execution_plan_r0`) is byte-identical across the five "
        "SYN-001 variants once `model_version` and `constants_sha256` are removed at every "
        "depth; `scripts/k05_structural_identity.py` carries the T02 plans in the document CI "
        "compares, and its nominal plan equals the one built here; and — from the two CI "
        "artifacts — the x86-64 and aarch64 `identity.json` are equal key for key, `t02.plans` "
        "included. Without `--identities` the cross-platform half is not measured and the check "
        "is `unsupported`."
    )
    try:
        local, value = _a02_local()
    except Exception as error:  # noqa: BLE001
        return check(
            "T02.A02", description, "fail", {"error": f"{type(error).__name__}: {error}"}, ""
        )
    expected: dict[str, Any] = {
        "variants_identical_up_to_identity": True,
        "k05_carries_t02_plans": True,
        "k05_nominal_plan_equals_built": True,
        "ci": {"platforms": 2, "identity_differences": [], "t02_plans_equal": True},
    }
    if identities is None:
        value["ci"] = "not measured: no --identities directory given"
        return check("T02.A02", description, "unsupported" if local else "fail", value, expected)
    ci = _ci_comparison(identities)
    value["ci"] = {
        "platforms": len(ci["platforms"]),
        "identity_differences": ci["identity_differences"],
        "t02_plans_equal": ci["t02_plans_equal"],
    }
    return check(
        "T02.A02",
        description,
        verdict(local and value["ci"] == expected["ci"]),
        value,
        expected,
    )


def _without_identity(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_identity(item)
            for key, item in value.items()
            if key not in {"model_version", "constants_sha256"}
        }
    if isinstance(value, list):
        return [_without_identity(item) for item in value]
    return value


def _a02_local() -> tuple[bool, dict[str, Any]]:
    from k05_structural_identity import identity as k05_identity

    from openflowsheet.orchestrator.trace import RecyclePolicy as Recycle
    from openflowsheet.orchestrator.trace import SolvePolicy
    from openflowsheet.run.identity import execution_plan_r0

    projections = {
        case_id: json.dumps(
            _without_identity(execution_plan_r0(plan_fixtures.plan_for(case_id).as_document())),
            sort_keys=True,
            allow_nan=False,
        ).encode()
        for case_id in VARIANTS
    }
    identical = len(set(projections.values())) == 1

    document = k05_identity()
    plans = document.get("t02", {}).get("plans", {})
    carries = {"SYN-001-nominal auto", "SYN-001-A02-360"} <= set(plans)

    # The nominal plan under the identity script's own policy id, built here by this script.
    policy = SolvePolicy(
        policy_id="T02-auto", residual_tolerances={}, scales={}, recycle=Recycle(method="auto")
    )
    built = execution_plan_r0(_syn001_plan("SYN-001-nominal", policy).as_document())
    equal = plans.get("SYN-001-nominal auto") == json.loads(json.dumps(built))
    value = {
        "variants_identical_up_to_identity": identical,
        "variant_r0_sha256": hashlib.sha256(next(iter(projections.values()))).hexdigest(),
        "k05_carries_t02_plans": carries,
        "k05_t02_plan_keys": sorted(plans),
        "k05_nominal_plan_equals_built": equal,
    }
    return identical and carries and equal, value


def _syn001_plan(case_id: str, policy: Any) -> Any:
    """`test_t02_plan.plan_for` under a given policy: the variant's flowsheet, traced and
    analysed once, then planned."""
    from openflowsheet.orchestrator.execution import build_execution_plan, declaration_identity

    entry = plan_fixtures.variants()[case_id]
    flowsheet = plan_fixtures.Syn001Flowsheet(
        provider=plan_fixtures.Syn001Provider(),
        context=plan_fixtures.EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
        split_fraction=float(entry["r"]),
        flash_temperature=float(entry["T_flash_K"]),
        heater_temperature=float(entry["T_heater_K"]),
        pressure=float(entry["P_Pa"]),
    )
    spec, graph, row_units = plan_fixtures.structural_inputs(flowsheet)
    model_version, constants = declaration_identity(spec)
    identity = {
        "row_units": row_units,
        "model_version": model_version,
        "constants_sha256": constants,
    }
    return build_execution_plan(
        spec=spec,
        declaration=plan_fixtures.trace_declaration(spec, **identity),
        graph=graph,
        report=plan_fixtures.analyse(spec, graph, **identity),
        manifests={unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=policy,
    )


def _a03() -> tuple[bool, Any, Any]:
    from openflowsheet.orchestrator.execution import eo_capability

    nominal = plan_fixtures.plan_for("SYN-001-nominal").steps[1]
    manifests = {
        unit.unit_id: dict(unit.manifest())
        for unit in plan_fixtures.Syn001Flowsheet(
            provider=plan_fixtures.Syn001Provider(),
            context=plan_fixtures.EvaluationContext(
                model_version="t02", constants_sha256="0" * 64, phase_signature=None
            ),
        ).units()
    }
    doubled_manifests = executor_fixtures.heater_without_derivatives(manifests)
    doubled = plan_fixtures.plan_for("SYN-001-nominal", manifests=doubled_manifests).steps[1]
    scales_equal = {}
    for case_id in VARIANTS:
        solve_plan = plan_fixtures.plan_for(case_id).steps[1].solve_plan
        scales_equal[case_id] = solve_plan is not None and all(
            solve_plan.column_scales[variable] == solve_plan.row_scales[row]
            for variable, row in zip(
                solve_plan.tear_variable_ids, solve_plan.tear_row_ids, strict=True
            )
        )
    nest_solve_plan = plan_fixtures.nest_plan().steps[1].solve_plan
    scales_equal["NEST-1"] = nest_solve_plan is not None and all(
        nest_solve_plan.column_scales[variable] == nest_solve_plan.row_scales[row]
        for variable, row in zip(
            nest_solve_plan.tear_variable_ids, nest_solve_plan.tear_row_ids, strict=True
        )
    )
    try:
        _, nest_graph, _, _ = plan_fixtures.nest_structure()
        nest_method: Any = {
            "all capable": plan_fixtures.nest_plan().steps[1].method,
            "B declares no residual derivative": plan_fixtures.nest_plan(
                manifests={**dict.fromkeys(nest_graph.units, plan_fixtures.CAPABLE), "B": {}}
            )
            .steps[1]
            .method,
        }
    except Exception as error:  # noqa: BLE001 - recorded: the builder refused the registered case
        nest_method = {"error": f"{type(error).__name__}: {error}"}
    value = {
        "SYN-001 auto": nominal.method,
        "SYN-001 merge region present": nominal.region_on_merge is not None,
        "heater unavailable: capability": list(eo_capability(doubled_manifests["U-HEAT"])),
        "heater unavailable: auto": doubled.method,
        "heater unavailable: merge_unsupported": list(doubled.merge_unsupported or ()),
        "NEST-1 auto": nest_method,
        "tear scales equal": scales_equal,
    }
    expected = {
        "SYN-001 auto": "newton_tear",
        "SYN-001 merge region present": True,
        "heater unavailable: capability": [False, "unavailable"],
        "heater unavailable: auto": "anderson",
        "heater unavailable: merge_unsupported": ["U-HEAT", "unavailable"],
        "NEST-1 auto": {
            "all capable": "newton_tear",
            "B declares no residual derivative": "anderson",
        },
        "tear scales equal": dict.fromkeys((*VARIANTS, "NEST-1"), True),
    }
    return value == expected, value, expected


# ------------------------------------------------------------------------------ A04–A06


def _syn001_anderson() -> dict[str, Any]:
    """The SYN-001 × Anderson runs, once each: from `t⁰` at all five variants, OFF-A at the three
    360 K ones, OFF-B at nominal."""
    from openflowsheet.orchestrator.tear import solve_tear

    runs: dict[str, Any] = {}
    for case_id in VARIANTS:
        flowsheet, t_star = recycle_fixtures._syn001(case_id)
        result, trace = solve_tear(flowsheet, policy=recycle_fixtures._anderson_policy())
        runs[f"{case_id} t0"] = (result, trace, t_star)
    for case_id in ("SYN-001-nominal", "SYN-001-high-recycle", "SYN-001-once-through"):
        flowsheet, t_star = recycle_fixtures._syn001(case_id)
        result, trace = solve_tear(
            flowsheet, policy=recycle_fixtures._anderson_policy(), initial_recycle=(0.1, 0.8, 1.2)
        )
        runs[f"{case_id} OFF-A"] = (result, trace, t_star)
    flowsheet, t_star = recycle_fixtures._syn001("SYN-001-nominal")
    result, trace = solve_tear(
        flowsheet, policy=recycle_fixtures._anderson_policy(), initial_recycle=(0.05, 0.1, 4.0)
    )
    runs["SYN-001-nominal OFF-B"] = (result, trace, t_star)
    return runs


def _a04(runs: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    iterations = {
        "SYN-001-nominal": 2,
        "SYN-001-high-recycle": 2,
        "SYN-001-all-liquid-310K": 2,
        "SYN-001-once-through": 0,
        "SYN-001-all-vapor-420K": 0,
    }
    value: dict[str, Any] = {}
    expected: dict[str, Any] = {}
    ok = True
    for case_id, count in iterations.items():
        result, trace, t_star = runs[f"{case_id} t0"]
        accelerations = trace.of_kind("acceleration")
        alphas = [event.alpha for event in trace.of_kind("step_accepted")]
        error = float(np.max(np.abs(result.x - t_star)))
        row = {
            "outcome": result.outcome,
            "iterations": result.iterations,
            "attempts": result.attempts,
            "max_abs_t_minus_t_star": error,
            "restarts": len(trace.of_kind("restart")),
            "column_drops": sum(
                (event.columns_dropped_condition or 0) + (event.columns_dropped_coefficient or 0)
                for event in accelerations
            ),
            "rejected_trials": len(trace.of_kind("trial")),
            "accepted_alphas": alphas,
            "depth_used": [event.depth_used for event in accelerations],
        }
        value[case_id] = row
        expected[case_id] = {
            "outcome": "CONVERGED",
            "iterations": count,
            "attempts": 1,
            "max_abs_t_minus_t_star": f"at most {TAU}",
            "restarts": 0,
            "column_drops": 0,
            "rejected_trials": 0,
            "accepted_alphas": "every one 1.0 (no landing)",
            "depth_used": "second step 1" if count == 2 else "no step",
        }
        ok = ok and (
            row["outcome"] == "CONVERGED"
            and row["iterations"] == count
            and row["attempts"] == 1
            and error <= TAU
            and row["restarts"] == row["column_drops"] == row["rejected_trials"] == 0
            and all(alpha == 1.0 for alpha in alphas)
            and (row["depth_used"][1:2] == [1] if count == 2 else not row["depth_used"])
        )
    return ok, value, expected


def _a05(runs: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    value: dict[str, Any] = {}
    ok = True
    for case_id in ("SYN-001-nominal", "SYN-001-high-recycle", "SYN-001-once-through"):
        result, trace, t_star = runs[f"{case_id} OFF-A"]
        invalid = [
            event for event in trace.of_kind("trial") if event.rejection_reason == "invalid_trial"
        ]
        error = float(np.max(np.abs(result.x - t_star)))
        value[case_id] = {
            "outcome": result.outcome,
            "iterations": result.iterations,
            "attempts": result.attempts,
            "invalid_trials": len(invalid),
            "max_abs_t_minus_t_star": error,
        }
        ok = ok and (
            result.outcome == "CONVERGED"
            and result.iterations <= 15
            and result.attempts == 1
            and not invalid
            and error <= TAU
        )
    expected = {
        "outcome": "CONVERGED",
        "iterations": "at most 15 (spec measured 9, 9, 1)",
        "attempts": 1,
        "invalid_trials": 0,
        "max_abs_t_minus_t_star": f"at most {TAU}",
    }
    return ok, value, expected


def _a06(runs: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    result, trace, t_star = runs["SYN-001-nominal OFF-B"]
    invalid = [
        event for event in trace.of_kind("trial") if event.rejection_reason == "invalid_trial"
    ]
    value = {
        "outcome": result.outcome,
        "attempts": result.attempts,
        "flash_signatures": [signature[0][1] for signature in result.signatures],
        "invalid_trials": len(invalid),
        "every_invalid_names_U-MIX": all("U-MIX" in event.message for event in invalid),
        "iterations": result.iterations,
        "max_abs_t_minus_t_star": float(np.max(np.abs(result.x - t_star))),
        "attempts_opened_closed": [
            len(trace.of_kind("attempt_opened")),
            len(trace.of_kind("attempt_closed")),
        ],
    }
    ok = (
        value["outcome"] == "CONVERGED"
        and value["attempts"] == 2
        and value["flash_signatures"] == ["LIQUID", "TWO_PHASE"]
        and value["invalid_trials"] >= 1
        and value["every_invalid_names_U-MIX"]
        and result.iterations <= 40
        and value["max_abs_t_minus_t_star"] <= TAU
        and value["attempts_opened_closed"] == [2, 2]
    )
    expected = {
        "outcome": "CONVERGED",
        "attempts": 2,
        "flash_signatures": ["LIQUID", "TWO_PHASE"],
        "invalid_trials": "at least 1",
        "every_invalid_names_U-MIX": True,
        "iterations": "at most 40",
        "max_abs_t_minus_t_star": f"at most {TAU}",
        "attempts_opened_closed": [2, 2],
    }
    return ok, value, expected


# ------------------------------------------------------------------------------ A07–A20


def _rec(
    ref: Mapping[str, Any],
    runs: dict[str, RecycleResult],
    name: str,
    gamma: float,
    **policy: Any,
) -> RecycleResult:
    label = f"{name} gamma={gamma}" + "".join(f" {key}={item}" for key, item in policy.items())
    if label not in runs:
        runs[label] = recycle_fixtures.run_rec(ref, name, gamma, **policy)[0]
    return runs[label]


def _a07(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    value: dict[str, Any] = {}
    ok = True
    for name in REC:
        result = _rec(ref, runs, name, 0.0)
        case = ref["cases_rec"][name]
        registered = case["variants"]["gamma=0"]["policy_simulation_anderson"]
        worst = worst_relative(result.residual_inf_scaled, registered["residual_inf_scaled"], 3)
        error = float(np.max(np.abs(result.x - recycle_fixtures.floats(case["t_star"]))))
        value[name] = {
            **recycle_summary(result),
            "krylov_grade_registered": case["variants"]["gamma=0"]["krylov_grade"],
            "twin_iterations": registered["iterations"],
            "trajectory_worst_relative_k0_3": worst,
            "max_abs_t_minus_t_star": error,
        }
        ok = ok and (
            result.outcome == "CONVERGED"
            and result.iterations == 4 == registered["iterations"]
            and case["variants"]["gamma=0"]["krylov_grade"] == 3
            and worst <= 1e-9
            and not result.restarts
            and result.columns_dropped_condition == result.columns_dropped_coefficient == 0
            and result.bound_landings == result.invalid_trials == 0
            and error <= 1e-5
        )
    expected = {
        "outcome": "CONVERGED",
        "iterations": 4,
        "trajectory_worst_relative_k0_3": "at most 1e-9",
        "restarts, drops, landings, invalid trials": 0,
        "max_abs_t_minus_t_star": "at most 1e-5",
    }
    return ok, value, expected


def _a08(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    value: dict[str, Any] = {}
    ok = True
    for name in REC:
        result = _rec(ref, runs, name, 0.1)
        case = ref["cases_rec"][name]
        registered = case["variants"]["gamma=0.1"]["policy_simulation_anderson"]
        worst = worst_relative(
            result.residual_inf_scaled, registered["residual_inf_scaled"], 5, floor=1e-6
        )
        t_star = recycle_fixtures.floats(case["t_star"])
        to_t_star = float(np.max(np.abs(result.x - t_star)))
        row: dict[str, Any] = {
            "outcome": result.outcome,
            "iterations": result.iterations,
            "twin_iterations": registered["iterations"],
            "trajectory_worst_relative_k0_5": worst,
            "max_abs_t_minus_t_star": to_t_star,
        }
        good = (
            result.outcome == "CONVERGED"
            and registered["iterations"] <= result.iterations <= registered["iterations"] + 2
            and worst <= 1e-8
        )
        if name == "REC-05":
            s1 = recycle_fixtures.floats(registered["final_t"])
            row["max_abs_t_minus_S1"] = float(np.max(np.abs(result.x - s1)))
            good = good and row["max_abs_t_minus_S1"] <= 1e-4 and to_t_star > 1.0
        else:
            good = good and to_t_star <= 1e-5
        value[name] = row
        ok = ok and good
    expected = {
        "outcome": "CONVERGED",
        "iterations": "within [twin, twin + 2]",
        "trajectory_worst_relative_k0_5": "at most 1e-8 where the twin exceeds 1e-6",
        "REC-01..04 max_abs_t_minus_t_star": "at most 1e-5",
        "REC-05": "max_abs_t_minus_S1 at most 1e-4 and max_abs_t_minus_t_star above 1",
    }
    return ok, value, expected


def _a09(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    result = _rec(ref, runs, "REC-01", 0.0, depth_max=0)
    registered = ref["cases_rec"]["REC-01"]["variants"]["gamma=0"][
        "policy_simulation_substitution_depth0"
    ]
    betas = [event.beta_substitution for event in result.accelerations]
    value = {
        **recycle_summary(result),
        "beta_first_three": betas[:3],
        "beta_after": sorted(set(betas[3:])),
        "twin_iterations": registered["iterations"],
    }
    ok = (
        result.oscillation_detected_at == 3
        and betas[:3] == [1.0, 1.0, 1.0]
        and set(betas[3:]) == {0.5}
        and result.outcome == "CONVERGED"
        and result.iterations <= 60
        and result.iterations == registered["iterations"]
    )
    expected = {
        "oscillation_detected_at": 3,
        "beta_first_three": [1.0, 1.0, 1.0],
        "beta_after": [0.5],
        "outcome": "CONVERGED",
        "iterations": f"at most 60 and equal to the twin's {registered['iterations']}",
    }
    return ok, value, expected


def _a10(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    case = ref["cases_rec"]["REC-02"]
    g, t0 = recycle_fixtures.manufactured(case, 0.0)
    trace = Trace()
    substitution = solve_recycle(
        recycle_fixtures.recycle_problem(g, [3.0] * 3),
        t0,
        policy=RecyclePolicy(depth_max=0),
        keep_trajectory=True,
        trace=trace,
    )
    runs["REC-02 gamma=0.0 depth_max=0"] = substitution
    second = substitution.trajectory[2]
    landed_alpha = [event.alpha for event in trace.of_kind("step_accepted")][1]
    registered_landed = [number(v) for v in case["substitution_iterate_2_landed"]]
    accelerated = {gamma: _rec(ref, runs, "REC-02", gamma) for gamma in (0.0, 0.1)}
    value = {
        "iterate_2": [float(v) for v in second],
        "iterate_2_t_A_sign_bit_positive": math.copysign(1.0, float(second[0])) == 1.0,
        "alpha_of_the_landing_step": landed_alpha,
        "unbounded_iterate_2_registered": [
            number(v) for v in case["unbounded_linear_substitution_iterate_2"]
        ],
        **{
            key: item
            for key, item in recycle_summary(substitution).items()
            if key in {"outcome", "iterations", "oscillation_detected_at", "invalid_trials"}
        },
        "anderson": {
            f"gamma={gamma}": {
                "bound_landings": result.bound_landings,
                "invalid_trials": result.invalid_trials,
            }
            for gamma, result in accelerated.items()
        },
    }
    ok = (
        float(second[0]) == 0.0
        and value["iterate_2_t_A_sign_bit_positive"]
        and relative_off(float(second[1]), registered_landed[1]) <= 1e-15
        and relative_off(float(second[2]), registered_landed[2]) <= 1e-15
        and relative_off(landed_alpha, 14.0 / 15.0) <= 1e-12
        and number(case["unbounded_linear_substitution_iterate_2"][0]) == -0.125
        and substitution.oscillation_detected_at == 3
        and substitution.outcome == "CONVERGED"
        and substitution.iterations <= 60
        and substitution.invalid_trials == 0
        and all(
            result.bound_landings == result.invalid_trials == 0 for result in accelerated.values()
        )
    )
    expected = {
        "iterate_2": registered_landed,
        "iterate_2_t_A_sign_bit_positive": True,
        "alpha_of_the_landing_step": "14/15 to 1e-12 relative",
        "unbounded_iterate_2_registered": "t_A = -0.125",
        "outcome": "CONVERGED",
        "iterations": "at most 60",
        "oscillation_detected_at": 3,
        "invalid_trials": 0,
        "anderson": "zero landings and zero invalid trials at both gamma",
    }
    return ok, value, expected


def _a11(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    case = ref["cases_rec"]["REC-03"]
    result = _rec(ref, runs, "REC-03", 0.0, depth_max=0)
    linear = _rec(ref, runs, "REC-03", 0.0)
    tail = _rec(ref, runs, "REC-03", 0.1)
    registered = case["variants"]["gamma=0"]["policy_simulation_substitution_depth0"]
    detected = result.oscillation_detected_at or 0
    value = {
        "outcome": result.outcome,
        "iterations": result.iterations,
        "final_residual_inf_scaled": result.residual_inf_scaled[-1],
        # The spec's argument, `0.65 · 0.95²⁰⁰`, is undamped substitution. Under the registered
        # policy the oscillation detector fires (the twin's too), the plain steps are damped by
        # 0.5, and the slow `+0.95` mode then governs at `(1 + 0.95) / 2 = 0.975`: from
        # `|f̂₀| = 0.05 · 0.5 / 3`, three undamped steps and the rest damped. Recorded, not
        # judged — the assertion's criterion is the residual above `τ̂`, which both clear.
        "spec_argument_0.65_x_0.95^200": 0.65 * 0.95**200,
        "oscillation_detected_at": result.oscillation_detected_at,
        "twin_oscillation_detected_at": registered["events"]["oscillation_detected_at"],
        "closed_form_under_the_policy": (0.05 * 0.5 / 3.0)
        * 0.95**detected
        * 0.975 ** (200 - detected),
        "best_damping": {key: number(item) for key, item in case["best_damping"].items()},
        "anderson_linear_iterations": linear.iterations,
        "anderson_tail_iterations": tail.iterations,
    }
    ok = (
        result.outcome == "BUDGET_EXHAUSTED"
        and result.iterations == 200
        and result.residual_inf_scaled[-1] > TAU_HAT
        and number(case["best_damping"]["omega_star"]) == 1.0
        and relative_off(number(case["best_damping"]["rate"]), 0.95) <= 1e-15
        and linear.iterations == 4
        and tail.iterations <= 9
    )
    expected = {
        "outcome": "BUDGET_EXHAUSTED",
        "iterations": 200,
        "final_residual_inf_scaled": f"above the scaled tolerance {TAU_HAT}",
        "best_damping": {"omega_star": 1.0, "rate": 0.95},
        "anderson_linear_iterations": 4,
        "anderson_tail_iterations": "at most 9",
    }
    return ok, value, expected


def _a12(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    result = _rec(ref, runs, "REC-04", 0.0, depth_max=0)
    linear = _rec(ref, runs, "REC-04", 0.0)
    tail = _rec(ref, runs, "REC-04", 0.1)
    value = {
        "iterations": result.iterations,
        "oscillation_detected_at": result.oscillation_detected_at,
        "any_event_flagged": any(event.oscillation_flag for event in result.accelerations),
        "anderson_linear_iterations": linear.iterations,
        "anderson_tail_iterations": tail.iterations,
    }
    ok = (
        result.iterations == 200
        and result.oscillation_detected_at is None
        and not value["any_event_flagged"]
        and linear.iterations == 4
        and tail.iterations <= 9
    )
    expected = {
        "iterations": 200,
        "oscillation_detected_at": None,
        "any_event_flagged": False,
        "anderson_linear_iterations": 4,
        "anderson_tail_iterations": "at most 9",
    }
    return ok, value, expected


def _a13(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    result = _rec(ref, runs, "REC-05", 0.0)
    norms = result.residual_inf_scaled
    value = {**recycle_summary(result), "residual_inf_scaled_k0_2": list(norms[:3])}
    ok = (
        norms[1] > norms[0]
        and norms[2] > norms[0]
        and result.residual_increases >= 1
        and not result.restarts
        and not result.stagnation_closures
        and result.columns_dropped_condition == result.columns_dropped_coefficient == 0
        and result.iterations == 4
    )
    expected = {
        "residual_inf_scaled_k0_2": "iterates 1 and 2 above iterate 0",
        "residual_increases": "at least 1",
        "restarts": [],
        "stagnation_closures": [],
        "columns_dropped": 0,
        "iterations": 4,
    }
    return ok, value, expected


def _merge(
    loop: Any, t0: Any, policy: RecyclePolicy | None = None, unsupported: Any = None
) -> tuple[Any, Trace]:
    result, trace = merge_fixtures.run(loop, t0, policy=policy, unsupported=unsupported)
    return result, trace


def _a14(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    loop, t0 = merge_fixtures.rec_05(ref, 0.1)
    result, _ = _merge(loop, t0, RecyclePolicy(depth_max=0))
    runs["REC-05 gamma=0.1 depth_max=0 (merge)"] = result.recycle
    roots = ref["cases_rec"]["REC-05"]["fixed_points_gamma=0.1"]
    distances = {
        name: float(np.max(np.abs(result.x - recycle_fixtures.floats(roots[name]))))
        for name in ("t*", "S1")
    }
    landing = next(
        (name for name, distance in distances.items() if distance <= 10 * TAU), "unregistered"
    )
    value = {
        "recycle": {
            key: item
            for key, item in recycle_summary(result.recycle).items()
            if key in {"outcome", "iterations", "stagnation_closures", "restarts"}
        },
        "merge_into_eo": result.merge_into_eo,
        "outcome": result.outcome,
        "merged_residual_inf": result.merged.residual_inf,
        "merged_iterations": result.merged.iterations,
        "landing_recorded": landing,
        "distance_to": distances,
        "x": [float(v) for v in result.x],
    }
    ok = (
        result.recycle.outcome == "RECYCLE_STAGNATION"
        and result.recycle.iterations == 20
        and result.recycle.stagnation_closures == (10, 15, 20)
        and len(result.recycle.restarts) == 2
        and result.merge_into_eo == "taken"
        and result.outcome == "CONVERGED"
        and result.merged.residual_inf <= TAU
    )
    expected = {
        "recycle": {
            "outcome": "RECYCLE_STAGNATION",
            "iterations": 20,
            "stagnation_closures": [10, 15, 20],
            "restarts": "two, counts 1 and 2",
        },
        "merge_into_eo": "taken",
        "outcome": "CONVERGED",
        "merged_residual_inf": f"at most {TAU}",
        "landing_recorded": "recorded, not asserted (t* or S1)",
    }
    return ok, plain(value), expected


def _a15(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    case = ref["cases_auxiliary"]["RCY-DIV"]
    a = np.array([recycle_fixtures.floats(row) for row in case["A"]])
    t_star = recycle_fixtures.floats(ref["cases_rec"]["REC-01"]["t_star"])
    loop = merge_fixtures.Loop(
        lambda t: t_star + a @ (t - t_star), lambda t: a, [3.0] * 3, bounded=False
    )
    result, _ = _merge(loop, recycle_fixtures.floats(case["start"]), RecyclePolicy(depth_max=0))
    runs["RCY-DIV depth_max=0"] = result.recycle
    accelerated, _ = _merge(loop, recycle_fixtures.floats(case["start"]))
    runs["RCY-DIV anderson"] = accelerated.recycle
    norms = result.recycle.residual_inf_scaled
    closed = [0.4] + [0.25 * 1.5**k / 3.0 for k in range(1, 17)]
    worst = max(relative_off(norms[k], closed[k]) for k in range(17)) if len(norms) >= 17 else None
    value = {
        "recycle": recycle_summary(result.recycle),
        "trajectory_worst_relative_vs_closed_form": worst,
        "merge_into_eo": result.merge_into_eo,
        "outcome": result.outcome,
        "merged_iterations": result.merged.iterations,
        "max_abs_x_minus_t_star": float(np.max(np.abs(result.x - t_star))),
        "anderson": {
            "outcome": accelerated.outcome,
            "iterations": accelerated.recycle.iterations,
            "merge_into_eo": accelerated.merge_into_eo,
        },
    }
    ok = (
        result.recycle.outcome == "RECYCLE_STAGNATION"
        and result.recycle.iterations == 16
        and result.recycle.stagnation_closures == (6, 11, 16)
        and worst is not None
        and worst <= 1e-12
        and result.merge_into_eo == "taken"
        and result.outcome == "CONVERGED"
        and result.merged.iterations == 1
        and value["max_abs_x_minus_t_star"] <= TAU
        and accelerated.outcome == "CONVERGED"
        and accelerated.recycle.iterations == 4
        and accelerated.merge_into_eo is None
    )
    expected = {
        "recycle": {
            "outcome": "RECYCLE_STAGNATION",
            "iterations": 16,
            "stagnation_closures": [6, 11, 16],
        },
        "trajectory_worst_relative_vs_closed_form": "at most 1e-12",
        "merge_into_eo": "taken",
        "outcome": "CONVERGED",
        "merged_iterations": 1,
        "max_abs_x_minus_t_star": f"at most {TAU}",
        "anderson": {"outcome": "CONVERGED", "iterations": 4, "merge_into_eo": None},
    }
    return ok, value, expected


def _a16(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    from openflowsheet.verify.failure import bundle_for

    registered = ref["cases_auxiliary"]["RCY-STALL"]["anderson"]
    loop = merge_fixtures.Loop(lambda t: t + 1.0, lambda t: np.eye(3), [3.0] * 3, bounded=False)
    result, trace = _merge(loop, np.zeros(3))
    runs["RCY-STALL"] = result.recycle
    bundle = bundle_for(result, trace).as_document()
    value = {
        "recycle": recycle_summary(result.recycle),
        "merge_into_eo": result.merge_into_eo,
        "outcome": result.outcome,
        "linear_reason": result.merged.linear_reason,
        "checkpoint": result.checkpoint,
        "INFEASIBLE_in_bundle": "INFEASIBLE" in json.dumps(bundle).upper(),
    }
    ok = (
        result.recycle.outcome == "RECYCLE_STAGNATION" == registered["outcome"]
        and result.recycle.iterations == 15 == registered["iterations"]
        and result.recycle.stagnation_closures == (5, 10, 15)
        and len(result.recycle.restarts) == 2
        and result.recycle.columns_dropped_condition
        == 27
        == registered["events"]["column_dropped_condition"]
        and result.recycle.anderson_steps == 0
        and result.merge_into_eo == "taken"
        and result.outcome == "LINEAR_SOLVE_FAILED"
        and result.merged.linear_reason == "exactly_singular"
        and result.checkpoint is None
        and not value["INFEASIBLE_in_bundle"]
    )
    expected = {
        "recycle": {
            "outcome": "RECYCLE_STAGNATION",
            "iterations": 15,
            "stagnation_closures": [5, 10, 15],
            "restarts": 2,
            "columns_dropped_condition": 27,
            "anderson_steps": 0,
        },
        "merge_into_eo": "taken",
        "outcome": "LINEAR_SOLVE_FAILED",
        "linear_reason": "exactly_singular",
        "checkpoint": None,
        "INFEASIBLE_in_bundle": False,
    }
    return ok, value, expected


def _a17(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    registered = ref["cases_auxiliary"]["RCY-COEF"]
    loop = merge_fixtures.Loop(
        lambda t: t + 1.0 + 1e-6 * t, lambda t: np.array([[1.0 + 1e-6]]), [1.0], bounded=False
    )
    result, _ = _merge(loop, np.zeros(1))
    runs["RCY-COEF"] = result.recycle
    first = result.recycle.accelerations[1]
    reason, refused = first.dropped[0]
    coefficient = number(registered["secant_coefficient_at_k1"])
    root = number(registered["root"])
    value = {
        "event_k1": {
            "iteration": first.iteration,
            "depth_used": first.depth_used,
            "columns_dropped_coefficient": first.columns_dropped_coefficient,
            "gamma_inf": first.gamma_inf,
            "dropped": [reason, refused],
        },
        "refused_relative_off": relative_off(refused, coefficient),
        "recycle": recycle_summary(result.recycle),
        "merge_into_eo": result.merge_into_eo,
        "outcome": result.outcome,
        "merged_iterations": result.merged.iterations,
        "x": float(result.x[0]),
        "root_relative_off": relative_off(float(result.x[0]), root),
    }
    ok = (
        first.iteration == 1
        and first.depth_used == 0
        and first.columns_dropped_coefficient == 1
        and first.gamma_inf is None
        and reason == "coefficient"
        and value["refused_relative_off"] <= 1e-6
        and result.recycle.columns_dropped_coefficient == 12
        and result.recycle.stagnation_closures == (5, 10, 15)
        and result.recycle.outcome == "RECYCLE_STAGNATION"
        and result.merge_into_eo == "taken"
        and result.outcome == "CONVERGED"
        and result.merged.iterations == 1
        and value["root_relative_off"] <= 1e-9
    )
    expected = {
        "event_k1": {
            "iteration": 1,
            "depth_used": 0,
            "columns_dropped_coefficient": 1,
            "gamma_inf": None,
            "dropped": ["coefficient", coefficient],
        },
        "refused_relative_off": "at most 1e-6",
        "recycle": {
            "outcome": "RECYCLE_STAGNATION",
            "columns_dropped_coefficient": 12,
            "stagnation_closures": [5, 10, 15],
        },
        "merge_into_eo": "taken",
        "outcome": "CONVERGED",
        "merged_iterations": 1,
        "x": root,
        "root_relative_off": "at most 1e-9",
    }
    return ok, value, expected


def _plan_recycle(spec: Any, declaration: Any, solve_plan: Any) -> tuple[Any, Any]:
    """The recycle `R(t) = G(t) − t` a `converge` step's own tear partition defines, for an affine
    declaration: given the tear vector, the inner rows are solved for the inner variables (one
    exact linear solve — every NEST-1 row is affine, and T01 traced its coefficients), and the
    tear rows are evaluated there. Each tear row must be `x_i − f(…)` in its own tear variable
    (coefficient +1), so that `−R_row(x(t)) = G_i(t) − t_i`; anything else is refused.

    This is what makes A18's tear sets measured *through the plan*: the rows, variables and
    partition come from the `SolvePlan`, not from a hand-written map."""
    from openflowsheet.numerics.newton import Evaluation, Problem
    from openflowsheet.numerics.scaling import Scaling

    tear, tear_rows = solve_plan.tear_variable_ids, solve_plan.tear_row_ids
    inner, inner_rows = solve_plan.inner_variable_ids, solve_plan.inner_row_ids
    rows = declaration.rows
    for variable, row in zip(tear, tear_rows, strict=True):
        coefficients = rows[row].coefficients
        if coefficients is None or coefficients.get(variable) != 1.0:
            raise ValueError(f"tear row {row} is not x - f(...) in {variable}")
    for row in (*tear_rows, *inner_rows):
        if rows[row].coefficients is None:
            raise ValueError(f"row {row} is not affine; this derivation is for affine loops")
    parameters = dict(spec.parameters)

    def affine(row: str) -> tuple[dict[str, float], float]:
        traced = rows[row]
        return dict(traced.coefficients), float(traced._constant.evaluate(parameters))

    inner_matrix = np.zeros((len(inner_rows), len(inner)))
    inner_constant = np.zeros(len(inner_rows))
    coupling = np.zeros((len(inner_rows), len(tear)))
    for i, row in enumerate(inner_rows):
        coefficients, constant = affine(row)
        inner_constant[i] = constant
        for column, coefficient in coefficients.items():
            if column in inner:
                inner_matrix[i, inner.index(column)] = coefficient
            else:
                coupling[i, tear.index(column)] = coefficient

    def state_of(t: Any) -> dict[str, float]:
        solved = np.linalg.solve(inner_matrix, -(inner_constant + coupling @ np.asarray(t)))
        return {
            **dict(zip(inner, map(float, solved), strict=True)),
            **dict(zip(tear, map(float, t), strict=True)),
        }

    def residual(t: Any) -> Evaluation:
        if bool(np.any(np.asarray(t) < 0.0)):
            return Evaluation(status="invalid_trial_state", message="negative component flow")
        state = state_of(t)
        values = []
        for row in tear_rows:
            coefficients, constant = affine(row)
            values.append(
                -(constant + sum(c * state[column] for column, c in coefficients.items()))
            )
        return Evaluation(status="ok", values=tuple(values))

    problem = Problem(
        variable_ids=tuple(tear),
        row_ids=tuple(tear_rows),
        residual=residual,
        jacobian=lambda t: np.zeros((len(tear), len(tear))),
        scaling=Scaling(column=dict.fromkeys(tear, 1.0), row=dict.fromkeys(tear_rows, 1.0)),
        row_tolerance=dict.fromkeys(tear_rows, TAU),
        lower_bounds=dict.fromkeys(tear, 0.0),
    )
    return problem, state_of


def _a18(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    from openflowsheet.orchestrator.execution import iterated_tear_set

    case = ref["cases_auxiliary"]["NEST-1"]
    registered = case["tear"]
    _, graph, _, report = plan_fixtures.nest_structure()
    assert report.tear is not None
    (loop,) = report.tear.loops
    streams, rounds = iterated_tear_set(graph, loop.units, loop.candidates)
    distances = {
        candidate.stream_id: candidate.consumer_boundary_distance for candidate in loop.candidates
    }
    registered_distances = {
        candidate["stream"]: candidate["consumer_boundary_distance"]
        for candidate in registered["rounds"][0]["candidates"]
    }

    spec, _, declaration, _ = plan_fixtures.nest_structure()
    rule_plan = plan_fixtures.nest_plan()
    alternate_plan = plan_fixtures.nest_plan(tear_streams=("s1", "s5"))
    runs_through_plans = {}
    for label, plan in (("rule", rule_plan), ("alternate", alternate_plan)):
        problem, state_of = _plan_recycle(spec, declaration, plan.steps[1].solve_plan)
        found = solve_recycle(problem, np.zeros(len(problem.variable_ids)))
        runs_through_plans[label] = (plan.steps[1], found, state_of(found.x))
    (rule_step, result, rule_state) = runs_through_plans["rule"]
    (alternate_step, alternate, alternate_state) = runs_through_plans["alternate"]
    runs["NEST-1"], runs["NEST-1 alternate"] = result, alternate
    fixed = recycle_fixtures.floats(case["fixed_point_s4_s5"])
    product, alternate_product = rule_state["s3.x"], alternate_state["s3.x"]
    value = {
        "t01_unsupported": loop.unsupported,
        "t01_candidates_break_loop": [candidate.breaks_loop for candidate in loop.candidates],
        "tear_streams": list(streams),
        "rounds": [
            {"cycle_edges": list(round_.cycle_edges), "chosen": round_.chosen} for round_ in rounds
        ],
        "consumer_boundary_distances": distances,
        "plan_tear": {
            "streams": list(rule_step.tear_streams),
            "variables": list(rule_step.solve_plan.tear_variable_ids),
            "rows": list(rule_step.solve_plan.tear_row_ids),
        },
        "anderson": {"outcome": result.outcome, "iterations": result.iterations},
        "fixed_point": [float(v) for v in result.x],
        "product_s3": product,
        "alternate": {
            "plan_tear": {
                "streams": list(alternate_step.tear_streams),
                "variables": list(alternate_step.solve_plan.tear_variable_ids),
                "rows": list(alternate_step.solve_plan.tear_row_ids),
            },
            "outcome": alternate.outcome,
            "iterations": alternate.iterations,
            "fixed_point": [float(v) for v in alternate.x],
            "product_s3": alternate_product,
        },
    }
    ok = (
        loop.unsupported == "multi_edge_feedback_set"
        and not any(value["t01_candidates_break_loop"])
        and list(streams) == registered["tear_streams"] == ["s4", "s5"]
        and value["rounds"]
        == [
            {"cycle_edges": entry["cycle_edges"], "chosen": entry["chosen"]}
            for entry in registered["rounds"]
        ]
        and distances == registered_distances
        and value["plan_tear"]
        == {"streams": ["s4", "s5"], "variables": ["s4.x", "s5.x"], "rows": ["B:s4", "C:s5"]}
        and value["alternate"]["plan_tear"]
        == {"streams": ["s1", "s5"], "variables": ["s1.x", "s5.x"], "rows": ["A:s1", "C:s5"]}
        and result.outcome == "CONVERGED"
        and result.iterations == 2
        and bool(np.all(np.abs(result.x - fixed) <= 1e-7))
        and abs(product - 1.0) <= 1e-7
        and alternate.outcome == "CONVERGED"
        and bool(
            np.all(
                np.abs(
                    alternate.x
                    - recycle_fixtures.floats(case["alternate_tear_s1_s5"]["fixed_point"])
                )
                <= 1e-7
            )
        )
        and abs(alternate_product - product) <= 1e-7
    )
    expected = {
        "t01_unsupported": "multi_edge_feedback_set",
        "t01_candidates_break_loop": [False, False, False, False],
        "tear_streams": registered["tear_streams"],
        "rounds": [
            {"cycle_edges": entry["cycle_edges"], "chosen": entry["chosen"]}
            for entry in registered["rounds"]
        ],
        "consumer_boundary_distances": registered_distances,
        "plan_tear": {
            "streams": ["s4", "s5"],
            "variables": ["s4.x", "s5.x"],
            "rows": ["B:s4", "C:s5"],
        },
        "anderson": {"outcome": "CONVERGED", "iterations": 2},
        "fixed_point": [float(v) for v in fixed],
        "product_s3": "1 within 1e-7",
        "alternate": {
            "plan_tear": {
                "streams": ["s1", "s5"],
                "variables": ["s1.x", "s5.x"],
                "rows": ["A:s1", "C:s5"],
            },
            "outcome": "CONVERGED",
            "iterations": "recorded (twin: 3)",
            "fixed_point": [float(v) for v in case["alternate_tear_s1_s5"]["fixed_point"]],
            "product_s3": "equal to the rule tear's within 1e-7",
        },
    }
    return ok, value, expected


def _a19(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    case = ref["cases_auxiliary"]["SCL-1"]
    g, t0 = recycle_fixtures.manufactured(ref["cases_rec"]["REC-03"], 0.0)
    result = solve_recycle(
        recycle_fixtures.recycle_problem(
            g,
            [number(v) for v in case["scale"]],
            tolerance=[number(v) for v in case["tolerance_mol_per_s"]],
        ),
        t0,
    )
    runs["SCL-1"] = result
    unscaled = _rec(ref, runs, "REC-03", 0.0)
    registered = case["anderson"]
    worst = worst_relative(result.residual_inf_scaled, registered["residual_inf_scaled"], 3)
    kappa = max(event.kappa_2 or 0.0 for event in result.accelerations)
    gamma = max(event.gamma_inf or 0.0 for event in result.accelerations)
    shift = abs(result.residual_inf_scaled[2] - unscaled.residual_inf_scaled[2])
    value = {
        "iterations": result.iterations,
        "trajectory_worst_relative_k0_3": worst,
        "iterate_2_shift_from_unscaled": shift,
        "max_kappa_2": kappa,
        "max_gamma_inf": gamma,
        "twin_max_kappa_2": number(registered["events"]["max_kappa"]),
        "twin_max_gamma_inf": number(registered["events"]["max_gamma_inf"]),
    }
    ok = result.iterations == 4 and worst <= 1e-9 and shift > 1e-2 and kappa <= 1e7 and gamma <= 1e3
    expected = {
        "iterations": 4,
        "trajectory_worst_relative_k0_3": "at most 1e-9",
        "iterate_2_shift_from_unscaled": "above 1e-2",
        "max_kappa_2": "at most 1e7",
        "max_gamma_inf": "at most 1e3",
    }
    return ok, value, expected


def _a20(ref: Mapping[str, Any], runs: dict[str, RecycleResult]) -> tuple[bool, Any, Any]:
    result = _rec(ref, runs, "REC-01", 0.0, depth_max=2)
    registered = ref["cases_auxiliary"]["RCY-TRUNC"]["anderson"]
    worst = worst_relative(
        result.residual_inf_scaled, registered["residual_inf_scaled"], 5, floor=1e-6
    )
    value = {
        "iterations": result.iterations,
        "twin_iterations": registered["iterations"],
        "trajectory_worst_relative_k0_5": worst,
        "max_depth_used": max(event.depth_used for event in result.accelerations),
        "oscillation_detected_at": result.oscillation_detected_at,
        "beta_on_anderson_steps": sorted(
            {event.beta_substitution for event in result.accelerations if not event.plain}
        ),
    }
    ok = (
        10 <= result.iterations <= 20
        and result.iterations > 4
        and worst <= 1e-8
        and value["max_depth_used"] <= 2
        and result.oscillation_detected_at == 7
        and value["beta_on_anderson_steps"] == [1.0]
    )
    expected = {
        "iterations": "within [10, 20]",
        "trajectory_worst_relative_k0_5": "at most 1e-8",
        "max_depth_used": "at most 2",
        "oscillation_detected_at": 7,
        "beta_on_anderson_steps": [1.0],
    }
    return ok, value, expected


# ------------------------------------------------------------------------------ A21–A24


def _p01_agreement(case_id: str, state: Mapping[str, float]) -> dict[str, float]:
    """The state against P01's 20-digit values directly, where P01 names the quantity."""
    entry = next(
        item
        for item in yaml.safe_load(P01.read_text(encoding="utf-8"))["variants"]
        if item["case_id"] == case_id
    )
    recycle = [number(v) for v in entry["recycle_mol_per_s"]]
    return {
        "S6.n max abs off (mol/s)": max(
            abs(state[f"S6.n.{c}"] - recycle[i]) for i, c in enumerate(("A", "B", "C"))
        ),
        "U-HEAT.Q abs off (W)": abs(state["U-HEAT.Q"] - number(entry["Q_heater_W"])),
        "U-FLASH.Q abs off (W)": abs(state["U-FLASH.Q"] - number(entry["Q_flash_W"])),
    }


def _p01_within(agreement: Mapping[str, float]) -> bool:
    return (
        agreement["S6.n max abs off (mol/s)"] <= FLOW
        and agreement["U-HEAT.Q abs off (W)"] <= DUTY
        and agreement["U-FLASH.Q abs off (W)"] <= DUTY
    )


def _a21() -> tuple[bool, Any, Any]:
    item = region_fixtures.case("SYN-001-nominal")
    result = region_fixtures.solve(item, region_fixtures.initializer(item))
    first, second = result.attempts
    prefix = "phase_disappeared(U-HEAT, vapor, "
    variable = first.reason.removeprefix(prefix).rstrip(")")
    off = region_fixtures.disagreement(item, result.state)
    agreement = _p01_agreement("SYN-001-nominal", result.state)
    pinned = {name: result.state[name] for name in ("S3.V", "S3.vap.A", "S3.vap.B", "S3.vap.C")}
    value = {
        "outcome": result.outcome,
        "attempts": [
            {
                "signature": dict(attempt.signature),
                "outcome": attempt.outcome,
                "iterations": attempt.iterations,
                "reason": attempt.reason,
            }
            for attempt in result.attempts
        ],
        "departures_from_tear_solution": off,
        "p01": agreement,
        "pinned_vapour": pinned,
    }
    ok = (
        result.outcome == "CONVERGED"
        and len(result.attempts) == 2
        and dict(first.signature) == {"U-HEAT": "TWO_PHASE", "U-FLASH": "TWO_PHASE"}
        and first.outcome == "PHASE_UPDATE_REQUIRED"
        and first.iterations <= 2
        and first.reason.startswith(prefix)
        and variable in {"S3.vap.A", "S3.vap.B", "S3.vap.C", "S3.V"}
        and dict(second.signature) == {"U-HEAT": "LIQUID", "U-FLASH": "TWO_PHASE"}
        and second.outcome == "CONVERGED"
        and second.iterations <= 5
        and not off
        and _p01_within(agreement)
        and all(amount == 0.0 for amount in pinned.values())
    )
    expected = {
        "outcome": "CONVERGED",
        "attempts": [
            {
                "signature": {"U-HEAT": "TWO_PHASE", "U-FLASH": "TWO_PHASE"},
                "outcome": "PHASE_UPDATE_REQUIRED",
                "iterations": "at most 2",
                "reason": "phase_disappeared(U-HEAT, vapor, one of S3.vap.A/B/C, S3.V)",
            },
            {
                "signature": {"U-HEAT": "LIQUID", "U-FLASH": "TWO_PHASE"},
                "outcome": "CONVERGED",
                "iterations": "at most 5",
            },
        ],
        "departures_from_tear_solution": [],
        "p01": {"S6.n": FLOW, "duties": DUTY},
        "pinned_vapour": dict.fromkeys(pinned, 0.0),
    }
    return ok, value, expected


def _a22() -> tuple[bool, Any, Any]:
    bounds = {
        "SYN-001-high-recycle": 10,
        "SYN-001-all-liquid-310K": 5,
        "SYN-001-once-through": 0,
        "SYN-001-all-vapor-420K": 0,
    }
    value: dict[str, Any] = {}
    ok = True
    for case_id, bound in bounds.items():
        item = region_fixtures.case(case_id)
        result = region_fixtures.solve(item, region_fixtures.initializer(item))
        off = region_fixtures.disagreement(item, result.state)
        agreement = _p01_agreement(case_id, result.state)
        row: dict[str, Any] = {
            "outcome": result.outcome,
            "attempts": len(result.attempts),
            "iterations": result.iterations,
            "departures_from_tear_solution": off,
            "p01": agreement,
        }
        good = (
            result.outcome == "CONVERGED"
            and len(result.attempts) == 1
            and result.iterations <= bound
            and not off
            and _p01_within(agreement)
        )
        if case_id == "SYN-001-high-recycle":
            row["heater_regime"] = dict(result.signatures[0])["U-HEAT"]
            row["S3.V"] = result.state["S3.V"]
            good = good and row["heater_regime"] == "LIQUID" and row["S3.V"] == 0.0
        value[case_id] = row
        ok = ok and good
    expected = {
        "outcome": "CONVERGED",
        "attempts": 1,
        "iterations": "at most 10, 5, 0, 0 (spec measured 5, 2, 0, 0)",
        "departures_from_tear_solution": [],
        "high-recycle": {"heater_regime": "LIQUID", "S3.V": 0.0},
    }
    return ok, value, expected


def _a23() -> tuple[bool, Any, Any]:
    from openflowsheet.orchestrator.tear import solve_tear

    value: dict[str, Any] = {}
    ok = True
    for case_id in VARIANTS:
        item = region_fixtures.case(case_id)
        tear, _ = solve_tear(item.flowsheet)
        assert tear.final_state is not None
        result = region_fixtures.solve(item, dict(tear.final_state))
        value[case_id] = {
            "outcome": result.outcome,
            "iterations": result.iterations,
            "jacobian_calls": result.counters.jacobian_calls,
            "factorizations": result.counters.factorizations,
        }
        ok = ok and value[case_id] == {
            "outcome": "CONVERGED",
            "iterations": 0,
            "jacobian_calls": 0,
            "factorizations": 0,
        }
    expected = {"outcome": "CONVERGED", "iterations": 0, "jacobian_calls": 0, "factorizations": 0}
    return ok, value, expected


def _a24() -> tuple[bool, Any, Any]:
    item = region_fixtures.case("SYN-001-once-through")
    state = region_fixtures.initializer(item)
    feed = [state[f"S3.n.{component}"] for component in item.flowsheet.components]
    for component, amount in zip(item.flowsheet.components, feed, strict=True):
        state[f"S3.liq.{component}"] = amount
        state[f"S3.vap.{component}"] = 0.0
    state["S3.V"], state["S3.L"] = 0.0, float(sum(feed))
    trace = Trace()
    result = region_fixtures.solve(item, state, trace)
    beta = result.state["S3.V"] / (result.state["S3.V"] + result.state["S3.L"])
    registered = number(item.p01["heater_outlet_vapor_fraction"])
    value = {
        "projections": list(result.projections),
        "initializer_candidate_messages": [
            event.message for event in trace.of_kind("initializer_candidate")
        ],
        "initializer_accepted_events": len(trace.of_kind("initializer_accepted")),
        "outcome": result.outcome,
        "attempts": len(result.attempts),
        "iterations": result.iterations,
        "heater_outlet_vapor_fraction": beta,
        "relative_off_p01": relative_off(beta, registered),
    }
    ok = (
        value["projections"] == ["S3"]
        and value["initializer_candidate_messages"] == ["projected(S3, all_liquid, TWO_PHASE)"]
        and value["initializer_accepted_events"] == 1
        and result.outcome == "CONVERGED"
        and len(result.attempts) == 1
        and result.iterations == 0
        and value["relative_off_p01"] <= 1e-12
    )
    expected = {
        "projections": ["S3"],
        "initializer_candidate_messages": ["projected(S3, all_liquid, TWO_PHASE)"],
        "initializer_accepted_events": 1,
        "outcome": "CONVERGED",
        "attempts": 1,
        "iterations": 0,
        "heater_outlet_vapor_fraction": registered,
        "relative_off_p01": "at most 1e-12",
    }
    return ok, value, expected


# ------------------------------------------------------------------------------ A25–A31


def _a25(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    registered = ref["syn001"]["plans"]["SYN-001-A02-*"]
    expected_step = registered[1]
    certified = set(ref["syn001"]["certified_rows"])
    fixed_upstream = list(ref["syn001"]["a02_region"]["fixed_upstream"])
    value: dict[str, Any] = {}
    ok = True
    for case_id in A02_CASES[:3]:
        item = a02_fixtures.structure(a02_fixtures.revision(case_id))
        declaration = item.declaration
        with _spied() as calls:
            plan = a02_fixtures.plan_for(item)
        evaluate, solve_eo = plan.steps
        region = solve_eo.region
        solve_plan = solve_eo.solve_plan
        assert region is not None and solve_plan is not None
        units = set(a02_fixtures.REGION_UNITS)
        unit_rows = {row for row in declaration.row_ids if declaration.rows[row].unit in units}
        free = set(declaration.column_ids)
        row = {
            "finding": item.report.finding,
            "kinds": [step.kind for step in plan.steps],
            "evaluate": list(evaluate.units),
            "region_units": list(solve_eo.units),
            "specification_rows": list(region.specification_rows),
            "adjusted_variables": list(region.adjusted_variables),
            "target_variables": list(region.target_variables),
            "removed_specification_rows": list(region.removed_specification_rows),
            "signature_units": list(solve_plan.signature_units),
            "square": [len(region.row_ids), len(region.variable_ids)],
            "tear_variable_ids": list(solve_plan.tear_variable_ids),
            "eliminated_rows": sorted(entry.row_id for entry in solve_plan.eliminated_rows),
            "unit_rows": len(unit_rows),
            "rows_are_unit_rows_minus_certificates": set(region.row_ids) == unit_rows - certified,
            "columns_are_free_minus_S1": set(region.variable_ids) == free - set(fixed_upstream),
            "fixed_upstream": list(region.fixed_upstream),
            "calls_during_plan_construction": dict(calls),
        }
        value[case_id] = row
        ok = ok and row == {
            "finding": "STRUCTURALLY_CLOSED",
            "kinds": [step["kind"] for step in registered],
            "evaluate": [registered[0]["unit"]],
            "region_units": expected_step["region_units"],
            "specification_rows": expected_step["specification_rows"],
            "adjusted_variables": [expected_step["adjusted_variable"]],
            "target_variables": [expected_step["target_variable"]],
            "removed_specification_rows": [expected_step["removed_specification_row"]],
            "signature_units": expected_step["signature_units"],
            "square": [expected_step["square"], expected_step["square"]],
            "tear_variable_ids": [],
            "eliminated_rows": sorted(certified),
            "unit_rows": 44,
            "rows_are_unit_rows_minus_certificates": True,
            "columns_are_free_minus_S1": True,
            "fixed_upstream": fixed_upstream,
            "calls_during_plan_construction": {},
        }
    expected = {
        "plan": registered,
        "eliminated_rows": sorted(certified),
        "unit_rows": 44,
        "fixed_upstream": fixed_upstream,
        "calls_during_plan_construction": {},
    }
    return ok, value, expected


def _a26() -> tuple[bool, Any, Any]:
    from openflowsheet.application.validation import validate
    from openflowsheet.orchestrator.execution import UnsupportedRankStructureError

    def refused(build: Callable[[], Any]) -> str:
        try:
            build()
        except (ValueError, UnsupportedRankStructureError) as error:
            return f"{type(error).__name__}: {error}"
        return "a plan was built"

    over_document = a02_fixtures.over_specified()
    over = a02_fixtures.structure(over_document)
    with _spied(analysis=False) as over_calls:
        report = validate(over_document)
        str03 = next(entry for entry in report.checks if entry.id == "STR-03")
        over_plan = refused(lambda: a02_fixtures.plan_for(over, specifications=()))
    over_value = {
        "status": report.status,
        "STR-03": [str03.result, "STRUCTURAL_OVER_SPECIFICATION" in str03.message],
        "finding": over.report.finding,
        "over_specified_units": list(over.report.over_specified_units),
        "STR-03_implicated_objects": list(str03.implicated_objects),
        "candidate_specifications": sorted(over.report.candidate_specifications),
        "declared_specifications": len(over_document["specifications"]),
        "plan": over_plan,
        "calls": dict(over_calls),
    }
    # A26 as amended: the unit T01's matching names, among the two the conflict involves, and
    # both conflicting specifications among the candidates.
    names_unit = bool(set(over_value["over_specified_units"]) & {"U-HEAT", "U-FLASH"})
    both_candidates = {"SPEC-heater-outlet-T", "SPEC-flash-duty"} <= set(
        over_value["candidate_specifications"]
    )

    under_document = a02_fixtures.under_specified()
    under = a02_fixtures.structure(under_document)
    with _spied(analysis=False) as under_calls:
        report = validate(under_document)
        str02 = next(entry for entry in report.checks if entry.id == "STR-02")
        under_plan = refused(lambda: a02_fixtures.plan_for(under, specifications=()))
    under_value = {
        "status": report.status,
        "STR-02": [str02.result, "STRUCTURAL_UNDER_SPECIFICATION" in str02.message],
        "S3.T_implicated": "S3.T" in str02.implicated_objects,
        "finding": under.report.finding,
        "plan": under_plan,
        "calls": dict(under_calls),
    }

    closed = a02_fixtures.structure(a02_fixtures.revision("SYN-001-A02-360"))
    region = a02_fixtures.the_region(closed)
    short = replace(region, row_ids=region.row_ids[:-1])
    with _spied(analysis=False) as short_calls:
        short_plan = refused(lambda: a02_fixtures.plan_for(closed, specifications=(short,)))
    short_value = {
        "square": short.square,
        "plan": short_plan,
        "calls": dict(short_calls),
    }

    value = {
        "HEAT-T retained": over_value,
        "over-specified unit among U-HEAT/U-FLASH": names_unit,
        "both conflicting specifications among the candidates": both_candidates,
        "no promotion row": under_value,
        "closed non-square region": short_value,
    }
    ok = (
        over_value["status"] == "INVALID"
        and over_value["STR-03"] == ["FAIL", True]
        and over_value["finding"] == "STRUCTURAL_OVER_SPECIFICATION"
        and over_plan.startswith("ValueError")
        and "structurally closed" in over_plan
        and names_unit
        and both_candidates
        and not over_calls
        and under_value["STR-02"] == ["FAIL", True]
        and under_value["S3.T_implicated"]
        and under_value["finding"] == "STRUCTURAL_UNDER_SPECIFICATION"
        and under_plan.startswith("ValueError")
        and not under_calls
        and not short.square
        and short_plan.startswith("UnsupportedRankStructureError")
        and "UNSUPPORTED_RANK_STRUCTURE" in short_plan
        and not short_calls
    )
    expected = {
        "HEAT-T retained": {
            "status": "INVALID",
            "STR-03": ["FAIL", True],
            "finding": "STRUCTURAL_OVER_SPECIFICATION",
            "plan": "refused: needs a structurally closed declaration",
            "calls": {},
        },
        "over-specified unit among U-HEAT/U-FLASH": True,
        "both conflicting specifications among the candidates": True,
        "no promotion row": {
            "status": "recorded (spec: not stated; measured DRAFT per R-022)",
            "STR-02": ["FAIL", True],
            "S3.T_implicated": True,
            "finding": "STRUCTURAL_UNDER_SPECIFICATION",
            "plan": "refused",
            "calls": {},
        },
        "closed non-square region": {
            "square": False,
            "plan": "UnsupportedRankStructureError: UNSUPPORTED_RANK_STRUCTURE",
            "calls": {},
        },
    }
    return ok, value, expected


def _a27() -> tuple[bool, Any, Any]:
    from openflowsheet.orchestrator.execution import PlanRefusal, plan_or_refusal
    from openflowsheet.verify.failure import refusal_bundle

    item = a02_fixtures.structure(a02_fixtures.revision("SYN-001-A02-360"))
    region = a02_fixtures.the_region(item)
    manifests = a02_fixtures.cap1_manifests(item)
    with _spied() as calls:
        outcome = plan_or_refusal(
            spec=item.binding.spec,
            declaration=item.declaration,
            graph=item.binding.graph,
            report=item.report,
            manifests=manifests,
            policy=a02_fixtures.POLICY,
            specifications=(region,),
            specification_ids=item.binding.specification_ids,
        )
    if not isinstance(outcome, PlanRefusal):
        return (
            False,
            {"refused": False, "steps": [step.kind for step in outcome.steps]},
            {"refused": True},
        )
    message = str(outcome.error)
    events = outcome.trace.events
    counters = events[-1].counters if events else None
    bundle = refusal_bundle(outcome).as_document()
    actions = [entry["action"] for entry in bundle["suggested_actions"]]
    schema_errors = len(list(a02_fixtures.failure_bundle_validator().iter_errors(bundle)))
    named = ("U-HEAT", "'unavailable'", *a02_fixtures.REGION_UNITS, "SPEC-flash-duty")
    value = {
        "outcome": outcome.outcome,
        "message_names": {name: name in message for name in named},
        "event_kinds": [event.kind for event in events],
        "counters": {
            "residual_calls": counters.residual_calls if counters else None,
            "jacobian_calls": counters.jacobian_calls if counters else None,
            "property_calls": counters.property_calls if counters else None,
        },
        "calls_during_refusal": dict(calls),
        "taxonomy": bundle["taxonomy"],
        "suggested_actions": actions,
        "implicated_sources": bundle["implicated_sources"],
        "attempt_tree": bundle["attempt_tree"],
        "bundle_schema_errors": schema_errors,
    }
    ok = (
        outcome.outcome == "CAPABILITY_UNAVAILABLE"
        and all(value["message_names"].values())
        and value["event_kinds"] == ["solve_closed"]
        and events[-1].outcome == "CAPABILITY_UNAVAILABLE"
        and value["counters"] == {"residual_calls": 0, "jacobian_calls": 0, "property_calls": 0}
        and not calls
        and bundle["taxonomy"] == "model domain/conservation/derivative defects"
        and actions == ["provide_derivatives"]
        and bundle["implicated_sources"][0] == "U-HEAT"
        and "SPEC-flash-duty" in bundle["implicated_sources"]
        and bundle["attempt_tree"] == []
        and schema_errors == 0
    )
    expected = {
        "outcome": "CAPABILITY_UNAVAILABLE",
        "message_names": dict.fromkeys(named, True),
        "event_kinds": ["solve_closed"],
        "counters": {"residual_calls": 0, "jacobian_calls": 0, "property_calls": 0},
        "calls_during_refusal": {},
        "taxonomy": "model domain/conservation/derivative defects",
        "suggested_actions": ["provide_derivatives"],
        "implicated_sources": "U-HEAT first, SPEC-flash-duty among them",
        "attempt_tree": [],
        "bundle_schema_errors": 0,
    }
    return ok, value, expected


def _a02_solves() -> dict[str, Any]:
    solves: dict[str, Any] = {}
    for case_id in A02_CASES:
        try:
            solves[case_id] = a02_fixtures.solve(case_id)
        except Exception as error:  # noqa: BLE001 - each consuming check records it
            solves[case_id] = error
    return solves


def _solved(solves: Mapping[str, Any], case_id: str) -> Any:
    result = solves[case_id]
    if isinstance(result, Exception):
        raise result
    return result


def _a28_a29(
    ref: Mapping[str, Any], solves: Mapping[str, Any], case_ids: Sequence[str]
) -> tuple[bool, Any, Any]:
    t_star = [number(v) for v in ref["syn001"]["t_star_nominal_mol_per_s"]]
    value: dict[str, Any] = {}
    expected: dict[str, Any] = {}
    ok = True
    for case_id in case_ids:
        temperature = float(case_id.rsplit("-", 1)[1])
        sweep = ref["syn001"]["a02_sweep"][f"T_heater={int(temperature)}K"]
        result = _solved(solves, case_id)
        state = result.state
        split_off = max(
            max(
                abs(state[f"S3.vap.{c}"] - number(sweep["S3_vapor_mol_per_s"][i])),
                abs(state[f"S3.liq.{c}"] - number(sweep["S3_liquid_mol_per_s"][i])),
            )
            for i, c in enumerate(("A", "B", "C"))
        )
        row = {
            "outcome": result.outcome,
            "attempts": len(result.attempts),
            "iterations": result.iterations,
            "S3.T": state["S3.T"],
            "S3.T abs off (K)": abs(state["S3.T"] - temperature),
            "U-HEAT.Q abs off (W)": abs(state["U-HEAT.Q"] - number(sweep["Q_heater_W"])),
            "U-FLASH.Q abs off (W)": abs(state["U-FLASH.Q"] - number(sweep["Q_flash_W"])),
            "S3 split max abs off (mol/s)": split_off,
            "S6.n max abs off t* (mol/s)": max(
                abs(state[f"S6.n.{c}"] - t_star[i]) for i, c in enumerate(("A", "B", "C"))
            ),
        }
        value[case_id] = row
        expected[case_id] = {
            "outcome": "CONVERGED",
            "attempts": 1,
            "iterations": "at most 6",
            "S3.T": temperature,
            "S3.T abs off (K)": f"at most {TEMPERATURE}",
            "U-HEAT.Q": number(sweep["Q_heater_W"]),
            "U-FLASH.Q": number(sweep["Q_flash_W"]),
            "duty abs off (W)": f"at most {DUTY}",
            "split and S6.n abs off (mol/s)": f"at most {FLOW}",
        }
        ok = ok and (
            result.outcome == "CONVERGED"
            and len(result.attempts) == 1
            and result.iterations <= 6
            and row["S3.T abs off (K)"] <= TEMPERATURE
            and row["U-HEAT.Q abs off (W)"] <= DUTY
            and row["U-FLASH.Q abs off (W)"] <= DUTY
            and split_off <= FLOW
            and row["S6.n max abs off t* (mol/s)"] <= FLOW
        )
    return ok, value, expected


def _a30(ref: Mapping[str, Any], solves: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    roots = ref["syn001"]["branch_roots"]["Q_flash=Q(355K)"]
    result = _solved(solves, "SYN-001-A02-355-liquid-guess")
    first, second = result.attempts
    prefix = "inadmissible(S3, all_liquid, "
    recorded = (
        float(first.reason.removeprefix(prefix).rstrip(")"))
        if first.reason.startswith(prefix)
        else None
    )
    value = {
        "outcome": result.outcome,
        "attempt_1": {
            "heater": dict(first.signature)["U-HEAT"],
            "solver_outcome": first.solver_outcome,
            "outcome": first.outcome,
            "reason": first.reason,
            "S3.T": first.end_state["S3.T"],
            "S3.T abs off root (K)": abs(
                first.end_state["S3.T"] - number(roots["liquid_branch_T_K"])
            ),
            "sum_zK_relative_off": (
                relative_off(recorded, number(roots["liquid_branch_sum_zK"]))
                if recorded is not None
                else None
            ),
        },
        "attempt_2": {"heater": dict(second.signature)["U-HEAT"], "reason": second.reason},
        "checkpoint_label": result.checkpoint.label if result.checkpoint else None,
        "checkpoint_scope": result.checkpoint.verification_scope if result.checkpoint else None,
    }
    ok = (
        result.outcome == "ACTIVE_SET_CYCLING"
        and value["attempt_1"]["heater"] == "LIQUID"
        and first.solver_outcome == "CONVERGED"
        and first.outcome == "PHASE_UPDATE_REQUIRED"
        and recorded is not None
        and value["attempt_1"]["sum_zK_relative_off"] <= 1e-9
        and value["attempt_1"]["S3.T abs off root (K)"] <= TEMPERATURE
        and value["attempt_2"]["heater"] == "VAPOR"
        and value["checkpoint_label"] == "partial"
        and value["checkpoint_scope"] == "unverified"
    )
    expected = {
        "outcome": "ACTIVE_SET_CYCLING",
        "attempt_1": {
            "heater": "LIQUID",
            "solver_outcome": "CONVERGED",
            "outcome": "PHASE_UPDATE_REQUIRED",
            "reason": "inadmissible(S3, all_liquid, 2.4959938386228986)",
            "S3.T": number(roots["liquid_branch_T_K"]),
            "S3.T abs off root (K)": f"at most {TEMPERATURE}",
            "sum_zK_relative_off": "at most 1e-9",
        },
        "attempt_2": {"heater": "VAPOR"},
        "checkpoint_label": "partial",
        "checkpoint_scope": "unverified (no certificate)",
    }
    return ok, value, expected


def _a31(solves: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    result = _solved(solves, "SYN-001-A02-360-liquid-guess")
    first, second = result.attempts
    value = {
        "outcome": result.outcome,
        "attempt_1": {
            "heater": dict(first.signature)["U-HEAT"],
            "solver_outcome": first.solver_outcome,
            "reason": first.reason,
            "S3.T": first.end_state["S3.T"],
        },
        "attempt_2": {
            "heater": dict(second.signature)["U-HEAT"],
            "solver_outcome": second.solver_outcome,
            "reason": second.reason,
            "S3.T": second.end_state["S3.T"],
        },
        "certificate": result.checkpoint.label if result.checkpoint else None,
        "INFEASIBLE": "INFEASIBLE" in f"{result.outcome} {result.message}".upper(),
    }
    ok = (
        result.outcome == "ACTIVE_SET_CYCLING"
        and value["attempt_1"]["heater"] == "LIQUID"
        and first.solver_outcome == "STAGNATION"
        and first.reason == "kernel_disagrees(U-HEAT, VAPOR)"
        and first.end_state["S3.T"] >= 430.0
        and value["attempt_2"]["heater"] == "VAPOR"
        and second.reason == "kernel_disagrees(U-HEAT, LIQUID)"
        and second.end_state["S3.T"] <= 290.0
        and value["certificate"] != "candidate_root"
        and not value["INFEASIBLE"]
    )
    expected = {
        "outcome": "ACTIVE_SET_CYCLING",
        "attempt_1": {
            "heater": "LIQUID",
            "solver_outcome": "STAGNATION",
            "reason": "kernel_disagrees(U-HEAT, VAPOR)",
            "S3.T": "at least 430 K (spec measured 439.9999997)",
        },
        "attempt_2": {
            "heater": "VAPOR",
            "reason": "kernel_disagrees(U-HEAT, LIQUID)",
            "S3.T": "at most 290 K (spec measured 280.00002)",
        },
        "certificate": "none (not candidate_root)",
        "INFEASIBLE": False,
    }
    return ok, value, expected


# ------------------------------------------------------------------------------ A32–A35


def _a32(runs: Mapping[str, RecycleResult]) -> tuple[bool, Any, Any]:
    from openflowsheet.verify.failure import bundle_for

    restarts = [
        (label, event.reason, event.count) for label, run in runs.items() for event in run.restarts
    ]
    bad_restarts = [entry for entry in restarts if entry[1] != "stagnation" or entry[2] > 2]

    # region_on_merge on SYN-001 under anderson: the loop, nothing added.
    from openflowsheet.orchestrator.execution import build_execution_plan, declaration_identity
    from openflowsheet.orchestrator.trace import RecyclePolicy as Recycle
    from openflowsheet.orchestrator.trace import SolvePolicy

    flowsheet = plan_fixtures.Syn001Flowsheet(
        provider=plan_fixtures.Syn001Provider(),
        context=plan_fixtures.EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    spec, graph, row_units = plan_fixtures.structural_inputs(flowsheet)
    model_version, constants = declaration_identity(spec)
    declaration = plan_fixtures.trace_declaration(
        spec, row_units=row_units, model_version=model_version, constants_sha256=constants
    )
    report = plan_fixtures.analyse(
        spec, graph, row_units=row_units, model_version=model_version, constants_sha256=constants
    )
    plan = build_execution_plan(
        spec=spec,
        declaration=declaration,
        graph=graph,
        report=report,
        manifests={unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=SolvePolicy(
            policy_id="T02", residual_tolerances={}, scales={}, recycle=Recycle(method="anderson")
        ),
    )
    (converge,) = [step for step in plan.steps if step.kind == "converge"]
    merged = converge.region_on_merge
    assert merged is not None and merged.region is not None and merged.solve_plan is not None
    assert converge.solve_plan is not None
    loop_rows = {
        row for row in declaration.row_ids if declaration.rows[row].unit in set(converge.units)
    }
    region_rows = set(merged.region.row_ids) | set(merged.region.eliminated_rows)
    merge_region = {
        "same_model_version": merged.solve_plan.model_version == converge.solve_plan.model_version,
        "same_constants_sha256": merged.solve_plan.constants_sha256
        == converge.solve_plan.constants_sha256,
        "rows_equal_loop_rows": region_rows == loop_rows,
        "solved_and_eliminated_disjoint": not set(merged.region.row_ids)
        & set(merged.region.eliminated_rows),
        "specification_rows": list(merged.region.specification_rows),
    }

    # At most one merge: the stall merges once, fails, and nothing tries again.
    loop = merge_fixtures.Loop(lambda t: t + 1.0, lambda t: np.eye(3), [3.0] * 3, bounded=False)
    once, once_trace = _merge(loop, np.zeros(3))
    closures = [(event.attempt, event.outcome) for event in once_trace.of_kind("attempt_closed")]

    # MERGE-U on the manufactured stall.
    loop = merge_fixtures.Loop(lambda t: t + 1.0, lambda t: np.eye(3), [3.0] * 3, bounded=False)
    refused, refused_trace = _merge(loop, np.zeros(3), unsupported=("U-HEAT", "unavailable"))
    reason = 'merge_into_eo: unsupported(U-HEAT, "derivatives: unavailable")'
    bundle = bundle_for(refused, refused_trace, implicated=("U-HEAT",)).as_document()
    manufactured = {
        "outcome": refused.outcome,
        "merge_into_eo": refused.merge_into_eo,
        "message_carries_reason": reason in refused.message,
        "bundle_merge_into_eo": bundle["observations"].get("merge_into_eo"),
        "bundle_implicated": bundle["implicated_sources"],
        "residual_calls_total_vs_recycle": [loop.calls, refused.recycle.residual_calls],
    }

    # MERGE-U on SYN-001: the heater without EO derivatives, a stalled Anderson loop.
    flowsheet = executor_fixtures.Syn001Flowsheet(
        provider=executor_fixtures.Syn001Provider(),
        context=executor_fixtures.EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    doubled = executor_fixtures.heater_without_derivatives(
        {unit.unit_id: unit.manifest() for unit in flowsheet.units()}
    )
    run = executor_fixtures.nominal(executor_fixtures.policy(max_iterations_per_attempt=1), doubled)
    (step,) = [entry for entry in run.result.steps if entry.kind == "converge"]
    events = run.result.trace.events
    (closing,) = [event for event in events if event.kind == "region_closed"]
    recycle_closed = max(event.sequence for event in events if event.kind == "attempt_closed")
    after = {event.counters.residual_calls for event in events if event.sequence > recycle_closed}
    syn001 = {
        "outcome": run.result.outcome,
        "step_outcome": step.outcome,
        "merge_into_eo": step.merge_into_eo,
        "merge_unsupported": list(step.merge_unsupported or ()),
        "closing_message_carries_reason": 'unsupported(U-HEAT, "derivatives: unavailable")'
        in closing.message,
        "closing_document_merge_unsupported": closing.as_document().get("merge_unsupported"),
        "residual_calls_after_closure": sorted(after),
        "residual_calls_at_closure": events[recycle_closed].counters.residual_calls,
    }

    value = {
        "restarts_seen": len(restarts),
        "restarts_not_stagnation_or_count_above_2": bad_restarts,
        "region_on_merge": merge_region,
        "one_merge": {"closures": closures, "outcome": once.outcome},
        "MERGE-U manufactured": manufactured,
        "MERGE-U SYN-001": syn001,
    }
    ok = (
        len(restarts) > 0
        and not bad_restarts
        and merge_region
        == {
            "same_model_version": True,
            "same_constants_sha256": True,
            "rows_equal_loop_rows": True,
            "solved_and_eliminated_disjoint": True,
            "specification_rows": [],
        }
        and closures == [(0, "RECYCLE_STAGNATION"), (1, "LINEAR_SOLVE_FAILED")]
        and once.outcome == "LINEAR_SOLVE_FAILED"
        and refused.outcome == "RECYCLE_STAGNATION"
        and refused.merge_into_eo == "unsupported"
        and refused.merged is None
        and manufactured["message_carries_reason"]
        and manufactured["bundle_merge_into_eo"] == reason.removeprefix("merge_into_eo: ")
        and manufactured["bundle_implicated"] == ["U-HEAT"]
        and loop.calls == refused.recycle.residual_calls
        and step.outcome == run.result.outcome == "BUDGET_EXHAUSTED"
        and step.merge_into_eo == "unsupported"
        and syn001["merge_unsupported"] == ["U-HEAT", "unavailable"]
        and syn001["closing_message_carries_reason"]
        and syn001["closing_document_merge_unsupported"]
        == {"unit": "U-HEAT", "method": "unavailable"}
        and syn001["residual_calls_after_closure"] == [syn001["residual_calls_at_closure"]]
    )
    expected = {
        "restarts_not_stagnation_or_count_above_2": [],
        "region_on_merge": {
            "same_model_version": True,
            "same_constants_sha256": True,
            "rows_equal_loop_rows": True,
            "solved_and_eliminated_disjoint": True,
            "specification_rows": [],
        },
        "one_merge": {
            "closures": [[0, "RECYCLE_STAGNATION"], [1, "LINEAR_SOLVE_FAILED"]],
            "outcome": "LINEAR_SOLVE_FAILED",
        },
        "MERGE-U manufactured": {
            "outcome": "RECYCLE_STAGNATION",
            "merge_into_eo": "unsupported",
            "message_carries_reason": True,
            "bundle_merge_into_eo": reason.removeprefix("merge_into_eo: "),
            "bundle_implicated": ["U-HEAT"],
            "residual_calls_total_vs_recycle": "equal (none after the closure)",
        },
        "MERGE-U SYN-001": {
            "outcome": "BUDGET_EXHAUSTED",
            "merge_into_eo": "unsupported",
            "merge_unsupported": ["U-HEAT", "unavailable"],
            "closing_message_carries_reason": True,
            "closing_document_merge_unsupported": {"unit": "U-HEAT", "method": "unavailable"},
            "residual_calls_after_closure": "only the count at the closure",
        },
    }
    return ok, plain(value), expected


def _well_formed(run: Any, validator: Any) -> list[str]:
    """`test_t02_executor.well_formed`, returning what is wrong instead of asserting."""
    wrong: list[str] = []
    events = run.result.trace.events
    if [event.sequence for event in events] != list(range(len(events))):
        wrong.append("sequence is not dense and increasing")
    if not (events[0].kind == "plan_built" and events[0].step_count == len(run.plan.steps)):
        wrong.append("the first event is not plan_built with the step count")
    if not (events[-1].kind == "solve_closed" and events[-1].outcome == run.result.outcome):
        wrong.append("the last event is not solve_closed with the result's outcome")
    if len(run.result.trace.of_kind("plan_built")) != 1:
        wrong.append("plan_built is not unique")
    if len(run.result.trace.of_kind("solve_closed")) != 1:
        wrong.append("solve_closed is not unique")
    opened: int | None = None
    order: list[int] = []
    for event in events[1:-1]:
        if event.kind == "unit_evaluated":
            if opened is not None:
                wrong.append(f"unit_evaluated inside step {opened}")
            order.append(int(event.step_index))
        elif event.kind == "region_opened":
            if opened is not None:
                wrong.append(f"region_opened inside step {opened}")
            opened = event.step_index
            order.append(int(event.step_index))
        elif event.kind == "region_closed":
            if event.step_index != opened:
                wrong.append(f"region_closed for {event.step_index} while {opened} is open")
            opened = None
        elif opened is None or event.step_index != opened:
            wrong.append(f"{event.kind} at {event.sequence} outside its step")
    if opened is not None:
        wrong.append(f"step {opened} never closed")
    if order != [step.index for step in run.plan.steps][: len(order)]:
        wrong.append(f"steps bracketed in order {order}")
    if len(order) != len(run.result.steps):
        wrong.append("bracketed steps differ from the result's steps")
    for event in events:
        document = event.as_document()
        try:
            json.dumps(document, allow_nan=False)
        except ValueError:
            wrong.append(f"non-finite number in {event.kind} at {event.sequence}")
        errors = list(validator.iter_errors(document))
        if errors:
            wrong.append(f"{event.kind} at {event.sequence}: {errors[0].message}")
        if event.kind == "acceleration":
            accelerated = (event.depth_used or 0) >= 1
            if not (
                event.depth_used is not None
                and 0 <= event.depth_used <= min(5, 3)
                and event.columns_dropped_condition is not None
                and event.columns_dropped_coefficient is not None
                and event.beta_substitution in (1.0, 0.5)
                and (document["kappa_2"] is not None) == accelerated
                and (document["gamma_inf"] is not None) == accelerated
            ):
                wrong.append(f"acceleration at {event.sequence} is malformed")
        if event.kind == "restart" and not (
            event.restart_reason == "stagnation"
            and event.restart_count is not None
            and event.restart_count <= 2
        ):
            wrong.append(f"restart at {event.sequence} is malformed")
    return wrong


@contextlib.contextmanager
def _provider_calls() -> Iterator[dict[str, int]]:
    """Count every call the SYN-001 provider class receives while inside, through whatever
    wrapper or compiled block reached it — the independent count the trace's meter is compared
    with."""
    from openflowsheet.thermo.syn001 import Syn001Provider

    calls = {"flash": 0, "evaluate_phase": 0}
    saved = {name: getattr(Syn001Provider, name) for name in calls}

    def counted(name: str) -> Callable[..., Any]:
        original = saved[name]

        def call(self: Any, *arguments: Any, **keywords: Any) -> Any:
            calls[name] += 1
            return original(self, *arguments, **keywords)

        return call

    for name in calls:
        setattr(Syn001Provider, name, counted(name))
    try:
        yield calls
    finally:
        for name, original in saved.items():
            setattr(Syn001Provider, name, original)


def _a33() -> tuple[bool, Any, Any]:
    from jsonschema import Draft202012Validator

    from openflowsheet.application.binding import Binding, bind_revision

    validator = Draft202012Validator(
        json.loads((ROOT / "schemas" / "solve-event.schema.json").read_text(encoding="utf-8"))
    )
    runs: dict[str, Any] = {}
    for name, method in (("nominal auto", "auto"), ("nominal anderson", "anderson")):
        runs[name] = executor_fixtures.nominal(executor_fixtures.policy(method))
    runs["nominal eo"] = executor_fixtures.nominal(executor_fixtures.policy("eo"))
    runs["A02-355-liquid-guess"] = executor_fixtures.revision_run("SYN-001-A02-355-liquid-guess")
    runs["nominal anderson merge"] = executor_fixtures.nominal(
        executor_fixtures.policy("anderson", max_iterations_per_attempt=1)
    )
    flowsheet = executor_fixtures.Syn001Flowsheet(
        provider=executor_fixtures.Syn001Provider(),
        context=executor_fixtures.EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    runs["MERGE-U"] = executor_fixtures.nominal(
        executor_fixtures.policy(max_iterations_per_attempt=1),
        executor_fixtures.heater_without_derivatives(
            {unit.unit_id: unit.manifest() for unit in flowsheet.units()}
        ),
    )

    # A02-360 with the provider's own calls counted, so the trace's meter can be compared.
    binding = bind_revision(
        yaml.safe_load((CASES / "SYN-001-A02-360.yaml").read_text(encoding="utf-8"))
    )
    assert isinstance(binding, Binding)
    with _provider_calls() as received:
        runs["A02-360"] = executor_fixtures.run_flowsheet(
            binding.flowsheet,
            binding.spec,
            binding.graph,
            binding.row_units,
            executor_fixtures.policy(),
            specification_ids=binding.specification_ids,
            freed=binding.freed,
            promoted=binding.promoted,
        )
    events = runs["A02-360"].result.trace.events
    opened = next(event for event in events if event.kind == "region_opened")
    closed = next(event for event in events if event.kind == "region_closed")
    first_region_attempt = next(
        (
            event
            for event in events
            if event.kind == "attempt_opened" and event.signature and len(event.signature) == 2
        ),
        None,
    )
    pre_solve_closed = [
        event
        for event in events
        if event.kind == "attempt_closed" and event.signature and len(event.signature) == 1
    ]
    pre_solve_end = pre_solve_closed[-1].counters.property_calls if pre_solve_closed else None
    metering = {
        "provider_calls_received": sum(received.values()),
        "pre_solve_property_calls_on_trace": (
            pre_solve_end - opened.counters.property_calls if pre_solve_end is not None else None
        ),
        "region_property_calls_on_trace_after_the_pre_solve": (
            closed.counters.property_calls - pre_solve_end if pre_solve_end is not None else None
        ),
        "trace_property_calls_at_solve_closed": events[-1].counters.property_calls,
        "region_step_property_calls_on_trace": closed.counters.property_calls
        - opened.counters.property_calls,
        "property_calls_on_trace_during_region_newton": (
            closed.counters.property_calls - first_region_attempt.counters.property_calls
            if first_region_attempt is not None
            else None
        ),
    }

    per_run = {
        name: {"outcome": run.result.outcome, "malformed": _well_formed(run, validator)}
        for name, run in runs.items()
    }

    recycle_events: list[str] = []
    ref = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))
    for name in REC:
        for gamma in (0.0, 0.1):
            result, _ = recycle_fixtures.run_rec(ref, name, gamma)
            for event in result.accelerations:
                if not (
                    event.depth_used <= min(5, 3)
                    and event.beta_substitution in (1.0, 0.5)
                    and (event.kappa_2 is not None) == (event.depth_used >= 1)
                    and (event.gamma_inf is not None) == (event.depth_used >= 1)
                    and all(v is None or math.isfinite(v) for v in (event.kappa_2, event.gamma_inf))
                ):
                    recycle_events.append(f"{name} gamma={gamma} k={event.iteration}")

    value = {
        "runs": per_run,
        "recycle_acceleration_events_malformed": recycle_events,
        "A02-360 property metering": metering,
    }
    outcomes = {
        "nominal auto": "CONVERGED",
        "nominal anderson": "CONVERGED",
        "nominal eo": "CONVERGED",
        "A02-355-liquid-guess": "ACTIVE_SET_CYCLING",
        "nominal anderson merge": "CONVERGED",
        "MERGE-U": "BUDGET_EXHAUSTED",
        "A02-360": "CONVERGED",
    }
    ok = (
        all(
            per_run[name] == {"outcome": outcome, "malformed": []}
            for name, outcome in outcomes.items()
        )
        and not recycle_events
        and metering["provider_calls_received"] == metering["trace_property_calls_at_solve_closed"]
        and (metering["property_calls_on_trace_during_region_newton"] or 0) > 0
    )
    expected = {
        "runs": {name: {"outcome": outcome, "malformed": []} for name, outcome in outcomes.items()},
        "recycle_acceleration_events_malformed": [],
        "A02-360 property metering": {
            "provider_calls_received": "equal to the trace's property_calls at solve_closed",
            "property_calls_on_trace_during_region_newton": "above 0 (the region is metered)",
        },
    }
    return ok, value, expected


def _a34(identities: Path | None) -> dict[str, Any]:
    description = (
        "Reproducibility classes (A34 as amended by the T02 review, M4): `kappa_2` and "
        "`gamma_inf` carry no floor (`REGISTERED_FLOOR` 0 for both) and the comparability window "
        "`{kappa_2, gamma_inf} → (residual_inf_scaled, 1e-4)` is registered where ADR 0007 D2.6 "
        "says the policy lives; the ADR's D2.2 table carries both rows with the window; on every "
        "accelerated event of every registered case, on this platform, `kappa_2 ∉ [1e7, 1e9]` and "
        "`gamma_inf ∉ [1e3, 1e5]` (D2.4's decision margin) and the window holds at least one "
        "event; the T02 R0 document holds no float (`beta_substitution` as its exact decimal) and "
        "is identical twice on one machine; the float document holds only `kappa_2`, `gamma_inf` "
        "and their selector `residual_inf_scaled`. From the two CI artifacts: the R0 fields of "
        "§5.8 (`t02.recycle`, `t02.runs`) are equal across x86-64 and aarch64 and the floats "
        "agree under `openflowsheet.run.compare.differences` (which implements the window) — "
        "the CI job's own comparison. Without `--identities` the cross-platform half is not "
        "measured and the check is `unsupported`."
    )
    try:
        local, value = _a34_local()
    except Exception as error:  # noqa: BLE001
        return check(
            "T02.A34", description, "fail", {"error": f"{type(error).__name__}: {error}"}, ""
        )
    expected: dict[str, Any] = {
        "floors": {"kappa_2": 0.0, "gamma_inf": 0.0},
        "window": {
            "kappa_2": ["residual_inf_scaled", 1e-4],
            "gamma_inf": ["residual_inf_scaled", 1e-4],
        },
        "adr_0007_d2_2_rows_carry_the_window": True,
        "accelerated_events_near_threshold": [],
        "accelerated_events_inside_window": "at least 1",
        "r0_floats": [],
        "r0_same_twice": True,
        "float_document_names": ["gamma_inf", "kappa_2", "residual_inf_scaled"],
        "ci": {"platforms": 2, "t02_r0_equal": True, "float_differences": []},
    }
    if identities is None:
        value["ci"] = "not measured: no --identities directory given"
        return check("T02.A34", description, "unsupported" if local else "fail", value, expected)
    ci = _ci_comparison(identities)
    value["ci"] = {
        "platforms": len(ci["platforms"]),
        "t02_r0_equal": ci["t02_r0_equal"],
        "float_differences": ci["float_differences"],
    }
    return check(
        "T02.A34", description, verdict(local and value["ci"] == expected["ci"]), value, expected
    )


def _floats_in(value: Any, path: str = "") -> list[str]:
    if isinstance(value, dict):
        return [found for key, item in value.items() for found in _floats_in(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [found for item in value for found in _floats_in(item, path)]
    return [path] if isinstance(value, float) else []


def _a34_local() -> tuple[bool, dict[str, Any]]:
    from t02_identity import identity

    from openflowsheet.run.compare import COMPARABILITY_WINDOW, REGISTERED_FLOOR

    (adr,) = (ROOT / "docs" / "adr").glob("0007-*.md")
    table = adr.read_text(encoding="utf-8").split("**D2.2", 1)[1].split("**D2.3", 1)[0]
    rows_ok = "1e-4" in table
    for name in ("kappa_2", "gamma_inf"):
        rows = [line for line in table.splitlines() if line.startswith(f"| `{name}`")]
        rows_ok = (
            rows_ok
            and len(rows) == 1
            and ("0 (relative only)" in rows[0] or "comparability window" in rows[0])
        )
    first, second = identity(), identity()
    events = [
        event
        for group in first["floats"].values()
        for runs in group.values()
        for event in runs
        if event["kappa_2"] is not None
    ]
    near = [
        event
        for event in events
        if 1e7 <= event["kappa_2"] <= 1e9 or 1e3 <= event["gamma_inf"] <= 1e5
    ]
    inside = [event for event in events if event["residual_inf_scaled"] >= 1e-4]
    names = sorted({path.rsplit(".", 1)[-1] for path in _floats_in(first["floats"])})
    value: dict[str, Any] = {
        "floors": {
            "kappa_2": REGISTERED_FLOOR.get("kappa_2"),
            "gamma_inf": REGISTERED_FLOOR.get("gamma_inf"),
        },
        "window": {
            name: list(COMPARABILITY_WINDOW[name])
            for name in ("kappa_2", "gamma_inf")
            if name in COMPARABILITY_WINDOW
        },
        "adr_0007_d2_2_rows_carry_the_window": rows_ok,
        "accelerated_events": len(events),
        "accelerated_events_near_threshold": near[:5],
        "accelerated_events_inside_window": len(inside),
        "max_kappa_2": max((event["kappa_2"] for event in events), default=None),
        "max_gamma_inf": max((event["gamma_inf"] for event in events), default=None),
        "r0_floats": sorted(set(_floats_in(first["r0"])))[:10],
        "r0_same_twice": first == second,
        "float_document_names": names,
    }
    local = (
        value["floors"] == {"kappa_2": 0.0, "gamma_inf": 0.0}
        and value["window"]
        == {
            "kappa_2": ["residual_inf_scaled", 1e-4],
            "gamma_inf": ["residual_inf_scaled", 1e-4],
        }
        and rows_ok
        and bool(events)
        and not near
        and bool(inside)
        and not value["r0_floats"]
        and value["r0_same_twice"]
        and names == ["gamma_inf", "kappa_2", "residual_inf_scaled"]
    )
    return local, value


def _ci_comparison(directory: Path) -> dict[str, Any]:
    """The CI `identity` job's comparison, applied to its two downloaded artifacts."""
    from openflowsheet.run.compare import differences

    found = sorted(directory.rglob("identity.json"))
    documents = {path.parent.name: json.loads(path.read_text(encoding="utf-8")) for path in found}
    floats = {
        path.parent.name: json.loads(path.read_text(encoding="utf-8"))
        for path in directory.rglob("t02-floats.json")
    }
    names = sorted(documents)
    identity_differences: list[str] = []
    float_differences: list[str] = []
    if sorted(floats) != names:
        float_differences.append(f"t02-floats.json from {sorted(floats)}, identities from {names}")
    if len(names) < 2:
        identity_differences.append(f"two platforms needed; found {len(names)}")
    first = documents[names[0]] if names else {}
    for name in names[1:]:
        other = documents[name]
        identity_differences += [
            f"{key}: {names[0]} != {name}"
            for key in sorted(set(first) | set(other))
            if first.get(key) != other.get(key)
        ]
        if name in floats and names[0] in floats:
            float_differences += [
                f"{entry} ({names[0]} vs {name})"
                for entry in differences(
                    floats[name],
                    floats[names[0]],
                    "t02_floats",
                    policy_id="K04-numerical-policy-v1",
                )
            ]
    t02 = [document.get("t02", {}) for document in documents.values()]
    return {
        "platforms": names,
        "identity_differences": identity_differences,
        "t02_plans_equal": len(t02) >= 2
        and bool(t02[0].get("plans"))
        and all(item.get("plans") == t02[0].get("plans") for item in t02),
        "t02_r0_equal": len(t02) >= 2
        and bool(t02[0].get("recycle"))
        and all(
            item.get("recycle") == t02[0].get("recycle") and item.get("runs") == t02[0].get("runs")
            for item in t02
        ),
        "float_differences": float_differences,
    }


def _a35(gate: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.orchestrator.attempts import solve_with_attempts
    from openflowsheet.orchestrator.trace import SolvePolicy

    files = sorted(str(path.relative_to(ROOT)) for path in ROOT.glob("tests/test_k03_*.py"))
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *files],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    rerun = _pytest_counts(completed.stdout)

    # BND-02 through the tear path's attempt controller, with a frozen signature in force.
    import test_k03_newton as k03_seeds

    problem = k03_seeds.scalar_problem(lambda x: x + 1.0, lambda x: 1.0, lower=0.0)
    signature = (("U-FLASH", "TWO_PHASE"),)
    context = EvaluationContext(model_version="bnd-02", constants_sha256="0" * 64)
    trace = Trace()
    result = solve_with_attempts(
        problem_for=lambda attempt: problem,
        x0=[0.0],
        signature_of=lambda x: signature,
        policy=SolvePolicy(policy_id="BND-02", residual_tolerances={}, scales={}),
        trace=trace,
        evaluation_context=context,
        flowsheet_context=context,
        column_scales={"x": 1.0},
        row_scales={"r": 1.0},
        variable_ids=("x",),
    )
    closures = [event.outcome for event in trace.of_kind("attempt_closed")]
    value = {
        "gate": dict(gate),
        "k03_files": files,
        "k03_rerun_exit_code": completed.returncode,
        "k03_rerun_passed": rerun.get("passed", 0),
        "k03_rerun_failures": bool(
            rerun.get("failed", 0) + rerun.get("error", 0) + rerun.get("errors", 0)
        ),
        "BND-02": {
            "outcome": result.outcome,
            "iterations": result.iterations,
            "attempts": result.attempts,
            "attempt_closures": closures,
        },
    }
    ok = (
        gate["passed"]
        and gate["pytest_passed"] > 0
        and not gate["pytest_failed_or_errors"]
        and completed.returncode == 0
        and value["k03_rerun_passed"] > 0
        and not value["k03_rerun_failures"]
        and result.outcome == "BOUND_BLOCKED"
        and result.iterations == 0
        and result.attempts == 1
        and "PHASE_UPDATE_REQUIRED" not in closures
    )
    expected = {
        "gate": {"passed": True, "pytest_failed_or_errors": False},
        "k03_rerun_exit_code": 0,
        "k03_rerun_failures": False,
        "BND-02": {
            "outcome": "BOUND_BLOCKED",
            "iterations": 0,
            "attempts": 1,
            "attempt_closures": "no PHASE_UPDATE_REQUIRED",
        },
    }
    return ok, value, expected


# ------------------------------------------------------------------------------ limitations


def _limitations(ci_run: bool, identities: bool) -> list[str]:
    stated = [
        # Spec §12, restated item by item.
        "Spec §12: correctness of any solver is not established by the specification; it "
        "registers what a correct one must produce. This manifest measures the implementation "
        "against those registrations — numerical verification, not empirical validation.",
        "Spec §12: minimality of a tear set for a multi-edge feedback set is not claimed (the "
        "rule of §3.3 is greedy), nor the quality of a tear beyond dimension and boundary "
        "distance.",
        "Spec §12: behaviour finer than the registered basin margin is not established. REC-05's "
        "landing on S1 is asserted with a ±5 % start margin; a fourth fixed point at gamma = 0.02 "
        "exists and is not registered; the merge edge's landing on REC-05 (A14) is recorded, "
        "not asserted.",
        "Spec §12: no trajectory beyond the registered iterates is claimed. Anderson "
        "trajectories below a residual of 1e-6 are roundoff-dominated and deliberately not "
        "compared.",
        "Spec §12: appearance of a phase during an EO attempt, and the adjacent-regime restart, "
        "are not delivered; the two A02 liquid-guess cases are registered failures (A30, A31) "
        "whose success is T03's evidence.",
        "Spec §12: a lifted component at zero because the stream lacks the component, a provider "
        "whose K-values can vanish or diverge, a saturated lifted stream, and more than one "
        "region or loop per plan on a registered flowsheet are stated rules that no registered "
        "case exercises beyond the synthetic.",
        "Spec §12: the equation-level (BTF-block) region for A02 is stated as recoverable and "
        "not delivered.",
        "Spec §12: Wegstein, Aitken, trust regions and Krylov linear solves are not "
        "implemented; nothing measured here motivates them.",
        "Spec §12: nothing is empirically validated. Every case is synthetic.",
        "Spec §12: human numerical and process-modeling review are `pending`; no agent sets them.",
        "Spec §12: cost at size is not measured — 47 variables and tears of dimension 1 to 3 "
        "say nothing about a plant.",
        # The review, and what it closed.
        "Reviewed by Fable against the specification: docs/reviews/T02-review.md (commit "
        "76a0437, 4 must-fix and 8 should-fix findings; the same commit amended spec §5.8, §7.1, "
        "A26 and A34, ADR 0009 D3, ADR 0007 D2.2 and register R-026). Every M and S finding is "
        "closed: M4 in ec916a8, M1 and M3 in 4682451, M2 and NEST-1's plan in c73a9a1, S1, S3, "
        "S5 and S6 in 5e560ce, S2, S4, S7 and S8 in a24ca16, N9's evaluate step in 797484c. A "
        "Fable review is not the human numerical and process-modeling sign-off, which stays "
        "`pending`.",
        # Measured values that differ from the spec's prose, recorded for the reader.
        "A11: the spec's argument `0.65 · 0.95^200 = 2.3e-5` is undamped substitution. Under the "
        "registered policy the oscillation detector fires at iteration 3 (implementation and "
        "40-digit twin alike), plain steps are then damped by 0.5, and the `+0.95` mode governs at "
        "0.975: measured 4.874e-5, equal to that closed form to 2e-14 relative. The assertion's "
        "criterion (residual above the scaled tolerance at 200) holds either way; the spec's "
        "`substitution needs 535` also includes the damping.",
        "Measured counts that differ from the spec's *measured* figures, all inside their "
        "registered bounds: A05 (OFF-A) 6, 6, 1 iterations against 9, 9, 1 (bound 15); A06 "
        "(OFF-B) 8 iterations and 1 invalid trial against 10 and 12 (bound 40, at least 1); A29 "
        "SYN-001-A02-355 3 iterations against 4 (bound 6).",
        "A14: the merge edge on REC-05 with the tail lands on S1 — recorded, not asserted "
        "(spec §12).",
        # Review notes carried forward, not findings this package closes.
        "Review N8, single-loop assumptions: the plan builder reads T01's inner rows and "
        "variables as if one loop existed and eliminates every consistent certificate in every "
        "loop's SolvePlan. No registered flowsheet has two loops (spec §12); the day one does, "
        "those lines are to be revisited.",
        "Review N10, performance: `compile_problem` runs once per region step and once per "
        "merge, and the tear problem is rebuilt for the merge's reconstruction — three to four "
        "compiles per plan run where one would do. Immaterial at 47 variables; to be measured "
        "before the first large flowsheet.",
        "Review N9, handed to T03: a `role: free` specification without a `value` is silently "
        "not freed by the binding, so it surfaces as over-specification rather than §7.5's "
        "INITIALIZATION_FAILED naming the variable — typed, but the wrong object.",
        "A26 as amended: the over-specified unit is the one T01's canonical matching names "
        "(U-FLASH, measured), and the under-specified revision validates DRAFT (register R-022's "
        "extension) with STR-02 FAIL.",
        "The frozen evidence-manifest schema takes D/A requirement ids only, so this manifest's "
        "`requirements` names D01, D06 and A02; V13 and V15 are recorded in "
        "`docs/requirements.yaml`.",
    ]
    if not identities:
        stated.append(
            "The cross-platform halves of A02 and A34 were not measured by this run: no "
            "`--identities` directory was given, so both checks are `unsupported`, not `pass`."
        )
    if not ci_run:
        stated.append(
            "No CI run was named (`--ci-run`), so `commands` records the local gate only and "
            "A36's two-architecture half is `unsupported`."
        )
    return stated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("gate_stdout", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument(
        "--identities",
        type=Path,
        default=None,
        help="directory holding the two downloaded structural-identity-* CI artifacts",
    )
    parser.add_argument("--ci-run", default=None, help="the workflow run that compared platforms")
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    manifest = plain(
        build(arguments.commit, arguments.gate_stdout, arguments.identities, arguments.ci_run)
    )
    destination = arguments.out or (ROOT / "evidence" / "T02" / arguments.commit / "manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=1, allow_nan=False) + "\n", encoding="utf-8")

    counts = {
        name: sum(entry["result"] == name for entry in manifest["checks"])
        for name in ("pass", "fail", "unsupported", "not_applicable")
    }
    print(f"wrote {destination}")
    print(
        f"checks: {counts['pass']} pass, {counts['fail']} fail, "
        f"{counts['unsupported']} unsupported, {counts['not_applicable']} not applicable; "
        f"status {manifest['status']}"
    )
    for entry in manifest["checks"]:
        if entry["result"] != "pass":
            print(f"  {entry['id']}: {entry['result']}")
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
