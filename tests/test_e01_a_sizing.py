"""E01 WO-A2/A2b: sizing — the volumetric-flow blocks and the unit families (E01 design §4.4, §9.3,
§9.4).

§6.1 A9 (Underwood), A10 (the exchanger hand case), A13 (the blocks against the provider, bitwise),
and the families on a solved SYN-001 state (P2's host): items, regime entries, refusals, the twin
against the reference path and a central-difference gradient. A11 and A12 need WO-B4's hand
cases and run in I1. A46 (model-identity and declared volumes) and A47 (the kinetic CSTR, a drum
with a dormant liquid) are WO-A2b's. Expectations are written from the note's formulas, never from
the program.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from typing import Any

import numpy as np
import pytest
from m03_support import flowsheet

from openflowsheet.assessment.blocks import (
    SaturatedVolumetricFlowBlock,
    VolumetricFlowBlock,
    volume_available,
)
from openflowsheet.assessment.program import (
    AssessmentProgram,
    BuildContext,
    ContributionPlan,
    Refusal,
)
from openflowsheet.assessment.sizing import FAMILIES, SizedItem, family_of, plan_sizing
from openflowsheet.assessment.sizing.families import actual_trays, underwood
from openflowsheet.assessment.spec import load_assessment
from openflowsheet.assessment.views import UnitRef, view_of
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.thermal.kernel import phase_properties, saturation
from openflowsheet.studies.nlp.verification import TAU_FEAS
from openflowsheet.studies.syn001 import solve_certified
from openflowsheet.thermo import PropertyRequest, StreamState
from openflowsheet.thermo.iapws95 import Iapws95Provider
from openflowsheet.thermo.pr_lib import PrLibProvider

CONTEXT = EvaluationContext(model_version="e01-a2", constants_sha256="0" * 64)


def lmtd(dt1: float, dt2: float) -> float:
    return (dt1 - dt2) / math.log(dt1 / dt2)


def underwood_hand(dt1: float, dt2: float) -> float:
    return ((dt1 ** (1.0 / 3.0) + dt2 ** (1.0 / 3.0)) / 2.0) ** 3


class Sizing:
    """The sizing families alone, as the `cost` contributor will merge them (WO-A4)."""

    name = "cost"

    def plan(self, ctx: BuildContext, state: Mapping[str, float]) -> ContributionPlan:
        plan, _ = plan_sizing(ctx, state)
        return plan.contribution()


class Capture(Sizing):
    """`Sizing`, keeping the last plan's items for the tests to read their records."""

    def __init__(self) -> None:
        self.items: dict[str, SizedItem] = {}

    def plan(self, ctx: BuildContext, state: Mapping[str, float]) -> ContributionPlan:
        plan, _ = plan_sizing(ctx, state)
        self.items = {item.item_id: item for item in plan.items}
        return plan.contribution()

    def item(self, item_id: str) -> SizedItem:
        return self.items[item_id]


#: SYN-001's own constants (`docs/derivations/SYN-001.md` §3; `thermo/syn001.py`), restated here so
#: the hand values do not read the module under test: R (CODATA exact) and v_i = 1.0e-4 m³/mol.
SYN_R = 8.31446261815324


def _syn_v(component: str) -> float:
    return 1.0e-4


# -- A9 ------------------------------------------------------------------------------------------


def test_a9_underwood() -> None:
    equal = underwood(10.0, 10.0)
    assert abs(equal - 10.0) <= 4 * math.ulp(10.0)
    assert underwood(10.0, 1.0) / lmtd(10.0, 1.0) - 1.0 == pytest.approx(3.801e-3, abs=1e-6)
    assert underwood(50.0, 1.0) / lmtd(50.0, 1.0) - 1.0 == pytest.approx(2.5592e-2, abs=1e-6)


def test_n_act_reads_the_efficiency_as_written() -> None:
    assert actual_trays(7, 0.7) == 10  # binary64 7/0.7 = 10.000000000000002
    assert actual_trays(10, 0.7) == 15
    assert actual_trays(8, 1.0) == 8


# -- A10: the exchanger hand case on a stub host -------------------------------------------------


class _NoFlash:
    """A provider stand-in: one component, no flash (the phase-change check is informational)."""

    @dataclass(frozen=True)
    class _Described:
        provider_id: str = "stub"
        components: tuple[str, ...] = ("A",)
        properties: tuple[str, ...] = ()
        phases: tuple[str, ...] = ()

    @dataclass(frozen=True)
    class _Result:
        status: str = "failed"
        phase_signature: None = None

    def describe(self) -> Any:
        return self._Described()

    def flash(self, request: Any, context: Any) -> Any:
        return self._Result()


@dataclass(frozen=True)
class _StubView:
    unit_refs: tuple[UnitRef, ...]
    components: tuple[str, ...] = ("A",)
    provider: Any = _NoFlash()
    context: EvaluationContext = CONTEXT

    def units(self) -> tuple[UnitRef, ...]:
        return self.unit_refs

    def molar_masses(self) -> Mapping[str, float]:
        return {"A": 0.1}


HEATER = UnitRef("H1", "thermal.heater", {"inlet": ("S1",), "outlet": ("S2",)}, {}, None)
HOST = ProblemSpec(
    label="stub-host",
    variable_ids=("S1.n.A", "S1.T", "S1.P", "S2.n.A", "S2.T", "S2.P", "H1.Q"),
    equations=(),
    parameter_ids=(),
    parameters={},
)
A10_STATE = {
    "S1.n.A": 1.0,
    "S1.T": 300.0,
    "S1.P": 2e5,
    "S2.n.A": 1.0,
    "S2.T": 400.0,
    "S2.P": 2e5,
    "H1.Q": 1.0e6,
}
STEAM = {
    "utility_id": "HPS",
    "kind": "heating",
    "T_supply": 433.15,
    "T_return": 433.15,
    "dT_min": 10.0,
    "price": {"value": 20.0, "per": "GJ"},
}
A10_DOC: dict[str, Any] = {
    "schema_version": "assessment-v1",
    "assessment_id": "e01-a10",
    "basis": {"currency": "USD", "year": 2024},
    "items": {"H1": {"U": 500.0, "F_T": 1.0}},
    "utilities": [STEAM],
}


def test_a10_exchanger_hand_case() -> None:
    program = AssessmentProgram.build(
        _StubView((HEATER,)), HOST, load_assessment(A10_DOC), A10_STATE, contributors=[Sizing()]
    )
    assert isinstance(program, AssessmentProgram)
    values = program.evaluate(A10_STATE)
    assert isinstance(values, Mapping)
    assert values["size.H1.area"] == pytest.approx(27.79342236620868, rel=1e-13)
    dlm = underwood(433.15 - 400.0, 433.15 - 300.0)
    assert dlm == pytest.approx(71.95947205233731, rel=1e-13)
    assert dlm / 71.92001136510889 - 1.0 == pytest.approx(5.4867e-4, abs=1e-8)
    assert program.regime.entries == {"H1.service": "heating", "H1.utility": "HPS"}
    assert values["adm.H1.utility.dT1"] == pytest.approx((33.15 - 10.0) / 33.15, rel=1e-12)
    assert values["adm.H1.service.duty"] == 1.0


def test_a10_auto_utility_is_the_cheapest_admissible_and_u_is_required() -> None:
    cheap_but_cold = {
        **STEAM,
        "utility_id": "LPS",
        "T_supply": 405.0,
        "T_return": 405.0,
        "price": {"value": 5.0, "per": "GJ"},
    }
    dear = {**STEAM, "utility_id": "XPS", "price": {"value": 0.1, "per": "kWh"}}  # 27.8 /GJ
    document = {**A10_DOC, "utilities": [cheap_but_cold, dear, STEAM]}
    program = AssessmentProgram.build(
        _StubView((HEATER,)), HOST, load_assessment(document), A10_STATE, contributors=[Sizing()]
    )
    assert isinstance(program, AssessmentProgram)
    assert program.regime.entries["H1.utility"] == "HPS"  # LPS: 405 − 400 < 10 K
    no_u = {**A10_DOC, "items": {"H1": {}}}
    program = AssessmentProgram.build(
        _StubView((HEATER,)), HOST, load_assessment(no_u), A10_STATE, contributors=[Sizing()]
    )
    assert isinstance(program, AssessmentProgram)
    assert Refusal("SIZING_INPUT_MISSING", "H1.U", "service heating") in program.refusals
    assert "size.H1.area" not in program.output_ids


# -- A13: the volumetric blocks against the provider, bitwise ------------------------------------


def test_a13_single_phase_block_is_n_times_v_with_the_providers_derivatives() -> None:
    water = Iapws95Provider()
    block = VolumetricFlowBlock(water, CONTEXT, "LIQUID", block_id="ASMVF_1")
    inputs = [2.5, 300.0, 2.0e5]
    result = water.evaluate_phase(
        PropertyRequest(StreamState((2.5,), 300.0, 2.0e5), "LIQUID", ("v",), ("T", "P")), CONTEXT
    )
    v, d = result.values["v"], result.derivatives["v"]
    assert list(block.values(inputs)) == [2.5 * v]
    assert list(block.jacobian(inputs)) == [(0, 0, v), (0, 1, 2.5 * d["T"]), (0, 2, 2.5 * d["P"])]
    assert set(block.jacobian_pattern()) == {(0, 0), (0, 1), (0, 2)}


def test_a13_mixture_block_carries_the_composition_derivatives() -> None:
    gas = PrLibProvider()
    components = gas.describe().components
    flows = tuple(0.5 + 0.25 * i for i in range(len(components)))
    block = VolumetricFlowBlock(gas, CONTEXT, "VAPOR", block_id="ASMVF_1")
    names = ("T", "P", *(f"n_{c}" for c in components))
    result = gas.evaluate_phase(
        PropertyRequest(StreamState(flows, 600.0, 5.0e5), "VAPOR", ("v",), names), CONTEXT
    )
    v, d = result.values["v"], result.derivatives["v"]
    total = sum(flows)
    inputs = [*flows, 600.0, 5.0e5]
    assert list(block.values(inputs)) == [total * v]
    expected = [(0, j, v + total * d[f"n_{c}"]) for j, c in enumerate(components)]
    expected += [(0, len(flows), total * d["T"]), (0, len(flows) + 1, total * d["P"])]
    assert list(block.jacobian(inputs)) == expected
    assert volume_available(gas, CONTEXT, "LIQUID", flows, 600.0, 5.0e5) is not None


def test_a13_saturated_block_chains_along_the_line() -> None:
    water = Iapws95Provider()
    block = SaturatedVolumetricFlowBlock(water, CONTEXT, block_id="ASMVF_1")
    pressure = 1.0e5
    sat = saturation(water, pressure, CONTEXT)
    jets = {
        phase: phase_properties(water, CONTEXT, sat.temperature, pressure, phase, ("v",))["v"]
        for phase in ("VAPOR", "LIQUID")
    }
    along = {phase: jet[1] * sat.dtsat_dp + jet[2] for phase, jet in jets.items()}
    inputs = [0.3, 0.7, pressure]
    assert list(block.values(inputs)) == [0.3 * jets["VAPOR"][0] + 0.7 * jets["LIQUID"][0]]
    assert list(block.jacobian(inputs)) == [
        (0, 0, jets["VAPOR"][0]),
        (0, 1, jets["LIQUID"][0]),
        (0, 2, 0.3 * along["VAPOR"] + 0.7 * along["LIQUID"]),
    ]


# -- the families on a solved SYN-001 state -----------------------------------------------------


@cache
def solved() -> tuple[Any, ProblemSpec, dict[str, float]]:
    sheet = flowsheet({})
    solve = solve_certified(sheet)
    assert solve.verified and solve.final_state is not None
    return sheet, sheet.spec(), dict(solve.final_state)


SYN_DOC: dict[str, Any] = {
    "schema_version": "assessment-v1",
    "assessment_id": "e01-a2-syn001",
    "basis": {"currency": "USD", "year": 2024},
    "defaults": {"U_by_service": {"heating": 800.0, "cooling": 500.0}},
    "utilities": [
        {
            "utility_id": "HPS",
            "kind": "heating",
            "T_supply": 520.0,
            "dT_min": 10.0,
            "price": {"value": 20.0, "per": "GJ"},
        },
        {
            "utility_id": "CW",
            "kind": "cooling",
            "T_supply": 293.15,
            "T_return": 303.15,
            "dT_min": 5.0,
            "price": {"value": 0.5, "per": "GJ"},
        },
    ],
}


@cache
def syn_program() -> AssessmentProgram:
    sheet, host, state = solved()
    program = AssessmentProgram.build(
        view_of(sheet), host, load_assessment(SYN_DOC), state, contributors=[Sizing()]
    )
    assert isinstance(program, AssessmentProgram)
    return program


def test_every_syn001_model_id_has_a_family() -> None:
    sheet, _, _ = solved()
    for unit in view_of(sheet).units():
        assert family_of(unit.model_id) is not None, unit.model_id
    assert "syn001.liquid_pump" in FAMILIES and "syn001.pump" not in FAMILIES


def test_syn001_items_entries_and_refusals() -> None:
    _, _, state = solved()
    program = syn_program()
    assert "size.U-HEAT.area" in program.output_ids
    assert "size.U-FLASH.duty.area" in program.output_ids
    # The SYN-001 provider offers no molar volume, but its potential defines both (§9.4, A46):
    # the drum is sized from the model identity, not refused.
    assert not [r for r in program.refusals if r.target.startswith("U-FLASH.drum")]
    assert "size.U-FLASH.drum.diameter" in program.output_ids
    heating = state["U-HEAT.Q"] > 0.0
    assert program.regime.entries["U-HEAT.service"] == ("heating" if heating else "cooling")
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    assert all(values[name] >= -TAU_FEAS for name in program.admissibility_ids)


def _hand_area(state: Mapping[str, float], unit: str, t_in: str, t_out: str) -> float:
    q = state[f"{unit}.Q"]
    if q > 0.0:
        dt1, dt2, u = 520.0 - state[t_out], 520.0 - state[t_in], 800.0
    else:
        dt1, dt2, u = state[t_in] - 303.15, state[t_out] - 293.15, 500.0
    return abs(q) / (u * 1.0 * underwood_hand(dt1, dt2))


def test_syn001_areas_match_the_formula_and_the_twin_matches_the_reference() -> None:
    _, host, state = solved()
    program = syn_program()
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    heater = _hand_area(state, "U-HEAT", "S2.T", "S3.T")
    assert values["size.U-HEAT.area"] == pytest.approx(heater, rel=1e-13)
    twin = program.linearize(state, {}, program.output_ids)
    assert not isinstance(twin, Refusal)
    for name in program.output_ids:
        reference = values[name]
        assert abs(twin.values[name] - reference) <= 1e-13 * max(1.0, abs(reference)), name


def test_syn001_area_gradient_against_central_differences() -> None:
    _, host, state = solved()
    program = syn_program()
    name = "size.U-HEAT.area"
    lin = program.linearize(state, {}, (name,))
    assert not isinstance(lin, Refusal)
    columns = lin.d_dx.col_ids
    dense = np.zeros(len(columns))
    for j in range(len(columns)):
        for k in range(lin.d_dx.indptr[j], lin.d_dx.indptr[j + 1]):
            dense[j] = lin.d_dx.data[k]
    checked = 0
    for j, column in enumerate(columns):
        if dense[j] == 0.0:
            continue
        h = 1e-6 * max(abs(state[column]), 1.0)
        up = program.evaluate({**state, column: state[column] + h})
        down = program.evaluate({**state, column: state[column] - h})
        assert isinstance(up, Mapping) and isinstance(down, Mapping)
        fd = (up[name] - down[name]) / (2.0 * h)
        y = lin.values[name]
        assert abs(dense[j] - fd) <= 1e-6 * max(abs(dense[j]), abs(y)) + 1e-12, column
        checked += 1
    assert checked == 3  # Q, T_in, T_out


# -- the families on S11's TH-R1 (H2O, IAPWS-95): heater, flash drum, pump and drive ------------

from s11_thermal_support import committed_case, solve  # noqa: E402
from test_s11_thermal_binding import registered  # noqa: E402, F401

from openflowsheet.models.thermal.state import liquid_id, vapor_id  # noqa: E402

TH_DOC: dict[str, Any] = {
    **SYN_DOC,
    "assessment_id": "e01-a2-th-r1",
    "utilities": [
        {
            "utility_id": "HPS",
            "kind": "heating",
            "T_supply": 520.0,
            "dT_min": 10.0,
            "price": {"value": 20.0, "per": "GJ"},
        },
    ],
}


def _saturated_v(pressure: float) -> tuple[float, float]:
    water = Iapws95Provider()
    sat = saturation(water, pressure, CONTEXT)
    v = {
        phase: phase_properties(water, CONTEXT, sat.temperature, pressure, phase, ("v",))["v"][0]
        for phase in ("VAPOR", "LIQUID")
    }
    return v["VAPOR"], v["LIQUID"]


def test_th_r1_drum_pump_and_heater(registered: None) -> None:  # noqa: F811
    binding, run = solve(committed_case("TH-R1"))
    assert run.state is not None
    state = dict(run.state)
    program = AssessmentProgram.build(
        view_of(binding.flowsheet),
        binding.spec,
        load_assessment(TH_DOC),
        state,
        contributors=[Sizing()],
    )
    assert isinstance(program, AssessmentProgram)
    assert not program.refusals, program.refusals
    names = set(program.output_ids)
    assert {
        "size.H.area",
        "size.D.drum.volume",
        "size.D.drum.diameter",
        "size.D.drum.height",
        "size.P.power",
        "size.P.vol_flow",
        "size.P.head",
        "size.P.drive.power",
    } <= names
    assert not any(name.startswith("size.D.duty.") for name in names)  # Q_spec = 0.0
    assert [lim.code for lim in program.limitations] == ["LMTD_ACROSS_PHASE_CHANGE"]
    values = program.evaluate(state)
    assert isinstance(values, Mapping)

    # Drum (§4.4.4) by hand: saturated products S5 (vapour), S6 (liquid) at the drum pressure.
    mass = 0.01801528  # IAPWS-95 basis molar mass of H2O, kg/mol
    m_view = view_of(binding.flowsheet).molar_masses()["H2O"]
    assert m_view == pytest.approx(mass, rel=1e-6)
    v_v, v_l = _saturated_v(state["S6.P"])
    vdot_l = state[vapor_id("S6")] * v_v + state[liquid_id("S6")] * v_l
    n_v = state[vapor_id("S5")] + state[liquid_id("S5")]
    vv5, vl5 = _saturated_v(state["S5.P"])
    vdot_v = state[vapor_id("S5")] * vv5 + state[liquid_id("S5")] * vl5
    rho_l = m_view * (state[vapor_id("S6")] + state[liquid_id("S6")]) / vdot_l
    rho_v = m_view * n_v / vdot_v
    volume = 300.0 * vdot_l / 0.5
    d2_l = (4.0 * volume / (math.pi * 3.0)) ** (2.0 / 3.0)
    d2_v = 4.0 * vdot_v / (math.pi * 0.07 * math.sqrt((rho_l - rho_v) / rho_v))
    controlling = "L" if d2_l >= d2_v else "V"
    assert program.regime.entries["D.drum.controlling"] == controlling
    assert values["size.D.drum.volume"] == pytest.approx(volume, rel=1e-12)
    assert values["size.D.drum.diameter"] == pytest.approx(math.sqrt(max(d2_l, d2_v)), rel=1e-12)
    assert values["size.D.drum.height"] == pytest.approx(
        3.0 * math.sqrt(max(d2_l, d2_v)), rel=1e-12
    )

    # Pump (§4.4.5): V̇_in on the saturated liquid S6, head = ΔP V̇/(ṁ g), drive W/0.95.
    assert values["size.P.vol_flow"] == pytest.approx(vdot_l, rel=1e-12)
    m_in = m_view * (state[vapor_id("S6")] + state[liquid_id("S6")])
    head = (state["S7.P"] - state["S6.P"]) * vdot_l / (m_in * 9.80665)
    assert values["size.P.head"] == pytest.approx(head, rel=1e-12)
    assert values["size.P.power"] == state["P.W"]
    assert values["size.P.drive.power"] == pytest.approx(state["P.W"] / 0.95, rel=1e-15)

    twin = program.linearize(state, {}, program.output_ids)
    assert not isinstance(twin, Refusal)
    for name in program.output_ids:
        reference = values[name]
        assert abs(twin.values[name] - reference) <= 1e-13 * max(1.0, abs(reference)), name


TH_C1_DOC: dict[str, Any] = {
    **SYN_DOC,
    "assessment_id": "e01-a2-th-c1",
    "utilities": [
        {
            "utility_id": "FH",
            "kind": "heating",
            "T_supply": 900.0,
            "dT_min": 25.0,
            "price": {"value": 8.0, "per": "GJ"},
        },
        {
            "utility_id": "CW",
            "kind": "cooling",
            "T_supply": 293.15,
            "T_return": 303.15,
            "dT_min": 5.0,
            "price": {"value": 0.5, "per": "GJ"},
        },
    ],
}


def test_th_c1_turbine_condenser_and_boiler(registered: None) -> None:  # noqa: F811
    binding, run = solve(committed_case("TH-C1"))
    assert run.state is not None
    state = dict(run.state)
    program = AssessmentProgram.build(
        view_of(binding.flowsheet),
        binding.spec,
        load_assessment(TH_C1_DOC),
        state,
        contributors=[Sizing()],
    )
    assert isinstance(program, AssessmentProgram)
    assert not program.refusals, program.refusals
    assert program.regime.entries["B.service"] == "heating"
    assert program.regime.entries["C.service"] == "cooling"
    assert program.regime.entries["C.utility"] == "CW"
    codes = sorted((lim.code, lim.target) for lim in program.limitations)
    assert ("GENERATOR_NOT_COSTED", "T") in codes
    assert ("LMTD_ACROSS_PHASE_CHANGE", "B") in codes  # liquid in, vapour out
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    assert values["size.T.power"] == -state["T.W"] > 0.0
    assert "size.T.drive.power" not in values
    boiler = state["B.Q"] / (800.0 * underwood_hand(900.0 - state["S3.T"], 900.0 - state["S2.T"]))
    assert values["size.B.area"] == pytest.approx(boiler, rel=1e-13)
    condenser = -state["C.Q"] / (
        500.0 * underwood_hand(state["S4.T"] - 303.15, state["S5.T"] - 293.15)
    )
    assert values["size.C.area"] == pytest.approx(condenser, rel=1e-13)
    assert all(values[name] >= -TAU_FEAS for name in program.admissibility_ids)
    twin = program.linearize(state, {}, program.output_ids)
    assert not isinstance(twin, Refusal)
    for name in program.output_ids:
        reference = values[name]
        assert abs(twin.values[name] - reference) <= 1e-13 * max(1.0, abs(reference)), name


# -- the column family on S11's M1 (SYN-001 basis: no molar volume) -----------------------------

from s11_column_support import column_registered  # noqa: E402
from s11_column_support import committed_case as column_committed  # noqa: E402

from openflowsheet.application.policies import T06_REVISION_V2  # noqa: E402
from openflowsheet.application.revision_binding import (  # noqa: E402
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.orchestrator.execution import ExecutionPlan  # noqa: E402
from openflowsheet.orchestrator.executor import execute_plan  # noqa: E402
from openflowsheet.orchestrator.revision import plan_revision  # noqa: E402


def _column_program(
    monkeypatch: pytest.MonkeyPatch, case: str, document: Mapping[str, Any]
) -> tuple[Any, AssessmentProgram, dict[str, float], UnitRef, Capture]:
    """S11's committed column case, solved, and the sizing program over it."""
    capture = Capture()
    with column_registered(monkeypatch, frozenset({"syn001", "wilson-ig-v2"})):
        binding = bind_revision_flowsheet(column_committed(case))
        assert isinstance(binding, RevisionBinding), binding
        plan, _ = plan_revision(binding, T06_REVISION_V2)
        assert isinstance(plan, ExecutionPlan), plan
        run = execute_plan(
            plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=T06_REVISION_V2
        )
        assert run.state is not None
        state = dict(run.state)
        view = view_of(binding.flowsheet)
        (column,) = [u for u in view.units() if u.model_id == "syn001.column"]
        program = AssessmentProgram.build(
            view, binding.spec, load_assessment(document), state, contributors=[capture]
        )
    assert isinstance(program, AssessmentProgram), program
    return view, program, state, column, capture


def test_column_m1_shell_sized_from_the_identity_condenser_and_reboiler_sized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view, program, state, column, capture = _column_program(monkeypatch, "M1", SYN_DOC)
    u = column.unit_id
    structure = column.structure.structure
    assert not [r for r in program.refusals if r.target.startswith(f"{u}.shell")]
    shell = capture.item(f"{u}.shell")
    sources = {r.name: r.v_source for r in shell.inputs if r.v_source is not None}
    assert sources and set(sources.values()) == {"model_identity"}
    _assert_shell_by_hand(view, program, state, column, vapour_r=SYN_R, liquid_v=_syn_v)
    assert ("COLUMN_AUXILIARIES_NOT_COSTED", u) in {(x.code, x.target) for x in program.limitations}
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    n = structure.stage_count
    if structure.condenser != "none":
        assert program.regime.entries[f"{u}.condenser.service"] == "cooling"
        q = state[f"{u}.stage.1.Q"]
        t_in, t_out = state[f"{u}.stage.2.T"], state[f"{u}.stage.1.T"]
        hand = -q / (500.0 * underwood_hand(t_in - 303.15, t_out - 293.15))
        assert values[f"size.{u}.condenser.area"] == pytest.approx(hand, rel=1e-13)
    if structure.reboiler != "none":
        assert program.regime.entries[f"{u}.reboiler.service"] == "heating"
        q = state[f"{u}.stage.{n}.Q"]
        t_in, t_out = state[f"{u}.stage.{n - 1}.T"], state[f"{u}.stage.{n}.T"]
        hand = q / (800.0 * underwood_hand(520.0 - t_out, 520.0 - t_in))
        assert values[f"size.{u}.reboiler.area"] == pytest.approx(hand, rel=1e-13)
    assert structure.condenser != "none" or structure.reboiler != "none"


class _VolumeProvider:
    """A test provider answering only `v`: ideal gas `RT/P` for the vapour, a constant 1e-4 m³/mol
    for the liquid, with their exact derivatives — so the column shell formula can be exercised on
    M1's solved stages (no registered column basis offers a volume; E01A_DECISIONS ESC-A5)."""

    R = 8.314462618

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def describe(self) -> Any:
        from dataclasses import replace  # noqa: PLC0415

        described = self._inner.describe()
        return replace(described, properties=("v",), phases=("LIQUID", "VAPOR"))

    def evaluate_phase(self, request: Any, context: Any) -> Any:
        from openflowsheet.thermo import PropertyResult  # noqa: PLC0415

        t, p = request.state.temperature, request.state.pressure
        names = request.derivatives
        if request.phase == "VAPOR":
            v, d = self.R * t / p, {"T": self.R / p, "P": -self.R * t / p**2}
        else:
            v, d = 1e-4, {"T": 0.0, "P": 0.0}
        derivs = {name: d.get(name, 0.0) for name in names}
        return PropertyResult(
            status="ok",
            phase_signature=request.phase,
            values={"v": v},
            derivatives={"v": derivs},
            achieved_accuracy=None,
            provider_id="stub-v",
            reference_convention="",
            message="",
        )

    def flash(self, request: Any, context: Any) -> Any:
        return self._inner.flash(request, context)


def test_column_m1_shell_formula_on_a_volume_test_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace  # noqa: PLC0415

    with column_registered(monkeypatch):
        binding = bind_revision_flowsheet(column_committed("M1"))
        assert isinstance(binding, RevisionBinding)
        plan, _ = plan_revision(binding, T06_REVISION_V2)
        assert isinstance(plan, ExecutionPlan)
        run = execute_plan(
            plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=T06_REVISION_V2
        )
        assert run.state is not None
        state = dict(run.state)
        base = view_of(binding.flowsheet)
        view = replace(base, provider=_VolumeProvider(base.provider))  # type: ignore[type-var]
        program = AssessmentProgram.build(
            view, binding.spec, load_assessment(SYN_DOC), state, contributors=[Sizing()]
        )
    assert isinstance(program, AssessmentProgram)
    (column,) = [u for u in view.units() if u.model_id == "syn001.column"]
    _assert_shell_by_hand(
        view, program, state, column, vapour_r=_VolumeProvider.R, liquid_v=lambda c: 1e-4
    )


def _assert_shell_by_hand(
    view: Any,
    program: AssessmentProgram,
    state: Mapping[str, float],
    column: UnitRef,
    *,
    vapour_r: float,
    liquid_v: Any,
) -> None:
    """§4.4.6 by hand on the solved stages: vapour `V̇ = N·R·T/P`, liquid `V̇ = Σ n_c·v_c`."""
    u, structure = column.unit_id, column.structure.structure
    n = structure.stage_count
    first = 2 if structure.condenser != "none" else 1
    last = n - 1 if structure.reboiler != "none" else n
    masses = view.molar_masses()
    d2: dict[int, float] = {}
    for j in range(first, last + 1):
        t, p = state[f"{u}.stage.{j}.T"], state[f"{u}.stage.{j}.P"]
        nv = [state[f"{u}.stage.{j}.v.{c}"] for c in view.components]
        nl = [state[f"{u}.stage.{j}.l.{c}"] for c in view.components]
        if sum(nv) == 0.0:
            continue
        vdot = sum(nv) * vapour_r * t / p
        rho_v = sum(masses[c] * x for c, x in zip(view.components, nv, strict=True)) / vdot
        rho_l = sum(masses[c] * x for c, x in zip(view.components, nl, strict=True)) / sum(
            x * liquid_v(c) for c, x in zip(view.components, nl, strict=True)
        )
        u_f = 0.09 * math.sqrt((rho_l - rho_v) / rho_v)
        d2[j] = 4.0 * vdot / (math.pi * 0.80 * 0.85 * u_f)
    best = max(d2, key=lambda j: (d2[j], -j))
    assert program.regime.entries.get(f"{u}.shell.controlling", str(best)) == str(best)
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    assert values[f"size.{u}.shell.diameter"] == pytest.approx(math.sqrt(d2[best]), rel=1e-12)
    n_act = math.ceil(round((last - first + 1) / 0.70, 12))
    height = (n_act - 1) * 0.6096 + 1.2192 + 3.048
    assert values[f"size.{u}.shell.height"] == pytest.approx(height, rel=1e-15)
    assert values[f"size.{u}.trays.diameter"] == values[f"size.{u}.shell.diameter"]
    assert all(values[name] >= -TAU_FEAS for name in program.admissibility_ids)


# -- A46: model-identity and declared volumes (amendment §9.4, WO-A2b) ---------------------------

from openflowsheet.assessment.blocks import identity_volume  # noqa: E402
from openflowsheet.models.revision_flowsheet import WILSON_RECORDS  # noqa: E402
from openflowsheet.thermo import syn001 as syn001_thermo  # noqa: E402
from openflowsheet.thermo import wilson_ig, wilson_ig_v2  # noqa: E402
from openflowsheet.thermo.syn001 import Syn001Provider  # noqa: E402
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider  # noqa: E402
from openflowsheet.thermo.wilson_ig_v2 import WilsonIdealGasProviderV2  # noqa: E402

GUARD_STATES = ((300.0, 60_000.0), (350.0, 101_325.0), (420.0, 190_000.0))
WILSON_STATES = ((330.0, 50_000.0), (350.0, 101_325.0), (380.0, 200_000.0))


def test_a46_guard_syn001_lnk_pressure_derivative_is_the_identity() -> None:
    """`R·T·∂lnK_i/∂P = v_i − RT/P` (SYN-001's potential), rel 1e-12 of RT/P, ≥ 3 states."""
    provider = Syn001Provider()
    for phase in ("LIQUID", "VAPOR"):
        for t, p in GUARD_STATES:
            result = provider.evaluate_phase(
                PropertyRequest(
                    state=StreamState(n=(1.0, 1.0, 1.0), temperature=t, pressure=p),
                    phase=phase,
                    properties=("lnK",),
                    derivatives=("P",),
                ),
                CONTEXT,
            )
            assert result.status == "ok", result.message
            rt_p = SYN_R * t / p
            for c in ("A", "B", "C"):
                lhs = SYN_R * t * result.derivatives[f"lnK_{c}"]["P"]
                assert abs(lhs - (_syn_v(c) - rt_p)) <= 1e-12 * rt_p, (phase, t, p, c)


def test_a46_guard_wilson_vapour_is_ideal_gas() -> None:
    """Wilson v1 and v2: vapour `lnphi_<c>` and its T, P derivatives are 0.0 exactly; v2's
    `P·∂s^V/∂P = −R` (rel 1e-15); the providers' `R` are one CODATA value."""
    assert wilson_ig.R == syn001_thermo.R == 8.31446261815324
    v1, v2 = WilsonIdealGasProvider(WILSON_RECORDS), WilsonIdealGasProviderV2(WILSON_RECORDS)
    components = v1.describe().components
    for provider in (v1, v2):
        names = tuple(f"lnphi_{c}" for c in components)
        for t, p in WILSON_STATES:
            result = provider.evaluate_phase(
                PropertyRequest(
                    state=StreamState(n=(0.3, 0.3, 0.4), temperature=t, pressure=p),
                    phase="VAPOR",
                    properties=names,
                    derivatives=("T", "P"),
                ),
                CONTEXT,
            )
            assert result.status == "ok", result.message
            for name in names:
                assert result.values[name] == 0.0
                assert result.derivatives[name]["T"] == 0.0
                assert result.derivatives[name]["P"] == 0.0
    for t, p in WILSON_STATES:
        result = v2.evaluate_phase(
            PropertyRequest(
                state=StreamState(n=(0.3, 0.3, 0.4), temperature=t, pressure=p),
                phase="VAPOR",
                properties=("s",),
                derivatives=("P",),
            ),
            CONTEXT,
        )
        assert result.status == "ok", result.message
        assert abs(p * result.derivatives["s"]["P"] + SYN_R) <= 1e-15 * SYN_R


def test_a46_only_the_tabled_providers_get_an_identity() -> None:
    syn = Syn001Provider()
    assert identity_volume(syn, "VAPOR", ("A", "B", "C")).kind == "ideal_gas"  # type: ignore[union-attr]
    assert identity_volume(syn, "LIQUID", ("A", "B", "C")).kind == "amagat"  # type: ignore[union-attr]
    assert identity_volume(syn, "LIQUID", ("A", "B", "X")) is None
    for provider in (
        WilsonIdealGasProvider(WILSON_RECORDS),
        WilsonIdealGasProviderV2(WILSON_RECORDS),
    ):
        components = provider.describe().components
        assert identity_volume(provider, "VAPOR", components).kind == "ideal_gas"  # type: ignore[union-attr]
        assert identity_volume(provider, "LIQUID", components) is None
    assert wilson_ig_v2.PROVIDER_ID == "wilson-ig-v2" and wilson_ig.PROVIDER_ID == "wilson-ig-v1"
    assert identity_volume(Iapws95Provider(), "VAPOR", ("H2O",)) is None


def _p2_flash() -> UnitRef:
    sheet, _, _ = solved()
    (flash,) = [u for u in view_of(sheet).units() if u.unit_id == "U-FLASH"]
    return flash


def _p2_drum_by_hand(
    state: Mapping[str, float], *, rho_l_declared: float | None = None
) -> dict[str, float]:
    """§4.4.4 by hand with SYN-001's identity volumes and the built-in defaults."""
    sheet, _, _ = solved()
    view = view_of(sheet)
    masses, components = view.molar_masses(), view.components
    flash = _p2_flash()
    vap, liq = flash.ports["vapor"][0], flash.ports["liquid"][0]
    nv = [state[f"{vap}.n.{c}"] for c in components]
    nl = [state[f"{liq}.n.{c}"] for c in components]
    vdot_v = sum(nv) * SYN_R * state[f"{vap}.T"] / state[f"{vap}.P"]
    vdot_l = sum(x * _syn_v(c) for c, x in zip(components, nl, strict=True))
    rho_v = sum(masses[c] * x for c, x in zip(components, nv, strict=True)) / vdot_v
    if rho_l_declared is None:
        rho_l = sum(masses[c] * x for c, x in zip(components, nl, strict=True)) / vdot_l
    else:
        rho_l = rho_l_declared
    volume = 300.0 * vdot_l / 0.5
    d2_l = (4.0 * volume / (math.pi * 3.0)) ** (2.0 / 3.0)
    d2_v = 4.0 * vdot_v / (math.pi * 0.07 * math.sqrt((rho_l - rho_v) / rho_v))
    d = math.sqrt(max(d2_l, d2_v))
    return {"volume": volume, "diameter": d, "height": 3.0 * d, "d2_l": d2_l, "d2_v": d2_v}


def test_a46_p2_drum_is_sized_from_the_identity_volumes() -> None:
    sheet, host, state = solved()
    capture = Capture()
    program = AssessmentProgram.build(
        view_of(sheet), host, load_assessment(SYN_DOC), state, contributors=[capture]
    )
    assert isinstance(program, AssessmentProgram)
    drum = capture.item("U-FLASH.drum")
    sources = {r.name: r.v_source for r in drum.inputs if r.v_source is not None}
    flash = _p2_flash()
    assert sources == {
        f"vdot.{flash.ports['liquid'][0]}": "model_identity",
        f"vdot.{flash.ports['vapor'][0]}": "model_identity",
    }
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    hand = _p2_drum_by_hand(state)
    for q in ("volume", "diameter", "height"):
        assert values[f"size.U-FLASH.drum.{q}"] == pytest.approx(hand[q], rel=1e-12), q
    controlling = "V" if hand["d2_v"] > hand["d2_l"] else "L"
    assert program.regime.entries["U-FLASH.drum.controlling"] == controlling
    # The identity rows' twin against the reference path, and A5's central differences on the
    # diameter and the controlling member's argmax rows (which read the other member's volume).
    rows = [n for n in program.admissibility_ids if "U-FLASH.drum.controlling" in n]
    assert rows
    for name in ("size.U-FLASH.drum.diameter", *rows):
        _central_differences(program, state, name)


def _central_differences(program: AssessmentProgram, state: Mapping[str, float], name: str) -> None:
    """A5: every nonzero column of `∂name/∂x` against a central difference, and the twin's value
    against the reference path (≤ 1e-13)."""
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    lin = program.linearize(state, {}, (name,))
    assert not isinstance(lin, Refusal)
    y = values[name]
    assert abs(lin.values[name] - y) <= 1e-13 * max(1.0, abs(y)), name
    checked = 0
    for j, column in enumerate(lin.d_dx.col_ids):
        start, stop = lin.d_dx.indptr[j], lin.d_dx.indptr[j + 1]
        if start == stop:
            continue
        derivative = float(lin.d_dx.data[start])
        h = 1e-6 * max(abs(state[column]), 1.0)
        up = program.evaluate({**state, column: state[column] + h})
        down = program.evaluate({**state, column: state[column] - h})
        assert isinstance(up, Mapping) and isinstance(down, Mapping)
        fd = (up[name] - down[name]) / (2.0 * h)
        assert abs(derivative - fd) <= 1e-6 * max(abs(derivative), abs(y)) + 1e-12, (name, column)
        checked += 1
    assert checked >= 3, name


def test_a46_an_item_declaration_behind_an_identity_is_reported_unused() -> None:
    sheet, host, state = solved()
    document = {**SYN_DOC, "items": {"U-FLASH.drum": {"liquid_molar_volume": 5.0e-5}}}
    capture = Capture()
    program = AssessmentProgram.build(
        view_of(sheet), host, load_assessment(document), state, contributors=[capture]
    )
    assert isinstance(program, AssessmentProgram)
    (record,) = [r for r in capture.item("U-FLASH.drum").inputs if r.name == "liquid_molar_volume"]
    assert record.used is False and record.value == 5.0e-5
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    hand = _p2_drum_by_hand(state)
    assert values["size.U-FLASH.drum.diameter"] == pytest.approx(hand["diameter"], rel=1e-12)


WILSON_VOLUMES = {
    "CH3OH": {"value": 1.0e-4, "source": "E01 test input; not a property claim"},
    "C2H5OH": {"value": 1.0e-4, "source": "E01 test input; not a property claim"},
    "H2O": {"value": 1.0e-4, "source": "E01 test input; not a property claim"},
}


def test_a46_wilson_column_shell_needs_declared_liquid_volumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C-MW (`wilson-ig-v2`, S11's Wilson column): the vapour has its identity, the liquid none, so
    the shell is refused at `v_L` without declarations and sized from them with (§9.4)."""
    _, program, _, column, _ = _column_program(monkeypatch, "C-MW", SYN_DOC)
    u = column.unit_id
    codes = {(r.code, r.target) for r in program.refusals}
    assert ("SIZING_INPUT_UNAVAILABLE", f"{u}.shell.v_L") in codes
    document = {**SYN_DOC, "liquid_molar_volumes": WILSON_VOLUMES}
    view, program, state, column, capture = _column_program(monkeypatch, "C-MW", document)
    assert not [r for r in program.refusals if r.target.startswith(f"{u}.shell")]
    shell = capture.item(f"{u}.shell")
    sources = {r.v_source for r in shell.inputs if r.v_source is not None}
    assert sources == {"model_identity", "declared_components"}
    assert sorted(t for t in program.theta if t.startswith("asm:liquid_molar_volume.")) == sorted(
        f"asm:liquid_molar_volume.{c}" for c in WILSON_VOLUMES
    )
    _assert_shell_by_hand(view, program, state, column, vapour_r=SYN_R, liquid_v=lambda c: 1.0e-4)
    twin = program.linearize(state, {}, program.output_ids)
    assert not isinstance(twin, Refusal)
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    for name in program.output_ids:
        assert abs(twin.values[name] - values[name]) <= 1e-13 * max(1.0, abs(values[name])), name
    # The item's own declaration comes before the document's (§9.4 step 3 before step 4).
    document = {**document, "items": {f"{u}.shell": {"liquid_molar_volume": 2.0e-4}}}
    view, program, state, column, capture = _column_program(monkeypatch, "C-MW", document)
    shell = capture.item(f"{u}.shell")
    assert {r.v_source for r in shell.inputs if r.v_source} == {"model_identity", "declared_item"}
    assert not [t for t in program.theta if t.startswith("asm:liquid_molar_volume.")]
    _assert_shell_by_hand(view, program, state, column, vapour_r=SYN_R, liquid_v=lambda c: 2.0e-4)


# -- A47: the kinetic CSTR's volume and a drum with a dormant liquid (amendment §9.3) ------------

from t08_cstr_support import OUTLET, UNIT, cstr_revision, root_state  # noqa: E402


def _cstr(
    document: Mapping[str, Any],
) -> tuple[AssessmentProgram, dict[str, float], Capture, Any]:
    bound = bind_revision_flowsheet(cstr_revision("e01-a47"))
    assert isinstance(bound, RevisionBinding), bound
    state = root_state("HIGH")
    capture = Capture()
    program = AssessmentProgram.build(
        view_of(bound.flowsheet),
        bound.spec,
        load_assessment(document),
        state,
        contributors=[capture],
    )
    assert isinstance(program, AssessmentProgram), program
    return program, state, capture, view_of(bound.flowsheet)


def test_a47_kinetic_cstr_volume_is_tau_times_the_outlet_flow() -> None:
    tau = 12.5
    document = {**SYN_DOC, "items": {f"{UNIT}.vessel": {"residence_time_s": tau}}}
    program, state, capture, view = _cstr(document)
    vdot = sum(state[f"{OUTLET}.n.{c}"] for c in ("A", "B", "C")) * SYN_R
    vdot = vdot * state[f"{OUTLET}.T"] / state[f"{OUTLET}.P"]
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    assert values[f"size.{UNIT}.vessel.volume"] == pytest.approx(tau * vdot, rel=1e-14)
    vessel = capture.item(f"{UNIT}.vessel")
    (k,) = [r for r in vessel.inputs if r.name == "implied_rate_constant"]
    (unit,) = [u for u in view.units() if u.unit_id == UNIT]
    damkohler = unit.parameters[f"{UNIT}.damkohler"]
    assert k.value == damkohler / tau and k.unit == "1/s"
    assert {r.v_source for r in vessel.inputs if r.v_source} == {"model_identity"}


def test_a47_kinetic_cstr_without_tau_is_refused_and_keeps_its_duty_item() -> None:
    program, _, capture, _ = _cstr(SYN_DOC)
    codes = {(r.code, r.target) for r in program.refusals}
    assert ("SIZING_INPUT_MISSING", f"{UNIT}.vessel.residence_time_s") in codes
    assert f"{UNIT}.vessel" not in capture.items
    assert f"{UNIT}.duty" in capture.items


def test_a47_drum_with_a_dormant_liquid_reads_the_declared_density() -> None:
    sheet, host, state = solved()
    flash = _p2_flash()
    liquid = flash.ports["liquid"][0]
    dormant = {**state, **{f"{liquid}.n.{c}": 0.0 for c in ("A", "B", "C")}}
    refused = AssessmentProgram.build(
        view_of(sheet), host, load_assessment(SYN_DOC), dormant, contributors=[Sizing()]
    )
    assert isinstance(refused, AssessmentProgram)
    codes = {(r.code, r.target) for r in refused.refusals}
    assert ("SIZING_INPUT_UNAVAILABLE", "U-FLASH.drum.rho_L") in codes
    rho = 750.0
    document = {**SYN_DOC, "items": {"U-FLASH.drum": {"dormant_liquid_density": rho}}}
    capture = Capture()
    program = AssessmentProgram.build(
        view_of(sheet), host, load_assessment(document), dormant, contributors=[capture]
    )
    assert isinstance(program, AssessmentProgram)
    assert not [r for r in program.refusals if r.target.startswith("U-FLASH.drum")]
    values = program.evaluate(dormant)
    assert isinstance(values, Mapping)
    hand = _p2_drum_by_hand(dormant, rho_l_declared=rho)
    assert hand["d2_l"] == 0.0
    assert values["size.U-FLASH.drum.diameter"] == pytest.approx(hand["diameter"], rel=1e-12)
    (record,) = [
        r for r in capture.item("U-FLASH.drum").inputs if r.name == "dormant_liquid_density"
    ]
    assert record.used is True
    # With an active liquid the declaration is reported unused.
    active = Capture()
    AssessmentProgram.build(
        view_of(sheet), host, load_assessment(document), state, contributors=[active]
    )
    (record,) = [
        r for r in active.item("U-FLASH.drum").inputs if r.name == "dormant_liquid_density"
    ]
    assert record.used is False
