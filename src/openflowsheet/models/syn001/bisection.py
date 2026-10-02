"""The bracketed bisection the unit layer's closures share (T05 spec §4.4 step 4; T05b spec §5.2).

Moved here from `ph_kernel` unchanged (T05b W1) so that the saturation band (`saturation_band`),
which the kernel and `tp_state` both read, can bisect without importing the kernel. The kernel
re-exports both names. `min_width` is T05b's: the band route's `β` bracket stops at a width floor
(`2⁻⁶⁰`, spec §5.2) as well as at adjacent doubles; its default `0.0` never triggers, because
`lo < middle < hi` already implies `hi - lo > 0`, so every T05 caller runs exactly as before.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

__all__ = ["Root", "bracketed_root"]


@dataclass(frozen=True)
class Root[P]:
    """Where a bracketed search stopped, and what the function said there."""

    point: float
    value: float
    payload: P
    evaluations: int
    #: False when the evaluation budget ran out before the bracket closed.
    converged: bool


def bracketed_root[P](
    function: Callable[[float], tuple[float, P]],
    lower: tuple[float, float, P],
    upper: tuple[float, float, P],
    *,
    evaluations: int,
    budget: int,
    min_width: float = 0.0,
) -> Root[P]:
    """Bisect an increasing function on a bracket whose ends are already evaluated.

    `lower` and `upper` are `(point, value, payload)` with `value(lower) <= 0 <= value(upper)`;
    `evaluations` is how many calls were spent on them, and counts against `budget`.

    Stops when `f = 0` exactly, when no double lies strictly between the bracket ends, or when
    the bracket is no wider than `min_width`, and returns the end with the smaller `|f|` (the
    lower one on a tie). This is spec §4.4 step 4 with the optional acceleration left out:
    bisection is deterministic, needs no safeguard to stay inside the bracket, and on the SYN-001
    domain closes it in about 44 evaluations, far inside the budget. The caller decides whether
    the returned `|f|` is acceptable. An end whose value is infinite (the band route's sign
    oracle, T05b spec §5.2) is compared by `abs` like any other and so loses to every finite one.
    """
    lo, f_lo, p_lo = lower
    hi, f_hi, p_hi = upper
    if f_lo == 0.0:
        return Root(lo, f_lo, p_lo, evaluations, True)
    if f_hi == 0.0:
        return Root(hi, f_hi, p_hi, evaluations, True)
    while True:
        middle = 0.5 * (lo + hi)
        if not lo < middle < hi or hi - lo <= min_width:
            break
        if evaluations >= budget:
            return Root(lo, f_lo, p_lo, evaluations, False)
        f_middle, p_middle = function(middle)
        evaluations += 1
        if f_middle == 0.0:
            return Root(middle, f_middle, p_middle, evaluations, True)
        if f_middle < 0.0:
            lo, f_lo, p_lo = middle, f_middle, p_middle
        else:
            hi, f_hi, p_hi = middle, f_middle, p_middle
    if abs(f_hi) < abs(f_lo):
        return Root(hi, f_hi, p_hi, evaluations, True)
    return Root(lo, f_lo, p_lo, evaluations, True)
