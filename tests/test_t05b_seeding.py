"""T05b W6, ADR 0012 D5 (spec §6.4): the traversal start seeds a PH-type split from its closure.

`initial_state` sets a heater-style lifted split whose unit closed its outlet by the PH kernel from
the kernel's split (carried on `UnitEvaluation.closure`), not from a TP re-flash of the outlet. On
the kernel's bracket route the two are the same function of the same inputs, so every registered
start is bitwise unchanged (B07's premise, asserted here per split); on the saturation and band
routes the re-flash lost the vapour fraction. `traversal_start` also names the units whose closure
took the band route (ADR 0012 D10 F1). Independent of the phase-contract literal: no policy here.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml
from t05_w12_support import bind
from t05b_support import NEAR_PURE_CASES, REF, near_pure, number, sc1, sc3

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.models.revision_flowsheet import RevisionFlowsheet
from openflowsheet.models.syn001.tp_state import tp_state
from openflowsheet.orchestrator.revision import (
    InitialStateFailure,
    TraversalStart,
    initial_state,
    instances_of,
    traversal_start,
)
from openflowsheet.orchestrator.splits import SPLIT_RULES, lifted_splits
from openflowsheet.thermo import StreamState

CASE_DIR = Path(__file__).resolve().parents[1] / "benchmarks" / "t05" / "cases"
COUPLED = ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3", "SYN-001-UL-C3X")


def _bits(value: float) -> bytes:
    return struct.pack("<d", value)


def _coupled(case: str) -> RevisionBinding:
    binding = bind_revision_flowsheet(yaml.safe_load((CASE_DIR / f"{case}.yaml").read_text()))
    assert isinstance(binding, RevisionBinding), binding
    return binding


def _start(binding: RevisionBinding) -> TraversalStart | InitialStateFailure:
    return traversal_start(binding.flowsheet, binding.spec.variable_ids)


def _reflash(flowsheet: RevisionFlowsheet, values: Mapping[str, float]) -> dict[str, float]:
    """What T05's `initial_state` wrote for every heater-style split: the TP flash of the outlet's
    `(n, T, P)` as the start carries it."""
    found: dict[str, float] = {}
    instances = instances_of(flowsheet)
    for split in lifted_splits(instances, flowsheet.components):
        model = next(model for unit, model, _ in instances if unit == split.unit)
        if SPLIT_RULES[model].style != "outlet":
            continue
        stream = StreamState(
            n=tuple(values[name] for name in split.feed),
            temperature=values[split.temperature],
            pressure=values[split.pressure],
        )
        flashed = tp_state(flowsheet.provider, stream, flowsheet.context)
        assert flashed.status == "ok" and flashed.vapor and flashed.liquid, flashed
        found.update(zip(split.vapor, flashed.vapor.n, strict=True))
        found.update(zip(split.liquid, flashed.liquid.n, strict=True))
        found[split.vapor_total] = sum(flashed.vapor.n)
        found[split.liquid_total] = sum(flashed.liquid.n)
    return found


@pytest.mark.parametrize("case", COUPLED)
def test_d5_the_registered_starts_are_bitwise_the_re_flash(case: str) -> None:
    """B07's premise: on C1–C3 every PH closure answered by the bracket route, where its split is
    the provider's TP flash at `(n, T*, P)`, so the seeded start is T05's bit for bit. C3X's
    traversal refuses (T05 A20) before any split is set, as before."""
    binding = _coupled(case)
    start = _start(binding)
    if case == "SYN-001-UL-C3X":
        assert isinstance(start, InitialStateFailure)
        assert start.message == "initializer_failed(U-HX): temperature_cross(cold_end)"
        return
    assert isinstance(start, TraversalStart), start
    assert start.band_routes == ()
    expected = _reflash(binding.flowsheet, start.values)
    # C1's valve and heater, C2's outlet-temperature reactor; C3's only split is a PH flash's
    # products, already the closure's.
    assert bool(expected) == (case != "SYN-001-UL-C3"), case
    for name, value in expected.items():
        assert _bits(start.values[name]) == _bits(value), (case, name)
    # The traversal's closures: bracket routes only (W0.1's baseline: 26 bracket, 1 saturation
    # — PHF-6, a unit case — and 3 refusals; none in a coupled case is a band route).
    traversed = binding.flowsheet.traverse({})
    routes = {
        unit: evaluation.closure.route
        for unit, evaluation in traversed.evaluations.items()
        if evaluation.closure is not None
    }
    assert set(routes.values()) <= {"bracket"}, routes


def test_d5_sc1_starts_on_the_lever_rule_split() -> None:
    """The saturation route: the valve's outlet at `T_sat` carries `β = 2 016/60 000`, which the
    re-flash would have written as all liquid (`ln K_B(360 K) = 0`: the flash calls it liquid)."""
    binding = bind(sc1())
    start = _start(binding)
    assert isinstance(start, TraversalStart), start
    assert start.band_routes == ()
    root: Any = REF["single_component_cases"]["SC-1"]["root"]["S2"]
    assert start.values["S2.T"] == number(root["T_K"])
    for index, component in enumerate(("A", "B", "C")):
        assert abs(
            start.values[f"S2.vap.{component}"] - number(root["vapor_mol_per_s"][index])
        ) <= (1e-15)
        assert abs(
            start.values[f"S2.liq.{component}"] - number(root["liquid_mol_per_s"][index])
        ) <= (1e-15)
    reflashed = _reflash(binding.flowsheet, start.values)
    assert reflashed["S2.V"] == 0.0
    assert start.values["S2.V"] > 0.0


def test_d5_sc3_seeds_the_valve_and_leaves_the_flash_products() -> None:
    """A products-style split is its product streams, already the closure's: SC-3's PH flash
    reads `S2` by `(n, T, P)` as liquid and opens all liquid at 355 K (spec §12.3)."""
    binding = bind(sc3())
    start = _start(binding)
    assert isinstance(start, TraversalStart), start
    assert start.values["S2.V"] > 0.0
    assert start.values["S3.N"] == 0.0
    assert start.values["S4.N"] == 2.0
    entry = REF["single_component_cases"]["SC-3"]["start"]
    assert abs(start.values["S3.T"] - number(entry["U-PHF_T_K"])) <= 1e-6


@pytest.mark.parametrize("case", NEAR_PURE_CASES)
def test_d10_f1_the_traversal_names_its_band_routes(case: str) -> None:
    """`closure_route(<unit>, band)`'s source: the units whose traversal closure took the band
    route. The twin's 53-bit emulation names NP-1 and NP-2 band, NP-3 and NP-G bracket."""
    start = _start(bind(near_pure(case)))
    assert isinstance(start, TraversalStart), start
    emulated = REF["near_pure_cases"][case]["measured_53_bit_traversal_route"]
    assert start.band_routes == (("U-PHF",) if emulated == "band" else ())


def test_initial_state_is_the_values_of_the_traversal_start() -> None:
    binding = bind(sc1())
    start = _start(binding)
    assert isinstance(start, TraversalStart)
    assert initial_state(binding.flowsheet, binding.spec.variable_ids) == start.values
