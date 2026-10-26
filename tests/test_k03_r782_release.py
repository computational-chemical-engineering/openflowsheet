"""K03 §5.3 as amended 2026-10-26 (R-782): the release at every step where it changes the step
(`docs/derivations/S10C-absent-component.md` §4.1–§4.2, gate G-R1).

R-064 discarded the factorization's roundoff on the released set `Z*` only where it would block
(`α_max = 0`). Where the roundoff on `Z*` happened to point inward, the step was taken and lifted
the set off its bound by ~1e-15, after which its rows were no longer exactly closed and it could
never be released again (S10-C's C-MW on aarch64). Now, at `α_max > 0`, a direction entry on
`Z*` is set to exactly zero too — the exact Newton step there — and `α_max` and the landing are
those of the unmodified direction (§4.2). The exactness conditions are R-064's, unchanged:

- **(i)** `a` at `+0.0` at the opening and the iterate, row `F = 2a` closed, roundoff
  `d_a = +1e-30`, a real step on `b`: `d_a := 0.0`, `released == (0,)`, `α` and the landing equal
  the unmodified direction's, and the trial keeps `a` at `+0.0`.
- **(ii)** The closed row's `F = 1e-300`, not exactly zero: nothing is released, `d_a` is kept.
- **(iii)** `a` positive at the opening, zero at the iterate (T02 §6.3.3's disappearance): not
  released.
- **(iv)** Two columns on their bounds and one closed row reading both (underdetermined): not
  released.
- **(v)** `d_a == 0.0` already: the input direction is returned, `released == ()`, and `_released`
  is never called (the common path's order, note §4.5).

The `α_max = 0` branch is R-064's, unchanged; B33c i–v (`test_t05b_near_pure_restarts.py`) hold it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp

from openflowsheet.numerics import newton

#: Two components on `x ≥ 0`: `a` at `+0.0` (at the opening too), `b = 1`.
X = np.array([0.0, 1.0])
LOWER = np.array([0.0, 0.0])
#: The factorization's roundoff on `a` (inward), and a real step on `b` that stays inside.
DIRECTION = np.array([1e-30, -0.5])
#: Row 0 is `F = 2a` (its one entry on `a`), row 1 reads both.
JACOBIAN = [[2.0, 0.0], [1.0, 1.0]]


def _step(
    residual: tuple[float, ...],
    jacobian: list[list[float]] = JACOBIAN,
    *,
    x: np.ndarray = X,
    direction: np.ndarray = DIRECTION,
    opening: np.ndarray | None = None,
) -> tuple[np.ndarray, float, tuple[int, ...], tuple[int, ...]]:
    return newton._bound_aware_step(
        x,
        direction,
        LOWER,
        opening=x if opening is None else opening,
        residual=residual,
        jacobian=sp.csc_matrix(np.array(jacobian)),
    )


def test_i_a_released_set_drops_its_inward_roundoff_at_a_positive_alpha_max() -> None:
    unmodified = newton._bound_aware_alpha(X, DIRECTION, LOWER)
    assert unmodified[0] == 1.0  # nothing blocks: before R-782 the step was taken as is
    before = DIRECTION.copy()
    direction, alpha, landing, released = _step((0.0, 0.5))
    assert released == (0,)
    assert direction[0] == 0.0 and direction[1] == -0.5
    assert (alpha, landing) == unmodified
    assert np.array_equal(DIRECTION, before)  # the caller's direction is not written to
    trial = newton._trial_point(X, direction, alpha, LOWER, landing)
    assert trial[0] == 0.0 and np.copysign(1.0, trial[0]) == 1.0  # `+0.0`, not 1e-30
    assert trial[1] == 0.5


def test_ii_a_row_of_the_set_off_zero_releases_nothing() -> None:
    direction, alpha, landing, released = _step((1e-300, 0.5))
    assert released == ()
    assert direction is DIRECTION and direction[0] == 1e-30
    assert (alpha, landing) == newton._bound_aware_alpha(X, DIRECTION, LOWER)


def test_iii_a_component_not_on_its_bound_at_the_opening_is_never_released() -> None:
    direction, _, _, released = _step((0.0, 0.5), opening=np.array([0.25, 1.0]))
    assert released == ()
    assert direction is DIRECTION


def test_iv_fewer_closed_rows_than_columns_is_not_released() -> None:
    x = np.array([0.0, 0.0])
    inward = np.array([1e-30, 0.5])
    direction, alpha, _, released = _step(
        (0.0, 1.0), [[1.0, 1.0], [0.0, 1.0]], x=x, direction=inward
    )
    assert released == ()
    assert direction is inward
    assert alpha == 1.0


def test_v_a_zero_direction_on_the_bound_returns_the_input_without_a_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []
    real = newton._released

    def spy(*arguments: Any) -> tuple[int, ...]:
        calls.append(arguments)
        return real(*arguments)

    monkeypatch.setattr(newton, "_released", spy)
    still = np.array([0.0, -0.5])
    direction, alpha, landing, released = _step((0.0, 0.5), direction=still)
    assert direction is still and released == ()
    assert (alpha, landing) == newton._bound_aware_alpha(X, still, LOWER)
    assert calls == []
    _step((0.0, 0.5))  # (i): the mask is non-empty, so `Z*` is computed once
    assert len(calls) == 1
