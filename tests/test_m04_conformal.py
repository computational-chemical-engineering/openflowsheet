"""M04.A04–A08: the finite-sample rule, the coverage test and the verdict function (spec §6–§7).

Pure functions against the design lane's generator (`benchmarks/m04/reference_values.json`): the
integer index k(n), the order-statistic q̂ with failed draws at +∞, the integer coverage test
H ≥ h_min(m), the Clopper–Pearson bound (reported, never decided on), and the sixteen verdict
vectors V01–V16, which between them reach all three verdicts and every reason of spec §7.3.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from fractions import Fraction
from math import comb
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from scipy.stats import binom

from openflowsheet.studies.surrogate import conformal as cf
from openflowsheet.studies.surrogate import plan as sp

REFERENCE: Mapping[str, Any] = load_json(REPO_ROOT / "benchmarks" / "m04" / "reference_values.json")
FINITE = REFERENCE["finite_sample"]
VECTORS = {vector["id"]: vector for vector in REFERENCE["verdict_vectors"]}
#: A06's tolerance on the Clopper–Pearson bound (spec §11): floor ≤ 1e-15 measured, ceiling 7e-4.
CP_TOLERANCE = 1e-9


def _scores(values: Sequence[str | None]) -> tuple[float | None, ...]:
    return tuple(None if v is None else float(v) for v in values)


def _evidence(document: Mapping[str, Any]) -> cf.StudyEvidence:
    gradient = document["gradient_errors"]
    return cf.StudyEvidence(
        budget_ok=document["budget_ok"],
        plan_complete=document["plan_complete"],
        training_ok=document["training_ok"],
        singular_value_ratio=float(document["singular_ratio"]),
        calibration_scores=_scores(document["calibration_scores"]),
        test_scores=_scores(document["test_scores"]),
        gradient_errors=None if gradient is None else tuple(float(e) for e in gradient),
        inadmissible=document["inadmissible"],
        extrapolated=document["extrapolated"],
    )


# -- the score (spec §6.1) ------------------------------------------------------------------------


def test_the_score_is_the_joint_max_scaled_by_the_width_limits() -> None:
    widths = REFERENCE["constants"]["width_limits"]
    assert (cf.WIDTH_X, cf.WIDTH_DT_K) == (widths["X"], widths["dT"])
    assert cf.score(0.16, 80.0, 0.16 + 0.0025, 80.0) == pytest.approx(1.0, rel=1e-12)
    assert cf.score(0.16, 80.0, 0.16, 80.0 - 3.0) == 2.0
    assert cf.score(0.16, 80.0, 0.16 - 0.00025, 80.0 + 0.75) == 0.5
    assert cf.score(0.16, 80.0, 0.16, 80.0) == 0.0
    with pytest.raises(ValueError, match="not finite"):
        cf.score(math.nan, 80.0, 0.16, 80.0)


# -- A04 ------------------------------------------------------------------------------------------


def test_a04_k_in_integers_for_every_registered_n() -> None:
    assert {str(n): cf.k_index(n) for n in map(int, FINITE["k"])} == FINITE["k"]
    assert cf.k_index(118) == 114 != math.ceil(0.95 * 118) == 113  # the ceiling correction
    assert cf.n_min() == FINITE["n_min"] == 19
    assert cf.k_index(18) == 19 > 18 and cf.k_index(19) == 19
    for n in range(0, 2000):  # the integer form is ⌈(n + 1)·19/20⌉ exactly
        assert cf.k_index(n) == math.ceil(Fraction(19 * (n + 1), 20))
    assert cf.conformal_band([0.1] * 18).refusal == "calibration_too_small"


# -- A05 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("vector_id", sorted(VECTORS))
def test_a05_q_hat_is_an_element_of_the_input(vector_id: str) -> None:
    vector = VECTORS[vector_id]
    expected = vector["expected"]["q_hat"]
    result = cf.study_verdict(_evidence(vector["input"]))
    if expected is None:
        assert result.q_hat is None
    else:
        assert result.q_hat is not None
        assert result.q_hat.hex() == float(expected).hex()
        assert result.q_hat in _scores(vector["input"]["calibration_scores"])
    # A band is absent exactly at V02 (k > n), V04 (+∞) and V15 (refused before running).
    assert (result.q_hat is None) == (vector_id in {"V02", "V04", "V15"})


def test_a05_failed_calibration_draws_widen_the_band_and_then_remove_it() -> None:
    """n = 118, k = 114: up to n − k = 4 failures (+∞) leave a finite band, a fifth removes it."""
    scores: list[float | None] = [(j + 1) / 1000 for j in range(118)]
    assert cf.conformal_band(scores).q_hat == 114 / 1000
    for failures in range(1, 5):
        scores[failures - 1] = None
        band = cf.conformal_band(scores)
        assert (band.n, band.k, band.refusal) == (118, 114, None)
        assert band.q_hat == (114 + failures) / 1000
    scores[4] = None
    band = cf.conformal_band(scores)
    assert (band.q_hat, band.refusal) == (None, "band_not_finite")


def test_a05_scores_are_finite_non_negative_or_none() -> None:
    for bad in (math.inf, math.nan, -1e-300):
        with pytest.raises(ValueError):
            cf.conformal_band([0.1] * 18 + [bad])
        with pytest.raises(ValueError):
            cf.coverage_hits([0.1, bad], 0.5)


# -- A06 ------------------------------------------------------------------------------------------


def test_a06_clopper_pearson_against_the_50_digit_values() -> None:
    worst = 0.0
    for row in FINITE["clopper_pearson"]:
        value = cf.clopper_pearson_lower(row["h"], row["m"])
        worst = max(worst, abs(value - float(row["lower_bound"])))
    assert worst <= CP_TOLERANCE, worst
    assert cf.clopper_pearson_lower(0, 300) == 0.0


def test_a06_h_min_and_m_min_exactly() -> None:
    assert {str(m): cf.h_min(m) for m in map(int, FINITE["h_min"])} == FINITE["h_min"]
    assert cf.m_min() == FINITE["m_min"] == 29
    assert cf.h_min(28) is None and cf.h_min(29) == 29
    for plan in (FINITE["registered_plan"], *FINITE["alternatives"]):
        assert cf.h_min(plan["m"]) == plan["h_min"]
        assert cf.k_index(plan["n"]) == plan["k"]


def test_a06_h_min_is_the_exact_binomial_boundary() -> None:
    """Independent of the integer form: the false-pass probabilities at h_min(300) and one below
    as exact rationals against the generator's 50 digits, and SciPy's binomial survival function."""
    registered = FINITE["registered_plan"]

    def tail(m: int, h: int) -> Fraction:
        return sum(
            (Fraction(comb(m, j)) * Fraction(9, 10) ** j * Fraction(1, 10) ** (m - j))
            for j in range(h, m + 1)
        ) or Fraction(0)

    at, below = tail(300, 279), tail(300, 278)
    assert abs(float(at) - float(registered["false_pass_at_minimum"])) <= 1e-15
    assert abs(float(below) - float(registered["false_pass_one_below_h_min"])) <= 1e-15
    assert at <= Fraction(1, 20) < below
    assert binom.sf(278, 300, 0.9) <= 0.05 < binom.sf(277, 300, 0.9)


@pytest.mark.parametrize("m", [29, 60, 118, 300])
def test_a06_the_integer_decision_equals_the_bound_decision(m: int) -> None:
    """H ≥ h_min(m) ⇔ L(H, m) ≥ 0.90 for every H; the nearest bound to 0.90 is reported."""
    minimum = cf.h_min(m)
    assert minimum is not None
    nearest = min(abs(cf.clopper_pearson_lower(h, m) - 0.9) for h in range(m + 1))
    assert nearest > 10 * CP_TOLERANCE, nearest
    for h in range(m + 1):
        assert (cf.clopper_pearson_lower(h, m) >= 0.9) == (h >= minimum), h


# -- A07 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("vector_id", sorted(VECTORS))
def test_a07_every_verdict_vector(vector_id: str) -> None:
    vector = VECTORS[vector_id]
    expected = vector["expected"]
    result = cf.study_verdict(_evidence(vector["input"]))
    assert result.verdict == expected["verdict"], vector["why"]
    assert list(result.insufficient) == expected["insufficient"]
    assert list(result.not_promotable) == expected["not_promotable"]
    assert result.k == expected["k"]
    assert result.hits == expected["hits"]
    if expected["lower_bound"] is None:
        assert result.lower_bound is None
    else:
        assert result.lower_bound is not None
        assert abs(result.lower_bound - float(expected["lower_bound"])) <= CP_TOLERANCE


def test_a07_the_vectors_reach_every_verdict_and_every_reason() -> None:
    verdicts = {v["expected"]["verdict"] for v in VECTORS.values()}
    assert verdicts == {"PROMOTABLE", "NOT_PROMOTABLE", "INSUFFICIENT_EVIDENCE"}
    reasons = {
        reason
        for v in VECTORS.values()
        for reason in (*v["expected"]["insufficient"], *v["expected"]["not_promotable"])
    }
    assert reasons == set(cf.INSUFFICIENT_REASONS) | set(cf.NOT_PROMOTABLE_REASONS)


def test_a07_reasons_are_recorded_in_the_order_of_the_table() -> None:
    """Every reason at once (IE and NP lists both in §7.3's order), and IE takes precedence."""
    evidence = cf.StudyEvidence(
        budget_ok=True,
        plan_complete=False,
        training_ok=35,
        singular_value_ratio=0.1,
        calibration_scores=(None,) * 19,
        test_scores=(0.05,) * 28,
        gradient_errors=None,
        inadmissible=2,
        extrapolated=1,
    )
    result = cf.study_verdict(evidence)
    assert result.verdict == "INSUFFICIENT_EVIDENCE"
    assert result.insufficient == (
        "plan_incomplete",
        "training_unidentifiable",
        "test_too_small",
        "gradient_check_incomplete",
    )
    assert result.not_promotable == (
        "band_not_finite",
        "inadmissible_prediction",
        "parent_extrapolated",
    )
    wide = cf.study_verdict(
        cf.StudyEvidence(
            budget_ok=True,
            plan_complete=True,
            training_ok=144,
            singular_value_ratio=0.1,
            calibration_scores=tuple(1.0 + j / 10 for j in range(19)),
            test_scores=(0.05,) * 28 + (5.0,),
            gradient_errors=(0.3,),
            inadmissible=0,
            extrapolated=0,
        )
    )
    assert wide.verdict == "NOT_PROMOTABLE"
    assert wide.not_promotable == (
        "width_limit_exceeded",
        "coverage_bound_below_minimum",
        "gradient_limit_exceeded",
    )


def test_a07_a_missing_ratio_or_no_gradient_centre() -> None:
    base = _evidence(VECTORS["V01"]["input"])
    unfitted = cf.study_verdict(cf.StudyEvidence(**{**base.__dict__, "singular_value_ratio": None}))
    assert unfitted.insufficient == ("training_unidentifiable",)
    with pytest.raises(ValueError, match="gradient_errors is empty"):
        cf.study_verdict(cf.StudyEvidence(**{**base.__dict__, "gradient_errors": ()}))


# -- A08 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("plan_id", "synthetic", "expected"),
    [("it1", False, (118, 114, 300, 279)), ("it1-prefix", True, (39, 38, 60, 59))],
)
def test_a08_the_plans_denominators(
    plan_id: str, synthetic: bool, expected: tuple[int, int, int, int]
) -> None:
    """n, k, m and h_min follow from the registered plan's counts; the manifest members that carry
    them (WO-5) must equal these, so no denominator can be narrowed by failures."""
    counts = sp.registered_plan(plan_id, synthetic_parent=synthetic).counts
    n, m = counts["calibration"], counts["test"]
    assert (n, cf.k_index(n), m, cf.h_min(m)) == expected
    # Failures keep the denominators: a calibration set with failed draws has the same n and k.
    band = cf.conformal_band([0.01] * (n - 2) + [None, None])
    assert (band.n, band.k) == (n, expected[1])
