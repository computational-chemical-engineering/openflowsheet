"""Default split-conformal reporting and the promotion verdict (M04 spec §6–§7, ADR 0036 D3–D5).

Every decision here is made in integers or by an exact comparison of binary64 values that are
themselves inputs; nothing is decided on the last digits of a floating-point quantile:

* the finite-sample index k = ⌈(n + 1)(1 − α)⌉ with α = 1/20 is `−(−(n+1)·19 // 20)`;
* q̂ is the k-th smallest calibration score — an element of the input, never interpolated;
* a failed draw scores +∞ (`None` here, as in the manifest) and stays in n or m (R-244);
* the coverage test passes iff H ≥ h_min(m), the smallest h with P(Bin(m, 9/10) ≥ h) ≤ 1/20,
  evaluated as an exact integer inequality; it is equivalent to the Clopper–Pearson bound ≥ 0.90
  and immune to the beta quantile's rounding (R-246);
* the Clopper–Pearson bound itself (SciPy's beta quantile) is reported, never decided on.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from typing import Final, Literal

from scipy.stats import beta

#: The score (spec §6.1): s = max(|e_X|/w_X, |e_ΔT|/w_ΔT), the scales being the width limits.
SCORE_ID: Final = "joint-max-scaled-abs-v1"
WIDTH_X: Final = 0.0025
WIDTH_DT_K: Final = 1.5
#: The method label of the uncertainty claim (spec §10.2).
METHOD_ID: Final = "split-conformal-default-v1"

#: Miscoverage α = 1/20: nominal coverage 0.95 (spec §6.2).
ALPHA: Final = Fraction(1, 20)
#: The coverage test's one-sided level δ = 1/20 and declared minimum coverage c_min = 9/10 (§6.4).
DELTA: Final = Fraction(1, 20)
C_MIN: Final = Fraction(9, 10)
#: The gradient limit ρ_g (spec §7.2) and the identifiability threshold τ_id (spec §3.4).
RHO_G: Final = 0.25
TAU_ID: Final = 1.0e-8
#: The number of coefficients of the full quadratic in seven inputs (spec §3.4).
TERMS: Final = 36

Verdict = Literal["PROMOTABLE", "NOT_PROMOTABLE", "INSUFFICIENT_EVIDENCE"]

#: The reasons of spec §7.3, in the order the verdict function evaluates and records them.
INSUFFICIENT_REASONS: Final[tuple[str, ...]] = (
    "budget_below_plan",
    "plan_incomplete",
    "training_unidentifiable",
    "calibration_too_small",
    "test_too_small",
    "gradient_check_incomplete",
)
NOT_PROMOTABLE_REASONS: Final[tuple[str, ...]] = (
    "band_not_finite",
    "width_limit_exceeded",
    "coverage_bound_below_minimum",
    "gradient_limit_exceeded",
    "inadmissible_prediction",
    "parent_extrapolated",
)


def _finite_nonnegative(value: float, what: str) -> float:
    if not (math.isfinite(value) and value >= 0.0):
        raise ValueError(f"{what} {value!r} is not finite and non-negative")
    return value


def score(x: float, dt: float, x_predicted: float, dt_predicted: float) -> float:
    """s = max(|X − X̃|/w_X, |ΔT − ΔT̃|/w_ΔT) of an `ok` draw (spec §6.1)."""
    value = max(abs(x - x_predicted) / WIDTH_X, abs(dt - dt_predicted) / WIDTH_DT_K)
    return _finite_nonnegative(value, "score")


def _scores(scores: Sequence[float | None], what: str) -> tuple[float | None, ...]:
    """Validate scores: a finite non-negative float, or `None` for a failed draw (+∞)."""
    return tuple(None if s is None else _finite_nonnegative(s, what) for s in scores)


# -- the finite-sample rule (spec §6.2) -----------------------------------------------------------


def k_index(n: int) -> int:
    """k(n) = ⌈(n + 1)(1 − α)⌉ in integers: −(−(n+1)·19 // 20) for α = 1/20."""
    if n < 0:
        raise ValueError(f"n = {n} is negative")
    keep = 1 - ALPHA
    return -(-(n + 1) * keep.numerator // keep.denominator)


def n_min() -> int:
    """The smallest n with k(n) ≤ n: below it no calibration set yields a band (19)."""
    n = 1
    while k_index(n) > n:
        n += 1
    return n


@dataclass(frozen=True)
class Band:
    """The conformal quantile of n calibration scores (spec §6.2).

    `q_hat` is the k-th smallest score, `None` when there is no band: `refusal` is then
    `calibration_too_small` (k > n) or `band_not_finite` (the k-th smallest score is +∞).
    """

    n: int
    k: int
    q_hat: float | None
    refusal: Literal["calibration_too_small", "band_not_finite"] | None

    @property
    def finite_sample_level(self) -> Fraction:
        """k/(n + 1): the guaranteed marginal coverage for continuous scores (spec §6.2)."""
        return Fraction(self.k, self.n + 1)

    def half_widths(self) -> tuple[float, float] | None:
        """(q̂ w_X, q̂ w_ΔT): the band's constant half-widths (spec §6.1, §8.6)."""
        if self.q_hat is None:
            return None
        return self.q_hat * WIDTH_X, self.q_hat * WIDTH_DT_K


def conformal_band(calibration_scores: Sequence[float | None]) -> Band:
    """q̂ = the k-th smallest of the n calibration scores, `None` (+∞) for a failed draw."""
    scores = _scores(calibration_scores, "calibration score")
    n = len(scores)
    k = k_index(n)
    if k > n:
        return Band(n, k, None, "calibration_too_small")
    finite = sorted(s for s in scores if s is not None)
    if k > len(finite):
        return Band(n, k, None, "band_not_finite")
    return Band(n, k, finite[k - 1], None)


# -- the coverage test (spec §6.4) ----------------------------------------------------------------


def coverage_hits(test_scores: Sequence[float | None], q_hat: float) -> int:
    """H = #{j : s_j ≤ q̂}; a failed draw (`None`, +∞) is a miss and stays in m."""
    return sum(1 for s in _scores(test_scores, "test score") if s is not None and s <= q_hat)


def binomial_tail_at_most_delta(m: int, h: int) -> bool:
    """P(Bin(m, c_min) ≥ h) ≤ δ, exactly: with c_min = a/b and δ = d/e,
    e · Σ_{j ≥ h} C(m, j) a^j (b − a)^(m − j) ≤ d · b^m."""
    a, b = C_MIN.numerator, C_MIN.denominator
    tail: int = sum(comb(m, j) * a**j * (b - a) ** (m - j) for j in range(max(h, 0), m + 1))
    total: int = b**m
    return DELTA.denominator * tail <= DELTA.numerator * total


def h_min(m: int) -> int | None:
    """The smallest h with P(Bin(m, 0.9) ≥ h) ≤ 0.05, or `None` when not even h = m qualifies."""
    if m < 0:
        raise ValueError(f"m = {m} is negative")
    for h in range(m + 1):
        if binomial_tail_at_most_delta(m, h):
            return h
    return None


def m_min() -> int:
    """The smallest test set that can pass the coverage test with no misses (29): 0.9^m ≤ 0.05."""
    m = 1
    while not binomial_tail_at_most_delta(m, m):
        m += 1
    return m


def clopper_pearson_lower(hits: int, m: int) -> float:
    """L(H, m) = B⁻¹(δ; H, m − H + 1), L(0, m) = 0: the one-sided 95 % lower bound on the frozen
    band's coverage (spec §6.4). Reported only; the decision is `hits >= h_min(m)`."""
    if not 0 <= hits <= m:
        raise ValueError(f"H = {hits} is not in [0, m = {m}]")
    if hits == 0:
        return 0.0
    return float(beta.ppf(float(DELTA), hits, m - hits + 1))


# -- the verdict (spec §7.3) ----------------------------------------------------------------------


@dataclass(frozen=True)
class StudyEvidence:
    """What the verdict function reads (spec §7.1, §7.3; the generator's `verdict_vectors`).

    `singular_value_ratio` is σ_min(Φ)/σ_max(Φ), `None` when the fit refused before computing it.
    `gradient_errors` are the gradient centres' errors e (spec §7.2), `None` when a centre has a
    failed stencil experiment. `inadmissible` counts inadmissible calibration and test predictions;
    `extrapolated` counts registered draws the parent flagged `extrapolated`.
    """

    budget_ok: bool
    plan_complete: bool
    training_ok: int
    singular_value_ratio: float | None
    calibration_scores: tuple[float | None, ...]
    test_scores: tuple[float | None, ...]
    gradient_errors: tuple[float, ...] | None
    inadmissible: int
    extrapolated: int


@dataclass(frozen=True)
class StudyVerdict:
    """The verdict and both reason lists, always recorded, with every metric that was computable."""

    verdict: Verdict
    insufficient: tuple[str, ...]
    not_promotable: tuple[str, ...]
    n: int | None
    k: int | None
    q_hat: float | None
    m: int | None
    hits: int | None
    h_min: int | None
    lower_bound: float | None


def study_verdict(evidence: StudyEvidence) -> StudyVerdict:
    """The registered verdict function (spec §7.3): every reason it finds, in the order of §7.3;
    INSUFFICIENT_EVIDENCE if any IE reason, else NOT_PROMOTABLE if any NP reason, else PROMOTABLE.

    A budget below the plan is refused before running: nothing else is evaluated.
    """
    if not evidence.budget_ok:
        return StudyVerdict(
            verdict="INSUFFICIENT_EVIDENCE",
            insufficient=("budget_below_plan",),
            not_promotable=(),
            n=None,
            k=None,
            q_hat=None,
            m=None,
            hits=None,
            h_min=None,
            lower_bound=None,
        )
    insufficient: list[str] = []
    not_promotable: list[str] = []
    if not evidence.plan_complete:
        insufficient.append("plan_incomplete")
    ratio = evidence.singular_value_ratio
    if evidence.training_ok < TERMS or ratio is None or ratio < TAU_ID:
        insufficient.append("training_unidentifiable")
    band = conformal_band(evidence.calibration_scores)
    if band.refusal == "calibration_too_small":
        insufficient.append("calibration_too_small")
    elif band.refusal == "band_not_finite":
        not_promotable.append("band_not_finite")
    m = len(evidence.test_scores)
    minimum = h_min(m)
    if minimum is None:
        insufficient.append("test_too_small")
    hits: int | None = None
    lower: float | None = None
    if band.q_hat is not None:
        hits = coverage_hits(evidence.test_scores, band.q_hat)
        lower = clopper_pearson_lower(hits, m)
        if band.q_hat > 1.0:
            not_promotable.append("width_limit_exceeded")
        if minimum is not None and hits < minimum:
            not_promotable.append("coverage_bound_below_minimum")
    if evidence.gradient_errors is None:
        insufficient.append("gradient_check_incomplete")
    else:
        errors = [_finite_nonnegative(e, "gradient error") for e in evidence.gradient_errors]
        if not errors:
            raise ValueError("gradient_errors is empty: a registered plan has gradient centres")
        if max(errors) > RHO_G:
            not_promotable.append("gradient_limit_exceeded")
    if evidence.inadmissible > 0:
        not_promotable.append("inadmissible_prediction")
    if evidence.extrapolated > 0:
        not_promotable.append("parent_extrapolated")
    verdict: Verdict = (
        "INSUFFICIENT_EVIDENCE"
        if insufficient
        else "NOT_PROMOTABLE"
        if not_promotable
        else "PROMOTABLE"
    )
    return StudyVerdict(
        verdict=verdict,
        insufficient=tuple(insufficient),
        not_promotable=tuple(not_promotable),
        n=band.n,
        k=band.k,
        q_hat=band.q_hat,
        m=m,
        hits=hits,
        h_min=minimum,
        lower_bound=lower,
    )
