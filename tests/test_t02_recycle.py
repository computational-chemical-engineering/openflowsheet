"""T02 §5: the safeguarded Anderson recycle, on the manufactured maps Frank required.

Every expectation comes from `benchmarks/t02/reference_values.yaml`, which Fable's generator emits
from closed forms and from the registered policy restated at 40 digits (`accelerate` in
`docs/derivations/scripts/t02_reference.py`). The maps are built here from that file's matrices,
starts and scales — the reference is the fixture, as K03's synthetic seeds were.

Why these cases exist at all: SYN-001's recycle has a real, non-negative spectrum with `ρ = r`
exactly, so it cannot tell a good accelerator from a bad one. Each case below breaks one comfort —
alternation (REC-01), divergence into a negative flow (REC-02), a spectrum no damping helps
(REC-03), rotation (REC-04), non-normal transient growth and a second fixed point (REC-05), a
constant residual (RCY-STALL), a coefficient of a million (RCY-COEF), scaling (SCL-1), truncation
(RCY-TRUNC) and a loop no single edge breaks (NEST-1).

Assertion ids are the specification's §10. The merge-edge halves of A14–A17 and A32 run the EO
region and live with it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
import yaml

from openflowsheet.numerics.anderson import RecyclePolicy, RecycleResult, solve_recycle
from openflowsheet.numerics.newton import Evaluation, Problem
from openflowsheet.numerics.scaling import Scaling

REPO_ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 3.1e-8
REC = ("REC-01", "REC-02", "REC-03", "REC-04", "REC-05")


@pytest.fixture(scope="module")
def ref() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t02" / "reference_values.yaml").read_text()
    )
    return loaded


def floats(values: Sequence[Any]) -> npt.NDArray[np.float64]:
    return np.array([float(value) for value in values], dtype=np.float64)


def recycle_problem(
    g_map: Callable[[npt.NDArray[np.float64]], npt.NDArray[np.float64]],
    scale: Sequence[float],
    *,
    tolerance: Sequence[float] | None = None,
    bounded: bool = True,
) -> Problem:
    """`R(t) = G(t) − t` as a K03 `Problem`. A bounded map refuses a negative flow (ADR 0001 D3)."""
    n = len(scale)
    ids = tuple(f"t{i}" for i in range(n))
    rows = tuple(f"R{i}" for i in range(n))
    tol = tolerance if tolerance is not None else [TOLERANCE] * n

    def residual(t: npt.NDArray[np.float64]) -> Evaluation:
        if bounded and bool(np.any(t < 0.0)):
            return Evaluation(status="invalid_trial_state", message="negative component flow")
        return Evaluation(status="ok", values=tuple(float(v) for v in g_map(t) - t))

    return Problem(
        variable_ids=ids,
        row_ids=rows,
        residual=residual,
        jacobian=lambda t: np.zeros((n, n)),
        scaling=Scaling(
            column=dict(zip(ids, scale, strict=True)), row=dict(zip(rows, scale, strict=True))
        ),
        row_tolerance=dict(zip(rows, tol, strict=True)),
        lower_bounds=dict.fromkeys(ids, 0.0) if bounded else {},
    )


def manufactured(
    case: Mapping[str, Any], gamma: float
) -> tuple[Callable[[npt.NDArray[np.float64]], npt.NDArray[np.float64]], npt.NDArray[np.float64]]:
    """The addendum's maps, `G(t) = t* + A (t − t*) + γ q(t − t*) / S`.

    `q(d) = (d₂d₃, d₃d₁, d₁d₂)`.
    """
    a = np.array([floats(row) for row in case["A"]])
    t_star = floats(case["t_star"])
    s = float(case["scale_mol_per_s"])

    def g(t: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        d = t - t_star
        return t_star + a @ d + gamma * np.array([d[1] * d[2], d[2] * d[0], d[0] * d[1]]) / s

    start = case["start"]
    t0 = floats(start) if isinstance(start, list) else float(start) * t_star
    return g, t0


def run_rec(
    ref: Mapping[str, Any], name: str, gamma: float, **policy: Any
) -> tuple[RecycleResult, Mapping[str, Any]]:
    case = ref["cases_rec"][name]
    g, t0 = manufactured(case, gamma)
    scale = [float(case["scale_mol_per_s"])] * 3
    return solve_recycle(recycle_problem(g, scale), t0, policy=RecyclePolicy(**policy)), case


def trajectory_agrees(
    found: Sequence[float],
    registered: Sequence[Any],
    *,
    relative: float,
    floor: float = 0.0,
    through: int | None = None,
) -> list[str]:
    """Where the trajectory departs from the twin's, compared while the value exceeds `floor`."""
    off = []
    limit = len(registered) if through is None else min(through + 1, len(registered))
    for k in range(limit):
        expected = float(registered[k])
        if abs(expected) <= floor:
            continue
        if abs(found[k] - expected) > relative * abs(expected):
            off.append(f"k={k}: {found[k]!r} vs {expected!r}")
    return off


# ------------------------------------------------------------------ A07: the linear variants


@pytest.mark.parametrize("name", REC)
def test_a07_linear_variants_terminate_at_exactly_iteration_4(
    ref: dict[str, Any], name: str
) -> None:
    """Full-memory Anderson on a linear map is GMRES (Walker and Ni, 2011), so it terminates at
    the Krylov grade plus one. Every registered linear variant has grade 3: exactly 4.

    Iterates 0–3 to `1e-9` relative: the measured floor is `4.4e-16`, six decades under it, and a
    wrong column sign, a type-I update, an unscaled least squares or a Tikhonov term moves iterate
    2 by at least `1e-2`.
    """
    result, case = run_rec(ref, name, 0.0)
    registered = case["variants"]["gamma=0"]["policy_simulation_anderson"]
    assert case["variants"]["gamma=0"]["krylov_grade"] == 3
    assert result.outcome == "CONVERGED"
    assert result.iterations == 4 == registered["iterations"]
    assert not trajectory_agrees(
        result.residual_inf_scaled, registered["residual_inf_scaled"], relative=1e-9, through=3
    )
    assert result.restarts == () and result.columns_dropped_condition == 0
    assert result.columns_dropped_coefficient == 0
    assert result.bound_landings == 0 and result.invalid_trials == 0
    assert float(np.max(np.abs(result.x - floats(case["t_star"])))) <= 1e-5


# ----------------------------------------------------------- A08: the variants with the tail


@pytest.mark.parametrize("name", REC)
def test_a08_nonlinear_variants_follow_the_twin(ref: dict[str, Any], name: str) -> None:
    """Nothing terminates on a nonlinear map; what is registered is the twin's trajectory through
    iterate 5 while the residual exceeds `1e-6`, the count within `[ref, ref + 2]`, and the root."""
    result, case = run_rec(ref, name, 0.1)
    registered = case["variants"]["gamma=0.1"]["policy_simulation_anderson"]
    assert result.outcome == "CONVERGED"
    assert registered["iterations"] <= result.iterations <= registered["iterations"] + 2
    assert not trajectory_agrees(
        result.residual_inf_scaled,
        registered["residual_inf_scaled"],
        relative=1e-8,
        floor=1e-6,
        through=5,
    )
    t_star = floats(case["t_star"])
    if name == "REC-05":
        # The recycle multiple-root case (spec §15.1): from 1.1 t* the iteration reaches a second
        # genuine fixed point, not the designed one. The addendum's own table got this wrong by
        # checking the residual and never which root; this assertion checks the root.
        s1 = floats(registered["final_t"])
        assert float(np.max(np.abs(result.x - s1))) <= 1e-4
        assert float(np.max(np.abs(result.x - t_star))) > 1.0
    else:
        assert float(np.max(np.abs(result.x - t_star))) <= 1e-5


# ------------------------------------------------ A09–A12: substitution, damping, detection


def test_a09_rec_01_substitution_detects_oscillation_and_damps(ref: dict[str, Any]) -> None:
    result, case = run_rec(ref, "REC-01", 0.0, depth_max=0)
    assert result.oscillation_detected_at == 3
    assert [event.beta_substitution for event in result.accelerations[:3]] == [1.0, 1.0, 1.0]
    assert all(event.beta_substitution == 0.5 for event in result.accelerations[3:])
    assert result.outcome == "CONVERGED" and result.iterations <= 60
    assert (
        result.iterations
        == case["variants"]["gamma=0"]["policy_simulation_substitution_depth0"]["iterations"]
    )


def test_a10_rec_02_lands_on_the_bound_exactly_and_is_rescued_by_damping(
    ref: dict[str, Any],
) -> None:
    """ADR 0001 D3.5: a tear flow is bounded below by 0, and a bound landing is exact (`+0.0`).

    The unbounded second substitution iterate has `t_A = −0.125`; the bound shortens the step to
    `α_max = 14/15` and lands the first component on `+0.0` — before the evaluator is ever asked,
    so there is no invalid trial. Without the damping response the first component cycles between
    0 and 2.5 on the bound for ever (measured by the specification).
    """
    result, _ = run_rec(ref, "REC-02", 0.0, depth_max=0)
    substitution = solve_recycle(
        recycle_problem(*_rec_map(ref, "REC-02", 0.0)[:1], [3.0] * 3),
        _rec_map(ref, "REC-02", 0.0)[1],
        policy=RecyclePolicy(depth_max=0),
        keep_trajectory=True,
    )
    second = substitution.trajectory[2]
    assert second[0] == 0.0 and np.copysign(1.0, second[0]) == 1.0, "+0.0, not -0.0"
    assert second[1] == pytest.approx(1.7333333333333333, rel=1e-15)
    assert second[2] == pytest.approx(2.924, rel=1e-15)
    assert result.oscillation_detected_at == 3
    assert result.outcome == "CONVERGED" and result.iterations <= 60
    assert result.invalid_trials == 0

    for gamma in (0.0, 0.1):
        accelerated, _ = run_rec(ref, "REC-02", gamma)
        assert accelerated.bound_landings == 0 and accelerated.invalid_trials == 0


def _rec_map(
    ref: Mapping[str, Any], name: str, gamma: float
) -> tuple[Callable[[npt.NDArray[np.float64]], npt.NDArray[np.float64]], npt.NDArray[np.float64]]:
    return manufactured(ref["cases_rec"][name], gamma)


def test_a11_rec_03_damping_cannot_help_and_the_budget_says_so(ref: dict[str, Any]) -> None:
    """`ω* = 1`, rate 0.95: no single damping factor improves on plain substitution, and 200
    iterations leave `0.65 · 0.95²⁰⁰ = 2.3e-5` above the scaled tolerance. Acceleration is the
    only remedy, which is the case's reason to exist."""
    case = ref["cases_rec"]["REC-03"]
    assert float(case["best_damping"]["omega_star"]) == 1.0
    assert float(case["best_damping"]["rate"]) == pytest.approx(0.95, rel=1e-15)

    result, _ = run_rec(ref, "REC-03", 0.0, depth_max=0)
    assert result.outcome == "BUDGET_EXHAUSTED"
    assert result.iterations == 200
    assert result.residual_inf_scaled[-1] > TOLERANCE / 3.0

    assert run_rec(ref, "REC-03", 0.0)[0].iterations == 4
    assert run_rec(ref, "REC-03", 0.1)[0].iterations <= 9


def test_a12_rec_04_rotation_is_invisible_to_the_sign_detector(ref: dict[str, Any]) -> None:
    result, _ = run_rec(ref, "REC-04", 0.0, depth_max=0)
    assert result.iterations == 200
    assert result.oscillation_detected_at is None
    assert not any(event.oscillation_flag for event in result.accelerations)
    assert run_rec(ref, "REC-04", 0.0)[0].iterations == 4
    assert run_rec(ref, "REC-04", 0.1)[0].iterations <= 9


# ------------------------------------------- A13–A14: REC-05, growth, and the second root


def test_a13_rec_05_linear_grows_and_no_safeguard_fires(ref: dict[str, Any]) -> None:
    """The assertion that a growth-based safeguard is absent: the residual rises above its start
    on the way to terminating at iteration 4, and nothing restarts, drops or closes."""
    result, case = run_rec(ref, "REC-05", 0.0)
    norms = result.residual_inf_scaled
    assert norms[1] > norms[0] and norms[2] > norms[0]
    assert result.residual_increases >= 1
    assert result.restarts == () and result.stagnation_closures == ()
    assert result.columns_dropped_condition == result.columns_dropped_coefficient == 0
    assert result.iterations == 4
    registered = case["variants"]["gamma=0"]["policy_simulation_anderson"]["residual_inf_scaled"]
    assert not trajectory_agrees(norms, registered, relative=1e-9, through=3)


def test_a14_rec_05_with_the_tail_stagnates_under_substitution(ref: dict[str, Any]) -> None:
    """Locally contractive (ρ = 0.5) and still no convergence under substitution: the windows
    close at 10, 15 and 20, the first two restart, the third gives up."""
    result, _ = run_rec(ref, "REC-05", 0.1, depth_max=0)
    assert result.outcome == "RECYCLE_STAGNATION"
    assert result.iterations == 20
    assert result.stagnation_closures == (10, 15, 20)
    assert len(result.restarts) == 2
    assert [event.count for event in result.restarts] == [1, 2]
    assert all(event.reason == "stagnation" for event in result.restarts)


# ------------------------------------------------------------------- A15–A17: the stalls


def test_a15_rcy_div_the_stagnation_rule_is_the_divergence_rule(ref: dict[str, Any]) -> None:
    case = ref["cases_auxiliary"]["RCY-DIV"]
    a = np.array([floats(row) for row in case["A"]])
    t_star = floats(ref["cases_rec"]["REC-01"]["t_star"])

    def g(t: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return t_star + a @ (t - t_star)

    problem = recycle_problem(g, [3.0] * 3, bounded=False)
    result = solve_recycle(problem, floats(case["start"]), policy=RecyclePolicy(depth_max=0))
    assert result.outcome == "RECYCLE_STAGNATION"
    assert result.iterations == 16
    assert result.stagnation_closures == (6, 11, 16)
    assert result.residual_inf_scaled[0] == pytest.approx(0.4, rel=1e-12)
    for k in range(1, 17):
        assert result.residual_inf_scaled[k] == pytest.approx(0.25 * 1.5**k / 3.0, rel=1e-12), k

    accelerated = solve_recycle(problem, floats(case["start"]))
    assert accelerated.outcome == "CONVERGED" and accelerated.iterations == 4


def test_a16_rcy_stall_every_column_is_dropped_for_condition(ref: dict[str, Any]) -> None:
    """A constant residual has no root, and every difference column is exactly zero: 27 drops, no
    Anderson step ever taken, two restarts, then `RECYCLE_STAGNATION`."""
    problem = recycle_problem(lambda t: t + 1.0, [3.0] * 3, bounded=False)
    result = solve_recycle(problem, np.zeros(3))
    registered = ref["cases_auxiliary"]["RCY-STALL"]["anderson"]
    assert result.outcome == "RECYCLE_STAGNATION" == registered["outcome"]
    assert result.iterations == 15
    assert result.stagnation_closures == (5, 10, 15)
    assert len(result.restarts) == 2
    assert (
        result.columns_dropped_condition == 27 == registered["events"]["column_dropped_condition"]
    )
    assert result.anderson_steps == 0


def test_a17_rcy_coef_refuses_a_coefficient_of_a_million(ref: dict[str, Any]) -> None:
    """The secant coefficient at k = 1 is `(1 + 1e-6)/1e-6 = 1 000 001`, past the 1e4 bound: it is
    refused, recorded on the drop, and the step is plain. Twelve such refusals, then the give-up."""
    problem = recycle_problem(lambda t: t + 1.0 + 1e-6 * t, [1.0], bounded=False)
    result = solve_recycle(problem, np.zeros(1))
    registered = ref["cases_auxiliary"]["RCY-COEF"]
    first = result.accelerations[1]
    assert first.iteration == 1 and first.depth_used == 0
    assert first.columns_dropped_coefficient == 1
    assert first.gamma_inf is None, "a plain step used no coefficient"
    reason, refused = first.dropped[0]
    assert reason == "coefficient"
    assert refused == pytest.approx(float(registered["secant_coefficient_at_k1"]), rel=1e-6)
    assert result.columns_dropped_coefficient == 12
    assert result.stagnation_closures == (5, 10, 15)
    assert result.outcome == "RECYCLE_STAGNATION"


# ------------------------------------------------------------------ A18–A20: the rest


def test_a18_nest_1_one_simultaneous_tear_vector(ref: dict[str, Any]) -> None:
    """A loop no single edge breaks, torn at `[s4, s5]` and converged as one vector — never a loop
    inside a loop. The alternate tear `{s1, s5}` reaches a different vector and the same product."""
    feed, split, recycle = 1.0, 0.5, 0.8

    def streams(s4: float, s5: float) -> dict[str, float]:
        s1 = feed + s4
        total = s1 + s5
        s2 = (1.0 - split) * total
        return {
            "s1": s1,
            "s2": s2,
            "s3": (1.0 - recycle) * s2,
            "s4": split * total,
            "s5": recycle * s2,
        }

    def rule_map(t: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        out = streams(float(t[0]), float(t[1]))
        return np.array([out["s4"], out["s5"]])

    def alternate_map(t: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        s1, s5 = float(t[0]), float(t[1])
        total = s1 + s5
        return np.array([feed + split * total, recycle * (1.0 - split) * total])

    case = ref["cases_auxiliary"]["NEST-1"]
    assert case["tear"]["tear_streams"] == ["s4", "s5"]
    assert case["tear"]["single_edge_feedback_set_exists"] is False

    result = solve_recycle(recycle_problem(rule_map, [1.0, 1.0]), np.zeros(2))
    assert result.outcome == "CONVERGED" and result.iterations == 2
    assert np.allclose(result.x, floats(case["fixed_point_s4_s5"]), atol=1e-7)
    product = streams(float(result.x[0]), float(result.x[1]))["s3"]
    assert product == pytest.approx(1.0, abs=1e-7)

    alternate = solve_recycle(recycle_problem(alternate_map, [1.0, 1.0]), np.zeros(2))
    assert alternate.outcome == "CONVERGED"
    assert np.allclose(alternate.x, [6.0, 4.0], atol=1e-7)
    s1, s5 = float(alternate.x[0]), float(alternate.x[1])
    assert (1.0 - recycle) * (1.0 - split) * (s1 + s5) == pytest.approx(product, abs=1e-7)


def test_a19_scl_1_the_least_squares_is_taken_in_scaled_coordinates(ref: dict[str, Any]) -> None:
    case = ref["cases_auxiliary"]["SCL-1"]
    g, t0 = _rec_map(ref, "REC-03", 0.0)
    scale = [float(v) for v in case["scale"]]
    tolerance = [float(v) for v in case["tolerance_mol_per_s"]]
    result = solve_recycle(recycle_problem(g, scale, tolerance=tolerance), t0)
    registered = case["anderson"]
    assert result.iterations == 4
    assert not trajectory_agrees(
        result.residual_inf_scaled, registered["residual_inf_scaled"], relative=1e-9, through=3
    )
    unscaled, _ = run_rec(ref, "REC-03", 0.0)
    assert abs(result.residual_inf_scaled[2] - unscaled.residual_inf_scaled[2]) > 1e-2
    assert max(event.kappa_2 or 0.0 for event in result.accelerations) <= 1e7
    assert max(event.gamma_inf or 0.0 for event in result.accelerations) <= 1e3


def test_a20_rcy_trunc_a_sliding_window_loses_finite_termination(ref: dict[str, Any]) -> None:
    result, _ = run_rec(ref, "REC-01", 0.0, depth_max=2)
    registered = ref["cases_auxiliary"]["RCY-TRUNC"]["anderson"]
    assert 10 <= result.iterations <= 20 and result.iterations > 4
    assert not trajectory_agrees(
        result.residual_inf_scaled,
        registered["residual_inf_scaled"],
        relative=1e-8,
        floor=1e-6,
        through=5,
    )
    assert all(event.depth_used <= 2 for event in result.accelerations)
    assert result.oscillation_detected_at == 7
    assert all(event.beta_substitution == 1.0 for event in result.accelerations if not event.plain)


# ------------------------------------------------------------- the trace fields (A33, part)


@pytest.mark.parametrize("name", REC)
def test_a33_acceleration_events_are_well_formed(ref: dict[str, Any], name: str) -> None:
    for gamma in (0.0, 0.1):
        result, _ = run_rec(ref, name, gamma)
        for event in result.accelerations:
            assert event.depth_used <= min(5, 3)
            assert event.beta_substitution in (1.0, 0.5)
            assert (event.kappa_2 is not None) == (event.depth_used >= 1)
            assert (event.gamma_inf is not None) == (event.depth_used >= 1)
            for value in (event.kappa_2, event.gamma_inf):
                assert value is None or np.isfinite(value)


# ============================================ SYN-001 under Anderson (A04–A06): real units


def _syn001(case_id: str) -> tuple[Any, npt.NDArray[np.float64]]:
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.thermo.syn001 import Syn001Provider

    variants = {
        entry["case_id"]: entry
        for entry in yaml.safe_load(
            (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
        )["variants"]
    }
    entry = variants[case_id]
    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
        split_fraction=float(entry["r"]),
        flash_temperature=float(entry["T_flash_K"]),
        heater_temperature=float(entry["T_heater_K"]),
        pressure=float(entry["P_Pa"]),
    )
    return flowsheet, floats(entry["recycle_mol_per_s"])


def _anderson_policy() -> Any:
    from openflowsheet.orchestrator.trace import RecyclePolicy as Recycle
    from openflowsheet.orchestrator.trace import SolvePolicy

    return SolvePolicy(
        policy_id="T02-anderson",
        residual_tolerances={},
        scales={},
        recycle=Recycle(method="anderson"),
    )


@pytest.mark.parametrize(
    ("case_id", "iterations"),
    [
        ("SYN-001-nominal", 2),
        ("SYN-001-high-recycle", 2),
        ("SYN-001-all-liquid-310K", 2),
        ("SYN-001-once-through", 0),
        ("SYN-001-all-vapor-420K", 0),
    ],
)
def test_a04_syn001_under_anderson_from_the_initializer(case_id: str, iterations: int) -> None:
    """On the ray through t* the map is affine exactly (K03 §10.2), so Anderson(1)'s second iterate
    is t*: exactly 2 iterations where the loop is live, 0 where it is dormant, and no restart, no
    drop, no landing and no invalid trial anywhere."""
    from openflowsheet.orchestrator.tear import solve_tear

    flowsheet, t_star = _syn001(case_id)
    result, trace = solve_tear(flowsheet, policy=_anderson_policy())
    assert result.outcome == "CONVERGED"
    assert result.iterations == iterations
    assert float(np.max(np.abs(result.x - t_star))) <= TOLERANCE
    assert trace.of_kind("trial") == (), "no rejected trial of any kind"
    assert result.attempts == 1


@pytest.mark.parametrize(
    "case_id", ["SYN-001-nominal", "SYN-001-high-recycle", "SYN-001-once-through"]
)
def test_a05_syn001_under_anderson_from_off_a(case_id: str) -> None:
    """OFF-A: off the ray, all components non-zero, the flash two-phase at the start — the
    genuinely nonlinear map, converged in one attempt with no invalid trial."""
    from openflowsheet.orchestrator.tear import solve_tear

    flowsheet, t_star = _syn001(case_id)
    result, trace = solve_tear(
        flowsheet, policy=_anderson_policy(), initial_recycle=(0.1, 0.8, 1.2)
    )
    assert result.outcome == "CONVERGED"
    assert float(np.max(np.abs(result.x - t_star))) <= TOLERANCE
    assert result.iterations <= 15
    assert result.attempts == 1
    assert not [
        event for event in trace.of_kind("trial") if event.rejection_reason == "invalid_trial"
    ]


def test_a06_syn001_under_anderson_from_off_b_changes_phase_through_k03s_contract() -> None:
    """OFF-B: the flash all-liquid at the start while the answer is two-phase. The attempt
    contract is K03's, unchanged, for either core: attempt 1 frozen LIQUID, the wall, a restart
    into TWO_PHASE. And the mixer refuses at least one trial, named, on the trace."""
    from openflowsheet.orchestrator.tear import solve_tear

    flowsheet, t_star = _syn001("SYN-001-nominal")
    result, trace = solve_tear(
        flowsheet, policy=_anderson_policy(), initial_recycle=(0.05, 0.1, 4.0)
    )
    assert result.outcome == "CONVERGED"
    assert float(np.max(np.abs(result.x - t_star))) <= TOLERANCE
    assert result.attempts == 2
    assert [signature[0][1] for signature in result.signatures] == ["LIQUID", "TWO_PHASE"]
    invalid = [
        event for event in trace.of_kind("trial") if event.rejection_reason == "invalid_trial"
    ]
    assert invalid and all("U-MIX" in event.message for event in invalid)
    assert result.iterations <= 40
    assert len(trace.of_kind("attempt_opened")) == len(trace.of_kind("attempt_closed")) == 2
