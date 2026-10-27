"""The estimate's class and first-order propagation (E01 design §4.9).

- `AACE_RANGES` — AACE 18R-97's expected accuracy ranges per class (low and high, each a span).
- `estimate_class` — the maximum class over costed items; `None` (class `none`) when any item was
  computed with `CORRELATION_EXTRAPOLATED`. Excluded items are not passed in.
- `worst_case` and `rss` — for one output y, from `g_k = ∂y/∂θ_k · θ_k` and each θ's declared
  relative range `[lo_k, hi_k]`: the fully correlated interval `y + Σ_k min/max(g_k lo_k, g_k hi_k)`
  and the independent-uniform standard deviation `sqrt(Σ_k g_k² (hi_k − lo_k)²/12)`, left folds in
  θ order.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Final

__all__ = ["AACE_RANGES", "ASSUMPTIONS", "STATEMENT", "estimate_class", "rss", "worst_case"]

#: §4.9's table: class → ((low from, low to), (high from, high to)), as fractions.
AACE_RANGES: Final[Mapping[int, tuple[tuple[float, float], tuple[float, float]]]] = {
    5: ((-0.20, -0.50), (0.30, 1.00)),
    4: ((-0.15, -0.30), (0.20, 0.50)),
    3: ((-0.10, -0.20), (0.10, 0.30)),
    2: ((-0.05, -0.15), (0.05, 0.20)),
    1: ((-0.03, -0.10), (0.03, 0.15)),
}

#: The labels each propagated quantity carries (§4.9).
ASSUMPTIONS: Final[Mapping[str, str]] = {
    "worst_case": "linear, first order; inputs fully correlated (conservative)",
    "rss": "linear, first order; inputs independent and uniform on their ranges",
}

#: §4.9, verbatim in every report.
STATEMENT: Final = (
    "Assessment evidence: an estimate under the stated basis, correlations, data and regimes. "
    "It is not numerical verification of the flowsheet and not empirical validation."
)


def estimate_class(classes: Iterable[int], extrapolated: bool) -> int | None:
    """The maximum class number over costed items, or `None` for class `none`."""
    if extrapolated:
        return None
    found = list(classes)
    return max(found) if found else None


def worst_case(
    y: float, sensitivities: Sequence[float], ranges: Sequence[tuple[float, float]]
) -> tuple[float, float]:
    """`(y + Σ min(g lo, g hi), y + Σ max(g lo, g hi))`, `g_k = ∂y/∂θ_k·θ_k`."""
    low, high = y, y
    for g, (lo, hi) in zip(sensitivities, ranges, strict=True):
        a, b = g * lo, g * hi
        low, high = low + min(a, b), high + max(a, b)
    return low, high


def rss(sensitivities: Sequence[float], ranges: Sequence[tuple[float, float]]) -> float:
    """`sqrt(Σ g_k² (hi_k − lo_k)²/12)`."""
    total = 0.0
    for g, (lo, hi) in zip(sensitivities, ranges, strict=True):
        total = total + g * g * (hi - lo) * (hi - lo) / 12.0
    return math.sqrt(total)
