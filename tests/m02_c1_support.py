"""Test support for M02's C1 revisions (design note §8, §8.1): minimal `ProcessRevision` documents
on `pr-c1-v1`, built in code so that each test states the one thing it varies.

Not a fixture of record: `C1-LOOP-M02-v1`'s registered documents are `benchmarks/m02/`'s.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from openflowsheet.thermo.pr_c1 import COMPONENTS, RECORDS_PATH

DIMENSIONLESS = [0, 0, 0, 0, 0, 0, 0]
PRESSURE = [-1, 1, -2, 0, 0, 0, 0]

#: Model id -> its `semantic_role` (the schema's enum).
ROLES = {
    "c1.feed_source": "feed",
    "c1.product_sink": "product_sink",
    "c1.adiabatic_mixer": "mixer",
    "c1.tp_heater": "heater",
    "c1.tp_flash": "flash",
    "c1.stream_splitter": "splitter",
    "c1.reactor": "reactor",
    "c1.reactor_standin": "reactor",
}

#: `kind` -> a specification's `tolerance` (ADR 0001 D6's registered values, as SYN-001's cases).
_TOLERANCE: dict[str, dict[str, float]] = {
    "molar_flow": {"absolute": 1.0e-9, "relative": 1.0e-8, "scale": 3.0},
    "mass_flow": {"absolute": 1.0e-9, "relative": 1.0e-8, "scale": 3.0},
    "temperature": {"absolute": 1.0e-6},
    "pressure": {"absolute": 0.01},
    "heat_rate": {"absolute": 1.0e-5, "relative": 1.0e-8, "scale": 1.0e5},
}

#: `kind` -> its SI unit, for the specifications these documents write.
_SI = {
    "molar_flow": "mol/s",
    "temperature": "K",
    "pressure": "Pa",
    "mass_flow": "kg/s",
    "heat_rate": "W",
}


def instance(
    unit: str,
    model: str,
    parameters: Mapping[str, Any] | None = None,
    *,
    version: str = "0.0.0-declared",
    artifact_ref: str | None = None,
) -> dict[str, Any]:
    return {
        "id": unit,
        "model": {"id": model, "version": version, "artifact_ref": artifact_ref},
        "semantic_role": ROLES[model],
        "parameters": dict(parameters or {}),
        "policy": {"fidelity": "test", "validity": "test"},
    }


def quantity(value: float, unit: str, kind: str, dimension: Sequence[int]) -> dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "dimension": list(dimension),
        "kind": kind,
        "meaning": "test",
        "role": "fixed",
    }


def connection(
    stream: str, source: tuple[str, str], target: tuple[str, str], phase: str = "vapor"
) -> dict[str, Any]:
    return {
        "id": stream,
        "kind": "material",
        "from": {"instance": source[0], "port": source[1]},
        "to": {"instance": target[0], "port": target[1]},
        "state_definition": "nTP-v1",
        "component_mapping": "revision_component_set",
        "phase_capability": phase,
        "notes": "test",
    }


def specification(
    name: str,
    object_type: str,
    object_id: str,
    path: str,
    value: float,
    kind: str,
    *,
    component: str | None = None,
    unit: str | None = None,
) -> dict[str, Any]:
    target: dict[str, Any] = {"object_type": object_type, "object_id": object_id, "path": path}
    if component is not None:
        target["component"] = component
    return {
        "id": name,
        "target": target,
        "kind": kind,
        "unit": unit or _SI[kind],
        "value": value,
        "tolerance": dict(_TOLERANCE[kind]),
        "role": "fixed",
        "provenance": "M02 test",
    }


def feed_specifications(
    stream: str, flows: Sequence[float], temperature: float, pressure: float
) -> list[dict[str, Any]]:
    """A stream's full nTP-v1 state, in `COMPONENTS` order."""
    return [
        *(
            specification(
                f"SPEC-{stream}-n-{c}",
                "connection",
                stream,
                "state.n",
                v,
                "molar_flow",
                component=c,
            )
            for c, v in zip(COMPONENTS, flows, strict=True)
        ),
        specification(
            f"SPEC-{stream}-T", "connection", stream, "state.T", temperature, "temperature"
        ),
        specification(f"SPEC-{stream}-P", "connection", stream, "state.P", pressure, "pressure"),
    ]


def revision(
    instances: Sequence[Mapping[str, Any]],
    connections: Sequence[Mapping[str, Any]],
    specifications: Sequence[Mapping[str, Any]],
    *,
    components: Sequence[str] = COMPONENTS,
    record_source: str = RECORDS_PATH,
    revision_id: str = "C1-TEST-r1",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "revision_id": revision_id,
        "parent_revision": None,
        "title": revision_id,
        "description": "M02 test revision on pr-c1-v1",
        "component_set": {"record_source": record_source, "components": list(components)},
        "instances": [dict(entry) for entry in instances],
        "connections": [dict(entry) for entry in connections],
        "specifications": [dict(entry) for entry in specifications],
        "provenance": {
            "actor": "M02 tests (build lane)",
            "operation": "create",
            "timestamp": "2026-10-08T00:00:00Z",
            "source_references": ["docs/design/M02-pymrm-adapter.md §8"],
            "notes": "built in code by tests/m02_c1_support.py",
        },
    }
