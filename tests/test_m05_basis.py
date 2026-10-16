"""M05 WO-4: `M05-basis-v1` (design note §6.6, §16.4, §16.5; R-264, R-277) — the affine Taylor
basis for property EFs and for external links.

§16.4's acceptance for the property basis: at w₀ the basis value equals the block's value
bitwise; its `differentiate` gradient equals the block Jacobian within 1e-15 relative; every basis
variable belongs to the clone; TR-E1 with an affine basis on `bb` converges to native within 1e-6
(probe P5's analogue). For a link: the same at w₀ against the truth, and an FD truth's basis
gradient is n_in = 7 `basis_fd_point` requests, memo hits after the gradient check at w₀.

Marked `nlp`: the projection and TRF need Pyomo. Nothing at module level imports it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from m05_support import LinkToyTruth, link_toy_projection, tr_e1_projection

from openflowsheet.studies.trust_region.holders import BASIS_FD_POINT, FDCHECK_POINT
from openflowsheet.studies.trust_region.truths import (
    ForwardDifference,
    gradient_check,
    in_process_meta,
)

pytestmark = pytest.mark.nlp


def _clone_calls(model: Any) -> list[tuple[str, Any]]:
    """Every `ExternalFunction` call in `model`'s active constraints, with its EF's name."""
    import pyomo.environ as pyo
    from pyomo.core.expr.numeric_expr import ExternalFunctionExpression

    found = []
    for constraint in model.component_data_objects(pyo.Constraint, active=True):
        stack = [constraint.body]
        while stack:
            node = stack.pop()
            if isinstance(node, ExternalFunctionExpression):
                found.append((node._fcn.local_name, node))
            elif getattr(node, "is_expression_type", lambda: False)():
                stack.extend(node.args)
    return found


def _check_affine_at_start(
    projection: Any,
    basis: Mapping[str, Any],
    expected: Mapping[str, tuple[float, Sequence[float], float]],
) -> float:
    """Each EF's basis on the clone's arguments: b(w₀)·s equals `value` bitwise and the
    `differentiate` gradient times s equals `gradient` within 1e-15 relative; every variable of
    the basis is the clone's. Returns the worst relative gradient error."""
    import pyomo.environ as pyo
    from pyomo.core.expr.calculus.derivatives import Modes, differentiate
    from pyomo.core.expr.visitor import identify_variables

    clone = projection.model.clone()
    clone_variables = {id(v) for v in clone.component_data_objects(pyo.Var)}
    worst = 0.0
    calls = _clone_calls(clone)
    assert {name for name, _ in calls} == set(expected) == set(basis)
    for name, call in calls:
        value, gradient, scale = expected[name]
        args = list(call.args[: len(gradient)])
        expression = basis[name].build(args)
        assert {id(v) for v in identify_variables(expression)} <= clone_variables
        assert pyo.value(expression) * scale == value
        derivative = differentiate(expression, wrt_list=args, mode=Modes.reverse_symbolic)
        for entry, exact in zip(derivative, gradient, strict=True):
            got = pyo.value(entry) * scale
            error = abs(got - exact) / max(abs(exact), 1e-300) if exact else abs(got)
            worst = max(worst, error)
    assert worst <= 1e-15
    return worst


def test_the_property_basis_is_the_blocks_taylor_model_at_the_start() -> None:
    from openflowsheet.studies.trust_region.basis import affine_block_basis

    projection = tr_e1_projection()
    basis = affine_block_basis(projection)
    assert {item.kind for item in basis.values()} == {"affine_taylor"}
    (entry,) = projection.source_map["block_outputs"]
    block = projection.spec.blocks[0]
    w0 = [float(projection.model.x[i].value) for i in projection.holder_inputs[0]]
    gradient = [0.0, 0.0]
    for _, column, value in block.jacobian(w0):
        gradient[column] += value
    expected = {entry["ef"]: (block.values(w0)[0], gradient, entry["output_scale"])}
    _check_affine_at_start(projection, basis, expected)
    assert all(holder.ledger == () for holder in projection.holders)  # blocks called directly


def _tr_e1_affine_and_native() -> tuple[Any, Any]:
    from test_m05_trf import native

    from openflowsheet.studies.trust_region.basis import affine_block_basis
    from openflowsheet.studies.trust_region.trf import run_trf
    from openflowsheet.studies.trust_region.trf_state import TRSP_SOLVER_ALIAS

    projection = tr_e1_projection()
    result = run_trf(
        projection, {"solver": TRSP_SOLVER_ALIAS}, basis=affine_block_basis(projection)
    )
    assert result.outcome == "TRF_CONVERGED", result.error
    assert result.basis == {name: "affine_taylor" for name in projection.ef_names.values()}
    return result, native()[0]


def test_tr_e1_with_the_affine_basis_reaches_natives_objective() -> None:
    """Measured beside §16.4's criterion (next test): with the affine basis TRF takes 7 iterations
    (native 5) and stops at a step of 6.9e-7; its objective is native's within 1e-10 relative and
    θ ≤ 1e-10."""
    import pyomo.environ as pyo

    result, model = _tr_e1_affine_and_native()
    final = result.final
    assert final is not None and final.theta <= 1e-10
    assert abs(final.objective - pyo.value(model.obj)) <= 1e-10 * abs(pyo.value(model.obj))


def test_tr_e1_with_the_affine_basis_converges_to_native_within_2_sigma(
    record_property: Any,
) -> None:
    """§16.4's third criterion as R-298 restates it (§17.3): both runs end `TRF_CONVERGED` with
    θ_recheck ≤ 1e-5, and ‖z_affine − z_native‖_∞ ≤ 2σ = 2e-5, absolute — σ = 1e-5 is TR-E1's own
    step-size and feasibility termination (Pyomo's defaults), so each final point lies within σ of
    the limit. |ΔJ| / max(1, |J|) is recorded. Measured at WO-4: |Δz| = (1.18e-6, 1.11e-6,
    5.7e-7). The native run is TR-E1 through `run_trf` with b ≡ 0, bitwise native's (G3)."""
    from test_m05_trf import run

    result, _ = _tr_e1_affine_and_native()
    _, native_run = run()
    for run_ in (result, native_run):
        assert run_.outcome == "TRF_CONVERGED", run_.error
        assert run_.theta_recheck is not None and run_.theta_recheck <= 1e-5
    affine, native_final = result.final, native_run.final
    assert affine is not None and native_final is not None
    dz = max(abs(affine.decisions[f"z{i}"] - native_final.decisions[f"z{i}"]) for i in range(3))
    dj = abs(affine.objective - native_final.objective) / max(1.0, abs(native_final.objective))
    record_property("M05.R298.tr_e1.dz_inf", dz)
    record_property("M05.R298.tr_e1.dJ_rel", dj)
    assert dz <= 2e-5


class FiniteDifferenceToy(LinkToyTruth):
    """The link toy's map without its gradient: `M05-fd-v2` through the holder, in process."""

    def __init__(self) -> None:
        self.finite_difference = ForwardDifference(lambda point: True, workers=1)

    def describe(self) -> Mapping[str, Any]:
        return {**super().describe(), "id": "link-toy-fd", "gradient": "finite_difference"}


def test_the_link_basis_is_the_truths_taylor_model_at_the_start_inlet() -> None:
    from openflowsheet.studies.trust_region.basis import affine_link_basis, m05_basis

    projection = link_toy_projection("forward")
    basis = affine_link_basis(projection)
    (holder,) = projection.holders
    w0 = [float(projection.model.x[i].value) for i in projection.holder_inputs[0]]
    truth = LinkToyTruth()
    conversion, rise, meta = truth.evaluate(w0)
    assert meta == in_process_meta()
    gradient = truth.gradient(w0)
    entries = projection.source_map["external_links"]
    expected = {
        entry["ef"]: ((conversion, rise)[k], gradient[k], entry["output_scale"])
        for k, entry in enumerate(entries)
    }
    _check_affine_at_start(projection, basis, expected)
    assert set(m05_basis(projection)) == set(projection.ef_names.values())


def test_an_fd_truths_link_basis_reuses_the_gradient_checks_points() -> None:
    """§6.6/§8.3: `basis_fd_point` = n_in = 7 requests at w₀; after the gradient check at the same
    w₀ every one is a memo hit, and the basis gradient is the check's G(η)."""
    from openflowsheet.studies.trust_region.basis import affine_link_basis

    projection = link_toy_projection("forward", FiniteDifferenceToy())
    (holder,) = projection.holders
    w0 = [float(projection.model.x[i].value) for i in projection.holder_inputs[0]]
    check = gradient_check(holder, w0)
    assert sum(1 for e in holder.ledger if e.purpose == FDCHECK_POINT) == 1 + 7 * 3
    before = len(holder.ledger)
    affine_link_basis(projection)
    after = holder.ledger[before:]
    basis_points = [e for e in after if e.purpose == BASIS_FD_POINT]
    assert len(basis_points) == 7 and all(e.served == "memo_hit" for e in basis_points)
    assert holder.request_jacobian(w0) == check.gradient


def test_the_stage_forms_the_basis_inside_the_holders_run() -> None:
    """S33: `TrfStage` hands `run_trf` its basis builder, so the basis's requests belong to the
    run: §8.3's per-run `basis_fd_point` = n_in = 7, with `trf_start_value` = 1 still TRF's own
    start. The basis's requests carry the run id but no `trf_iteration` and no call-order purpose,
    and TRF's run is bitwise the one on a basis built before the run (same document, same
    TRF-phase ledger)."""
    from openflowsheet.studies.trust_region.basis import m05_basis
    from openflowsheet.studies.trust_region.study import IN_PROCESS_BUDGET, StudyBudget, TrfStage
    from openflowsheet.studies.trust_region.trf import run_trf
    from openflowsheet.studies.trust_region.trf_state import TRSP_SOLVER_ALIAS

    config = {"solver": TRSP_SOLVER_ALIAS, "trust_radius": 1.0}
    projection = link_toy_projection("forward", FiniteDifferenceToy())
    stage = TrfStage(lambda s: projection, m05_basis, config)
    staged = stage(None, run_id="R", radius_factor=1.0, budget=StudyBudget(IN_PROCESS_BUDGET))
    (holder,) = projection.holders
    summary = staged.document["ledger"]["summary"][holder.name]
    assert summary["by_purpose"]["basis_fd_point"] == 7
    assert summary["by_purpose"]["trf_start_value"] == 1
    assert all(e.run_id == "R" for e in holder.ledger)
    basis_entries = [e for e in holder.ledger if e.trf_iteration is None]
    # w₀'s value, the FD base (a memo hit), the seven points, the Jacobian they form
    assert [(e.call, e.purpose) for e in basis_entries] == [("value", None)] * 2 + [
        ("value", BASIS_FD_POINT)
    ] * 7 + [("jacobian", None)]

    before = link_toy_projection("forward", FiniteDifferenceToy())
    direct = run_trf(before, config, basis=m05_basis(before), run_id="R")
    (direct_holder,) = before.holders
    assert staged.outcome == direct.outcome
    assert staged.document["iterations"] == [r.as_document() for r in direct.iterations]
    assert staged.decisions == (direct.final.decisions if direct.final is not None else None)

    def trf_phase(entries: Any) -> list[tuple[Any, ...]]:
        return [
            (e.call, e.inputs_sha256, e.served, e.trf_iteration, e.purpose, e.status)
            for e in entries
            if e.trf_iteration is not None
        ]

    assert trf_phase(holder.ledger) == trf_phase(direct_holder.ledger)


@pytest.mark.parametrize("radius_factor", [1.0, 0.25])
def test_the_live_run_document_validates_and_holds_the_request_identity(
    radius_factor: float,
) -> None:
    """WO-7b (S14, S16; §8.3): a live `TrfStage` run document with the loop's keys is a valid
    closed `runs[]` entry of `trust-region-study-v1`, and its FD truth's holder summary satisfies
    G12's request identity (`request_identity_violations`)."""
    from test_m05_study_record import VALIDATOR, request_identity_violations

    from openflowsheet.studies.trust_region.basis import m05_basis
    from openflowsheet.studies.trust_region.study import IN_PROCESS_BUDGET, StudyBudget, TrfStage
    from openflowsheet.studies.trust_region.trf_state import TRSP_SOLVER_ALIAS

    config = {"solver": TRSP_SOLVER_ALIAS, "trust_radius": 1.0}
    projection = link_toy_projection("forward", FiniteDifferenceToy())
    stage = TrfStage(lambda s: projection, m05_basis, config)
    budget = StudyBudget(IN_PROCESS_BUDGET)
    start: Any = None  # the toy's projection ignores the start solve
    staged = stage(start, run_id="C1", radius_factor=radius_factor, budget=budget)
    run = {
        **dict(staged.document),
        "run_id": "C1",
        "stage": "C",
        "study_iteration": 1,
        "retry": 0 if radius_factor == 1.0 else 1,
        "start_check_id": "S0",
        "radius_factor": radius_factor,
        "outcome": staged.outcome,
        "cold": staged.cold,
    }
    schema: Any = VALIDATOR.schema
    runs = VALIDATOR.evolve(
        schema={**schema["properties"]["runs"]["items"], "$defs": schema["$defs"]}
    )
    assert sorted(runs.iter_errors(run), key=str) == []
    assert run["truth"][0]["gradient"] == "finite_difference"
    assert request_identity_violations({"runs": [run]}) == []


# -- R-400: M05-basis-v2, the truth's curvature along the decision path (§20.1, WO-8d) -----------

#: The toy's path: T_in = 680 z with z = 1 + 0.1 d, so dT_in/dd = 68 K per unit scaled decision.
TOY_DT_DD = 68.0
#: The quadratic toy's X = 0.2 + 1e-4 (T − 680) + A (T − 680)²: c_X = 2 A · 68², c_ΔT = 350 c_X.
QUADRATIC = 1e-6


class QuadraticToy(LinkToyTruth):
    """The link toy with curvature in T_in (exact second derivative 2·`QUADRATIC`)."""

    def __init__(self, parent: bool = False) -> None:
        self.parent = parent

    def describe(self) -> Mapping[str, Any]:
        kind = "parent_experiment" if self.parent else "test"
        return {"kind": kind, "id": "link-toy-quadratic", "sha256": None, "gradient": "analytic"}

    def evaluate(self, inlet: Sequence[float]) -> tuple[float, float, Mapping[str, Any]]:
        from openflowsheet.studies.trust_region.truths import in_process_meta

        x = 0.2 + 1e-4 * (inlet[5] - 680.0) + QUADRATIC * (inlet[5] - 680.0) ** 2
        return x, 350.0 * x, in_process_meta()

    def gradient(self, inlet: Sequence[float]) -> Sequence[Sequence[float]]:
        slope = 1e-4 + 2 * QUADRATIC * (inlet[5] - 680.0)
        row = [0.0, 0.0, 0.0, 0.0, 0.0, slope, 0.0]
        return [row, [350.0 * value for value in row]]


class ToyPath:
    """`basis.DecisionPath` on the link toy: the inlet with T_in = 680 z (the heater row), the
    flows and pressure at the projection's start; `fail` makes every solve fail."""

    def __init__(self, projection: Any, tolerance: float = 0.001, fail: bool = False) -> None:
        self.start = projection.state_of()
        self.tolerance = tolerance
        self.fail = fail
        self.asked: list[float] = []

    def state_at(self, decisions: Mapping[str, float]) -> tuple[dict[str, float] | None, str]:
        self.asked.append(decisions["z"])
        if self.fail:
            return None, "NOT_CONVERGED"
        return {**self.start, "T_in": 680.0 * decisions["z"]}, "CONVERGED"


def _v2(truth: Any = None, **path: Any) -> tuple[Any, Any, Any]:
    from openflowsheet.studies.trust_region.basis import m05_basis_v2

    projection = link_toy_projection("forward", truth or QuadraticToy())
    toy = ToyPath(projection, **path)
    return projection, toy, m05_basis_v2(projection, path=toy)


def test_r400_the_curvature_is_the_truths_along_the_path() -> None:
    """Central stencil at d₀ = 0, t = δ/h = 0.001/0.1: c_X = 2·1e-6·68² and c_ΔT = 350 c_X to
    rounding, v = 68 K e_T, the two path points `basis_curvature_point` requests."""
    projection, toy, basis = _v2()
    (holder,) = projection.holders
    (link,) = basis.record["links"].values()
    assert basis.record["policy"] == "M05-basis-v2" and basis.limitations == ()
    assert (link["stencil"], link["t"], link["status"], link["reason"]) == (
        "central",
        0.001 / projection.half_widths[0],
        "ok",
        None,
    )
    expected = 2 * QUADRATIC * TOY_DT_DD**2
    assert link["c"][0] == pytest.approx(expected, rel=1e-6)
    assert link["c"][1] == pytest.approx(350.0 * expected, rel=1e-6)
    assert link["v"] == pytest.approx([0.0] * 5 + [TOY_DT_DD, 0.0], rel=1e-12, abs=1e-12)
    assert toy.asked == [projection.parameter_value(0, d) for d in link["d_points"]]
    assert link["solves"] == ["CONVERGED", "CONVERGED"]
    assert [e.purpose for e in holder.ledger].count("basis_curvature_point") == 2
    kinds = {basis[name].kind for name in projection.ef_names.values() if name.startswith("ef_ext")}
    assert kinds == {"affine_curvature"}


def test_r400_the_basis_value_and_gradient_at_the_start_are_v1s_bitwise() -> None:
    """§20.7 WO-8d (ii): at w₀ the added ½ c p² and its gradient are exact zeros."""
    import pyomo.environ as pyo
    from pyomo.core.expr.calculus.derivatives import Modes, differentiate

    from openflowsheet.studies.trust_region.basis import m05_basis

    projection, _, v2 = _v2()
    v1 = m05_basis(link_toy_projection("forward", QuadraticToy()))
    w0 = projection.state_of()
    names = [name for name in projection.ef_names.values() if name.startswith("ef_ext")]
    model = pyo.ConcreteModel()
    ids = projection.source_map["external_links"][0]["input_variable_ids"]
    model.w = pyo.Var(range(7), initialize=dict(enumerate(w0[i] for i in ids)))
    args = [model.w[j] for j in range(7)]
    for name in names:
        new, old = v2[name].build(args), v1[name].build(args)
        assert pyo.value(new) == pyo.value(old)
        mode = Modes.reverse_numeric
        assert differentiate(new, wrt_list=args, mode=mode) == differentiate(
            old, wrt_list=args, mode=mode
        )


def test_r400_the_stencil_is_one_sided_at_the_box() -> None:
    """§20.7 WO-8d (iv): one-sided towards the interior at d₀ = −1 and at d₀ = 1 − t/2."""
    from openflowsheet.studies.trust_region.basis import _stencil

    t = 0.025
    assert _stencil(0.0, t) == ("central", t, -t, 1.0, 1.0, 0)
    assert _stencil(-1.0, t) == ("forward", -1.0 + t, -1.0 + 2 * t, -2.0, 1.0, 1)
    d0 = 1.0 - t / 2
    assert _stencil(d0, t) == ("backward", d0 - t, d0 - 2 * t, -2.0, 1.0, -1)


def test_r400_the_one_sided_curvature_and_direction_are_exact_on_a_quadratic() -> None:
    """At d₀ = −1 the forward stencil's c = (−2R(t) + R(2t))/t² and
    v = (4w₁ − 3w₀ − w₂)/(2t) are exact for a path and a truth quadratic in d."""
    from openflowsheet.studies.trust_region.basis import m05_basis_v2

    projection = link_toy_projection("forward", QuadraticToy())
    projection.model.d[0].value = -1.0
    toy = ToyPath(projection)
    # w₀ is the projection's x (T_in 680 K): shift the path so that w₀ lies on it at d₀ = −1,
    # T(d) = 680 + 68 (d + 1).
    toy.state_at = lambda decisions: (  # type: ignore[method-assign]
        {**projection.state_of(), "T_in": 680.0 + 680.0 * (decisions["z"] - 0.9)},
        "CONVERGED",
    )
    (link,) = m05_basis_v2(projection, path=toy).record["links"].values()
    assert link["stencil"] == "forward"
    assert link["c"][0] == pytest.approx(2 * QUADRATIC * TOY_DT_DD**2, rel=1e-6)
    assert link["v"][5] == pytest.approx(TOY_DT_DD, rel=1e-9)


def test_r400_a_failed_inner_solve_falls_back_to_the_affine_basis() -> None:
    """§20.7 WO-8d (v): c = 0, `status: failed` with the reason, the limitation, v1's kinds."""
    projection, _, basis = _v2(fail=True)
    (link,) = basis.record["links"].values()
    assert (link["status"], link["reason"], link["c"], link["v"]) == (
        "failed",
        "inner_solve:NOT_CONVERGED",
        [0.0, 0.0],
        None,
    )
    assert basis.limitations == ("basis_without_curvature",)
    assert {basis[n].kind for n in projection.ef_names.values()} == {"affine_taylor"}


def test_r400_a_budget_refusal_propagates_and_another_refusal_falls_back() -> None:
    """§20.7 WO-8d (v): at a path point a budget refusal raises (the run's outcome is then
    `TRF_TRUTH_REFUSED(budget:budget_exhausted)`); any other refusal is a fallback."""
    from openflowsheet.studies.trust_region.basis import m05_basis_v2
    from openflowsheet.studies.trust_region.holders import ColdBudget, RunState, TruthRefused

    projection = link_toy_projection("forward", QuadraticToy(parent=True))
    (holder,) = projection.holders
    holder.begin_run(RunState("C1"), (ColdBudget("C1", 2),))
    with pytest.raises(TruthRefused) as refused:
        m05_basis_v2(projection, path=ToyPath(projection))
    assert refused.value.code == "budget:budget_exhausted"

    class Refusing(QuadraticToy):
        def evaluate(self, inlet: Sequence[float]) -> tuple[float, float, Mapping[str, Any]]:
            if inlet[5] != 680.0:
                return 0.0, 0.0, {"status": "out_of_domain"}
            return super().evaluate(inlet)

    projection, _, basis = _v2(Refusing())
    (link,) = basis.record["links"].values()
    assert (link["status"], link["reason"]) == (
        "failed",
        "refused:out_of_domain:link-toy-quadratic",
    )


def test_r400_more_than_one_decision_is_refused_before_any_request() -> None:
    """§20.7 WO-8d (vi)."""
    from types import SimpleNamespace

    from openflowsheet.studies.trust_region.basis import curvature_link_basis
    from openflowsheet.studies.trust_region.trf_state import TrfConfigurationRefusedError

    stub: Any = SimpleNamespace(decisions=("a", "b"))
    with pytest.raises(TrfConfigurationRefusedError) as refused:
        curvature_link_basis(stub, ToyPath.__new__(ToyPath))
    assert refused.value.codes == ("TRF_CONFIGURATION_REFUSED(basis_curvature_nd:2)",)


def test_r400_the_stage_records_the_basis_block_and_two_curvature_points() -> None:
    """§20.7 WO-8d (vii): through `TrfStage(path_for=)` the run's ledger shows
    `basis_curvature_point` = 2 and its `basis` block is R-400's, a valid `runs[]` entry."""
    from test_m05_study_record import VALIDATOR

    from openflowsheet.studies.trust_region.basis import m05_basis_v2
    from openflowsheet.studies.trust_region.study import IN_PROCESS_BUDGET, StudyBudget, TrfStage
    from openflowsheet.studies.trust_region.trf_state import TRSP_SOLVER_ALIAS

    projection = link_toy_projection("forward", QuadraticToy())
    config = {"solver": TRSP_SOLVER_ALIAS, "trust_radius": 1.0}
    stage = TrfStage(
        lambda s: projection, m05_basis_v2, config, path_for=lambda s: ToyPath(projection)
    )
    staged = stage(None, run_id="C1", radius_factor=1.0, budget=StudyBudget(IN_PROCESS_BUDGET))
    (holder,) = projection.holders
    summary = staged.document["ledger"]["summary"][holder.name]
    assert summary["by_purpose"]["basis_curvature_point"] == 2
    block = staged.document["basis"]
    assert block["policy"] == "M05-basis-v2"
    assert block["links"][holder.name]["noise_ratio"] is None  # no FD check in this run
    schema: Any = VALIDATOR.schema
    basis_schema = {**schema["properties"]["runs"]["items"]["properties"]["basis"]}
    basis_validator = VALIDATOR.evolve(schema={**basis_schema, "$defs": schema["$defs"]})
    assert sorted(basis_validator.iter_errors(block), key=str) == []


def test_r432_noise_ratio_is_the_value_noise_over_the_curvature_step() -> None:
    """R-432 (§21.3): noise_ratio_k = 4σ̂_k/(t²|c_k|), σ̂_k = ν̂·η_sel·s_k/√2, on REAL's committed
    numbers (`runs[C1].basis.links["link:reactor"]`, `fd_check`): c = (−1.2248e-3, 0.81206),
    t = 0.025, ν̂ = 6.8735e-4 at η = 2⁻¹⁴, s = (0.25, 128). By hand: ν̂η = 4.1953e-8, so
    σ̂ = (7.4162e-9, 3.7971e-6) and the ratios are 2.9665e-8/7.6551e-7 = 0.038752 and
    1.5188e-5/5.0754e-4 = 0.029926 — the review's (0.0388, 0.0299), not R-400's (3591.6, 5.42)."""
    from types import SimpleNamespace

    from openflowsheet.studies.trust_region.study import _basis_block

    eta = 2.0**-14
    check = SimpleNamespace(
        as_document=lambda: {
            "selected_eta": eta,
            "candidates": [
                {"eta": 2.0**-12, "noise": 1.0},
                {"eta": eta, "noise": 6.873546997784466e-4},
            ],
        }
    )
    record = {
        "policy": "M05-basis-v2",
        "links": {
            "link:reactor": {
                "t": 0.025,
                "c": [-0.0012248110072319606, 0.8120615673748331],
                "noise_ratio": None,
            },
            "link:other": {"t": 0.5, "c": [0.0, 2.0], "noise_ratio": None},
        },
    }
    scales = {"link:reactor": [0.25, 128.0], "link:other": [1.0, 4.0]}
    block = _basis_block({"ef": "curvature"}, record, [check], scales)
    ratio = block["links"]["link:reactor"]["noise_ratio"]
    assert ratio == pytest.approx([0.038752, 0.029926], rel=2e-5)
    # The committed (3591.6, 5.42) were R-400's 4ν̂/(t²|c_k|): the factor dropped is η·s_k/√2.
    old = [3591.6317314324565, 5.417163248844561]
    assert ratio == pytest.approx(
        [o * eta * s / 2.0**0.5 for o, s in zip(old, [0.25, 128.0], strict=True)]
    )
    # c_k = 0 stays null; σ̂ = 6.8735e-4·2⁻¹⁴·4/√2 = 1.1866e-7, 4σ̂/(0.25·2) = 9.4925e-7.
    assert block["links"]["link:other"]["noise_ratio"] == [None, pytest.approx(9.4925e-7, rel=1e-4)]
    # The builder's record is untouched.
    assert record["links"]["link:reactor"]["noise_ratio"] is None
    assert _basis_block({"ef": "curvature"}, record, [], scales)["links"] == record["links"]
