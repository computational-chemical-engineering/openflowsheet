"""S02 WO-1 — the column's specification, refusals, declared rows and initializer.

Every expectation is a value of `docs/derivations/scripts/s02_reference.json` (the design lane's
50-digit generator, `s02_reference.py --check`), a code of `docs/derivations/S02-spec.md` §5, or
arithmetic done here independently of the row builders. Each test names the assertion of the
spec's §10 it closes: A01, A02, A03, A04.
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

import openflowsheet.models.syn001.column as column_module
from openflowsheet.compile.reference import row_values
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import flow_id, temperature_id
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    InletState,
    SideFeed,
    declared_problem,
    inlet_stream,
    liquid_id,
    liquid_total_id,
    stage_duty_id,
    stage_pressure_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.column import (
    ColumnSpec,
    EndSpecification,
    ProfileInitial,
    ProfileLabel,
    declared_rows,
    distillate_id,
    distillate_total_id,
    profile_initial,
    ratio_parameter,
    reflux_fraction_id,
    reflux_id,
    regime_form,
    validate,
)
from openflowsheet.models.syn001.saturation_band import BandTemperature
from openflowsheet.models.syn001.tp_state import enthalpy_flow
from openflowsheet.thermo import PropertyRequest, StreamState
from openflowsheet.thermo.syn001 import Syn001Provider

REFERENCE_PATH = REPO_ROOT / "docs" / "derivations" / "scripts" / "s02_reference.json"
#: The reference this module was written against; a re-emitted reference must be re-read here.
REFERENCE_SHA256 = "62296289aee9c95facaaa36ffefd05807d437645c5b6beeb0f70da62f18579a4"
REFERENCE: dict[str, Any] = json.loads(REFERENCE_PATH.read_bytes())

UNIT = "S02"
COMPONENTS = ("A", "B", "C")
PROVIDER = Syn001Provider()
CONTEXT = EvaluationContext(model_version="S02-WO1@" + "0" * 64, constants_sha256="0" * 64)
CASES = ("M1", "M2", "M3", "M4")
REGIMES = ("TWO_PHASE", "LIQUID", "VAPOR", "ZERO_FLOW")
FEED = (0.3, 0.4, 0.3)


def _pressures(count: int) -> tuple[float, ...]:
    """§9: `P_j* = 1.00 + 0.01 (j − 1)` bar."""
    return tuple(1.0e5 + 1.0e3 * j for j in range(count))


def _feed(temperature: float = 340.0, pressure: float = 1.04e5) -> SideFeed:
    return SideFeed("feed", 4, InletState(FEED, temperature, pressure, "LIQUID"))


#: §9's registered cases, transcribed from the spec's table (and the generator's `CASES`).
SPECS: dict[str, ColumnSpec] = {
    "M1": ColumnSpec(
        unit_id=UNIT,
        stage_count=7,
        pressures=_pressures(7),
        duties=(None, 0.0, 0.0, 0.0, 0.0, 0.0, None),
        condenser="partial",
        reboiler="partial",
        condenser_spec=EndSpecification("reflux_ratio", 2.0),
        reboiler_spec=EndSpecification("boilup_ratio", 1.5),
        sides=(_feed(),),
    ),
    "M2": ColumnSpec(
        unit_id=UNIT,
        stage_count=7,
        pressures=_pressures(7),
        duties=(None, 0.0, 0.0, 0.0, 0.0, 0.0, None),
        condenser="total",
        reboiler="partial",
        condenser_spec=EndSpecification("reflux_ratio", 1.5),
        reboiler_spec=EndSpecification("bottoms_rate", 0.55),
        sides=(_feed(),),
    ),
    "M3": ColumnSpec(
        unit_id=UNIT,
        stage_count=5,
        pressures=_pressures(5),
        duties=(0.0, 0.0, 0.0, 0.0, None),
        reboiler="partial",
        reboiler_spec=EndSpecification("duty", 30000.0),
        top=InletState(FEED, 300.0, 1.0e5, "LIQUID"),
    ),
    "M4": ColumnSpec(
        unit_id=UNIT,
        stage_count=5,
        pressures=_pressures(5),
        duties=(None, 0.0, 0.0, 0.0, 0.0),
        condenser="partial",
        condenser_spec=EndSpecification("distillate_rate", 0.5),
        bottom=InletState(FEED, 385.0, 1.04e5, "VAPOR"),
    ),
}
#: §9 P1: M3 at `Q_r* = 3 kW`.
SPECS["P1"] = replace(
    SPECS["M3"],
    reboiler_spec=EndSpecification("duty", float(REFERENCE["phase_case"]["P1"]["Q_reboiler"])),
)


def _close(actual: float, expected: str | float, rel: float, absolute: float = 0.0) -> bool:
    target = float(expected)
    return abs(actual - target) <= rel * abs(target) + absolute


def _variant(case: str, variant: str) -> ColumnSpec:
    """`ref.variants.<case>.<variant>` as a specification of the registered case."""
    record = REFERENCE["variants"][case][variant]["spec"]
    return replace(
        SPECS[case],
        condenser_spec=EndSpecification(record["condenser"][0], float(record["condenser"][1])),
        reboiler_spec=EndSpecification(record["reboiler"][0], float(record["reboiler"][1])),
    )


def test_the_reference_is_the_registered_one() -> None:
    assert hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest() == REFERENCE_SHA256


def test_the_transcribed_cases_are_the_generators() -> None:
    """The specifications above against what `ref` records of them: N, the signature length and
    the end specifications of `spec_values`."""
    for case in CASES:
        spec = SPECS[case]
        record = REFERENCE["cases"][case]
        assert len(record["signature"]) == spec.stage_count
        assert len(record["initializer"]["profile"]) == spec.stage_count
        values = record["spec_values"]
        for end, given in (("condenser", spec.condenser_spec), ("reboiler", spec.reboiler_spec)):
            if given is None:
                continue
            key = f"{end}_duty" if given.kind == "duty" else given.kind
            assert _close(given.value, values[key], 1e-15), (case, end)
    assert SPECS["P1"].stage_count == REFERENCE["phase_case"]["P1"]["N"]


# -- A01 -----------------------------------------------------------------------------------------

ROW_ID = re.compile(
    rf"^{UNIT}:(stage:[1-9][0-9]*:(mix|mole|eq|bal|split):[ABC]"
    rf"|stage:[1-9][0-9]*:(Ldef|Vdef|Ddef|bubble|energy|P|Q)"
    rf"|stage:[1-9][0-9]*:spec:(reflux_ratio|distillate_rate|boilup_ratio|bottoms_rate|duty)"
    rf"|inlet:[A-Za-z0-9_]+:(n:[ABC]|T|P))$"
)


@pytest.mark.parametrize("case", [*CASES, "P1"])
def test_a01_declared_counts_and_ids(case: str) -> None:
    """A01: columns = rows = `ref.dof` (P1 has M3's), unique well-formed ids, a kind for every row
    and for every column but `phi` (see the strict xfail below)."""
    expected = REFERENCE["dof"]["M3" if case == "P1" else case]
    spec = SPECS[case]
    rows = declared_rows(spec, PROVIDER, CONTEXT)
    row_ids = [equation.equation_id for equation in rows.equations]
    assert len(rows.variable_ids) == expected["columns"]
    assert len(row_ids) == expected["rows"]
    assert len(spec.equilibrium_stages()) == expected["equilibrium_stages"]
    assert len(spec.inlets()) == expected["inlets"]
    assert int(spec.total_condenser) == expected["total_condenser_block"]
    slots = [name for name in row_ids if ":spec:" in name]
    assert len(slots) == expected["column_specifications"]
    assert len(set(row_ids)) == len(row_ids)
    assert len(set(rows.variable_ids)) == len(rows.variable_ids)
    assert all(ROW_ID.match(name) for name in row_ids), [
        name for name in row_ids if not ROW_ID.match(name)
    ]
    assert set(rows.row_kinds) == set(row_ids)
    untyped = set(rows.variable_ids) - set(rows.variable_kinds)
    assert untyped == ({reflux_fraction_id(UNIT)} if spec.total_condenser else set())
    # Every stage carries exactly one slot row: S01's `Q` or a column specification (§2.1).
    for stage in range(1, spec.stage_count + 1):
        mine = [name for name in row_ids if re.match(rf"^{UNIT}:stage:{stage}:(Q|spec:.*)$", name)]
        assert len(mine) == 1, (stage, mine)
    declared_problem(rows)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Q-S02-WO1-1: spec §0 calls `phi`'s kind `dimensionless` 'an existing kind', but "
        "`compile.spec.QuantityKind` and `numerics.scaling.REGISTERED_NOMINALS` have no "
        "`dimensionless`; measured: `phi` has no declared kind (docs/S02_DECISIONS.md)"
    ),
)
def test_a01_phi_is_declared_dimensionless() -> None:
    """A01 / §2.2: the total condenser's `phi` column is of kind `dimensionless`."""
    rows = declared_rows(SPECS["M2"], PROVIDER, CONTEXT)
    assert rows.variable_kinds.get(reflux_fraction_id(UNIT)) == "dimensionless"  # type: ignore[comparison-overlap]


#: §2.1's slot rows of each case, `(stage, kind, row kind)`.
SLOTS: dict[str, tuple[tuple[int, str, str], ...]] = {
    "M1": ((1, "reflux_ratio", "molar_flow"), (7, "boilup_ratio", "molar_flow")),
    "M2": ((1, "reflux_ratio", "molar_flow"), (7, "bottoms_rate", "molar_flow")),
    "M3": ((5, "duty", "heat_rate"),),
    "M4": ((1, "distillate_rate", "molar_flow"),),
}


@pytest.mark.parametrize("case", CASES)
def test_a01_slot_rows_are_the_column_specifications(case: str) -> None:
    """A01 / §2.1: each end's slot row has its id, its kind and a pinned input; no `Q_j − Q_j*`
    remains at an end stage."""
    spec = SPECS[case]
    rows = declared_rows(spec, PROVIDER, CONTEXT)
    row_ids = {equation.equation_id for equation in rows.equations}
    for stage, kind, row_kind in SLOTS[case]:
        name = f"{UNIT}:stage:{stage}:spec:{kind}"
        assert name in row_ids and rows.row_kinds[name] == row_kind
        assert f"{UNIT}:stage:{stage}:Q" not in row_ids
    pinned = {
        "M1": {ratio_parameter(UNIT, 1, "reflux_ratio"): 2.0, f"{UNIT}.stage.7.boilup_ratio*": 1.5},
        "M2": {ratio_parameter(UNIT, 1, "reflux_ratio"): 1.5, f"{liquid_total_id(UNIT, 7)}*": 0.55},
        "M3": {f"{stage_duty_id(UNIT, 5)}*": 30000.0},
        "M4": {f"{vapor_total_id(UNIT, 1)}*": 0.5},
    }[case]
    for parameter, value in pinned.items():
        assert rows.parameters[parameter] == value


def _evaluate(spec: ColumnSpec, state: dict[str, float]) -> dict[str, float]:
    return row_values(declared_problem(declared_rows(spec, PROVIDER, CONTEXT)), state)


def _k(temperature: float, pressure: float) -> tuple[float, ...]:
    result = PROVIDER.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=(1.0, 1.0, 1.0), temperature=temperature, pressure=pressure),
            phase="LIQUID",
            properties=("lnK",),
        ),
        CONTEXT,
    )
    assert result.status == "ok"
    return tuple(math.exp(result.values[f"lnK_{c}"]) for c in COMPONENTS)


@pytest.mark.parametrize("case", ["M1", "M2", "M4"])
def test_a01_slot_and_condenser_rows_are_the_stated_expressions(case: str) -> None:
    """A01 / §2.1–§2.2: at a perturbed `x_K` each S02 row equals its §2 expression, formed here
    from the state with plain arithmetic, so a swapped argument or sign in a builder is caught."""
    spec = SPECS[case]
    initial = profile_initial(spec, PROVIDER, CONTEXT)
    assert isinstance(initial, ProfileInitial)
    state = dict(initial.state)
    # Move every flow off the initializer's relations, so no row vanishes by construction.
    for k, name in enumerate(sorted(state)):
        if re.search(r"\.(l|v|r|d)\.[ABC]$|\.(L|V|D|phi)$", name):
            state[name] *= 1.0 + 0.01 * (1 + k % 7)
    residual = _evaluate(spec, state)

    def at(name: str) -> float:
        return state[name]

    tol = 1e-12
    if case == "M1":
        expected = at(liquid_total_id(UNIT, 1)) - 2.0 * at(vapor_total_id(UNIT, 1))
        assert abs(residual[f"{UNIT}:stage:1:spec:reflux_ratio"] - expected) <= tol
        expected = at(vapor_total_id(UNIT, 7)) - 1.5 * at(liquid_total_id(UNIT, 7))
        assert abs(residual[f"{UNIT}:stage:7:spec:boilup_ratio"] - expected) <= tol
    if case == "M4":
        expected = at(vapor_total_id(UNIT, 1)) - 0.5
        assert abs(residual[f"{UNIT}:stage:1:spec:distillate_rate"] - expected) <= tol
    if case == "M2":
        r = [at(reflux_id(UNIT, c)) for c in COMPONENTS]
        d = [at(distillate_id(UNIT, c)) for c in COMPONENTS]
        v2 = [at(vapor_id(UNIT, 2, c)) for c in COMPONENTS]
        phi, big_d = at(reflux_fraction_id(UNIT)), at(distillate_total_id(UNIT))
        expected = sum(r) - 1.5 * big_d
        assert abs(residual[f"{UNIT}:stage:1:spec:reflux_ratio"] - expected) <= tol
        expected = at(liquid_total_id(UNIT, 7)) - 0.55
        assert abs(residual[f"{UNIT}:stage:7:spec:bottoms_rate"] - expected) <= tol
        for i, c in enumerate(COMPONENTS):
            assert abs(residual[f"{UNIT}:stage:1:bal:{c}"] - (v2[i] - r[i] - d[i])) <= tol
            assert abs(residual[f"{UNIT}:stage:1:split:{c}"] - (r[i] - phi * v2[i])) <= tol
        assert abs(residual[f"{UNIT}:stage:1:Ddef"] - (big_d - sum(d))) <= tol
        k = _k(at(stage_temperature_id(UNIT, 1)), at(stage_pressure_id(UNIT, 1)))
        expected = sum(k[i] * v2[i] for i in range(3)) - at(vapor_total_id(UNIT, 2))
        assert abs(residual[f"{UNIT}:stage:1:bubble"] - expected) <= tol
        # Stage 2 receives `r` from above, not an `l_1` (there is none).
        assert liquid_id(UNIT, 1, "A") not in state
        mix = f"{UNIT}:stage:2:mix:B"
        expected = r[1] + at(vapor_id(UNIT, 3, "B")) - at(f"{UNIT}.stage.2.m.B")
        assert abs(residual[mix] - expected) <= tol


def _hdot(flows: list[float], temperature: float, pressure: float, phase: str) -> float:
    status, value, message = enthalpy_flow(
        PROVIDER,
        StreamState(n=tuple(flows), temperature=temperature, pressure=pressure),
        phase,  # type: ignore[arg-type]
        COMPONENTS,
        CONTEXT,
    )
    assert status == "ok", message
    return value


@pytest.mark.parametrize("case", CASES)
def test_a01_energy_rows_read_the_stated_streams(case: str) -> None:
    """A01 / §2.2–§2.3: at a perturbed `x_K` every energy row equals `Q_j + Σ Ḣ_in − Σ Ḣ_out`
    formed here from the provider's enthalpies: stage 2 below a total condenser receives `r` at
    `(T_c, P_c)`, an end stage receives nothing from an absent inlet."""
    spec = SPECS[case]
    initial = profile_initial(spec, PROVIDER, CONTEXT)
    assert isinstance(initial, ProfileInitial)
    state = dict(initial.state)
    for k, name in enumerate(sorted(state)):
        if re.search(r"\.(l|v|r|d)\.[ABC]$|\.stage\.[0-9]+\.T$", name):
            state[name] *= 1.0 + 0.003 * (1 + k % 5)
    residual = _evaluate(spec, state)

    def flows(kind: str, stage: int) -> list[float]:
        return [state[f"{UNIT}.stage.{stage}.{kind}.{c}"] for c in COMPONENTS]

    def tp(stage: int) -> tuple[float, float]:
        return state[stage_temperature_id(UNIT, stage)], state[stage_pressure_id(UNIT, stage)]

    def inlet(port: str) -> float:
        stream = inlet_stream(UNIT, port)
        placed = next(i for i in spec.inlets() if i.port == port)
        return _hdot(
            [state[flow_id(stream, c)] for c in COMPONENTS],
            state[temperature_id(stream)],
            state[f"{stream}.P"],
            placed.state.phase,
        )

    count = spec.stage_count
    if spec.total_condenser:
        expected = (
            state[stage_duty_id(UNIT, 1)]
            + _hdot(flows("v", 2), *tp(2), "VAPOR")
            - _hdot(flows("r", 1), *tp(1), "LIQUID")
            - _hdot(flows("d", 1), *tp(1), "LIQUID")
        )
        assert abs(residual[f"{UNIT}:stage:1:energy"] - expected) <= 1e-8
    for stage in spec.equilibrium_stages():
        inflow = 0.0
        if stage == 1:
            inflow += inlet("top") if spec.top is not None else 0.0
        elif stage == 2 and spec.total_condenser:
            inflow += _hdot(flows("r", 1), *tp(1), "LIQUID")
        else:
            inflow += _hdot(flows("l", stage - 1), *tp(stage - 1), "LIQUID")
        if stage == count:
            inflow += inlet("bottom") if spec.bottom is not None else 0.0
        else:
            inflow += _hdot(flows("v", stage + 1), *tp(stage + 1), "VAPOR")
        inflow += sum(inlet(side.port) for side in spec.sides if side.stage == stage)
        expected = (
            state[stage_duty_id(UNIT, stage)]
            + inflow
            - _hdot(flows("v", stage), *tp(stage), "VAPOR")
            - _hdot(flows("l", stage), *tp(stage), "LIQUID")
        )
        assert abs(residual[f"{UNIT}:stage:{stage}:energy"] - expected) <= 1e-8, stage


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("regime", REGIMES)
def test_a01_each_regime_pins_as_many_columns_as_it_drops_rows(case: str, regime: str) -> None:
    """A01: per regime and equilibrium stage, pinned = dropped, all declared; the `ZERO_FLOW`
    label is §2.3's (a column, or the profile's `T_1⁰` without a `top` inlet)."""
    spec = SPECS[case]
    rows = declared_rows(spec, PROVIDER, CONTEXT)
    row_ids = {equation.equation_id for equation in rows.equations}
    for stage in spec.equilibrium_stages():
        form = regime_form(spec, stage, regime)  # type: ignore[arg-type]
        assert len(form.pinned) == len(form.dropped)
        assert set(form.pinned) <= set(rows.variable_ids)
        assert set(form.dropped) <= row_ids
        if regime != "ZERO_FLOW":
            assert form.swapped == "" and form.label is None
            continue
        assert form.swapped == f"{UNIT}:stage:{stage}:energy" and form.swapped in row_ids
        assert form.label is not None
        label_row, temperature, source = form.label
        assert temperature == stage_temperature_id(UNIT, stage) and label_row not in row_ids
        if stage > 1:
            # With a total condenser, stage 2's label is `T_c`, the column `<U>.stage.1.T`.
            assert source == stage_temperature_id(UNIT, stage - 1)
            assert source in rows.variable_ids
        elif spec.top is not None:
            assert source == temperature_id(inlet_stream(UNIT, "top"))
        else:
            assert source == ProfileLabel(1)
    if spec.total_condenser:
        with pytest.raises(ValueError, match="not an equilibrium stage"):
            regime_form(spec, 1, regime)  # type: ignore[arg-type]


def test_a01_the_new_builders_reject_malformed_input() -> None:
    from openflowsheet.models.rows import bubble_row, ratio_row

    with pytest.raises(ValueError):
        ratio_row((), "p", "b")
    with pytest.raises(ValueError):
        bubble_row(("a", "b"), ("k",), "N")


# -- A02 -----------------------------------------------------------------------------------------

M1, M2, M3, M4 = (SPECS[case] for case in CASES)
NAN = float("nan")
FEED_STREAM = inlet_stream(UNIT, "feed")


def _ratio(kind: str, value: float) -> EndSpecification:
    return EndSpecification(kind, value)


REFUSALS: dict[str, tuple[ColumnSpec, str, str]] = {
    # S01 R1–R7 applied to a column.
    "R1": (replace(M1, stage_count=0), "INVALID_SPECIFICATION", "invalid_spec(stage_count)"),
    "R2": (
        replace(
            M1,
            sides=(replace(_feed(), state=InletState((0.3, -0.4, 0.3), 340.0, 1.04e5, "LIQUID")),),
        ),
        "INVALID_SPECIFICATION",
        "invalid_spec(inlet_flow:feed)",
    ),
    "R3-inlet": (
        replace(M1, sides=(_feed(temperature=279.0),)),
        "INVALID_SPECIFICATION",
        f"invalid_spec(domain:{temperature_id(FEED_STREAM)})",
    ),
    "R3-stage": (
        replace(M1, pressures=(1.0e5, 1.01e5, 2.5e5, 2.6e5, 2.7e5, 2.8e5, 2.9e5)),
        "INVALID_SPECIFICATION",
        f"invalid_spec(domain:{stage_pressure_id(UNIT, 3)})",
    ),
    "R4": (
        replace(M1, sides=(replace(_feed(), stage=8),)),
        "INVALID_SPECIFICATION",
        "invalid_spec(side_feed_stage:feed)",
    ),
    "R6": (
        replace(M1, sides=(replace(_feed(), state=InletState(FEED, 340.0, 1.04e5, "TWO_PHASE")),)),
        "CAPABILITY_UNAVAILABLE",
        "unsupported(two_phase_inlet:feed)",
    ),
    "R7-low": (
        replace(M3, reboiler_spec=_ratio("duty", 1.0), duties=(-1.0e7, 0.0, 0.0, 0.0, None)),
        "INVALID_SPECIFICATION",
        "infeasible_spec(energy_outside_domain)",
    ),
    "R7-high": (
        replace(M3, reboiler_spec=_ratio("duty", 1.0e7)),
        "INVALID_SPECIFICATION",
        "infeasible_spec(energy_outside_domain)",
    ),
    "R7-duty-duty": (
        replace(_variant("M1", "duty+duty"), condenser_spec=_ratio("duty", -1.0e7)),
        "INVALID_SPECIFICATION",
        "infeasible_spec(energy_outside_domain)",
    ),
    # S1
    "S1-condenser": (
        replace(M1, condenser="subcooled"),
        "CAPABILITY_UNAVAILABLE",
        "unsupported(condenser:subcooled)",
    ),
    "S1-reboiler": (
        replace(M1, reboiler="total"),
        "CAPABILITY_UNAVAILABLE",
        "unsupported(reboiler:total)",
    ),
    # S2
    "S2-missing": (
        replace(M1, condenser_spec=None),
        "INVALID_SPECIFICATION",
        "invalid_spec(specification:condenser)",
    ),
    "S2-at-none-end": (
        replace(M3, condenser_spec=_ratio("duty", -1.0e3)),
        "INVALID_SPECIFICATION",
        "invalid_spec(specification:condenser)",
    ),
    "S2-wrong-end": (
        replace(M1, reboiler_spec=_ratio("reflux_ratio", 1.5)),
        "INVALID_SPECIFICATION",
        "invalid_spec(specification:reboiler)",
    ),
    "S2-not-offered": (
        replace(M1, condenser_spec=_ratio("purity", 0.95)),
        "CAPABILITY_UNAVAILABLE",
        "unsupported(specification:purity)",
    ),
    # S4
    "S4-reflux-ratio": (
        replace(M1, condenser_spec=_ratio("reflux_ratio", 0.0)),
        "INVALID_SPECIFICATION",
        "invalid_spec(reflux_ratio:condenser)",
    ),
    "S4-boilup-ratio": (
        replace(M1, reboiler_spec=_ratio("boilup_ratio", NAN)),
        "INVALID_SPECIFICATION",
        "invalid_spec(boilup_ratio:reboiler)",
    ),
    "S4-distillate-rate": (
        replace(M4, condenser_spec=_ratio("distillate_rate", -0.1)),
        "INVALID_SPECIFICATION",
        "invalid_spec(distillate_rate:condenser)",
    ),
    "S4-bottoms-rate": (
        replace(M2, reboiler_spec=_ratio("bottoms_rate", 0.0)),
        "INVALID_SPECIFICATION",
        "invalid_spec(bottoms_rate:reboiler)",
    ),
    "S4-condenser-duty": (
        replace(M1, condenser_spec=_ratio("duty", 0.0)),
        "INVALID_SPECIFICATION",
        "invalid_spec(duty:condenser)",
    ),
    "S4-reboiler-duty": (
        replace(M3, reboiler_spec=_ratio("duty", -1.0)),
        "INVALID_SPECIFICATION",
        "invalid_spec(duty:reboiler)",
    ),
    # S5
    "S5-distillate": (
        replace(M4, condenser_spec=_ratio("distillate_rate", 1.0)),
        "INVALID_SPECIFICATION",
        "infeasible_spec(distillate_rate_exceeds_feed)",
    ),
    "S5-bottoms": (
        replace(M2, reboiler_spec=_ratio("bottoms_rate", 1.2)),
        "INVALID_SPECIFICATION",
        "infeasible_spec(bottoms_rate_exceeds_feed)",
    ),
    # S6
    "S6-top-with-condenser": (
        replace(M1, top=InletState(FEED, 300.0, 1.0e5, "LIQUID")),
        "INVALID_SPECIFICATION",
        "invalid_spec(top_inlet)",
    ),
    "S6-no-top-without-condenser": (
        replace(M3, top=None, sides=(replace(_feed(), stage=2),)),
        "INVALID_SPECIFICATION",
        "invalid_spec(top_inlet)",
    ),
    "S6-bottom-with-reboiler": (
        replace(M1, bottom=InletState(FEED, 385.0, 1.06e5, "VAPOR")),
        "INVALID_SPECIFICATION",
        "invalid_spec(bottom_inlet)",
    ),
    "S6-no-bottom-without-reboiler": (
        replace(
            M4, bottom=None, sides=(SideFeed("feed", 3, InletState(FEED, 385.0, 1.04e5, "VAPOR")),)
        ),
        "INVALID_SPECIFICATION",
        "invalid_spec(bottom_inlet)",
    ),
    # S7
    "S7-condenser": (
        replace(M1, sides=(replace(_feed(), stage=1),)),
        "INVALID_SPECIFICATION",
        "invalid_spec(side_feed_stage:feed)",
    ),
    "S7-reboiler": (
        replace(M2, sides=(replace(_feed(), stage=7),)),
        "INVALID_SPECIFICATION",
        "invalid_spec(side_feed_stage:feed)",
    ),
    # S8
    "S8-one-stage-condenser": (
        replace(M4, stage_count=1, pressures=(1.0e5,), duties=(None,)),
        "INVALID_SPECIFICATION",
        "invalid_spec(stage_count)",
    ),
    "S8-two-stages-two-ends": (
        replace(M1, stage_count=2, pressures=(1.0e5, 1.01e5), duties=(None, None), sides=()),
        "INVALID_SPECIFICATION",
        "invalid_spec(stage_count)",
    ),
    # S9
    "S9": (
        replace(M1, pressures=(1.0e5, 1.01e5, 1.02e5, 1.03e5, 1.035e5, 1.034e5, 1.06e5)),
        "INVALID_SPECIFICATION",
        "invalid_spec(pressure_profile)",
    ),
    # S10
    "S10": (
        replace(
            M1,
            sides=(replace(_feed(), state=InletState((0.0, 0.0, 0.0), 340.0, 1.04e5, "LIQUID")),),
        ),
        "INVALID_SPECIFICATION",
        "invalid_spec(no_feed)",
    ),
    # S-R5 (§9): M1 with the feed at 360 K; and §5's registered probe at 360 K, 1.03 bar.
    "S-R5": (
        replace(M1, sides=(_feed(temperature=360.0),)),
        "INVALID_SPECIFICATION",
        "inadmissible_inlet(feed, LIQUID)",
    ),
    "S-R5-probe": (
        replace(M1, sides=(_feed(temperature=360.0, pressure=1.03e5),)),
        "INVALID_SPECIFICATION",
        "inadmissible_inlet(feed, LIQUID)",
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_a02_refusals(name: str) -> None:
    """A02: S1–S10, S-R5 and S01's R1–R7 on a column, each with its §5 category and code."""
    spec, outcome, cause = REFUSALS[name]
    failure = validate(spec, PROVIDER, CONTEXT)
    assert isinstance(failure, CascadeFailure), failure
    assert (failure.outcome, failure.cause) == (outcome, cause)


def test_a02_the_r5_probe_is_above_its_bubble_point() -> None:
    """A02 / §5: the registered R5 probe's bubble margin `1 − Σ z_i K_i(360 K, 1.03 bar)`, formed
    here from the provider's `K`, is `ref.refusals.feed_360K_bubble_margin`."""
    k = _k(360.0, 1.03e5)
    margin = 1.0 - sum(z * ki for z, ki in zip(FEED, k, strict=True))
    assert _close(margin, REFERENCE["refusals"]["feed_360K_bubble_margin"], 0.0, 5e-7)


def test_a02_r7_is_applied_only_when_every_slot_is_a_duty() -> None:
    """A02 / §5: an intermediate duty that R7 would refuse passes beside a ratio slot (the end
    duty is free there), and is refused when both slots are duties."""
    duties = (None, 0.0, 0.0, 1.0e7, 0.0, 0.0, None)
    assert validate(replace(M1, duties=duties), PROVIDER, CONTEXT) is None
    failure = validate(replace(_variant("M1", "duty+duty"), duties=duties), PROVIDER, CONTEXT)
    assert isinstance(failure, CascadeFailure)
    assert failure.cause == "infeasible_spec(energy_outside_domain)"


def test_a02_misuse_raises() -> None:
    """A `None` duty anywhere but a column-specification stage (or a duty there) is a malformed
    object, not a §5 refusal."""
    with pytest.raises(ValueError, match="None exactly"):
        validate(replace(M1, duties=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, None)), PROVIDER, CONTEXT)
    with pytest.raises(ValueError, match="None exactly"):
        validate(replace(M3, duties=(0.0, None, 0.0, 0.0, None)), PROVIDER, CONTEXT)
    with pytest.raises(ValueError, match="pressures"):
        validate(replace(M1, pressures=(1.0e5,)), PROVIDER, CONTEXT)


VALID: dict[str, ColumnSpec] = {
    **SPECS,
    **{
        f"{case}:{variant}": _variant(case, variant)
        for case in ("M1", "M2")
        for variant in REFERENCE["variants"][case]
        if variant != "distillate_rate+bottoms_rate"
    },
}


@pytest.mark.parametrize("name", sorted(VALID))
def test_a02_every_registered_case_passes_section_5(name: str) -> None:
    """A02: M1–M4, P1 and the registered V-M1/V-M2 sets pass §5."""
    assert validate(VALID[name], PROVIDER, CONTEXT) is None


# -- A03 -----------------------------------------------------------------------------------------


def _no_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("S3 refuses before any row, initializer or energy evaluation")

    for name in ("declared_rows", "profile_initial", "energy_precheck", "band_temperature"):
        monkeypatch.setattr(column_module, name, refuse)


@pytest.mark.parametrize("case", ["M1", "M2"])
@pytest.mark.parametrize("split", ["registered", "not_summing_to_F"])
def test_a03_distillate_and_bottoms_rates_are_refused(
    case: str, split: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A03: (D*, B*) is `invalid_spec(redundant_specification)` at the registered split
    `D* + B* = F` (`ref.variants`, where the generator's `σ_min < 1e-40`) and at one that is not."""
    spec = _variant(case, "distillate_rate+bottoms_rate")
    assert spec.condenser_spec is not None and spec.reboiler_spec is not None
    total = spec.condenser_spec.value + spec.reboiler_spec.value
    assert abs(total - 1.0) <= 1e-15
    assert float(REFERENCE["variants"][case]["distillate_rate+bottoms_rate"]["sigma_min"]) < 1e-40
    if split == "not_summing_to_F":
        spec = replace(spec, condenser_spec=EndSpecification("distillate_rate", 0.3))
    _no_evaluation(monkeypatch)
    failure = validate(spec, PROVIDER, CONTEXT)
    assert isinstance(failure, CascadeFailure)
    assert (failure.outcome, failure.cause) == (
        "INVALID_SPECIFICATION",
        "invalid_spec(redundant_specification)",
    )


# -- A04 -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_a04_the_initializer_on_the_registered_cases(case: str) -> None:
    """A04: `z`, `T_a`, `T_b`, the profile (abs 1e-8 K), `L_cmo`, `V_cmo`, `l`, `v` (rel 1e-10)
    against `ref.cases.*.initializer`; `x_K` is a full state on which the definitional rows hold."""
    spec = SPECS[case]
    expected = REFERENCE["cases"][case]["initializer"]
    initial = profile_initial(spec, PROVIDER, CONTEXT)
    assert isinstance(initial, ProfileInitial)
    assert all(_close(a, b, 1e-10) for a, b in zip(initial.z, expected["z"], strict=True))
    assert _close(initial.t_a, expected["T_a"], 0.0, 1e-8)
    assert _close(initial.t_b, expected["T_b"], 0.0, 1e-8)
    assert all(
        _close(a, b, 0.0, 1e-8) for a, b in zip(initial.profile, expected["profile"], strict=True)
    )
    for actual, wanted in ((initial.liquid_cmo, "L_cmo"), (initial.vapor_cmo, "V_cmo")):
        assert all(_close(a, b, 1e-10) for a, b in zip(actual, expected[wanted], strict=True))
    assert sorted(initial.liquid) == sorted(int(j) for j in expected["l"])
    assert sorted(initial.vapor) == sorted(int(j) for j in expected["v"])
    for j, values in expected["l"].items():
        for i in range(3):
            assert _close(initial.liquid[int(j)][i], values[i], 1e-10), ("l", j, i)
            assert _close(initial.vapor[int(j)][i], expected["v"][j][i], 1e-10), ("v", j, i)
            # §6 step 6: every initial flow is positive (generator claim).
            assert initial.liquid[int(j)][i] > 0.0 and initial.vapor[int(j)][i] > 0.0

    state = initial.state
    problem = declared_problem(declared_rows(spec, PROVIDER, CONTEXT))
    assert tuple(state) == problem.variable_ids
    for stage in spec.equilibrium_stages():
        assert state[stage_temperature_id(UNIT, stage)] == initial.profile[stage - 1]
        assert state[stage_pressure_id(UNIT, stage)] == spec.pressures[stage - 1]
        assert state[liquid_id(UNIT, stage, "A")] == initial.liquid[stage][0]
        assert state[vapor_id(UNIT, stage, "C")] == initial.vapor[stage][2]
    if spec.total_condenser:
        assert state[reflux_fraction_id(UNIT)] == 0.5
        assert state[stage_temperature_id(UNIT, 1)] == initial.profile[0]
        assert state[stage_pressure_id(UNIT, 1)] == spec.pressures[0]
        for i, c in enumerate(COMPONENTS):
            assert state[reflux_id(UNIT, c)] == 0.5 * initial.vapor[2][i]
            assert state[distillate_id(UNIT, c)] == initial.vapor[2][i] - state[reflux_id(UNIT, c)]
    residual = row_values(problem, state)
    for name, value in residual.items():
        if re.search(r":(mix|split|bal):|:P$|:inlet:", name):
            assert value == 0.0, (name, value)
        elif re.search(r":(Ldef|Vdef|Ddef)$", name):
            assert abs(value) <= 1e-15, (name, value)
        elif name.endswith(":energy"):
            assert abs(value) <= 1e-10, (name, value)
    # A duty column's value is the energy row's closure, so it is finite and nonzero here.
    for stage in range(1, spec.stage_count + 1):
        assert math.isfinite(state[stage_duty_id(UNIT, stage)])


def test_a04_the_profile_outside_the_domain_is_a_typed_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§6 step 2: `T_a` or `T_b` outside the domain ends `INITIALIZATION_FAILED`. SYN-001 cannot
    reach this branch, so the band's answer is stubbed: this checks the mapping only."""
    for position in ("below", "above"):
        monkeypatch.setattr(
            column_module,
            "band_temperature",
            lambda *args, position=position, **kwargs: BandTemperature(position),
        )
        failure = profile_initial(M1, PROVIDER, CONTEXT)
        assert isinstance(failure, CascadeFailure)
        assert (failure.outcome, failure.cause) == (
            "INITIALIZATION_FAILED",
            "initialization_failed(s02-profile-cmo-v1, profile_outside_domain)",
        )


def test_a04_the_inlet_columns_are_the_feed_pattern() -> None:
    """§2: a present inlet's `C + 2` columns are pinned; an absent one has none (§2.3)."""
    rows = declared_rows(M1, PROVIDER, CONTEXT)
    assert {flow_id(FEED_STREAM, c) for c in COMPONENTS} <= set(rows.variable_ids)
    assert rows.parameters[f"{temperature_id(FEED_STREAM)}*"] == 340.0
    assert not any(".inlet.top." in name or ".inlet.bottom." in name for name in rows.variable_ids)
