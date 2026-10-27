"""The column theorem's premises P1–P3 on a `wilson-ig-v1` record set, decided in closed form.

S11 design §4.3 (ADR 0050 D4; closes R-781). S10-C's column theorem needs, for every component
over the records' temperature domain (S10C-spec §2.1, θ = T/1000 K):

- **P1** `d ln Psat/dT = (−b/θ² + c/θ + 2dθ)/1000 > 0` (1/K);
- **P2** `c_p^0L/R = (b0 − c) + b1θ + (b2 − 6d)θ² + b3θ³ + b4θ⁴ > 0`;
- **P3** `c_p^ig/R = b0 + b1θ + b2θ² + b3θ³ + b4θ⁴ > 0`.

Each function's minimum over `[θ_lo, θ_hi]` is taken over the two endpoints and every real root in
the interval of its critical-point cubic (its derivative, times θ³ for P1), which is exact for a
smooth function on a closed interval: a grid is not a proof (R-781). A premise holds iff its
minimum is ≥ 1e-9 1/K (P1) or ≥ 1e-6 J/(mol K) after multiplying by R (P2, P3).

Pure: reads a `WilsonRecords`, imports no provider class, and is not part of `wilson_ig.py`, whose
bytes are its `implementation_sha256`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Final, Literal

import numpy as np

from openflowsheet.thermo.wilson_ig import WilsonRecords

__all__ = ["R", "THRESHOLDS", "Minimum", "minima", "violations"]

#: J/(mol K), as `wilson_ig.R`.
R: Final = 8.31446261815324
#: θ = T / T_UNIT.
_T_UNIT: Final = 1000.0

Premise = Literal["P1", "P2", "P3"]

#: Premise -> the least admissible minimum, in the minimum's SI unit (1/K; J/(mol K)).
THRESHOLDS: Final[dict[str, float]] = {"P1": 1e-9, "P2": 1e-6, "P3": 1e-6}
#: A root of `numpy.roots` counts as real when |Im| ≤ this × max(1, |Re|).
_IMAGINARY: Final = 1e-12
#: Newton steps that refine each real root on its cubic.
_NEWTON_STEPS: Final = 2


@dataclass(frozen=True)
class Minimum:
    """One premise's minimum for one component over the records' T domain."""

    component: str
    premise: Premise
    #: The minimum, in 1/K (P1) or J/(mol K) (P2, P3).
    value: float
    #: K, where it is attained.
    temperature: float
    #: `endpoint` or `root` (a real root in the interval of the critical-point cubic).
    where: Literal["endpoint", "root"]

    @property
    def holds(self) -> bool:
        return self.value >= THRESHOLDS[self.premise]

    @property
    def hint(self) -> str:
        """S11 design §4.3's refusal hint."""
        return (
            f"{self.premise}: {self.component} min {self.value:.4g} at T = {self.temperature:.4g} K"
        )


def _polyval(coefficients: Sequence[float], x: float) -> float:
    """Horner, highest power first."""
    value = 0.0
    for coefficient in coefficients:
        value = value * x + coefficient
    return value


def _derivative(coefficients: Sequence[float]) -> tuple[float, ...]:
    degree = len(coefficients) - 1
    return tuple(c * (degree - k) for k, c in enumerate(coefficients[:-1]))


def _critical_points(cubic: Sequence[float], lo: float, hi: float) -> tuple[float, ...]:
    """The real roots of `cubic` (highest power first) in `[lo, hi]`, each refined by two Newton
    steps on the cubic."""
    if not any(cubic):
        return ()
    slope = _derivative(cubic)
    found = []
    for root in np.roots(np.asarray(cubic, dtype=float)):
        re, im = float(root.real), float(root.imag)
        if abs(im) > _IMAGINARY * max(1.0, abs(re)):
            continue
        for _ in range(_NEWTON_STEPS):
            d = _polyval(slope, re)
            if d == 0.0:
                break
            re -= _polyval(cubic, re) / d
        if lo <= re <= hi:
            found.append(re)
    return tuple(found)


def _minimum(
    component: str,
    premise: Premise,
    function: Callable[[float], float],
    cubic: Sequence[float],
    domain: tuple[float, float],
) -> Minimum:
    lo, hi = domain[0] / _T_UNIT, domain[1] / _T_UNIT
    candidates = [(function(lo), lo, "endpoint"), (function(hi), hi, "endpoint")]
    candidates += [(function(t), t, "root") for t in _critical_points(cubic, lo, hi)]
    value, theta, where = min(candidates, key=lambda c: c[0])
    return Minimum(component, premise, value, theta * _T_UNIT, where)  # type: ignore[arg-type]


def _p1(slope: tuple[float, float, float], theta: float) -> float:
    """d ln Psat/dT in 1/K, with `slope` = (−b, c, 2d)."""
    minus_b, c, two_d = slope
    return (minus_b / theta**2 + c / theta + two_d * theta) / _T_UNIT


def _cp(coefficients: Sequence[float], theta: float) -> float:
    """R times a polynomial in θ (highest power first): J/(mol K)."""
    return R * _polyval(coefficients, theta)


def minima(records: WilsonRecords) -> tuple[Minimum, ...]:
    """Every component's P1, P2 and P3 minima, components in file order, then P1, P2, P3."""
    found: list[Minimum] = []
    domain = records.temperature_domain
    for component, (_, b, c, d), cp in zip(
        records.components, records.vapour_pressure, records.cp, strict=True
    ):
        b0, b1, b2, b3, b4 = cp
        slope = (-b, c, 2.0 * d)  # ln Psat's constant `a` does not enter its slope
        liquid = (b4, b3, b2 - 6.0 * d, b1, b0 - c)
        ideal = (b4, b3, b2, b1, b0)
        found.append(
            _minimum(component, "P1", partial(_p1, slope), (2.0 * d, 0.0, -c, 2.0 * b), domain)
        )
        found.append(_minimum(component, "P2", partial(_cp, liquid), _derivative(liquid), domain))
        found.append(_minimum(component, "P3", partial(_cp, ideal), _derivative(ideal), domain))
    return tuple(found)


def violations(records: WilsonRecords) -> tuple[Minimum, ...]:
    """The minima that break their premise, in `minima`'s order; `()` iff P1–P3 hold."""
    return tuple(m for m in minima(records) if not m.holds)
