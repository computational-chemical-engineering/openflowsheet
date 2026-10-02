"""T02 A33 (and the SYN-001 halves of §4.4): a plan run's trace, with ADR 0009's kinds.

One trace per plan run: `plan_built` once (with `step_count`), every step bracketed in plan order —
`unit_evaluated` for an `evaluate`, `region_opened` … `region_closed` for a `converge` or `solve_eo`
— every event inside a step stamped with its `step_index`, the inner solves' own `plan_built` and
`solve_closed` absorbed, and one `solve_closed` whose outcome is the result's. Every event validates
against the extended `solve-event` schema and serializes without a non-finite number.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from openflowsheet.application.binding import Binding, bind_revision, structural_inputs
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.budget import PropertyMeter
from openflowsheet.orchestrator.execution import (
    ExecutionPlan,
    build_execution_plan,
    declaration_identity,
    specification_regions,
)
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.trace import RecyclePolicy, SolvePolicy
from openflowsheet.thermo.syn001 import Syn001Provider

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES = REPO_ROOT / "benchmarks" / "syn001" / "cases"


@dataclass(frozen=True)
class Run:
    plan: ExecutionPlan
    result: PlanResult


def policy(method: str = "auto", **recycle: Any) -> SolvePolicy:
    return SolvePolicy(
        policy_id=f"T02-{method}",
        residual_tolerances={},
        scales={},
        recycle=RecyclePolicy(method=method, **recycle),  # type: ignore[arg-type]
    )


def heater_without_derivatives(manifests: dict[str, Any]) -> dict[str, Any]:
    heater = dict(manifests["U-HEAT"])
    heater["derivatives"] = [
        {**entry, "method": "unavailable"} if entry["output"] == "residuals" else entry
        for entry in heater["derivatives"]
    ]
    return {**manifests, "U-HEAT": heater}


def run_flowsheet(
    flowsheet: Syn001Flowsheet,
    spec: ProblemSpec,
    graph: Any,
    row_units: Mapping[str, str],
    solve_policy: SolvePolicy,
    *,
    specification_ids: Mapping[str, str] | None = None,
    freed: Mapping[str, str] | None = None,
    promoted: Mapping[str, str] | None = None,
    manifests: dict[str, Any] | None = None,
    missing_guesses: tuple[str, ...] = (),
) -> Run:
    model_version, constants = declaration_identity(spec)
    identity = {
        "row_units": row_units,
        "specification_ids": specification_ids or {},
        "model_version": model_version,
        "constants_sha256": constants,
    }
    declaration = trace_declaration(spec, **identity)
    report = analyse(spec, graph, **identity)
    regions = (
        specification_regions(
            declaration,
            graph,
            report,
            freed=freed,
            promoted=promoted or {},
            missing_guesses=missing_guesses,
        )
        if freed
        else ()
    )
    plan = build_execution_plan(
        spec=spec,
        declaration=declaration,
        graph=graph,
        report=report,
        manifests=manifests or {unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=solve_policy,
        specifications=regions,
    )
    result = execute_plan(plan=plan, flowsheet=flowsheet, spec=spec, policy=solve_policy)
    return Run(plan, result)


def nominal(solve_policy: SolvePolicy, manifests: dict[str, Any] | None = None) -> Run:
    flowsheet = Syn001Flowsheet(
        provider=PropertyMeter(Syn001Provider()),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    spec, graph, row_units = structural_inputs(flowsheet)
    if manifests is None:
        manifests = {unit.unit_id: unit.manifest() for unit in flowsheet.units()}
    return run_flowsheet(flowsheet, spec, graph, row_units, solve_policy, manifests=manifests)


def revision_run(case_id: str) -> Run:
    binding = bind_revision(yaml.safe_load((CASES / f"{case_id}.yaml").read_text()))
    assert isinstance(binding, Binding)
    return run_flowsheet(
        binding.flowsheet,
        binding.spec,
        binding.graph,
        binding.row_units,
        policy(),
        specification_ids=binding.specification_ids,
        freed=binding.freed,
        promoted=binding.promoted,
        missing_guesses=binding.missing_guesses,
    )


@pytest.fixture(scope="module")
def event_validator() -> Draft202012Validator:
    schema = json.loads((REPO_ROOT / "schemas" / "solve-event.schema.json").read_text())
    return Draft202012Validator(schema)


def well_formed(run: Run, validator: Draft202012Validator) -> None:
    """A33, stated once and applied to every run below."""
    events = run.result.trace.events
    assert [event.sequence for event in events] == list(range(len(events)))
    assert events[0].kind == "plan_built" and events[0].step_count == len(run.plan.steps)
    assert events[-1].kind == "solve_closed" and events[-1].outcome == run.result.outcome
    assert len(run.result.trace.of_kind("plan_built")) == 1
    assert len(run.result.trace.of_kind("solve_closed")) == 1

    # The brackets, in plan order, with every event inside a step stamped with its index.
    opened: int | None = None
    order: list[int] = []
    for event in events[1:-1]:
        if event.kind == "unit_evaluated":
            assert opened is None
            order.append(int(event.step_index))  # type: ignore[arg-type]
        elif event.kind == "region_opened":
            assert opened is None
            opened = event.step_index
            order.append(int(event.step_index))  # type: ignore[arg-type]
        elif event.kind == "region_closed":
            assert event.step_index == opened
            opened = None
        else:
            assert opened is not None, f"{event.kind} outside every step"
            assert event.step_index == opened
    assert opened is None
    assert order == [step.index for step in run.plan.steps][: len(order)]
    assert len(order) == len(run.result.steps)

    for event in events:
        document = event.as_document()
        json.dumps(document, allow_nan=False)  # no non-finite number anywhere
        errors = list(validator.iter_errors(document))
        assert not errors, (event.kind, errors[0].message)
        if event.kind == "acceleration":
            assert event.depth_used is not None and 0 <= event.depth_used <= min(5, 3)
            assert event.columns_dropped_condition is not None
            assert event.columns_dropped_coefficient is not None
            assert event.beta_substitution in (1.0, 0.5)
            accelerated = event.depth_used >= 1
            assert (document["kappa_2"] is not None) == accelerated
            assert (document["gamma_inf"] is not None) == accelerated
        if event.kind == "restart":
            assert event.restart_reason == "stagnation"
            assert event.restart_count is not None and event.restart_count <= 2


@pytest.mark.parametrize(
    "name",
    ["tear", "anderson", "eo"],
)
def test_a33_nominal_plans_run_to_the_registered_answer_on_one_trace(
    name: str, event_validator: Draft202012Validator
) -> None:
    method = {"tear": "auto", "anderson": "anderson", "eo": "eo"}[name]
    run = nominal(policy(method))
    assert run.result.outcome == "CONVERGED"
    well_formed(run, event_validator)
    kinds = [step.kind for step in run.plan.steps]
    assert kinds == (["evaluate", "solve_eo"] if name == "eo" else ["evaluate", "converge"])
    if name == "anderson":
        assert run.result.trace.of_kind("acceleration"), "the recycle's decisions are recorded"
    assert run.result.state is not None and run.result.state["S3.V"] >= 0.0


@pytest.mark.parametrize(
    ("case_id", "outcome"),
    [
        ("SYN-001-A02-360", "CONVERGED"),
        # T03 §10.1: re-registered CONVERGED under ADR 0005's contract (was ACTIVE_SET_CYCLING).
        ("SYN-001-A02-355-liquid-guess", "CONVERGED"),
    ],
)
def test_a33_a02_plans_run_on_one_trace(
    case_id: str, outcome: str, event_validator: Draft202012Validator
) -> None:
    run = revision_run(case_id)
    assert run.result.outcome == outcome
    well_formed(run, event_validator)
    if outcome == "CONVERGED":
        assert run.result.state is not None
        target = 355.0 if "355" in case_id else 360.0
        assert abs(run.result.state["S3.T"] - target) <= 1e-5
    counters = run.result.counters
    assert counters.property_calls > 0, "the pre-solve's provider calls are metered"
    # And the region's own: the counters rise between the step's first inner event and its close.
    events = run.result.trace.events
    region_events = [event for event in events if event.step_index == run.plan.steps[-1].index]
    inside = [event for event in region_events if event.kind == "attempt_opened"]
    assert inside and region_events[-1].counters.property_calls > inside[0].counters.property_calls
    region = run.result.steps[-1]
    assert region.checkpoint is not None and region.checkpoint.step_index == region.index
    expected = "candidate_root" if outcome == "CONVERGED" else "partial"
    assert region.checkpoint.label == expected


def test_a33_the_stalled_anderson_loop_merges_into_its_region(
    event_validator: Draft202012Validator,
) -> None:
    """§4.4 on SYN-001: a recycle budget of one iteration exhausts the Anderson attempt; the step
    re-solves once as `region_on_merge` from the best iterate, and says so on its closing event."""
    run = nominal(policy("anderson", max_iterations_per_attempt=1))
    well_formed(run, event_validator)
    (converge,) = [step for step in run.result.steps if step.kind == "converge"]
    assert converge.merge_into_eo == "taken"
    assert run.result.outcome == "CONVERGED"
    (closing,) = [
        event
        for event in run.result.trace.of_kind("region_closed")
        if event.step_index == converge.index
    ]
    assert closing.merge_into_eo == "taken"
    assert closing.as_document()["merge_into_eo"] == "taken"


def test_a32_merge_u_on_syn001_ends_with_the_recycles_outcome(
    event_validator: Draft202012Validator,
) -> None:
    """The heater without EO derivatives: `auto` resolves to Anderson and the plan records the
    merge as unsupported; a stalled loop ends `BUDGET_EXHAUSTED` with the reason on the closing
    event and no residual call after the recycle's closure."""
    flowsheet = Syn001Flowsheet(
        provider=PropertyMeter(Syn001Provider()),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    manifests = heater_without_derivatives(
        {unit.unit_id: unit.manifest() for unit in flowsheet.units()}
    )
    run = nominal(policy(max_iterations_per_attempt=1), manifests)
    well_formed(run, event_validator)
    (converge,) = [step for step in run.result.steps if step.kind == "converge"]
    assert converge.outcome == run.result.outcome == "BUDGET_EXHAUSTED"
    assert converge.merge_into_eo == "unsupported"
    assert converge.merge_unsupported == ("U-HEAT", "unavailable")
    events = run.result.trace.events
    (closing,) = [event for event in events if event.kind == "region_closed"]
    assert closing.as_document()["merge_unsupported"] == {"unit": "U-HEAT", "method": "unavailable"}
    assert 'unsupported(U-HEAT, "derivatives: unavailable")' in closing.message
    recycle_closed = max(event.sequence for event in events if event.kind == "attempt_closed")
    after = [event for event in events if event.sequence > recycle_closed]
    assert all(
        event.counters.residual_calls == events[recycle_closed].counters.residual_calls
        for event in after
    ), "no residual call after the closure"


def test_an_unmetered_flowsheet_is_refused_rather_than_reported_as_zero() -> None:
    """Region steps count provider calls through the flowsheet's `PropertyMeter`; without one
    the run refuses, because a structurally zero counter would read as a measurement."""
    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    spec, graph, row_units = structural_inputs(flowsheet)
    with pytest.raises(TypeError, match="PropertyMeter"):
        run_flowsheet(flowsheet, spec, graph, row_units, policy("eo"))


# ------------------------------------------------------------------ review M1 and M3


def heater_duty_revision(value: float = 40_000.0) -> Binding:
    """Review M1's probe: A02-360 with its duty specification retargeted to the *heater*."""
    document = yaml.safe_load((CASES / "SYN-001-A02-360.yaml").read_text())
    for entry in document["specifications"]:
        if entry["id"] == "SPEC-flash-duty":
            entry["id"] = "SPEC-heater-duty"
            entry["target"]["object_id"] = "heater"
            entry["value"] = value
    binding = bind_revision(document)
    assert isinstance(binding, Binding)
    return binding


def test_m1_a_one_owner_freed_and_promoted_pair_is_a_region_and_meets_its_specification(
    event_validator: Draft202012Validator,
) -> None:
    """Before the fix: planned as a plain tear, `CONVERGED` with the heater at its 358 K guess and
    `U-HEAT.Q = 46 381 W` against 40 000 W specified. The closed form (§7.6) puts the answer
    between 355 K (31 657 W) and 358 K (46 381 W)."""
    binding = heater_duty_revision()
    run = run_flowsheet(
        binding.flowsheet,
        binding.spec,
        binding.graph,
        binding.row_units,
        policy(),
        specification_ids=binding.specification_ids,
        freed=binding.freed,
        promoted=binding.promoted,
    )
    assert [step.kind for step in run.plan.steps] == ["evaluate", "solve_eo"]
    well_formed(run, event_validator)
    assert run.result.outcome == "CONVERGED"
    state = run.result.state
    assert state is not None
    assert abs(state["U-HEAT.Q"] - 40_000.0) <= 1e-2
    assert 355.0 < state["S3.T"] < 358.0


def test_m3_a_converge_step_on_another_declaration_is_refused_before_it_runs() -> None:
    """The A02 declaration planned *without* its region (a converge step over rows the flowsheet
    does not have): the step never runs, and never reports `CONVERGED`."""
    binding = bind_revision(yaml.safe_load((CASES / "SYN-001-A02-360.yaml").read_text()))
    assert isinstance(binding, Binding)
    run = run_flowsheet(binding.flowsheet, binding.spec, binding.graph, binding.row_units, policy())
    (converge,) = [step for step in run.result.steps if step.kind == "converge"]
    assert converge.outcome == run.result.outcome == "UNSUPPORTED_RANK_STRUCTURE"
    assert "HEAT-T" in converge.message and "SPEC-flash-duty" in converge.message
    assert run.result.counters.residual_calls == 0, "nothing ran"


def test_m3_an_executed_plan_that_differs_from_the_recorded_one_is_not_reported() -> None:
    from dataclasses import replace

    flowsheet = Syn001Flowsheet(
        provider=PropertyMeter(Syn001Provider()),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    run = nominal(policy())
    converge = run.plan.steps[1]
    assert converge.solve_plan is not None
    altered = replace(
        converge,
        solve_plan=replace(converge.solve_plan, tear_variable_ids=("S3.n.A", "S3.n.B", "S3.n.C")),
    )
    plan = replace(run.plan, steps=(run.plan.steps[0], altered))
    spec, _, _ = structural_inputs(flowsheet)
    result = execute_plan(plan=plan, flowsheet=flowsheet, spec=spec, policy=policy())
    assert result.outcome == "UNSUPPORTED_RANK_STRUCTURE"
    assert "tear_variable_ids" in result.steps[1].message
    assert result.state is None


# ------------------------------------------------------------------ review S4, S7, S8


def test_s4_a_region_spends_no_more_than_the_budget_leaves() -> None:
    """A02-360 spends 155 provider calls in the pre-solve and 92 in the region. At a cap of 200 the
    region is refused its 46th call: `BUDGET_EXHAUSTED`, and the count is exactly the cap."""
    binding = bind_revision(yaml.safe_load((CASES / "SYN-001-A02-360.yaml").read_text()))
    assert isinstance(binding, Binding)
    capped = SolvePolicy(
        policy_id="T02-capped", residual_tolerances={}, scales={}, max_property_calls=200
    )
    run = run_flowsheet(
        binding.flowsheet,
        binding.spec,
        binding.graph,
        binding.row_units,
        capped,
        specification_ids=binding.specification_ids,
        freed=binding.freed,
        promoted=binding.promoted,
    )
    assert run.result.outcome == "BUDGET_EXHAUSTED"
    assert run.result.counters.property_calls == 200
    assert "property-call budget of 200" in run.result.message


def test_s7_attempt_indices_increase_within_a_step() -> None:
    """The pre-solve's attempt and the region's are 0 and 1, not two attempt 0s."""
    run = revision_run("SYN-001-A02-360")
    opened = [event.attempt for event in run.result.trace.events if event.kind == "attempt_opened"]
    assert opened == sorted(set(opened)) and len(opened) >= 2


def test_s8_a_merged_step_keeps_the_recycles_result() -> None:
    run = nominal(policy("anderson", max_iterations_per_attempt=1))
    (converge,) = [step for step in run.result.steps if step.kind == "converge"]
    assert converge.merge_into_eo == "taken"
    assert converge.recycle is not None and converge.recycle.outcome == "BUDGET_EXHAUSTED"
    assert converge.detail is not None and converge.detail.outcome == "CONVERGED"


def test_n9_an_evaluate_step_this_runner_cannot_run_is_a_typed_refusal() -> None:
    from dataclasses import replace

    run = nominal(policy())
    feed, converge = run.plan.steps
    plan = replace(run.plan, steps=(replace(feed, units=("U-MIX",)), converge))
    flowsheet = Syn001Flowsheet(
        provider=PropertyMeter(Syn001Provider()),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    spec, _, _ = structural_inputs(flowsheet)
    result = execute_plan(plan=plan, flowsheet=flowsheet, spec=spec, policy=policy())
    assert result.outcome == "UNSUPPORTED_RANK_STRUCTURE"
    assert "U-MIX" in result.message
    assert result.trace.events[-1].kind == "solve_closed"
