"""S08 WO-2 — sources, candidates and the block endpoint: S08 design note §5.2, §5.3, §7 A01–A04.

Expectations are the design note's tables (§5.2's candidate lists, §6.2's closed forms for P1's
and P2's all-one-phase endpoints), S02 §18.2's `x⁰` (A03: the builder at all-2P), the target's
own rows at the endpoint (A02) and the refusal codes of §5.3 (A04). §6.2's P2, P3, F1 and D1 are
inline until WO-G registers them; WO-4 wires in their 50-digit roots. Each test names the
assertion of §7 it closes.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

import pytest
from test_s02_column_wo1 import FEED, PROVIDER, REFERENCE, SPECS, UNIT, _variant
from test_s02_column_wo2 import T_ABS
from test_s06_column_wo1 import J_CASES, U_SETS

import openflowsheet.models.syn001.cascade_solve as cascade_solve_module
import openflowsheet.models.syn001.column_blocks as blocks_module
from openflowsheet.compile.reference import row_values
from openflowsheet.models.syn001 import ENERGY_TOLERANCE
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    InletState,
    SideFeed,
    liquid_id,
    liquid_total_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT
from openflowsheet.models.syn001.column import ColumnSpec, EndSpecification, profile_initial
from openflowsheet.models.syn001.column_blocks import (
    BLOCK_ENDPOINT_ID,
    BlockEndpoint,
    block_endpoint,
    block_signature,
    candidates,
    sources,
)
from openflowsheet.models.syn001.column_solve import (
    BubblePointEndpoint,
    bubble_point_endpoint,
    compile_column,
    lifted_splits,
    slots,
)
from openflowsheet.models.syn001.saturation_band import BandTemperature
from openflowsheet.orchestrator.region import KIND_TOLERANCE
from openflowsheet.orchestrator.roots import branch_found
from openflowsheet.thermo.syn001 import C_P

# -- §6.2's new cases, inline (WO-G registers them) ----------------------------------------------

#: P2: M4 with the condenser under `duty` −3000 W and the bottom inlet `VAPOR` FEED at 420 K.
P2 = replace(
    SPECS["M4"],
    condenser_spec=EndSpecification("duty", -3000.0),
    bottom=InletState(FEED, 420.0, 1.04e5, "VAPOR"),
)
#: P3: partial condenser `distillate_rate` 0.5, partial reboiler `duty` 1000 W, a vapour feed at
#: stage 3 and a cold liquid feed at stage 4.
P3 = replace(
    SPECS["M4"],
    bottom=None,
    reboiler="partial",
    reboiler_spec=EndSpecification("duty", 1000.0),
    duties=(None, 0.0, 0.0, 0.0, None),
    sides=(
        SideFeed("feed", 3, InletState(FEED, 385.0, 1.02e5, "VAPOR")),
        SideFeed("cold", 4, InletState((0.15, 0.2, 0.15), 300.0, 1.03e5, "LIQUID")),
    ),
)
#: F1: M4 with no bottom vapour, a cold liquid bottom inlet and a vapour side feed at stage 3.
F1 = replace(
    SPECS["M4"],
    sides=(SideFeed("feed", 3, InletState(FEED, 385.0, 1.02e5, "VAPOR")),),
    bottom=InletState((0.03, 0.04, 0.03), 330.0, 1.04e5, "LIQUID"),
)
#: D1: M3 with a small vapour top inlet, the liquid FEED at stage 3 and the reboiler at 30 kW.
D1 = replace(
    SPECS["M3"],
    sides=(SideFeed("feed", 3, InletState(FEED, 340.0, 1.02e5, "LIQUID")),),
    top=InletState((0.03, 0.04, 0.03), 400.0, 1.0e5, "VAPOR"),
)
USE_CASES: dict[str, ColumnSpec] = {"P1": SPECS["P1"], "P2": P2, "P3": P3, "F1": F1, "D1": D1}

#: §5.2's expected candidate lists (A01).
EXPECTED_CANDIDATES: dict[str, tuple[ColumnSpec, tuple[tuple[int, int], ...]]] = {
    "P1": (SPECS["P1"], ((0, 5),)),
    "P2": (P2, ((5, 0),)),
    "P3": (P3, ((0, 2),)),
    "F1": (F1, ((0, 2),)),
    "D1": (D1, ((2, 0),)),
    "M3": (SPECS["M3"], ((0, 5),)),
    "V-M1.duty+duty": (_variant("M1", "duty+duty"), ((3, 0),)),
    "M1": (SPECS["M1"], ()),
    "M2": (SPECS["M2"], ()),
    "M4": (SPECS["M4"], ()),
    "J5": (J_CASES["J5"], ()),
    "U1": (U_SETS["U1"], ()),
    "U2": (U_SETS["U2"], ()),
}


def _initial(spec: ColumnSpec) -> Any:
    initial = profile_initial(spec, PROVIDER, DECLARATION_CONTEXT)
    assert not isinstance(initial, CascadeFailure), initial
    return initial


_BUILT: dict[str, BlockEndpoint] = {}


def built(case: str) -> BlockEndpoint:
    """§5.3 on `case`'s only candidate, once per session."""
    if case not in _BUILT:
        spec = USE_CASES[case]
        (candidate,) = candidates(spec)
        found = block_endpoint(spec, PROVIDER, _initial(spec), candidate)
        assert isinstance(found, BlockEndpoint), found
        _BUILT[case] = found
    return _BUILT[case]


def _no_region_solve(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("A04: solve_region was called")

    monkeypatch.setattr(cascade_solve_module, "solve_region", refuse)


def _refused(found: BlockEndpoint | CascadeFailure, reason: str) -> None:
    assert isinstance(found, CascadeFailure), found
    assert found.outcome == "INITIALIZATION_FAILED"
    assert found.cause == f"initialization_failed({BLOCK_ENDPOINT_ID}, {reason})", found


# -- A01: candidate lists ------------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(EXPECTED_CANDIDATES))
def test_a01_candidate_lists(case: str) -> None:
    """A01: §5.2's candidate list of each tabled specification, exactly and in order; a second
    call gives the same tuple (determinism, §2 item 8)."""
    spec, expected = EXPECTED_CANDIDATES[case]
    assert candidates(spec) == expected
    assert candidates(spec) == expected


@pytest.mark.parametrize("case", ["U1", "U2"])
def test_a01_u_sets_fix_stages_2_and_7(case: str) -> None:
    """A01: U1's and U2's fixed stages are {2, 7}, which no block pair keeps in its core."""
    assert sources(U_SETS[case]).fixed == (2, 7)


def test_a01_sources_of_p3() -> None:
    """§5.2's sets on P3: the partial condenser and the cold feed are liquid sources, the vapour
    feed and the partial reboiler (under `duty`) vapour sources; only stage 1 is fixed."""
    found = sources(P3)
    assert found.liquid == ((1, "end"), (4, "inlet"))
    assert found.vapor == ((5, "end"), (3, "inlet"))
    assert found.fixed == (1,)


def test_a01_signature() -> None:
    """`σ(a, c) = V^a 2P^b L^c` over the equilibrium stages."""
    assert block_signature(D1, (2, 0)) == ("VAPOR", "VAPOR", "TWO_PHASE", "TWO_PHASE", "TWO_PHASE")
    assert block_signature(P3, (0, 2)) == ("TWO_PHASE",) * 3 + ("LIQUID",) * 2
    assert block_signature(SPECS["M2"], (0, 0)) == ("TWO_PHASE",) * 6
    with pytest.raises(ValueError, match="block pair"):
        block_signature(P3, (3, 3))


# -- A02: the identity at every built endpoint ---------------------------------------------------


@pytest.mark.parametrize("case", sorted(USE_CASES))
def test_a02_the_block_endpoint_identity(case: str) -> None:
    """A02: at the built endpoint every target row except the continued slots holds within its
    kind tolerance; each block stage's duty slot row within `ENERGY_TOLERANCE`; the pinned flows
    are exactly `+0.0`, sign bit included; the branch found is `σ(a, c)`."""
    spec = USE_CASES[case]
    (candidate,) = candidates(spec)
    found = built(case)
    signature = block_signature(spec, candidate)
    assert found.signature == signature
    stages = spec.equilibrium_stages()
    regimes = dict(zip(stages, signature, strict=True))
    target = compile_column(spec, PROVIDER).spec
    replaced = [s for s in slots(spec, _initial(spec).profile) if s.parameter]
    continued = {s.target_row for s in replaced}
    values = row_values(target, found.state)
    assert continued <= set(values)
    over = {
        row: abs(value) / KIND_TOLERANCE[target.row_kinds[row]]
        for row, value in values.items()
        if row not in continued
    }
    assert max(over.values()) <= 1.0, max(over.items(), key=lambda item: item[1])
    block_duties = [s for s in replaced if s.continued == "Q" and regimes[s.stage] != "TWO_PHASE"]
    assert block_duties, "every block stage of §6.2's cases carries a duty slot"
    for s in block_duties:
        assert abs(values[s.target_row]) <= ENERGY_TOLERANCE, (s.stage, values[s.target_row])
    for j, regime in regimes.items():
        if regime == "TWO_PHASE":
            continue
        pinned = vapor_id if regime == "LIQUID" else liquid_id
        total = vapor_total_id if regime == "LIQUID" else liquid_total_id
        for name in (*(pinned(UNIT, j, c) for c in spec.components), total(UNIT, j)):
            assert found.state[name] == 0.0 and math.copysign(1.0, found.state[name]) == 1.0, name
    assert branch_found(lifted_splits(spec), found.state) == [
        (f"{UNIT}.stage.{j}", regimes[j]) for j in stages
    ]


def test_a02_p1_endpoint_is_the_closed_form() -> None:
    """P1's L×5 endpoint is `ref.phase_case.P1`'s closed form (S02 §9): `T` and `l` within S02's
    state tolerance, and the distillate `v_1` exactly `+0.0`."""
    record = REFERENCE["phase_case"]["P1"]
    state = built("P1").state
    for j, expected in enumerate(record["T"], start=1):
        assert abs(state[stage_temperature_id(UNIT, j)] - float(expected)) <= T_ABS, j
        for c, flow in zip(SPECS["P1"].components, record["l"], strict=True):
            assert abs(state[liquid_id(UNIT, j, c)] - float(flow)) <= 1e-12, (j, c)
    for c in SPECS["P1"].components:
        assert math.copysign(1.0, state[vapor_id(UNIT, 1, c)]) == 1.0
        assert state[vapor_id(UNIT, 1, c)] == 0.0


def test_a02_p2_endpoint_is_the_closed_form() -> None:
    """P2's V×5 endpoint is §6.2's closed form: `v_j` the bottom inlet's flows, `T_j = 420 K` for
    `j ≥ 2`, `T_1 = 420 + Q_c*/(F C_P) = 390 K`; bottoms exactly `+0.0`."""
    state = built("P2").state
    for j in range(1, 6):
        for c, flow in zip(P2.components, FEED, strict=True):
            assert state[vapor_id(UNIT, j, c)] == flow, (j, c)
            assert state[liquid_id(UNIT, j, c)] == 0.0
            assert math.copysign(1.0, state[liquid_id(UNIT, j, c)]) == 1.0
    expected = [420.0 + (-3000.0) / (sum(FEED) * C_P)] + [420.0] * 4
    assert expected[0] == pytest.approx(390.0, abs=1e-9)
    for j, temperature in enumerate(expected, start=1):
        assert abs(state[stage_temperature_id(UNIT, j)] - temperature) <= T_ABS, j


# -- A03: the builder at all-2P is §18.2 ----------------------------------------------------------


@pytest.mark.parametrize("case", ["M1", "M2", "M3", "M4"])
def test_a03_the_builder_at_all_2p_is_the_bubble_point_endpoint(case: str) -> None:
    """A03: the builder at `(0, 0)` equals §18.2's `x⁰` on M1–M4 (rel 1e-12, every column), with
    the same `ρ`, `φ` and sweep count. This tests the builder only; Stage A never calls it."""
    spec = SPECS[case]
    initial = _initial(spec)
    reference = bubble_point_endpoint(spec, PROVIDER, initial)
    assert isinstance(reference, BubblePointEndpoint), reference
    found = block_endpoint(spec, PROVIDER, initial, (0, 0))
    assert isinstance(found, BlockEndpoint), found
    assert list(found.state) == list(reference.state)
    for name, value in reference.state.items():
        assert abs(found.state[name] - value) <= 1e-12 * abs(value), name
    assert dict(found.rho) == dict(reference.rho)
    assert found.phi == reference.phi
    assert (found.sweeps, found.last_delta) == (reference.sweeps, reference.last_delta)


# -- A04: refusals, with no region solve ---------------------------------------------------------


def test_a04_a_bubble_point_outside_the_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    """A04: `band_temperature` answering `below` at a core stage (the second call: stage 2 of
    sweep 1) refuses P3's `(0, 2)` with `bubble_point_outside_domain`, before any region solve."""
    _no_region_solve(monkeypatch)
    real = blocks_module.band_temperature
    calls: list[float] = []

    def below_once(provider: Any, flows: Any, pressure: float, *rest: Any, **kw: Any) -> Any:
        calls.append(pressure)
        if len(calls) == 2:
            return BandTemperature("below", evaluations=1)
        return real(provider, flows, pressure, *rest, **kw)

    monkeypatch.setattr(blocks_module, "band_temperature", below_once)
    _refused(block_endpoint(P3, PROVIDER, _initial(P3), (0, 2)), "bubble_point_outside_domain")
    assert calls == [P3.pressures[0], P3.pressures[1]]


def test_a04_sweeps_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A04: `max_sweeps = 1` refuses P3's `(0, 2)` with `sweeps_exhausted`."""
    _no_region_solve(monkeypatch)
    _refused(block_endpoint(P3, PROVIDER, _initial(P3), (0, 2), max_sweeps=1), "sweeps_exhausted")


def test_a04_an_inadmissible_block_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    """A04: P1's `(0, 5)` at `Q_r* = 8 kW` heats stage 5's liquid to about 380 K, about 30 K
    above its bubble point: `inadmissible_endpoint(5)`."""
    _no_region_solve(monkeypatch)
    spec = replace(SPECS["P1"], reboiler_spec=EndSpecification("duty", 8000.0))
    found = block_endpoint(spec, PROVIDER, _initial(spec), (0, 5))
    _refused(found, "inadmissible_endpoint(5)")


def test_a04_no_energy_root_on_the_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    """§5.3 step 5: a duty that would take an L-block stage past the domain's upper end (P1's
    stage 5 at `Q_r* = 100 kW`, ≈ 3600 K) refuses with `block_energy_outside_domain`."""
    _no_region_solve(monkeypatch)
    spec = replace(SPECS["P1"], reboiler_spec=EndSpecification("duty", 1.0e5))
    found = block_endpoint(spec, PROVIDER, _initial(spec), (0, 5))
    _refused(found, "block_energy_outside_domain")
