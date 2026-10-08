"""M03 WO-7a: the optimization report's status rule (spec §8.5, Amendment 1; ADR 0032 D3) — A47.

The rule is one pure function of `(Ipopt status, V1-V5 outcomes)` per start, `classify_starts`, in
default-gate code that imports no third-party solver (G6 walks its module), so it is judged here on
synthetic per-start inputs and needs no Ipopt. WO-8's adapter calls it and computes no status of its
own. A start is classified by the first rule that applies — V1-V5 pass, Ipopt claimed a solution,
Ipopt reported infeasibility, anything else — and the report takes the highest classification
under `KKT_POINT_VERIFIED` > `NOT_VERIFIED` > `INFEASIBLE_REPORTED` > `SOLVER_FAILED`: a refuted
claim of success is never masked by Ipopt's local, heuristic infeasibility verdict (case e).
"""

from __future__ import annotations

import pytest

from openflowsheet.studies.nlp.closure import (
    IPOPT_STATUS_NAMES,
    STATUS_PRECEDENCE,
    StartEvidence,
    classify_starts,
)
from openflowsheet.studies.nlp.verification import CHECKS

K, NV, IR, SF = STATUS_PRECEDENCE

#: V1-V5 all `pass`, and V6 recorded.
VERIFIED = dict.fromkeys(CHECKS, "pass")
#: A point was returned and re-solved, and the reduced KKT check refuted it.
REFUTED = {**VERIFIED, "V5": "fail"}


def start(ipopt_status: int | None, verified: bool | None) -> StartEvidence:
    """A synthetic start: `verified` None means it returned no decisions (nothing to verify)."""
    if verified is None:
        return StartEvidence(ipopt_status, {}, "the adapter raised before Ipopt returned")
    return StartEvidence(ipopt_status, VERIFIED if verified else REFUTED)


#: Spec A47's thirteen cases: the starts, their classifications, the report's status.
CASES = {
    "a": ([(0, True)], [K], K),
    "b": ([(0, False)], [NV], NV),
    "c": ([(2, False)], [IR], IR),
    "d": ([(-1, False)], [SF], SF),
    "e": ([(2, False), (0, False)], [IR, NV], NV),
    "f": ([(0, False), (2, False)], [NV, IR], NV),
    "g": ([(2, False), (-1, False)], [IR, SF], IR),
    "h": ([(-1, True)], [K], K),
    "i": ([(2, True)], [K], K),
    "j": ([(0, True), (0, False)], [K, NV], K),
    "k": ([(1, False), (-2, False), (2, False)], [NV, SF, IR], NV),
    "l": ([(3, False)], [SF], SF),
    "m": ([(None, None)], [SF], SF),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_a47_each_start_is_classified_and_the_status_is_the_highest(case: str) -> None:
    starts, classifications, status = CASES[case]
    verdict = classify_starts([start(*item) for item in starts])
    assert list(verdict.classifications) == classifications
    assert verdict.status == status
    # `reasons`: one entry per start not verified, in start order, its classification the code.
    expected = [
        (classification, f"start {index}")
        for index, classification in enumerate(classifications)
        if classification != K
    ]
    assert [(reason.code, reason.subject) for reason in verdict.reasons] == expected
    if status != K:
        assert len(verdict.reasons) == len(starts)
        assert verdict.verified_starts == ()  # the candidate is null
        assert verdict.local_stationarity is False
    else:
        assert verdict.local_stationarity is True
        assert verdict.verified_starts == tuple(
            index for index, item in enumerate(classifications) if item == K
        )


def test_a47_case_j_keeps_the_refuted_start_visible_beside_the_verified_candidate() -> None:
    verdict = classify_starts([start(0, True), start(0, False)])
    (reason,) = verdict.reasons
    assert (reason.code, reason.subject) == (NV, "start 1")
    assert "Solve_Succeeded (0)" in reason.detail
    assert "failing V checks: V5" in reason.detail


def test_a47_the_detail_names_ipopts_status_and_what_was_not_evaluated() -> None:
    no_point = classify_starts([start(None, None)]).reasons[0]
    assert no_point.detail.startswith("no Ipopt status; failing V checks: none")
    assert "not evaluated: V1, V2, V3, V4, V5" in no_point.detail
    assert "the adapter raised" in no_point.detail
    small = classify_starts([start(3, False)]).reasons[0]
    assert small.detail.startswith("Ipopt Search_Direction_Becomes_Too_Small (3)")
    assert IPOPT_STATUS_NAMES[2] == "Infeasible_Problem_Detected"
    unknown = classify_starts([start(-7, False)]).reasons[0]
    assert unknown.code == SF and "unknown status (-7)" in unknown.detail


def test_a47_v2_not_evaluated_is_not_verified_whatever_ipopt_said() -> None:
    """Spec §8.5: without an optimizer's state V2 is `not_evaluated`, so the start is not
    `KKT_POINT_VERIFIED` (A32's reference optimum is such a point)."""
    without_v2 = {**VERIFIED, "V2": "not_evaluated"}
    verdict = classify_starts([StartEvidence(0, without_v2)])
    assert verdict.status == NV
    assert "not evaluated: V2" in verdict.reasons[0].detail
    # V6 records values and decides nothing.
    assert classify_starts([StartEvidence(4, {**VERIFIED, "V6": "fail"})]).status == K


def test_each_start_record_carries_its_classification() -> None:
    verdict = classify_starts([start(2, False), start(0, False)])
    records = verdict.start_records([{"ipopt_status": 2}, {"ipopt_status": 0}])
    assert [record["classification"] for record in records] == [IR, NV]
    assert records[0]["ipopt_status"] == 2
    with pytest.raises(ValueError, match="2 classified starts"):
        verdict.start_records([{}])
    with pytest.raises(ValueError, match="the rule"):
        verdict.start_records([{"classification": K}, {}])


def test_malformed_evidence_is_refused() -> None:
    with pytest.raises(ValueError, match="before any solve"):
        classify_starts([])
    with pytest.raises(ValueError, match="not V checks"):
        StartEvidence(0, {"V7": "pass"})
    with pytest.raises(ValueError, match="not check outcomes"):
        StartEvidence(0, {"V1": "passed"})  # type: ignore[dict-item]
