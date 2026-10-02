"""T05b review S3 (`docs/reviews/T05b-review.md` §3 S3, probes §8): three paths no test drove end
to end.

- **P2 — a lifted split leaving and entering `ZERO_FLOW` at a restart, with its F2 record.** C1's
  PH flash (`U-PHF`, duty `Q`) → `S2` vapour → C1's valve (`U-VLV`, `S4.P = 0.9e5 Pa`) → `S4`;
  `S3` liquid → sink; feed `(1,1,1)` 300 K `P_r` liquid. Solved under `T05b-v2` from the
  traversal start of the other duty: `Q = 0 → 30 kW` leaves `ZERO_FLOW` by the TP flash at the
  valve's feed, recorded `fallback(U-VLV, tp)` on that attempt's `attempt_opened` (spec §7.4, F2
  row of §6); `Q = 30 kW → 0` enters it by `phase_wall(patience, U-VLV:VAPOR->ZERO_FLOW)` with
  no `fallback(…)` item. A heater-style split's feed is its own outlet stream `S4.n`, which no
  opening writes — so this is not review M1's path (a products-style split downstream), which is
  left to M1's own regression.
- **P3 — a label row under the PTC core (§7.8 (v)).** DZ-1 (lifted valve, `ZERO_FLOW` form),
  DZ-6 (pump) and DZ-9 (mixer) (dormancy forms), each from its traversal start with the dormant
  outlet's temperature (the label's `T_out`) moved 5 K off, under `eo_core = "ptc"`,
  `eo_recovery = "none"`: the label row is met exactly and the root is the registered one.
- **Edge 3 (T04 §5) under `T05b-v2`.** HOM-01…HOM-05 (`test_t04_edge3`), the cases where edge 3
  is reached, run the whole plan under the v2 literal: the contract's items, the λ-path and the
  end state are v1's exactly (v1's are T04's registered ones, `test_a04_a08`). No signature there
  carries a `ZERO_FLOW` regime or item, and a revision flowsheet's region (P2's) has no
  continuation parameter, so edge 3 with a `ZERO_FLOW` signature is not reached by these cases:
  that remains unexercised (review §9), stated here rather than implied.

Expectations: P2's `Q = 30 kW` root is PHF-1's (`ref…DZ-12.root`: the same feed and duty), and
SYN-001's vapour is an ideal gas, so the isenthalpic valve keeps `S4.T = S2.T` and `S4.n = S2.n`;
its `Q = 0` root is the subcooled feed through an adiabatic, isobaric flash, `S2.T = 300 K`, and
the label `S4.T = S2.T`. The attempt structures, records and the `T05-W13` outcomes are
*regression* values (measured 2026-09-25 at `c2cc22f`), pinned beside their assertion.
"""

from __future__ import annotations

import dataclasses
from functools import cache
from typing import Any

import pytest
from t05_w12_support import bind, connection_pin, duty_pin, planned_step
from t05b_support import (
    P_R,
    POLICY_V2,
    REF,
    Document,
    Link,
    Product,
    Source,
    dz1,
    dz6,
    dz9,
    error,
    instance,
    judged_where,
    registered_state,
    revision,
    solve_from_v2,
)
from test_t04_edge3 import (
    HOM,
    HOMOTOPY_CASES,
    case_document,
    case_policy,
    full_run,
    plan_run,
    region_step,
)
from test_t05_coupled import POLICY as POLICY_V1

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.orchestrator import revision as revision_module
from openflowsheet.orchestrator.homotopy import continuation_parameter
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.revision import initial_state
from openflowsheet.orchestrator.splits import (
    closure_types,
    dormancy_forms,
    lifted_splits,
    zero_flow_forms,
)
from openflowsheet.orchestrator.trace import GlobalizationPolicy, SolvePolicy, Trace
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision

#: Spec §13's EO allowances (T02 §6.4), as `ref.tolerances.coupled_allowances` states them.
ALLOWANCE: dict[str, float] = {
    kind: float(value) for kind, value in REF["tolerances"]["coupled_allowances"].items()
}
#: `τ_flow` (spec §13), a mole row's own tolerance.
TAU_FLOW = float(REF["tolerances"]["molar_flow"])
#: PHF-1 at `Q = 30 000 W` from feed `(1,1,1)` 300 K `P_r`: DZ-12's registered `S2`.
PHF1 = REF["dormant_non_lifted_cases"]["DZ-12"]["root"]


def _allowance(column: str) -> float:
    kind = column.rsplit(".", 1)[-1]
    return {"T": ALLOWANCE["T"], "P": ALLOWANCE["P"], "Q": ALLOWANCE["duty"]}.get(
        kind, ALLOWANCE["flow"]
    )


# ------------------------------------------- P2: a lifted split leaving / entering ZERO_FLOW


def p2(duty: float) -> Document:
    """Feed `(1,1,1)` 300 K `P_r` liquid → `U-PHF` (`Q = duty`) → `S2` vap → `U-VLV`
    (`S4.P = 0.9e5 Pa`) → `S4` → sink; `S3` liq → sink."""
    return revision(
        f"S3-P2-{duty:g}",
        [instance("SYN-001-UL-C1", "U-PHF"), instance("SYN-001-UL-C1", "U-VLV")],
        [Source("S1", "U-PHF", "inlet", "liquid", (1.0, 1.0, 1.0), 300.0, P_R)],
        [Link("S2", ("U-PHF", "vapor"), ("U-VLV", "inlet"), "vapor")],
        [
            Product("S3", ("U-PHF", "liquid"), "liquid"),
            Product("S4", ("U-VLV", "outlet"), "vapor_liquid"),
        ],
        [
            duty_pin("SPEC-phf-Q", "U-PHF", duty),
            connection_pin("SPEC-valve-P", "S4", "state.P", 0.9e5),
        ],
    )


@dataclasses.dataclass(frozen=True)
class P2Run:
    result: RegionResult
    opened: list[str]
    certificate: SolutionCertificate | None


@cache
def _p2(start_duty: float, target_duty: float, contract: str = "v2") -> P2Run:
    """P2's `target_duty` revision solved from the traversal start of its `start_duty` one."""
    source = bind(p2(start_duty))
    start = initial_state(source.flowsheet, source.spec.variable_ids)
    assert isinstance(start, dict), start
    policy = POLICY_V2 if contract == "v2" else POLICY_V1
    document = p2(target_duty)
    binding = bind(document)
    trace = Trace()
    result = solve_from_v2(binding, start, policy, trace=trace)
    opened = [event.message for event in trace.events if event.kind == "attempt_opened"]
    certificate = None
    if result.outcome == "CONVERGED":
        step = planned_step(binding, policy)
        certificate = verify_revision(
            binding, document, result, state=dict(result.state), solve_plan=step.solve_plan
        )
    return P2Run(result, opened, certificate)


def _attempts(result: RegionResult) -> list[tuple[Any, ...]]:
    return [
        (a.outcome, a.solver_outcome, a.iterations, [list(e) for e in a.signature], a.reason)
        for a in result.attempts
    ]


LEAVING = "phase_update(phase_wall(stall, U-VLV:ZERO_FLOW->VAPOR); fallback(U-VLV, tp))"
ENTERING = "phase_update(phase_wall(patience, U-VLV:VAPOR->ZERO_FLOW))"


def test_s3_p2_leaving_zero_flow_at_a_restart_records_the_tp_fallback() -> None:
    """`Q = 0 → 30 kW` under v2: attempt 0 opens with the valve's feed dormant (`ZERO_FLOW`);
    the flash's restart to `TWO_PHASE` makes `S2` flow; the valve's form stalls and the contract
    leaves `ZERO_FLOW` by the TP flash at the feed, recorded `fallback(U-VLV, tp)` on the
    `attempt_opened` — `Conversion.fallbacks` from `_LiftedOps` through `restart_message`."""
    run = _p2(0.0, 30_000.0)
    result = run.result
    assert result.outcome == "CONVERGED", result.message
    # Regression values (measured 2026-09-25, c2cc22f).
    assert _attempts(result) == [
        (
            "PHASE_UPDATE_REQUIRED",
            "PHASE_UPDATE_REQUIRED",
            2,
            [["U-PHF", "LIQUID"], ["U-VLV", "ZERO_FLOW"]],
            "phase_wall(patience, U-PHF:LIQUID->TWO_PHASE)",
        ),
        (
            "PHASE_UPDATE_REQUIRED",
            "LINE_SEARCH_FAILED",
            0,
            [["U-PHF", "TWO_PHASE"], ["U-VLV", "ZERO_FLOW"]],
            "phase_wall(stall, U-VLV:ZERO_FLOW->VAPOR)",
        ),
        ("CONVERGED", "CONVERGED", 0, [["U-PHF", "TWO_PHASE"], ["U-VLV", "VAPOR"]], ""),
    ]
    assert run.opened == [
        "initial",
        "phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE))",
        LEAVING,
    ]
    assert [p["signature"] for p in result.branch_provenance] == [
        list(map(list, a.signature)) for a in result.attempts
    ]


def test_s3_p2_leaving_zero_flow_the_root_and_certificate() -> None:
    """The root is PHF-1's (`ref…DZ-12.root`'s `S2`), carried through the ideal-gas isenthalpic
    valve unchanged in `T` and `n`; `VERIFIED` at the projection with no label check (the valve
    flows)."""
    run = _p2(0.0, 30_000.0)
    state = run.result.state
    for column in ("S2.n.A", "S2.n.B", "S2.n.C", "S2.T", "U-PHF.Q"):
        assert error(state[column], PHF1[column]) <= _allowance(column), column
    for component in "ABC":
        # At the allowance, as `S4.T`: bitwise equality with `S2.n` held until W9.4, whose opening
        # (both of `U-PHF`'s products at the closure's `T`, Q-S11 (a)) moved `S4.n.B` by one ulp.
        assert error(state[f"S4.n.{component}"], PHF1[f"S2.n.{component}"]) <= ALLOWANCE["flow"]
        # The copy itself, at the valve's mole row's own tolerance (re-review N-W3).
        assert abs(state[f"S4.n.{component}"] - state[f"S2.n.{component}"]) <= TAU_FLOW
    assert error(state["S4.T"], PHF1["S2.T"]) <= ALLOWANCE["T"]
    assert state["S4.P"] == 0.9e5
    certificate = run.certificate
    assert certificate is not None
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result in ("fail", "unsupported")
    ]
    judged_where(certificate, "projection")
    assert not any("zero-flow-label" in c.id for c in certificate.checks)
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    assert certificate.regularity.dimension == 31  # regression value


def test_s3_p2_entering_zero_flow_at_a_restart() -> None:
    """`Q = 30 kW → 0` under v2: the flash's vapour disappears (`BOUND_BLOCKED` on `S2.n.C`),
    the restart runs the valve `VAPOR` on a dormant feed until the wall's patience moves it to
    `ZERO_FLOW` — no `fallback(…)` item on entering (spec §7.4) — and the last attempt runs the
    form; the root is the subcooled feed at 300 K with the label met exactly; `VERIFIED`."""
    run = _p2(30_000.0, 0.0)
    result = run.result
    assert result.outcome == "CONVERGED", result.message
    # Regression values (measured 2026-09-25, c2cc22f).
    assert _attempts(result) == [
        (
            "PHASE_UPDATE_REQUIRED",
            "BOUND_BLOCKED",
            1,
            [["U-PHF", "TWO_PHASE"], ["U-VLV", "VAPOR"]],
            "phase_disappeared(U-PHF, vapor, S2.n.C)",
        ),
        (
            "PHASE_UPDATE_REQUIRED",
            "PHASE_UPDATE_REQUIRED",
            2,
            [["U-PHF", "LIQUID"], ["U-VLV", "VAPOR"]],
            "phase_wall(patience, U-VLV:VAPOR->ZERO_FLOW)",
        ),
        ("CONVERGED", "CONVERGED", 1, [["U-PHF", "LIQUID"], ["U-VLV", "ZERO_FLOW"]], ""),
    ]
    assert run.opened == [
        "initial",
        "phase_update(phase_disappeared(U-PHF, vapor, S2.n.C))",
        ENTERING,
    ]
    assert not any("fallback(" in message for message in run.opened)
    state = result.state
    flows = [f"{stream}.n.{c}" for stream in ("S2", "S4") for c in "ABC"]
    assert all(state[column] == 0.0 for column in flows)
    for component in "ABC":
        assert abs(state[f"S3.n.{component}"] - 1.0) <= ALLOWANCE["flow"]
    assert abs(state["S2.T"] - 300.0) <= ALLOWANCE["T"]
    assert state["S4.T"] == state["S2.T"]  # the label row `S4.T − S2.T`, met exactly
    certificate = run.certificate
    assert certificate is not None
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result in ("fail", "unsupported")
    ]
    judged_where(certificate, "projection")
    by_id = {c.id: c for c in certificate.checks}
    assert by_id["residual.U-VLV:zero-flow-label"].result == "pass"
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    assert certificate.regularity.dimension == 23  # regression value


def test_s3_p2_under_v1() -> None:
    """The same two runs under `T05-W13` (regression values, measured 2026-09-25, c2cc22f):
    leaving, v1 opens the valve `TWO_PHASE` on a dormant feed and its first Jacobian is singular;
    entering, v1 converges in the declared form with the valve outlet 48.3 K off its label, which
    the verifier's label check (applied under both literals) fails — never `VERIFIED`."""
    leaving = _p2(0.0, 30_000.0, "v1").result
    assert leaving.outcome == "LINEAR_SOLVE_FAILED"
    assert _attempts(leaving) == [
        (
            "LINEAR_SOLVE_FAILED",
            "LINEAR_SOLVE_FAILED",
            0,
            [["U-PHF", "LIQUID"], ["U-VLV", "TWO_PHASE"]],
            "",
        )
    ]
    entering = _p2(30_000.0, 0.0, "v1")
    assert entering.result.outcome == "CONVERGED"
    assert [list(map(list, a.signature)) for a in entering.result.attempts][-1] == [
        ["U-PHF", "LIQUID"],
        ["U-VLV", "VAPOR"],
    ]
    certificate = entering.certificate
    assert certificate is not None
    assert certificate.verification_status == "FAILED"
    judged_where(certificate, "final_state", "residual_not_passed")
    failing = {c.id: c for c in certificate.checks if c.result == "fail"}
    assert list(failing) == ["residual.U-VLV:zero-flow-label"]
    label = failing["residual.U-VLV:zero-flow-label"]
    assert label.value == pytest.approx(48.3138, abs=1e-3)


# ------------------------------------------------------------ P3: a label row under PTC


PTC = dataclasses.replace(
    POLICY_V2, globalization=GlobalizationPolicy(eo_core="ptc", eo_recovery="none")
)
#: Each case, its registered root, and the zero-flow form's registered dimension.
LABEL_CASES = {
    "DZ-1": (dz1, REF["dormant_cases"]["DZ-1"]),
    "DZ-6": (dz6, REF["dormant_non_lifted_cases"]["DZ-6"]),
    "DZ-9": (dz9, REF["dormant_non_lifted_cases"]["DZ-9"]),
}


def _label(document: Document) -> tuple[str, str, str]:
    """The case's one label row `(row id, T_out, T_label)`, lifted or dormancy form."""
    flowsheet = bind(document).flowsheet
    instances = revision_module.instances_of(flowsheet)
    splits = lifted_splits(instances, flowsheet.components)
    types = closure_types(flowsheet.units())
    forms = [
        *zero_flow_forms(instances, splits, types, flowsheet.components).values(),
        *dormancy_forms(instances, flowsheet.units(), flowsheet.components),
    ]
    (label,) = [form.label for form in forms if form.label is not None]
    return label


@pytest.mark.parametrize("case", LABEL_CASES)
def test_s3_p3_a_label_row_under_the_ptc_core(case: str) -> None:
    """From the traversal start with the dormant outlet's `T_out` raised 5 K off its label, the
    PTC core (`eo_core = "ptc"`) runs the zero-flow form: `CONVERGED` in one iteration, the label
    met exactly, the root the registered one, `VERIFIED` at the zero-flow form's dimension."""
    build, registered = LABEL_CASES[case]
    document = build()
    binding = bind(document)
    row, t_out, t_label = _label(document)
    labels = [registered["label"]["row"]] if case == "DZ-1" else list(registered["label_rows"])
    assert labels == [row]
    start = initial_state(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(start, dict), start
    assert start[t_out] == start[t_label]
    start[t_out] += 5.0
    result = solve_from_v2(binding, start, PTC)
    assert result.outcome == "CONVERGED", result.message
    ((attempt, provenance),) = zip(result.attempts, result.branch_provenance, strict=True)
    assert provenance["core"] == "ptc"
    assert attempt.iterations == 1  # regression value
    assert [e[1] for e in attempt.signature] == ["ZERO_FLOW"]
    assert result.state[t_out] == result.state[t_label]
    assert {c: result.state[c] for c in registered["root"]} == registered_state(registered["root"])
    certificate = verify_revision(
        binding,
        document,
        result,
        state=dict(result.state),
        solve_plan=planned_step(binding, PTC).solve_plan,
    )
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result in ("fail", "unsupported")
    ]
    judged_where(certificate, "projection")
    label = {c.id: c for c in certificate.checks}[f"residual.{row}"]
    assert (label.result, label.value) == ("pass", 0.0)
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    assert certificate.regularity.dimension == registered["zero_flow_form"]["dimension"]


# ------------------------------------------------------------ edge 3 under T05b-v2


def _v2(case_id: str) -> SolvePolicy:
    """`case_policy(case_id)` under the v2 literal, built from `POLICY_V2` (B06: v2 is constructed
    once, in `t05b_support`); every other field is the case's."""
    overrides = HOMOTOPY_CASES[case_id]["policy_overrides"] or {}
    policy = dataclasses.replace(POLICY_V2, policy_id=f"T04-{case_id}", **overrides)
    v1 = case_policy(case_id)
    differing = [
        field.name
        for field in dataclasses.fields(SolvePolicy)
        if getattr(policy, field.name) != getattr(v1, field.name)
    ]
    assert differing == ["phase_contract"], differing
    return policy


def _edge3_record(run: Any) -> dict[str, Any]:
    result = run.result
    step = region_step(result)
    homotopy = step.detail.homotopy
    return {
        "outcome": result.outcome,
        "edge3": (step.eo_recovery, step.eo_recovery_unsupported),
        "failed": (step.recovered_from.outcome, step.recovered_from.message),
        "items": list(step.detail.branch_provenance),
        "trials": [
            (
                str(t.lambda_value),
                str(t.delta_lambda),
                t.corrector.result.outcome,
                t.corrector.result.iterations,
                t.accepted,
                [float(x) for x in t.corrector.result.x],
            )
            for t in homotopy.trials
        ],
        "lambda_reached": str(homotopy.lambda_reached),
        "state": dict(result.state) if result.state is not None else None,
        "opened": [
            e.message for e in result.trace.of_kind("attempt_opened") if e.step_index == step.index
        ],
    }


@pytest.mark.parametrize("case_id", HOM)
def test_s3_edge3_under_v2_is_v1s_registered_path(case_id: str) -> None:
    """Edge 3 under `T05b-v2`: the failed contract, its items, the recovery's item, every λ trial
    (its corrector's outcome, iterations and end point) and the step's state are v1's exactly —
    and v1's are T04's registered path (`test_t04_edge3.test_a04_a08`). No signature carries a
    `ZERO_FLOW` regime or item: SYN-001's feed flows and its A02 region has no dormancy form."""
    v2 = _edge3_record(plan_run(case_document(case_id), _v2(case_id)))
    v1 = _edge3_record(full_run(case_id))
    assert v2 == v1
    assert v2["edge3"] == ("taken", None)
    for item in v2["items"]:
        assert all(regime != "ZERO_FLOW" for _, regime in item["signature"])


def test_s3_edge3_a_revision_region_has_no_continuation_parameter() -> None:
    """Why edge 3 with a `ZERO_FLOW` signature is not reached here: T04 §4.1's parameter is a
    promoted specification row, and a revision flowsheet's region (P2's) has none, so edge 3 on it
    records `unsupported(no_continuation_parameter)` (§5.2) instead of running."""
    binding = bind(p2(30_000.0))
    region = planned_step(binding, POLICY_V2).region
    assert region is not None
    assert (
        continuation_parameter(
            specification_rows=region.specification_rows,
            target_variables=region.target_variables,
            spec=binding.spec,
            structural_pattern=compile_problem(binding.spec).structural_pattern(),
        )
        is None
    )
