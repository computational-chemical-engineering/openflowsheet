"""X04 WO-1: the display core, `display-conversion-v1` (ADR 0075 D2, D3, D5).

Assertions A1–A8 of `docs/derivations/X04-test-specification.md` §5 U. Every expected value comes
from `docs/derivations/scripts/x04_reference.json` (`x04_reference.py --check`); every comparison
is exact — bit for bit, including the sign of zero (§2).
"""

from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from openflowsheet import units
from openflowsheet.units import (
    CONVERSION_ROWS,
    DISPLAY_CONVERSION_ID,
    DISPLAY_KINDS,
    DISPLAY_ROWS,
    DisplayUnits,
    DisplayUnitsError,
    convert_input_value,
    display_item,
    parse_display_units,
)
from openflowsheet.units import display as display_module
from openflowsheet.units.display import GAUGE_ROWS, PRESETS, TEXT_UNITS, row_to_si, text_unit

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "derivations" / "scripts" / "x04_reference.py"
REFERENCE: dict[str, Any] = json.loads(SCRIPT.with_suffix(".json").read_text(encoding="utf-8"))
STATES = {state["id"]: state for state in REFERENCE["display_states"]}


def _ambient(text: str | None) -> float | None:
    return None if text is None else float(text)


def _units(kind: str, unit: str, ambient: str | None) -> DisplayUnits:
    return DisplayUnits({kind: unit}, _ambient(ambient))


def _bits(x: float) -> str:
    return x.hex()


# -- A1. Table ----------------------------------------------------------------------------------


def test_a1_display_table_equals_the_reference() -> None:
    assert DISPLAY_CONVERSION_ID == "display-conversion-v1" == REFERENCE["conversion_id"]
    rows = [
        {
            "kind": row.kind,
            "unit": row.unit,
            "a": f"{row.a.numerator}/{row.a.denominator}",
            "b": row.b if isinstance(row.b, str) else f"{row.b.numerator}/{row.b.denominator}",
            "direction": row.direction,
            "csv_suffix": row.csv_suffix,
        }
        for row in DISPLAY_ROWS.values()
    ]
    assert rows == REFERENCE["rows"]
    assert list(DISPLAY_ROWS) == [(row["kind"], row["unit"]) for row in rows]
    assert GAUGE_ROWS == {("pressure", "barg"), ("pressure", "psig")}
    kinds = {
        kind: {"si_unit": spec.si_unit, "dimension": list(spec.dimension)}
        for kind, spec in DISPLAY_KINDS.items()
    }
    expected = {
        kind: {"si_unit": spec["si_unit"], "dimension": spec["dimension"]}
        for kind, spec in REFERENCE["display_kinds"].items()
    }
    assert kinds == expected
    assert list(DISPLAY_KINDS) == list(REFERENCE["display_kinds"])
    assert {name: dict(entries) for name, entries in PRESETS.items()} == REFERENCE["presets"]


# -- A2. One registry ---------------------------------------------------------------------------


def test_a2_one_registry_for_both_directions() -> None:
    input_rows = {key: row for key, row in CONVERSION_ROWS.items() if row.rule != "mass_to_molar"}
    for key, row in input_rows.items():
        assert key in DISPLAY_ROWS, key
        assert (DISPLAY_ROWS[key].a, DISPLAY_ROWS[key].b) == (row.a, row.b), key
    adr0016_kinds = {kind for kind, _unit in CONVERSION_ROWS}
    missing = {
        key for key in DISPLAY_ROWS if key[0] in adr0016_kinds and key not in CONVERSION_ROWS
    }
    assert missing == {("pressure", "barg"), ("pressure", "psig")}
    for unit in ("g/s", "kg/h"):
        assert DISPLAY_ROWS[("mass_flow", unit)].a == CONVERSION_ROWS[("molar_flow", unit)].a
        assert CONVERSION_ROWS[("molar_flow", unit)].rule == "mass_to_molar"


# -- A3. Display states -------------------------------------------------------------------------


@pytest.mark.parametrize("state", REFERENCE["display_states"], ids=lambda state: state["id"])
def test_a3_display_states(state: dict[str, Any]) -> None:
    kind, unit, ambient = state["kind"], state["unit"], state["ambient_pressure"]
    x = float(state["si_value"])
    item = display_item(x, kind, _units(kind, unit, ambient))
    if state["display_value"] is None:
        assert item == {
            "value": None,
            "unit": unit,
            "reason": {"code": "display_out_of_range", "params": {"kind": kind, "unit": unit}},
        }
        return
    assert item is not None and set(item) == {"value", "unit"}
    value = item["value"]
    assert item["unit"] == unit
    assert type(value) is float
    assert repr(value) == state["display_value"]
    if value == 0:
        assert math.copysign(1.0, value) == 1.0
    if state["converts_back_to_si"]:
        assert _bits(row_to_si(value, kind, unit, _ambient(ambient))) == _bits(x)


@pytest.mark.parametrize(
    ("state_id", "expected"),
    [
        ("DS01", 25.0),
        ("DS02", 298.15),
        ("DS03", 0.0),
        ("DS05", -40.0),
        ("DS08", 98.33),
        ("DS10", 25.0),
        ("DS14", 14.695948775513449),
        ("DS17", 0.06325),
        ("DS19", -0.51325),
        ("DS25", 1.0),
        ("DS44", 0.0),
        ("DS46", 3.6e305),
        ("DS51", 313.3313778486533),
    ],
)
def test_a3_spot_values(state_id: str, expected: float) -> None:
    state = STATES[state_id]
    kind, unit = state["kind"], state["unit"]
    item = display_item(
        float(state["si_value"]), kind, _units(kind, unit, state["ambient_pressure"])
    )
    assert item is not None
    assert _bits(item["value"]) == _bits(expected)


def test_a3_out_of_range_states_are_the_registered_ones() -> None:
    assert sorted(i for i, s in STATES.items() if s["display_value"] is None) == ["DS45", "DS47"]


# -- A4. Round trips ----------------------------------------------------------------------------


def _input_to_si(trip: dict[str, Any]) -> float:
    kind, unit, value = trip["kind"], trip["unit"], float(trip["input"])
    ambient = _ambient(trip["ambient_pressure"])
    if (kind, unit) in GAUGE_ROWS:
        return row_to_si(value, kind, unit, ambient)
    component: str | None = None
    target = f"state.{kind}"
    if kind == "temperature":
        target = "state.T"
    elif kind == "dimensionless":
        target = "parameters.split_fraction"
    elif kind == "molar_flow":
        component = "A"
    si_value, _record = convert_input_value("x04", value, unit, kind, kind, target, component, {})
    return si_value


@pytest.mark.parametrize(
    "trip",
    REFERENCE["round_trips"],
    ids=lambda t: f"{t['kind']}-{t['unit']}-{t['input']}-{t['ambient_pressure']}",
)
def test_a4_round_trips(trip: dict[str, Any]) -> None:
    si_value = _input_to_si(trip)
    assert repr(si_value) == trip["si_value"]
    kind, unit = trip["kind"], trip["unit"]
    item = display_item(si_value, kind, _units(kind, unit, trip["ambient_pressure"]))
    assert item is not None
    assert _bits(item["value"]) == _bits(float(trip["input"]))


def test_a4_registered_trips_include_the_plain_rounding_misses() -> None:
    trips = REFERENCE["round_trips"]
    assert len(trips) == 400
    assert sum(trip["plain_rounding"] != trip["input"] for trip in trips) == 63


# -- A5. Sample reproduction --------------------------------------------------------------------


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("x04_reference_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


def test_a5_sample_reproduction() -> None:
    generator = _load_generator()
    recorded: list[tuple[float, str, str, float | None, dict[str, Any]]] = []
    original = generator.display

    def recording(x: float, kind: str, unit: str, ambient: float | None = None) -> dict[str, Any]:
        result: dict[str, Any] = original(x, kind, unit, ambient)
        recorded.append((x, kind, unit, ambient, result))
        return result

    generator.__dict__["display"] = recording
    sample = generator.sampled()
    assert json.loads(json.dumps(sample)) == REFERENCE["sample"]
    assert len(recorded) > 60_000
    mismatches = []
    for x, kind, unit, ambient, result in recorded:
        item = display_item(x, kind, _units(kind, unit, None if ambient is None else repr(ambient)))
        assert item is not None
        expected = result["value"]
        got = item["value"]
        if (expected is None) != (got is None) or (
            expected is not None and _bits(expected + 0.0) != _bits(got)
        ):
            mismatches.append((x, kind, unit, ambient, expected, got))
    assert mismatches == []


# -- A6. Grammar --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    [case for case in REFERENCE["preferences"] if case["id"] != "PU16"],
    ids=lambda case: case["id"],
)
def test_a6_preference_grammar(case: dict[str, Any]) -> None:
    ambient = _ambient(case["ambient_pressure"])
    expected = case["expected"]
    if "refused" in expected:
        refused = expected["refused"]
        with pytest.raises(DisplayUnitsError) as caught:
            parse_display_units(case["text"], ambient)
        error = caught.value
        assert (error.api_error, error.reason, error.message) == (
            refused["api_error"],
            refused["reason"],
            refused["message"],
        )
        assert str(error) == refused["message"]
        assert error.pointer == (
            "/display_units" if refused["api_error"] == "invalid_request" else None
        )
        return
    resolved = parse_display_units(case["text"], ambient)
    document = resolved.as_document()
    want_ambient = expected["ambient_pressure"]
    assert document == {
        "units": expected["units"],
        "ambient_pressure": None
        if want_ambient is None
        else {"value": float(want_ambient), "unit": "Pa"},
    }
    assert dict(resolved) == expected["units"]


def test_a6_canonical_text() -> None:
    assert parse_display_units("eng", None).canonical() == (
        "enthalpy_flow=kW,heat_rate=kW,mass_flow=kg/h,molar_enthalpy=kJ/mol,molar_flow=kmol/h,"
        "power=kW,pressure=bar,specific_enthalpy=kJ/kg,specific_entropy=kJ/(kg K),"
        "temperature=degC,temperature_difference=degC"
    )
    assert parse_display_units("si", None).canonical() == ""


def test_a6_display_units_is_an_immutable_mapping() -> None:
    resolved = parse_display_units("temperature=degC,pressure=barg", 101325.0)
    assert resolved == DisplayUnits({"pressure": "barg", "temperature": "degC"}, 101325.0)
    assert resolved != DisplayUnits({"pressure": "barg", "temperature": "degC"}, 95000.0)
    assert list(resolved) == ["pressure", "temperature"] and len(resolved) == 2
    assert hash(resolved) == hash(DisplayUnits(dict(resolved), 101325.0))
    # The ambient is kept iff a gauge unit is in the map (ADR 0075 D5.4, PU08).
    assert DisplayUnits({"pressure": "bar"}, 101325.0).ambient_pressure is None
    with pytest.raises(ValueError):
        DisplayUnits({"pressure": "barg"})
    with pytest.raises(ValueError):
        DisplayUnits({"temperature": "K"})


# -- A7. Kinds decide ---------------------------------------------------------------------------


def test_a7_kinds_decide_never_the_si_unit() -> None:
    celsius = parse_display_units("temperature=degC", None)
    assert display_item(298.15, "temperature_difference", celsius) is None
    assert display_item(298.15, None, celsius) is None
    assert display_item(298.15, "temperature", celsius) == {"value": 25.0, "unit": "degC"}
    kilowatt = parse_display_units("heat_rate=kW", None)
    assert display_item(1000.0, "power", kilowatt) is None
    assert display_item(1000.0, "heat_rate", kilowatt) == {"value": 1.0, "unit": "kW"}


def test_a7_reexported_from_units() -> None:
    for name in (
        "DISPLAY_CONVERSION_ID",
        "DISPLAY_KINDS",
        "DISPLAY_ROWS",
        "DisplayUnits",
        "DisplayUnitsError",
        "display_item",
        "parse_display_units",
        "text_unit",
    ):
        assert name in units.__all__
        assert getattr(units, name) is getattr(display_module, name)


def test_d7_7_text_spelling_maps_degc_and_degf_only() -> None:
    """ADR 0075 D7.7 (FQ4, Frank, 2026-11-09): human text shows `°C`/`°F`; the display item, a
    machine member, keeps the D2 spelling; every other D2 unit is its own text spelling."""
    assert dict(TEXT_UNITS) == {"degC": "°C", "degF": "°F"}
    assert text_unit("degC") == "°C" and text_unit("degF") == "°F"
    others = {unit for (_kind, unit) in DISPLAY_ROWS} - set(TEXT_UNITS)
    assert others and all(text_unit(unit) == unit for unit in others)
    assert {kind for (kind, unit) in DISPLAY_ROWS if unit in TEXT_UNITS} == {
        "temperature",
        "temperature_difference",
    }
    for kind in ("temperature", "temperature_difference"):
        item = display_item(298.15, kind, parse_display_units(f"{kind}=degF", None))
        assert item is not None and item["unit"] == "degF"


# -- A8. Generator ------------------------------------------------------------------------------


def test_a8_generator_check() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    lines = completed.stdout.splitlines()
    assert sum(line.startswith("PASS ") for line in lines) == 17
    assert "x04_reference.json is byte-identical to --emit" in lines


def test_a8_generator_is_lint_clean() -> None:
    ruff = Path(sys.executable).with_name("ruff")
    command = [str(ruff)] if ruff.is_file() else [sys.executable, "-m", "ruff"]
    for arguments in (["check"], ["format", "--check"]):
        completed = subprocess.run(
            [*command, *arguments, str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
