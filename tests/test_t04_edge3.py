"""T04 W3: recovery edge 3 in the plan executor (T04 §5; ADR 0010 D3). A04–A11, A28's refusal.

Every case runs the whole plan — the evaluate step, the §7.5 pre-solve, the region, and the edge —
on one trace, under the default policy (edge 3 on, T04 Q4) unless the case registers an override.
Expectations are `benchmarks/t04/reference_values.yaml`'s; the contract half of each case is also
T03's registered trajectory where T03 registered it (`benchmarks/t03/reference_values.yaml`).

The family scan's flash duties are the registered 20-digit values where a YAML has them (340, 350,
352, 355, 358, 360, 365 K) and the SYN-001 oracle's elsewhere (345, 370, 375 K) — the oracle is the
independent acceptance reference, and it reproduces every registered value to 7.6e-11 W.
"""

from __future__ import annotations

import copy
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any, get_args

import pytest
import yaml
from jsonschema import Draft202012Validator

import openflowsheet.orchestrator.executor as executor_module
import openflowsheet.orchestrator.region as region_module
from openflowsheet.application.binding import Binding, bind_revision
from openflowsheet.orchestrator.executor import PlanResult, StepResult
from openflowsheet.orchestrator.phase_contract import OpeningRefusal
from openflowsheet.orchestrator.recovery import (
    EO_RECOVERY_TRIGGERS,
    eo_recovery_due,
    recovered_provenance,
)
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.trace import (
    GlobalizationPolicy,
    RecyclePolicy,
    SolveOutcome,
    SolvePolicy,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES = REPO_ROOT / "benchmarks" / "syn001" / "cases"
BASE = "SYN-001-A02-355-dew-guess"
CONTINUED = "SPEC:SPEC-flash-duty"
RELATIVE = 1e-9
TEMPERATURE, DUTY, FLOW = 1e-5, 1e-2, 3.1e-7
HOM = ("HOM-01", "HOM-02", "HOM-03", "HOM-04", "HOM-05")
NONE = GlobalizationPolicy(eo_recovery="none")


def reference(package: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / package / "reference_values.yaml").read_text()
    )
    return loaded


T04 = reference("t04")
T03 = reference("t03")
HOMOTOPY_CASES = T04["policy_simulation"]["homotopy_cases"]


def document_for(guess: float, duty: float, name: str) -> dict[str, Any]:
    """The A02 base revision with another guess and flash duty (T02 §7.3: nothing else differs)."""
    document: dict[str, Any] = copy.deepcopy(yaml.safe_load((CASES / f"{BASE}.yaml").read_text()))
    document["revision_id"] = f"{name}-t04-test"
    for entry in document["specifications"]:
        if entry["id"] == "GUESS-heater-outlet-T":
            entry["value"] = guess
        elif entry["id"] == "SPEC-flash-duty":
            entry["value"] = duty
    return document


def case_document(case_id: str) -> dict[str, Any]:
    case = HOMOTOPY_CASES[case_id]
    return document_for(
        float(case["guess_S3_T_K"]), float(case["Q_flash_spec_W"]), case["registry_id"]
    )


def case_policy(case_id: str, globalization: GlobalizationPolicy | None = None) -> SolvePolicy:
    overrides = HOMOTOPY_CASES[case_id]["policy_overrides"] or {}
    return SolvePolicy(
        policy_id=f"T04-{case_id}",
        residual_tolerances={},
        scales={},
        globalization=globalization or GlobalizationPolicy(),
        **overrides,
    )


def plan_run(document: dict[str, Any], policy: SolvePolicy) -> Any:
    """The plan and its result (`test_t02_executor.Run`)."""
    from test_t02_executor import run_flowsheet

    binding = bind_revision(document)
    assert isinstance(binding, Binding)
    return run_flowsheet(
        binding.flowsheet,
        binding.spec,
        binding.graph,
        binding.row_units,
        policy,
        specification_ids=binding.specification_ids,
        freed=binding.freed,
        promoted=binding.promoted,
        missing_guesses=binding.missing_guesses,
    )


_RUNS: dict[str, Any] = {}


def run(case_id: str) -> PlanResult:
    return full_run(case_id).result


def full_run(case_id: str) -> Any:
    if case_id not in _RUNS:
        _RUNS[case_id] = plan_run(case_document(case_id), case_policy(case_id))
    return _RUNS[case_id]


def region_step(result: PlanResult) -> StepResult:
    (step,) = [step for step in result.steps if step.kind == "solve_eo"]
    return step


def close(value: float, expected: Any, relative: float = RELATIVE) -> bool:
    target = float(expected)
    return abs(value - target) <= relative * max(1.0, abs(target))


# ------------------------------------------------------------------ A04–A08: the five cases


@pytest.mark.parametrize("case_id", HOM)
def test_a04_a08_edge_3_takes_the_registered_path(case_id: str) -> None:
    """Through the executor: the contract's attempts as registered, edge 3 `taken`, the λ-path of
    `ref.hom.<case>.homotopy` trial by trial, the registered outcome, and the state reported."""
    registered = HOMOTOPY_CASES[case_id]
    result = run(case_id)
    step = region_step(result)
    assert step.eo_recovery == registered["edge3"] == "taken"
    assert step.eo_recovery_unsupported is None
    assert result.outcome == step.outcome == registered["outcome"]

    failed = step.recovered_from
    assert isinstance(failed, RegionResult)
    assert failed.outcome == registered["contract"]["outcome"]
    contract = registered["contract"]["attempts"]
    items = step.detail.branch_provenance
    assert len(items) == len(contract) + 1, "the contract's items, then the recovery's one"
    for item, attempt in zip(items, contract, strict=False):
        signature = ",".join(f"{unit}:{regime}" for unit, regime in item["signature"])
        assert (signature, item["opening_source"], item["core"]) == (
            attempt["signature"],
            attempt["opening_source"],
            attempt["core"],
        )
        assert (item["core_outcome"], item["iterations"], item["decision"]) == (
            attempt["core_outcome"],
            attempt["iterations"],
            attempt["decision"],
        )
        if attempt["decision"] == "terminal":
            # ADR 0005 D7: the closing message; `ref` registers null (T04 §17 F11).
            assert attempt["cause"] is None
            assert item["cause"] == failed.message
        else:
            assert item["cause"] == attempt["cause"]

    recovery = step.detail
    record = recovery.homotopy
    assert record is not None
    steps = registered["homotopy"]["steps"]
    assert len(record.trials) == len(steps) == registered["homotopy"]["lambda_trials"] + 1
    where = record.variable_ids.index("S3.T")
    for trial, expected in zip(record.trials, steps, strict=True):
        corrector = trial.corrector.result
        assert (str(trial.lambda_value), str(trial.delta_lambda)) == (
            str(expected["lambda"]),
            str(expected["delta_lambda"]),
        )
        assert (corrector.outcome, corrector.iterations, trial.accepted) == (
            expected["corrector_outcome"],
            expected["corrector_iterations"],
            expected["accepted"],
        )
        assert close(float(corrector.x[where]), expected["S3_T_K"]), (case_id, trial.index)
    assert str(record.lambda_reached) == str(registered["homotopy"]["lambda_reached"])
    assert result.state is not None
    assert close(result.state["S3.T"], registered["homotopy"]["end_S3_T_K"])
    assert abs(result.state["S3.V"] - float(registered["homotopy"]["end_S3_V_mol_per_s"])) <= FLOW


def test_a04_the_contract_half_of_hom_01_is_t03_a12() -> None:
    """HOM-01's failed solve is PHS-05 exactly as T03 registered it — the edge is the only thing
    that ran after it — and its closing message is T03 A12's."""
    step = region_step(run("HOM-01"))
    failed = step.recovered_from
    registered = T03["policy_simulation"]["cases"][BASE]
    assert failed.outcome == registered["outcome"] == "ACTIVE_SET_CYCLING"
    assert failed.message == (
        "active_set_cycling(U-HEAT:TWO_PHASE,U-FLASH:TWO_PHASE; "
        "phase_wall(stall, U-HEAT:LIQUID->TWO_PHASE))"
    )
    for item, attempt in zip(failed.branch_provenance, registered["attempts"], strict=True):
        assert item["core_outcome"] == attempt["core_outcome"]
        assert item["iterations"] == attempt["core_iterations"]
        assert item["opening_trial"] == attempt["opening_trial"]
        if attempt["decision"] == "restart":
            assert item["cause"] == attempt["cause"]
    assert close(failed.attempts[0].end_state["S3.T"], registered["attempts"][0]["end_S3_T_K"])


@pytest.mark.parametrize("case_id", ["HOM-01", "HOM-02", "HOM-05"])
def test_a04_a05_a08_the_provenance_continues_densely(case_id: str) -> None:
    """§5.3/§9.2: the recovery's item follows the contract's with the next attempt number, opens
    `eo_recovery_start` at item 0's state with item 0's initializer source, and carries the
    continuation history; the trace's attempts run on in the same step."""
    result = run(case_id)
    step = region_step(result)
    items = step.detail.branch_provenance
    assert [item["attempt"] for item in items] == list(range(len(items)))
    last = items[-1]
    assert last["core"] == "homotopy" and last["opening_source"] == "eo_recovery_start"
    assert last["initializer_source"] == items[0]["initializer_source"] == "user_guess"
    assert last["opening_state_sha256"] == items[0]["opening_state_sha256"]
    assert last["decision"] == "converged"
    assert last["continuation"] == {
        "type": "specification_continuation",
        "parameter_ids": [CONTINUED],
        "lambda_levels": ["1/4", "3/4", "1"],
        "lambda_reached": "1",
        "rejected_trials": 0,
    }
    opened = [e for e in result.trace.of_kind("attempt_opened") if e.step_index == step.index]
    # The pre-solve's attempt 0, the contract's attempts, the recovery's one — indices increase.
    assert [e.attempt for e in opened] == list(range(len(opened)))
    assert step.checkpoint is not None
    assert (step.checkpoint.continuation_lambda, step.checkpoint.label) == ("1", "candidate_root")
    assert step.checkpoint.step_index == step.index


def test_a05_the_lambda_three_quarters_corrector_lands_and_carries_on() -> None:
    """HOM-02: at λ = 3/4 iteration 0 lands `S3.vap.C` on `+0.0` at `α_max = 0.982 888 7` and the
    corrector does not close there (T03 §4.6's persistent-block rule inside a corrector)."""
    result = run("HOM-02")
    step = region_step(result)
    registered = HOMOTOPY_CASES["HOM-02"]["homotopy"]["steps"][2]
    (landing,) = registered["landings"]
    record = step.detail.homotopy
    trial = record.trials[2]
    assert trial.lambda_value == Fraction(3, 4) and trial.accepted
    accepted = [
        e
        for e in result.trace.of_kind("step_accepted")
        if e.step_index == step.index and e.homotopy_level == 2 and e.iteration == 0
    ]
    assert len(accepted) == 1
    assert close(float(accepted[0].alpha), landing["alpha_max"])
    assert trial.corrector.result.iterations == registered["corrector_iterations"] == 4


@pytest.mark.parametrize(("case_id", "level"), [("HOM-03", "23/256"), ("HOM-04", "909/1024")])
def test_a06_a07_a_stalled_recovery(case_id: str, level: str) -> None:
    """`HOMOTOPY_STALLED` ends the step; the checkpoint is the last accepted level's, `partial`
    at its λ; the bundle's class and action are ADR 0010 D8's and its one hypothesis is
    `phase_boundary_on_path(U-HEAT)`; no certificate."""
    from openflowsheet.verify.failure import ACTIONS, OUTCOME_ACTIONS, TAXONOMY

    result = run(case_id)
    step = region_step(result)
    assert result.outcome == "HOMOTOPY_STALLED"
    assert step.checkpoint is not None
    assert (step.checkpoint.continuation_lambda, step.checkpoint.label) == (level, "partial")
    assert step.checkpoint.verification_scope == "unverified"
    record = step.detail.homotopy
    assert record.inferred_cause == "phase_boundary_on_path(U-HEAT)"
    taxonomy = TAXONOMY[result.outcome]
    assert taxonomy == "homotopy/PTC/active-set stalls"
    assert OUTCOME_ACTIONS.get(result.outcome, ACTIONS[taxonomy]) == "supply_initial_guess"
    assert step.detail.root_fingerprint is None
    (closing,) = result.trace.of_kind("solve_closed")
    assert closing.outcome == "HOMOTOPY_STALLED"
    assert closing.message == f"homotopy_stalled({record.trials[-1].corrector.result.outcome})"


def test_a07_hom_04s_bubble_point_bracket() -> None:
    lam = Fraction(T04["closed_form"]["a02"]["HOM-04_lambda_bubble"])
    record = region_step(run("HOM-04")).detail.homotopy
    assert record.lambda_reached == Fraction(909, 1024)
    assert record.lambda_reached < lam < record.lambda_reached + Fraction(1, 512)
    rejected = [t for t in record.trials if not t.accepted]
    assert rejected and all(
        t.corrector.result.outcome == "BOUND_BLOCKED"
        and "S3.vap.C" in t.corrector.result.blocked_by
        for t in rejected
    )


# ------------------------------------------------------------------ A09: trigger discipline


def test_a09_the_trigger_set_is_section_5_1s() -> None:
    """Exactly §5.1's set, `BUDGET_EXHAUSTED` only for the cores' budgets; every other outcome of
    the vocabulary is not a trigger."""
    assert set(EO_RECOVERY_TRIGGERS) == set(T04["constants"]["edge3_triggers"])
    triggers = {
        "LINE_SEARCH_FAILED",
        "STAGNATION",
        "BOUND_BLOCKED",
        "PTC_STALLED",
        "ACTIVE_SET_CYCLING",
        "ATTEMPTS_EXHAUSTED",
    }
    for outcome in get_args(SolveOutcome):
        assert eo_recovery_due(outcome, None) == (outcome in triggers), outcome
    assert eo_recovery_due("BUDGET_EXHAUSTED", "newton_iterations")
    assert eo_recovery_due("BUDGET_EXHAUSTED", "ptc_steps")
    assert not eo_recovery_due("BUDGET_EXHAUSTED", "property_calls")
    assert not eo_recovery_due("BUDGET_EXHAUSTED", "homotopy_steps")
    for outcome in (
        "CONVERGED",
        "LINEAR_SOLVE_FAILED",
        "EVALUATION_ERROR",
        "CHECKPOINT_INCOMPATIBLE",
        "INITIALIZATION_FAILED",
        "CAPABILITY_UNAVAILABLE",
        "UNSUPPORTED_RANK_STRUCTURE",
        "PTC_MAPPING_INVALID",
        "HOMOTOPY_STALLED",
    ):
        assert not eo_recovery_due(outcome, None), outcome


def test_a09_hom_u_a_region_without_a_promoted_specification_is_unsupported() -> None:
    """SYN-001 under `eo` with one Newton iteration per attempt: `BUDGET_EXHAUSTED` with budget
    `newton_iterations` stands, and `region_closed` records why no recovery ran."""
    from test_t02_executor import nominal, policy

    result = nominal(replace(policy("eo"), max_iterations_per_attempt=1)).result
    step = region_step(result)
    assert result.outcome == step.outcome == "BUDGET_EXHAUSTED"
    assert step.detail.budget == "newton_iterations"
    assert step.eo_recovery == "unsupported"
    assert step.eo_recovery_unsupported == "no_continuation_parameter"
    (closed,) = result.trace.of_kind("region_closed")[-1:]
    document = closed.as_document()
    assert document["eo_recovery"] == "unsupported"
    assert document["eo_recovery_unsupported"] == "no_continuation_parameter"
    assert not result.trace.of_kind("homotopy_step")


def test_a09_edge_3_after_a_merged_region_is_unsupported_and_recorded() -> None:
    """§5.2: a merged recycle region has no promoted specification. Anderson capped at one
    iteration merges; the region's Newton, capped too, ends `BUDGET_EXHAUSTED(newton_iterations)`;
    edge 3 is due and recorded `unsupported` beside `merge_into_eo: taken`."""
    from test_t02_executor import nominal

    solve_policy = SolvePolicy(
        policy_id="T04-merge-then-edge",
        residual_tolerances={},
        scales={},
        max_iterations_per_attempt=1,
        recycle=RecyclePolicy(method="anderson", max_iterations_per_attempt=1),
    )
    result = nominal(solve_policy).result
    (converge,) = [step for step in result.steps if step.kind == "converge"]
    assert converge.merge_into_eo == "taken"
    assert converge.detail.outcome == "BUDGET_EXHAUSTED"
    assert converge.detail.budget == "newton_iterations"
    assert converge.eo_recovery == "unsupported"
    assert converge.eo_recovery_unsupported == "no_continuation_parameter"
    assert not result.trace.of_kind("homotopy_step")


def test_a09_hom_n_with_the_edge_off_phs_05_cycles_exactly_as_t03_a12() -> None:
    """`eo_recovery: none`: the step ends `ACTIVE_SET_CYCLING` with T03 A12's message and
    attempts, no `homotopy_step`, and nothing recorded about a recovery."""
    result = plan_run(case_document("HOM-01"), case_policy("HOM-01", NONE)).result
    step = region_step(result)
    assert result.outcome == "ACTIVE_SET_CYCLING"
    assert step.eo_recovery is None and step.recovered_from is None
    assert not result.trace.of_kind("homotopy_step")
    assert step.detail.message == region_step(run("HOM-01")).recovered_from.message
    with_edge = region_step(run("HOM-01")).recovered_from.branch_provenance
    assert [dict(item) for item in step.detail.branch_provenance] == [dict(i) for i in with_edge]
    assert "eo_recovery" not in result.trace.of_kind("region_closed")[-1].as_document()


def test_a09_a_spent_property_budget_is_not_a_trigger() -> None:
    """T03 review S1's P3b case (PHS-01 capped at 346 property calls) under the default policy:
    `BUDGET_EXHAUSTED(property_calls)` stands and the edge is not considered."""
    from test_t03_contract import capped_phs_01

    run_, _ = capped_phs_01(346)
    step = region_step(run_.result)
    assert run_.result.outcome == "BUDGET_EXHAUSTED"
    assert step.detail.budget == "property_calls"
    assert step.eo_recovery is None
    assert not run_.result.trace.of_kind("homotopy_step")


def test_a09_a_constructed_incompatible_opening_is_not_a_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T03 A16's constructed refusal, through the executor: PHS-01's restart is refused at the
    opening checks, the step ends `CHECKPOINT_INCOMPATIBLE` (a defect), and no recovery runs."""
    monkeypatch.setattr(
        region_module,
        "check_opening",
        lambda state, requirement: OpeningRefusal("coverage", "S3.T"),
    )
    document = yaml.safe_load((CASES / "SYN-001-A02-355-liquid-guess.yaml").read_text())
    result = plan_run(
        document, SolvePolicy(policy_id="T04", residual_tolerances={}, scales={})
    ).result
    step = region_step(result)
    assert result.outcome == "CHECKPOINT_INCOMPATIBLE"
    assert step.eo_recovery is None
    assert not result.trace.of_kind("homotopy_step")


def test_a09_rcy_stalls_linear_solve_failure_is_not_a_trigger() -> None:
    """RCY-STALL's merge ends `LINEAR_SOLVE_FAILED` (T02 A16). It runs through
    `converge_with_merge`, which is not a plan step, so edge 3 cannot reach it; the executor's edge
    given a region solve that ended that way leaves the step as it is."""
    step = StepResult(
        1,
        "solve_eo",
        ("U-HEAT",),
        "LINEAR_SOLVE_FAILED",
        detail=RegionResult(outcome="LINEAR_SOLVE_FAILED", state={}, attempts=()),
    )
    unchanged = executor_module._eo_recovery(
        step,
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        SolvePolicy(policy_id="T04", residual_tolerances={}, scales={}),
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        {},
        0,
    )
    assert unchanged[0] is step


@pytest.mark.parametrize("case_id", ["HOM-03", "HOM-04"])
def test_a09_a_failed_recovery_does_not_fire_the_edge_again(case_id: str) -> None:
    """One recovery per region step: one easy endpoint, one homotopy attempt, one `taken`."""
    result = run(case_id)
    steps = result.trace.of_kind("homotopy_step")
    assert [e.iteration for e in steps] == list(range(len(steps)))
    assert sum(1 for e in steps if e.iteration == 0) == 1
    closed = result.trace.of_kind("region_closed")
    assert [e.eo_recovery for e in closed] == [None, "taken"][-len(closed) :]
    homotopy_attempts = [
        item for item in region_step(result).detail.branch_provenance if item["core"] == "homotopy"
    ]
    assert len(homotopy_attempts) == 1


def test_a09_the_provenance_continuation_refuses_a_wrong_first_item() -> None:
    failed = ({"attempt": 0, "initializer_source": "user_guess"},)
    good = (
        {"attempt": 0, "opening_source": "eo_recovery_start", "initializer_source": "user_guess"},
    )
    assert [item["attempt"] for item in recovered_provenance(failed, good)] == [0, 1]
    with pytest.raises(ValueError, match="item-0 state"):
        recovered_provenance(failed, ({**good[0], "opening_source": "initializer"},))
    with pytest.raises(ValueError, match="item-0 state"):
        recovered_provenance(failed, ({**good[0], "initializer_source": None},))


# ------------------------------------------------------------------ A10: unchanged physics


@dataclass
class Spy:
    rebound: list[dict[str, float]]
    compiled: list[Any]


@pytest.mark.parametrize("case_id", HOM)
def test_a10_the_recovery_solves_the_same_problem(
    case_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§5.4: the λ = 1 instance's identity is the failed solve's; the recovery's attempt 0 has
    the failed attempt 0's rows and columns; every λ < 1 level differs from the target only at the
    continued id (spy on the re-binding); the fingerprint of a converged recovery is the
    revision's identity."""
    from openflowsheet.orchestrator import homotopy

    spy = Spy([], [])
    real_rebind = homotopy.rebind

    def rebind(spec: Any, values: dict[str, float]) -> Any:
        spy.rebound.append(dict(values))
        level = real_rebind(spec, values)
        changed = {k for k in spec.parameters if level.parameters[k] != spec.parameters[k]}
        assert changed <= set(values) == {CONTINUED}
        assert level.variable_ids == spec.variable_ids and level.equations == spec.equations
        return level

    monkeypatch.setattr(region_module, "rebind", rebind)
    result = plan_run(case_document(case_id), case_policy(case_id)).result
    step = region_step(result)
    failed, recovery = step.recovered_from, step.detail
    target = failed.contexts[0].evaluation_context
    at_one = recovery.contexts[0].evaluation_context
    assert (at_one.model_version, at_one.constants_sha256) == (
        target.model_version,
        target.constants_sha256,
    )
    assert list(recovery.contexts[0].row_scales) == list(failed.contexts[0].row_scales)
    assert list(recovery.contexts[0].column_scales) == list(failed.contexts[0].column_scales)
    assert recovery.contexts[0].signature == failed.contexts[0].signature
    lambdas = {t.lambda_value for t in recovery.homotopy.trials if t.lambda_value != 1}
    assert len(spy.rebound) == len(lambdas)
    steps = [e for e in result.trace.of_kind("homotopy_step")]
    for event in steps:
        if event.lambda_value == "1":
            assert event.level_constants_sha256 == target.constants_sha256
        else:
            assert event.level_constants_sha256 != target.constants_sha256
    if recovery.outcome == "CONVERGED":
        fingerprint = recovery.root_fingerprint
        assert fingerprint["model_version"] == target.model_version
        assert fingerprint["constants_sha256"] == target.constants_sha256


# ------------------------------------------------------------------ A12 on the plan trace


def test_a12_the_plan_trace_is_well_formed_and_validates() -> None:
    """A33's well-formedness (one `plan_built`, one `solve_closed`, bracketed steps, every event
    in a step stamped) with the recovery inside its step, and every event against the schema."""
    from test_t02_executor import well_formed

    schema = json.loads((REPO_ROOT / "schemas" / "solve-event.schema.json").read_text())
    validator = Draft202012Validator(schema)
    for case_id in HOM:
        well_formed(full_run(case_id), validator)
        result = run(case_id)
        level_events = [e for e in result.trace.events if e.homotopy_level is not None]
        assert level_events and all(e.step_index is not None for e in level_events)


# ------------------------------------------------------------------ A28: a refusal inside


def test_a28_a_property_refusal_inside_a_corrector_keeps_everything() -> None:
    """HOM-01 with the property cap set between the λ = 1/4 acceptance and the λ = 3/4 corrector's
    end: `BUDGET_EXHAUSTED(property_calls)`, the contract's attempts and the recovery's item kept,
    and the checkpoint the last accepted level's (λ = 1/4, `partial`) — T03 review S1's shape."""
    free = run("HOM-01")
    steps = free.trace.of_kind("homotopy_step")
    quarter, three_quarters = steps[1], steps[2]
    assert (quarter.lambda_value, three_quarters.lambda_value) == ("1/4", "3/4")
    cap = (quarter.counters.property_calls + three_quarters.counters.property_calls) // 2
    assert quarter.counters.property_calls < cap < three_quarters.counters.property_calls
    policy = replace(case_policy("HOM-01"), max_property_calls=cap)
    result = plan_run(case_document("HOM-01"), policy).result
    step = region_step(result)
    assert result.outcome == "BUDGET_EXHAUSTED"
    assert result.counters.property_calls == cap
    assert step.eo_recovery == "taken"
    recovery = step.detail
    assert recovery.budget == "property_calls"
    assert len(step.recovered_from.branch_provenance) == 2
    assert [item["core"] for item in recovery.branch_provenance] == ["newton", "newton", "homotopy"]
    assert recovery.branch_provenance[-1]["continuation"]["lambda_reached"] == "1/4"
    assert step.checkpoint is not None
    assert (step.checkpoint.continuation_lambda, step.checkpoint.label) == ("1/4", "partial")
    assert close(result.state["S3.T"], HOMOTOPY_CASES["HOM-01"]["homotopy"]["steps"][1]["S3_T_K"])


# ------------------------------------------------------------------ A11: the family scan


def family_duty(target: int) -> float:
    """The registered `Q_flash(T)` where a YAML carries it, the SYN-001 oracle's otherwise."""
    from benchmarks.syn001.oracle import recycle_oracle

    sweep = reference("t02")["syn001"]["a02_sweep"]
    registered = {int(key.split("=")[1][:-1]): row["Q_flash_W"] for key, row in sweep.items()}
    registered[352] = HOMOTOPY_CASES["HOM-03"]["Q_flash_spec_W"]
    oracle = recycle_oracle((1.0, 1.0, 1.0), 0.5, 360.0, T_heater=float(target)).Q_flash
    if target in registered:
        assert abs(oracle - float(registered[target])) <= 1e-9 * max(1.0, abs(oracle))
        return float(registered[target])
    return float(oracle)


@cache
def family_run(target: Any, guess: Any) -> tuple[dict[str, Any], Any]:
    """One run of §9.3's scan — its revision and its plan run under the default policy — keyed by
    the registered target and guess as the YAML spells them. Shared by A11 and K04-F9's X04
    (`test_k04f9_family`), so the gate solves the 180 runs once."""
    document = document_for(float(guess), family_duty(int(target)), f"FAM-{target}-{guess}")
    return document, plan_run(
        document, SolvePolicy(policy_id="T04-FAM", residual_tolerances={}, scales={})
    )


def test_a11_the_family_scan(record_property: Callable[[str, Any], None]) -> None:
    """§9.3: 10 targets × 18 guesses = 180 runs under the default policy. Exactly the registered
    contract failures, each with its edge-3 outcome and λ-trial count; every other run converges
    by the contract alone, with no recovery; and every run's contract attempts — signature, core
    outcome, iterations, decision, in order — equal `ref.ptc.a02_family_scan.contract_attempts`
    (A11 as amended, review S4: all 180 records, exactly)."""
    scan = T04["policy_simulation"]["a02_family_scan"]
    failures = {
        (int(entry["T_target_K"]), float(entry["guess_K"])): entry
        for entry in scan["contract_failures"]
    }
    registered_attempts = {
        (int(entry["T_target_K"]), float(entry["guess_K"])): entry
        for entry in scan["contract_attempts"]
    }
    assert len(registered_attempts) == 180
    started = time.perf_counter()
    seen: dict[tuple[int, float], tuple[str, str | None, str, int | None]] = {}
    attempts: dict[tuple[int, float], tuple[str, list[list[Any]]]] = {}
    for target in scan["targets_K"]:
        for guess in scan["guesses_K"]:
            key = (int(target), float(guess))
            result = family_run(target, guess)[1].result
            step = region_step(result)
            contract = step.recovered_from.outcome if step.recovered_from else step.outcome
            trials = (
                len(step.detail.homotopy.trials) - 1 if step.detail.homotopy is not None else None
            )
            seen[key] = (contract, step.eo_recovery, result.outcome, trials)
            solve = step.recovered_from if step.recovered_from is not None else step.detail
            attempts[key] = (
                contract,
                [
                    [
                        ",".join(f"{unit}:{regime}" for unit, regime in item["signature"]),
                        item["core_outcome"],
                        item["iterations"],
                        item["decision"],
                    ]
                    for item in solve.branch_provenance
                ],
            )
    elapsed = time.perf_counter() - started
    record_property("family_scan_seconds", round(elapsed, 1))
    assert len(seen) == scan["runs"] == 180
    for key, (contract, edge, outcome, trials) in seen.items():
        if key in failures:
            entry = failures[key]
            assert (contract, edge, outcome, trials) == (
                entry["contract"],
                entry["edge3"],
                entry["outcome"],
                entry["lambda_trials"],
            ), key
        else:
            assert (contract, edge, outcome, trials) == ("CONVERGED", None, "CONVERGED", None), key
    differing = [
        key
        for key, (contract, recorded) in attempts.items()
        if (contract, recorded)
        != (registered_attempts[key]["contract"], registered_attempts[key]["attempts"])
    ]
    assert set(attempts) == set(registered_attempts)
    assert differing == [], [(key, attempts[key], registered_attempts[key]) for key in differing]
