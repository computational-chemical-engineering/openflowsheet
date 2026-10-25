"""S02 WO-3 — phases: spec §4.3's singular pairs on the compiled Jacobian (A11) and the phase
case P1 (A12). A14 is §18.6's, closed in `test_s02_column_wo2b.py`.

Expectations are values of `docs/derivations/scripts/s02_reference.json` (the design lane's
50-digit generator: `singular_pairs`, `phase_case.P1`, `cases.*.target`), codes and rules of
`docs/derivations/S02-spec.md` §4, §10 and §18.5, or arithmetic done here. Each test names the
assertion of §10 it closes.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from test_s02_column_wo1 import PROVIDER, REFERENCE, SPECS, UNIT
from test_s02_column_wo2 import FLOW_ABS, FLOW_REL, T_ABS, stages_state

from openflowsheet.models.syn001.cascade import (
    liquid_id,
    liquid_total_id,
    mixed_id,
    stage_pressure_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.column import ColumnSpec, _inflow, regime_form
from openflowsheet.models.syn001.column_solve import (
    FD_COLUMN_SCALE,
    ColumnSolution,
    acceptance_failures,
    compile_column,
    solve_column,
    stage_unit,
)
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.thermo.syn001 import C_P, h_liquid, h_vapor

# -- A11: §4.3's circulation vector on the compiled Jacobian -------------------------------------

#: §10 A11: the bound at the singular probes and the floor at M1's all-2P root.
NULL_BOUND, NOT_NULL_FLOOR = 1e-9, 1e-3
#: `ref.singular_pairs`' probe label → the registered case it is built from.
PROBES = {"M1_stage3_LIQUID": "M1", "M3_stage1_LIQUID": "M3", "M1_stage4_VAPOR": "M1"}


def _probe_state(case: str, pair: tuple[int, int], upper_liquid: bool) -> dict[str, float]:
    """`ref.cases.<case>.target` with the regime's pins applied, as the generator builds the probe
    (`s02_reference.py` `singular_pairs`): a `LIQUID` stage j has `v_j = 0` (`V_j = 0`), a `VAPOR`
    stage j+1 has `l_{j+1} = 0` (`L_{j+1} = 0`); the `m` columns follow from their inflows."""
    stages = [dict(record) for record in REFERENCE["cases"][case]["target"]["stages"]]
    stage, flows, total = (pair[0], "v", "V") if upper_liquid else (pair[1], "l", "L")
    for record in stages:
        if record["stage"] == stage:
            record[flows], record[total] = ["0"] * 3, "0"
    return stages_state(SPECS[case], stages)


def _circulation(
    spec: ColumnSpec, state: dict[str, float], j: int, upper_liquid: bool
) -> dict[str, float]:
    """Spec §4.3's null vector for the pair `(j, j+1)` mapped onto the implementation's columns
    (§10 A11): `l_j`, `v_{j+1}`, `m_j` and `m_{j+1}` each `+= c`; `L_j`, `V_{j+1}` `+= 1`; the
    `T` shift on `T_j` (stage j `LIQUID`, `c = v_{j+1}/V_{j+1}`) or on `T_{j+1}` (stage j+1
    `VAPOR`, `c = l_j/L_j`), with SYN-001's `h^L(T_j, P_j)` and `h^V(T_{j+1})`."""
    components = spec.components
    for c in components:  # the mapping's premise: m_j takes v_{j+1}, m_{j+1} takes l_j
        assert vapor_id(UNIT, j + 1, c) in _inflow(spec, j, c)
        assert liquid_id(UNIT, j, c) in _inflow(spec, j + 1, c)
    if upper_liquid:
        flows = [state[vapor_id(UNIT, j + 1, c)] for c in components]
    else:
        flows = [state[liquid_id(UNIT, j, c)] for c in components]
    composition = [flow / sum(flows) for flow in flows]
    t_upper, t_lower = (
        state[stage_temperature_id(UNIT, j)],
        state[stage_temperature_id(UNIT, j + 1)],
    )
    pressure = state[stage_pressure_id(UNIT, j)]
    h_v = sum(x * h_vapor(t_lower, i) for i, x in enumerate(composition))
    h_l = sum(x * h_liquid(t_upper, pressure, i) for i, x in enumerate(composition))
    delta: dict[str, float] = {}
    for c, x in zip(components, composition, strict=True):
        for name in (
            liquid_id(UNIT, j, c),
            vapor_id(UNIT, j + 1, c),
            mixed_id(UNIT, j, c),
            mixed_id(UNIT, j + 1, c),
        ):
            delta[name] = x
    delta[liquid_total_id(UNIT, j)] = 1.0
    delta[vapor_total_id(UNIT, j + 1)] = 1.0
    if upper_liquid:
        shift = (h_v - h_l) / (C_P * state[liquid_total_id(UNIT, j)])
        delta[stage_temperature_id(UNIT, j)] = shift
    else:
        shift = (h_l - h_v) / (C_P * state[vapor_total_id(UNIT, j + 1)])
        delta[stage_temperature_id(UNIT, j + 1)] = shift
    return delta


def scaled_null_residual(
    spec: ColumnSpec,
    state: dict[str, float],
    regimes: dict[int, str],
    delta: dict[str, float],
) -> float:
    """§10 A11's measure `‖D_r⁻¹ J δ‖∞ / ‖D_x⁻¹ δ‖∞` on the compiled Jacobian at `state`, over
    the rows the signature keeps (each stage's `regime_form` drops); `δ` must vanish on the
    columns it pins. `D_x`, `D_r` are A10's (`FD_COLUMN_SCALE`, `REGISTERED_NOMINALS`)."""
    target = compile_column(spec, PROVIDER)
    problem, compiled = target.spec, target.compiled
    dropped: set[str] = set()
    pinned: set[str] = set()
    for stage, regime in regimes.items():
        form = regime_form(spec, stage, regime)  # type: ignore[arg-type]
        dropped.update(form.dropped)
        pinned.update(form.pinned)
    assert not pinned & set(delta), "δ moves a pinned column"
    assert set(delta) <= set(problem.variable_ids)
    x = np.array([state[name] for name in problem.variable_ids], dtype=np.float64)
    result = compiled.jacobian(x, target.context())
    assert result.status == "ok" and tuple(result.col_ids) == problem.variable_ids
    d_x = np.array([FD_COLUMN_SCALE[problem.variable_kinds[n]] for n in problem.variable_ids])
    d_r = np.array([REGISTERED_NOMINALS[problem.row_kinds[n]] for n in problem.equation_ids])
    step = np.array([delta.get(name, 0.0) for name in problem.variable_ids])
    product = np.zeros(len(result.row_ids))
    for column in range(len(result.col_ids)):
        for k in range(result.indptr[column], result.indptr[column + 1]):
            product[result.indices[k]] += result.data[k] * step[column]
    kept = np.array([name not in dropped for name in problem.equation_ids])
    assert kept.sum() == len(problem.equation_ids) - len(dropped)
    return float(np.max(np.abs(product[kept] / d_r[kept])) / np.max(np.abs(step / d_x)))


@pytest.mark.parametrize("label", sorted(PROBES))
def test_a11_the_circulation_vector_is_null_at_the_singular_probes(label: str) -> None:
    """A11: at each of `ref.singular_pairs`' probe states (its case's root with the regime's
    pins), §4.3's circulation vector annihilates the compiled Jacobian of the signature's rows:
    ≤ 1e-9 scaled (the generator: `J_delta_max` ≤ 5.2e-53 at 50 digits)."""
    record = REFERENCE["singular_pairs"][label]
    case = PROBES[label]
    spec = SPECS[case]
    j, below = record["pair"]
    assert below == j + 1
    regimes = dict(zip(spec.equilibrium_stages(), record["signature"], strict=True))
    upper_liquid = regimes[j] == "LIQUID"
    assert upper_liquid or regimes[j + 1] == "VAPOR"
    assert [stage for stage, regime in regimes.items() if regime != "TWO_PHASE"] == [
        j if upper_liquid else j + 1
    ]
    assert float(record["J_delta_max"]) <= 5.2e-53 and float(record["sigma_min"]) <= 4.4e-41
    state = _probe_state(case, (j, j + 1), upper_liquid)
    delta = _circulation(spec, state, j, upper_liquid)
    measured = scaled_null_residual(spec, state, regimes, delta)
    assert measured <= NULL_BOUND, measured


def test_a11_the_same_vector_is_not_null_at_m1s_two_phase_root() -> None:
    """A11's control: at M1's all-2P root (`ref.cases.M1.target`), the stage-3-`LIQUID` vector
    (pair (3, 4)) moves two-phase stage 3's `T` and with it its `K`: ≥ 1e-3 scaled. An all-zero
    Jacobian fails here (and in A10)."""
    spec = SPECS["M1"]
    state = stages_state(spec, REFERENCE["cases"]["M1"]["target"]["stages"])
    regimes = {j: "TWO_PHASE" for j in spec.equilibrium_stages()}
    delta = _circulation(spec, state, 3, True)
    measured = scaled_null_residual(spec, state, regimes, delta)
    assert measured >= NOT_NULL_FLOOR, measured


# -- A12: the phase case P1 ----------------------------------------------------------------------

_P1: list[ColumnSolution] = []


def p1() -> ColumnSolution:
    """`solve_column` on §9's P1 (M3's stripper at `Q_r* = 3 kW`), once per session."""
    if not _P1:
        answer = solve_column(SPECS["P1"], PROVIDER)
        assert isinstance(answer, ColumnSolution), answer
        _P1.append(answer)
    return _P1[0]


def attempt_list(result: RegionResult, recovered_from: RegionResult | None) -> list[dict[str, Any]]:
    """Every attempt of a solve and of its recovery, in order: which solve, its outcome, what
    Newton ended on, and the attempted signature (top to bottom)."""
    solves: list[tuple[str, RegionResult]] = []
    if recovered_from is not None:
        solves.append(("target", recovered_from))
        solves.append(("edge 3", result))
    else:
        solves.append(("target", result))
    return [
        {
            "solve": which,
            "attempt": index,
            "outcome": attempt.outcome,
            "solver_outcome": attempt.solver_outcome,
            "signature": [regime for _, regime in attempt.signature],
        }
        for which, result in solves
        for index, attempt in enumerate(result.attempts)
    ]


def _closed_form(spec: ColumnSpec) -> dict[str, float]:
    """`ref.phase_case.P1`: every stage `LIQUID` with `l_j` the top inlet, `v_j = +0.0`."""
    record = REFERENCE["phase_case"]["P1"]
    stages = [
        {
            "stage": j,
            "l": record["l"],
            "v": record["top_product"],
            "L": str(sum(float(value) for value in record["l"])),
            "V": "0",
            "T": record["T"][j - 1],
            "Q": record["Q_reboiler"] if j == spec.stage_count else "0",
        }
        for j in spec.equilibrium_stages()
    ]
    return stages_state(spec, stages)


def test_a12_p1_is_the_closed_form() -> None:
    """A12, its `CONVERGED` branch only (S08 design note §6.1 withdraws the typed branch for P1):
    P1's outcome is `CONVERGED` with signature LIQUID ×5 equal to the closed form
    (`ref.phase_case.P1`, distillate `+0.0` sign-checked), passing §8, and its attempt records
    name every attempted signature. S08's Stage B reaches it (Stage A is held below)."""
    spec = SPECS["P1"]
    record = REFERENCE["phase_case"]["P1"]
    assert record["signature"] == ["LIQUID"] * spec.stage_count
    answer = p1()
    assert answer.outcome == "CONVERGED"
    attempts = attempt_list(answer.result, answer.recovered_from)
    assert attempts
    for attempt in attempts:
        assert len(attempt["signature"]) == len(spec.equilibrium_stages())
        assert set(attempt["signature"]) <= {"TWO_PHASE", "LIQUID", "VAPOR", "ZERO_FLOW"}
    names = {stage_unit(UNIT, j) for j in spec.equilibrium_stages()}
    for result in (answer.result, answer.recovered_from):
        for attempt in result.attempts if result is not None else ():
            assert {unit for unit, _ in attempt.signature} == names
    regimes = dict(zip(spec.equilibrium_stages(), answer.signature, strict=True))
    declared = compile_column(spec, PROVIDER).spec
    assert acceptance_failures(spec, PROVIDER, declared, answer.state, regimes) == ()
    assert answer.signature == ("LIQUID",) * spec.stage_count
    expected = _closed_form(spec)
    for j in spec.equilibrium_stages():
        name = stage_temperature_id(UNIT, j)
        assert abs(answer.state[name] - expected[name]) <= T_ABS
        for c in spec.components:
            name = liquid_id(UNIT, j, c)
            assert abs(answer.state[name] - expected[name]) <= FLOW_REL * expected[name] + FLOW_ABS
    for c in spec.components:
        top = answer.state[vapor_id(UNIT, 1, c)]
        assert top == 0.0 and np.copysign(1.0, top) == 1.0


def test_a12_p1_measured_branch_is_held() -> None:
    """A12's measured branch (§18.5, WO-3), held as a regression value, is now S08's Stage A
    inside P1's answer (S08 design note §6.1: `reentry.stage_a`, exactly): `HOMOTOPY_STALLED`,
    `homotopy_stalled(BOUND_BLOCKED)`; the target's attempts 2P×5 (Newton `BOUND_BLOCKED`) then
    `(2P, L, 2P, 2P, 2P)` (`LINE_SEARCH_FAILED`, closing `ACTIVE_SET_CYCLING`), then edge 3 from
    2P×5. `(2P, L, 2P, 2P, 2P)` breaks §4.3's block rule (R-533). A move of this branch is
    re-registered with the design lane, not re-baselined here."""
    reentry = p1().reentry
    assert reentry is not None and reentry.trigger == "HOMOTOPY_STALLED"
    stage_a = reentry.stage_a
    assert (stage_a.outcome, stage_a.cause) == (
        "HOMOTOPY_STALLED",
        "homotopy_stalled(BOUND_BLOCKED)",
    )
    assert stage_a.failures == ()
    two_phase, broken = ["TWO_PHASE"] * 5, ["TWO_PHASE", "LIQUID"] + ["TWO_PHASE"] * 3
    attempts = attempt_list(stage_a.result, stage_a.recovered_from)
    assert [(a["solve"], a["solver_outcome"], a["signature"]) for a in attempts] == [
        ("target", "BOUND_BLOCKED", two_phase),
        ("target", "LINE_SEARCH_FAILED", broken),
        ("edge 3", "HOMOTOPY_STALLED", two_phase),
    ]
    assert stage_a.recovered_from is not None
    assert stage_a.recovered_from.outcome == "ACTIVE_SET_CYCLING"
