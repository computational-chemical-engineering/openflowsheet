"""E01 WO-B3 parts 2-3 (§4.10.2, §4.10.3): assessment outputs in M03's NLP, on SYN-001 (P2's host).

A test contributor publishes `size.TOY.area = S3.T·S3.n.A` with a held `units:N` size entry,
`size.FAR.area = 2·S1.n.A` with its own size entry, `capex.purchased.TOY`, `opex.utility.steam`
`= θ_price·1e-5·Q_heat` and `tac = 0.1·capex.purchased.TOY + opex.utility.steam`. The gray box is
checked against the program's own linearization (the same twin), its admissibility closure
against the structural patterns above, and readiness's assessment codes. The Pyomo half (A35 and
the model with outputs) runs only in the audited `nlp` environment (`scripts/m03_nlp_check.sh`);
A33, A34 and A36 run on the registered P2 in I1.

Verification (§4.10.3) runs `verify_candidate` at registered start decisions: V6's values against
the program's float path, V5's gradients against central differences of re-solved states (the
direct `∂G/∂d` term on a variant that reads a pin), V3's admissibility rows, and V7 on a size
entry outside the closure and on a held dormancy entry whose flow is not zero.
"""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from m03_support import flowsheet, nlp_formulation

from openflowsheet.application.types import schema_errors
from openflowsheet.assessment.program import (
    AssessmentProgram,
    BuildContext,
    ContributionPlan,
    Linearization,
    OutputDef,
    Symbols,
    Theta,
)
from openflowsheet.assessment.regimes import (
    AdmissibilityRow,
    Regime,
    RegimeEntry,
    select_dormancy,
    select_size,
    size_units,
)
from openflowsheet.assessment.spec import load_assessment
from openflowsheet.assessment.views import view_of
from openflowsheet.studies.nlp.closure import (
    Readiness,
    SolverAvailability,
    StartEvidence,
    assessment_record,
    classify_starts,
    optimization_readiness,
    start_closure,
    unsupported_report,
)
from openflowsheet.studies.nlp.formulation import (
    AssessmentBinding,
    AssessmentOutputUnknownError,
    Decision,
    FullSpaceNlp,
    NlpFormulation,
    QuadraticExpression,
)
from openflowsheet.studies.nlp.verification import (
    CHECKS,
    CandidateVerification,
    CheckOutcome,
    verify_candidate,
)
from openflowsheet.studies.syn001 import solve_certified, with_pinned

X1, X2, FAR, Q = "S3.T", "S3.n.A", "S1.n.A", "U-HEAT.Q"
FIXTURES = Path(__file__).parent / "fixtures" / "schemas" / "optimization_report" / "valid"
PRICE, MATERIAL = "asm:item.TOY.price", "asm:item.TOY.material"
DOCUMENT: dict[str, Any] = {
    "schema_version": "assessment-v1",
    "assessment_id": "e01-b3-nlp",
    "basis": {"currency": "USD", "year": 2024},
}


class Steam:
    """The test contributor (module docstring). `bounds` are `(S_min, S_max)` per item."""

    name = "cost"

    def __init__(
        self, bounds: Mapping[str, tuple[float, float]], unavailable: tuple[str, ...] = ()
    ) -> None:
        self.bounds = dict(bounds)
        self.unavailable = unavailable

    def plan(self, ctx: BuildContext, state: Mapping[str, float]) -> ContributionPlan:
        toy = OutputDef("size.TOY.area", "m2", lambda s, a: s.x(X1) * s.x(X2))
        far = OutputDef("size.FAR.area", "m2", lambda s, a: 2.0 * s.x(FAR))
        sizes = ctx.evaluate(state, [toy, far])
        entries = []
        units: dict[str, int] = {}
        for item in ("TOY", "FAR"):
            low, high = self.bounds[item]
            size_id = f"size.{item}.area"
            choice = ctx.regime.choice(f"{item}.size") or select_size(sizes[size_id], low, high)
            n = size_units(choice)
            assert n is not None, "the test keeps both items sized"
            units[item] = n
            entries.append(
                RegimeEntry(
                    f"{item}.size",
                    "size",
                    choice,
                    "§4.3.2 rule 4",
                    (
                        AdmissibilityRow(
                            "max", _row(lambda v, n=n, h=high: n * h - v, size_id), high
                        ),
                        AdmissibilityRow(
                            "min", _row(lambda v, n=n, lo=low: v - n * lo, size_id), high
                        ),
                    ),
                )
            )
        n_toy = units["TOY"]

        def capex(s: Symbols, a: Any) -> Any:
            return n_toy * 1e4 * a.exp(0.6 * a.log(s.out("size.TOY.area") / n_toy))

        return ContributionPlan(
            outputs=(
                toy,
                far,
                OutputDef("capex.purchased.TOY", "currency", capex),
                OutputDef(
                    "opex.utility.steam", "currency/yr", lambda s, a: s.theta(PRICE) * 1e-5 * s.x(Q)
                ),
                OutputDef(
                    "tac",
                    "currency/yr",
                    lambda s, a: 0.1 * s.out("capex.purchased.TOY") + s.out("opex.utility.steam"),
                ),
            ),
            theta=(
                Theta(PRICE, 1.5, "1", "test price", relative_range=(-0.1, 0.1)),
                Theta(MATERIAL, 1.0, "1", "test material", structural=True),
            ),
            regime_entries=tuple(entries),
            unavailable=tuple((name, "a test withholding") for name in self.unavailable),
        )


def _row(form: Any, size_id: str) -> Any:
    return lambda s, a: form(s.out(size_id))


@cache
def base() -> tuple[Any, dict[str, float]]:
    sheet = flowsheet({})
    solve = solve_certified(sheet)
    assert solve.verified and solve.final_state is not None
    return sheet, dict(solve.final_state)


def sizes(state: Mapping[str, float]) -> dict[str, float]:
    return {"TOY": state[X1] * state[X2], "FAR": 2.0 * state[FAR]}


def program(
    bounds: Mapping[str, tuple[float, float]] | None = None, unavailable: tuple[str, ...] = ()
) -> AssessmentProgram:
    sheet, state = base()
    if bounds is None:
        bounds = {item: (value / 4.0, value * 4.0) for item, value in sizes(state).items()}
    built = AssessmentProgram.build(
        view_of(sheet),
        sheet.spec(),
        load_assessment(DOCUMENT),
        state,
        contributors=[Steam(bounds, unavailable)],
    )
    assert isinstance(built, AssessmentProgram), built
    return built


def formulation(
    objective: QuadraticExpression,
    binding: AssessmentBinding | None,
    decisions: tuple[Decision, ...] | None = None,
) -> NlpFormulation:
    m03 = nlp_formulation()
    chosen = m03.decisions if decisions is None else decisions
    extra = len(chosen) - len(m03.decisions)
    return NlpFormulation(
        problem_id="E01-B3",
        decisions=chosen,
        objective=objective,
        constraints=m03.constraints,
        starts=tuple((*start, *([1.0] * extra)) for start in m03.starts),
        assessment=binding,
    )


def tac_objective(scale: float = 1.0) -> QuadraticExpression:
    return QuadraticExpression(linear={"assessment:tac": 1.0 / scale}, text="tac/|tac(x0)|")


def available() -> SolverAvailability:
    return SolverAvailability(True, "test double: the audited extra is present")


def ready(f: NlpFormulation) -> Readiness:
    return optimization_readiness(f, flowsheet({}), solver_probe=available)


@cache
def m03_readiness() -> Readiness:
    return ready(nlp_formulation())


def full_space(f: NlpFormulation, start: int = 0) -> FullSpaceNlp:
    record = m03_readiness().starts[start]
    assert record.state is not None
    pinned = with_pinned(flowsheet({}), f.decision_values(record.start))
    return FullSpaceNlp(pinned, f, record.state, record.start)


def binding(outputs: tuple[str, ...], p: AssessmentProgram | None = None) -> AssessmentBinding:
    return AssessmentBinding.at(program() if p is None else p, outputs, base()[1])


# -- names -------------------------------------------------------------------------------------


def test_assessment_names_are_split_from_state_variables() -> None:
    objective = QuadraticExpression(
        linear={"assessment:tac": 1.0, Q: 1e-5}, quadratic={("assessment:tac", X1): 2.0}
    )
    f = formulation(objective, binding(("tac",)))
    assert f.variables == (Q, X1, "S4.n.A", "S1.n.A")
    assert f.assessment_outputs == ("tac",)
    assert f.unknown_assessment_outputs() == ()
    assert nlp_formulation().assessment is None
    assert nlp_formulation().assessment_outputs == ()


def test_the_binding_scale_is_max_abs_y_at_the_state_and_one_at_least() -> None:
    p = program()
    values = p.evaluate(base()[1])
    assert isinstance(values, Mapping)
    b = binding(("tac", "size.TOY.area"), p)
    assert b.output_scales == {
        "tac": max(abs(values["tac"]), 1.0),
        "size.TOY.area": max(abs(values["size.TOY.area"]), 1.0),
    }
    with pytest.raises(ValueError, match="one scale per output"):
        AssessmentBinding(p, ("tac",), {})
    with pytest.raises(ValueError, match="finite and > 0"):
        AssessmentBinding(p, ("tac",), {"tac": 0.0})


def test_an_unknown_assessment_name_is_refused_before_any_solve() -> None:
    p = program()
    cases = {
        "no binding": (tac_objective(), None),
        "not bound": (
            QuadraticExpression(linear={"assessment:size.FAR.area": 1.0}),
            binding(("tac",), p),
        ),
        "not published": (
            QuadraticExpression(linear={"assessment:capex.purchased.NOPE": 1.0}),
            AssessmentBinding(p, ("capex.purchased.NOPE",), {"capex.purchased.NOPE": 1.0}),
        ),
        "an admissibility row": (
            QuadraticExpression(linear={"assessment:adm.TOY.size.max": 1.0}),
            AssessmentBinding(p, ("adm.TOY.size.max",), {"adm.TOY.size.max": 1.0}),
        ),
    }
    for case, (objective, bound) in cases.items():
        f = formulation(objective, bound)
        with pytest.raises(AssessmentOutputUnknownError) as raised:
            full_space(f)
        assert raised.value.names == f.assessment_outputs, case
        assert ready(f).codes == ("ASSESSMENT_OUTPUT_UNKNOWN",), case


def test_a_null_output_is_unavailable_and_an_assessment_parameter_is_never_a_decision() -> None:
    withheld = program(unavailable=("tac",))
    f = formulation(tac_objective(), AssessmentBinding(withheld, ("tac",), {"tac": 1.0}))
    assert ready(f).codes == ("ASSESSMENT_OUTPUT_UNAVAILABLE",)

    m03 = nlp_formulation()
    for theta, code in (
        (PRICE, "ASSESSMENT_PARAMETER_DECISION"),
        (MATERIAL, "ASSESSMENT_PARAMETER_STRUCTURAL"),
    ):
        decisions = (*m03.decisions, Decision(theta, 0.5, 2.0, 1.0))
        found = ready(formulation(tac_objective(), binding(("tac",)), decisions))
        assert found.codes == (code,), theta
        assert found.reasons[0].subject == theta


def test_the_held_regime_is_checked_at_every_start() -> None:
    starts = [record.state for record in m03_readiness().starts]
    assert all(state is not None for state in starts)
    at_base = sizes(base()[1])["TOY"]
    at_starts = [sizes(state)["TOY"] for state in starts if state is not None]
    # S_max between the base size and the largest start size: units:1 holds at the base and is
    # violated at that start.
    largest = max(at_starts)
    assert largest > at_base * (1.0 + 1e-6)
    high = 0.5 * (at_base + largest)
    far = sizes(base()[1])["FAR"]
    p = program({"TOY": (at_base / 4.0, high), "FAR": (far / 4.0, far * 2.0)})
    assert p.regime.choice("TOY.size") == "units:1"
    found = ready(formulation(tac_objective(), binding(("tac",), p)))
    assert set(found.codes) == {"ASSESSMENT_REGIME_INADMISSIBLE"}
    violated = {reason.subject for reason in found.reasons}
    assert violated == {"adm.TOY.size.max"}
    index = at_starts.index(largest)
    assert any(reason.detail.startswith(f"start {index}:") for reason in found.reasons)


def test_a_bound_formulation_without_violations_is_ready() -> None:
    assert ready(formulation(tac_objective(), binding(("tac",)))).status == (
        "READY_FOR_OPTIMIZATION"
    )


# -- the gray box's outputs (FullSpaceNlp; no Pyomo) --------------------------------------------


def test_without_an_assessment_there_are_no_outputs() -> None:
    nlp = full_space(nlp_formulation())
    assert nlp.output_ids == ()
    assert nlp.output_scales == {}
    assert nlp.assessment_property_calls() == 0


def test_the_closure_takes_the_entries_whose_rows_share_a_column_with_a_bound_output() -> None:
    p = program()
    rows = {
        "TOY": ("adm.TOY.size.max", "adm.TOY.size.min"),
        "FAR": ("adm.FAR.size.max", "adm.FAR.size.min"),
    }
    assert set(p.admissibility_ids) == {*rows["TOY"], *rows["FAR"]}
    expected = {
        ("tac",): ("tac", *rows["TOY"]),
        ("opex.utility.steam",): ("opex.utility.steam",),
        ("size.FAR.area", "tac"): ("size.FAR.area", "tac", *rows["TOY"], *rows["FAR"]),
    }
    for outputs, ids in expected.items():
        objective = QuadraticExpression(linear={f"assessment:{outputs[-1]}": 1.0})
        nlp = full_space(formulation(objective, binding(outputs, p)))
        # Bound outputs in catalogue (program) order, then the closure's rows in theirs.
        assert nlp.output_ids == tuple(sorted(ids, key=lambda name: p.output_ids.index(name))), (
            outputs
        )
        assert set(nlp.admissibility_nominals) == set(ids) - set(outputs)


def test_outputs_and_their_jacobian_are_the_programs_linearization_bitwise() -> None:
    p = program()
    f = formulation(tac_objective(), binding(("size.FAR.area", "tac"), p))
    nlp = full_space(f)
    z = nlp.initial_point()
    x, decisions = nlp.split(z)
    state = dict(zip(nlp.variable_ids, (float(v) for v in x), strict=True))
    lin = p.linearize(state, decisions, nlp.output_ids, symbolic=nlp.decision_ids)
    assert isinstance(lin, Linearization), lin
    values = nlp.output_values(z)
    assert values.tolist() == [lin.values[name] for name in nlp.output_ids]
    jacobian = nlp.output_jacobian(z).toarray()
    expected = np.zeros_like(jacobian)
    for matrix, offset in ((lin.d_dx, 0), (lin.d_dp, nlp.n_variables)):
        for j in range(len(matrix.col_ids)):
            for k in range(matrix.indptr[j], matrix.indptr[j + 1]):
                expected[matrix.indices[k], offset + j] = matrix.data[k]
    assert np.array_equal(jacobian, expected)
    # Twin and float reference path agree (A4's tolerance) at the start.
    reference = p.evaluate(state, decisions)
    assert isinstance(reference, Mapping)
    for name, value in zip(nlp.output_ids, values, strict=True):
        assert abs(value - reference[name]) <= 1e-13 * max(1.0, abs(reference[name])), name


def test_the_jacobian_pattern_is_fixed_and_canonical_across_points() -> None:
    nlp = full_space(formulation(tac_objective(), binding(("size.FAR.area", "tac"))))
    z = nlp.initial_point()
    first = nlp.output_jacobian(z)
    moved = z.copy()
    moved[: nlp.n_variables] *= 1.0 + 1e-3
    second = nlp.output_jacobian(moved)
    assert first.has_canonical_format and second.has_canonical_format
    assert np.array_equal(first.indptr, second.indptr)
    assert np.array_equal(first.indices, second.indices)
    assert not np.array_equal(first.data, second.data)


def test_output_scaling_is_one_over_the_binding_scale_and_one_for_admissibility() -> None:
    b = binding(("tac",))
    nlp = full_space(formulation(tac_objective(), b))
    expected = [1.0 / b.output_scales["tac"]] + [1.0] * (len(nlp.output_ids) - 1)
    assert nlp.output_scaling().tolist() == expected
    entries = {
        f"adm.{e.entry_id}.{r.row_id}": r.nominal
        for e in b.program.entries
        for r in e.admissibility
    }
    assert nlp.admissibility_nominals == {name: entries[name] for name in nlp.output_ids[1:]}


# -- Pyomo (the audited nlp environment) -------------------------------------------------------


@pytest.mark.nlp
def test_a35_without_an_assessment_the_model_is_m03s() -> None:
    """A35: no outputs, and the component list and objective are what `main` builds (recorded
    from `main`'s greybox.py at 9b214095, before E01 touched it)."""
    from openflowsheet.studies.nlp import greybox

    nlp = full_space(nlp_formulation())
    box = greybox.FullSpaceGreyBox(nlp)
    assert box.output_names() == []
    model = greybox.build_model(nlp, box)
    components = [(c.name, type(c).__name__) for c in model.component_objects(descend_into=True)]
    assert components == [
        ("greybox", "ScalarExternalGreyBoxBlock"),
        ("objective", "ScalarObjective"),
        ("inequalities", "IndexedConstraint"),
        ("scaling_factor", "Suffix"),
    ]
    assert str(model.objective.expr) == (
        "1e-05*greybox.inputs['U-HEAT.Q'] + 1e-05*greybox.inputs['U-FLASH.Q'] + "
        "1e-08*greybox.inputs['U-HEAT.Q']*greybox.inputs['U-HEAT.Q']"
    )


@pytest.mark.nlp
def test_the_model_maps_assessment_names_to_outputs_and_adds_the_admissibility_rows() -> None:
    from pyomo.contrib.pynumero.interfaces.pyomo_grey_box_nlp import PyomoNLPWithGreyBoxBlocks

    from openflowsheet.studies.nlp import greybox

    b = binding(("tac",))
    nlp = full_space(formulation(tac_objective(b.output_scales["tac"]), b))
    box = greybox.FullSpaceGreyBox(nlp)
    assert box.output_names() == list(nlp.output_ids)
    model = greybox.build_model(nlp, box)
    outputs = model.greybox.outputs
    z = nlp.initial_point()
    g0 = nlp.output_values(z)
    assert [outputs[name].value for name in nlp.output_ids] == g0.tolist()
    assert str(model.objective.expr) == f"{1.0 / b.output_scales['tac']!r}*greybox.outputs[tac]"
    admissibility = list(nlp.admissibility_nominals)
    assert list(model.assessment_admissibility) == admissibility
    for name in admissibility:
        constraint = model.assessment_admissibility[name]
        assert constraint.lower == 0.0 and constraint.upper is None
        assert model.scaling_factor[constraint] == 1.0
    for name, factor in zip(nlp.output_ids, nlp.output_scaling(), strict=True):
        assert model.scaling_factor[outputs[name]] == factor

    pynumero = PyomoNLPWithGreyBoxBlocks(model)
    pynumero.set_primals(pynumero.init_primals())
    rows = pynumero.constraint_names()
    # The gray box's output rows `G(z) − y` vanish at the initial point, where y = G(x₀).
    residual = pynumero.evaluate_constraints()
    output_rows = [i for i, row in enumerate(rows) if row.startswith("greybox.output_constraints")]
    assert len(output_rows) == len(nlp.output_ids)
    assert np.array_equal(residual[output_rows], np.zeros(len(output_rows)))
    scaling = pynumero.get_constraints_scaling()
    assert scaling[output_rows].tolist() == nlp.output_scaling().tolist()
    assert math.isclose(pynumero.evaluate_objective(), g0[0] / b.output_scales["tac"])


# -- verification at x_sim (§4.10.3) -------------------------------------------------------------

#: The variant's pinned-input term (a decision the program reads directly, so `∂G/∂d ≠ 0`).
PIN_WEIGHT = 1.0e3


class PinnedSteam(Steam):
    """`Steam` plus `opex.utility.pinned = tac + PIN_WEIGHT·d₀`, `d₀` the first M03 decision
    read as a pin."""

    def plan(self, ctx: BuildContext, state: Mapping[str, float]) -> ContributionPlan:
        plan = super().plan(ctx, state)
        pin = nlp_formulation().decision_ids[0]
        extra = OutputDef(
            "opex.utility.pinned",
            "currency/yr",
            lambda s, a: s.out("tac") + PIN_WEIGHT * s.pin(pin),
        )
        return dataclasses.replace(plan, outputs=(*plan.outputs, extra))


class DormantSteam(Steam):
    """`Steam` plus a dormancy entry on the stream whose flow is `FAR` (§4.3.1: no rows)."""

    def plan(self, ctx: BuildContext, state: Mapping[str, float]) -> ContributionPlan:
        plan = super().plan(ctx, state)
        entry_id = "FAR.feed.dormant"
        choice = ctx.regime.choice(entry_id) or select_dormancy(state[FAR])
        entry = RegimeEntry(entry_id, "dormant", choice, "§4.3.2 rule 3")
        return dataclasses.replace(plan, regime_entries=(*plan.regime_entries, entry))


def built(contributor: Any, regime: Regime | None = None) -> AssessmentProgram:
    sheet, state = base()
    made = AssessmentProgram.build(
        view_of(sheet),
        sheet.spec(),
        load_assessment(DOCUMENT),
        state,
        regime,
        contributors=[contributor],
    )
    assert isinstance(made, AssessmentProgram), made
    return made


def default_bounds() -> dict[str, tuple[float, float]]:
    return {item: (value / 4.0, value * 4.0) for item, value in sizes(base()[1]).items()}


def bound(p: AssessmentProgram, output: str) -> NlpFormulation:
    b = binding((output,), p)
    objective = QuadraticExpression(
        linear={f"assessment:{output}": 1.0 / b.output_scales[output]}, text=f"{output}/scale"
    )
    return formulation(objective, b)


def verify(f: NlpFormulation, start: int = 0) -> CandidateVerification:
    record = m03_readiness().starts[start]
    assert record.state is not None and record.regimes is not None
    return verify_candidate(
        flowsheet({}), f, record.start, regimes=record.regimes, optimizer_state=record.state
    )


def resolved(p: AssessmentProgram, decisions: Mapping[str, float]) -> Mapping[str, float]:
    solve = solve_certified(with_pinned(flowsheet({}), decisions))
    assert solve.verified and solve.final_state is not None
    values = p.evaluate(solve.final_state, decisions)
    assert isinstance(values, Mapping)
    return values


def test_v6_and_v3_take_the_assessment_values_from_the_float_path_at_x_sim() -> None:
    p = program()
    f = bound(p, "tac")
    result = verify(f)
    assert [check.check for check in result.checks] == list(CHECKS)
    # A start is neither feasible for M03's own constraints nor stationary: V3 and V5 decide
    # nothing here; the admissibility rows are inside their range.
    for check in ("V1", "V2", "V4", "V6", "V7"):
        assert result.outcome(check) == "pass", check
    v3 = next(check for check in result.checks if check.check == "V3")
    assert not [name for name in v3.detail["violated"] if name.startswith("adm.")]
    assert result.simulation_state is not None
    values = p.evaluate(result.simulation_state, f.decision_values(verify_start(0)))
    assert isinstance(values, Mapping)
    rows = ("adm.TOY.size.max", "adm.TOY.size.min")
    assert result.assessment_values == {name: values[name] for name in ("tac", *rows)}
    scale = f.assessment.output_scales["tac"]  # type: ignore[union-attr]
    assert result.objective == math.fsum([0.0, values["tac"] / scale])
    for name in rows:
        # V3: each closure row is `adm ≥ 0`, its value the program's, its slack the value.
        assert result.constraint_values[name] == values[name]
        assert result.slacks[name] == {"lower": values[name]}
    v6 = next(check for check in result.checks if check.check == "V6")
    assert v6.detail["assessment_values"] == result.assessment_values
    v7 = next(check for check in result.checks if check.check == "V7")
    assert v7.detail["selected"] == v7.detail["held"] == dict(p.regime.entries)


def verify_start(index: int) -> tuple[float, ...]:
    return tuple(m03_readiness().starts[index].start)


@pytest.mark.parametrize(
    ("contributor", "output"), [("plain", "tac"), ("pinned", "opex.utility.pinned")]
)
def test_v5_assessment_gradients_match_central_differences_of_resolved_states(
    contributor: str, output: str
) -> None:
    p = program() if contributor == "plain" else built(PinnedSteam(default_bounds()))
    f = bound(p, output)
    result = verify(f)
    assert result.kkt is not None and result.sensitivity is not None
    assert result.sensitivity.status == "QUALIFIED"
    scale = f.assessment.output_scales[output]  # type: ignore[union-attr]
    row = "adm.TOY.size.max"
    measured = {output: result.kkt.objective_gradient, row: result.kkt.constraint_gradients[row]}
    assert result.simulation_state is not None
    base_decisions = f.decision_values(verify_start(0))
    for j, decision in enumerate(f.decisions):
        step = 1e-4 * decision.scale
        plus = resolved(
            p,
            {**base_decisions, decision.parameter_id: base_decisions[decision.parameter_id] + step},
        )
        minus = resolved(
            p,
            {**base_decisions, decision.parameter_id: base_decisions[decision.parameter_id] - step},
        )
        for name, divisor in ((output, scale), (row, 1.0)):
            expected = (plus[name] - minus[name]) / (2.0 * step) * decision.scale / divisor
            got = measured[name][j]
            assert abs(got - expected) <= 1e-6 * max(abs(expected), 1e-12), (name, j, got, expected)


def test_v5_the_direct_term_is_the_pins_coefficient() -> None:
    # `opex.utility.pinned − tac = PIN_WEIGHT·d₀`: the scaled gradients differ by exactly that,
    # on d₀ only.
    p = built(PinnedSteam(default_bounds()))
    scale = binding(("opex.utility.pinned",), p).output_scales["opex.utility.pinned"]
    f = formulation(
        QuadraticExpression(
            linear={"assessment:opex.utility.pinned": 1.0 / scale, "assessment:tac": -1.0 / scale}
        ),
        binding(("opex.utility.pinned", "tac"), p),
    )
    result = verify(f)
    assert result.kkt is not None
    expected = [0.0] * len(f.decisions)
    expected[0] = PIN_WEIGHT * f.decisions[0].scale / scale
    got = result.kkt.objective_gradient
    for j, value in enumerate(expected):
        assert abs(got[j] - value) <= 1e-9 * max(abs(value), 1.0), (j, got[j], value)


def sized_to_change() -> tuple[AssessmentProgram, int]:
    """A program holding `TOY.size = units:1` at the base whose `S_max` a start exceeds."""
    starts = [record.state for record in m03_readiness().starts]
    at_starts = [sizes(state)["TOY"] for state in starts if state is not None]
    at_base = sizes(base()[1])["TOY"]
    largest = max(at_starts)
    far = sizes(base()[1])["FAR"]
    high = 0.5 * (at_base + largest)
    p = program({"TOY": (at_base / 4.0, high), "FAR": (far / 4.0, far * 2.0)})
    assert p.regime.choice("TOY.size") == "units:1"
    return p, at_starts.index(largest)


def test_v7_catches_a_regime_change_outside_the_closure_and_v3_inside_it() -> None:
    p, start = sized_to_change()
    # `opex.utility.steam`'s closure holds no row: V3 passes, V7 alone refuses.
    outside = verify(bound(p, "opex.utility.steam"), start)
    v7 = next(check for check in outside.checks if check.check == "V7")
    v3 = next(check for check in outside.checks if check.check == "V3")
    assert not [name for name in v3.detail["violated"] if name.startswith("adm.")]
    assert v7.outcome == "fail"
    assert v7.detail["regime_changed"] == ["TOY.size"]
    assert v7.detail["codes"] == ["ASSESSMENT_REGIME_CHANGED(TOY.size)"]
    assert v7.detail["selected"]["TOY.size"] == "units:2"
    assert not outside.passed
    # `tac`'s closure holds the TOY rows: V3 sees the violated row too.
    inside = verify(bound(p, "tac"), start)
    v3 = next(check for check in inside.checks if check.check == "V3")
    assert v3.outcome == "fail"
    assert [name for name in v3.detail["violated"] if name.startswith("adm.")] == [
        "adm.TOY.size.max"
    ]
    assert inside.outcome("V7") == "fail"


def test_v7_compares_a_dormancy_entry_exactly_and_refuses_like_v2() -> None:
    entry = "FAR.feed.dormant"
    active = built(DormantSteam(default_bounds()))
    assert active.regime.choice(entry) == "active"
    assert verify(bound(active, "tac")).outcome("V7") == "pass"
    dormant = built(DormantSteam(default_bounds()), Regime({entry: "dormant"}))
    assert dormant.regime.choice(entry) == "dormant"
    result = verify(bound(dormant, "tac"))
    v7 = next(check for check in result.checks if check.check == "V7")
    assert v7.outcome == "fail"
    assert v7.detail["codes"] == [f"ASSESSMENT_REGIME_CHANGED({entry})"]
    assert v7.detail["dormancy_released"] == [entry]
    assert not result.passed
    # Status precedence as V2: V1-V5 passed and V7 failed is a refuted claim, not a verification.
    checks: dict[str, CheckOutcome] = dict.fromkeys(CHECKS[:6], "pass")
    verdict = classify_starts([StartEvidence(0, {**checks, "V7": "fail"})])
    assert verdict.status == "NOT_VERIFIED"
    assert classify_starts([StartEvidence(0, {**checks, "V7": "pass"})]).status == (
        "KKT_POINT_VERIFIED"
    )


def test_the_report_records_v7_and_the_formulation_assessment_valid_against_the_schema() -> None:
    p = program()
    f = bound(p, "tac")
    result = verify(f)
    readiness = ready(f)
    closure = start_closure(f, flowsheet({}), readiness)
    assert closure is not None
    assert closure.output_ids == full_space(f).output_ids
    record = assessment_record(f, closure, result)
    assert record is not None
    assert record["outputs"] == [{"id": "tac", "scale": f.assessment.output_scales["tac"]}]  # type: ignore[union-attr]
    assert record["admissibility"] == [
        {"id": name, "nominal": closure.nominals[name]} for name in closure.admissibility
    ]
    assert record["regime_sha256"] == p.regime.sha256
    assert record["regime_bounds_active"] == []  # the start is inside its size range
    report = json.loads((FIXTURES / "nlp_1_solved.json").read_text(encoding="utf-8"))
    report["candidate"] = result.as_document()
    report["formulation"]["assessment"] = record
    assert schema_errors("optimization-report.schema.json", report) == []
    absent = optimization_readiness(
        f, flowsheet({}), solver_probe=lambda: SolverAvailability(False, "test: no extra")
    )
    unsupported = unsupported_report(f, flowsheet({}), absent).as_document()
    assert unsupported["formulation"]["assessment"] == record
    assert schema_errors("optimization-report.schema.json", unsupported) == []
    # Without a binding the formulation record has no `assessment` key (G9).
    plain = unsupported_report(nlp_formulation(), flowsheet({}), m03_readiness()).as_document()
    assert "assessment" not in plain["formulation"]


@pytest.mark.nlp
def test_a_tac_objective_solves_to_a_verified_point_with_v7_from_every_m03_start() -> None:
    from openflowsheet.studies.nlp.closure import optimize

    p = program()
    f = bound(p, "tac")
    report = optimize(f, flowsheet({})).as_document()
    assert schema_errors("optimization-report.schema.json", report) == []
    assert report["status"] == "KKT_POINT_VERIFIED"
    for start in report["starts"]:
        assert [check["check"] for check in start["checks"]] == list(CHECKS)
        assert start["checks"][-1]["outcome"] == "pass"
    candidate = report["candidate"]
    assert [check["outcome"] for check in candidate["checks"]] == ["pass"] * len(CHECKS)
    v6 = next(check for check in candidate["checks"] if check["check"] == "V6")
    at_candidate = v6["assessment_values"]["tac"]
    for record in m03_readiness().starts:
        assert record.state is not None
        values = p.evaluate(record.state, f.decision_values(record.start))
        assert isinstance(values, Mapping)
        assert at_candidate <= values["tac"]
    assert report["formulation"]["assessment"]["outputs"][0]["id"] == "tac"
