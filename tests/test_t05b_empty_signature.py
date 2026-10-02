"""T05b W9.2: the screen at an empty signature (spec §7.8 (iii) as ruled 2026-09-25, Q-S4 (6);
R-058 amended).

"Every trial" includes an attempt whose frozen signature is empty — a v2 region with a
dormancy-form outlet, no lifted split and no active item. The Newton core used to compare a trial's
reported signature with the frozen one only when the frozen one was non-empty (`signature and …`),
so a trial that made a trigger exactly dormant there was accepted and the declared form's next
Jacobian had an empty `T_out` column (§7.7). Now:

- (a) the Newton core (and the PTC core, which runs the same attempts, §7.8 (v)) rejects a trial
  whose reported signature differs from an empty frozen one, `phase_update_required`, when the
  caller asks it to (`compare_empty`). The region asks for every v2 attempt in a region with a
  dormancy-form outlet — §7.8 (iii)'s scope; everywhere else `()` keeps meaning "no frozen
  signature" (K03's tear problem, driven directly, reports the flash's: comparing it there moved
  four K03 tests, measured at W9.2);
- (b) the region's trial evaluation reports the item at a trial whose pump inlet is exactly `+0.0`,
  whatever the frozen signature;
- end to end, DZ-6 from a start whose pump inlet flows now restarts at the screen's phase wall
  rather than at the closure's agreement check (§7.8 (iv) 1);
- (c) inertness is the protocol's (the `t05b` key, B07, `t05`, the identity minus both keys, T02's
  floats, every K03–T04 test), recorded in `docs/t05b-measurements.md`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import scipy.sparse as sp
from t05_w12_support import bind, connection_pin, planned_step
from t05b_support import (
    P_R,
    POLICY_V2,
    REF,
    Document,
    Product,
    Source,
    dz6,
    instance,
    registered_state,
    revision,
    solve_from_v2,
)

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.numerics.newton import Evaluation, Problem, another_signature, solve_newton
from openflowsheet.numerics.ptc import PtcProblem, solve_ptc
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.region import RegionResult, _attempt_screen, _region_problem
from openflowsheet.orchestrator.revision import instances_of, plan_revision
from openflowsheet.orchestrator.splits import dormancy_forms
from openflowsheet.orchestrator.trace import PtcPolicy, SolvePolicy, Trace
from openflowsheet.thermo import EvaluationContext

ITEM = (("X.outlet", "ZERO_FLOW"),)
POLICY = SolvePolicy(policy_id="T05b-W9-stub", residual_tolerances={}, scales={})


def _stub(wall: float, reported: Any = ITEM) -> Problem:
    """`r = 4 − x` from `x = 0` (a holdup balance filling to 4, so the PTC core can run it too);
    a trial past `wall` reports `reported`, every other one `()`."""

    def evaluate(x: np.ndarray) -> Evaluation:
        value = float(x[0])
        return Evaluation(
            status="ok", values=(4.0 - value,), signature=reported if value > wall else ()
        )

    return Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=evaluate,
        jacobian=lambda x: sp.csc_matrix(np.array([[-1.0]])),
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-12},
    )


def _rejections(trace: Trace) -> list[str | None]:
    return [e.rejection_reason for e in trace.of_kind("trial") if e.trial_status == "rejected"]


def test_the_predicate() -> None:
    """`another_signature(frozen, reported)`: the old predicate (`frozen and reported not in
    (None, frozen)`) by default; with `compare_empty`, an empty frozen signature is compared too.
    A trial reporting nothing is never rejected."""
    lifted = (("U-PHF", "LIQUID"),)
    for compare_empty in (False, True):
        assert another_signature(lifted, (("U-PHF", "VAPOR"),), compare_empty=compare_empty)
        assert another_signature(lifted, (*lifted, *ITEM), compare_empty=compare_empty)
        assert not another_signature(lifted, lifted, compare_empty=compare_empty)
        assert not another_signature(lifted, None, compare_empty=compare_empty)
        assert not another_signature((), (), compare_empty=compare_empty)
        assert not another_signature((), None, compare_empty=compare_empty)
    assert another_signature((), ITEM, compare_empty=True)
    assert not another_signature((), ITEM)


def test_a_the_newton_core_rejects_an_item_at_an_empty_frozen_signature() -> None:
    """Q-S4 (6) (a): frozen `()`, the full step lands at `x = 4` where the trial reports
    `((X.outlet, ZERO_FLOW),)`: `phase_update_required`, and the step halves back inside."""
    trace = Trace()
    result = solve_newton(_stub(1.5), [0.0], POLICY, trace=trace, signature=(), compare_empty=True)
    rejected = _rejections(trace)
    assert rejected and rejected[0] == "phase_update_required"
    assert result.x[0] <= 1.5, "no accepted iterate crossed into the item"
    # A trial that reports the empty signature is the attempt's own, and converges.
    trace = Trace()
    result = solve_newton(
        _stub(1.5, reported=()), [0.0], POLICY, trace=trace, signature=(), compare_empty=True
    )
    assert result.outcome == "CONVERGED" and _rejections(trace) == []
    # Without `compare_empty` (every caller but a v2 region with forms) nothing changes: the
    # full step is taken.
    trace = Trace()
    result = solve_newton(_stub(1.5), [0.0], POLICY, trace=trace, signature=())
    assert result.outcome == "CONVERGED" and _rejections(trace) == []


def test_a_the_ptc_core_rejects_an_item_at_an_empty_frozen_signature() -> None:
    """The same at the PTC core's trials (§7.8 (v): a v2 attempt under `eo_core = "ptc"`)."""
    problem = _stub(1.5)
    ptc = PtcProblem(problem, lambda x: sp.csc_matrix(np.array([[1.0]])), {"r": "holdup_balance"})
    trace = Trace()
    result, _ = solve_ptc(
        ptc, np.array([0.0]), PtcPolicy(), trace=trace, signature=(), compare_empty=True
    )
    assert "phase_update_required" in _rejections(trace)
    assert result.x[0] <= 1.5
    trace = Trace()
    solve_ptc(ptc, np.array([0.0]), PtcPolicy(), trace=trace, signature=())
    assert "phase_update_required" not in _rejections(trace)


# ------------------------------------------------------------ (b): the region's trial evaluation


def pump_flowing() -> Document:
    """Feed `(1,1,1)` 300 K `P_r` liquid → C1's `U-PUMP` (`P_out = 1.5e5 Pa`) → `S2` → sink: a
    v2 region with one dormancy-form outlet, no lifted split and, flowing, no item."""
    return revision(
        "W9-pump-flowing",
        [instance("SYN-001-UL-C1", "U-PUMP")],
        [Source("S1", "U-PUMP", "inlet", "liquid", (1.0, 1.0, 1.0), 300.0, P_R)],
        [],
        [Product("S2", ("U-PUMP", "outlet"), "liquid")],
        [connection_pin("SPEC-pump-P", "S2", "state.P", 1.5e5)],
    )


def test_b_the_region_reports_the_item_at_a_dormant_trial_whatever_the_frozen_signature() -> None:
    """Q-S4 (6) (b): the flowing pump solves in one attempt whose signature is `()`; that
    attempt's trial evaluation, at a trial whose pump inlet `S1.n` is exactly `+0.0`, reports
    `((U-PUMP.outlet, ZERO_FLOW),)` — which the Newton core now rejects — and at a flowing trial
    reports `()`."""
    binding = bind(pump_flowing())
    flowsheet, spec = binding.flowsheet, binding.spec
    plan, _ = plan_revision(binding, POLICY_V2)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=flowsheet, spec=spec, policy=POLICY_V2)
    assert run.outcome == "CONVERGED", run.message
    (step,) = run.steps
    assert isinstance(step.detail, RegionResult)
    assert [a.signature for a in step.detail.attempts] == [()]
    region = planned_step(binding, POLICY_V2).region
    assert region is not None and region.signature_units == ()
    state = run.state
    assert state is not None
    forms = dormancy_forms(instances_of(flowsheet), flowsheet.units(), flowsheet.components)
    compiled = compile_problem(spec)
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
        phase_signature=None,
    )
    screen = _attempt_screen(
        splits=(),
        regimes={},
        provider=flowsheet.provider,
        context=context,
        epsilon=POLICY_V2.admissibility_epsilon,
        ph_units=frozenset(),
        v2=True,
        dormancy=forms,
    )
    free = region.variable_ids
    opening = np.array([state[name] for name in free])
    problem = _region_problem(
        compiled,
        context,
        spec,
        Scaling.from_spec(spec),
        state,
        free,
        region.row_ids,
        screen,
        opening,
    )

    def trial(**changes: float) -> Evaluation:
        values = dict(zip(free, opening.tolist(), strict=True))
        values.update(changes)
        return problem.residual(np.array([values[name] for name in free]))

    dormant = trial(**{f"S1.n.{c}": 0.0 for c in "ABC"})
    assert dormant.status == "ok", dormant.message
    assert dormant.signature == (("U-PUMP.outlet", "ZERO_FLOW"),)
    # What the region's Newton call (`compare_empty=bool(dormancy)`, true here) then rejects.
    assert another_signature((), dormant.signature, compare_empty=True)
    flowing = trial(**{"S1.n.A": 0.5})
    assert flowing.status == "ok" and flowing.signature == ()


# ------------------------------------------------------------------ end to end: DZ-6, flowing start


def test_dz6_from_a_flowing_start_restarts_at_the_screens_wall() -> None:
    """DZ-6 (dormant feed) from its root with the pump's inlet and outlet at `(1,1,1)` mol/s:
    attempt 0 opens with signature `()`; Newton's step lands `S1.n` exactly on `+0.0`, the trial
    reports the item and is phase-rejected, and the attempt closes at the phase wall; attempt 1
    runs the form and converges at the registered root (`S2.T == 330.0`, the label). Before W9.2
    the trial was accepted and only the closure's agreement check restarted it —
    `inadmissible(S2, dormant)` (*measured*). Attempt counts and iterations are *regression*."""
    root = registered_state(REF["dormant_non_lifted_cases"]["DZ-6"]["root"])
    start = dict(root)
    for component in "ABC":
        start[f"S1.n.{component}"] = start[f"S2.n.{component}"] = 1.0
    trace = Trace()
    result = solve_from_v2(bind(dz6()), start, trace=trace)
    assert result.outcome == "CONVERGED", result.message
    item = (("U-PUMP.outlet", "ZERO_FLOW"),)
    wall = "phase_wall(patience, U-PUMP.outlet:LIQUID->ZERO_FLOW)"
    assert [(a.signature, a.iterations, a.reason) for a in result.attempts] == [
        ((), 2, wall),
        (item, 0, ""),
    ]
    assert [e.message for e in trace.events if e.kind == "attempt_opened"] == [
        "initial",
        f"phase_update({wall})",
    ]
    state = result.state
    assert state["S2.T"] == 330.0
    assert all(state[f"{s}.n.{c}"] == 0.0 for s in ("S1", "S2") for c in "ABC")
