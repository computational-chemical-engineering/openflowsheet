"""M02 WO-10: the outer coupling driver with the inner solve and the experiments stubbed (design
note §4.2–§4.3; ADR 0034 D2, D3; G8 (f), driver level).

- G8 (f): affine maps F(w) = w* + G (w − w*) with w* = (0.25, 0 K), the stand-in's fixed point:
  G = diag(0.5, 0) converges; G = diag(1.8, 0) (non-contractive) — see the xfail below, which
  records a conflict between the gate and §4.3's own safeguard; F(w) = w + (1, 0) (no fixed point)
  ends `COUPLING_NOT_CONVERGED`.
- §4.3: the first step from B₀ = −I is successive substitution; steps are clipped to the bounds;
  a second reset in a row ends `no_decrease`; `max_outer` accepted iterates at most; an inner
  failure or a deterministic refusal halves the step towards its base at most three times; an
  inner failure at k = 0 passes its outcome through; a transient answer ends `EVALUATION_ERROR`
  `external_<status>(<unit>)`.
- §4.2: ρ and the residual's components as the record carries them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "G8 (f) vs §4.3 (escalated, build log D50): pure Broyden on G = diag(1.8, 0) converges "
        "at k = 3 (Gay), but passes through rho_2 = 6.1e3 > rho_1 = 3.3e3 (4.7e3 with X clipped "
        "to its bound 0), so §4.3's reset fires at k = 2 and again at k = 3: no_decrease"
    ),
)
def test_g8f_a_non_contractive_affine_map_converges_within_five_iterations() -> None:
    run = Stub(affine((1.8, 0.0))).run()
    assert run.outcome == "CONVERGED"
    assert run.outer_iterations <= 2 * 2 + 1


def test_g8f_the_non_contractive_map_as_section_4_3_ends_it_measured() -> None:
    """The measured end of the G = diag(1.8, 0) case under the registered safeguards (the record
    the escalation cites): ρ falls at k = 1 (X̂ = 0.07), rises at k = 2 (the Broyden step leaves the
    bound and is clipped to X̂ = 0: reset to substitution from k = 1), and the substitution step
    lands on the same clipped point (second reset in a row)."""
    run = Stub(affine((1.8, 0.0))).run()
    assert (run.outcome, run.reason) == ("COUPLING_NOT_CONVERGED", "no_decrease")
    kinds = [item["step"]["kind"] for item in run.iterations]
    assert kinds == ["broyden", "broyden", "reset", "none"]
    n_tot = sum(INLET.n)

    def rho(x: float) -> float:
        return abs(0.8 * (x - 0.25)) * INLET.n_key / (1e-5 * n_tot)

    rhos = [item["rho"] for item in run.iterations]
    assert rhos[0] == pytest.approx(80.0 / 1e-2)
    assert rhos[1] == pytest.approx(rho(0.07), rel=1e-12)
    assert rhos[2] == pytest.approx(rho(0.0), rel=1e-12) == rhos[3]
    assert rhos[2] > rhos[1]
    assert run.iterations[2]["w"][0] == 0.0 == run.iterations[3]["w"][0]  # clipped to the bound


def test_g8f_no_fixed_point_ends_coupling_not_converged() -> None:
    run = Stub(lambda w: (w[0] + 1.0, w[1])).run()
    assert run.outcome == "COUPLING_NOT_CONVERGED"
    assert run.reason in {"broyden_singular", "no_decrease", "max_outer"}
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


def test_two_resets_in_a_row_end_no_decrease() -> None:
    """ρ rises against the best twice in a row: the second reset ends the run."""
    calls = {"n": 0}

    def rising(w: tuple[float, float]) -> tuple[float, float]:
        calls["n"] += 1
        # ρ is set by |ΔT̂ residual|: 80 at k = 0, then 10, then 40, then 40.
        return (w[0], {1: 0.0, 2: w[1] - 10.0, 3: w[1] - 40.0}.get(calls["n"], w[1] - 40.0))

    run = Stub(rising).run()
    assert (run.outcome, run.reason) == ("COUPLING_NOT_CONVERGED", "no_decrease")
    assert [item["step"]["kind"] for item in run.iterations][-2:] == ["reset", "none"]


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
