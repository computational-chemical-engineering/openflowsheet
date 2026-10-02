"""K04 §10: the structured failure, and the two things it must never say.

Blueprint §8.2: "an injected failure must not become a successful certificate through
fallback." So a bundle carries no verdict word at all — not even `UNVERIFIED`, which would
read as a judgement on a state nobody judged. A budget-exhausted iterate that happens to
satisfy every check still reads as the failure it is.

Blueprint §7.7: no infeasibility claim, ever. `PHYSICALLY_INFEASIBLE` is deliberately absent
from K03's outcome vocabulary, and the type refuses to let it back in as prose.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify.failure import (
    TAXONOMY,
    VERDICT_WORDS,
    FailureBundle,
    InfeasibilityClaimError,
    SuggestedActionEntry,
    bundle_for,
)


def capped_solve() -> tuple[Any, Any]:
    import sys

    from conftest import REPO_ROOT

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import flowsheet

    policy = SolvePolicy(
        policy_id="SYN-001-capped", residual_tolerances={}, scales={}, max_property_calls=20
    )
    return solve_tear(flowsheet(), policy=policy)


def test_a21_the_capped_budget_bundle_is_complete() -> None:
    """§10.2's first row, with the budget actually consumed against its cap."""
    result, trace = capped_solve()
    bundle = bundle_for(result, trace)

    assert bundle.outcome == "BUDGET_EXHAUSTED"
    assert bundle.taxonomy == "budget/cancellation outcomes"
    assert bundle.observations["counters"]["property_calls"] == 20
    assert bundle.best_checkpoint is None, "nothing was accepted, so there is nothing to carry"
    assert [entry.action for entry in bundle.suggested_actions] == ["increase_budget"]
    assert all(entry.requires_permission for entry in bundle.suggested_actions)

    document = bundle.as_document()
    for required in (
        "outcome",
        "taxonomy",
        "observations",
        "inferred_causes",
        "implicated_sources",
        "attempt_tree",
        "replay_identity",
        "suggested_actions",
    ):
        assert required in document, required
    assert document["inferred_causes"] == [], "empty, and present rather than absent"


def test_a20_a_bundle_carries_no_verdict_word() -> None:
    """§8.3 and A20. The rule is enforced by the type, not by reviewer attention."""
    result, trace = capped_solve()
    bundle = bundle_for(result, trace)
    serialized = json.dumps(bundle.as_document())
    for word in VERDICT_WORDS:
        assert word not in serialized, word

    # And it is enforced, not merely observed: smuggling one in is refused.
    with pytest.raises(ValueError, match="no verdict word"):
        FailureBundle(
            outcome="STAGNATION",
            taxonomy=TAXONOMY["STAGNATION"],
            observations={"note": "the state looked VERIFIED to me"},
            inferred_causes=(),
            implicated_sources=(),
            attempt_tree=(),
            replay_identity={},
        )


def test_a20_every_outcome_with_a_class_can_be_bundled() -> None:
    """An outcome code is not a verdict: `INITIALIZATION_FAILED`, `LINEAR_SOLVE_FAILED` and
    `LINE_SEARCH_FAILED` bundles are buildable (they were not, until T02 A16 built one), and the
    exemption is exactly the codes
    that need it — every code in the vocabulary containing a verdict word, and no other."""
    from typing import get_args

    from openflowsheet.orchestrator.trace import SolveOutcome
    from openflowsheet.verify.failure import OUTCOME_CODES_WITH_VERDICT_WORDS

    codes = get_args(SolveOutcome)
    needing = {code for code in codes if any(word in code for word in VERDICT_WORDS)}
    assert set(OUTCOME_CODES_WITH_VERDICT_WORDS) == needing
    for code in codes:
        if code in TAXONOMY:
            FailureBundle(
                outcome=code,
                taxonomy=TAXONOMY[code],
                observations={"message": code},
                inferred_causes=(),
                implicated_sources=(),
                attempt_tree=(),
                replay_identity={},
            )
    with pytest.raises(ValueError, match="no verdict word"):
        FailureBundle(
            outcome="LINEAR_SOLVE_FAILED",
            taxonomy=TAXONOMY["LINEAR_SOLVE_FAILED"],
            observations={"message": "the linear solve FAILED"},
            inferred_causes=(),
            implicated_sources=(),
            attempt_tree=(),
            replay_identity={},
        )


def test_no_bundle_may_claim_infeasibility() -> None:
    """Blueprint §7.7: a solver reports that *it* failed, never that no answer exists.

    K03 leaves `PHYSICALLY_INFEASIBLE` out of its fifteen outcomes deliberately. The risk is
    that it returns as an inferred cause or a message, where it would read like a conclusion
    about the process rather than about the solver.
    """
    with pytest.raises(InfeasibilityClaimError):
        FailureBundle(
            outcome="STAGNATION",
            taxonomy=TAXONOMY["STAGNATION"],
            observations={},
            inferred_causes=({"hypothesis": "the specification is physically infeasible"},),
            implicated_sources=(),
            attempt_tree=(),
            replay_identity={},
        )


def test_observations_and_inferences_are_separate_fields() -> None:
    """Blueprint §8.2: "distinguish observations from inferred causes".

    A bundle is read by someone deciding what to do next, and a guess formatted like a
    measurement is worse than no guess. The type keeps them apart; this asserts that a caller
    supplying an inference cannot land it among the observations.
    """
    result, trace = capped_solve()
    bundle = bundle_for(
        result,
        trace,
        inferred=({"hypothesis": "the cap is too small for a cold start", "evidence_refs": []},),
        implicated=("U-MIX",),
    )
    assert len(bundle.inferred_causes) == 1
    assert "hypothesis" in bundle.inferred_causes[0]
    assert "hypothesis" not in bundle.observations
    assert bundle.implicated_sources == ("U-MIX",)
    # Every observation is a measurement the solve actually produced.
    assert bundle.observations["attempts"] == result.attempts
    assert bundle.observations["iterations"] == result.iterations


def test_every_k03_outcome_has_a_class_and_an_action() -> None:
    """§10.1: the map is total over K03's vocabulary, minus the one success.

    A missing entry would surface as an exception at the worst moment — while reporting some
    other failure — so it is checked against the outcome literal rather than a hand-written
    list.
    """
    from typing import get_args

    from openflowsheet.orchestrator.trace import SolveOutcome
    from openflowsheet.verify.failure import ACTIONS

    outcomes = set(get_args(SolveOutcome)) - {"CONVERGED"}
    assert outcomes <= set(TAXONOMY), sorted(outcomes - set(TAXONOMY))
    assert set(TAXONOMY.values()) <= set(ACTIONS), "a class with no suggested action"
    assert "PHYSICALLY_INFEASIBLE" not in outcomes


def test_a_suggested_action_is_a_proposal_and_never_executable() -> None:
    """§10.1: typed entries from a registered vocabulary, and permission always required."""
    entry = SuggestedActionEntry(action="increase_budget", preconditions="the cap was reached")
    assert entry.requires_permission is True
    document = entry.as_document()
    assert set(document) == {"action", "preconditions", "requires_permission"}
    assert isinstance(document["action"], str)
