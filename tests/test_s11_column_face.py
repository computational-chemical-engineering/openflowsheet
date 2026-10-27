"""S11 WO-B1: `syn001.column`'s flowsheet face (`docs/derivations/S11-design.md` §4.7.2–§4.7.4).

S11.A20 (link mode: DOF, the rows it replaces and adds), S11.A21 (`links=None` is the base),
S11.A22 (the NaN guard on a structural spec), and the parser `column_structure` on every
registered standalone case. S11.A23 (the S08 and S10-C identity lines) is the gate scripts'.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace
from typing import Any

import pytest
from test_s02_column_wo1 import PROVIDER, SPECS
from test_s06_column_wo1 import J_CASES
from test_s06_column_wo2 import expected_root
from test_s10c_blocks import REAL, column_spec

from openflowsheet.models import Contribution, flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import InstanceView, RevisionError
from openflowsheet.models.syn001.cascade import BOTTOM, TOP, inlet_row_id, inlet_stream
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT
from openflowsheet.models.syn001.column import (
    CONDENSER,
    F_REF,
    REBOILER,
    ColumnSpec,
    EndSpecification,
    component_feeds,
    declared_rows,
    product_flow_id,
    product_total_id,
    purity_flow_id,
    recovery_flow_id,
    slot_row_id,
)
from openflowsheet.models.syn001.column_solve import (
    closure_types,
    lifted_splits,
    split_temperatures,
    zero_flow_forms,
)
from openflowsheet.models.syn001.column_unit import (
    END_PARAMETERS,
    END_PREFIXES,
    ColumnStructure,
    column_structure,
    structural_spec,
)
from openflowsheet.thermo import PropertyProvider

#: S11.A21: `declared_rows(spec)` digests (`_digest`) at the base `3cbd3bd3` (= `8c34ecb0` for
#: `column.py`), before any S11 change.
BASE_DIGESTS = {
    "M1": "f608721c4a230096",
    "M2": "ff59ffd1aac060f1",
    "M3": "c65fa5f9c2a40145",
    "M4": "2b90e41325a53725",
    "P1": "9ef39b9960f47028",
    "J1": "e3d9c725c6195c21",
    "J2": "e17ad86d1efff506",
    "J3": "fa82236d634fb930",
    "J4": "bc7e877dfedb9284",
    "J5": "2952e213e2ce1b38",
    "J6": "cddf554dbffbda18",
    "J7": "76707044f5a43a8d",
    "J8": "75478047ae765178",
}

CASES: dict[str, ColumnSpec] = {
    **{name: SPECS[name] for name in ("M1", "M2", "M3", "M4", "P1")},
    **J_CASES,
    "C-MW": column_spec("C-MW"),
    "C-EW": column_spec("C-EW"),
}


def provider_of(name: str) -> PropertyProvider:
    return REAL if name.startswith("C-") else PROVIDER


def _digest(rows: Contribution) -> str:
    """Ids, kinds, accumulations, origins, parameters (`float.hex`) and block wiring."""
    document = {
        "v": list(rows.variable_ids),
        "vk": dict(rows.variable_kinds),
        "e": [[e.equation_id, e.accumulation, e.origin] for e in rows.equations],
        "rk": dict(rows.row_kinds),
        "p": [[p, float(rows.parameters[p]).hex()] for p in rows.parameter_ids],
        "b": [[b.block_id, list(rows.block_inputs[b.block_id])] for b in rows.blocks],
    }
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()[:16]


# -- a revision instance for a registered standalone case ---------------------------------------


def _end_entries(spec: ColumnSpec) -> dict[str, float]:
    entries: dict[str, float] = {}
    for end in (CONDENSER, REBOILER):
        given = spec.end_specification(end)
        if given is None:
            continue
        attribute = given.component if given.component is not None else given.stage
        suffix = "" if attribute is None else f".{attribute}"
        entries[f"{end}_{given.kind}{suffix}"] = given.value
    return entries


def view_of(spec: ColumnSpec) -> InstanceView:
    """The `syn001.column` instance a revision writes for `spec` (§4.7.1): side feeds on `feed`
    as `S-F<k>`, `top`/`bottom` as `S-TOP`/`S-BOT`, products `S-D` and `S-B`."""
    ports: dict[str, tuple[str, ...]] = {}
    directions: dict[str, Any] = {}
    phases: dict[str, Any] = {}
    parameters: dict[str, float] = {
        "stage_count": float(spec.stage_count),
        **{f"stage_pressure.{j}": p for j, p in enumerate(spec.pressures, start=1)},
        **{f"stage_duty.{j}": q for j, q in enumerate(spec.duties, start=1) if q is not None},
        **_end_entries(spec),
    }
    if spec.top is not None:
        ports[TOP], directions[TOP], phases[TOP] = ("S-TOP",), "inlet", spec.top.phase
    if spec.bottom is not None:
        ports[BOTTOM], directions[BOTTOM], phases[BOTTOM] = ("S-BOT",), "inlet", spec.bottom.phase
    if spec.sides:
        streams = tuple(f"S-F{k}" for k in range(1, len(spec.sides) + 1))
        ports["feed"], directions["feed"] = streams, "inlet"
        (phases["feed"],) = {side.state.phase for side in spec.sides}
        for stream, side in zip(streams, spec.sides, strict=True):
            parameters[f"feed_stage.{stream}"] = float(side.stage)
    ports["distillate"], directions["distillate"] = ("S-D",), "outlet"
    phases["distillate"] = "LIQUID" if spec.total_condenser else "VAPOR"
    ports["bottoms"], directions["bottoms"], phases["bottoms"] = ("S-B",), "outlet", "LIQUID"
    return InstanceView(
        unit_id=spec.unit_id,
        model_id="syn001.column",
        ports=ports,
        directions=directions,
        phases=phases,
        parameters=parameters,
        pins={},
    )


def renamed(spec: ColumnSpec) -> ColumnSpec:
    """`spec` with its side feeds named `feed1, feed2, …` (§4.7.1)."""
    sides = tuple(replace(side, port=f"feed{k}") for k, side in enumerate(spec.sides, start=1))
    return replace(spec, sides=sides)


def structure_of(name: str) -> ColumnStructure:
    spec = CASES[name]
    return column_structure(view_of(spec), spec.components)


@pytest.mark.parametrize("name", list(CASES))
def test_the_parser_reads_every_registered_case(name: str) -> None:
    """`column_structure` on the case's revision instance, with the case's inlet states, is the
    case (side feeds renamed)."""
    spec = renamed(CASES[name])
    structure = structure_of(name)
    states = {inlet.port: inlet.state for inlet in spec.inlets()}
    assert structure.spec(states) == spec


# -- S11.A21 --------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(BASE_DIGESTS))
def test_a21_links_none_is_the_base(name: str) -> None:
    rows = declared_rows(CASES[name], PROVIDER, DECLARATION_CONTEXT)
    assert _digest(rows) == BASE_DIGESTS[name]
    assert (
        _digest(declared_rows(CASES[name], PROVIDER, DECLARATION_CONTEXT, links=None))
        == (BASE_DIGESTS[name])
    )


# -- S11.A20 --------------------------------------------------------------------------------------


def _recovery_ends(spec: ColumnSpec) -> list[str]:
    return [
        end
        for end in spec.ends()
        if (found := spec.end_specification(end)) is not None and found.kind == "recovery"
    ]


@pytest.mark.parametrize("name", list(CASES))
def test_a20_link_mode_replaces_the_pins_and_keeps_the_dof(name: str) -> None:
    spec = renamed(CASES[name])
    provider = provider_of(name)
    structure = structure_of(name)
    standalone = declared_rows(spec, provider, DECLARATION_CONTEXT)
    linked = declared_rows(spec, provider, DECLARATION_CONTEXT, links=structure.links())
    width = len(spec.components) + 2
    inlets = spec.inlets()
    recoveries = len(_recovery_ends(spec))

    std_rows = [e.equation_id for e in standalone.equations]
    link_rows = [e.equation_id for e in linked.equations]
    pins = [
        row
        for row in std_rows
        if any(row.startswith(f"{inlet_row_id(spec.unit_id, i.port, '')}") for i in inlets)
    ]
    assert len(pins) == width * len(inlets)
    products = [row for row in link_rows if ":product:" in row]
    assert len(products) == 2 * width
    recovery_rows = [row for row in link_rows if row.endswith(":spec:recovery_definition")]
    assert len(recovery_rows) == recoveries
    # The link rows keep the pin rows' ids and kinds, and nothing else changes id.
    assert [r for r in link_rows if r not in products and r not in recovery_rows] == std_rows
    for row in pins:
        assert linked.row_kinds[row] == standalone.row_kinds[row]
    families = {e.equation_id: e.origin.split("#")[1] for e in linked.equations}
    assert {families[row] for row in pins} == {"COL-inlet-link"}
    assert {families[row] for row in products} == {"COL-product-link"}
    # Owned columns: the standalone's (inlet columns included) plus one `w` per recovery end.
    extra = [v for v in linked.variable_ids if v not in standalone.variable_ids]
    assert extra == [
        recovery_flow_id(spec.unit_id, spec.end_stage(e)) for e in _recovery_ends(spec)
    ]
    assert set(standalone.variable_ids) <= set(linked.variable_ids)
    # DOF: the stream columns (inlets and products) join; the feed streams' pins join as rows.
    streams = width * (len(inlets) + 2)
    feed_pins = width * len(inlets)
    linked_dof = len(linked.variable_ids) + streams - len(link_rows) - feed_pins
    assert linked_dof == len(standalone.variable_ids) - len(std_rows)
    # No pinned value is formed from an inlet state.
    inlet_pins = [p for p in linked.parameter_ids if inlet_stream(spec.unit_id, "") in p]
    assert inlet_pins == []


def _float_rows(rows: Contribution, state: dict[str, float]) -> dict[str, float]:
    """The link, slot and definition rows of `rows` (block-free) in binary64 at `state`."""
    return {
        equation.equation_id: float(
            equation.build(state, {}, rows.parameters, None)  # type: ignore[arg-type]
        )
        for equation in rows.equations
        if any(part in equation.equation_id for part in (":inlet:", ":product:", ":spec:"))
    }


@pytest.mark.parametrize("name", ["J1", "J2", "J4", "J7", "J8"])
def test_a20_the_q7_rows_vanish_at_the_standalone_root(name: str) -> None:
    """§4.7.4: at S06's registered root, with `u = F_ref·x` and `w = F_ref·n_c/F_c`, the purity
    and recovery definitions vanish to rounding, the slots to the registered state tolerance,
    and every link row exactly when the streams carry the inlet and product values."""
    standalone = CASES[name]
    spec = renamed(standalone)
    unit = spec.unit_id
    root = expected_root(name)
    state = {key.replace(".inlet.feed.", ".inlet.feed1."): value for key, value in root.items()}
    feeds = component_feeds(spec)
    for end in spec.ends():
        given = spec.end_specification(end)
        assert given is not None
        stage = spec.end_stage(end)
        if given.kind == "purity":
            assert given.component is not None
            flow = state[product_flow_id(spec, end, given.component)]
            state[purity_flow_id(unit, stage)] = F_REF * flow / state[product_total_id(spec, end)]
        if given.kind == "recovery":
            assert given.component is not None
            flow = state[product_flow_id(spec, end, given.component)]
            state[recovery_flow_id(unit, stage)] = (
                F_REF * flow / feeds[spec.components.index(given.component)]
            )
    structure = structure_of(name)
    links = structure.links()
    for inlet in spec.inlets():
        internal, stream = inlet_stream(unit, inlet.port), links.inlets[inlet.port]
        for c in spec.components:
            state[flow_id(stream, c)] = state[flow_id(internal, c)]
        state[temperature_id(stream)] = state[temperature_id(internal)]
        state[pressure_id(stream)] = state[pressure_id(internal)]
    for _product, end, stage, stream in (
        ("distillate", CONDENSER, 1, links.distillate),
        ("bottoms", REBOILER, spec.stage_count, links.bottoms),
    ):
        for c in spec.components:
            state[flow_id(stream, c)] = state[product_flow_id(spec, end, c)]
        state[temperature_id(stream)] = state[f"{unit}.stage.{stage}.T"]
        state[pressure_id(stream)] = state[f"{unit}.stage.{stage}.P"]

    linked = declared_rows(spec, PROVIDER, DECLARATION_CONTEXT, links=links)
    values = _float_rows(linked, state)
    for row, value in values.items():
        if ":inlet:" in row or ":product:" in row:
            assert value == 0.0, row
    tolerance = 1e-6 + 10 * 1e-9  # S06 §10's flow tolerance at x ≈ 1: rel 1e-6 + 10 τ_flow
    for end in spec.ends():
        given = spec.end_specification(end)
        assert given is not None
        stage = spec.end_stage(end)
        if given.kind in ("purity", "recovery"):
            definition = values[f"{unit}:stage:{stage}:spec:{given.kind}_definition"]
            assert abs(definition) <= 1e-15, (end, definition)
            slot = values[slot_row_id(unit, stage, given.kind)]
            assert abs(slot) <= tolerance, (end, slot)
            assert linked.parameters[f"{unit}.stage.{stage}.{given.kind}_reference*"] == F_REF


# -- S11.A22 --------------------------------------------------------------------------------------


def _ids(value: Any) -> list[str]:
    """Every string inside `value` (dataclasses, mappings, sequences)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in (*_ids(k), *_ids(v))]
    if isinstance(value, tuple | list | set | frozenset):
        return [s for item in value for s in _ids(item)]
    if hasattr(value, "__dataclass_fields__"):
        return [s for field in value.__dataclass_fields__ for s in _ids(getattr(value, field))]
    return []


@pytest.mark.parametrize("name", list(CASES))
def test_a22_no_nan_reaches_a_structural_output(name: str) -> None:
    structure = structure_of(name)
    structural = structural_spec(structure)
    assert all(math.isnan(a) for inlet in structural.inlets() for a in (*inlet.state.n,)), (
        "the structural spec carries NaN inlet states"
    )
    rows = declared_rows(
        structural, provider_of(name), DECLARATION_CONTEXT, links=structure.links()
    )
    assert all(math.isfinite(rows.parameters[p]) for p in rows.parameter_ids)
    outputs = (
        rows.variable_ids,
        [e.equation_id for e in rows.equations],
        rows.parameter_ids,
        dict(rows.block_inputs),
        lifted_splits(structural),
        zero_flow_forms(structural),
        closure_types(structural),
        split_temperatures(structural),
    )
    for output in outputs:
        found = _ids(output)
        assert found, output
        assert not any("nan" in text.lower() for text in found)


# -- the parser's refusals ------------------------------------------------------------------------


def test_the_parser_refuses_an_undeclared_inlet_and_two_end_specifications() -> None:
    view = view_of(CASES["M1"])
    lifted = replace(view, phases={**view.phases, "feed": None})
    with pytest.raises(RevisionError) as raised:
        column_structure(lifted, CASES["M1"].components)
    assert raised.value.code == "port_unsupported(S02.feed)"
    doubled = replace(view, parameters={**view.parameters, "condenser_distillate_rate": 0.4})
    with pytest.raises(RevisionError) as raised:
        column_structure(doubled, CASES["M1"].components)
    assert raised.value.code == "specification_conflict(S02.condenser)"
    top = replace(
        view_of(CASES["M3"]), phases={**view_of(CASES["M3"]).phases, "distillate": "LIQUID"}
    )
    with pytest.raises(RevisionError) as raised:
        column_structure(top, CASES["M3"].components)
    assert raised.value.code == "specification_conflict(S02.distillate)"


def test_the_recovery_definition_sums_its_inlets_left_associated() -> None:
    """§4.7.4: `F_ref n_c − w Σ_k n_{k,c}`, the sum in the given order, left-associated."""
    from openflowsheet.models.rows import scaled_sum_definition_row

    build = scaled_sum_definition_row("n", "F", "w", ("a", "b", "c"))
    values = {"n": 0.3, "w": 0.7, "a": 0.1, "b": 0.2, "c": 1e-17}
    found = build(values, {}, {"F": 1.0}, None)  # type: ignore[arg-type]
    assert found == 1.0 * 0.3 - 0.7 * ((0.1 + 0.2) + 1e-17)
    with pytest.raises(ValueError):
        scaled_sum_definition_row("n", "F", "w", ())


# -- S11.A92: the end parameters (§10.5, R-824) ---------------------------------------------------

#: The twelve end parameters, each with an attribute where its kind takes one, and the
#: `EndSpecification` it configures (value 0.5; the parser judges no value).
END_NAMES: dict[str, tuple[str, EndSpecification]] = {
    "condenser_reflux_ratio": (CONDENSER, EndSpecification("reflux_ratio", 0.5)),
    "condenser_distillate_rate": (CONDENSER, EndSpecification("distillate_rate", 0.5)),
    "condenser_duty": (CONDENSER, EndSpecification("duty", 0.5)),
    "condenser_purity.A": (CONDENSER, EndSpecification("purity", 0.5, component="A")),
    "condenser_recovery.B": (CONDENSER, EndSpecification("recovery", 0.5, component="B")),
    "condenser_temperature.2": (CONDENSER, EndSpecification("temperature", 0.5, stage=2)),
    "reboiler_boilup_ratio": (REBOILER, EndSpecification("boilup_ratio", 0.5)),
    "reboiler_bottoms_rate": (REBOILER, EndSpecification("bottoms_rate", 0.5)),
    "reboiler_duty": (REBOILER, EndSpecification("duty", 0.5)),
    "reboiler_purity.C": (REBOILER, EndSpecification("purity", 0.5, component="C")),
    "reboiler_recovery.A": (REBOILER, EndSpecification("recovery", 0.5, component="A")),
    "reboiler_temperature.6": (REBOILER, EndSpecification("temperature", 0.5, stage=6)),
}


def _with_end(view: InstanceView, ends: dict[str, float]) -> InstanceView:
    """`view` with its end parameters replaced by `ends`."""
    kept = {k: v for k, v in view.parameters.items() if not k.startswith(END_PREFIXES)}
    return replace(view, parameters={**kept, **ends})


def test_the_twelve_end_parameters_are_the_end_kinds() -> None:
    assert len(END_NAMES) == 12
    assert {name.partition(".")[0] for name in END_NAMES} == set(END_PARAMETERS)


@pytest.mark.parametrize("name", sorted(END_NAMES))
def test_each_end_parameter_configures_its_end_specification(name: str) -> None:
    """S11.A92: each of the twelve names configures its `EndSpecification` at its end; the
    other end keeps M1's."""
    end, expected = END_NAMES[name]
    view = view_of(CASES["M1"])
    other = REBOILER if end == CONDENSER else CONDENSER
    keep = {k: v for k, v in view.parameters.items() if k.startswith(f"{other}_")}
    structure = column_structure(_with_end(view, {**keep, name: 0.5}), CASES["M1"].components)
    found = structure.condenser_spec if end == CONDENSER else structure.reboiler_spec
    assert found == expected


@pytest.mark.parametrize(
    "name", ["condenser.reflux_ratio", "reboiler.boilup_ratio", "condenser_boilup_ratio"]
)
def test_a_dotted_or_foreign_end_parameter_is_unsupported(name: str) -> None:
    """S11.A92: the dotted spelling, and a kind the end does not take, by name."""
    view = view_of(CASES["M1"])
    with pytest.raises(RevisionError) as raised:
        column_structure(
            replace(view, parameters={**view.parameters, name: 2.0}), CASES["M1"].components
        )
    assert raised.value.code == f"parameter_unsupported(S02.{name})"


def test_two_end_parameters_at_one_end_conflict() -> None:
    """S11.A92: two `condenser_*` names."""
    view = _with_end(
        view_of(CASES["M1"]),
        {"condenser_reflux_ratio": 2.0, "condenser_duty": -1.0, "reboiler_boilup_ratio": 1.5},
    )
    with pytest.raises(RevisionError) as raised:
        column_structure(view, CASES["M1"].components)
    assert raised.value.code == "specification_conflict(S02.condenser)"
