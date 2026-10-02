"""T06 W6: the ensemble harness — scoring, the gate, the reports, replay (T6-A27…A36, A66, A84).

Spec `docs/derivations/T06-corpus-spec.md` §6.6, §7, §10 as amended (Amendments 1–3); the
harness is `benchmarks/t06/ensemble.py`. The scoring run itself (440 starts, A28–A30 measured) is
the design lane's WO9 and waits for Frank's decision on ADR 0017; what is asserted here is the
machinery: the classification is a pure function of the record (A27), the gate and the reports
recompute from records (A30, A31, A66), the report carries §7.4's wording verbatim (A84), and a
handful of published starts — the smoke set, start 00 of five cases covering the three paths and
the restart — run, record their times and counters (A36), carry A32's and A33's checks, and
replay `MATCH` on this machine class (A34).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import cache
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t06_ensemble_support import ensemble_cases
from test_t06_w6_generator import BY_CASE, PUBLISHED

import openflowsheet.orchestrator.executor as executor_module
import openflowsheet.verify.regularity as regularity_module
from benchmarks.t06 import ensemble
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.trace import SolveOutcome
from openflowsheet.verify.failure import TAXONOMY

SPEC = (REPO_ROOT / "docs" / "derivations" / "T06-corpus-spec.md").read_text("utf-8")
TWIN: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")
CASES = {case.case: case for case in ensemble_cases()}
#: The smoke set: start 00 of the tear path (NET-01), the legacy EO path (NET-05), an acyclic
#: revision case (STR-01) and the two revision cases the smoke run saw rescued (NET-02, NET-11).
SMOKE = ("STR-01", "NET-01", "NET-02", "NET-05", "NET-11")


# -- A27: the classification -------------------------------------------------------------------


def _record(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "case": "X",
        "start": 0,
        "generation_failure": None,
        "crash": None,
        "outcome": "CONVERGED",
        "certificate": {
            "verdict": "VERIFIED",
            "regularity_status": "NO_RANK_LOSS_DETECTED",
            "not_passed": [],
            "rcond_1": 1e-3,
            "b": 1e-12,
            "root_fingerprint": None,
        },
        "worst": [0.5, "S1.T"],
        "times": {"compile": 0.0, "init": 0.0, "solve": 0.1, "verify": 0.1, "total": 0.2},
        "eo_recovery": None,
        "sources": ["user_guess"],
    }
    base.update(fields)
    return base


def _certificate(**fields: Any) -> dict[str, Any]:
    certificate = dict(_record()["certificate"])
    certificate.update(fields)
    return certificate


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        (_record(), "SUCCESS"),
        (_record(generation_failure="joint_cap", crash="x", outcome=None), "F-GEN"),
        (_record(crash="solve: ValueError: x", outcome=None), "F-CRASH"),
        (_record(times={"total": 60.5}), "F-TIME"),
        (_record(times={"total": 60.0}), "SUCCESS"),
        (_record(outcome="BUDGET_EXHAUSTED", certificate=None), "F-BUDGET"),
        (_record(outcome="ATTEMPTS_EXHAUSTED", certificate=None), "F-BUDGET"),
        (_record(outcome="BOUND_BLOCKED", certificate=None), "F-TYPED(BOUND_BLOCKED)"),
        (_record(certificate=_certificate(verdict="FAILED")), "F-FALSE-SUCCESS-CAUGHT"),
        (
            _record(
                certificate=_certificate(verdict="UNVERIFIED", regularity_status="RANK_DEFICIENT")
            ),
            "F-UNVERIFIED(RANK_DEFICIENT)",
        ),
        (
            _record(certificate=_certificate(verdict="UNVERIFIED", not_passed=["a.b"])),
            "F-UNVERIFIED(a.b)",
        ),
        (_record(certificate=_certificate(verdict="RELAXED")), "F-UNVERIFIED(RELAXED)"),
        (_record(worst=[1.0000001, "S3.T"]), "F-OTHER-ROOT"),
        (_record(worst=[1.0, "S3.T"]), "SUCCESS"),
    ],
)
def test_a27_the_classification_is_first_match_on_the_record(
    record: dict[str, Any], expected: str
) -> None:
    assert ensemble.classify(record) == expected
    assert ensemble.classify(record) == expected  # a pure function: no state between calls


def test_a27_every_non_converged_outcome_has_exactly_one_class() -> None:
    outcomes = [o for o in SolveOutcome.__args__ if o != "CONVERGED"]  # type: ignore[attr-defined]
    for outcome in outcomes:
        label = ensemble.classify(_record(outcome=outcome, certificate=None))
        budget = TAXONOMY[outcome] == "budget/cancellation outcomes"
        assert label == ("F-BUDGET" if budget else f"F-TYPED({outcome})")


def test_a66_a_start_is_rescued_iff_the_edge_was_taken_and_the_restart_opened_an_item() -> None:
    restart = revision.RESTART_INITIALIZER_ID
    assert ensemble.rescued(_record(eo_recovery="taken", sources=["user_guess", restart]))
    assert not ensemble.rescued(_record(eo_recovery="taken", sources=["user_guess"]))
    assert not ensemble.rescued(_record(eo_recovery="unsupported", sources=["user_guess"]))
    assert not ensemble.rescued(_record(eo_recovery=None, sources=[restart]))


# -- A30, A31, A66: the gate and the reports recompute from records ----------------------------


def test_a31_the_clopper_pearson_bound_is_the_twins_table() -> None:
    table = TWIN["closed_form"]["gate"]["clopper_pearson_one_sided_95_lower"]
    assert sorted(int(s) for s in table) == list(range(410, 441))
    for successes, registered in table.items():
        assert f"{ensemble.clopper_pearson_lower(int(successes), 440):.12f}" == registered


@cache
def _facts() -> dict[str, dict[str, Any]]:
    return {case.case: ensemble.facts(case) for case in ensemble_cases()}


def _full(
    fail: Callable[[str, int], dict[str, Any] | None] = lambda case, start: None,
) -> list[dict[str, Any]]:
    """440 synthetic records over the registered cases; `fail` may replace any of them."""
    records = []
    for case in _facts():
        for start in range(20):
            replaced = fail(case, start)
            records.append(replaced if replaced is not None else _record(case=case, start=start))
    return records


def _typed(case: str, start: int) -> dict[str, Any]:
    return _record(case=case, start=start, outcome="STAGNATION", certificate=None)


def test_a30_the_gate_is_s_at_least_418_of_440_with_no_crash_and_no_other_root() -> None:
    def failing(count: int) -> Callable[[str, int], dict[str, Any] | None]:
        cut = {(case, start) for case in _facts() for start in range(20)}
        chosen = sorted(cut)[:count]
        return lambda case, start: _typed(case, start) if (case, start) in chosen else None

    assert ensemble.report(_full(failing(22)), _facts(), PUBLISHED)["gate"]["pass"]
    assert not ensemble.report(_full(failing(23)), _facts(), PUBLISHED)["gate"]["pass"]
    crash = _full(
        lambda c, s: _record(case=c, start=s, crash="x", outcome=None)
        if s == 0 and c == "NET-01"
        else None
    )
    assert not ensemble.report(crash, _facts(), PUBLISHED)["gate"]["pass"]
    other = _full(
        lambda c, s: _record(case=c, start=s, worst=[2.0, "S3.T"])
        if s == 0 and c == "NET-01"
        else None
    )
    summary = ensemble.report(other, _facts(), PUBLISHED)
    assert summary["S"] == 439 and not summary["gate"]["pass"]
    partial = [r for r in _full() if r["case"] != "NET-11"]
    assert not ensemble.report(partial, _facts(), PUBLISHED)["gate"]["pass"]


def test_a31_a66_per_case_counts_and_both_bounds_recompute_from_the_records() -> None:
    restart = revision.RESTART_INITIALIZER_ID

    def mixed(case: str, start: int) -> dict[str, Any] | None:
        if case == "NET-02" and start < 6:
            return _record(
                case=case, start=start, eo_recovery="taken", sources=["user_guess", restart]
            )
        if case == "NET-03" and start < 2:
            return _typed(case, start)
        return None

    summary = ensemble.report(_full(mixed), _facts(), PUBLISHED)
    assert (summary["N"], summary["S"], summary["S_first"], summary["S_rescued"]) == (
        440,
        438,
        432,
        6,
    )
    net02, net03 = summary["per_case"]["NET-02"], summary["per_case"]["NET-03"]
    assert (net02["s"], net02["s_first"], net02["s_rescued"]) == (20, 14, 6)
    assert (net03["s"], net03["s_first"], net03["classes"]) == (
        18,
        18,
        {"F-TYPED(STAGNATION)": 2, "SUCCESS": 18},
    )
    for case in summary["per_case"].values():
        assert case["s_first"] + case["s_rescued"] == case["s"]
    assert summary["cp_lower"] == ensemble.clopper_pearson_lower(438, 440)
    assert summary["cp_lower_first"] == ensemble.clopper_pearson_lower(432, 440)
    assert (summary["cases_p1"], summary["cases_below_1"], summary["cases_below_0p8"]) == (21, 1, 0)
    assert list(summary["per_case"]) == [entry["case"] for entry in PUBLISHED["cases"]]


# -- A84: the report's wording ------------------------------------------------------------------


def _quoted(opening: str) -> str:
    """The spec's italic quotation that begins `opening`, as written."""
    match = re.search(r'\*"(' + re.escape(opening) + r'.*?)"\*', SPEC, re.S)
    assert match is not None, opening
    return " ".join(match.group(1).split())


def test_a84_the_statements_are_the_specs_verbatim() -> None:
    assert ensemble.RESCUE_STATEMENT == _quoted("A rescued start's outcome")
    acyclic = _quoted("On the <n> acyclic cases")
    assert ensemble.ACYCLIC_STATEMENT == acyclic.replace("<n>", "{n}").replace("<ids>", "{ids}")


def test_a84_the_report_carries_the_wording_and_the_acyclic_census_from_the_plans() -> None:
    text = ensemble.render(ensemble.report(_full(), _facts(), PUBLISHED))
    flat = " ".join(text.split())
    acyclic = [case for case, facts in _facts().items() if facts["acyclic"]]
    assert ensemble.RESCUE_STATEMENT in flat
    assert ensemble.ACYCLIC_STATEMENT.format(n=len(acyclic), ids=", ".join(acyclic)) in flat
    assert ensemble.DESIGNS_STATEMENT in flat
    # Measured (docs/t06-measurements.md, M7): ten cases have no loop, as the text says since A3;
    # on the full set the report prints no finding against the text.
    assert ensemble.ACYCLIC_TEXT_COUNT == 10
    assert acyclic == [
        "STR-01",
        "STA-01",
        "STA-05",
        "NUM-03",
        "THM-01",
        "THM-02",
        "THM-07",
        "THM-08",
        "THM-09",
        "THM-10",
    ]
    assert "finding against the text" not in flat
    for case in _facts():
        assert re.search(rf"\| {case} \| (yes|no) \| 20/20 \| 20/20 \| 0 \|", text), case


@pytest.mark.parametrize(("flip", "count"), [("NET-01", 11), ("THM-09", 9)])
def test_a84_a_count_other_than_the_texts_is_reported_as_a_finding(flip: str, count: int) -> None:
    """(A3) A constructed census that counts otherwise than ten prints the finding line; the
    flag itself is reported as the plans give it, never corrected to the text."""
    facts = {case: dict(entry) for case, entry in _facts().items()}
    facts[flip]["acyclic"] = not facts[flip]["acyclic"]
    flat = " ".join(ensemble.render(ensemble.report(_full(), facts, PUBLISHED)).split())
    assert f"says 10 acyclic cases; the plans count {count}." in flat
    assert "This is a finding against the text (A84)" in flat


# -- the smoke set: run, record, replay (A32, A33, A34, A36) --------------------------------------


@cache
def _smoke(case: str) -> dict[str, Any]:
    (start,) = [s for s in BY_CASE[case]["starts"] if s["start"] == 0]
    return ensemble.run_start(CASES[case], start)


@pytest.mark.parametrize("case", SMOKE)
def test_a36_a32_a33_a_smoke_start_records_its_times_counters_and_checks(case: str) -> None:
    record = _smoke(case)
    assert record["crash"] is None, record["crash"]
    assert ensemble.classify(record) == "SUCCESS", record
    times = record["times"]
    assert set(times) == {"compile", "init", "solve", "verify", "total"}
    assert all(value >= 0.0 for value in times.values())
    assert times["total"] >= times["compile"] + times["solve"] + times["verify"] - 1e-9
    assert times["total"] <= ensemble.CEILING_S
    assert record["counters"]["property_calls"] > 0 and record["iterations"] >= 0
    assert record["events"][0][0] == "plan_built" and record["events"][-1][0] == "solve_closed"
    assert record["a32"] and all(c["lower"] and c["agree"] for c in record["a32"])
    assert record["a33"] == {"ok": True, "problems": []}
    if CASES[case].path == "revision_eo":
        assert record["sources"][0] == "user_guess"


def test_the_smoke_set_meets_its_paths_and_the_restart() -> None:
    assert [CASES[case].path for case in SMOKE] == [
        "revision_eo",
        "tear",
        "revision_eo",
        "legacy_eo",
        "revision_eo",
    ]
    assert [ensemble.rescued(_smoke(case)) for case in SMOKE] == [False, False, True, False, True]


@pytest.mark.parametrize("case", SMOKE)
def test_a34_a_replayed_start_matches_its_record(case: str) -> None:
    (start,) = [s for s in BY_CASE[case]["starts"] if s["start"] == 0]
    emitted = ensemble.run_start(CASES[case], start)
    assert ensemble.replay_differences(_smoke(case), emitted) == []


def test_a_run_restores_every_entry_point_and_records_a_crash_rather_than_raising() -> None:
    originals = (
        executor_module.compile_problem,
        executor_module.solve_tear,
        revision.traversal_start,
        revision.restart_start,
        regularity_module.screen,
    )
    case = CASES["STR-01"]

    def broken() -> dict[str, Any]:
        raise RuntimeError("the revision could not be read")

    crashing = ensemble.EnsembleCase(
        case.case, case.fixture, case.path, case.policy, broken, case.root
    )
    (start,) = [s for s in BY_CASE["STR-01"]["starts"] if s["start"] == 0]
    record = ensemble.run_start(crashing, start)
    assert record["crash"] == "harness: RuntimeError: the revision could not be read"
    assert ensemble.classify(record) == "F-CRASH"
    _smoke("STR-01")
    assert (
        executor_module.compile_problem,
        executor_module.solve_tear,
        revision.traversal_start,
        revision.restart_start,
        regularity_module.screen,
    ) == originals
    failure = ensemble.generation_failure_record(case, {"start": 3, "reason": "joint_cap"})
    assert ensemble.classify(failure) == "F-GEN"
