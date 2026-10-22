"""S01 WO-2 — the cascade compiled and solved: spec §4.1–§4.5, §7 and §8.

Every expectation is a value of `docs/derivations/scripts/s01_reference.json` (the design lane's
50-digit generator) or a rule of `docs/derivations/S01-spec.md`. Each test names the §10 assertion
it closes: A04, A05, A06, A07, A08, A09, A10, A20. A measured value that misses a registered
tolerance stays a failure: such a test is `xfail(strict=True)` with the measurement, and the
question is logged in `docs/S01_DECISIONS.md`.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pytest
from test_s01_cascade_wo1 import REFERENCE, UNIT, _spec

import openflowsheet.models.syn001.cascade_solve as solve_module
from openflowsheet.application.policies import T05B_V2
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001 import ENERGY_TOLERANCE, FLOW_TOLERANCE
from openflowsheet.models.syn001.cascade import (
    CascadeSpec,
    KremserInitial,
    _enthalpy_flow,
    kremser_initial,
    liquid_id,
    liquid_total_id,
    mixed_id,
    stage_duty_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.cascade_solve import (
    DECLARATION_CONTEXT,
    FD_COLUMN_SCALE,
    PRESOLVE_ID,
    S01_DEFAULT_V1,
    CascadeSolution,
    acceptance_failures,
    compile_cascade,
    overall_closure,
    products,
    solve_cascade,
    stage_unit,
)
from openflowsheet.models.syn001.ph_kernel import ph_state
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS
from openflowsheet.orchestrator.trace import Trace
from openflowsheet.thermo.syn001 import Syn001Provider

PROVIDER = Syn001Provider()
CASES = ("C1", "C2", "C3", "C4", "C5")

# Spec §10's state tolerance; its flow floor is 10·τ_flow (spec §17.5, R-514).
FLOW_REL, T_ABS, Q_ABS = 1e-6, 1e-4, 1e-2
FLOW_ABS = 10 * FLOW_TOLERANCE


_SOLVED: dict[str, CascadeSolution] = {}


def solved(case: str) -> CascadeSolution:
    """One solve per registered case per session (the solve is deterministic, A20)."""
    if case not in _SOLVED:
        answer = solve_cascade(_spec(REFERENCE["cases"][case]), PROVIDER)
        assert isinstance(answer, CascadeSolution), answer
        _SOLVED[case] = answer
    return _SOLVED[case]


def deviation(state: Any, records: list[dict[str, Any]]) -> dict[str, float]:
    """The worst error of `state` against `records`, each column in units of its own state
    tolerance (≤ 1 passes): flows, `T`, `Q`. (`P_j` is pinned by its own row.)"""
    worst = {"flow": 0.0, "T": 0.0, "Q": 0.0}
    for record in records:
        stage = record["stage"]
        for key, column in (("l", liquid_id), ("v", vapor_id), ("m", mixed_id)):
            for c, expected in zip(("A", "B", "C"), record[key], strict=True):
                target = float(expected)
                error = abs(state[column(UNIT, stage, c)] - target)
                worst["flow"] = max(worst["flow"], error / (FLOW_REL * abs(target) + FLOW_ABS))
        for key, total in (("L", liquid_total_id), ("V", vapor_total_id)):
            target = float(record[key])
            error = abs(state[total(UNIT, stage)] - target)
            worst["flow"] = max(worst["flow"], error / (FLOW_REL * abs(target) + FLOW_ABS))
        for key, column, tolerance in (
            ("T", stage_temperature_id, T_ABS),
            ("Q", stage_duty_id, Q_ABS),
        ):
            error = abs(state[column(UNIT, stage)] - float(record[key]))
            worst[key] = max(worst[key], error / tolerance)
    return worst


# -- the policy and the region descriptors -------------------------------------------------------


def test_the_policy_is_t05b_v2_with_newton_refined() -> None:
    """Spec §7.6 (build decision: the base policy is `T05b-v2`)."""
    expected = replace(
        T05B_V2,
        policy_id="s01-default-v1",
        globalization=replace(T05B_V2.globalization, eo_core="newton_refined"),
    )
    assert S01_DEFAULT_V1 == expected
    assert S01_DEFAULT_V1.globalization.eo_recovery == "homotopy"
    assert solve_module.PRESOLVE_POLICY.max_attempts == 1
    assert solve_module.PRESOLVE_POLICY.globalization.eo_recovery == "none"


@pytest.mark.parametrize("case", CASES)
def test_the_region_is_square_and_each_stage_is_one_split(case: str) -> None:
    """Spec §4.1–§4.2: one lifted split per stage, keyed `<U>.stage.<j>`, `feed = m_j`; every
    ZERO_FLOW form pins one column per dropped row, its energy row (last) swapped for the label."""
    spec = _spec(REFERENCE["cases"][case])
    for problem in ("target", "presolve"):
        compiled = compile_cascade(spec, PROVIDER, problem, tbar=360.0)  # type: ignore[arg-type]
        assert compiled.region.square
        assert compiled.region.units == tuple(
            stage_unit(UNIT, j) for j in range(1, spec.stage_count + 1)
        )
        assert set(compiled.types.values()) == {"PH" if problem == "target" else "TP"}
        for split in compiled.splits:
            form = compiled.forms[split.unit]
            assert split.feed == tuple(
                mixed_id(UNIT, int(split.unit.rsplit(".", 1)[1]), c) for c in "ABC"
            )
            # The swapped energy row is replaced by the label row; the other drops are pinned.
            assert len(form.columns) == len(form.rows) - 1
            assert form.rows[-1] == form.swapped
            assert form.label is not None and form.label[1] == split.temperature
    target = compile_cascade(spec, PROVIDER)
    presolve = compile_cascade(spec, PROVIDER, "presolve", tbar=360.0)
    assert target.spec.variable_ids == presolve.spec.variable_ids
    assert target.compiled.metadata.model_version != presolve.compiled.metadata.model_version


# -- A04: the pre-solve --------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_a04_the_presolve_root_and_q0(case: str) -> None:
    """A04: the isothermal pre-solve from `x_K` converges with every stage TWO_PHASE, to
    `ref.cases.*.presolve` (with `Q⁰`) within the state tolerance."""
    answer = solved(case)
    summary = answer.presolve_summary
    assert summary.outcome == "CONVERGED"
    assert summary.signature == ("TWO_PHASE",) * len(REFERENCE["cases"][case]["presolve"])
    assert answer.presolve.branch_provenance[0]["initializer_source"] == "s01-kremser-cmo-v1"
    worst = deviation(answer.presolve.state, REFERENCE["cases"][case]["presolve"])
    assert max(worst.values()) <= 1.0, worst


@pytest.mark.parametrize(
    ("case", "which"), [(case, which) for case in CASES for which in ("presolve", "target")]
)
def test_a04_a06_the_state_tolerance_is_ten_times_the_deviation(case: str, which: str) -> None:
    """Spec §10 ("needs a fact"): the measured maximum deviation, in units of the state
    tolerance, is at most 1/10."""
    answer = solved(case)
    state = answer.presolve.state if which == "presolve" else answer.state
    worst = deviation(state, REFERENCE["cases"][case][which])
    assert max(worst.values()) <= 0.1, worst


def test_a04_a_failed_presolve_is_initialization_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec §4.5: a pre-solve that does not converge ends `INITIALIZATION_FAILED`,
    `initialization_failed(s01-isothermal-presolve-v1, <outcome>)`, and no target solve runs."""
    starved = replace(solve_module.PRESOLVE_POLICY, max_iterations_per_attempt=1)
    monkeypatch.setattr(solve_module, "PRESOLVE_POLICY", starved)
    answer = solve_cascade(_spec(REFERENCE["cases"]["C2"]), PROVIDER)
    assert isinstance(answer, CascadeSolution)
    assert answer.outcome == "INITIALIZATION_FAILED"
    assert answer.presolve.outcome != "CONVERGED"
    assert answer.cause == f"initialization_failed({PRESOLVE_ID}, {answer.presolve.outcome})"
    assert answer.result is None


# -- A05: N = 1 is the PH flash ------------------------------------------------------------------


# A05's tolerance (spec §17.6, R-515): 10·τ_T and 10·τ_flow.
A05_T_ABS, A05_FLOW_ABS = 1e-5, 10 * FLOW_TOLERANCE


def _c1_ph_state() -> Any:
    spec = _spec(REFERENCE["cases"]["C1"])
    state = solved("C1").state
    feed = tuple(float(state[mixed_id(UNIT, 1, c)]) for c in "ABC")
    target = spec.duties[0] + sum(
        _enthalpy_flow(
            PROVIDER,
            DECLARATION_CONTEXT,
            spec.components,
            inlet.state.n,
            inlet.state.temperature,
            inlet.state.pressure,
            "LIQUID" if inlet.state.phase == "LIQUID" else "VAPOR",
        )
        for inlet in spec.inlets()
    )
    return ph_state(PROVIDER, feed, spec.pressures[0], target, DECLARATION_CONTEXT)


def test_a05_c1_is_the_ph_flash_branch() -> None:
    """A05 (branch): C1's stage is on the PH flash's branch, TWO_PHASE, as registered."""
    closure = _c1_ph_state()
    assert closure.status == "ok"
    assert closure.split.phase_signature == "TWO_PHASE"
    assert solved("C1").signature == ("TWO_PHASE",) == tuple(REFERENCE["cases"]["C1"]["signature"])


def test_a05_c1_equals_ph_state_and_ref_within_the_registered_tolerance() -> None:
    """A05: C1 equals `ph_state(m_1, P_r, H*)` and `ref`: T abs 1e-5 K (10·τ_T), flows abs
    10·τ_flow (spec §17.6, R-515)."""
    closure = _c1_ph_state()
    state = solved("C1").state
    record = REFERENCE["cases"]["C1"]["target"][0]
    temperature = state[stage_temperature_id(UNIT, 1)]
    assert abs(temperature - closure.temperature) <= A05_T_ABS
    assert abs(temperature - float(record["T"])) <= A05_T_ABS
    for i, c in enumerate("ABC"):
        for column, kernel, expected in (
            (liquid_id, closure.split.liquid.n[i], record["l"][i]),
            (vapor_id, closure.split.vapor.n[i], record["v"][i]),
        ):
            value = state[column(UNIT, 1, c)]
            assert abs(value - kernel) <= A05_FLOW_ABS
            assert abs(value - float(expected)) <= A05_FLOW_ABS


def test_a05_c1_is_within_the_state_tolerance_of_ref() -> None:
    """A05's weaker companion: C1 is within spec §10's state tolerance of `ref`."""
    worst = deviation(solved("C1").state, REFERENCE["cases"]["C1"]["target"])
    assert max(worst.values()) <= 1.0, worst


# -- A06, A07: the targets -----------------------------------------------------------------------


def test_a06_the_nominal_cascade() -> None:
    """A06: C2's root equals `ref.cases.C2.target` within the state tolerance, signature 2P ×3,
    reached from the pre-solve's root, and its products are the registered ones."""
    answer = solved("C2")
    record = REFERENCE["cases"]["C2"]
    assert answer.outcome == "CONVERGED"
    assert answer.signature == ("TWO_PHASE",) * 3 == tuple(record["signature"])
    assert answer.result is not None and answer.recovered_from is None
    assert answer.result.branch_provenance[0]["initializer_source"] == PRESOLVE_ID
    worst = deviation(answer.state, record["target"])
    assert max(worst.values()) <= 1.0, worst
    spec = _spec(record)
    for port, flows in products(spec, answer.state).items():
        for value, expected in zip(flows, record["products"][port], strict=True):
            assert abs(value - float(expected)) <= FLOW_REL * abs(float(expected)) + FLOW_ABS


def test_a07_the_side_fed_cascade_and_its_reversed_duties() -> None:
    """A07: C3's root equals `ref`; reversing the duty list moves the T profile by > 0.1 K."""
    answer = solved("C3")
    record = REFERENCE["cases"]["C3"]
    assert answer.outcome == "CONVERGED"
    assert answer.signature == tuple(record["signature"])
    worst = deviation(answer.state, record["target"])
    assert max(worst.values()) <= 1.0, worst

    spec = _spec(record)
    reversed_spec = replace(spec, duties=tuple(reversed(spec.duties)))
    flipped = solve_cascade(reversed_spec, PROVIDER)
    assert isinstance(flipped, CascadeSolution) and flipped.outcome == "CONVERGED"
    moved = max(
        abs(
            flipped.state[stage_temperature_id(UNIT, j)]
            - answer.state[stage_temperature_id(UNIT, j)]
        )
        for j in range(1, spec.stage_count + 1)
    )
    assert moved > 0.1
    # The generator's claim for the same comparison, at the state tolerance.
    assert abs(moved - float(REFERENCE["sensitivity"]["C3_reversed_duties_max_dT"])) <= 2 * T_ABS


# -- A08, A09: closure and acceptance ------------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_a08_overall_closure(case: str) -> None:
    """A08: spec §2's overall component and energy closure at the converged root, within
    `n_rows·τ_kind` — the `2N` mix and mole rows summed per component, the `N` energy rows."""
    answer = solved(case)
    assert answer.outcome == "CONVERGED"
    spec = _spec(REFERENCE["cases"][case])
    closure = overall_closure(spec, PROVIDER, answer.state)
    count = spec.stage_count
    assert all(abs(value) <= 2 * count * FLOW_TOLERANCE for value in closure.components), closure
    assert abs(closure.energy) <= count * ENERGY_TOLERANCE, closure


@pytest.mark.parametrize("case", CASES)
def test_a09_every_accepted_state_passes_section_8(case: str) -> None:
    """A09: the returned state passes §8 under its final signature (solve_cascade already
    refuses a CONVERGED answer that does not; this re-derives it independently of that path)."""
    answer = solved(case)
    spec = _spec(REFERENCE["cases"][case])
    assert answer.signature == tuple(REFERENCE["cases"][case]["signature"])
    declared = compile_cascade(spec, PROVIDER).spec
    assert acceptance_failures(spec, PROVIDER, declared, answer.state, answer.signature) == ()


def test_a09_section_8_refuses_a_state_off_the_root() -> None:
    """A09's converse: §8 names the rows a perturbed state violates, and a wrong signature."""
    answer = solved("C2")
    spec = _spec(REFERENCE["cases"]["C2"])
    declared = compile_cascade(spec, PROVIDER).spec
    off = dict(answer.state)
    off[stage_temperature_id(UNIT, 2)] += 1e-3
    failures = acceptance_failures(spec, PROVIDER, declared, off, answer.signature)
    assert any("S01:stage:2:energy" in failure for failure in failures)
    liquid = ("TWO_PHASE", "LIQUID", "TWO_PHASE")
    failures = acceptance_failures(spec, PROVIDER, declared, answer.state, liquid)  # type: ignore[arg-type]
    assert any("pinned column S01.stage.2.v.A" in failure for failure in failures)


# -- A10: the compiled Jacobian ------------------------------------------------------------------


def _fd_errors(spec: CascadeSpec, state: Any) -> dict[tuple[str, str], float]:
    """Spec §10 A10: `D_r⁻¹ J D_x` against central differences at `h = 1e-6·max(D_x, |x|)`
    (spec §17.7, R-516: a uniform scaled step), per
    entry, relative to `max(1, |exact|)` (the generator's `fd_floor` measure); the worst entry of
    each column, keyed `(column, row)`. Also checks the compiled ids are the declared ones."""
    target = compile_cascade(spec, PROVIDER)
    problem, compiled = target.spec, target.compiled
    context: EvaluationContext = target.context()
    x = np.array([state[name] for name in problem.variable_ids], dtype=np.float64)
    result = compiled.jacobian(x, context)
    assert result.status == "ok"
    assert tuple(result.row_ids) == problem.equation_ids
    assert tuple(result.col_ids) == problem.variable_ids
    exact = np.zeros((len(result.row_ids), len(result.col_ids)))
    for column in range(len(result.col_ids)):
        for k in range(result.indptr[column], result.indptr[column + 1]):
            exact[result.indices[k], column] = result.data[k]
    d_x = np.array([FD_COLUMN_SCALE[problem.variable_kinds[n]] for n in problem.variable_ids])
    d_r = np.array([REGISTERED_NOMINALS[problem.row_kinds[n]] for n in problem.equation_ids])
    errors: dict[tuple[str, str], float] = {}
    for column in range(len(x)):
        h = 1e-6 * max(d_x[column], abs(x[column]))
        up, down = x.copy(), x.copy()
        up[column] += h
        down[column] -= h
        f_up = compiled.residual(up, context)
        f_down = compiled.residual(down, context)
        assert f_up.values is not None and f_down.values is not None
        fd = (np.asarray(f_up.values) - np.asarray(f_down.values)) / (2 * h)
        scaled_exact = exact[:, column] * d_x[column] / d_r
        scaled_fd = fd * d_x[column] / d_r
        error = np.abs(scaled_fd - scaled_exact) / np.maximum(1.0, np.abs(scaled_exact))
        row = int(error.argmax())
        errors[(problem.variable_ids[column], problem.equation_ids[row])] = float(error[row])
    return errors


#: Spec §10 A10's tolerance, and the floor it must clear at both points: the comparison's
#: resolution, 100× under the tolerance (spec §17.7, R-516). Measurements in docs/S01_DECISIONS.md.
FD_TOLERANCE = 1e-6
FD_FLOOR = 1e-8


def test_a10_the_compiled_jacobian_at_the_initializer() -> None:
    """A10 at C2's `x_K`: within 1e-6, and the floor under 1e-8 (measured 5.90e-11)."""
    spec = _spec(REFERENCE["cases"]["C2"])
    initial = kremser_initial(spec, PROVIDER, DECLARATION_CONTEXT)
    assert isinstance(initial, KremserInitial)
    worst = max(_fd_errors(spec, initial.state).values())
    assert worst <= FD_TOLERANCE
    assert worst <= FD_FLOOR


def test_a10_the_compiled_jacobian_at_the_c2_root_is_within_tolerance() -> None:
    """A10 at C2's root, at the registered 1e-6 (measured 5.90e-11)."""
    spec = _spec(REFERENCE["cases"]["C2"])
    assert max(_fd_errors(spec, solved("C2").state).values()) <= FD_TOLERANCE


def test_a10_the_fd_floor_at_the_c2_root_is_below_1e_8() -> None:
    """Handoff gap 3, closed by R-516: the FD floor on the compiled Jacobian at C2's root is below
    1e-8 (measured 5.90e-11)."""
    spec = _spec(REFERENCE["cases"]["C2"])
    assert max(_fd_errors(spec, solved("C2").state).values()) <= FD_FLOOR


def test_a10_where_the_c2_root_floor_sits() -> None:
    """The measured floor under R-516's step, held as a fact. Under the old step `1e-6·max(1, |x|)`
    the `(Q_j, energy_j)` entries carried 3.39e-8 of rounding; with a uniform scaled step they
    measure 1.6e-11 to 2.0e-11, and no entry exceeds 1e-10 (worst 5.90e-11). The compiled
    `(Q_j, energy_j)` derivative is exactly `+1` (`energy_j`'s source term)."""
    spec = _spec(REFERENCE["cases"]["C2"])
    state = solved("C2").state
    errors = _fd_errors(spec, state)
    assert max(errors.values()) <= 1e-10, max(errors.values())
    for j in range(1, spec.stage_count + 1):
        assert errors[(stage_duty_id(UNIT, j), f"S01:stage:{j}:energy")] <= 1e-10
    target = compile_cascade(spec, PROVIDER)
    x = np.array([state[name] for name in target.spec.variable_ids], dtype=np.float64)
    result = target.compiled.jacobian(x, target.context())
    columns, rows = list(result.col_ids), list(result.row_ids)
    for j in range(1, spec.stage_count + 1):
        column = columns.index(stage_duty_id(UNIT, j))
        entries = {
            rows[result.indices[k]]: result.data[k]
            for k in range(result.indptr[column], result.indptr[column + 1])
        }
        assert entries[f"S01:stage:{j}:energy"] == 1.0


# -- A20: reproducibility ------------------------------------------------------------------------


def _records(answer: CascadeSolution, trace: Trace) -> list[str]:
    assert answer.result is not None
    return [
        repr(answer.presolve_summary),
        answer.initial_sha256,
        str(answer.presolve_sha256),
        str(answer.final_sha256),
        repr([dict(item) for item in answer.result.branch_provenance]),
        repr(answer.result.signatures),
        repr(answer.result.root_fingerprint),
        *(repr(event.as_document()) for event in trace.events),
    ]


def test_a20_c2_solved_twice_is_identical() -> None:
    """A20: two solves of C2 give the same final `state_sha256` and the same records."""
    spec = _spec(REFERENCE["cases"]["C2"])
    runs = []
    for _ in range(2):
        trace = Trace()
        answer = solve_cascade(spec, PROVIDER, trace=trace)
        assert isinstance(answer, CascadeSolution) and answer.outcome == "CONVERGED"
        runs.append((answer, trace))
    (first, first_trace), (second, second_trace) = runs
    assert first.final_sha256 == second.final_sha256
    assert first.state == second.state
    assert len(first_trace) > 0
    assert _records(first, first_trace) == _records(second, second_trace)
