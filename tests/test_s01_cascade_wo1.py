"""S01 WO-1 — the cascade's specification, declared rows, initializer and dormant answer.

Every expectation is a value of `docs/derivations/scripts/s01_reference.json` (the design lane's
50-digit generator, `s01_reference.py --check`), or a code of spec §5. Each test names the
assertion of `docs/derivations/S01-spec.md` §10 it closes: A01, A02, A03, A13, A14, A15, A16.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import replace
from typing import Any

import pytest
from conftest import REPO_ROOT

import openflowsheet.models.syn001.cascade as cascade_module
import openflowsheet.numerics.newton as newton_module
import openflowsheet.orchestrator.region as region_module
from openflowsheet.compile.reference import row_values
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.syn001.cascade import (
    BOTTOM,
    TOP,
    CascadeFailure,
    CascadeSpec,
    InletState,
    KremserInitial,
    SideFeed,
    declared_problem,
    declared_rows,
    dormant_answer,
    energy_precheck,
    inlet_stream,
    kremser_initial,
    liquid_id,
    liquid_total_id,
    mixed_id,
    regime_form,
    stage_duty_id,
    stage_pressure_id,
    stage_temperature_id,
    validate,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.saturation_band import BandTemperature
from openflowsheet.thermo.syn001 import Syn001Provider

REFERENCE_PATH = REPO_ROOT / "docs" / "derivations" / "scripts" / "s01_reference.json"
#: The reference this module was written against; a re-emitted reference must be re-read here.
REFERENCE_SHA256 = "4c1a24f68a2beccdfc000af699bb342bf0a200bd7ecaee989934302ef7d81930"
REFERENCE: dict[str, Any] = json.loads(REFERENCE_PATH.read_bytes())

UNIT = "S01"
COMPONENTS = ("A", "B", "C")
PROVIDER = Syn001Provider()
CONTEXT = EvaluationContext(model_version="S01-WO1@" + "0" * 64, constants_sha256="0" * 64)
CASES = ("C1", "C2", "C3", "C4", "C5")
REGIMES = ("TWO_PHASE", "LIQUID", "VAPOR", "ZERO_FLOW")


def _inlet(record: dict[str, Any]) -> InletState:
    return InletState(
        n=tuple(float(a) for a in record["n"]),
        temperature=float(record["T"]),
        pressure=float(record["P"]),
        phase=record["phase"],
    )


def _spec(record: dict[str, Any]) -> CascadeSpec:
    """A reference case as a `CascadeSpec`: inlets are `top`, `bottom`, then side feeds."""
    inlets = record["inlets"]
    count = record["N"]
    assert inlets[0]["stage"] == 1 and inlets[1]["stage"] == count
    return CascadeSpec(
        unit_id=UNIT,
        stage_count=count,
        pressures=tuple(float(p) for p in record["P"]),
        duties=tuple(float(q) for q in record["Q"]),
        top=_inlet(inlets[0]),
        bottom=_inlet(inlets[1]),
        sides=tuple(
            SideFeed(f"side{k}", side["stage"], _inlet(side)) for k, side in enumerate(inlets[2:])
        ),
    )


def _close(actual: float, expected: str, rel: float, absolute: float = 0.0) -> bool:
    target = float(expected)
    return abs(actual - target) <= rel * abs(target) + absolute


def test_the_reference_is_the_registered_one() -> None:
    assert hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest() == REFERENCE_SHA256


# -- A01 -----------------------------------------------------------------------------------------

ROW_ID = re.compile(
    rf"^{UNIT}:(stage:[1-9][0-9]*:(mix|mole|eq):[ABC]|stage:[1-9][0-9]*:(Ldef|Vdef|energy|P|Q)"
    rf"|inlet:[A-Za-z0-9_]+:(n:[ABC]|T|P))$"
)


@pytest.mark.parametrize("case", CASES)
def test_a01_declared_counts_and_ids(case: str) -> None:
    """A01: columns = rows = `ref.dof`, `2N + n_in(C + 2)` specifications, unique ids."""
    expected = REFERENCE["dof"][case]
    spec = _spec(REFERENCE["cases"][case])
    rows = declared_rows(spec, PROVIDER, CONTEXT)
    row_ids = [equation.equation_id for equation in rows.equations]
    assert len(rows.variable_ids) == expected["variables"]
    assert len(row_ids) == expected["rows"]
    specifications = [name for name in row_ids if re.search(r":(P|Q)$|:inlet:", name) is not None]
    assert len(specifications) == expected["specifications"]
    assert len(rows.variable_ids) - (len(row_ids) - len(specifications)) == len(specifications)
    assert len(set(row_ids)) == len(row_ids)
    assert len(set(rows.variable_ids)) == len(rows.variable_ids)
    assert all(ROW_ID.match(name) for name in row_ids), [
        name for name in row_ids if not ROW_ID.match(name)
    ]
    # Every row has its kind, every column its kind; the problem passes ProblemSpec.validate.
    assert set(rows.row_kinds) == set(row_ids)
    assert set(rows.variable_kinds) == set(rows.variable_ids)
    declared_problem(rows)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("regime", REGIMES)
def test_a01_each_regime_pins_as_many_columns_as_it_drops_rows(case: str, regime: str) -> None:
    """A01: per regime, pinned = dropped = `ref.dof.per_regime_pinned_dropped`, all declared."""
    pinned, dropped = REFERENCE["dof"]["per_regime_pinned_dropped"][regime]
    spec = _spec(REFERENCE["cases"][case])
    rows = declared_rows(spec, PROVIDER, CONTEXT)
    row_ids = {equation.equation_id for equation in rows.equations}
    for stage in range(1, spec.stage_count + 1):
        form = regime_form(spec, stage, regime)  # type: ignore[arg-type]
        assert (len(form.pinned), len(form.dropped)) == (pinned, dropped)
        assert set(form.pinned) <= set(rows.variable_ids)
        assert set(form.dropped) <= row_ids
        if regime == "ZERO_FLOW":
            assert form.swapped == f"{UNIT}:stage:{stage}:energy" and form.swapped in row_ids
            assert form.label is not None
            label_row, temperature, label = form.label
            assert temperature == stage_temperature_id(UNIT, stage)
            assert label == (
                temperature_id(inlet_stream(UNIT, TOP))
                if stage == 1
                else stage_temperature_id(UNIT, stage - 1)
            )
            assert label_row not in row_ids
        else:
            assert form.swapped == "" and form.label is None


# -- A02 -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("entry", sorted(REFERENCE["kremser"]))
def test_a02_the_initializer_reaches_the_kremser_closed_form(entry: str) -> None:
    """A02: with K injected stage-independent, the public initializer's `l` is Kremser's."""
    record = REFERENCE["kremser"][entry]
    count = len(record["l"])
    k = tuple(float(a) for a in record["K"])
    spec = CascadeSpec(
        unit_id=UNIT,
        stage_count=count,
        pressures=(1.0e5,) * count,
        duties=(0.0,) * count,
        top=InletState(tuple(float(a) for a in record["l_top"]), 330.0, 1.0e5, "LIQUID"),
        bottom=InletState(tuple(float(a) for a in record["v_bot"]), 380.0, 1.0e5, "VAPOR"),
    )
    assert validate(spec, PROVIDER, CONTEXT) is None
    initial = kremser_initial(spec, PROVIDER, CONTEXT, k_values=lambda t, p: k)
    assert isinstance(initial, KremserInitial)
    # The CMO totals are the registered L and V: S_i = K_i V / L.
    assert all(_close(a, record["L"], 1e-15) for a in initial.liquid_cmo)
    assert all(_close(a, record["V"], 1e-15) for a in initial.vapor_cmo)
    for j in range(count):
        for i in range(3):
            assert _close(initial.liquid[j][i], record["l"][j][i], 1e-12), (j, i)


# -- A03 -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_a03_the_initializer_on_the_registered_cases(case: str) -> None:
    """A03: `β̄`, `T̄` (abs 1e-8 K), `L_cmo`, `V_cmo`, `l`, `v` (rel 1e-10) against `ref`."""
    record = REFERENCE["cases"][case]
    expected = record["initializer"]
    spec = _spec(record)
    initial = kremser_initial(spec, PROVIDER, CONTEXT)
    assert isinstance(initial, KremserInitial)
    assert all(_close(a, b, 1e-10) for a, b in zip(initial.z, expected["z"], strict=True))
    assert _close(initial.beta, expected["beta"], 1e-10)
    assert _close(initial.beta_clamped, expected["beta_clamped"], 1e-10)
    assert _close(initial.pbar, expected["Pbar"], 1e-12)
    assert _close(initial.tbar, expected["Tbar"], 0.0, 1e-8)
    for actual, wanted in ((initial.liquid_cmo, "L_cmo"), (initial.vapor_cmo, "V_cmo")):
        assert all(_close(a, b, 1e-10) for a, b in zip(actual, expected[wanted], strict=True))
    for j in range(spec.stage_count):
        for i in range(3):
            assert _close(initial.liquid[j][i], expected["l"][j][i], 1e-10), ("l", j, i)
            assert _close(initial.vapor[j][i], expected["v"][j][i], 1e-10), ("v", j, i)
    # x_K is a full state of the declared rows: §6.5's last step. T_j = T̄, P_j = P_j*, the totals
    # are the sums, and mix, Ldef, Vdef and energy hold there by construction (to rounding).
    state = initial.state
    rows = declared_problem(declared_rows(spec, PROVIDER, CONTEXT))
    assert tuple(state) == rows.variable_ids
    for stage in range(1, spec.stage_count + 1):
        assert state[stage_temperature_id(UNIT, stage)] == initial.tbar
        assert state[stage_pressure_id(UNIT, stage)] == spec.pressures[stage - 1]
        assert state[liquid_id(UNIT, stage, "A")] == initial.liquid[stage - 1][0]
        assert state[vapor_id(UNIT, stage, "C")] == initial.vapor[stage - 1][2]
    residual = row_values(rows, state)
    for name, value in residual.items():
        if re.search(r":mix:|:P$|:inlet:", name):
            assert value == 0.0, (name, value)
        elif re.search(r":Ldef$|:Vdef$", name):
            # `L - l_A - l_B - l_C` against `sum(l)`: the two orders differ by rounding only.
            assert abs(value) <= 1e-15, (name, value)
        elif name.endswith(":energy"):
            assert abs(value) <= 1e-10, (name, value)


def test_a03_tbar_outside_the_domain_is_a_typed_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec §6.3: `T̄` outside the domain ends `INITIALIZATION_FAILED`, never a clamped guess.

    SYN-001 cannot reach this branch (its band temperature lies in about [298, 428] K for every
    composition and pressure in the domain), so the band's answer is stubbed: this checks the
    mapping of `below` and `above` to the typed failure, nothing about the provider."""
    for position in ("below", "above"):
        monkeypatch.setattr(
            cascade_module,
            "band_temperature",
            lambda *args, position=position, **kwargs: BandTemperature(position),
        )
        failure = kremser_initial(C2, PROVIDER, CONTEXT)
        assert isinstance(failure, CascadeFailure)
        assert (failure.outcome, failure.cause) == (
            "INITIALIZATION_FAILED",
            "initialization_failed(s01-kremser-cmo-v1, tbar_outside_domain)",
        )


# -- A13, A14 ------------------------------------------------------------------------------------

FLOW_COLUMN = re.compile(r"\.(l|v|m|n)\.[ABC]$|\.(L|V)$")


def _no_newton(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("spec §4.6 answers without a Newton solve")

    monkeypatch.setattr(region_module, "solve_region", refuse)
    monkeypatch.setattr(newton_module, "solve_newton", refuse)


def _check_dormant_state(name: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    record = REFERENCE["dormant"][name]
    spec = _spec(record)
    assert validate(spec, PROVIDER, CONTEXT) is None
    _no_newton(monkeypatch)
    answer = dormant_answer(spec, PROVIDER, CONTEXT)
    assert answer.newton_iterations == 0
    assert list(answer.signature) == record["signature"]
    for stage_record in record["stages"]:
        stage = stage_record["stage"]
        assert stage_record["regime"] == "ZERO_FLOW"
        assert answer.state[stage_temperature_id(UNIT, stage)] == float(stage_record["T"])
        assert answer.state[stage_pressure_id(UNIT, stage)] == float(stage_record["P"])
        assert answer.state[stage_duty_id(UNIT, stage)] == float(stage_record["Q"])
        label = stage_record["T_label"]
        assert answer.labels[stage - 1] == (
            temperature_id(inlet_stream(UNIT, TOP))
            if label == "T_top"
            else stage_temperature_id(UNIT, int(label.removeprefix("T_")))
        )
        for i, component in enumerate(COMPONENTS):
            for column, key in (
                (liquid_id(UNIT, stage, component), "l"),
                (vapor_id(UNIT, stage, component), "v"),
                (mixed_id(UNIT, stage, component), "m"),
            ):
                assert answer.state[column] == float(stage_record[key][i])
        assert answer.state[liquid_total_id(UNIT, stage)] == float(stage_record["L"])
        assert answer.state[vapor_total_id(UNIT, stage)] == float(stage_record["V"])
    # The label chain is T_top's 330 K, not the vapour inlet's 380 K.
    assert answer.state[temperature_id(inlet_stream(UNIT, BOTTOM))] == 380.0
    assert {answer.state[stage_temperature_id(UNIT, j)] for j in (1, 2, 3)} == {330.0}
    # ADR 0001 D3.1: every flow is +0.0, the sign bit checked.
    flows = [column for column in answer.state if FLOW_COLUMN.search(column)]
    assert len(flows) == 3 * (3 * 3 + 2) + 2 * 3
    for column in flows:
        value = answer.state[column]
        assert value == 0.0 and math.copysign(1.0, value) == 1.0, column
    # Every row of the ZERO_FLOW system (mix, label, P, Q, inlet rows) is exactly zero.
    assert len(answer.residuals) == 28
    assert all(value == 0.0 for value in answer.residuals.values()), answer.residuals
    assert [float(a) for a in record["swapped_energy"]] == list(answer.swapped_energy)
    return answer, record


def test_a13_every_inlet_dormant_converges_in_closed_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A13: D1 — `CONVERGED`, `ZERO_FLOW` ×3, `T_j = 330` K by the label chain, flows `+0.0`."""
    answer, record = _check_dormant_state("D1", monkeypatch)
    assert answer.outcome == record["outcome"] == "CONVERGED"
    assert answer.cause is record["cause"] is None


def test_a14_a_duty_into_a_dormant_stage_is_a_specification_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A14: D2 — `SPECIFICATION_CONFLICT`, `zero_flow_conflict(<U>:stage:2:energy)`,
    swapped energy `(0, 50, 0)` W."""
    answer, record = _check_dormant_state("D2", monkeypatch)
    assert answer.outcome == record["outcome"] == "SPECIFICATION_CONFLICT"
    assert answer.cause == record["cause"].replace("<cascade>", UNIT)
    assert answer.cause == f"zero_flow_conflict({UNIT}:stage:2:energy)"
    assert answer.swapped_energy == (0.0, 50.0, 0.0)


# -- A15, A16 ------------------------------------------------------------------------------------

C2 = _spec(REFERENCE["cases"]["C2"])
SIDE = InletState((0.2, 0.5, 0.3), 340.0, 1.0e5, "LIQUID")
NAN = float("nan")


def _with_top(**changes: Any) -> CascadeSpec:
    return replace(C2, top=replace(C2.top, **changes))


def _with_bottom(**changes: Any) -> CascadeSpec:
    return replace(C2, bottom=replace(C2.bottom, **changes))


REFUSALS: dict[str, tuple[CascadeSpec, str, str]] = {
    "R1-zero": (replace(C2, stage_count=0), "INVALID_SPECIFICATION", "invalid_spec(stage_count)"),
    "R1-negative": (
        replace(C2, stage_count=-3),
        "INVALID_SPECIFICATION",
        "invalid_spec(stage_count)",
    ),
    "R1-float": (
        replace(C2, stage_count=3.0),  # type: ignore[arg-type]
        "INVALID_SPECIFICATION",
        "invalid_spec(stage_count)",
    ),
    "R1-bool": (
        replace(C2, stage_count=True, pressures=(1e5,), duties=(0.0,)),
        "INVALID_SPECIFICATION",
        "invalid_spec(stage_count)",
    ),
    "R2-negative": (
        _with_top(n=(0.2, -0.3, 0.5)),
        "INVALID_SPECIFICATION",
        "invalid_spec(inlet_flow:top)",
    ),
    "R2-nan": (
        _with_bottom(n=(0.5, NAN, 0.2)),
        "INVALID_SPECIFICATION",
        "invalid_spec(inlet_flow:bottom)",
    ),
    "R2-inf": (
        replace(C2, sides=(SideFeed("feed", 2, replace(SIDE, n=(math.inf, 0.0, 0.0))),)),
        "INVALID_SPECIFICATION",
        "invalid_spec(inlet_flow:feed)",
    ),
    "R3-inlet-T": (
        _with_top(temperature=279.0),
        "INVALID_SPECIFICATION",
        f"invalid_spec(domain:{temperature_id(inlet_stream(UNIT, TOP))})",
    ),
    "R3-inlet-T-nan": (
        _with_bottom(temperature=NAN),
        "INVALID_SPECIFICATION",
        f"invalid_spec(domain:{temperature_id(inlet_stream(UNIT, BOTTOM))})",
    ),
    "R3-inlet-P": (
        _with_bottom(pressure=2.5e5),
        "INVALID_SPECIFICATION",
        f"invalid_spec(domain:{pressure_id(inlet_stream(UNIT, BOTTOM))})",
    ),
    "R3-stage-P": (
        replace(C2, pressures=(1.0e5, 4.0e4, 1.0e5)),
        "INVALID_SPECIFICATION",
        f"invalid_spec(domain:{stage_pressure_id(UNIT, 2)})",
    ),
    "R4-below": (
        replace(C2, sides=(SideFeed("feed", 0, SIDE),)),
        "INVALID_SPECIFICATION",
        "invalid_spec(side_feed_stage:feed)",
    ),
    "R4-above": (
        replace(C2, sides=(SideFeed("feed", 4, SIDE),)),
        "INVALID_SPECIFICATION",
        "invalid_spec(side_feed_stage:feed)",
    ),
    "R4-twice": (
        replace(C2, sides=(SideFeed("first", 2, SIDE), SideFeed("second", 2, SIDE))),
        "INVALID_SPECIFICATION",
        "invalid_spec(side_feed_stage:second)",
    ),
    "R5-liquid": (
        _with_top(temperature=380.0),
        "INVALID_SPECIFICATION",
        "inadmissible_inlet(top, LIQUID)",
    ),
    "R5-vapour": (
        _with_bottom(temperature=330.0),
        "INVALID_SPECIFICATION",
        "inadmissible_inlet(bottom, VAPOR)",
    ),
    "R6-top": (
        _with_top(phase="TWO_PHASE"),
        "CAPABILITY_UNAVAILABLE",
        "unsupported(two_phase_inlet:top)",
    ),
    "R6-side": (
        replace(C2, sides=(SideFeed("feed", 2, replace(SIDE, phase="VAPOR_LIQUID")),)),
        "CAPABILITY_UNAVAILABLE",
        "unsupported(two_phase_inlet:feed)",
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_a15_refusals(name: str) -> None:
    """A15: R1–R6, each with its §5 category and code, before any row is built."""
    spec, outcome, cause = REFUSALS[name]
    failure = validate(spec, PROVIDER, CONTEXT)
    assert isinstance(failure, CascadeFailure)
    assert (failure.outcome, failure.cause) == (outcome, cause)


def test_a15_the_r5_and_r6_boundaries() -> None:
    """A15: R5 judges flowing inlets only (a dormant inlet has no phase, ADR 0001 D3.1), and an
    in-range side feed passes R4."""
    dormant_bottom = _with_bottom(n=(0.0, 0.0, 0.0), temperature=330.0)
    assert validate(dormant_bottom, PROVIDER, CONTEXT) is None
    assert validate(replace(C2, sides=(SideFeed("feed", 2, SIDE),)), PROVIDER, CONTEXT) is None


@pytest.mark.parametrize(
    "record",
    [
        *(REFERENCE["cases"][case] for case in CASES),
        REFERENCE["dormant"]["D1"],
        REFERENCE["dormant"]["D2"],
        REFERENCE["partial_dormancy"],
    ],
    ids=[*CASES, "D1", "D2", "A19"],
)
def test_a15_a16_every_registered_case_passes_section_5(record: dict[str, Any]) -> None:
    """A15/A16: C1–C5, D1, D2 and the A19 probe pass §5 (generator claims R5 and R7 for A19)."""
    assert validate(_spec(record), PROVIDER, CONTEXT) is None


@pytest.mark.parametrize("duty", REFERENCE["precheck"]["Q_refused"])
def test_a16_the_energy_precheck_refuses_both_signs(duty: str) -> None:
    """A16: R7 — C1 with `Q_1 = ±200 kW` is `infeasible_spec(energy_outside_domain)`."""
    spec = replace(_spec(REFERENCE["cases"]["C1"]), duties=(float(duty),))
    failure = validate(spec, PROVIDER, CONTEXT)
    assert isinstance(failure, CascadeFailure)
    assert (failure.outcome, failure.cause) == (
        "INVALID_SPECIFICATION",
        "infeasible_spec(energy_outside_domain)",
    )


def test_a16_the_energy_precheck_bounds_are_the_registered_ones() -> None:
    """A16: C1 as registered passes, and its `H_in`, `H_lo`, `H_hi` are `ref.precheck`'s."""
    expected = REFERENCE["precheck"]
    spec = _spec(REFERENCE["cases"][expected["case"]])
    assert validate(spec, PROVIDER, CONTEXT) is None
    bounds = energy_precheck(spec, PROVIDER, CONTEXT)
    assert _close(bounds.inflow, expected["H_in"], 1e-12, 1e-9)
    assert bounds.target == bounds.inflow + sum(spec.duties)
    assert _close(bounds.lower, expected["H_lo"], 1e-12, 1e-9)
    assert _close(bounds.upper, expected["H_hi"], 1e-12, 1e-9)
    assert bounds.lower < bounds.target < bounds.upper


def test_the_inlet_columns_are_the_feed_pattern() -> None:
    """Spec §2: an inlet's `C + 2` columns are fixed by `C + 2` specification rows."""
    rows = declared_rows(C2, PROVIDER, CONTEXT)
    stream = inlet_stream(UNIT, TOP)
    assert {flow_id(stream, c) for c in COMPONENTS} <= set(rows.variable_ids)
    assert rows.parameters[f"{temperature_id(stream)}*"] == 330.0
    assert rows.parameters[f"{pressure_id(stream)}*"] == 1.0e5
