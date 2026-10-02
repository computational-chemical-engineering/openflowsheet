"""T06 W6, T6-A32 (A2): §8.3's exact-norm check at every certificate the corpus issues.

Spec `docs/derivations/T06-corpus-spec.md` §8.1 (A2) and §8.3 (A2): the seeded `onenormest` is
deterministic, not exact, so wherever a corpus certificate screens a matrix the exact `‖Ĵ⁻¹‖₁`
(dense inverse; every T06 matrix has `n ≤ 128`) is computed, the estimate must not exceed it by
more than 1e-12 relative, and the decision the screen takes with the exact norm — `τ_ill`'s
relative test, K04 §7.4's absolute limit — must be the recorded one. The ensemble's certified
states carry the same check in their records (`benchmarks/t06/ensemble.py`, `a32`).

Each certificate is re-issued here with the screen captured (`ensemble.captured_screens`), from
the solve its registration names: A02's revision-built runs (W5's), its tear-path cases (NET-01,
THM-03, THM-04, STA-03's two unit variants), NUM-04's region at the tear root, NET-05 (A02-360,
with 355 and 365 as its regression variants) and ADV-01 (HOM-01) on the bound declaration
(T04's), A47's our-side REF solves and PC-2 (W8's), STR-05's twin CH-UP-DP (T05b B31 (i)), and
VER-01's twins — K04 INJ-1's is SYN-001-nominal's (NET-01 here), T05 INJ-T1's is VLV-2 at its
true root. **(W7)** ADV-06 L and M: C1 bound with `NoisyProvider` (`t06_adv06_support`) under the
revision path's registered `T06-revision-v2`, certified again here from the cached solve (H issues
no certificate: it ends `INITIALIZATION_FAILED`).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

import pytest
import scipy.sparse as sp
import test_t04_certificate as t04c
import test_t05_w12_injections as w12
import test_t05b_openings as openings
import test_t06_w5_corpus as w5
from conftest import REPO_ROOT
from t05_w12_support import planned_step
from t05b_support import POLICY_V2, solve_from_v2
from t06_adv06_support import adv06
from test_t06_w4_registry import BY_ID, CONSTRUCTED

from benchmarks.t06.ensemble import captured_screens, exact_norm_check
from openflowsheet.application.binding import Binding, bind_revision
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.verify.certificate import verify, verify_bound, verify_revision

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t06_references_ours as ours_side  # noqa: E402


def _revision(run: w5.Run) -> Callable[[], Any]:
    def issue() -> Any:
        solved = w5.solved(run)
        return verify_revision(
            solved.binding, solved.document, solved.run, solve_plan=solved.plan.steps[-1].solve_plan
        )

    return issue


def _tear(fixture: str, revision: str) -> Callable[[], Any]:
    def issue() -> Any:
        binding = bind_revision(w5._document(fixture, revision))
        assert isinstance(binding, Binding)
        result, _ = solve_tear(binding.flowsheet, policy=CONSTRUCTED["SYN-001-K03"])
        assert result.outcome == "CONVERGED"
        return verify(binding.flowsheet, result)

    return issue


def _bound(solved: Callable[[], Any]) -> Callable[[], Any]:
    def issue() -> Any:
        item = solved()
        return verify_bound(item.binding, item.document, item.result, solve_plan=item.solve_plan)

    return issue


def _ch_up_dp() -> Any:
    document, start = openings.CASES["CH-UP-DP"]()
    binding = openings.bind(document)
    result = solve_from_v2(binding, start)
    assert result.outcome == "CONVERGED"
    step = planned_step(binding, POLICY_V2)
    return verify_revision(
        binding, document, result, state=dict(result.state), solve_plan=step.solve_plan
    )


def _inj_t1_twin() -> Any:
    document = w12._valve()
    binding, solve_plan, run = w12._executed(document)
    return verify_revision(binding, document, run, solve_plan=solve_plan)


def _tear_fixtures() -> dict[str, Callable[[], Any]]:
    out = {}
    for case_id in ("NET-01", "THM-03", "THM-04"):
        case = BY_ID[case_id]
        out[f"tear:{case_id}"] = _tear(case["fixture"], case["revision"])
    for variant in BY_ID["STA-03"]["variants"]:
        out[f"tear:STA-03:{variant['fixture']}"] = _tear(variant["fixture"], variant["revision"])
    return out


def _adv06(level: str) -> Any:
    solved = adv06(level, "T06-revision-v2")
    assert solved.run.outcome == "CONVERGED"
    return verify_revision(
        solved.binding, solved.document, solved.run, solve_plan=solved.plan.steps[-1].solve_plan
    )


#: NUM-04 is certified inside its W5 test, which issues exactly that one certificate.
NUM04 = w5.test_a02_num04_the_region_at_the_tear_root_converges_at_iteration_0_and_is_verified

SOURCES: dict[str, Callable[[], Any]] = {
    **{
        f"revision:{run.case}:{run.fixture}:{run.policy}": _revision(run)
        for run in w5.REVISION_RUNS
    },
    **_tear_fixtures(),
    "NUM-04": NUM04,
    **{
        f"bound:{name}": _bound(lambda name=name: t04c.solved(name))
        for name in ("HOM-01", "SYN-001-A02-360", "SYN-001-A02-365")
    },
    "bound:SYN-001-A02-355": _bound(t04c.solved_355),
    **{
        f"REF:{fixture}": (lambda fixture=fixture: ours_side.solve(fixture))
        for fixture in ours_side.SOURCES
    },
    "STR-05-twin:CH-UP-DP": _ch_up_dp,
    "VER-01-twin:INJ-T1": _inj_t1_twin,
    "ADV-06:L": lambda: _adv06("L"),
    "ADV-06:M": lambda: _adv06("M"),
}


def test_the_sources_are_the_corpus_certificates() -> None:
    """A02's 23 revision runs (W5), five tear runs, NUM-04, four bound-declaration certificates,
    nine REF/PC-2 solves, the two twins, and ADV-06 L and M (W7)."""
    assert len(w5.REVISION_RUNS) == 23
    assert len(SOURCES) == 23 + 5 + 1 + 4 + len(ours_side.SOURCES) + 2 + 2
    assert sorted(ours_side.SOURCES) == sorted([f"REF-0{k}" for k in range(1, 9)] + ["PC-2"])


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_a32_the_estimate_is_a_lower_bound_and_the_exact_norm_decides_alike(source: str) -> None:
    captured: list[tuple[sp.csc_matrix, Any]] = []
    with captured_screens(captured):
        SOURCES[source]()
    assert captured, f"{source}: no matrix was screened"
    for matrix, evidence in captured:
        assert matrix.shape[0] <= 128
        check = exact_norm_check(matrix, evidence)
        assert check["lower"], (source, check)
        assert check["agree"], (source, check)
