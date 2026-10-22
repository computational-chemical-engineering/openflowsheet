"""S02 WO-2 — the column compiled and solved: spec §7, §8 and §17's A17–A19.

Expectations are values of `docs/derivations/scripts/s02_reference.json` (the design lane's
50-digit generator), codes and rules of `docs/derivations/S02-spec.md`, or arithmetic done here.
Each test names the assertion of §10 / §17 it closes.

Measured (WO-2, `docs/S02_DECISIONS.md` Q-S02-WO2-1): §7.3's pre-solve from `x_K` does not
converge on any registered case, so every assertion read through `solve_column` from `x_K` is a
strict xfail carrying its measured outcome. Steps 4–5 (target, edge 3, §8) are tested from the
generator's own pre-solve root `x⁰` (`ref.cases.*.presolve`), an independent expectation.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import numpy as np
import pytest
from test_s02_column_wo1 import CASES, PROVIDER, REFERENCE, SPECS, UNIT, _variant

import openflowsheet.models.syn001.column_solve as solve_module
import openflowsheet.orchestrator.region as region_module
from openflowsheet.compile.reference import row_values
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models.syn001 import FLOW_TOLERANCE
from openflowsheet.models.syn001.cascade import (
    label_row_id,
    liquid_id,
    liquid_total_id,
    mixed_id,
    stage_duty_id,
    stage_pressure_id,
    stage_row_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.cascade_solve import S01_DEFAULT_V1
from openflowsheet.models.syn001.column import (
    _inflow,
    _inlet_columns,
    declared_rows,
    distillate_id,
    distillate_total_id,
    label_source,
    profile_initial,
    reflux_fraction_id,
    reflux_id,
    regime_form,
    validate,
)
from openflowsheet.models.syn001.column_solve import (
    DECLARATION_CONTEXT,
    FD_COLUMN_SCALE,
    PRESOLVE_ID,
    PRESOLVE_POLICY,
    S02_TARGET_POLICY,
    ColumnSolution,
    acceptance_failures,
    compile_column,
    continuation,
    overall_closure,
    products,
    singular_pairs,
    slots,
    solve_column,
    solve_target,
    spec_values,
)
from openflowsheet.numerics.scaling import (
    REGISTERED_NOMINALS,
    ScaleUnavailableError,
    Scaling,
)
from openflowsheet.orchestrator.region import KIND_TOLERANCE, RegionResult
from openflowsheet.orchestrator.roots import same_root
from openflowsheet.orchestrator.splits import check_agreement
from openflowsheet.orchestrator.trace import Trace

# Spec §10's state tolerance (S01's, R-514): flows rel 1e-6 + 10·τ_flow, T 1e-4 K, Q 1e-2 W.
FLOW_REL, FLOW_ABS, T_ABS, Q_ABS = 1e-6, 10 * FLOW_TOLERANCE, 1e-4, 1e-2
#: §10 A10: the tolerance and the floor the measurement must clear.
FD_TOLERANCE, FD_FLOOR = 1e-6, 1e-8


def ref_state(case: str, which: str = "presolve") -> dict[str, float]:
    """`ref.cases.<case>.<which>` mapped onto the implementation's columns: the generator's
    `(l, v, T, Q)` per equilibrium stage and `(φ, r, d, T_c, Q_c)` at a total condenser; `P_j`
    pinned at `P_j*`, `L, V, D` their sums as recorded, `m` from the `mix` rows, inlets as given."""
    spec = SPECS[case]
    values = _inlet_columns(spec)
    for record in REFERENCE["cases"][case][which]["stages"]:
        j = record["stage"]
        if record.get("kind") == "total_condenser":
            for c, r, d in zip("ABC", record["reflux"], record["distillate"], strict=True):
                values[reflux_id(UNIT, c)] = float(r)
                values[distillate_id(UNIT, c)] = float(d)
            values[reflux_fraction_id(UNIT)] = float(record["phi"])
            values[distillate_total_id(UNIT)] = sum(float(d) for d in record["distillate"])
        else:
            for c, liquid, vapor in zip("ABC", record["l"], record["v"], strict=True):
                values[liquid_id(UNIT, j, c)] = float(liquid)
                values[vapor_id(UNIT, j, c)] = float(vapor)
            values[liquid_total_id(UNIT, j)] = float(record["L"])
            values[vapor_total_id(UNIT, j)] = float(record["V"])
        values[stage_temperature_id(UNIT, j)] = float(record["T"])
        values[stage_duty_id(UNIT, j)] = float(record["Q"])
        values[stage_pressure_id(UNIT, j)] = spec.pressures[j - 1]
    for j in spec.equilibrium_stages():
        for c in "ABC":
            values[mixed_id(UNIT, j, c)] = sum(values[name] for name in _inflow(spec, j, c))
    return values


def deviation(case: str, state: Any) -> dict[str, float]:
    """The worst error of `state` against `ref.cases.<case>.target`, each column in units of its
    own state tolerance (≤ 1 passes): flows (`l, v, L, V`, and `r, d` at a total condenser),
    `T`, `Q`, and `φ` (a ratio: rel 1e-6)."""
    worst = {"flow": 0.0, "T": 0.0, "Q": 0.0, "ratio": 0.0}
    expected = ref_state(case, "target")
    for name, target in expected.items():
        if name.endswith((".T", ".Q", ".phi")) or ".n." in name or ".flow." in name:
            continue
        if name.split(".")[-1] in ("P",) or name not in state:
            continue
        error = abs(state[name] - target)
        worst["flow"] = max(worst["flow"], error / (FLOW_REL * abs(target) + FLOW_ABS))
    for j in range(1, SPECS[case].stage_count + 1):
        for key, column, tolerance in (
            ("T", stage_temperature_id, T_ABS),
            ("Q", stage_duty_id, Q_ABS),
        ):
            name = column(UNIT, j)
            worst[key] = max(worst[key], abs(state[name] - expected[name]) / tolerance)
    if SPECS[case].total_condenser:
        phi = reflux_fraction_id(UNIT)
        worst["ratio"] = abs(state[phi] - expected[phi]) / (FLOW_REL * abs(expected[phi]))
    return worst


_TARGETS: dict[str, tuple[RegionResult, RegionResult | None, dict[int, Any]]] = {}


def from_x0(case: str) -> tuple[RegionResult, RegionResult | None, dict[int, Any]]:
    """Spec §7 steps 4–5 and §8 from the generator's pre-solve root, once per session."""
    if case not in _TARGETS:
        spec = SPECS[case]
        profile = [float(t) for t in REFERENCE["cases"][case]["initializer"]["profile"]]
        _TARGETS[case] = solve_target(
            spec, PROVIDER, compile_column(spec, PROVIDER), ref_state(case), profile
        )
    return _TARGETS[case]


#: Steps 4–5 from `x⁰` converge unforced on these (measured); M1's ends LINEAR_SOLVE_FAILED.
FROM_X0 = ("M2", "M3", "M4")


# -- the policy -----------------------------------------------------------------------------------


def test_the_policies_are_s01s_registered_ones() -> None:
    """Spec §0, §7.3–§7.4: the target runs S01's `s01-default-v1` (the object itself); the
    pre-solve is S01's pre-solve policy under `s02-profile-presolve-v1` (no `phase_contract`
    keyword here, T05b B06)."""
    assert S02_TARGET_POLICY is S01_DEFAULT_V1
    assert PRESOLVE_POLICY.policy_id == PRESOLVE_ID == "s02-profile-presolve-v1"
    assert PRESOLVE_POLICY.max_attempts == 1
    assert PRESOLVE_POLICY.globalization.eo_recovery == "none"
    assert PRESOLVE_POLICY.phase_contract == S01_DEFAULT_V1.phase_contract


@pytest.mark.parametrize("case", CASES)
def test_the_region_is_square_with_one_split_per_equilibrium_stage(case: str) -> None:
    spec = SPECS[case]
    profile = [float(t) for t in REFERENCE["cases"][case]["initializer"]["profile"]]
    target = compile_column(spec, PROVIDER)
    pre = compile_column(spec, PROVIDER, "presolve", profile=profile)
    for compiled in (target, pre):
        assert compiled.region.square
        assert len(compiled.splits) == len(spec.equilibrium_stages())
    assert target.spec.variable_ids == pre.spec.variable_ids
    assert set(target.types.values()) == {"PH"} and set(pre.types.values()) == {"TP"}
    assert target.compiled.metadata.model_version != pre.compiled.metadata.model_version


# -- A05: the pre-solve ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_a05_the_slot_substitutions_are_refs(case: str) -> None:
    """A05: §7.3's substitution at every stage (kind exact, value as `ref.presolve_slots`), the
    continued slots' kinds as `ref.continued`, and `p⁰` = the slot's column at the generator's
    `x⁰` within A13's tolerance (Q abs 1e-2 W, rates rel 1e-6)."""
    spec = SPECS[case]
    record = REFERENCE["cases"][case]
    profile = [float(t) for t in record["initializer"]["profile"]]
    found = {slot.stage: slot for slot in slots(spec, profile)}
    assert sorted(found) == sorted(int(j) for j in record["presolve_slots"])
    for stage, (kind, value) in record["presolve_slots"].items():
        slot = found[int(stage)]
        assert slot.kind == kind
        assert abs(slot.value - float(value)) <= 1e-9 * abs(float(value))
    continued = {slot.stage: slot for slot in found.values() if slot.parameter}
    assert sorted(continued) == sorted(int(j) for j in record["continued"])
    x0 = ref_state(case)
    for stage, expected in record["continued"].items():
        slot = continued[int(stage)]
        assert slot.continued == expected["kind"]
        p0 = x0[slot.variable]
        tolerance = Q_ABS if expected["kind"] == "Q" else FLOW_REL * abs(float(expected["p0"]))
        assert abs(p0 - float(expected["p0"])) <= tolerance
    assert continuation(spec, profile).parameter_ids == tuple(
        continued[j].parameter for j in sorted(continued)
    )


@pytest.mark.parametrize("case", CASES)
def test_a05_the_presolve_rows_hold_at_the_generators_x0(case: str) -> None:
    """A05: the pre-solve's rows — every replaced slot as `T_j − T_j⁰` (or `Σ r − 1·D`), every
    ratio kept at its target — vanish at the generator's `x⁰` within their kind tolerances."""
    spec = SPECS[case]
    profile = [float(t) for t in REFERENCE["cases"][case]["initializer"]["profile"]]
    pre = compile_column(spec, PROVIDER, "presolve", profile=profile)
    values = row_values(pre.spec, ref_state(case))
    worst = {row: abs(v) / KIND_TOLERANCE[pre.spec.row_kinds[row]] for row, v in values.items()}
    assert max(worst.values()) <= 1.0, max(worst.items(), key=lambda item: item[1])
    kept = [s for s in slots(spec, profile) if not s.parameter]
    assert all(s.row in values for s in kept)


#: Measured at WO-2 (`docs/S02_DECISIONS.md` Q-S02-WO2-1): §7.3's pre-solve from `x_K`.
PRESOLVE_MEASURED = {
    "M1": "LINEAR_SOLVE_FAILED (opening V,V,V,2P,2P,2P,2P; structurally singular, rank 90 of 91)",
    "M2": "ATTEMPTS_EXHAUSTED (one attempt, phase update required)",
    "M3": "ATTEMPTS_EXHAUSTED (opening 2P,L,L,L,L; phase update required)",
    "M4": "ATTEMPTS_EXHAUSTED (one attempt, phase update required)",
}


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            case,
            marks=pytest.mark.xfail(
                strict=True, reason=f"Q-S02-WO2-1, measured: {PRESOLVE_MEASURED[case]}"
            ),
        )
        for case in CASES
    ],
)
def test_a05_the_presolve_root(case: str) -> None:
    """A05: §7.3's pre-solve from `x_K` converges, every stage TWO_PHASE, to `ref.presolve`."""
    answer = solve_column(SPECS[case], PROVIDER)
    assert isinstance(answer, ColumnSolution)
    assert answer.presolve_summary.outcome == "CONVERGED"
    assert max(deviation_presolve(case, answer.presolve.state).values()) <= 1.0


def deviation_presolve(case: str, state: Any) -> dict[str, float]:
    expected = ref_state(case)
    return {
        name: abs(state[name] - target) / (T_ABS if name.endswith(".T") else Q_ABS)
        for name, target in expected.items()
        if name.endswith((".T", ".Q"))
    }


@pytest.mark.parametrize("case", CASES)
def test_a05_a_failed_presolve_is_a_typed_initialization_failure(case: str) -> None:
    """The measured pre-solve failure ends typed, never as a success (§7.3)."""
    answer = solve_column(SPECS[case], PROVIDER)
    assert isinstance(answer, ColumnSolution)
    assert answer.outcome == "INITIALIZATION_FAILED" and answer.result is None
    assert answer.cause.startswith(f"initialization_failed({PRESOLVE_ID}, ")
    assert answer.presolve_summary.outcome != "CONVERGED"


# -- A06, A08, A09: the target from x⁰ -------------------------------------------------------------


@pytest.mark.parametrize("case", FROM_X0)
def test_a06_the_target_root_from_the_generators_x0(case: str) -> None:
    """A06 (steps 4–5): the target from `x⁰` returns `ref.target` within the state tolerance,
    signature exact (`SATURATED_LIQUID` is the total condenser's, which is not a split), its
    products and `spec_values`."""
    result, _, regimes = from_x0(case)
    record = REFERENCE["cases"][case]
    assert result.outcome == "CONVERGED"
    assert list(regimes.values()) == [s for s in record["signature"] if s != "SATURATED_LIQUID"]
    worst = deviation(case, result.state)
    assert max(worst.values()) <= 1.0, worst
    ports = products(SPECS[case], result.state)
    for port, key in (("distillate", "top_product"), ("bottoms", "bottom_product")):
        for actual, expected in zip(ports[port], record["target"][key], strict=True):
            assert abs(actual - float(expected)) <= FLOW_REL * abs(float(expected)) + FLOW_ABS
    values = spec_values(SPECS[case], result.state)
    for key, expected in record["spec_values"].items():
        target = float(expected)
        if key.endswith("duty"):
            assert abs(values[key] - target) <= Q_ABS, key
        else:
            assert abs(values[key] - target) <= FLOW_REL * abs(target) + FLOW_ABS, key


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Q-S02-WO2-2, measured: from x⁰ the target's attempts are 2P×7 BOUND_BLOCKED, (L,2P×6) "
        "BOUND_BLOCKED, (L,L,2P×5) LINEAR_SOLVE_FAILED rank 94 of 95 — not an edge-3 trigger"
    ),
)
def test_a06_m1_target_root_from_the_generators_x0() -> None:
    result, _, _ = from_x0("M1")
    assert result.outcome == "CONVERGED"


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(c, marks=pytest.mark.xfail(strict=True, reason="Q-S02-WO2-1 (A05)"))
        for c in CASES
    ],
)
def test_a06_the_target_root_through_solve_column(case: str) -> None:
    """A06 through §7 from `x_K`."""
    answer = solve_column(SPECS[case], PROVIDER)
    assert isinstance(answer, ColumnSolution) and answer.outcome == "CONVERGED"


@pytest.mark.parametrize("case", FROM_X0)
def test_a08_overall_closure(case: str) -> None:
    """A08: overall component and energy closure, within `n_rows·τ_kind`."""
    result, _, _ = from_x0(case)
    spec = SPECS[case]
    rows = len(compile_column(spec, PROVIDER).spec.equation_ids)
    closure = overall_closure(spec, PROVIDER, result.state)
    assert max(abs(e) for e in closure.components) <= rows * KIND_TOLERANCE["molar_flow"]
    assert abs(closure.energy) <= rows * KIND_TOLERANCE["heat_rate"]


@pytest.mark.parametrize("case", FROM_X0)
def test_a09_every_accepted_state_passes_section_8(case: str) -> None:
    result, _, regimes = from_x0(case)
    spec = SPECS[case]
    target = compile_column(spec, PROVIDER)
    assert acceptance_failures(spec, PROVIDER, target.spec, result.state, regimes) == ()


def test_a09_section_8_items_refuse_what_they_name() -> None:
    """A09: each §8 item refuses a state built to break it (M2's root, one thing changed)."""
    spec = SPECS["M2"]
    result, _, regimes = from_x0("M2")
    declared = compile_column(spec, PROVIDER).spec
    state = dict(result.state)

    def failures(changed: dict[str, float], regimes: dict[int, Any] = regimes) -> str:
        return " | ".join(
            acceptance_failures(spec, PROVIDER, declared, {**state, **changed}, regimes)
        )

    # item 1: a row off its tolerance.
    assert f"row {UNIT}:stage:1:spec:reflux_ratio = " in failures(
        {reflux_id(UNIT, "A"): state[reflux_id(UNIT, "A")] + 1e-3}
    )
    # item 2: the partial reboiler under bottoms_rate must be TWO_PHASE.
    assert "§8.2: reboiler stage 7" in failures({}, {**regimes, 7: "LIQUID"})
    # item 3: phi in (0, 1).
    assert "§8.3: phi = 1.0" in failures({reflux_fraction_id(UNIT): 1.0})
    # item 4: (2P above VAPOR) is a singular pair.
    assert "§8.4: stages (5, 6)" in failures({}, {**regimes, 6: "VAPOR"})
    # item 5: a pinned zero product flow carries +0.0.
    m3 = SPECS["M3"]
    assert singular_pairs({1: "LIQUID", 2: "TWO_PHASE"}) == ((1, 2),)
    assert singular_pairs({1: "VAPOR", 2: "TWO_PHASE", 3: "LIQUID"}) == ()
    lv = {j: "LIQUID" for j in m3.equilibrium_stages()}
    zeros = {vapor_id(UNIT, 1, c): -0.0 for c in "ABC"}
    found = acceptance_failures(
        m3, PROVIDER, compile_column(m3, PROVIDER).spec, {**from_x0("M3")[0].state, **zeros}, lv
    )
    assert any(f.startswith("§8.5: product distillate") for f in found)


# -- A07: the matched specification sets ---------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "variant"),
    [
        pytest.param(
            c,
            v,
            marks=pytest.mark.xfail(
                strict=True,
                reason="Q-S02-WO2-1: the variant's own §7.3 pre-solve fails (measured; DECISIONS)",
            ),
        )
        for c in ("M1", "M2")
        for v in REFERENCE["variants"][c]
        if v != "distillate_rate+bottoms_rate"
    ],
)
def test_a07_each_matched_set_returns_the_a06_root(case: str, variant: str) -> None:
    answer = solve_column(_variant(case, variant), PROVIDER)
    assert isinstance(answer, ColumnSolution) and answer.outcome == "CONVERGED"
    assert max(deviation(case, answer.state).values()) <= 1.0


# -- A10: the compiled Jacobian ------------------------------------------------------------------


def fd_errors(case: str, state: Any) -> dict[tuple[str, str], float]:
    """§10 A10: `D_r⁻¹ J D_x` against central differences at `h = 1e-6·max(D_x, |x|)` (R-516),
    per entry relative to `max(1, |exact|)`; the worst entry of each column, keyed
    `(column, row)`. `D_x(φ) = 1`."""
    target = compile_column(SPECS[case], PROVIDER)
    problem, compiled = target.spec, target.compiled
    context = target.context()
    x = np.array([state[name] for name in problem.variable_ids], dtype=np.float64)
    result = compiled.jacobian(x, context)
    assert result.status == "ok" and tuple(result.col_ids) == problem.variable_ids
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
        f_up, f_down = compiled.residual(up, context), compiled.residual(down, context)
        assert f_up.values is not None and f_down.values is not None
        fd = (np.asarray(f_up.values) - np.asarray(f_down.values)) / (2 * h)
        scaled_exact = exact[:, column] * d_x[column] / d_r
        error = np.abs(fd * d_x[column] / d_r - scaled_exact) / np.maximum(
            1.0, np.abs(scaled_exact)
        )
        row = int(error.argmax())
        errors[(problem.variable_ids[column], problem.equation_ids[row])] = float(error[row])
    return errors


@pytest.mark.parametrize("case", ["M2", "M1"])
@pytest.mark.parametrize("point", ["x_K", "root"])
def test_a10_the_compiled_jacobian(case: str, point: str) -> None:
    """A10 at `x_K` and at the root (`ref.target`, the generator's 50-digit root rounded to
    binary64): within 1e-6, and the floor under 1e-8 (measured: see `docs/S02_DECISIONS.md`)."""
    if point == "x_K":
        initial = profile_initial(SPECS[case], PROVIDER, DECLARATION_CONTEXT)
        state = dict(initial.state)  # type: ignore[union-attr]
    else:
        state = ref_state(case, "target")
    worst = max(fd_errors(case, state).values())
    assert worst <= FD_TOLERANCE
    assert worst <= FD_FLOOR, worst


# -- A13: edge 3 forced --------------------------------------------------------------------------


def _forced(monkeypatch: pytest.MonkeyPatch, case: str) -> tuple[Any, list[dict[str, float]]]:
    rebound: list[dict[str, float]] = []
    real = region_module.rebind

    def rebind(spec: Any, values: dict[str, float]) -> Any:
        rebound.append(dict(values))
        return real(spec, values)

    monkeypatch.setattr(solve_module, "eo_recovery_due", lambda outcome, budget: True)
    monkeypatch.setattr(region_module, "rebind", rebind)
    spec = SPECS[case]
    profile = [float(t) for t in REFERENCE["cases"][case]["initializer"]["profile"]]
    answer = solve_target(spec, PROVIDER, compile_column(spec, PROVIDER), ref_state(case), profile)
    return answer, rebound


def _dyadic(value: Fraction) -> bool:
    return 0 <= value <= 1 and value.denominator & (value.denominator - 1) == 0


@pytest.mark.parametrize("case", ["M1", "M2"])
def test_a13_forced_edge_3_from_x0(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    """A13: edge 3 forced from `x⁰`: `p⁰ = ref.continued` (Q abs 1e-2 W, rates rel 1e-6); every
    re-binding names exactly the continued parameters (the ratio rows' `RR*`, `BR*` never move);
    dyadic λ; the λ = 1 instance is the target's; the final root is A06's (M2: `same_root` SAME
    against the unforced root; M1, whose unforced target fails, within the state tolerance of
    `ref.target`)."""
    (result, failed, regimes), rebound = _forced(monkeypatch, case)
    spec = SPECS[case]
    profile = [float(t) for t in REFERENCE["cases"][case]["initializer"]["profile"]]
    expected = continuation(spec, profile).parameter_ids
    assert result.outcome == "CONVERGED" and failed is not None
    assert set(regimes.values()) == {"TWO_PHASE"}
    assert rebound and all(tuple(level) == expected for level in rebound)
    by_id = {s.parameter: s for s in slots(spec, profile) if s.parameter}
    for name, value in rebound[0].items():
        record = REFERENCE["cases"][case]["continued"][str(by_id[name].stage)]
        tolerance = Q_ABS if record["kind"] == "Q" else FLOW_REL * abs(float(record["p0"]))
        assert abs(value - float(record["p0"])) <= tolerance, name
    record = result.homotopy
    assert record is not None and record.lambda_reached == 1
    assert all(_dyadic(trial.lambda_value) for trial in record.trials)
    assert result.branch_provenance[len(failed.branch_provenance)]["core"] == "homotopy"
    compiled = compile_column(spec, PROVIDER).compiled.metadata
    at_one = result.contexts[0].evaluation_context
    assert (at_one.model_version, at_one.constants_sha256) == (
        compiled.model_version,
        compiled.constants_sha256,
    )
    assert max(deviation(case, result.state).values()) <= 1.0
    if case == "M2":
        unforced = from_x0("M2")[0]
        assert unforced.root_fingerprint is not None and result.root_fingerprint is not None
        target = compile_column(spec, PROVIDER).spec
        assert (
            same_root(
                unforced.root_fingerprint,
                unforced.state,
                result.root_fingerprint,
                result.state,
                Scaling.from_spec(target).column,
                target.variable_ids,
            )
            == "SAME"
        )


# -- A15: reproducibility ------------------------------------------------------------------------


def _records(result: RegionResult, trace: Trace) -> list[str]:
    return [
        repr([dict(item) for item in result.branch_provenance]),
        repr(result.signatures),
        repr(result.root_fingerprint),
        *(repr(event.as_document()) for event in trace.events),
    ]


@pytest.mark.parametrize("case", ["M1", "M2"])
def test_a15_solved_twice_is_identical(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    """A15: §7 twice (from `x_K`: the typed pre-solve answer) and steps 4–5 twice from `x⁰`
    (M1 with edge 3 forced, since its unforced target fails): identical `state_sha256`, states
    and records."""
    spec = SPECS[case]
    first, second = solve_column(spec, PROVIDER), solve_column(spec, PROVIDER)
    assert isinstance(first, ColumnSolution) and isinstance(second, ColumnSolution)
    assert (first.presolve_summary, first.opening_sha256) == (
        second.presolve_summary,
        second.opening_sha256,
    )
    if case == "M1":
        monkeypatch.setattr(solve_module, "eo_recovery_due", lambda outcome, budget: True)
    profile = [float(t) for t in REFERENCE["cases"][case]["initializer"]["profile"]]
    runs = []
    for _ in range(2):
        trace = Trace()
        result, _, _ = solve_target(
            spec, PROVIDER, compile_column(spec, PROVIDER), ref_state(case), profile, trace=trace
        )
        assert result.outcome == "CONVERGED"
        runs.append((result, trace))
    (a, a_trace), (b, b_trace) = runs
    assert a.state == b.state and len(a_trace) > 0
    assert _records(a, a_trace) == _records(b, b_trace)


# -- A17: phi's kind and scale -------------------------------------------------------------------


def test_a17_phi_is_dimensionless_with_scale_one() -> None:
    """A17: M2's `phi` is `dimensionless`; `Scaling.from_spec` builds for M2 and V-M2's two
    sets with `column[phi] == 1.0` and every other entry its kind's nominal; the kind is in
    neither tolerance table."""
    from openflowsheet.orchestrator.region import KIND_TOLERANCE as REGION_TOLERANCE

    for spec in (
        SPECS["M2"],
        _variant("M2", "duty+duty"),
        _variant("M2", "distillate_rate+boilup_ratio"),
    ):
        problem = compile_column(spec, PROVIDER).spec
        assert problem.variable_kinds[reflux_fraction_id(UNIT)] == "dimensionless"
        scaling = Scaling.from_spec(problem)
        assert scaling.column[reflux_fraction_id(UNIT)] == 1.0
        for name, kind in problem.variable_kinds.items():
            assert scaling.column[name] == REGISTERED_NOMINALS[kind]
        for name, kind in problem.row_kinds.items():
            assert scaling.row[name] == REGISTERED_NOMINALS[kind]
    assert "dimensionless" not in REGION_TOLERANCE
    from openflowsheet.verify import checks

    tables = [v for v in vars(checks).values() if isinstance(v, dict) and "molar_flow" in v]
    assert all("dimensionless" not in table for table in tables)


def test_a17_a_dimensionless_row_is_refused_by_name() -> None:
    problem: ProblemSpec = compile_column(SPECS["M2"], PROVIDER).spec
    row = problem.equation_ids[0]
    kinds = {**problem.row_kinds, row: "dimensionless"}
    with pytest.raises(ScaleUnavailableError, match=row.replace(".", r"\.")):
        Scaling.from_kinds(
            variable_ids=problem.variable_ids,
            equation_ids=problem.equation_ids,
            variable_kinds=problem.variable_kinds,
            row_kinds=kinds,  # type: ignore[arg-type]
        )


# -- A18: the stage-1 label ----------------------------------------------------------------------


def test_a18_the_stage_1_labels() -> None:
    """A18: M1's stage-1 label is `T_feed`, M4's `T_bottom`, M3's `T_top`, M2's stage-2 `T_c`;
    every stage's label is a declared column."""
    from openflowsheet.models import temperature_id
    from openflowsheet.models.syn001.cascade import inlet_stream

    assert label_source(SPECS["M1"], 1) == temperature_id(inlet_stream(UNIT, "feed"))
    assert label_source(SPECS["M4"], 1) == temperature_id(inlet_stream(UNIT, "bottom"))
    assert label_source(SPECS["M3"], 1) == temperature_id(inlet_stream(UNIT, "top"))
    assert label_source(SPECS["M2"], 2) == stage_temperature_id(UNIT, 1)
    for case in CASES:
        spec = SPECS[case]
        columns = set(declared_rows(spec, PROVIDER, DECLARATION_CONTEXT).variable_ids)
        for stage in spec.equilibrium_stages():
            form = regime_form(spec, stage, "ZERO_FLOW")
            assert form.label == (
                label_row_id(UNIT, stage),
                stage_temperature_id(UNIT, stage),
                label_source(spec, stage),
            )
            assert label_source(spec, stage) in columns


@pytest.mark.parametrize("case", CASES)
def test_a18_the_agreement_check_accepts_every_form(case: str) -> None:
    """A18: `splits.check_agreement`'s zero-flow-form branch accepts every stage's form."""
    target = compile_column(SPECS[case], PROVIDER)
    metadata = target.compiled.metadata
    # Each stage's rows are its split's; the condenser's and the inlets' rows are the column's.
    row_units = {
        row: (
            f"{UNIT}.stage.{row.split(':')[2]}"
            if row.startswith(f"{UNIT}:stage:")
            and f"{UNIT}.stage.{row.split(':')[2]}" in target.forms
            else UNIT
        )
        for row in target.spec.equation_ids
    }
    declaration = trace_declaration(
        target.spec,
        model_version=metadata.model_version,
        constants_sha256=metadata.constants_sha256,
        specification_ids={},
        row_units=row_units,
    )
    check_agreement((), target.splits, target.spec, row_units, declaration, forms=target.forms)


def test_a18_m1_stage_1_zero_flow_label_residual() -> None:
    """A18: on M1 at `x_K` with stage 1 ZERO_FLOW and the rest TWO_PHASE, the system is square
    and the label row's residual is `T_1 − T_feed`, one IEEE subtraction."""
    from openflowsheet.models import temperature_id
    from openflowsheet.models.syn001.cascade import inlet_stream
    from openflowsheet.models.syn001.column_solve import system_residuals

    spec = SPECS["M1"]
    state = dict(profile_initial(spec, PROVIDER, DECLARATION_CONTEXT).state)  # type: ignore[union-attr]
    declared = compile_column(spec, PROVIDER).spec
    regimes = {j: "TWO_PHASE" for j in spec.equilibrium_stages()} | {1: "ZERO_FLOW"}
    residuals, pinned = system_residuals(spec, declared, state, regimes)  # type: ignore[arg-type]
    assert len(residuals) == len(declared.variable_ids) - len(pinned)
    t_feed = temperature_id(inlet_stream(UNIT, "feed"))
    assert residuals[label_row_id(UNIT, 1)] == state[stage_temperature_id(UNIT, 1)] - state[t_feed]


def test_a18_a_column_without_inlets_is_refused_before_any_form() -> None:
    from dataclasses import replace

    spec = replace(SPECS["M1"], sides=())
    refused = validate(spec, PROVIDER, DECLARATION_CONTEXT)
    assert refused is not None and refused.cause == "invalid_spec(no_feed)"
    with pytest.raises(ValueError, match="no label"):
        label_source(spec, 1)


# -- A19: the total condenser's accumulation and sign --------------------------------------------


def test_a19_condenser_accumulation_and_sign() -> None:
    spec = SPECS["M2"]
    problem = compile_column(spec, PROVIDER).spec
    rows = declared_rows(spec, PROVIDER, DECLARATION_CONTEXT)
    accumulation = compile_column(spec, PROVIDER).compiled.metadata.row_accumulation
    families = {e.equation_id: e.origin for e in rows.equations}
    column_rows = [row for row, source in families.items() if "COL-" in source]
    assert column_rows
    for row in column_rows:
        holdup = families[row].endswith(("COL-tc-bal", "COL-tc-energy"))
        assert accumulation[row] == ("holdup_balance" if holdup else "algebraic"), families[row]
    held = [row for row in column_rows if accumulation[row] == "holdup_balance"]
    assert len(held) == 4  # bal_A, bal_B, bal_C and energy
    state = ref_state("M2", "target")
    trial = {
        **{vapor_id(UNIT, 2, c): v for c, v in zip("ABC", (0.5, 0.375, 0.25), strict=True)},
        **{reflux_id(UNIT, c): v for c, v in zip("ABC", (0.125, 0.0625, 0.03125), strict=True)},
        **{distillate_id(UNIT, c): v for c, v in zip("ABC", (0.25, 0.0625, 0.03125), strict=True)},
    }
    values = row_values(problem, {**state, **trial})
    assert [values[stage_row_id(UNIT, 1, "bal", c)] for c in "ABC"] == [0.125, 0.25, 0.1875]
    zeros = {name: 0.0 for name in trial} | {stage_duty_id(UNIT, 1): 1000.0}
    zeros[stage_pressure_id(UNIT, 1)] = spec.pressures[0]
    assert row_values(problem, {**state, **zeros})[stage_row_id(UNIT, 1, "energy")] == 1000.0
