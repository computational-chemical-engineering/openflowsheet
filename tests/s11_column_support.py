"""S11 track B test support: a revision document for a registered standalone column case, and the
column registered in the binder's tables for the length of a test (I1 registers it for good).

`column_revision(spec)` writes `feed_source(s) → syn001.column → 2 product_sinks` (§6.1 A29): one
feed source per inlet of `spec`, pinned to that inlet's state, the column's parameters as §4.7.1
names them, its end specifications as instance parameters `<end>_<kind>[.<attr>]` (§10.5), and a
product sink on each product.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from openflowsheet.application import revision_binding
from openflowsheet.application.column_binding import build_column
from openflowsheet.application.revision_binding import _COLUMN
from openflowsheet.models.revision_flowsheet import WILSON_RECORDS
from openflowsheet.models.syn001.cascade import BOTTOM, TOP
from openflowsheet.models.syn001.column import CONDENSER, MODEL_ID, REBOILER, ColumnSpec
from openflowsheet.models.syn001.column_unit import END_PARAMETERS
from openflowsheet.units import dimension_of
from openflowsheet.verify import column, table
from openflowsheet.verify.table import ModelChecks

_SI = {
    "molar_flow": "mol/s",
    "temperature": "K",
    "pressure": "Pa",
    "heat_rate": "W",
    "dimensionless": "1",
}
_TOLERANCE = {
    "molar_flow": {"absolute": 1.0e-9, "relative": 1.0e-8, "scale": 3.0},
    "temperature": {"absolute": 1.0e-6},
    "pressure": {"absolute": 0.01},
}
_END_KIND = {
    "reflux_ratio": "dimensionless",
    "boilup_ratio": "dimensionless",
    "distillate_rate": "molar_flow",
    "bottoms_rate": "molar_flow",
    "duty": "heat_rate",
    "purity": "dimensionless",
    "recovery": "dimensionless",
    "temperature": "temperature",
}


def quantity(value: float, kind: str) -> dict[str, Any]:
    return {
        "value": value,
        "unit": _SI[kind],
        "dimension": list(dimension_of(kind)),
        "kind": kind,
        "meaning": "S11 test",
        "role": "fixed",
    }


def _instance(unit: str, model: str, role: str, parameters: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": unit,
        "model": {"id": model, "version": "0.0.0-declared", "artifact_ref": None},
        "semantic_role": role,
        "parameters": dict(parameters),
        "policy": {"fidelity": "test", "validity": "test"},
    }


def _connection(stream: str, source: tuple[str, str], target: tuple[str, str], phase: str) -> Any:
    return {
        "id": stream,
        "kind": "material",
        "from": {"instance": source[0], "port": source[1]},
        "to": {"instance": target[0], "port": target[1]},
        "state_definition": "nTP-v1",
        "component_mapping": "revision_component_set",
        "phase_capability": phase,
        "notes": "S11 test",
    }


def _specification(name: str, stream: str, path: str, value: float, kind: str, **extra: Any) -> Any:
    target = {"object_type": "connection", "object_id": stream, "path": path, **extra}
    return {
        "id": name,
        "target": target,
        "kind": kind,
        "unit": _SI[kind],
        "value": value,
        "tolerance": dict(_TOLERANCE[kind]),
        "role": "fixed",
        "provenance": "S11 test",
    }


def column_parameters(spec: ColumnSpec, feeds: tuple[str, ...]) -> dict[str, Any]:
    """§4.7.1's instance parameters for `spec`, its side feeds on the streams `feeds`."""
    parameters: dict[str, Any] = {"stage_count": quantity(float(spec.stage_count), "dimensionless")}
    for j, pressure in enumerate(spec.pressures, start=1):
        parameters[f"stage_pressure.{j}"] = quantity(pressure, "pressure")
    for j, duty in enumerate(spec.duties, start=1):
        if duty is not None and duty != 0.0:
            parameters[f"stage_duty.{j}"] = quantity(duty, "heat_rate")
    for stream, side in zip(feeds, spec.sides, strict=True):
        parameters[f"feed_stage.{stream}"] = quantity(float(side.stage), "dimensionless")
    for end in (CONDENSER, REBOILER):
        given = spec.end_specification(end)
        if given is None:
            continue
        attribute = given.component if given.component is not None else given.stage
        name = f"{end}_{given.kind}" + ("" if attribute is None else f".{attribute}")
        parameters[name] = quantity(given.value, _END_KIND[given.kind])
    return parameters


def column_revision(
    spec: ColumnSpec, *, record_source: str = "syn001", unit: str = "UCOL"
) -> dict[str, Any]:
    """`feed_source(s) → syn001.column → 2 product_sinks` for `spec` (§6.1 A29)."""
    instances: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []
    specifications: list[dict[str, Any]] = []
    feeds: list[str] = []
    for k, inlet in enumerate(spec.inlets(), start=1):
        source, stream = f"U-FEED{k}", f"S-IN{k}"
        port = inlet.port if inlet.port in (TOP, BOTTOM) else "feed"
        if port == "feed":
            feeds.append(stream)
        instances.append(_instance(source, "syn001.feed_source", "feed", {}))
        phase = inlet.state.phase.lower()
        connections.append(_connection(stream, (source, "outlet"), (unit, port), phase))
        for c, value in zip(spec.components, inlet.state.n, strict=True):
            specifications.append(
                _specification(
                    f"SPEC-{stream}-n-{c}", stream, "state.n", value, "molar_flow", component=c
                )
            )
        specifications.append(
            _specification(
                f"SPEC-{stream}-T", stream, "state.T", inlet.state.temperature, "temperature"
            )
        )
        specifications.append(
            _specification(f"SPEC-{stream}-P", stream, "state.P", inlet.state.pressure, "pressure")
        )
    instances.append(_instance(unit, MODEL_ID, "separator", column_parameters(spec, tuple(feeds))))
    distillate = "liquid" if spec.total_condenser else "vapor"
    for port, phase, sink in (("distillate", distillate, "U-DIST"), ("bottoms", "liquid", "U-BOT")):
        instances.append(_instance(sink, "syn001.product_sink", "product_sink", {}))
        connections.append(_connection(f"S-{port.upper()}", (unit, port), (sink, "inlet"), phase))
    return {
        "schema_version": 1,
        "revision_id": f"S11-{spec.unit_id}-r1",
        "parent_revision": None,
        "title": "S11 column in a flowsheet",
        "description": "S11 track B test revision",
        "component_set": {"record_source": record_source, "components": list(spec.components)},
        "instances": instances,
        "connections": connections,
        "specifications": specifications,
        "provenance": {
            "actor": "S11 tests (build lane)",
            "operation": "create",
            "timestamp": "2026-10-27T00:00:00Z",
            "source_references": ["docs/derivations/S11-design.md §6.1"],
            "notes": "built in code by tests/s11_column_support.py",
        },
    }


def column_checks() -> ModelChecks:
    """The column's verifier rows (§4.8, WO-B4), the entry I1 adds to `MODEL_CHECKS`."""
    return ModelChecks(
        material=column.material,
        energy=column.energy,
        specification=column.specification,
        declared_ports=column.DECLARED_PORTS,
        admissibility=column.admissibility,
    )


@contextmanager
def column_registered(
    monkeypatch: pytest.MonkeyPatch, bases: frozenset[str] = frozenset({"syn001"})
) -> Iterator[None]:
    """The column in `MODEL_BUILDERS`, `MODEL_SIGNATURES`, `MODEL_BASES` and the verifier's
    `MODEL_CHECKS` for one test."""
    monkeypatch.setitem(revision_binding.MODEL_BUILDERS, MODEL_ID, build_column)
    monkeypatch.setitem(revision_binding.MODEL_SIGNATURES, MODEL_ID, _COLUMN)
    monkeypatch.setitem(revision_binding.MODEL_BASES, MODEL_ID, bases)
    monkeypatch.setitem(table.MODEL_CHECKS, MODEL_ID, column_checks())
    yield


# -- the registered column flowsheet cases (WO-B3e: `benchmarks/s11/flowsheets/*.json`) ----------

#: §6.1 A29's SYN-001 standalone cases embedded in a flowsheet (S02 M1–M4, S06 J1–J8).
COLUMN_CASES: tuple[str, ...] = ("M1", "M2", "M3", "M4", *(f"J{k}" for k in range(1, 9)))
#: A29's recycle case: M1 with its bottoms split 0.2 back to a side feed on stage 5.
RECYCLE_CASE = "M1-recycle"
#: §6.1 A29's Wilson cases (S10-C `ref.columns.<case>`), on the `wilson-ig-v1` basis.
WILSON_CASES: tuple[str, ...] = ("C-MW", "C-EW")
#: §7 Q11's Wilson column with a `none` end: C-MW's feed as the `top` liquid of a 10-stage stripper
#: (no condenser, C-MW's reboiler and `bottoms_rate`), which `solve_column` accepts.
WILSON_STRIPPER = "C-MW-stripper"
FLOWSHEETS = Path(__file__).resolve().parents[1] / "benchmarks" / "s11" / "flowsheets"
#: The column's sample in the T07/T08 sample tables (design note §8.3, I1): a committed case on
#: SYN-001's basis and one on Wilson's.
COLUMN_SAMPLES: tuple[str, ...] = ("M1", "C-MW")
#: The column's optional instance parameters, by the name up to the first `.` (§4.7.1, §10.5):
#: `ModelSignature` has no optional field to list them in (S11B_DECISIONS B3b).
COLUMN_OPTIONAL: frozenset[str] = frozenset(
    {"stage_pressure", "stage_duty", "feed_stage", *END_PARAMETERS}
)


def column_case_spec(name: str) -> ColumnSpec:
    """The registered standalone `ColumnSpec` of a case (`test_s02_column_wo1`/`_s06_…_wo1`,
    `test_s10c_blocks`), or Q11's stripper built from C-MW."""
    if name in WILSON_CASES:
        from test_s10c_blocks import column_spec

        return column_spec(name)
    if name == WILSON_STRIPPER:
        return wilson_stripper()
    from test_s02_column_wo1 import SPECS
    from test_s06_column_wo1 import J_CASES

    return {**SPECS, **J_CASES}[name.removesuffix("-recycle")]


def wilson_stripper(stage_count: int = 10) -> ColumnSpec:
    """§7 Q11: C-MW without its condenser, its saturated-liquid feed entering at the top."""
    from test_s10c_blocks import column_spec

    base = column_spec("C-MW")
    (feed,) = base.sides
    return replace(
        base,
        stage_count=stage_count,
        pressures=base.pressures[:stage_count],
        duties=(0.0,) * (stage_count - 1) + (None,),
        condenser="none",
        condenser_spec=None,
        sides=(),
        top=feed.state,
    )


def column_case(name: str) -> dict[str, Any]:
    """The revision of a registered column flowsheet case, as committed under `FLOWSHEETS`. The
    column instance is named after the standalone unit (`S02`/`S06`), so its stage columns carry
    the standalone ids."""
    spec = column_case_spec(name)
    wilson = name in (*WILSON_CASES, WILSON_STRIPPER)
    source = WILSON_RECORDS if wilson else "syn001"
    document = column_revision(spec, record_source=source, unit=spec.unit_id)
    document["revision_id"] = f"S11-COL-{name}"
    if name != RECYCLE_CASE:
        return document
    unit = spec.unit_id
    document["title"] = "S11 column in a flowsheet: bottoms split 0.2 back to a side feed"
    for connection in document["connections"]:
        if connection["id"] == "S-BOTTOMS":
            connection["to"] = {"instance": "U-SPLIT", "port": "inlet"}
    for instance in document["instances"]:
        if instance["id"] == unit:
            instance["parameters"]["feed_stage.S-REC"] = quantity(5.0, "dimensionless")
    document["instances"].append(
        _instance(
            "U-SPLIT",
            "syn001.stream_splitter",
            "splitter",
            {"split_fraction": quantity(0.2, "dimensionless")},
        )
    )
    document["connections"] += [
        _connection("S-REC", ("U-SPLIT", "recycle"), (unit, "feed"), "liquid"),
        _connection("S-PURGE", ("U-SPLIT", "purge"), ("U-BOT", "inlet"), "liquid"),
    ]
    return document


def committed_case(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((FLOWSHEETS / f"{name}.json").read_bytes())
    return document


if __name__ == "__main__":
    # Regenerates the committed cases: `PYTHONPATH=src:tests python tests/s11_column_support.py`.
    FLOWSHEETS.mkdir(parents=True, exist_ok=True)
    for case in (*COLUMN_CASES, RECYCLE_CASE, *WILSON_CASES, WILSON_STRIPPER):
        text = json.dumps(column_case(case), indent=2, sort_keys=True) + "\n"
        (FLOWSHEETS / f"{case}.json").write_text(text, encoding="utf-8")
