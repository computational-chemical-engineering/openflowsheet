"""T06 W20: a revision-path solve records the property counts its meter charged (spec A93; brief
`docs/briefs/T06-scoring-round.md` item 3; ruling 3).

A region solve's counts were the last inner event's sample (`Trace`'s property sampler), so the
calls made after it — the phase controller between iterations, the call a budget refusal
interrupts — were charged against the budget and never recorded: run 1's THM-08 start 3 recorded
6 943 where the meter had refused its 10 001st call. Now each region step's counts are the meter's
own, so the closing event carries what the budget charged, and exactly `max_property_calls` at
`BUDGET_EXHAUSTED(property_calls)` (K03 §11.2; `SYN-001-capped-budget` on the tear path).

"Charged" is what the plan meters: calls made while a region's budget is set (`PropertyMeter.limit`
not `None`). An initializer's calls fall outside that window (T05 §2.2's rule) and were never in
the count.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest
from t06_ensemble_support import STARTS_FILE, ensemble_cases
from t06_support import T06_REVISION_POLICY, case_document
from test_t05b_contract import solve

from benchmarks.t06 import ensemble
from openflowsheet.orchestrator.budget import PropertyMeter

#: A93: run 1's three `F-BUDGET` starts; recorded 6 943, 6 902 and 9 250 before W20.
BUDGET_STARTS = [("THM-08", 3), ("THM-08", 12), ("THM-09", 4)]


def _start(case: str, index: int) -> tuple[Any, dict[str, Any]]:
    (entry,) = [c for c in ensemble_cases() if c.case == case]
    published = json.loads(STARTS_FILE.read_bytes())
    (starts,) = [e for e in published["cases"] if e["case"] == case]
    (start,) = [s for s in starts["starts"] if s["start"] == index]
    return entry, start


@pytest.mark.parametrize(("case", "index"), BUDGET_STARTS, ids=lambda v: str(v))
def test_a93_run_1s_budget_starts_record_the_cap(case: str, index: int) -> None:
    """Each of run 1's three `F-BUDGET` starts, re-run, records `property_calls` and
    `requested_evaluations` of exactly `max_property_calls` (10 000)."""
    entry, start = _start(case, index)
    record = ensemble.run_start(entry, start)
    assert record["crash"] is None, record["crash"]
    assert record["outcome"] == "BUDGET_EXHAUSTED", record["outcome"]
    cap = entry.policy.max_property_calls
    assert cap == 10_000
    assert record["counters"]["property_calls"] == cap
    assert record["counters"]["requested_evaluations"] == cap


def _charged(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Counts every call a `PropertyMeter` makes while a region's budget is set."""
    charged = [0]
    real = PropertyMeter._spend

    def spend(self: PropertyMeter, what: str) -> None:
        metered = self.limit is not None
        real(self, what)  # a refused call raises here and is not charged
        if metered:
            charged[0] += 1

    monkeypatch.setattr(PropertyMeter, "_spend", spend)
    return charged


@pytest.mark.parametrize("fixture", ["SYN-001-T06-THM01", "SYN-001-T06-NET11", "SYN-001-T06-NET02"])
def test_a93_the_closing_event_carries_the_meters_charge(
    fixture: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On revision-path solves (NET-02's through edge 3's restart, two region solves), the
    closing event's `property_calls` and `requested_evaluations` equal the calls the meter
    charged, with no cache hits."""
    charged = _charged(monkeypatch)
    solved = solve(case_document(fixture), T06_REVISION_POLICY)
    closing = solved.run.trace.events[-1]
    assert closing.kind == "solve_closed"
    assert closing.counters == solved.run.counters
    assert charged[0] > 0
    assert closing.counters.property_calls == charged[0]
    assert closing.counters.requested_evaluations == charged[0]
    assert closing.counters.cache_hits == 0


@pytest.mark.parametrize("fraction", [0.25, 0.5, 0.999])
def test_a93_an_exhausted_budget_records_exactly_the_cap(fraction: float) -> None:
    """NET-11 under its policy with the cap lowered below what its solve needs:
    `BUDGET_EXHAUSTED(property_calls)` and a closing `property_calls` of exactly the cap."""
    needed = solve(case_document("SYN-001-T06-NET11"), T06_REVISION_POLICY).run.counters
    cap = int(fraction * needed.property_calls)
    solved = solve(
        case_document("SYN-001-T06-NET11"), replace(T06_REVISION_POLICY, max_property_calls=cap)
    )
    assert solved.run.outcome == "BUDGET_EXHAUSTED", (solved.run.outcome, cap)
    closing = solved.run.trace.events[-1]
    assert closing.counters.property_calls == cap
    assert closing.counters.requested_evaluations == cap
