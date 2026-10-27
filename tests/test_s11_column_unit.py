"""S11 WO-B2: `syn001.column` as a unit, and its revision builder (S11 design note §4.7.1,
§4.7.2, §4.7.5).

S11.A25 (`UnitEvaluation.owned`), S11.A26 (one test per structural item of B1's inventory,
`docs/S11B_DECISIONS.md`), S11.A27 (a Wilson column with a purity end), the column bound in a
revision through a monkeypatched builder table, and `evaluate` against the standalone solve.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from s11_column_support import column_registered, column_revision
from test_s02_column_wo1 import PROVIDER, SPECS
from test_s06_column_wo1 import J_CASES
from test_s10c_blocks import REAL, column_spec
from test_s11_column_face import view_of

from openflowsheet.application.binding import Unbound
from openflowsheet.application.column_binding import build_column
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.models import SpecificationError, UnitEvaluation
from openflowsheet.models.revision_flowsheet import InstanceView, RevisionError
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT
from openflowsheet.models.syn001.column import ColumnSpec
from openflowsheet.models.syn001.column_solve import ColumnSolution, products, solve_column
from openflowsheet.models.syn001.column_unit import ColumnUnit
from openflowsheet.thermo import StreamState

M1 = SPECS["M1"]


def build(view: InstanceView, provider: Any = PROVIDER) -> ColumnUnit:
    unit, _ = build_column(view, provider, DECLARATION_CONTEXT, M1.components)
    assert isinstance(unit, ColumnUnit)
    return unit


def with_parameters(spec: ColumnSpec, changes: dict[str, float | None]) -> InstanceView:
    """`view_of(spec)` with parameters set (a value) or removed (`None`)."""
    view = view_of(spec)
    parameters = dict(view.parameters)
    for name, value in changes.items():
        if value is None:
            parameters.pop(name, None)
        else:
            parameters[name] = value
    return replace(view, parameters=parameters)


# -- S11.A25 --------------------------------------------------------------------------------------


def test_a25_a_failed_evaluation_carries_no_owned_value() -> None:
    with pytest.raises(ValueError):
        UnitEvaluation(status="not_converged", owned={"U.stage.1.T": 300.0})
    assert UnitEvaluation(status="ok").owned == {}
    assert UnitEvaluation(status="unsupported", message="x").owned == {}


# -- S11.A26: the structural refusals at bind ------------------------------------------------------

#: One structural item of B1's inventory each: the view, and the code (a `RevisionError`) or the
#: `invalid_spec(<key>)` (a `SpecificationError`) it is refused with.
STRUCTURAL: dict[str, tuple[InstanceView, str]] = {
    "R1": (
        with_parameters(M1, {"stage_count": 0.0}),
        "parameter_value_unsupported(S02.stage_count)",
    ),
    "R1-integer": (
        with_parameters(M1, {"stage_count": 6.5}),
        "parameter_value_unsupported(S02.stage_count)",
    ),
    "R3": (with_parameters(M1, {"stage_pressure.3": 1.0}), "invalid_spec(domain:S02.stage.3.P)"),
    "R4": (with_parameters(M1, {"feed_stage.S-F1": 9.0}), "invalid_spec(side_feed_stage:feed1)"),
    "R6": (
        replace(view_of(M1), phases={**view_of(M1).phases, "feed": None}),
        "port_unsupported(S02.feed)",
    ),
    "S2-missing": (
        with_parameters(M1, {"condenser.reflux_ratio": None}),
        "specification_missing(S02.condenser)",
    ),
    "S2-kind": (
        with_parameters(M1, {"condenser.reflux_ratio": None, "condenser.boilup_ratio": 1.0}),
        "specification_unsupported(S02.condenser.boilup_ratio)",
    ),
    "S2-not-offered": (
        with_parameters(M1, {"condenser.reflux_ratio": None, "condenser.distillate_ratio": 0.4}),
        "specification_unsupported(S02.condenser.distillate_ratio)",
    ),
    "S2-two": (
        with_parameters(M1, {"condenser.distillate_rate": 0.4}),
        "specification_conflict(S02.condenser)",
    ),
    "S2-none-end": (
        with_parameters(SPECS["M3"], {"condenser.reflux_ratio": 2.0}),
        "specification_conflict(S02.condenser)",
    ),
    "S3": (
        with_parameters(
            SPECS["M2"], {"condenser.reflux_ratio": None, "condenser.distillate_rate": 0.4}
        ),
        "invalid_spec(redundant_specification)",
    ),
    "S4": (
        with_parameters(M1, {"condenser.reflux_ratio": -1.0}),
        "invalid_spec(reflux_ratio:condenser)",
    ),
    "S4-duty": (
        with_parameters(SPECS["M3"], {"reboiler.duty": -5.0}),
        "invalid_spec(duty:reboiler)",
    ),
    "S6": (
        replace(
            view_of(SPECS["M3"]), phases={**view_of(SPECS["M3"]).phases, "distillate": "LIQUID"}
        ),
        "specification_conflict(S02.distillate)",
    ),
    "S7": (with_parameters(M1, {"feed_stage.S-F1": 7.0}), "invalid_spec(side_feed_stage:feed1)"),
    "S8": (
        with_parameters(
            SPECS["M3"],
            {
                "stage_count": 1.0,
                **{f"stage_{q}.{j}": None for q in ("pressure", "duty") for j in range(1, 6)},
                "stage_pressure.1": 1.0e5,
            },
        ),
        "invalid_spec(stage_count)",
    ),
    "S9": (with_parameters(M1, {"stage_pressure.5": 1.0e5}), "invalid_spec(pressure_profile)"),
    "I1-component": (
        with_parameters(J_CASES["J1"], {"condenser.purity.A": None, "condenser.purity.Z": 0.8}),
        "invalid_spec(purity:condenser)",
    ),
    "I1-stage": (
        with_parameters(
            J_CASES["J3"], {"reboiler.temperature.6": None, "reboiler.temperature.9": 368.0}
        ),
        "invalid_spec(temperature:reboiler)",
    ),
    "I2": (
        with_parameters(J_CASES["J1"], {"condenser.purity.A": 1.2}),
        "invalid_spec(purity:condenser)",
    ),
}


@pytest.mark.parametrize("item", list(STRUCTURAL))
def test_a26_each_structural_item_is_refused_at_bind(item: str) -> None:
    view, code = STRUCTURAL[item]
    with pytest.raises((RevisionError, SpecificationError)) as raised:
        build(view)
    error = raised.value
    found = error.code if isinstance(error, RevisionError) else str(error)
    assert code in found, (item, found)


def test_a26_every_registered_case_builds() -> None:
    for spec in (*(SPECS[n] for n in ("M1", "M2", "M3", "M4", "P1")), *J_CASES.values()):
        build(view_of(spec))


# -- S11.A27 --------------------------------------------------------------------------------------


def test_a27_a_wilson_column_refuses_a_purity_end() -> None:
    spec = column_spec("C-MW")
    view = with_parameters(spec, {"condenser.reflux_ratio": None, "condenser.purity.CH3OH": 0.9})
    with pytest.raises(RevisionError) as raised:
        build_column(view, REAL, DECLARATION_CONTEXT, spec.components)
    assert raised.value.code == "specification_unsupported(COL.condenser.purity)"
    assert raised.value.hint is not None and "reflux_ratio" in raised.value.hint
    unit, _ = build_column(view_of(spec), REAL, DECLARATION_CONTEXT, spec.components)
    assert isinstance(unit, ColumnUnit)


# -- the column in a revision ----------------------------------------------------------------------


def test_q7_the_binder_requires_every_declared_port_wired(monkeypatch: pytest.MonkeyPatch) -> None:
    """Q7's fact: an unwired declared port of any multiplicity is `port_unwired`, so the unit
    declares only the ports its instance wires (`docs/S11B_DECISIONS.md`)."""
    with column_registered(monkeypatch):
        binding = bind_revision_flowsheet(column_revision(SPECS["M3"]))
        assert isinstance(binding, RevisionBinding), binding
        (unit,) = [u for u in binding.flowsheet.units() if u.unit_id == "UCOL"]
        assert [p.name for p in unit.ports()] == ["top", "distillate", "bottoms"]


@pytest.mark.parametrize("name", ["M1", "M4", "J2", "J4"])
def test_the_column_binds_square(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = {**SPECS, **J_CASES}[name]
    with column_registered(monkeypatch):
        binding = bind_revision_flowsheet(column_revision(spec))
    assert isinstance(binding, RevisionBinding), binding
    assert len(binding.spec.variable_ids) == len(binding.spec.equations)
    owners = {row: unit for row, unit in binding.row_units.items() if unit == "UCOL"}
    assert any(row.startswith("UCOL:product:distillate") for row in owners)


def test_the_column_is_refused_on_a_basis_it_is_not_admitted_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with column_registered(monkeypatch, frozenset({"wilson-ig-v1"})):
        found = bind_revision_flowsheet(column_revision(M1))
    assert isinstance(found, Unbound) and found.detail.startswith("model_unsupported"), found


def test_a_pin_on_the_column_is_unconsumed(monkeypatch: pytest.MonkeyPatch) -> None:
    document = column_revision(M1)
    document["specifications"].append(
        {
            **document["specifications"][-1],
            "id": "SPEC-COL-Q",
            "target": {"object_type": "instance", "object_id": "UCOL", "path": "duty.Q"},
            "kind": "heat_rate",
            "unit": "W",
            "value": 1.0,
            "tolerance": {"absolute": 1.0e-5, "relative": 1.0e-8, "scale": 1.0e5},
        }
    )
    with column_registered(monkeypatch):
        found = bind_revision_flowsheet(document)
    assert isinstance(found, Unbound) and found.detail == "specification_unconsumed(SPEC-COL-Q)"


# -- evaluate (§4.7.5) -----------------------------------------------------------------------------


def _inlets(spec: ColumnSpec) -> dict[str, list[StreamState]]:
    inlets: dict[str, list[StreamState]] = {}
    for inlet in spec.inlets():
        port = inlet.port if inlet.port in ("top", "bottom") else "feed"
        state = StreamState(
            n=inlet.state.n, temperature=inlet.state.temperature, pressure=inlet.state.pressure
        )
        inlets.setdefault(port, []).append(state)
    return inlets


@pytest.mark.parametrize("name", ["M1", "J2", "J4"])
def test_evaluate_is_the_standalone_solve(name: str) -> None:
    spec = {**SPECS, **J_CASES}[name]
    unit = build(view_of(spec))
    answer = unit.evaluate(_inlets(spec), DECLARATION_CONTEXT)
    assert answer.status == "ok", answer.message
    standalone = solve_column(spec, PROVIDER)
    assert isinstance(standalone, ColumnSolution)
    flows = products(spec, standalone.state)
    assert answer.outlets["distillate"].n == flows["distillate"]
    assert answer.outlets["bottoms"].n == flows["bottoms"]
    count = spec.stage_count
    assert (
        answer.outlets["bottoms"].temperature == standalone.state[f"{spec.unit_id}.stage.{count}.T"]
    )
    owned = unit.contribute(view_of(spec).wiring, spec.components).variable_ids
    assert set(answer.owned) == set(owned)


def test_evaluate_refuses_an_inlet_out_of_its_declared_phase() -> None:
    unit = build(view_of(M1))
    inlets = _inlets(M1)
    (feed,) = inlets["feed"]
    hot = StreamState(n=feed.n, temperature=440.0, pressure=feed.pressure)
    answer = unit.evaluate({"feed": [hot]}, DECLARATION_CONTEXT)
    assert answer.status != "ok"
    assert answer.message.splitlines()[0] == "inadmissible_phase(feed, LIQUID)"
    assert answer.owned == {} and answer.outlets == {}


def test_evaluate_returns_the_columns_typed_refusal() -> None:
    spec = J_CASES["J1"]
    unit = build(view_of(spec))
    inlets = _inlets(spec)
    (feed,) = inlets["feed"]
    absent = StreamState(n=(0.0, *feed.n[1:]), temperature=feed.temperature, pressure=feed.pressure)
    answer = unit.evaluate({"feed": [absent]}, DECLARATION_CONTEXT)
    assert answer.status == "unsupported"
    assert answer.message.splitlines()[0] == "infeasible_spec(absent_component:condenser)"
