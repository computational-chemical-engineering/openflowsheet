"""RRC WO-3 (ADR 0072; design note `docs/design/RRC-revision-region-continuation.md` §5.5, §5.7,
§8.2): edge 3's revision continuation, through the executor and the region solve.

Every source is built **in-process**, as WO-3's row says: the ancestor revision is solved under
`T06-revision-v2`, verified (`verify_revision`), and the candidate is read off that run and its
certificate — the identity and the root from `root_fingerprint`, the signature from the last
`branch_provenance` item, the state from the run. No store, no assembly (WO-4).

- **G2** (level identity) on NET-02 continued from its split-0.5 ancestor (§8.1's N1).
- **G3** (controller): a stub corrector rejects at λ = 1/4 once, or at every λ > 0.
- **G6** (typed refusals) (b) and (f)–(j), with R3 and a supplied refusal: one
  `initializer_rejected` event, then the step and its trace are `T06-revision-v2`'s.
- **F1, F2** (forced edge, S01 A17's precedent): edge 3 is forced after a `CONVERGED` item 0, so
  item 0's root — reached from `traversal-G0-v1` by Newton, without the code under test — is the
  independent expectation of the continuation's.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cache
from typing import Any

import pytest
from s11_column_support import RECYCLE_CASE, column_registered, committed_case
from t06_support import T06_REVISION_POLICY, case_document

from openflowsheet.application.policies import RRC_REVISION_V1
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.canonical import encode_doubles
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator import executor, revision
from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.execution import ExecutionPlan, declaration_identity
from openflowsheet.orchestrator.executor import PlanResult, StepResult, execute_plan
from openflowsheet.orchestrator.homotopy import CorrectorOutcome, level_values, rebind
from openflowsheet.orchestrator.revision import INITIALIZER_ID
from openflowsheet.orchestrator.revision_continuation import (
    REVISION_CONTINUATION_SOURCE,
    RevisionContinuationCandidate,
    RevisionContinuationRecord,
    RevisionContinuationRefusal,
)
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision
from openflowsheet.verify.checks import VerifierError

NET02 = "SYN-001-T06-NET02"
NET03 = "SYN-001-T06-NET03"
SPLIT = "U-SPLIT.split_fraction"
#: §8.2 F1, F2 (and G4's root comparison): the scaled distance between two roots of one problem.
SAME_ROOT = 1e-8
#: A dyadic λ as the trace writes it (`fraction_string`).
DYADIC = re.compile(r"^(0|1|[1-9][0-9]*/[1-9][0-9]*)$")


@dataclass(frozen=True)
class Solved:
    document: dict[str, Any]
    binding: RevisionBinding
    plan: ExecutionPlan
    run: PlanResult

    @property
    def step(self) -> StepResult:
        (step,) = [step for step in self.run.steps if step.kind == "solve_eo"]
        return step

    def certificate(self) -> SolutionCertificate:
        return verify_revision(
            self.binding, self.document, self.run, solve_plan=self.plan.steps[-1].solve_plan
        )


def solve(document: dict[str, Any], policy: SolvePolicy, **keywords: Any) -> Solved:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = revision.plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy, **keywords
    )
    return Solved(document, binding, plan, run)


def candidate(source: Solved) -> RevisionContinuationCandidate:
    """§5.3's candidate, from a `VERIFIED` solve of the ancestor and its certificate."""
    certificate = source.certificate()
    assert certificate.verification_status == "VERIFIED"
    fingerprint = certificate.root_fingerprint
    assert fingerprint is not None and source.run.state is not None
    return RevisionContinuationCandidate(
        job_id="job-source",
        revision_id=source.document["revision_id"],
        model_version=fingerprint["model_version"],
        constants_sha256=fingerprint["constants_sha256"],
        full_state_sha256=fingerprint["full_state_sha256"],
        signature=tuple(
            (str(unit), str(regime))
            for unit, regime in certificate.branch_provenance[-1]["signature"]
        ),
        state=dict(source.run.state),
        parameters=dict(source.binding.spec.parameters),
    )


def net02(split: float | None = None) -> dict[str, Any]:
    document = case_document(NET02)
    if split is not None:
        (splitter,) = [item for item in document["instances"] if item["id"] == "U-SPLIT"]
        splitter["parameters"]["split_fraction"]["value"] = split
    return document


@cache
def n1() -> RevisionContinuationCandidate:
    """§8.1's N1: NET-02 with `split_fraction` 0.5, `VERIFIED` under `T06-revision-v2`."""
    source = solve(net02(0.5), T06_REVISION_POLICY)
    assert source.run.outcome == "CONVERGED"
    return candidate(source)


@cache
def restarted() -> Solved:
    """NET-02 under `T06-revision-v2`: rescued by the ADR 0015 restart (T06-F4 G1)."""
    return solve(net02(), T06_REVISION_POLICY)


@cache
def continued() -> Solved:
    return solve(net02(), RRC_REVISION_V1, revision_continuation=n1())


def scaled_distance(binding: RevisionBinding, x: Any, y: Any) -> float:
    """‖x − y‖∞ in the region's column scales (`Scaling.from_spec`, as `solve_region` scales)."""
    scaling = Scaling.from_spec(binding.spec)
    return max(abs(x[name] - y[name]) / scaling.column[name] for name in binding.spec.variable_ids)


# ------------------------------------------------------------------ the action and G2


def test_the_policy_differs_from_t06_revision_v2_in_its_edge_only() -> None:
    assert RRC_REVISION_V1.globalization.eo_recovery == executor._REVISION_RECOVERY
    assert (
        replace(
            RRC_REVISION_V1,
            policy_id=T06_REVISION_POLICY.policy_id,
            globalization=T06_REVISION_POLICY.globalization,
        )
        == T06_REVISION_POLICY
    )


def test_net02_is_continued_from_its_verified_ancestor_and_certified() -> None:
    """The action (§5.5 R9b): item 0 `BOUND_BLOCKED` from `traversal-G0-v1`, item 1 the homotopy
    from the ancestor's root, `CONVERGED`, `VERIFIED`; no refusal, no restart; and the root is the
    restart's (G4's comparison, an independent path to NET-02's root)."""
    solved = continued()
    step, run = solved.step, solved.run
    assert run.outcome == step.outcome == "CONVERGED"
    assert (step.eo_recovery, step.eo_recovery_unsupported) == ("taken", None)
    assert step.recovered_from.outcome == "BOUND_BLOCKED"
    assert step.iterations == step.recovered_from.iterations + step.detail.iterations
    assert step.revision_continuation == run.revision_continuation
    assert step.revision_continuation == RevisionContinuationRecord("taken", None, (SPLIT,), (0.5,))
    items = [
        (item["attempt"], item["opening_source"], item["initializer_source"], item["core"])
        for item in step.detail.branch_provenance
    ]
    assert items == [
        (0, "initializer", INITIALIZER_ID, "newton"),
        (1, "eo_recovery_start", REVISION_CONTINUATION_SOURCE, "homotopy"),
    ]
    provenance = step.detail.branch_provenance[1]["continuation"]
    assert provenance["type"] == "revision_continuation"
    assert provenance["parameter_ids"] == [SPLIT]
    assert provenance["lambda_reached"] == "1"
    (context,) = [c for c in step.detail.contexts if c.core == "homotopy"]
    assert context.continuation == {"type": "revision_continuation", "parameter_ids": [SPLIT]}
    assert not run.trace.of_kind("initializer_rejected")
    (closed,) = run.trace.of_kind("region_closed")
    assert closed.as_document()["eo_recovery"] == "taken"
    assert solved.certificate().verification_status == "VERIFIED"
    other = restarted()
    assert other.run.outcome == "CONVERGED"
    assert scaled_distance(solved.binding, run.state, other.run.state) <= SAME_ROOT


def test_g2_every_level_has_its_identity() -> None:
    """G2 (a)–(f) on the run's trace and records."""
    solved, source = continued(), n1()
    step, spec = solved.step, solved.binding.spec
    record = step.revision_continuation
    assert record is not None
    continuation = step.detail.homotopy.continuation
    events = [event.as_document() for event in solved.run.trace.of_kind("homotopy_step")]
    levels = {event["lambda_value"]: event["level_constants_sha256"] for event in events}
    # (d) every λ is a dyadic `p/q` string.
    for text in levels:
        assert DYADIC.match(text), text
        lam = Fraction(text)
        assert lam.denominator & (lam.denominator - 1) == 0, text
    # (a) λ = 0 is the ancestor's certified problem.
    opening = rebind(spec, level_values(continuation, spec.parameters, {}, Fraction(0)))
    assert declaration_identity(opening) == (source.model_version, source.constants_sha256)
    assert levels["0"] == source.constants_sha256
    # (b) every λ < 1 level differs from the target only at `D`, and is the level the trace names.
    target_model_version, target_constants = declaration_identity(spec)
    for text, recorded in levels.items():
        lam = Fraction(text)
        if lam == 1:
            continue
        values = level_values(continuation, spec.parameters, {}, lam)
        level = rebind(spec, values).parameters
        moved = [
            pid
            for pid in spec.parameter_ids
            if encode_doubles((level[pid],)) != encode_doubles((spec.parameters[pid],))
        ]
        assert set(moved) <= set(record.parameter_ids), (text, moved)
        assert declaration_identity(rebind(spec, values)) == (target_model_version, recorded)
        # (e) each level's value is formed in exact rationals and rounded once (WO-1's rule).
        for pid, start in zip(record.parameter_ids, record.start_values, strict=True):
            target = Fraction(spec.parameters[pid])
            assert values[pid] == float(target + (1 - lam) * (Fraction(start) - target))
    # (c) λ = 1 is the target: the failed solve's identity, the certificate's, the restart's.
    assert levels["1"] == target_constants
    failed = step.recovered_from.contexts[0].evaluation_context
    assert (failed.model_version, failed.constants_sha256) == (
        target_model_version,
        target_constants,
    )
    for certificate in (solved.certificate(), restarted().certificate()):
        fingerprint = certificate.root_fingerprint
        assert fingerprint is not None
        assert (fingerprint["model_version"], fingerprint["constants_sha256"]) == (
            target_model_version,
            target_constants,
        )
    # (f) the recovery item opens at the ancestor's root.
    assert step.detail.branch_provenance[1]["opening_state_sha256"] == source.full_state_sha256


def test_an_inert_value_ignores_a_supplied_source() -> None:
    """§5.5: under every other `eo_recovery` value the source is never read nor recorded — the
    run is the one without it, event for event."""
    with_source = solve(net02(), T06_REVISION_POLICY, revision_continuation=n1())
    assert with_source.step.revision_continuation is None
    assert with_source.run.revision_continuation is None
    assert _events(with_source.run) == _events(restarted().run)


# ------------------------------------------------------------------ G3: the controller


def _stub(
    monkeypatch: pytest.MonkeyPatch, rejects: Callable[[Fraction], bool]
) -> list[tuple[Fraction, Any, Any]]:
    """Wrap every corrector of the homotopy core: run it, and report a λ > 0 trial that `rejects`
    as not converged. Records `(λ, start, end)` of every trial, in order."""
    calls: list[tuple[Fraction, Any, Any]] = []
    real = region_module.continue_specification

    def wrapped(*, correct: Any, **keywords: Any) -> Any:
        def stub(lam: Fraction, start: Any, running: Any) -> CorrectorOutcome:
            outcome: CorrectorOutcome = correct(lam, start, running)
            calls.append((lam, start.copy(), outcome.result.x.copy()))
            if lam > 0 and rejects(lam):
                result = replace(outcome.result, outcome="BUDGET_EXHAUSTED", converged=False)
                return replace(outcome, result=result, boundary_unit=None)
            return outcome

        return real(correct=stub, **keywords)

    monkeypatch.setattr(region_module, "continue_specification", wrapped)
    return calls


def test_g3_a_rejection_halves_the_step_from_the_last_accepted_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G3: one rejection at λ = 1/4; the next trial is λ = 1/8, from the λ = 0 root, bitwise."""
    seen: set[Fraction] = set()

    def once_at_a_quarter(lam: Fraction) -> bool:
        first = lam == Fraction(1, 4) and lam not in seen
        seen.add(lam)
        return first

    calls = _stub(monkeypatch, once_at_a_quarter)
    solved = solve(net02(), RRC_REVISION_V1, revision_continuation=n1())
    assert [lam for lam, _, _ in calls[:3]] == [Fraction(0), Fraction(1, 4), Fraction(1, 8)]
    (_, _, easy_root), (_, at_quarter, _), (_, at_eighth, _) = calls[:3]
    assert at_quarter.tobytes() == easy_root.tobytes()
    assert at_eighth.tobytes() == easy_root.tobytes()
    assert solved.step.detail.homotopy.rejected_trials == 1
    assert solved.run.outcome == "CONVERGED"


def test_g3_every_rejection_stalls_bracketed_without_a_certificate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G3: every λ > 0 rejected — `HOMOTOPY_STALLED` at λ = 0, its bracket within 2/1024, no root
    fingerprint and no certificate; the step's one recovery was the continuation (FQ3: no
    restart follows)."""
    _stub(monkeypatch, lambda lam: True)
    solved = solve(net02(), RRC_REVISION_V1, revision_continuation=n1())
    step = solved.step
    assert solved.run.outcome == step.outcome == "HOMOTOPY_STALLED"
    assert step.eo_recovery == "taken"
    assert step.revision_continuation is not None
    assert step.revision_continuation.status == "taken"
    record = step.detail.homotopy
    assert record.stalled_at == "resolution"
    assert record.lambda_reached == 0
    assert record.trials[0].accepted and not any(trial.accepted for trial in record.trials[1:])
    # The bracket: the last accepted level and the last rejected trial, which the stall ended on.
    last = record.trials[-1]
    assert not last.accepted
    assert 0 < last.lambda_value - record.lambda_reached <= Fraction(2, 1024)
    assert step.detail.root_fingerprint is None
    assert step.detail.checkpoint.continuation_lambda == "0"
    assert step.detail.checkpoint.label == "partial"
    assert not solved.run.trace.of_kind("initializer_rejected")
    with pytest.raises(VerifierError):
        solved.certificate()


# ------------------------------------------------------------------ G6: typed refusals


def _events(run: PlanResult) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in event.as_document().items() if key != "sequence"}
        for event in run.trace.events
    ]


def _source_for(case: str) -> RevisionContinuationCandidate | RevisionContinuationRefusal | None:
    source = n1()
    if case == "not_supplied":
        return None
    if case == "supplied_refusal":
        return RevisionContinuationRefusal("absent", "no_verified_ancestor")
    if case == "model_version":
        return replace(source, model_version="tampered@" + "0" * 64)
    if case == "no_changed_specification":
        target = restarted()
        assert target.run.outcome == "CONVERGED"
        return candidate(target)
    if case == "level_identity":
        return replace(source, constants_sha256="0" * 64)
    if case == "active_set":
        tampered = tuple(
            (unit, "LIQUID" if unit == "U-HEAT" else regime) for unit, regime in source.signature
        )
        assert tampered != source.signature
        return replace(source, signature=tampered)
    if case == "coverage":
        return replace(
            source, signature=tuple(item for item in source.signature if item[0] != "U-PHF")
        )
    raise AssertionError(case)


#: G6's cases this WO reaches, with the recorded status and reason (§8.2; (a) the lookup's
#: `absent`, here supplied as the application would pass it).
G6 = {
    "not_supplied": ("absent", "not_supplied"),
    "supplied_refusal": ("absent", "no_verified_ancestor"),
    "model_version": ("rejected", "model_version"),
    "no_changed_specification": ("rejected", "no_changed_specification"),
    "level_identity": ("rejected", "level_identity"),
    "active_set": ("rejected", None),
    "coverage": ("rejected", "opening(coverage:U-PHF)"),
}


@pytest.mark.parametrize("case", list(G6))
def test_g6_a_refusal_is_recorded_and_the_restart_runs_unchanged(case: str) -> None:
    """G6 (b), (f)–(j): exactly one `initializer_rejected` event with the R0 message; the step's
    record says why; and everything else — every other event, the step's outcome, provenance,
    state and counters — is the same case's under `T06-revision-v2`."""
    status, reason = G6[case]
    solved = solve(net02(), RRC_REVISION_V1, revision_continuation=_source_for(case))
    step, run = solved.step, solved.run
    (rejected,) = run.trace.of_kind("initializer_rejected")
    record = step.revision_continuation
    assert record is not None and record == run.revision_continuation
    if case == "active_set":
        # (i): `U-HEAT` reported `LIQUID` pins its vapour columns, which the root holds non-zero.
        match = re.fullmatch(r"opening\(active_set:(.+)\)", record.reason or "")
        assert match is not None, record.reason
        column = match.group(1)
        assert column.startswith("S") and "vap" in column.lower(), column
        assert n1().state[column] > 0.0
        reason = record.reason
    assert (record.status, record.reason) == (status, reason)
    assert (record.parameter_ids, record.start_values) == ((), ())
    assert rejected.message == f"revision_continuation_{status}: {reason}"
    reference = restarted()
    events = _events(run)
    at = [event["kind"] for event in events].index("initializer_rejected")
    assert [event["kind"] for event in events[at + 1 :]].count("attempt_opened") >= 1
    del events[at]
    # "except for `policy_id`": the plan's id names the policy, and nothing else does.
    (built,) = [event for event in events if event["kind"] == "plan_built"]
    built["message"] = built["message"].replace(
        f"-{RRC_REVISION_V1.policy_id}-", f"-{T06_REVISION_POLICY.policy_id}-"
    )
    assert events == _events(reference.run)
    for name in ("outcome", "iterations", "message", "eo_recovery", "eo_recovery_unsupported"):
        assert getattr(step, name) == getattr(reference.step, name), name
    assert step.detail.branch_provenance == reference.step.detail.branch_provenance
    assert run.state == reference.run.state
    assert run.counters == reference.run.counters
    assert run.outcome == "CONVERGED"


def test_r3_a_syn001_region_is_not_revision_built() -> None:
    """R3: on SYN-001's own flowsheet (T04's HOM-U, edge 3 due, no continuation parameter) the
    continuation is `absent(not_revision_built)`, then the restart's P3 refuses as ADR 0015 says."""
    from test_t02_executor import nominal, policy
    from test_t04_edge3 import region_step

    registered = replace(policy("eo"), max_iterations_per_attempt=1)
    solve_policy = replace(
        registered,
        globalization=replace(registered.globalization, eo_recovery=executor._REVISION_RECOVERY),
    )
    result = nominal(solve_policy).result
    step = region_step(result)
    assert result.outcome == step.outcome == "BUDGET_EXHAUSTED"
    assert (step.eo_recovery, step.eo_recovery_unsupported) == (
        "unsupported",
        "no_restart_initializer",
    )
    assert step.revision_continuation == RevisionContinuationRecord("absent", "not_revision_built")
    assert [event.message for event in result.trace.of_kind("initializer_rejected")] == [
        "revision_continuation_absent: not_revision_built"
    ]


# ------------------------------------------------------------------ F1, F2: forced edge


@pytest.fixture
def registered(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    with column_registered(monkeypatch):
        yield monkeypatch


def _forced(
    monkeypatch: pytest.MonkeyPatch, source: dict[str, Any], target: dict[str, Any]
) -> tuple[RevisionContinuationCandidate, Solved]:
    found = solve(source, T06_REVISION_POLICY)
    assert found.run.outcome == "CONVERGED"
    ancestor = candidate(found)
    monkeypatch.setattr(executor, "eo_recovery_due", lambda outcome, budget, *, attempts: True)
    return ancestor, solve(target, RRC_REVISION_V1, revision_continuation=ancestor)


def _same_root(solved: Solved, ancestor: RevisionContinuationCandidate) -> tuple[str, ...]:
    step = solved.step
    assert step.recovered_from.outcome == "CONVERGED"
    assert solved.run.outcome == step.outcome == "CONVERGED"
    assert step.eo_recovery == "taken"
    record = step.revision_continuation
    assert record is not None and record.status == "taken"
    assert step.detail.branch_provenance[1]["opening_state_sha256"] == ancestor.full_state_sha256
    assert solved.certificate().verification_status == "VERIFIED"
    item0 = step.recovered_from.state
    assert scaled_distance(solved.binding, solved.run.state, item0) <= SAME_ROOT
    return record.parameter_ids


def test_f1_a_column_continued_in_its_end_specifications_reaches_item_0s_root(
    registered: pytest.MonkeyPatch,
) -> None:
    """F1: M1-recycle → C5's change (reflux 2.0 → 4.0, boil-up 1.5 → 3.0, split 0.2)."""
    source = committed_case(RECYCLE_CASE)
    target = copy.deepcopy(source)
    (column,) = [item for item in target["instances"] if item["id"] == "S02"]
    column["parameters"]["condenser_reflux_ratio"]["value"] = 4.0
    column["parameters"]["reboiler_boilup_ratio"]["value"] = 3.0
    ancestor, solved = _forced(registered, source, target)
    continued_ids = _same_root(solved, ancestor)
    assert len(continued_ids) == 2
    assert any("reflux" in pid for pid in continued_ids)
    assert any("boilup" in pid for pid in continued_ids)


def test_f2_a_flash_liquid_loop_continued_in_its_feed_temperature_reaches_item_0s_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F2: NET-03 from a source whose first feed `state.T` is 5 K lower (300 K → 295 K)."""
    target = case_document(NET03)
    source = copy.deepcopy(target)
    (feed_t,) = [item for item in source["specifications"] if item["id"] == "SPEC-S1-T"]
    feed_t["value"] = 295.0
    ancestor, solved = _forced(monkeypatch, source, target)
    continued_ids = _same_root(solved, ancestor)
    assert continued_ids == ("U-FEED.T_spec",)
