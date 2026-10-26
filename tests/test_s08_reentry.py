"""S08 WO-3 — Stage B in `solve_column`: S08 design note §5.1, §5.4, §5.6, §5.7, §6.1 and §7 A05,
A06, A14 (a), (d), (e), A15 and A16; Amendment 1's A17 (§13.6, §5.4's candidate rows).

Expectations are the design note's: §6.1's new expectations for S02's P1 (the closed form
`ref.phase_case.P1` of `s02_reference.json`, and Stage A's held branch, the values S02 A12 held
before S08), §5.1's trigger, §5.6's records and §5.7's final answer. F1 and P3 are §6.2's (inline
in `test_s08_blocks.py`, equal to WO-G's registered inputs); A09 checks F1's root against WO-G's
50-digit record (`test_s08_roots.check_root`, WO-4). Each test names the assertion of §7 it
closes.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import replace
from functools import cache
from typing import Any

import pytest
from test_s02_column_wo1 import PROVIDER, SPECS, UNIT
from test_s02_column_wo2 import FLOW_ABS, FLOW_REL, T_ABS
from test_s02_column_wo3 import _closed_form, attempt_list
from test_s06_column_wo1 import J_CASES, U_SETS
from test_s06_column_wo2 import _stubbed
from test_s08_blocks import F1, P3
from test_s08_roots import check_root

import openflowsheet.models.syn001.cascade_solve as cascade_solve_module
import openflowsheet.models.syn001.column_blocks as blocks_module
import openflowsheet.models.syn001.column_solve as solve_module
from openflowsheet.canonical import state_sha256
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    liquid_id,
    stage_temperature_id,
    vapor_id,
)
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT, AcceptanceDefectError
from openflowsheet.models.syn001.column import profile_initial
from openflowsheet.models.syn001.column_blocks import BLOCK_ENDPOINT_ID, BlockEndpoint
from openflowsheet.models.syn001.column_solve import (
    NEAR_TRIVIAL_SPLIT,
    PRESOLVE_ID,
    REENTRY_OUTCOMES,
    BlockReentry,
    BubblePointEndpoint,
    ColumnSolution,
    acceptance_failures,
    bubble_point_endpoint,
    compile_column,
    reentry_trigger,
    regimes_of,
    saturation_errors,
    solve_column,
)
from openflowsheet.orchestrator.region import RegionResult

LIQUID5 = ("LIQUID",) * 5
#: §6.2: F1's (and P3's) block root, the candidate `(0, 2)`.
CORE3_L2 = ("TWO_PHASE",) * 3 + ("LIQUID",) * 2


@cache
def solved(name: str) -> ColumnSolution:
    """`solve_column` on P1, P3 or F1, unmutated, once per session."""
    spec = {"P1": SPECS["P1"], "P3": P3, "F1": F1}[name]
    answer = solve_column(spec, PROVIDER)
    assert isinstance(answer, ColumnSolution), answer
    return answer


def _source(result: RegionResult) -> str:
    """The `initializer_source` of a solve's attempt 0 (its certificate's)."""
    return str(result.branch_provenance[0]["initializer_source"])


def _state_digest(state: Mapping[str, float]) -> str:
    items = sorted((name, float(value).hex()) for name, value in state.items())
    return hashlib.sha256(repr(items).encode()).hexdigest()


def _result_fields(result: RegionResult | None) -> Any:
    """§9 G1's per-solve fields: the outcome and, per attempt, the signature, outcome,
    `solver_outcome`, iterations, reason and end state."""
    if result is None:
        return None
    return (
        result.outcome,
        result.message,
        tuple(
            (
                a.signature,
                a.outcome,
                a.solver_outcome,
                a.iterations,
                a.reason,
                _state_digest(a.end_state),
            )
            for a in result.attempts
        ),
        _state_digest(result.state),
    )


def reentry_digest(reentry: BlockReentry | None) -> str:
    """A digest of every field of a `reentry` record (region results by §9 G1's fields, so that
    cache counters, which depend on what ran before, do not enter)."""
    assert reentry is not None
    stage_a = reentry.stage_a
    fields = (
        reentry.trigger,
        reentry.accepted,
        (
            stage_a.outcome,
            stage_a.cause,
            stage_a.endpoint_sha256,
            stage_a.final_sha256,
            stage_a.failures,
            _result_fields(stage_a.result),
            _result_fields(stage_a.recovered_from),
        ),
        tuple(
            (
                c.a,
                c.c,
                c.signature,
                c.endpoint,
                c.endpoint_sha256,
                c.outcome,
                c.cause,
                _result_fields(c.result),
                _result_fields(c.recovered_from),
            )
            for c in reentry.candidates
        ),
    )
    return hashlib.sha256(repr(fields).encode()).hexdigest()


# -- the checks the mutations of A14 must break ----------------------------------------------------


def check_a05(answer: Any) -> None:
    """A05 (§6.1, top level): P1 is `CONVERGED` with signature LIQUID ×5 at the closed form
    `ref.phase_case.P1` within S02's state tolerance, every `v_j` zero and the distillate `+0.0`
    sign-checked; one attempt, LIQUID ×5, `CONVERGED` in ≤ 1 iteration, no recovery; its
    `initializer_source` is `s08-block-endpoint-v1` and its endpoint the block endpoint."""
    spec = SPECS["P1"]
    assert isinstance(answer, ColumnSolution), answer
    assert (answer.outcome, answer.cause) == ("CONVERGED", "")
    assert answer.signature == LIQUID5
    expected = _closed_form(spec)
    for j in spec.equilibrium_stages():
        name = stage_temperature_id(UNIT, j)
        assert abs(answer.state[name] - expected[name]) <= T_ABS, name
        for c in spec.components:
            name = liquid_id(UNIT, j, c)
            assert abs(answer.state[name] - expected[name]) <= FLOW_REL * expected[name] + FLOW_ABS
            assert answer.state[vapor_id(UNIT, j, c)] == 0.0
    for c in spec.components:
        top = answer.state[vapor_id(UNIT, 1, c)]
        assert top == 0.0 and math.copysign(1.0, top) == 1.0
    (attempt,) = answer.result.attempts
    assert tuple(regime for _, regime in attempt.signature) == LIQUID5
    assert attempt.outcome == "CONVERGED" and attempt.iterations <= 1
    assert answer.recovered_from is None
    assert _source(answer.result) == BLOCK_ENDPOINT_ID
    assert isinstance(answer.endpoint, BlockEndpoint)
    assert answer.endpoint.signature == LIQUID5


def check_a09_route(answer: Any) -> None:
    """A09 (§6.2, §7): F1's Stage A converges to a state that fails §8 on item 6 alone, at stage 4,
    by ≥ 0.1 K; Stage B's only candidate `(0, 2)` then gives an accepted `(2P, 2P, 2P, L, L)` root
    from the block endpoint, WO-G's root (state tolerance; `v_4`, `v_5` exactly `+0.0`)."""
    assert isinstance(answer, ColumnSolution), answer
    assert answer.outcome == "CONVERGED" and answer.signature == CORE3_L2
    reentry = answer.reentry
    assert reentry is not None and reentry.trigger == NEAR_TRIVIAL_SPLIT
    stage_a = reentry.stage_a
    assert (stage_a.outcome, stage_a.cause) == ("CONVERGED", f"{NEAR_TRIVIAL_SPLIT}(4)")
    assert stage_a.failures
    assert all(f.startswith("§8.6: TWO_PHASE stage 4: ") for f in stage_a.failures)
    regimes = regimes_of(F1, stage_a.result.attempts[-1].signature)
    errors = saturation_errors(F1, PROVIDER, stage_a.result.state, regimes)
    assert errors[4] >= 0.1, errors
    assert [(c.a, c.c, c.endpoint, c.outcome, c.cause) for c in reentry.candidates] == [
        (0, 2, "built", "CONVERGED", "")
    ]
    assert reentry.accepted == 0
    assert _source(answer.result) == BLOCK_ENDPOINT_ID
    declared = compile_column(F1, PROVIDER).spec
    regimes = dict(zip(F1.equilibrium_stages(), answer.signature, strict=True))
    assert acceptance_failures(F1, PROVIDER, declared, answer.state, regimes) == ()
    check_root("F1", answer)


# -- A05, A06: P1 (§6.1) -------------------------------------------------------------------------


def test_a05_p1_top_level() -> None:
    check_a05(solved("P1"))


def test_a06_p1_stage_a_is_the_held_branch() -> None:
    """A06 (§6.1): `reentry` has trigger `HOMOTOPY_STALLED`; `stage_a` is S02 A12's held branch
    exactly (outcome, cause, attempts, recovery), from §18.2's endpoint; one candidate `(0, 5)`,
    built and `CONVERGED`, accepted; the top level is that candidate's solve."""
    answer = solved("P1")
    reentry = answer.reentry
    assert reentry is not None and reentry.trigger == "HOMOTOPY_STALLED"
    stage_a = reentry.stage_a
    assert (stage_a.outcome, stage_a.cause) == (
        "HOMOTOPY_STALLED",
        "homotopy_stalled(BOUND_BLOCKED)",
    )
    assert stage_a.failures == ()
    two_phase, broken = ["TWO_PHASE"] * 5, ["TWO_PHASE", "LIQUID"] + ["TWO_PHASE"] * 3
    attempts = attempt_list(stage_a.result, stage_a.recovered_from)
    assert [(a["solve"], a["solver_outcome"], a["signature"]) for a in attempts] == [
        ("target", "BOUND_BLOCKED", two_phase),
        ("target", "LINE_SEARCH_FAILED", broken),
        ("edge 3", "HOMOTOPY_STALLED", two_phase),
    ]
    assert stage_a.recovered_from is not None
    assert stage_a.recovered_from.outcome == "ACTIVE_SET_CYCLING"
    # S08b A6 (§6.1, R-790): the stall's change list names the stage that moved.
    assert stage_a.recovered_from.message == (
        "active_set_cycling(S02.stage.1:TWO_PHASE,S02.stage.2:TWO_PHASE,S02.stage.3:TWO_PHASE,"
        "S02.stage.4:TWO_PHASE,S02.stage.5:TWO_PHASE; "
        "phase_wall(stall, S02.stage.2:LIQUID->TWO_PHASE))"
    )
    assert _source(stage_a.recovered_from) == PRESOLVE_ID
    # Stage A opened from §18.2's `x⁰`, rebuilt here.
    spec = SPECS["P1"]
    initial = profile_initial(spec, PROVIDER, DECLARATION_CONTEXT)
    assert not isinstance(initial, CascadeFailure)
    endpoint = bubble_point_endpoint(spec, PROVIDER, initial)
    assert isinstance(endpoint, BubblePointEndpoint)
    order = compile_column(spec, PROVIDER).spec.variable_ids
    assert stage_a.endpoint_sha256 == state_sha256(dict(endpoint.state), order)
    assert stage_a.final_sha256 == state_sha256(dict(stage_a.result.state), order)
    (candidate,) = reentry.candidates
    assert (candidate.a, candidate.c, candidate.signature) == (0, 5, LIQUID5)
    assert (candidate.endpoint, candidate.outcome, candidate.cause) == ("built", "CONVERGED", "")
    assert reentry.accepted == 0
    assert candidate.endpoint_sha256 == answer.endpoint_sha256
    assert candidate.result is answer.result and candidate.recovered_from is None
    assert answer.final_sha256 == state_sha256(dict(answer.state), order)


# -- A15: determinism ----------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["P1", "P3"])
def test_a15_stage_b_is_deterministic(name: str) -> None:
    """A15: P1 and P3 solved twice give identical final `state_sha256` and `reentry` records."""
    spec = {"P1": SPECS["P1"], "P3": P3}[name]
    first, second = (solve_column(spec, PROVIDER) for _ in range(2))
    assert isinstance(first, ColumnSolution) and isinstance(second, ColumnSolution)
    assert first.outcome == "CONVERGED" and first.reentry is not None
    assert first.reentry.accepted == 0
    assert first.final_sha256 == second.final_sha256
    assert first.endpoint_sha256 == second.endpoint_sha256
    assert reentry_digest(first.reentry) == reentry_digest(second.reentry)


def test_p3_goes_through_stage_b() -> None:
    """P3 (§6.2): Stage A typed, then the candidate `(0, 2)` accepted at `(2P, 2P, 2P, L, L)`.
    (`test_s08_roots.py`'s A08 compares the root with WO-G's.)"""
    answer = solved("P3")
    assert answer.outcome == "CONVERGED" and answer.signature == CORE3_L2
    reentry = answer.reentry
    assert reentry is not None and reentry.trigger in REENTRY_OUTCOMES
    assert reentry.stage_a.outcome == reentry.trigger and reentry.stage_a.failures == ()
    assert [(c.a, c.c, c.endpoint, c.outcome) for c in reentry.candidates] == [
        (0, 2, "built", "CONVERGED")
    ]
    assert _source(answer.result) == BLOCK_ENDPOINT_ID


# -- A16: exclusions -----------------------------------------------------------------------------


def _no_stage_b(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("A16: Stage B ran")

    monkeypatch.setattr(blocks_module, "candidates", refuse)
    monkeypatch.setattr(blocks_module, "block_endpoint", refuse)


def test_a16_an_endpoint_failure_does_not_start_stage_b(monkeypatch: pytest.MonkeyPatch) -> None:
    """A16 / S02 A22 (§5.1, §10 Q9): M1 with `max_sweeps = 1` still ends
    `initialization_failed(s02-bubble-point-v1, sweeps_exhausted)`, with no region solve and no
    Stage B."""
    _no_stage_b(monkeypatch)

    def no_region(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("A22: solve_region was called")

    monkeypatch.setattr(cascade_solve_module, "solve_region", no_region)
    answer = solve_column(SPECS["M1"], PROVIDER, max_sweeps=1)
    assert isinstance(answer, CascadeFailure)
    assert answer.outcome == "INITIALIZATION_FAILED"
    assert answer.cause == f"initialization_failed({PRESOLVE_ID}, sweeps_exhausted)"


def test_a16_the_unsupported_answer_does_not_start_stage_b(monkeypatch: pytest.MonkeyPatch) -> None:
    """A16 / S06 A14 (`test_s06_column_wo2.py`): J5's stubbed `CONVERGED` answer with stage 5
    `LIQUID` is still `CAPABILITY_UNAVAILABLE`, with no Stage B."""
    _no_stage_b(monkeypatch)
    _stubbed(monkeypatch, J_CASES["J5"], 5, "LIQUID")
    monkeypatch.setattr(solve_module, "acceptance_failures", lambda *_: ())
    answer = solve_column(J_CASES["J5"], PROVIDER)
    assert isinstance(answer, CascadeFailure), answer
    assert answer.outcome == "CAPABILITY_UNAVAILABLE"
    assert answer.cause == "unsupported(temperature_specification_on_single_phase_stage:5)"


def test_a16_a_defect_other_than_item_6_does_not_start_stage_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A16 / S06 A14: J5's stubbed state, not a root, still raises `AcceptanceDefectError`
    (§5.1: any §8 failure other than item 6), with no Stage B."""
    _no_stage_b(monkeypatch)
    _stubbed(monkeypatch, J_CASES["J5"], 5, "LIQUID")
    with pytest.raises(AcceptanceDefectError) as raised:
        solve_column(J_CASES["J5"], PROVIDER)
    assert any(failure.startswith("row ") for failure in raised.value.failures)


def test_a16_an_accepted_stage_a_has_no_reentry(monkeypatch: pytest.MonkeyPatch) -> None:
    """§5.6: `reentry` is `None` when Stage B is not triggered (M1, `CONVERGED` in Stage A)."""
    _no_stage_b(monkeypatch)
    answer = solve_column(SPECS["M1"], PROVIDER)
    assert isinstance(answer, ColumnSolution) and answer.outcome == "CONVERGED"
    assert answer.reentry is None and _source(answer.result) == PRESOLVE_ID


@pytest.mark.parametrize("name", sorted(U_SETS))
def test_a16_u1_u2_have_no_candidate(name: str) -> None:
    """A16 / §5.6: U1 and U2 trigger Stage B but generate no candidate (fixed stages 2 and 7):
    `reentry.candidates == ()`, nothing accepted, and the top level is Stage A's answer."""
    answer = solve_column(U_SETS[name], PROVIDER)
    assert isinstance(answer, ColumnSolution), answer
    reentry = answer.reentry
    assert reentry is not None
    assert (reentry.candidates, reentry.accepted) == ((), None)
    assert reentry.trigger == answer.outcome and answer.outcome in REENTRY_OUTCOMES
    stage_a = reentry.stage_a
    assert (stage_a.outcome, stage_a.cause, stage_a.failures) == (answer.outcome, answer.cause, ())
    assert stage_a.result is answer.result and stage_a.recovered_from is answer.recovered_from
    assert stage_a.endpoint_sha256 == answer.endpoint_sha256
    assert stage_a.final_sha256 == answer.final_sha256
    assert isinstance(answer.endpoint, BubblePointEndpoint)
    assert answer.unreached


# -- §5.1's trigger and §5.7's final answer --------------------------------------------------------


@pytest.mark.parametrize(
    ("outcome", "budget", "near_trivial", "expected"),
    [
        *((outcome, None, (), outcome) for outcome in sorted(REENTRY_OUTCOMES)),
        ("BUDGET_EXHAUSTED", "newton_iterations", (), "BUDGET_EXHAUSTED"),
        ("BUDGET_EXHAUSTED", "ptc_steps", (), "BUDGET_EXHAUSTED"),
        ("BUDGET_EXHAUSTED", "property_calls", (), None),
        ("BUDGET_EXHAUSTED", "homotopy_steps", (), None),
        ("CONVERGED", None, (), None),
        ("CONVERGED", None, (4,), NEAR_TRIVIAL_SPLIT),
        ("INITIALIZATION_FAILED", None, (), None),
        ("CAPABILITY_UNAVAILABLE", None, (), None),
        ("CHECKPOINT_INCOMPATIBLE", None, (), None),
        ("SPECIFICATION_CONFLICT", None, (), None),
    ],
)
def test_the_trigger(
    outcome: str, budget: str | None, near_trivial: tuple[int, ...], expected: str | None
) -> None:
    """§5.1: trigger (i) is `T_B`, plus `BUDGET_EXHAUSTED` on `newton_iterations` or
    `ptc_steps`; trigger (ii) is a `CONVERGED` state failing item 6 alone; nothing else."""
    result = RegionResult(outcome=outcome, state={}, attempts=(), budget=budget)  # type: ignore[arg-type]
    assert reentry_trigger(result, near_trivial) == expected


def test_t_b_is_the_registered_set() -> None:
    assert REENTRY_OUTCOMES == {
        "HOMOTOPY_STALLED",
        "ACTIVE_SET_CYCLING",
        "ATTEMPTS_EXHAUSTED",
        "LINE_SEARCH_FAILED",
        "LINEAR_SOLVE_FAILED",
        "BOUND_BLOCKED",
        "STAGNATION",
        "PTC_STALLED",
        "EVALUATION_ERROR",
    }


def test_a_refused_candidate_is_recorded_and_stage_a_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§5.3 "Refusals" and §5.7 item 2: P1's only candidate refused (`max_sweeps` cannot refuse
    a core-free candidate, so `block_endpoint` is stubbed) is recorded with its cause and nothing
    solved; P1's answer is then Stage A's typed answer with `reentry`."""
    cause = f"initialization_failed({BLOCK_ENDPOINT_ID}, inadmissible_endpoint(5))"
    monkeypatch.setattr(
        blocks_module,
        "block_endpoint",
        lambda *args, **kwargs: CascadeFailure("INITIALIZATION_FAILED", cause),
    )
    answer = solve_column(SPECS["P1"], PROVIDER)
    assert isinstance(answer, ColumnSolution)
    assert (answer.outcome, answer.cause) == ("HOMOTOPY_STALLED", "homotopy_stalled(BOUND_BLOCKED)")
    reentry = answer.reentry
    assert reentry is not None and reentry.accepted is None
    (candidate,) = reentry.candidates
    assert (candidate.a, candidate.c, candidate.signature) == (0, 5, LIQUID5)
    assert (candidate.endpoint, candidate.cause) == (cause, cause)
    assert candidate.endpoint_sha256 is None and candidate.outcome is None
    assert candidate.result is None and candidate.recovered_from is None
    assert answer.result is reentry.stage_a.result


def test_an_item_6_rejection_with_no_accepted_candidate_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§5.7 item 3: F1 with Stage B given no candidate raises `AcceptanceDefectError` with Stage
    A's item-6 failures, its message naming the candidates tried."""
    monkeypatch.setattr(blocks_module, "candidates", lambda spec: ())
    with pytest.raises(AcceptanceDefectError) as raised:
        solve_column(F1, PROVIDER)
    failures = raised.value.failures
    assert failures and all(f.startswith("§8.6: TWO_PHASE stage 4: ") for f in failures)
    assert any(
        "no Stage-B candidate was accepted; tried: none" in n for n in raised.value.__notes__
    )


# -- A17: §5.4's candidate rows (Amendment 1, §13.6) ----------------------------------------------

#: A17's candidates on P3: `(0, 2)`, then `X`. `X` is `(0, 2)` again, the one candidate that builds
#: and converges on P3, so the second solve is real and its acceptance is WO-G's root (S08 WO-5).
A17_CANDIDATES = ((0, 2), (0, 2))


def _first_candidate(
    monkeypatch: pytest.MonkeyPatch, row: str
) -> list[tuple[RegionResult, tuple[str, ...]]]:
    """P3 with `candidates` stubbed to `A17_CANDIDATES` and the first Stage-B `target_attempt`
    (`initializer_source` = `s08-block-endpoint-v1`) answering §5.4's `row`; Stage A's call and
    every later Stage-B call pass through. Returns each Stage-B call's (result, failures)."""
    real = solve_module.target_attempt
    calls: list[tuple[RegionResult, tuple[str, ...]]] = []

    def stubbed(*args: Any, **kwargs: Any) -> Any:
        found = real(*args, **kwargs)
        if kwargs.get("initializer_source", PRESOLVE_ID) != BLOCK_ENDPOINT_ID:
            return found
        result, recovered_from, regimes, failures, unsupported = found
        if not calls:
            assert result.outcome == "CONVERGED" and failures == () and unsupported is None
            if row == "typed":
                result = replace(
                    result, outcome="HOMOTOPY_STALLED", message="homotopy_stalled(stub)"
                )
            elif row == "unsupported":
                unsupported = 4
            else:
                failures = ("§8.1: stub, not item 6",)
        calls.append((result, failures))
        return result, recovered_from, regimes, failures, unsupported

    monkeypatch.setattr(blocks_module, "candidates", lambda spec: A17_CANDIDATES)
    monkeypatch.setattr(solve_module, "target_attempt", stubbed)
    return calls


@pytest.mark.parametrize(
    ("row", "outcome", "cause"),
    [
        ("typed", "HOMOTOPY_STALLED", "homotopy_stalled(stub)"),
        (
            "unsupported",
            "CONVERGED",
            "unsupported(temperature_specification_on_single_phase_stage:4)",
        ),
    ],
)
def test_a17_a_failed_first_candidate_is_recorded_and_the_second_accepted(
    monkeypatch: pytest.MonkeyPatch, row: str, outcome: str, cause: str
) -> None:
    """A17 (i), (ii): the first candidate ends typed, or `CONVERGED` with a single-phase
    `temperature`-specified stage (`unsupported(…)`); it is recorded with its outcome and cause,
    the second is tried and accepted, `accepted == 1`. A loop that stops after the first built
    candidate fails here."""
    calls = _first_candidate(monkeypatch, row)
    answer = solve_column(P3, PROVIDER)
    assert len(calls) == 2
    assert isinstance(answer, ColumnSolution), answer
    assert (answer.outcome, answer.cause, answer.signature) == ("CONVERGED", "", CORE3_L2)
    reentry = answer.reentry
    assert reentry is not None and reentry.accepted == 1
    assert [(c.a, c.c, c.endpoint, c.outcome, c.cause) for c in reentry.candidates] == [
        (0, 2, "built", outcome, cause),
        (0, 2, "built", "CONVERGED", ""),
    ]
    assert reentry.candidates[0].result is calls[0][0]
    assert answer.result is calls[1][0] is reentry.candidates[1].result
    assert _source(answer.result) == BLOCK_ENDPOINT_ID


def test_a17_a_defect_of_the_first_candidate_raises_with_no_second_solve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A17 (iii): the first candidate `CONVERGED` failing a §8 item other than item 6 raises
    `AcceptanceDefectError` with that failure, and the second candidate is never solved."""
    calls = _first_candidate(monkeypatch, "defect")
    with pytest.raises(AcceptanceDefectError) as raised:
        solve_column(P3, PROVIDER)
    assert len(calls) == 1
    assert raised.value.failures == ("§8.1: stub, not item 6",)


# -- A14 (a), (d), (e): mutations ----------------------------------------------------------------


def test_a09_f1_is_rejected_by_item_6_then_wo_g_s_root_through_stage_b() -> None:
    check_a09_route(solved("F1"))


def test_a14_the_f1_route_holds_unmutated() -> None:
    """The baseline of mutations (d) and (e): A09 holds on the unmutated code."""
    check_a09_route(solved("F1"))


def test_a14a_stage_b_disabled_fails_a05(monkeypatch: pytest.MonkeyPatch) -> None:
    """A14 (a): with Stage B disabled (no trigger), P1 ends typed and A05 fails."""
    monkeypatch.setattr(solve_module, "reentry_trigger", lambda *_: None)
    answer = solve_column(SPECS["P1"], PROVIDER)
    with pytest.raises(AssertionError):
        check_a05(answer)
    assert isinstance(answer, ColumnSolution) and answer.outcome == "HOMOTOPY_STALLED"


def test_a14d_an_infinite_tolerance_fails_a09(monkeypatch: pytest.MonkeyPatch) -> None:
    """A14 (d): with `τ₆ = ∞`, F1's near-trivial Stage-A state is accepted and A09 fails."""
    monkeypatch.setattr(solve_module, "TWO_PHASE_SATURATION_TOLERANCE", math.inf)
    answer = solve_column(F1, PROVIDER)
    with pytest.raises(AssertionError):
        check_a09_route(answer)
    assert isinstance(answer, ColumnSolution)
    assert answer.signature == ("TWO_PHASE",) * 4 + ("LIQUID",) and answer.reentry is None


def test_a14e_no_item_6_trigger_fails_a09(monkeypatch: pytest.MonkeyPatch) -> None:
    """A14 (e): with trigger (ii) removed, F1's Stage-A rejection raises (A09 fails by raising)."""
    real = solve_module.reentry_trigger
    monkeypatch.setattr(solve_module, "reentry_trigger", lambda result, _: real(result, ()))
    with pytest.raises(AcceptanceDefectError) as raised:
        check_a09_route(solve_column(F1, PROVIDER))
    assert all(f.startswith("§8.6: TWO_PHASE stage 4: ") for f in raised.value.failures)
