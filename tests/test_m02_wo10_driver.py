"""M02 WO-10: the outer coupling driver with the inner solve and the experiments stubbed (design
note §4.2–§4.3; ADR 0034 D2, D3; G8 (f), driver level).

- G8 (f) as amended (§14.5 D5, R-305), f1–f5, against an independent replica of §4.3
  (`tests/m02_broyden_replica.py`): affine maps F(w) = w* + G (w − w*) with w* = (0.25, 0 K), the
  stand-in's fixed point — G = diag(0.5, 0) converges (f1); G = diag(1.8, 0) (non-contractive)
  converges at k = 3 with ρ rising at k = 2 inside the 2n window (f2), and from ΔT̂ = 0 with the
  rise on substitution's own step (f3); a scripted residual resets at k = 2n and ends
  `no_decrease` at k = 2n + 1, and does not reset on a rise at k = 2 (f4); F(w) = w + (1, 0) (no
  fixed point) ends `COUPLING_NOT_CONVERGED` (f5).
- §4.3: the first step from B₀ = −I is successive substitution; steps are clipped to the bounds;
  `max_outer` accepted iterates at most; an inner failure or a deterministic refusal halves the
  step towards its base at most three times; an inner failure at k = 0 passes its outcome
  through; a transient answer ends `EVALUATION_ERROR` `external_<status>(<unit>)`.
- §4.2: ρ and the residual's components as the record carries them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest
from m02_broyden_replica import Replica, replicate

from openflowsheet.adapters import variants
from openflowsheet.orchestrator.coupling import (
    BACKTRACKS,
    CouplingBlock,
    CouplingRun,
    ExternalAnswer,
    InnerSolve,
    UnitInlet,
    couple,
)

BLOCK = CouplingBlock.from_document(variants.registered_variant("standin-x025-v1").coupling)
W_STAR = (0.25, 0.0)
#: A reactor inlet at the loop's scale (H2/N2 = 3), mol/s, K, Pa.
INLET = UnitInlet(n=(3.0, 1.0, 0.1, 0.1, 0.15), T=673.15, P=1.0e7, n_key=1.0)


@dataclass
class Stub:
    """An inner solve that always converges at `INLET` and an external map `F(w)`; or, per call,
    an inner failure or an answer of another status."""

    F: Callable[[tuple[float, float]], tuple[float, float]]  # noqa: N815
    #: Inner-solve call indices (0-based) that fail.
    inner_fails: set[int] = field(default_factory=set)
    #: Experiment call indices that answer this status instead of `ok`.
    answers: Mapping[int, str] = field(default_factory=dict)
    w_seen: list[tuple[float, float]] = field(default_factory=list)
    starts: list[Any] = field(default_factory=list)
    experiments: int = 0

    def solve(self, w: Mapping[str, tuple[float, float]], start: Any) -> InnerSolve:
        index = len(self.w_seen)
        self.w_seen.append(w["R"])
        self.starts.append(start)
        if index in self.inner_fails:
            return InnerSolve("LINE_SEARCH_FAILED", None, {}, 7, "s", None, None)
        state = {"index": float(index)}
        return InnerSolve("CONVERGED", state, {"R": INLET}, 3, "s", "0" * 64, "0" * 64)

    def evaluate(self, unit: str, inlet: UnitInlet) -> ExternalAnswer:
        index = self.experiments
        self.experiments += 1
        status = self.answers.get(index, "ok")
        if status == "transient":
            return ExternalAnswer("transient", "external_timed_out")
        if status == "refused":
            return ExternalAnswer("refused", "out_of_domain")
        x, dt = self.F(self.w_seen[-1])
        return ExternalAnswer("ok", "ok", xi=x * inlet.n_key, T_out=inlet.T + dt)

    def run(self) -> CouplingRun:
        return couple(["R"], BLOCK, self.solve, self.evaluate)


def affine(g: tuple[float, float]) -> Callable[[tuple[float, float]], tuple[float, float]]:
    return lambda w: (W_STAR[0] + g[0] * (w[0] - W_STAR[0]), W_STAR[1] + g[1] * (w[1] - W_STAR[1]))


def test_the_registered_coupling_block_is_section_4_3s() -> None:
    assert (BLOCK.tau_xi_rel, BLOCK.tau_T_K, BLOCK.max_outer) == (1e-5, 1e-2, 15)
    assert (BLOCK.scale_X, BLOCK.scale_dT) == (0.1, 10.0)
    assert (BLOCK.bounds_X, BLOCK.bounds_dT) == ((0.0, 0.95), (-50.0, 250.0))
    assert BLOCK.initial == (0.15, 80.0)
    real = CouplingBlock.from_document(
        variants.registered_variant("pymrm-6089593-g2-nz800-s123-v2").coupling
    )
    assert real == BLOCK


def test_g8f_a_contractive_affine_map_converges() -> None:
    stub = Stub(affine((0.5, 0.0)))
    run = stub.run()
    assert run.outcome == "CONVERGED" and run.reason is None
    assert run.outer_iterations == 4 == stub.experiments
    assert [item["k"] for item in run.iterations] == [0, 1, 2, 3]
    assert run.iterations[-1]["rho"] <= 1.0
    assert run.w["R"][0] == pytest.approx(0.25, abs=1e-12) and run.w["R"][1] == 0.0


def scripted(residuals: list[float]) -> Callable[[tuple[float, float]], tuple[float, float]]:
    """G8 (f4)'s scripted residual stub: r_X = 0 and r_T = residuals[call] K, whatever w is."""
    calls = iter(residuals)
    return lambda w: (w[0], w[1] + next(calls))


def agrees_with_the_replica(run: CouplingRun, replica: Replica) -> None:
    """X̂_k, ΔT̂_k and ρ_k to a relative 1e-9; k and the step kinds exactly."""
    assert [item["k"] for item in run.iterations] == [it.k for it in replica.iterates]
    kinds = [item["step"]["kind"] for item in run.iterations]
    assert kinds[:-1] == [it.kind for it in replica.iterates][:-1]
    for item, it in zip(run.iterations, replica.iterates, strict=True):
        assert item["w"] == pytest.approx(list(it.w), rel=1e-9, abs=1e-12)
        assert item["rho"] == pytest.approx(it.rho, rel=1e-9)


N_TOT = sum(INLET.n)


def test_g8f1_a_contractive_affine_map_agrees_with_the_replica() -> None:
    """f1: G = diag(0.5, 0) from (0.15, 80 K), CONVERGED at k = 3; inert under §14.5 D5."""
    run = Stub(affine((0.5, 0.0))).run()
    replica = replicate(affine((0.5, 0.0)), BLOCK.initial, n_tot=N_TOT)
    assert replica.end == "converged"
    agrees_with_the_replica(run, replica)
    assert (run.outcome, run.iterations[-1]["k"]) == ("CONVERGED", 3)
    assert run.iterations[-1]["rho"] <= 1e-9
    # The design lane's replica values (n_tot,in = 4.35 exactly).
    table = replicate(affine((0.5, 0.0)), BLOCK.initial)
    assert [it.w[0] for it in table.iterates] == pytest.approx(
        [0.15, 0.2, 0.225048732943, 0.25], rel=1e-9
    )
    assert [it.rho for it in table.iterates[:3]] == pytest.approx(
        [8000.0, 574.7126437, 286.7961731], rel=1e-9
    )


def test_g8f2_the_non_contractive_affine_map_converges_without_a_reset() -> None:
    """f2 (D50's case): G = diag(1.8, 0) from (0.15, 80 K). ρ rises at k = 2 (the step to X̂ =
    −0.0766 clipped to 0) inside the 2n = 4 window, so there is no reset; pure Broyden then lands on
    the root at k = 3 ≤ 4 (the clause's five iterations)."""
    run = Stub(affine((1.8, 0.0))).run()
    replica = replicate(affine((1.8, 0.0)), BLOCK.initial, n_tot=N_TOT)
    agrees_with_the_replica(run, replica)
    assert (run.outcome, run.reason) == ("CONVERGED", None)
    assert run.iterations[-1]["k"] == 3 and run.outer_iterations <= 2 * 2 + 1
    assert [item["step"]["kind"] for item in run.iterations] == ["broyden"] * 3 + ["converged"]
    rhos = [item["rho"] for item in run.iterations]
    assert rhos[2] > rhos[1]  # why the case is registered
    assert rhos[3] <= 1e-9
    assert run.iterations[2]["w"][0] == 0.0  # clipped to the bound
    assert [it.clipped for it in replica.iterates[:3]] == [False, True, False]
    table = replicate(affine((1.8, 0.0)), BLOCK.initial)
    assert [it.w[0] for it in table.iterates] == pytest.approx([0.15, 0.07, 0.0, 0.25], abs=1e-12)
    assert [it.rho for it in table.iterates[:3]] == pytest.approx(
        [8000.0, 3310.344828, 4597.701149], rel=1e-9
    )


def test_g8f3_substitutions_own_step_raises_rho_without_a_clip() -> None:
    """f3: G = diag(1.8, 0) from (0.15, 0 K). The first (substitution) step raises ρ, with no clip:
    the window, not the clip, is what lets the run converge (k = 2)."""
    from dataclasses import replace

    stub = Stub(affine((1.8, 0.0)))
    run = couple(["R"], replace(BLOCK, initial=(0.15, 0.0)), stub.solve, stub.evaluate)
    replica = replicate(affine((1.8, 0.0)), (0.15, 0.0), n_tot=N_TOT)
    agrees_with_the_replica(run, replica)
    assert (run.outcome, run.iterations[-1]["k"]) == ("CONVERGED", 2)
    assert not any(it.clipped for it in replica.iterates)
    rhos = [item["rho"] for item in run.iterations]
    assert rhos[1] > rhos[0] and rhos[2] <= 1e-9
    assert [item["w"][1] for item in run.iterations] == [0.0, 0.0, 0.0]
    table = replicate(affine((1.8, 0.0)), (0.15, 0.0))
    assert [it.w[0] for it in table.iterates] == pytest.approx([0.15, 0.07, 0.25], rel=1e-9)
    assert [it.rho for it in table.iterates[:2]] == pytest.approx(
        [1839.08046, 3310.344828], rel=1e-9
    )


#: G8 (f4): ρ = 100 |r_T| falls to k = 3 = 2n − 1, then rises above ρ_best at k = 4 and k = 5.
F4_LATE = [-8.0, -4.0, -2.0, -1.0, -3.0, -5.0]
#: The same stub with its rise moved to k = 2, then falling to convergence.
F4_EARLY = [-8.0, -4.0, -6.0, -3.0, -2.0, -1.0, -0.005]


def test_g8f4_the_safeguard_is_live_after_the_window() -> None:
    """f4: a rise at k = 2n resets (to substitution from the best); a second rise at k = 2n + 1
    ends `no_decrease`. No step is clipped."""
    run = Stub(scripted(F4_LATE)).run()
    replica = replicate(scripted(F4_LATE), BLOCK.initial, n_tot=N_TOT)
    agrees_with_the_replica(run, replica)
    assert replica.end == "no_decrease"
    assert not any(it.clipped for it in replica.iterates)
    assert (run.outcome, run.reason) == ("COUPLING_NOT_CONVERGED", "no_decrease")
    kinds = [item["step"]["kind"] for item in run.iterations]
    assert kinds == ["broyden"] * 4 + ["reset", "none"]
    assert run.iterations[4]["step"]["B"] == [[-1.0, 0.0], [0.0, -1.0]]
    # The reset steps from the best iterate (k = 3), not from k = 4.
    du = run.iterations[4]["step"]["du"]
    assert run.iterations[5]["u"] == pytest.approx(
        [a + b for a, b in zip(run.iterations[3]["u"], du, strict=True)], abs=1e-15
    )


def test_g8f4_a_rise_inside_the_window_does_not_reset() -> None:
    """f4's stub with its rise moved to k = 2: no reset there."""
    run = Stub(scripted(F4_EARLY)).run()
    replica = replicate(scripted(F4_EARLY), BLOCK.initial, n_tot=N_TOT)
    agrees_with_the_replica(run, replica)
    assert not any(it.clipped for it in replica.iterates)
    rhos = [item["rho"] for item in run.iterations]
    assert rhos[2] > rhos[1]
    assert run.iterations[2]["step"]["kind"] == "broyden"
    assert "reset" not in [item["step"]["kind"] for item in run.iterations]
    assert run.outcome == "CONVERGED"


def test_g8f5_no_fixed_point_ends_coupling_not_converged() -> None:
    """f5, as built: r = (1, 0) at every w, so the secant update leaves B singular at k = 1."""
    run = Stub(lambda w: (w[0] + 1.0, w[1])).run()
    assert (run.outcome, run.reason) == ("COUPLING_NOT_CONVERGED", "broyden_singular")
    assert [item["k"] for item in run.iterations] == [0, 1]
    assert not run.answers


def test_the_first_step_is_successive_substitution_and_steps_are_clipped() -> None:
    stub = Stub(affine((0.5, 0.0)))
    run = stub.run()
    first = run.iterations[0]
    assert first["step"]["B"] == [[-1.0, 0.0], [0.0, -1.0]]
    # u1 = D F(w0): F(0.15, 80) = (0.2, 0).
    assert stub.w_seen[1] == pytest.approx((0.2, 0.0), abs=1e-15)
    clipped = Stub(lambda w: (2.0, 400.0)).run()
    assert clipped.iterations[1]["w"] == pytest.approx([0.95, 250.0])


def test_rho_and_the_residual_are_section_4_2s() -> None:
    run = Stub(affine((0.5, 0.0))).run()
    unit = run.iterations[0]["units"]["R"]
    # w0 = (0.15, 80): F = (0.2, 0); r = (0.05, −80).
    assert unit["xi_E"] == pytest.approx(0.2) and unit["T_E"] == INLET.T
    assert unit["r_xi"] == pytest.approx(0.05) and unit["r_T"] == -80.0
    n_tot = sum(INLET.n)
    assert unit["n_tot_in"] == n_tot and unit["n_N2_in"] == 1.0
    expected = max(abs(0.2 - 0.15) / (1e-5 * n_tot), 80.0 / 1e-2)
    assert run.iterations[0]["rho"] == pytest.approx(expected)
    assert unit["floor_ratio_xi"] is None and unit["floor_ratio_T"] is None  # no floor given


def test_inner_solves_after_the_first_start_from_the_bases_solution() -> None:
    stub = Stub(affine((0.5, 0.0)))
    stub.run()
    assert stub.starts[0] is None
    assert [start["index"] for start in stub.starts[1:]] == [0.0, 1.0, 2.0]


def test_an_inner_failure_halves_the_step_three_times_then_ends_inner_failed() -> None:
    stub = Stub(affine((0.5, 0.0)), inner_fails={1, 2, 3, 4})
    run = stub.run()
    assert (run.outcome, run.reason) == ("COUPLING_NOT_CONVERGED", "inner_failed")
    assert len(stub.w_seen) == 2 + BACKTRACKS
    x = [w[0] for w in stub.w_seen[1:]]
    # Each trial halves the step from the base X̂ = 0.15 towards 0.2.
    assert x == pytest.approx([0.2, 0.175, 0.1625, 0.15625])
    assert [item["step"]["kind"] for item in run.iterations] == [
        "broyden",
        "backtrack",
        "backtrack",
        "backtrack",
        "none",
    ]
    assert stub.experiments == 1  # an experiment only at an accepted point


def test_a_backtracked_point_that_succeeds_continues_the_iteration() -> None:
    stub = Stub(affine((0.5, 0.0)), inner_fails={1})
    run = stub.run()
    assert run.outcome == "CONVERGED"
    assert [item["k"] for item in run.iterations][:3] == [0, 1, 1]
    assert run.iterations[1]["step"]["kind"] == "backtrack"


def test_an_inner_failure_at_k0_passes_its_outcome_through() -> None:
    run = Stub(affine((0.5, 0.0)), inner_fails={0}).run()
    assert (run.outcome, run.reason) == ("LINE_SEARCH_FAILED", None)
    assert len(run.iterations) == 1 and run.iterations[0]["units"] == {}


def test_a_refusal_backtracks_and_at_k0_ends_external_refused() -> None:
    stub = Stub(affine((0.5, 0.0)), answers={1: "refused"})
    run = stub.run()
    assert run.outcome == "CONVERGED"
    assert run.iterations[1]["step"]["kind"] == "backtrack"
    assert run.iterations[1]["units"]["R"]["xi_E"] is None
    at_start = Stub(affine((0.5, 0.0)), answers={0: "refused"}).run()
    assert (at_start.outcome, at_start.reason) == (
        "COUPLING_NOT_CONVERGED",
        "external_refused(out_of_domain)",
    )
    always = Stub(affine((0.5, 0.0)), answers={i: "refused" for i in range(1, 9)}).run()
    assert (always.outcome, always.reason) == (
        "COUPLING_NOT_CONVERGED",
        "external_refused(out_of_domain)",
    )


def test_a_transient_answer_ends_evaluation_error_naming_the_unit() -> None:
    run = Stub(affine((0.5, 0.0)), answers={1: "transient"}).run()
    assert (run.outcome, run.reason) == ("EVALUATION_ERROR", "external_timed_out(R)")
    assert run.iterations[-1]["units"]["R"]["result"] is None


def test_at_most_max_outer_accepted_iterates() -> None:
    """The contractive map needs four accepted iterates; with `max_outer` = 3 the run stops at
    the third, k = 2."""
    from dataclasses import replace

    stub = Stub(affine((0.5, 0.0)))
    run = couple(["R"], replace(BLOCK, max_outer=3), stub.solve, stub.evaluate)
    assert (run.outcome, run.reason) == ("COUPLING_NOT_CONVERGED", "max_outer")
    assert run.outer_iterations == 3 == stub.experiments
    assert run.iterations[-1]["k"] == 2 and run.iterations[-1]["rho"] > 1.0


def test_the_record_is_flat_over_units_in_order() -> None:
    """Two units: w, u and B are 2m-wide, units in the order given."""
    inlets = {"A": INLET, "B": INLET}

    def solve(w: Mapping[str, tuple[float, float]], start: Any) -> InnerSolve:
        return InnerSolve("CONVERGED", {"x": 0.0}, inlets, 1, "s", None, None)

    def evaluate(unit: str, inlet: UnitInlet) -> ExternalAnswer:
        return ExternalAnswer("ok", "ok", xi=0.25 * inlet.n_key, T_out=inlet.T)

    run = couple(["A", "B"], BLOCK, solve, evaluate)
    assert run.outcome == "CONVERGED" and run.outer_iterations == 2
    first = run.iterations[0]
    assert first["w"] == [0.15, 80.0, 0.15, 80.0]
    assert np.array(first["step"]["B"]).shape == (4, 4)
    assert list(first["units"]) == ["A", "B"]
