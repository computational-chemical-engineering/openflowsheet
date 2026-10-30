"""E01 WO-A1: the assessment core on a toy contributor over a solved SYN-001 state.

E01 design §4.1–§4.3, §6.1 A4–A8 (gate G2's mechanism; the P1–P4 runs are I1's). The toy has the
three shapes WO-A1's acceptance names: `y = x₁·x₂` (a sizing quantity), `y = exp(θ)·x₁` (a
continuous θ), and one `size` regime (`units:N` / `floor`) with its admissibility rows, plus a
structural θ. Expectations are written from the formulas, never from the program's output.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from functools import cache
from typing import Any

import numpy as np
import pytest
from m03_support import flowsheet

from openflowsheet.assessment.defaults import DEFAULTS, REQUIRED
from openflowsheet.assessment.program import (
    AssessmentProgram,
    BuildContext,
    ContributionPlan,
    Linearization,
    OutputDef,
    Refusal,
    Symbols,
    Theta,
)
from openflowsheet.assessment.quantities import classify, study_name
from openflowsheet.assessment.regimes import (
    AdmissibilityRow,
    Regime,
    RegimeEntry,
    select_argmax,
    select_piece,
    select_size,
    size_units,
)
from openflowsheet.assessment.spec import AssessmentDocumentError, load_assessment
from openflowsheet.assessment.views import view_of
from openflowsheet.canonical import document_sha256
from openflowsheet.compile.casadi_backend import TwinEvaluationError, compile_parametric_twin
from openflowsheet.compile.reference import row_values
from openflowsheet.compile.spec import EquationSpec, ProblemSpec
from openflowsheet.studies.nlp.verification import TAU_FEAS
from openflowsheet.studies.syn001 import solve_certified

X1, X2 = "S3.T", "S3.n.A"
K, CF, FM = "asm:item.TOY.k", "asm:item.TOY.c", "asm:item.TOY.material"
EXPONENT = 0.6
DOCUMENT: dict[str, Any] = {
    "schema_version": "assessment-v1",
    "assessment_id": "e01-a1-toy",
    "basis": {"currency": "USD", "year": 2024},
}


class Toy:
    """`size.TOY.area = x₁x₂`; `size.TOY.volume = exp(θ_k)x₁`;
    `capex.purchased.TOY = F_M·N·exp(θ_c)·(S/N)^0.6` (`units:N`) or `F_M·exp(θ_c)·S_min^0.6`."""

    name = "cost"

    def __init__(self, size_min: float, size_max: float) -> None:
        self.size_min, self.size_max = size_min, size_max

    def plan(self, ctx: BuildContext, state: Mapping[str, float]) -> ContributionPlan:
        area = OutputDef("size.TOY.area", "m2", lambda s, a: s.x(X1) * s.x(X2))
        size = ctx.evaluate(state, [area])["size.TOY.area"]
        choice = ctx.regime.choice("TOY.size") or select_size(size, self.size_min, self.size_max)
        units = size_units(choice)
        smin, smax = self.size_min, self.size_max

        def capex(s: Symbols, a: Any) -> Any:
            scale = s.theta(FM) * a.exp(s.theta(CF))
            if units is None:
                return scale * math.exp(EXPONENT * math.log(smin))
            return scale * units * a.exp(EXPONENT * a.log(s.out("size.TOY.area") / units))

        if units is None:
            rows = (AdmissibilityRow("min", lambda s, a: smin - s.out("size.TOY.area"), smax),)
        else:
            rows = (
                AdmissibilityRow("max", lambda s, a: units * smax - s.out("size.TOY.area"), smax),
                AdmissibilityRow("min", lambda s, a: s.out("size.TOY.area") - units * smin, smax),
            )
        return ContributionPlan(
            outputs=(
                area,
                OutputDef("size.TOY.volume", "m3", lambda s, a: a.exp(s.theta(K)) * s.x(X1)),
                OutputDef("capex.purchased.TOY", "currency", capex),
            ),
            theta=(
                Theta(K, 0.3, "1", "toy", relative_range=(-0.1, 0.1)),
                Theta(CF, 2.0, "1", "toy"),
                Theta(FM, 1.5, "1", "toy material factor", structural=True),
            ),
            regime_entries=(RegimeEntry("TOY.size", "size", choice, "§4.3.2 rule 4", rows),),
        )


@cache
def solved() -> tuple[Any, ProblemSpec, dict[str, float]]:
    sheet = flowsheet({})
    solve = solve_certified(sheet)
    assert solve.verified and solve.final_state is not None
    return sheet, sheet.spec(), dict(solve.final_state)


def size_at(state: Mapping[str, float]) -> float:
    return state[X1] * state[X2]


def build(
    toy: Toy, state: Mapping[str, float] | None = None, regime: Regime | None = None
) -> AssessmentProgram | Refusal:
    sheet, host, solved_state = solved()
    return AssessmentProgram.build(
        view_of(sheet),
        host,
        load_assessment(DOCUMENT),
        solved_state if state is None else state,
        regime,
        contributors=[toy],
    )


def program(toy: Toy, state: Mapping[str, float] | None = None, **kw: Any) -> AssessmentProgram:
    built = build(toy, state, **kw)
    assert isinstance(built, AssessmentProgram), built
    return built


def values_of(p: AssessmentProgram, x: Mapping[str, float], **kw: Any) -> Mapping[str, float]:
    values = p.evaluate(x, **kw)
    assert not isinstance(values, Refusal), values
    return values


def mid_toy() -> Toy:
    """S_min/S_max around the solved size so that `units:1` is selected."""
    size = size_at(solved()[2])
    return Toy(size / 4.0, size * 2.0)


# -- the host and the view -------------------------------------------------------------------------


def test_no_host_variable_uses_the_assessment_prefix() -> None:
    _, host, _ = solved()
    assert not [name for name in host.variable_ids if name.startswith("assessment:")]


def test_the_view_lists_the_units_in_declaration_order_with_their_molar_masses() -> None:
    sheet, _, _ = solved()
    view = view_of(sheet)
    assert [u.unit_id for u in view.units()] == [u.unit_id for u in sheet.units()]
    heater = next(u for u in view.units() if u.unit_id == "U-HEAT")
    assert heater.model_id == "syn001.tp_heater"
    assert heater.parameters["U-HEAT.T_spec"] == sheet.heater_temperature
    assert dict(view.molar_masses()) == {"A": 0.1, "B": 0.1, "C": 0.1}


# -- the document --------------------------------------------------------------------------------


def test_the_document_is_validated_and_identified_by_its_canonical_hash() -> None:
    spec = load_assessment(DOCUMENT)
    assert spec.assessment_sha256 == document_sha256(DOCUMENT)
    assert spec.assessment_id == "e01-a1-toy"
    with pytest.raises(AssessmentDocumentError, match="unexpected|Additional"):
        load_assessment({**DOCUMENT, "surprise": 1})
    with pytest.raises(AssessmentDocumentError, match="canonical"):
        load_assessment({**DOCUMENT, "operation": {"discount_rate": math.nan}})


def test_the_catalogue_classifies_every_section_and_refuses_the_rest() -> None:
    expected = {
        "size.U-FLASH.drum.diameter": "size",
        "capex.purchased.U-HEAT": "capex.purchased",
        "capex.sum_bare_module": "capex.sum",
        "capex.TDC": "capex.step",
        "opex.total": "opex.total",
        "opex.utility.LPS": "opex.utility",
        "revenue.total": "revenue.total",
        "tac": "tac",
        "impact.climate_change.per_fu": "impact",
        "adm.U-HEAT.size.max": "adm",
    }
    for output_id, name in expected.items():
        entry = classify(output_id)
        assert entry is not None and entry.name == name, output_id
    assert classify("assessment:tac") is None
    assert classify("size.U-HEAT.weight") is None
    assert study_name("tac") == "assessment:tac"


def test_the_defaults_table_states_each_default_once_and_u_and_dt_min_have_none() -> None:
    assert DEFAULTS["drum_residence_time"].value == 300.0
    assert DEFAULTS["operation.discount_rate"].value == 0.08
    assert all(entry.text and entry.section for entry in DEFAULTS.values())
    assert set(REQUIRED) == {"U", "dT_min"}
    assert not {"U", "dT_min"} & set(DEFAULTS)


# -- the selection rules (§4.3.2) ------------------------------------------------------------------


def test_the_size_rule_takes_the_smallest_n_and_ties_select_n() -> None:
    assert select_size(10.0, 1.0, 10.0) == "units:1"
    assert select_size(20.0, 1.0, 10.0) == "units:2"
    assert select_size(20.000000000000004, 1.0, 10.0) == "units:3"
    assert select_size(0.5, 1.0, 10.0) == "floor"
    assert select_size(1.0, 1.0, 10.0) == "units:1"
    with pytest.raises(ValueError, match="2 S_min"):
        select_size(1.0, 1.0, 1.5)
    assert select_piece(2.0, [(0.0, 2.0), (2.0, 5.0)]) == 1
    assert select_piece(5.0, [(0.0, 2.0), (2.0, 5.0)]) == 1
    assert select_argmax([1.0, 3.0, 3.0]) == 1


def test_the_regime_signature_is_the_canonical_json_of_the_sorted_choices() -> None:
    regime = Regime({"b.size": "units:2", "a.service": "heating"})
    assert regime.signature == '{"a.service":"heating","b.size":"units:2"}'
    assert regime.sha256 == document_sha256({"b.size": "units:2", "a.service": "heating"})


# -- A4: twin against the float reference ----------------------------------------------------------


def test_a4_the_twin_reproduces_the_reference_within_1e_13() -> None:
    p = program(mid_toy())
    _, host, x = solved()
    reference = values_of(p, x)
    for symbolic in ((), (K,), (K, CF), ("U-HEAT.T_spec", K)):
        linear = p.linearize(x, {}, p.output_ids, symbolic)
        assert isinstance(linear, Linearization)
        for name in p.output_ids:
            assert abs(linear.values[name] - reference[name]) <= 1e-13 * max(
                1.0, abs(reference[name])
            )
    # The hand formulas (the float path is the builder; the expectation is written out here).
    size = x[X1] * x[X2]
    assert reference["size.TOY.area"] == size
    assert reference["size.TOY.volume"] == math.exp(0.3) * x[X1]
    assert math.isclose(
        reference["capex.purchased.TOY"], 1.5 * math.exp(2.0) * size**EXPONENT, rel_tol=1e-14
    )


# -- A5: the gradient oracle -----------------------------------------------------------------------


def _fd(p: AssessmentProgram, x: Mapping[str, float], name: str, h: float) -> dict[str, float]:
    plus, minus = dict(x), dict(x)
    plus[name] += h
    minus[name] -= h
    up, down = values_of(p, plus), values_of(p, minus)
    return {out: (up[out] - down[out]) / (2.0 * h) for out in p.output_ids}


def _dense(linear: Linearization) -> dict[tuple[str, str], float]:
    matrix, entries = linear.d_dx, {}
    for j, col in enumerate(matrix.col_ids):
        for k in range(matrix.indptr[j], matrix.indptr[j + 1]):
            entries[(matrix.row_ids[matrix.indices[k]], col)] = matrix.data[k]
    return entries


def test_a5_every_stored_nonzero_and_twenty_structural_zeros_match_central_differences() -> None:
    p = program(mid_toy())
    _, host, x = solved()
    linear = p.linearize(x, {}, p.output_ids)
    assert isinstance(linear, Linearization)
    stored = _dense(linear)
    assert {col for _, col in stored} == {X1, X2}
    reference = values_of(p, x)
    zeros = [(r, c) for r in p.output_ids for c in host.variable_ids if (r, c) not in stored]
    seeded = random.Random(20261027).sample(zeros, 20)
    for row, col in [*stored, *seeded]:
        scale = 1.0  # S_x,j: the toy's columns are far from zero, so max(|x_j|, S_x,j) = |x_j|
        h = 1e-6 * max(abs(x[col]), scale)
        fd = _fd(p, x, col, h)[row]
        exact = stored.get((row, col), 0.0)
        bound = 1e-6 * max(abs(exact), abs(reference[row]) / scale) + 1e-12 / scale
        assert abs(exact - fd) <= bound, (row, col, exact, fd)
    # θ: ∂ size.TOY.volume/∂θ_k = exp(θ_k) x₁ exactly as written.
    with_theta = p.linearize(x, {}, ["size.TOY.volume"], (K,))
    assert isinstance(with_theta, Linearization)
    assert with_theta.d_dp.data == pytest.approx((math.exp(0.3) * x[X1],), rel=1e-15)


# -- A6, A7: selection and holding -----------------------------------------------------------------


def test_a6_selection_is_deterministic_and_a_held_regime_evaluates_bitwise_equal() -> None:
    _, _, x = solved()
    selected = program(mid_toy())
    assert selected.select(x).signature == selected.select(x).signature == selected.regime.signature
    held = program(mid_toy(), regime=selected.regime)
    assert dict(values_of(held, x)) == dict(values_of(selected, x))
    assert held.label == selected.label


def test_a7_admissibility_holds_at_selection_and_two_s_max_selects_two_units() -> None:
    _, _, x = solved()
    size = size_at(x)
    for toy, expected in (
        (Toy(size / 8.0, size / 2.0), "units:2"),  # S = 2·S_max exactly
        (Toy(size / 8.0, size / 2.5), "units:3"),
        (Toy(size * 2.0, size * 5.0), "floor"),
        (mid_toy(), "units:1"),
    ):
        p = program(toy)
        assert p.regime.entries == {"TOY.size": expected}
        values = values_of(p, x)
        assert all(values[name] >= 0.0 for name in p.admissibility_ids), expected
    two = values_of(program(Toy(size / 8.0, size / 2.0)), x)
    assert two["adm.TOY.size.max"] == 0.0


def test_a17_a18_the_held_size_formulas_and_the_floor_has_an_empty_row() -> None:
    _, _, x = solved()
    size = size_at(x)
    three = values_of(program(Toy(size / 8.0, size / 2.5)), x)
    assert three["capex.purchased.TOY"] == 1.5 * math.exp(2.0) * 3 * math.exp(
        EXPONENT * math.log(size / 3)
    )
    floor_toy = Toy(size * 2.0, size * 5.0)
    floor = program(floor_toy)
    assert values_of(floor, x)["capex.purchased.TOY"] == 1.5 * math.exp(2.0) * math.exp(
        EXPONENT * math.log(size * 2.0)
    )
    linear = floor.linearize(x, {}, ["capex.purchased.TOY"])
    assert isinstance(linear, Linearization)
    assert linear.d_dx.data == ()


def test_holding_keeps_a_choice_within_tau_feas_and_releases_it_beyond() -> None:
    _, _, x = solved()
    size = size_at(x)
    toy = Toy(size / 8.0, size)  # units:1 with S = S_max
    held = program(toy).regime
    assert held.entries == {"TOY.size": "units:1"}
    # Within τ_feas: the scaled row (S_max − S)/S_max = −τ_feas/2 keeps units:1.
    near = {**x, X2: x[X2] * (1.0 + TAU_FEAS / 2.0)}
    kept = program(toy, near, regime=held)
    assert kept.regime == held
    assert program(toy).select(near) == held
    # Beyond it: the held regime is refused at that state, and select releases it to units:2.
    far = {**x, X2: x[X2] * (1.0 + 1e-6)}
    refused = build(toy, far, regime=held)
    assert isinstance(refused, Refusal) and refused.code == "ASSESSMENT_REGIME_INADMISSIBLE"
    assert program(toy).select(far).entries == {"TOY.size": "units:2"}
    unknown = build(toy, regime=Regime({"NOPE.size": "floor"}))
    assert isinstance(unknown, Refusal) and unknown.code == "ASSESSMENT_REGIME_INADMISSIBLE"


# -- A8: symbolic θ --------------------------------------------------------------------------------


def test_a8_every_continuous_theta_compiles_symbolic_and_a_structural_one_is_refused() -> None:
    p = program(mid_toy())
    continuous = [t for t, theta in p.theta.items() if not theta.structural]
    assert continuous == [K, CF]
    assert not isinstance(p.twin(continuous), Refusal)
    refused = p.twin([K, FM])
    assert isinstance(refused, Refusal) and refused.code == "ASSESSMENT_PARAMETER_STRUCTURAL"
    decided = p.evaluate(solved()[2], {K: 0.1})
    assert isinstance(decided, Refusal) and decided.code == "ASSESSMENT_PARAMETER_DECISION"


def test_a_decision_moves_the_value_through_the_pins_on_both_paths() -> None:
    """A host pin as a decision: the toy reads none, so its outputs are unchanged on both paths."""
    p = program(mid_toy())
    _, _, x = solved()
    moved = values_of(p, x, decisions={"U-HEAT.T_spec": 351.0})
    assert dict(moved) == dict(values_of(p, x))
    linear = p.linearize(x, {"U-HEAT.T_spec": 351.0}, p.output_ids, ("U-HEAT.T_spec",))
    assert isinstance(linear, Linearization)
    assert linear.d_dp.data == ()


def test_a_domain_failure_is_an_evaluation_error_never_nan() -> None:
    p = program(mid_toy())
    _, _, x = solved()
    with pytest.raises(TwinEvaluationError):
        p.evaluate({**x, X2: -x[X2]})


# -- §4.2.3: the memo ------------------------------------------------------------------------------


def _probe_spec(host: ProblemSpec, seen: list[tuple[int, tuple[int, ...]]]) -> ProblemSpec:
    def record(variables: Any, blocks: Any, pins: Mapping[str, Any], algebra: Any) -> Any:
        seen.append((id(variables), tuple(map(id, pins.values()))))
        return variables[X1] * 1.0

    rows = tuple(EquationSpec(f"probe.{i}", record, "algebraic") for i in range(3))
    return ProblemSpec(
        label="E01-probe",
        variable_ids=host.variable_ids,
        equations=rows,
        parameter_ids=host.parameter_ids,
        parameters=host.parameters,
    )


def test_the_twin_and_the_reference_pass_one_mapping_to_every_row_of_a_pass() -> None:
    _, host, x = solved()
    for run in ("twin", "reference"):
        seen: list[tuple[int, tuple[int, ...]]] = []
        spec = _probe_spec(host, seen)
        if run == "twin":
            compile_parametric_twin(spec, ("U-HEAT.T_spec",))
        else:
            row_values(spec, x)
        assert len(seen) == 3 and len(set(seen)) == 1, run


def test_the_memo_builds_each_output_once_per_pass() -> None:
    p = program(mid_toy())
    p.memo.builds = 0
    twin = p.twin((K,))
    assert not isinstance(twin, Refusal)
    assert p.memo.builds == len(p.output_ids)
    p.memo.builds = 0
    values_of(p, solved()[2])
    assert p.memo.builds == len(p.output_ids)
    # Disabled, `out` rebuilds: the area is built again by the capex row and each admissibility row.
    p.memo.enabled = False
    p.memo.builds = 0
    disabled = values_of(p, solved()[2])
    assert p.memo.builds > len(p.output_ids)
    p.memo.enabled = True
    assert dict(disabled) == dict(values_of(p, solved()[2]))


def test_the_functional_label_carries_both_identities() -> None:
    p = program(mid_toy())
    spec = load_assessment(DOCUMENT)
    assert p.label == f"ASM1-{spec.assessment_sha256[:12]}-{p.regime.sha256[:8]}"
    assert np.all([name in p.units for name in p.output_ids])
