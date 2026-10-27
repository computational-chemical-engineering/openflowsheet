"""S11 track B test support: a revision document for a registered standalone column case, and the
column registered in the binder's tables for the length of a test (I1 registers it for good).

`column_revision(spec)` writes `feed_source(s) → syn001.column → 2 product_sinks` (§6.1 A29): one
feed source per inlet of `spec`, pinned to that inlet's state, the column's parameters as §4.7.1
names them, its end specifications as instance parameters `<end>_<kind>[.<attr>]` (§10.5), and a
product sink on each product.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

import pytest

from openflowsheet.application import revision_binding
from openflowsheet.application.column_binding import _COLUMN, build_column
from openflowsheet.models.syn001.cascade import BOTTOM, TOP
from openflowsheet.models.syn001.column import CONDENSER, MODEL_ID, REBOILER, ColumnSpec
from openflowsheet.units import dimension_of

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


@contextmanager
def column_registered(
    monkeypatch: pytest.MonkeyPatch, bases: frozenset[str] = frozenset({"syn001"})
) -> Iterator[None]:
    """The column in `MODEL_BUILDERS`, `MODEL_SIGNATURES` and `MODEL_BASES` for one test."""
    monkeypatch.setitem(revision_binding.MODEL_BUILDERS, MODEL_ID, build_column)
    monkeypatch.setitem(revision_binding.MODEL_SIGNATURES, MODEL_ID, _COLUMN)
    monkeypatch.setitem(revision_binding.MODEL_BASES, MODEL_ID, bases)
    yield
