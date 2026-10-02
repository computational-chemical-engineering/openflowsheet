"""T05 W10: the rows at the twin's causal solutions and the dormant-flow singularity (spec §4.7,
§14; A06, A15).

A06 evaluates each model's assembled rows — the trial-state harness's assembly path, compiled
through K01 — at the design lane's registered causal solution of its cases, every coordinate the
double its 20-digit string rounds to, and requires each row within K04's `τ_kind`. The expected
value is zero; §14 argues the floor (`≤ 2e-10 W`, `≤ 1e-14 mol/s`: one ulp of `T` times
`∂Ḣ/∂T`), so the ratios are the implementation's rows agreeing with the twin's evaluator, not a
self-comparison. Worst ratios per model: `docs/t05-measurements.md`, "W10".

A15 evaluates the Jacobian at the registered dormant states (`ref.dormant_temperature_columns`)
and requires each listed temperature's column to be nonzero in exactly the listed rows.

A13 and A14 are the per-model modules' (PHF-2 against K02's flash, PHF-7 = VLV-2, RX-7 = the
heater, HX-1/2/3; the exact zeros, PHF-6's route and every dormant case's label and zeros), and
are not repeated here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
from t05_support import REF
from t05_trial_states import assemble_trial
from test_t05_manifests import MODELS, Model, unit_trial

from openflowsheet.compile.casadi_backend import CasadiCompiledProblem, compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import UnitModel
from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.verify.checks import KIND_TOLERANCE

#: Spec §15 A06: the cases whose causal solution the rows are evaluated at.
A06_CASES = (
    "PHF-1",
    "PHF-5",
    "PHF-6",
    "VLV-2",
    "VLV-5",
    "PUMP-1",
    "RX-3",
    "RX-4",
    "RX-5",
    "SEP-2",
    "HX-1",
    "HX-4",
)

Values = dict[str, Decimal]


def _stream(values: Values, stream_id: str, document: Mapping[str, Any]) -> None:
    for component, flow in zip(COMPONENTS, document["n_mol_per_s"], strict=True):
        values[f"{stream_id}.n.{component}"] = Decimal(flow)
    values[f"{stream_id}.T"] = Decimal(document["T_K"])
    values[f"{stream_id}.P"] = Decimal(document["P_Pa"])


def _split(values: Values, stream_id: str, vapour: Sequence[str], liquid: Sequence[str]) -> None:
    """A lifted stream's split; `V` and `L` are the exact sums of the registered strings."""
    for component, up, down in zip(COMPONENTS, vapour, liquid, strict=True):
        values[f"{stream_id}.vap.{component}"] = Decimal(up)
        values[f"{stream_id}.liq.{component}"] = Decimal(down)
    values[f"{stream_id}.V"] = sum((Decimal(flow) for flow in vapour), Decimal(0))
    values[f"{stream_id}.L"] = sum((Decimal(flow) for flow in liquid), Decimal(0))


def registered_state(case_id: str) -> Values:
    """Every column of the unit's assembly at the twin's causal solution of `case_id`.

    Streams are named as `test_t05_manifests.MODELS` wires them (the inlet `S1`, outlets from
    `S2`; the exchanger's hot side `S1`/`S2`, cold `S3`/`S4`). VLV-5's inlet is lifted: its split
    is VLV-2's registered outlet split, the stream spec §8 says VLV-5 reads.
    """
    case = REF["unit_cases"][case_id]
    model, inputs, expected = case["model"], case["inputs"], case["expected"]
    values: Values = {}
    if model == "syn001.heat_exchanger":
        _stream(values, "S1", inputs["hot_inlet"])
        _stream(values, "S2", expected["hot_outlet"])
        _stream(values, "S3", inputs["cold_inlet"])
        _stream(values, "S4", expected["cold_outlet"])
        values["U-HX.Q"] = Decimal(expected["duty_W"])
        return values

    _stream(values, "S1", inputs["inlet"])
    if model == "syn001.ph_flash":
        _stream(values, "S2", expected["vapor"])
        _stream(values, "S3", expected["liquid"])
        for stream_id, port in (("S2", "vapor"), ("S3", "liquid")):
            flows = expected[port]["n_mol_per_s"]
            values[f"{stream_id}.N"] = sum((Decimal(n) for n in flows), Decimal(0))
        values["U-PHF.Q"] = Decimal(expected["duty_W"])
    elif model == "syn001.component_separator":
        _stream(values, "S2", expected["top"])
        _stream(values, "S3", expected["bottom"])
        values["U-SEP.Q"] = Decimal(expected["duty_W"])
    else:
        outlet = expected["outlet"]
        _stream(values, "S2", outlet)
        if model == "syn001.liquid_pump":
            values["U-PUMP.W"] = Decimal(expected["work_W"])
        else:
            _split(values, "S2", outlet["vapor_n_mol_per_s"], outlet["liquid_n_mol_per_s"])
        if model == "syn001.conversion_reactor":
            values["U-RX.Q"] = Decimal(expected["duty_W"])
            values["U-RX.xi"] = Decimal(expected["extent_mol_per_s"])
        if model == "syn001.valve" and inputs["inlet_phase"] is None:
            producer = REF["unit_cases"]["VLV-2"]["expected"]["outlet"]
            # VLV-5's inlet is VLV-2's outlet with `T` as a double (spec §8).
            assert float(producer["T_K"]) == float(inputs["inlet"]["T_K"])
            _split(values, "S1", producer["vapor_n_mol_per_s"], producer["liquid_n_mol_per_s"])
    return values


@dataclass(frozen=True)
class Evaluated:
    problem: CasadiCompiledProblem
    variable_ids: tuple[str, ...]
    row_kinds: Mapping[str, str]
    x: np.ndarray[Any, np.dtype[np.float64]]
    context: EvaluationContext


def evaluate_at(model: Model, unit: UnitModel, inlet_phase: Any, values: Values) -> Evaluated:
    """Compile the unit alone and place `values`, each rounded once to a double, as `x`."""
    spec = assemble_trial(unit_trial(model, unit, inlet_phase), label="T05-W10")
    assert set(spec.variable_ids) == set(values), (sorted(set(spec.variable_ids) ^ set(values)),)
    problem = compile_problem(spec)
    context = EvaluationContext(
        model_version=problem.metadata.model_version,
        constants_sha256=problem.metadata.constants_sha256,
    )
    x = np.array([float(values[name]) for name in spec.variable_ids])
    return Evaluated(problem, spec.variable_ids, spec.row_kinds, x, context)


def rows_at_solution(case_id: str) -> dict[str, tuple[float, str]]:
    """`row -> (|value|, kind)` of the case's unit at its registered causal solution."""
    case = REF["unit_cases"][case_id]
    model = MODELS[case["model"]]
    inputs = case["inputs"]
    evaluated = evaluate_at(
        model, model.build(inputs), inputs.get("inlet_phase", "LIQUID"), registered_state(case_id)
    )
    residual = evaluated.problem.residual(evaluated.x, evaluated.context)
    assert residual.status == "ok", residual.message
    assert residual.values is not None
    kinds = evaluated.row_kinds
    return {
        row: (abs(float(value)), kinds[row])
        for row, value in zip(residual.equation_ids, residual.values, strict=True)
    }


def worst_ratio(rows: Mapping[str, tuple[float, str]]) -> tuple[float, str]:
    """The largest `|row| / τ_kind`, and its row."""
    return max((value / KIND_TOLERANCE[kind], row) for row, (value, kind) in rows.items())


def test_the_a06_cases_are_registered_and_ok() -> None:
    for case_id in A06_CASES:
        assert REF["unit_cases"][case_id]["expected"]["status"] == "ok", case_id
    assert {REF["unit_cases"][case_id]["model"] for case_id in A06_CASES} == set(MODELS)


@pytest.mark.parametrize("case_id", A06_CASES)
def test_a06_rows_at_the_twins_causal_solution_are_within_tau_kind(case_id: str) -> None:
    rows = rows_at_solution(case_id)
    ratio, row = worst_ratio(rows)
    assert ratio <= 1.0, f"{case_id}: {row} = {rows[row][0]!r}, {ratio:.3g} of tau_{rows[row][1]}"


# ----------------------------------------------------------------------------------- A15

#: `ref.dormant_temperature_columns.structure` key -> (the registered dormant case whose state it
#: is, and the configuration change that selects the keyed variant).
DORMANT_STATES: dict[str, tuple[str, dict[str, Any]]] = {
    "syn001.valve": ("VLV-Z", {}),
    "syn001.ph_flash": ("PHF-Z0", {}),
    "syn001.conversion_reactor(duty)": (
        "RX-Z",
        {"energy_specification": "duty", "value": "0.0"},
    ),
    "syn001.conversion_reactor(outlet_temperature)": ("RX-Z", {}),
    "syn001.liquid_pump": ("PUMP-Z", {}),
    "syn001.component_separator": ("SEP-Z", {}),
    "syn001.heat_exchanger(hot side dormant)": ("HX-Z0", {}),
}
STRUCTURE: Mapping[str, Mapping[str, list[str]]] = REF["dormant_temperature_columns"]["structure"]


def test_every_registered_dormant_structure_has_its_state() -> None:
    assert set(DORMANT_STATES) == set(STRUCTURE)
    for case_id, _ in DORMANT_STATES.values():
        expected = REF["unit_cases"][case_id]["expected"]
        assert expected["status"] == "ok", case_id
    # The exchanger's registered state has a dormant hot side and a flowing cold side.
    hx = REF["unit_cases"]["HX-Z0"]["inputs"]
    assert all(Decimal(n) == 0 for n in hx["hot_inlet"]["n_mol_per_s"])
    assert all(Decimal(n) > 0 for n in hx["cold_inlet"]["n_mol_per_s"])


@pytest.mark.parametrize("key", sorted(DORMANT_STATES))
def test_a15_a_dormant_temperature_column_is_read_by_exactly_the_registered_rows(
    key: str,
) -> None:
    """Spec §4.7: at zero flow `∂Ḣ/∂T = 0`, so a temperature fixed only by an energy balance is
    read by no row, or only by a copy row it shares; the zero entries are exact products with
    an exact-zero flow."""
    case_id, changes = DORMANT_STATES[key]
    case = REF["unit_cases"][case_id]
    model = MODELS[case["model"]]
    inputs = {**case["inputs"], **changes}
    evaluated = evaluate_at(
        model,
        model.build(inputs),
        inputs.get("inlet_phase", "LIQUID"),
        registered_state(case_id),
    )
    jacobian = evaluated.problem.jacobian(evaluated.x, evaluated.context)
    assert jacobian.status == "ok", jacobian.message
    for column_id, registered in STRUCTURE[key].items():
        column = list(jacobian.col_ids).index(column_id)
        reading = {
            jacobian.row_ids[jacobian.indices[offset]]
            for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1])
            if jacobian.data[offset] != 0.0
        }
        assert reading == set(registered), f"{key}: column {column_id}"
