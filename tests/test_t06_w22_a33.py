"""T06 W22: A33's amended wording in the ensemble harness (spec A33 (A4), §8.4 (A4); ruling 4;
register R-080 annotated).

The certificate qualifies a check iff the check consulted the provider. A33 (A1) asked for every
check whose id begins `energy_balance.`, `phase_admissibility.` or `independent_split.`; run 1 found
137 certificates where that fails, every missing id a `not_applicable` check (200 `ZERO_FLOW`, 94
`temperature_degenerate`). A33 (A4): the qualified ids are the prefixed checks whose `result` is
`pass` or `fail` — falsifiable both ways.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from test_t06_w5_corpus import REVISION_RUNS, solved

from benchmarks.t06 import ensemble
from openflowsheet.verify import dormant
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision


def _certified(case: str) -> tuple[SolutionCertificate, Any]:
    (run,) = [run for run in REVISION_RUNS if run.case == case]
    item = solved(run)
    certificate = verify_revision(
        item.binding, item.document, item.run, solve_plan=item.plan.steps[-1].solve_plan
    )
    return certificate, item.binding.flowsheet.provider


def _prefixed(certificate: SolutionCertificate) -> set[str]:
    return {check.id for check in certificate.checks if check.id.startswith(ensemble.A33_PREFIXES)}


@pytest.mark.parametrize(
    ("case", "reason"),
    [("STA-01", "ZERO_FLOW"), ("THM-09", "temperature_degenerate"), ("THM-01", None)],
)
def test_a33_a4_holds_where_a_prefixed_check_does_not_apply(case: str, reason: str | None) -> None:
    """STA-01 (T05b DZ-3, dormant streams) and THM-09 (T05b SC-3, degenerate splits) carry
    prefixed `not_applicable` checks with no entry: A33 (A4) holds, A33 (A1)'s set would not.
    THM-01 has none, and the two wordings agree."""
    certificate, provider = _certified(case)
    assert ensemble._a33(certificate, provider) == {"ok": True, "problems": []}
    qualified = {entry["check_id"] for entry in certificate.independence_qualifications}
    assert qualified == ensemble.a33_expected(certificate.checks)
    skipped = _prefixed(certificate) - qualified
    assert {check.reason for check in certificate.checks if check.id in skipped} == (
        {reason} if reason else set()
    )
    assert all(
        check.result == "not_applicable" for check in certificate.checks if check.id in skipped
    )


def test_a33_a4_fails_an_evaluated_prefixed_check_without_an_entry() -> None:
    certificate, provider = _certified("THM-01")
    entries = certificate.independence_qualifications
    assert len(entries) > 1
    constructed = dataclasses.replace(certificate, independence_qualifications=entries[1:])
    assert ensemble._a33(constructed, provider) == {
        "ok": False,
        "problems": ["qualified_check_ids"],
    }


def test_a33_a4_fails_an_entry_on_a_not_applicable_check() -> None:
    certificate, provider = _certified("THM-01")
    entry = certificate.independence_qualifications[0]
    (check,) = [c for c in certificate.checks if c.id == entry["check_id"]]
    assert check.result == "pass"
    constructed = dataclasses.replace(
        certificate,
        checks=tuple(
            dormant(id=c.id, category=c.category, subject=c.subject) if c is check else c
            for c in certificate.checks
        ),
    )
    assert ensemble._a33(constructed, provider) == {
        "ok": False,
        "problems": ["qualified_check_ids"],
    }
