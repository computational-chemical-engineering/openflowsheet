"""T05b B35: the release's opening is the attempt's (K03 §5.3 note of 2026-09-25, ruling Q-S13;
re-review S-W1).

K03 §5.3 as amended releases a set `Z` of components that sit exactly on their bounds at the
current iterate *and at the attempt's opening*, when the rows closed on `Z` make its exact Newton
step zero. `solve_newton` took its own start as that opening; T04's homotopy corrector starts each
call from the last accepted λ-level, so a phase that vanished at an earlier level would count as
"on its bound at the opening" and be released — the disappearance §5.3 excludes. Now
`solve_newton(..., opening=)` names the opening (default: the call's start), and `_homotopy`'s
corrector passes its attempt's `x⁰`.

- (a) At the level of the Newton core: an affine 3×3 problem whose row 0 (`F = 0.1 a`) is closed on
  `a = 0`, and whose factorization leaves a roundoff outward component on `a` (pivoting on row 2).
  Without `opening=` (the call's start, `a = 0` there) `{a}` is released and the problem converges
  in one step with `a == +0.0`; with an `opening=` where `a = 0.25` nothing is released and the
  call ends `BOUND_BLOCKED` on `a` from the original direction (K03 BND-02).
- (b) `_homotopy`'s corrector passes its attempt's `x⁰` bitwise on every `solve_newton` call (a spy
  on T04's HOM-01); the region's own Newton attempts pass none.
- (c) Inertness: the protocol's hashes, and the build lane's census (every homotopy corrector
  call of the test suite: the released set is the same with either opening) —
  `docs/t05b-measurements.md`.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
import scipy.sparse as sp
from test_t04_edge3 import case_document, case_policy, plan_run, region_step

from openflowsheet.numerics.newton import Evaluation, Problem, solve_newton
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.trace import SolvePolicy, Trace

POLICY = SolvePolicy(policy_id="K03-synthetic-seeds", residual_tolerances={}, scales={})
IDS = ("a", "b", "c")
ROWS = ("r0", "r1", "r2")
#: Row 0 reads `a` alone; column `a`'s largest entry is row 2's, so the factorization pivots there
#: and `a`'s exact-zero step comes out as roundoff (outward: see `test_b35a_…_blocks`).
JACOBIAN = np.array([[0.1, 0.0, 0.0], [0.9, 0.1, 0.7], [3.0, 0.5, 0.3]])
RHS = np.array([0.0, 0.9, 0.7])
#: The start: `a` on its bound (row 0 closed, `F = 0.0`), `b`, `c` free.
START = np.array([0.0, 1.0, 1.0])
#: `(a, b, c)` with `J x = RHS`.
ROOT = (0.0, 0.6875, 1.1875)


def affine() -> Problem:
    def evaluate(x: npt.NDArray[np.float64]) -> Evaluation:
        return Evaluation(status="ok", values=tuple(float(v) for v in JACOBIAN @ x - RHS))

    def jacobian(x: npt.NDArray[np.float64]) -> sp.csc_matrix:
        return sp.csc_matrix(JACOBIAN)

    return Problem(
        variable_ids=IDS,
        row_ids=ROWS,
        residual=evaluate,
        jacobian=jacobian,
        scaling=Scaling(column=dict.fromkeys(IDS, 1.0), row=dict.fromkeys(ROWS, 1.0)),
        row_tolerance=dict.fromkeys(ROWS, 1e-9),
        lower_bounds={"a": 0.0},
    )


def test_b35a_the_calls_start_is_the_default_opening_and_releases() -> None:
    """(a) Without `opening=`, `a` is on its bound at the opening (the call's start) and at the
    iterate, its row closed: `{a}` is released, and the step is exact — one iteration, `a` stays
    `+0.0`, `b`, `c` land on the root. Passing the start explicitly is the same call."""
    result = solve_newton(affine(), START, POLICY, trace=Trace())
    assert (result.outcome, result.iterations) == ("CONVERGED", 1)
    assert result.x[0] == 0.0 and math.copysign(1.0, result.x[0]) == 1.0
    assert tuple(result.x[1:]) == pytest.approx(ROOT[1:], rel=1e-14)
    explicit = solve_newton(affine(), START, POLICY, trace=Trace(), opening=START.copy())
    assert explicit.outcome == result.outcome
    assert explicit.x.tobytes() == result.x.tobytes()


def test_b35a_off_its_bound_at_the_opening_it_is_not_released_and_blocks() -> None:
    """(a) The same call with an `opening=` where `a = 0.25`: `a` was not on its bound at the
    attempt's opening, so nothing is released; the original direction's roundoff on `a` points
    out, and the call ends `BOUND_BLOCKED` on `a` at iteration 0 (K03 BND-02)."""
    opening = np.array([0.25, 1.0, 1.0])
    result = solve_newton(affine(), START, POLICY, trace=Trace(), opening=opening)
    assert (result.outcome, result.iterations, result.blocked_by) == ("BOUND_BLOCKED", 0, ("a",))
    assert result.x.tobytes() == START.tobytes()


def test_b35a_an_opening_of_another_length_is_refused() -> None:
    with pytest.raises(ValueError, match="opening has 2 components"):
        solve_newton(affine(), START, POLICY, trace=Trace(), opening=[0.0, 1.0])


def test_b35b_the_corrector_passes_its_attempts_opening() -> None:
    """(b) On T04's HOM-01 every `solve_newton` call made inside `_homotopy` carries
    `opening=` bitwise that attempt's `x⁰`; the region's Newton attempts pass none."""
    calls: list[tuple[bool, Any]] = []
    openings: list[npt.NDArray[np.float64]] = []
    inside = {"depth": 0}
    real_homotopy, real_solve = region_module._homotopy, region_module.solve_newton

    def homotopy(**kwargs: Any) -> Any:
        openings.append(np.array(kwargs["x0"], dtype=np.float64, copy=True))
        inside["depth"] += 1
        try:
            return real_homotopy(**kwargs)
        finally:
            inside["depth"] -= 1

    def solve(*args: Any, **kwargs: Any) -> Any:
        calls.append((inside["depth"] > 0, kwargs.get("opening")))
        return real_solve(*args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(region_module, "_homotopy", homotopy)
        patch.setattr(region_module, "solve_newton", solve)
        run = plan_run(case_document("HOM-01"), case_policy("HOM-01"))
    step = region_step(run.result)
    assert (step.eo_recovery, step.outcome) == ("taken", "CONVERGED")
    (x0,) = openings
    corrector = [opening for inside_homotopy, opening in calls if inside_homotopy]
    assert len(corrector) >= 2
    assert all(
        opening is not None and np.asarray(opening).tobytes() == x0.tobytes()
        for opening in corrector
    )
    assert all(opening is None for inside_homotopy, opening in calls if not inside_homotopy)
