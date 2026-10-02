"""Shared support for T08 W2's kinetic-CSTR tests: the reference YAML, the revisions, the states.

Not collected as tests. The expected values are `benchmarks/t08/build_first_reference.yaml`'s
(the design lane's 40-digit generator, `docs/derivations/scripts/t08_build_first_reference.py`),
never this code's output.

**The revisions carry all three SYN-001 components** (build-first spec Amendment 1 §Am1.1,
R-126): PTC-R1 binds on `(A, B, C)`, with `C` an inert trace of `2⁻¹⁰` mol/s taken from A's feed
(`ν_C = 0`), so the feed is `(0.4990234375, 0.5, 0.0009765625)` mol/s and `n_tot = 1`. Every
state below carries `S1.n.C = S2.n.C = 2⁻¹⁰`; the YAML lists the `C` entries itself.

**No run of either method from a registered PTC-R1 start** (§A4.6). Evaluations at the three
roots and single steps at the three off-grid states of §A5 are the only calls made at PTC-R1's
parameters; the region solves here are of other flowsheets (a dormant feed, the liquid variant).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any

from conftest import REPO_ROOT, load_yaml

REFERENCE: dict[str, Any] = load_yaml(
    REPO_ROOT / "benchmarks" / "t08" / "build_first_reference.yaml"
)
REALIZATION: dict[str, Any] = REFERENCE["case"]["realization"]
ROOTS: dict[str, dict[str, Any]] = REFERENCE["closed_form"]["steady_states"]
MODEL: dict[str, Any] = REFERENCE["model"]
SINGLE_STEPS: list[dict[str, Any]] = REFERENCE["closed_form"]["single_steps"]
UNITS: dict[str, Any] = json.loads((REPO_ROOT / "schemas" / "units.json").read_text())

Document = dict[str, Any]

UNIT, FEED, SINK = "U-CSTR", "U-FEED", "U-SINK"
INLET, OUTLET = "S1", "S2"
COMPONENTS = ("A", "B", "C")

#: The realization's scalars, binary64 of the YAML's decimal strings.
T_F = float(REALIZATION["feed_T_K"])
P_F = float(REALIZATION["feed_P_Pa"])
T_SCALE = float(REALIZATION["T_scale_K"])
CAPACITY = float(REALIZATION["coolant_flow_mol_s"]) * float(REALIZATION["coolant_cp_J_molK"])
KEY_FEED = float(REALIZATION["feed_B_mol_s"])
#: The realization's feed `(A, B, C)` and its inert `C` trace, `2⁻¹⁰` mol/s (§Am1.1).
FEED_N: tuple[float, float, float] = (
    float(REALIZATION["feed_A_mol_s"]),
    float(REALIZATION["feed_B_mol_s"]),
    float(REALIZATION["feed_C_mol_s"]),
)
TRACE = FEED_N[2]


def f(value: str) -> float:
    """A YAML decimal string as the nearest binary64."""
    return float(value)


def _quantity(value: float, kind: str, meaning: str) -> Document:
    entry = UNITS["kinds"][kind]
    return {
        "value": value,
        "unit": entry["si_unit"],
        "dimension": list(entry["dimension"]),
        "kind": kind,
        "meaning": meaning,
        "role": "fixed",
    }


def cstr_parameters(**overrides: float) -> dict[str, float]:
    """The realization's parameters by revision name (`damkohler.B` names the key), overridable."""
    values = {
        "nu.A": f(REALIZATION["nu_A"]),
        "nu.B": f(REALIZATION["nu_B"]),
        "nu.C": 0.0,
        "damkohler.B": f(REALIZATION["damkohler"]),
        "T_ref": f(REALIZATION["T_ref_K"]),
        "T_scale": T_SCALE,
        "coolant_flow": f(REALIZATION["coolant_flow_mol_s"]),
        "coolant_cp": f(REALIZATION["coolant_cp_J_molK"]),
        "T_coolant": f(REALIZATION["T_coolant_K"]),
        "pressure_drop": f(REALIZATION["pressure_drop_Pa"]),
    }
    values.update(overrides)
    return values


_KINDS = {
    "nu": "dimensionless",
    "damkohler": "dimensionless",
    "T_ref": "temperature",
    "T_scale": "temperature_difference",
    "coolant_flow": "molar_flow",
    "coolant_cp": "molar_heat_capacity",
    "T_coolant": "temperature",
    "pressure_drop": "pressure",
}


def _connection(
    identifier: str, source: tuple[str, str], target: tuple[str, str], phase: str
) -> Document:
    return {
        "id": identifier,
        "kind": "material",
        "from": {"instance": source[0], "port": source[1]},
        "to": {"instance": target[0], "port": target[1]},
        "state_definition": "nTP-v1",
        "component_mapping": "revision_component_set",
        "phase_capability": phase,
        "notes": "T08 W2 test fixture.",
    }


def _stream_pin(
    identifier: str, stream: str, path: str, value: float, component: str | None
) -> Document:
    kind = {"state.n": "molar_flow", "state.T": "temperature", "state.P": "pressure"}[path]
    target: Document = {"object_type": "connection", "object_id": stream, "path": path}
    if component is not None:
        target["component"] = component
    return {
        "id": identifier,
        "target": target,
        "kind": kind,
        "unit": UNITS["kinds"][kind]["si_unit"],
        "value": value,
        "tolerance": {"absolute": 1e-09, "relative": 1e-08, "scale": 3.0},
        "role": "fixed",
        "provenance": "docs/derivations/T08-build-first-spec.md §A1.5",
        "notes": "T08 W2 test fixture.",
    }


def cstr_revision(
    name: str,
    *,
    feed: tuple[float, float, float] = FEED_N,
    temperature: float = T_F,
    pressure: float = P_F,
    phase: str = "vapor",
    parameters: Mapping[str, float] | None = None,
) -> Document:
    """feed → `U-CSTR` → sink, schema-valid, over `(A, B, C)`: the realization of §A1.5 as
    amended (§Am1.1, the `C` trace) by default, every field overridable."""
    template = load_yaml(REPO_ROOT / "benchmarks" / "t05" / "cases" / "SYN-001-UL-C2.yaml")
    feed_instance, sink_instance = (
        next(i for i in template["instances"] if i["id"] == identifier)
        for identifier in ("U-FEED", "U-PROD")
    )
    values = dict(parameters if parameters is not None else cstr_parameters())
    unit: Document = {
        "id": UNIT,
        "model": {"id": "syn001.kinetic_cstr", "version": "0.0.0-declared", "artifact_ref": None},
        "semantic_role": "reactor",
        "parameters": {
            key: _quantity(value, _KINDS[key.split(".")[0]], f"T08 W2 fixture: {key}")
            for key, value in values.items()
        },
        "policy": {
            "fidelity": "synthetic first-order kinetics (T08 build-first §A1)",
            "validity": "SYN-001 declared domain 280-440 K, 50000-200000 Pa",
        },
    }
    pins = [
        _stream_pin(f"SPEC-feed-n-{c}", INLET, "state.n", value, c)
        for c, value in zip(COMPONENTS, feed, strict=True)
    ]
    pins.append(_stream_pin("SPEC-feed-T", INLET, "state.T", temperature, None))
    pins.append(_stream_pin("SPEC-feed-P", INLET, "state.P", pressure, None))
    document = copy.deepcopy(template)
    document.update(
        revision_id=f"T08-W2-{name}",
        title=f"T08 W2 test fixture: {name}",
        description="feed -> syn001.kinetic_cstr -> sink (T08 build-first §A1.5).",
        instances=[
            dict(copy.deepcopy(feed_instance), id=FEED),
            unit,
            dict(copy.deepcopy(sink_instance), id=SINK),
        ],
        connections=[
            _connection(INLET, (FEED, "outlet"), (UNIT, "inlet"), phase),
            _connection(OUTLET, (UNIT, "outlet"), (SINK, "inlet"), phase),
        ],
        specifications=pins,
    )
    return document


def ptc_r1_revision() -> Document:
    """§A1.5's realization as amended (§Am1.1), as a revision."""
    return cstr_revision("PTC-R1-realization")


def liquid_variant_revision() -> Document:
    """§A5's liquid variant: feed, `T_ref` and `T_c` at 300 K, the outlet liquid, at `P_r`."""
    return cstr_revision(
        "liquid-variant",
        temperature=300.0,
        phase="liquid",
        parameters=cstr_parameters(T_ref=300.0, T_coolant=300.0),
    )


def dormant_revision(coolant_flow: float = 0.3) -> Document:
    """The realization with a dormant feed (B16)."""
    return cstr_revision(
        f"dormant-coolant-{coolant_flow}",
        feed=(0.0, 0.0, 0.0),
        parameters=cstr_parameters(coolant_flow=coolant_flow),
    )


def state_at(n_a: float, n_b: float, temperature: float) -> dict[str, float]:
    """A full state of the realization at outlet `(n_A, n_B, T)`: the feed at its pins, `C` at its
    trace in and out, `P = P_F` and `Q` from `CSTR-cooling` (a consistent start, as the YAML's
    steps are)."""
    return {
        f"{INLET}.n.A": FEED_N[0],
        f"{INLET}.n.B": FEED_N[1],
        f"{INLET}.n.C": TRACE,
        f"{INLET}.T": T_F,
        f"{INLET}.P": P_F,
        f"{OUTLET}.n.A": n_a,
        f"{OUTLET}.n.B": n_b,
        f"{OUTLET}.n.C": TRACE,
        f"{OUTLET}.T": temperature,
        f"{OUTLET}.P": P_F,
        f"{UNIT}.Q": CAPACITY * (T_F - temperature),
    }


def root_state(name: str) -> dict[str, float]:
    """A registered root (LOW, MID, HIGH) as binary64 of the YAML's dimensional values."""
    root = ROOTS[name]
    assert f(root["n_C_mol_s"]) == TRACE
    state = state_at(f(root["n_A_mol_s"]), f(root["n_B_mol_s"]), f(root["T_K"]))
    state[f"{UNIT}.Q"] = f(root["Q_W"])
    return state


def off_grid_state(x1: float, x2: float) -> dict[str, float]:
    """§A1.5's map as amended at a dimensionless state: `n_B = 0.5 (1 − x₁)`,
    `n_A = 1 − 2⁻¹⁰ − n_B` (`1 − 2⁻¹⁰` is exact), `n_C = 2⁻¹⁰`, `T = 360 + 3.125 x₂`."""
    n_b = KEY_FEED * (1.0 - x1)
    return state_at((1.0 - TRACE) - n_b, n_b, T_F + T_SCALE * x2)


#: The YAML's column names → the revision's column ids.
COLUMN = {
    "n_A": f"{OUTLET}.n.A",
    "n_B": f"{OUTLET}.n.B",
    "n_C": f"{OUTLET}.n.C",
    "T": f"{OUTLET}.T",
    "P": f"{OUTLET}.P",
    "Q": f"{UNIT}.Q",
}


def row(label: str) -> str:
    """A YAML row label (`CSTR-mole:A`, `CSTR-duty`) as the unit's row id."""
    return f"{UNIT}:{label}"
