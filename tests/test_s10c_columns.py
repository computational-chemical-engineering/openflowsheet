"""S10-C WO-4, gate G7: the registered columns C-MW and C-EW on `wilson-ig-v1` (design note
`docs/derivations/S10C-design.md` §4.9, §4.10; specification `docs/derivations/S10C-spec.md` §4,
§5.5, assertions S10C.A35, A40–A45), mutation M4 (`SWEEP_RELAXATION = 1`), and a constructed
Stage-B opening on a Wilson specification (exact zeros, mass balance; design §7 limitations).

The expectations are the 50-digit generator's roots (`benchmarks/s10c/reference_values.yaml`,
`columns.<case>`), with the per-variable tolerances the specification registers (F-2: 10× the
first-order acceptance image), plus A42's sharp check that every declared row vanishes at the
reference root to `1e-4 τ_kind`, independently of where Newton stopped.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from functools import cache
from typing import Any

import pytest
from test_s10c_blocks import CONTEXT, REAL, REFERENCE, UNIT, M1Block, column_spec

import openflowsheet.models.syn001.column as column_module
import openflowsheet.models.syn001.column_solve as column_solve
from openflowsheet.compile.reference import row_values
from openflowsheet.models.syn001 import ENERGY_TOLERANCE
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    InletState,
    SideFeed,
    declared_problem,
    liquid_id,
    liquid_total_id,
    stage_duty_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT, AcceptanceDefectError
from openflowsheet.models.syn001.column import (
    ColumnSpec,
    EndSpecification,
    _initial_state,
    declared_rows,
    distillate_id,
    distillate_total_id,
    profile_initial,
    reflux_fraction_id,
    reflux_id,
    validate,
)
from openflowsheet.models.syn001.column_blocks import (
    BlockEndpoint,
    block_endpoint,
    block_signature,
    candidates,
)
from openflowsheet.models.syn001.column_solve import (
    PRESOLVE_ID,
    TWO_PHASE_SATURATION_TOLERANCE,
    BubblePointEndpoint,
    ColumnSolution,
    acceptance_failures,
    bubble_point_endpoint,
    compile_column,
    lifted_splits,
    regimes_of,
    saturation_errors,
    slots,
    solve_column,
)
from openflowsheet.models.syn001.gamma_phi_blocks import GammaPhiLnKBlock, probe_flows
from openflowsheet.models.syn001.saturation_band import band_temperature
from openflowsheet.orchestrator.region import KIND_TOLERANCE
from openflowsheet.orchestrator.roots import branch_found
from openflowsheet.orchestrator.trace import Trace
from openflowsheet.thermo import StreamState

CASES = ("C-MW", "C-EW")
#: A42: every declared row at the reference root within `1e-4 τ_kind` (spec §5.5).
ROWS_AT_ROOT: float = 1e-4


def root(case: str) -> Mapping[str, Any]:
    found: Mapping[str, Any] = REFERENCE["columns"][case]["root"]
    return found


def light(spec: ColumnSpec) -> int:
    """The light component of the binary: the first flowing feed component (spec §4)."""
    (feed,) = spec.sides
    return next(i for i, a in enumerate(feed.state.n) if a > 0.0)


def absent(spec: ColumnSpec) -> int:
    """The component whose feed flow is exactly `+0.0` (spec §4: a binary on the ternary)."""
    (feed,) = spec.sides
    (index,) = (i for i, a in enumerate(feed.state.n) if a == 0.0)
    return index


@cache
def solved(case: str) -> tuple[ColumnSolution, tuple[float, ...]]:
    """`solve_column` on `case` once per session, and the residual norms of its Newton steps."""
    trace = Trace()
    found = solve_column(column_spec(case), REAL, trace=trace)
    assert isinstance(found, ColumnSolution), found
    return found, newton_residuals(trace)


def newton_residuals(trace: Trace) -> tuple[float, ...]:
    return tuple(e.residual_inf_unscaled for e in trace.events if e.kind == "step_accepted")


def observed_order(residuals: Sequence[float]) -> float:
    """The observed order over the last three accepted Newton steps (A43, recorded)."""
    a, b, c = residuals[-3:]
    return math.log(c / b) / math.log(b / a)


# -- A40, A45: converged, two-phase, accepted ------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_a40_a45_the_column_converges_and_is_accepted(case: str) -> None:
    """A45: the feed is admitted; A40: `CONVERGED` in Stage A, signature TWO_PHASE on every
    equilibrium stage, S02 §8 and S08 §5.5 acceptance with item 6 (≤ 1e-4 K) re-checked here."""
    spec = column_spec(case)
    assert validate(spec, REAL, DECLARATION_CONTEXT) is None
    found, _ = solved(case)
    assert found.outcome == "CONVERGED", (found.outcome, found.cause)
    assert found.reentry is None
    assert isinstance(found.endpoint, BubblePointEndpoint)
    assert found.signature == ("TWO_PHASE",) * len(spec.equilibrium_stages())
    regimes = regimes_of(spec, found.result.attempts[-1].signature)
    target = compile_column(spec, REAL).spec
    assert acceptance_failures(spec, REAL, target, found.state, regimes) == ()
    errors = saturation_errors(spec, REAL, found.state, regimes)
    assert max(errors.values()) <= TWO_PHASE_SATURATION_TOLERANCE, errors


# -- A41: the returned state against the registered root -------------------------------------------


def deviations(case: str, state: Mapping[str, float]) -> dict[str, list[tuple[float, str]]]:
    """`|Δ|/tolerance` per variable class against `ref.columns.<case>.root` (A41, A43)."""
    spec = column_spec(case)
    ref = root(case)
    components = spec.components
    out: dict[str, list[tuple[float, str]]] = {}

    def add(kind: str, name: str, got: float, want: float, tolerance: float) -> None:
        out.setdefault(kind, []).append((abs(got - float(want)) / float(tolerance), name))

    for key, entry in ref["stages"].items():
        j, tol = int(key), entry["tolerance"]
        add(
            "T",
            stage_temperature_id(UNIT, j),
            state[stage_temperature_id(UNIT, j)],
            entry["T"],
            tol["T"],
        )
        for i, c in enumerate(components):
            add(
                "l",
                liquid_id(UNIT, j, c),
                state[liquid_id(UNIT, j, c)],
                entry["liquid_n"][i],
                tol["liquid_n"],
            )
            add(
                "v",
                vapor_id(UNIT, j, c),
                state[vapor_id(UNIT, j, c)],
                entry["vapor_n"][i],
                tol["vapor_n"],
            )
    condenser, reboiler = ref["condenser"], ref["reboiler"]
    ctol, rtol = condenser["tolerance"], reboiler["tolerance"]
    bottom = spec.stage_count
    k = light(spec)
    distillate = [state[distillate_id(UNIT, c)] for c in components]
    bottoms = [state[liquid_id(UNIT, bottom, c)] for c in components]
    add("T_c", "T_c", state[stage_temperature_id(UNIT, 1)], condenser["T"], ctol["T"])
    add("D", "D", state[distillate_total_id(UNIT)], condenser["D"], ctol["D"])
    add("x_D", "x_D", distillate[k] / sum(distillate), condenser["x_D"], ctol["x_D"])
    add("Q_c", "Q_c", state[stage_duty_id(UNIT, 1)], condenser["Q"], ctol["Q"])
    add("B", "B", state[liquid_total_id(UNIT, bottom)], reboiler["B"], rtol["B"])
    add("x_B", "x_B", bottoms[k] / sum(bottoms), reboiler["x_B"], rtol["x_B"])
    add("Q_r", "Q_r", state[stage_duty_id(UNIT, bottom)], reboiler["Q"], rtol["Q"])
    flows = ctol["reflux_n_and_distillate_n"]
    for i, c in enumerate(components):
        add("r", reflux_id(UNIT, c), state[reflux_id(UNIT, c)], condenser["reflux_n"][i], flows)
        add("d", distillate_id(UNIT, c), distillate[i], condenser["distillate_n"][i], flows)
    return out


def worst(found: Mapping[str, list[tuple[float, str]]]) -> tuple[float, str]:
    return max(item for items in found.values() for item in items)


@pytest.mark.parametrize("case", CASES)
def test_a41_the_state_is_the_registered_root(case: str, record_property: Any) -> None:
    """A41: every stage's T, liquid and vapour flows (the absent component's included, against
    that stage's flow tolerance); T_c, D, B, x_D, x_B, Q_c, Q_r, reflux and distillate flows;
    each within its registered tolerance. A43 (recorded): Newton iterations, the largest
    `|Δ|/tolerance` per class, absent flows exactly 0.0 or not, the observed order."""
    found, residuals = solved(case)
    measured = deviations(case, found.state)
    assert worst(measured)[0] <= 1.0, worst(measured)
    spec = column_spec(case)
    gone = spec.components[absent(spec)]
    zeros = [
        found.state[name]
        for j in spec.equilibrium_stages()
        for name in (liquid_id(UNIT, j, gone), vapor_id(UNIT, j, gone))
    ]
    record_property("newton_iterations", len(residuals))
    record_property("observed_order", observed_order(residuals))
    record_property("worst_by_class", {k: max(v) for k, v in measured.items()})
    record_property("absent_flows_exactly_zero", all(z == 0.0 for z in zeros))
    record_property("absent_flows_max", max(abs(z) for z in zeros))


# -- A42: every declared row at the reference root -------------------------------------------------


@cache
def reference_state(case: str) -> dict[str, float]:
    """The implementation's full column state at the YAML root (spec §5.5): flows, temperatures,
    `φ`, `D` and duties from `ref`; `m`, `L`, `V`, `r`, `d` from their definition rows in
    binary64 (`_initial_state`: `r = φ v_2`, `d = v_2 − r`, totals as sums, `m` by `mix`)."""
    spec = column_spec(case)
    ref = root(case)
    stages = ref["stages"]
    liquid = {int(j): [float(a) for a in e["liquid_n"]] for j, e in stages.items()}
    vapor = {int(j): [float(a) for a in e["vapor_n"]] for j, e in stages.items()}
    order = sorted(stages, key=int)
    assert [int(j) for j in order] == list(spec.equilibrium_stages())
    profile = (float(ref["condenser"]["T"]), *(float(stages[j]["T"]) for j in order))
    phi = float(ref["condenser"]["phi"])
    state = _initial_state(spec, REAL, CONTEXT, liquid, vapor, profile, phi=phi)
    assert state[reflux_fraction_id(UNIT)] == phi
    state[distillate_total_id(UNIT)] = float(ref["condenser"]["D"])
    for j in range(1, spec.stage_count + 1):
        state[stage_duty_id(UNIT, j)] = 0.0
    state[stage_duty_id(UNIT, 1)] = float(ref["condenser"]["Q"])
    state[stage_duty_id(UNIT, spec.stage_count)] = float(ref["reboiler"]["Q"])
    return state


def rows_over_tolerance(case: str) -> dict[str, float]:
    """`|row|/τ_kind` for every declared row at `reference_state(case)`."""
    spec = column_spec(case)
    problem = declared_problem(declared_rows(spec, REAL, CONTEXT))
    values = row_values(problem, reference_state(case))
    return {
        row: abs(value) / KIND_TOLERANCE[problem.row_kinds[row]] for row, value in values.items()
    }


@pytest.mark.parametrize("case", CASES)
def test_a42_every_declared_row_vanishes_at_the_reference_root(
    case: str, record_property: Any
) -> None:
    """A42: each declared row ≤ 1e-4 τ_kind at the root built from `ref` (floor ≤ 1.2e-6)."""
    over = rows_over_tolerance(case)
    largest = max(over.items(), key=lambda item: item[1])
    record_property("rows_at_root_max_over_tau", largest)
    assert largest[1] <= ROWS_AT_ROOT, largest


# -- A44 (M2): the K-block at the probe instead of `l` ---------------------------------------------


class M2Block(GammaPhiLnKBlock):
    """M2: the K-block evaluates at the probe `(1, …, 1)` whatever `l` is (values and Jacobian
    of that composition-independent function, so the mutant is self-consistent)."""

    def _evaluated(self, inputs: Sequence[float]) -> tuple[StreamState, bool]:
        count = len(self._components)
        probe = StreamState(
            n=probe_flows(count),
            temperature=float(inputs[count]),
            pressure=float(inputs[count + 1]),
        )
        return probe, True


def accepted_at_root(case: str) -> bool:
    """`solve_column` returns an accepted `CONVERGED` answer within A41's tolerances."""
    try:
        found = solve_column(column_spec(case), REAL)
    except AcceptanceDefectError:
        return False
    if not isinstance(found, ColumnSolution) or found.outcome != "CONVERGED":
        return False
    return worst(deviations(case, found.state))[0] <= 1.0


@pytest.mark.parametrize("case", CASES)
def test_a44_m2_is_detected(
    case: str, monkeypatch: pytest.MonkeyPatch, record_property: Any
) -> None:
    """A44: under M2, A42 fails, and A41 fails or the solve is not accepted (spec §5.5: rows of
    0.62 and 0.26 (mol/s)² at the roots, ≥ 2.8e6 τ_eq)."""
    reference_state(case)  # built from the unmutated declared rows
    assert rows_over_tolerance(case) and accepted_at_root(case)  # not vacuous
    monkeypatch.setattr(column_module, "GammaPhiLnKBlock", M2Block)
    mutated = rows_over_tolerance(case)
    record_property("m2_rows_at_root_max_over_tau", max(mutated.items(), key=lambda item: item[1]))
    assert max(mutated.values()) > ROWS_AT_ROOT
    assert not accepted_at_root(case)


# -- A35 (M1): recorded --------------------------------------------------------------------------


def test_a35_m1_record_on_c_mw(monkeypatch: pytest.MonkeyPatch, record_property: Any) -> None:
    """A35 (recorded): C-MW's Newton iterations and observed order under WO-3's M1 mutant (the
    K-block's `n` columns 0.0). Only a typed answer is asserted; the record is the result."""
    monkeypatch.setattr(column_module, "GammaPhiLnKBlock", M1Block)
    trace = Trace()
    found = solve_column(column_spec("C-MW"), REAL, trace=trace)
    assert isinstance(found, ColumnSolution | CascadeFailure)
    residuals = newton_residuals(trace)
    assert residuals
    record_property("outcome", (found.outcome, found.cause))
    record_property("newton_steps_in_trace", len(residuals))


# -- M4: undamped composition sweeps --------------------------------------------------------------


def test_m4_undamped_sweeps_exhaust_on_c_ew(monkeypatch: pytest.MonkeyPatch) -> None:
    """M4: with `SWEEP_RELAXATION = 1` C-EW's endpoint ends `initialization_failed(…,
    sweeps_exhausted)`; with the registered `1/2` it is built (design §4.9)."""
    spec = column_spec("C-EW")
    initial = profile_initial(spec, REAL, DECLARATION_CONTEXT)
    assert not isinstance(initial, CascadeFailure), initial
    damped = bubble_point_endpoint(spec, REAL, initial)
    assert isinstance(damped, BubblePointEndpoint), damped
    monkeypatch.setattr(column_solve, "SWEEP_RELAXATION", 1.0)
    undamped = bubble_point_endpoint(spec, REAL, initial)
    assert isinstance(undamped, CascadeFailure), undamped
    assert undamped.cause == f"initialization_failed({PRESOLVE_ID}, sweeps_exhausted)"


# -- Stage B: a constructed opening on a Wilson specification --------------------------------------


def stage_b_spec() -> ColumnSpec:
    """C-MW turned into a column with a flooded bottom section (S08 §5.2 candidate `(0, 10)`): a
    vapour feed `z = (0.4, 0, 0.6)` 5 K above its dew point on stage 10, a cold liquid feed on
    stage 11 and the reboiler under `duty` 500 W."""
    base = column_spec("C-MW")
    z = (0.4, 0.0, 0.6)
    dew = band_temperature(REAL, z, 101325.0, 1.0, DECLARATION_CONTEXT).temperature
    assert dew is not None
    return replace(
        base,
        reboiler_spec=EndSpecification("duty", 500.0),
        duties=(None,) + (0.0,) * (base.stage_count - 2) + (None,),
        sides=(
            SideFeed("feed", 10, InletState(z, dew + 5.0, 101325.0, "VAPOR")),
            SideFeed("cold", 11, InletState((0.1, 0.0, 0.3), 300.0, 101325.0, "LIQUID")),
        ),
    )


def test_stage_b_opening_on_a_wilson_specification() -> None:
    """S08 §5.3 on a Wilson specification (relaxed core sweeps, S10-C §4.9): built; every target
    row except the continued slots within its kind tolerance and the block duty slots within
    `ENERGY_TOLERANCE`; the L-block's vapour flows exactly `+0.0`; the absent component exactly
    zero; the overall component balance `Σ feed = d + l_N` to `1e-12 F`; the branch is σ(0, 10)."""
    spec = stage_b_spec()
    assert validate(spec, REAL, DECLARATION_CONTEXT) is None
    assert candidates(spec) == ((0, 10),)
    initial = profile_initial(spec, REAL, DECLARATION_CONTEXT)
    assert not isinstance(initial, CascadeFailure), initial
    found = block_endpoint(spec, REAL, initial, (0, 10))
    assert isinstance(found, BlockEndpoint), found
    assert 1 <= found.sweeps and found.last_delta <= column_solve.SWEEP_TOLERANCE
    signature = block_signature(spec, (0, 10))
    assert found.signature == signature
    stages = spec.equilibrium_stages()
    regimes = dict(zip(stages, signature, strict=True))
    target = compile_column(spec, REAL).spec
    replaced = [s for s in slots(spec, initial.profile) if s.parameter]
    continued = {s.target_row for s in replaced}
    values = row_values(target, found.state)
    over = {
        row: abs(value) / KIND_TOLERANCE[target.row_kinds[row]]
        for row, value in values.items()
        if row not in continued
    }
    assert max(over.values()) <= 1.0, max(over.items(), key=lambda item: item[1])
    block_duties = [s for s in replaced if s.continued == "Q" and regimes[s.stage] != "TWO_PHASE"]
    assert block_duties
    for s in block_duties:
        assert abs(values[s.target_row]) <= ENERGY_TOLERANCE, (s.stage, values[s.target_row])
    for j, regime in regimes.items():
        if regime == "LIQUID":
            for name in (*(vapor_id(UNIT, j, c) for c in spec.components), vapor_total_id(UNIT, j)):
                assert found.state[name] == 0.0, name
                assert math.copysign(1.0, found.state[name]) == 1.0, name
    gone = spec.components[1]
    for j in stages:
        assert found.state[liquid_id(UNIT, j, gone)] == 0.0
        assert found.state[vapor_id(UNIT, j, gone)] == 0.0
    feed_total = sum(sum(inlet.state.n) for inlet in spec.inlets())
    for i, c in enumerate(spec.components):
        fed = sum(inlet.state.n[i] for inlet in spec.inlets())
        out = (
            found.state[distillate_id(UNIT, c)] + found.state[liquid_id(UNIT, spec.stage_count, c)]
        )
        assert abs(fed - out) <= 1e-12 * feed_total, (c, fed - out)
    assert branch_found(lifted_splits(spec), found.state) == [
        (f"{UNIT}.stage.{j}", regimes[j]) for j in stages
    ]
