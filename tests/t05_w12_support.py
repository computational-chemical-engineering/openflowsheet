"""Shared support for T05 W12's tests: region solves started at a given state, the twin's states,
and the mini-revisions (feed → unit → sinks) the injections run on.

Not collected as tests. Design note `docs/design/T05-generalization.md` §8 (W12): a state the
traversal cannot reach (INJ-T2, C3X's second branch) is solved by `solve_region(...,
state=<twin state>, initializer_source="user_guess")` over the region `plan_revision` plans —
the call `orchestrator.executor` makes for a revision flowsheet, with no new API.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from test_t05_w11_cases import case_document

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.execution import ExecutionPlan, PlanStep
from openflowsheet.orchestrator.mass import residence_time
from openflowsheet.orchestrator.region import RegionResult, solve_region
from openflowsheet.orchestrator.splits import lifted_splits
from openflowsheet.orchestrator.trace import SolvePolicy

Document = dict[str, Any]

POLICY = SolvePolicy(policy_id="T05-W12", residual_tolerances={}, scales={})


def bind(document: Document) -> RevisionBinding:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    return binding


def planned_step(binding: RevisionBinding, policy: SolvePolicy = POLICY) -> PlanStep:
    """The one `solve_eo` step `plan_revision` plans for a revision flowsheet (§2.1)."""
    plan, _ = revision.plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    (step,) = plan.steps
    assert step.kind == "solve_eo" and step.region is not None
    return step


def solve_from(
    binding: RevisionBinding, state: Mapping[str, float], policy: SolvePolicy = POLICY
) -> tuple[RegionResult, PlanStep]:
    """The planned region solved from `state` (a full state over the spec's variables), as
    `executor._region` calls `solve_region` for a revision flowsheet, with item 0's source
    `user_guess`: the state is the user's, not the registered initializer's."""
    step = planned_step(binding, policy)
    flowsheet, spec = binding.flowsheet, binding.spec
    missing = [column for column in spec.variable_ids if column not in state]
    assert not missing, f"the start has no value for {missing}"
    assert step.region is not None
    result = solve_region(
        compiled=compile_problem(spec),
        spec=spec,
        region=step.region,
        state={column: state[column] for column in spec.variable_ids},
        splits=lifted_splits(revision.instances_of(flowsheet), flowsheet.components),
        provider=flowsheet.provider,
        policy=policy,
        initializer_source="user_guess",
        mass_mapping=residence_time(flowsheet.wiring, flowsheet.components),
    )
    return result, step


# -- mini-revisions: feed(s) -> one unit -> sinks ----------------------------------------------


@dataclass(frozen=True)
class Feed:
    port: str
    stream: str
    capability: str
    flows: tuple[float, float, float]
    temperature: float
    pressure: float


@dataclass(frozen=True)
class Outlet:
    port: str
    stream: str
    capability: str


def _find(items: Sequence[dict[str, Any]], identifier: str) -> dict[str, Any]:
    (found,) = (item for item in items if item["id"] == identifier)
    return found


#: The templates: C1's feed, sink, first connection and specifications (schema-valid, W11).
_C1 = case_document("SYN-001-UL-C1")


def unit_instance(case: str, unit: str) -> Document:
    """A registered case's instance, copied (its parameters are the case's)."""
    return copy.deepcopy(_find(case_document(case)["instances"], unit))


def connection_pin(identifier: str, stream: str, path: str, value: float) -> Document:
    """A `role: fixed` specification on a connection's `state.T` or `state.P`."""
    template = {"state.P": "SPEC-pump-P", "state.T": "SPEC-heater-outlet-T"}[path]
    pin = copy.deepcopy(_find(_C1["specifications"], template))
    pin["id"] = identifier
    pin["target"]["object_id"] = stream
    pin["value"] = value
    return pin


def duty_pin(identifier: str, unit: str, value: float) -> Document:
    """A `role: fixed` specification on an instance's `duty.Q`."""
    pin = copy.deepcopy(_find(_C1["specifications"], "SPEC-phf-Q"))
    pin["id"] = identifier
    pin["target"]["object_id"] = unit
    pin["value"] = value
    return pin


def mini_revision(
    name: str,
    unit: Document,
    feeds: Sequence[Feed],
    outlets: Sequence[Outlet],
    pins: Sequence[Document],
) -> Document:
    """feed(s) → `unit` → one sink per outlet, streams in the order given (feeds first).

    Feed `k` is `U-FEED-<k>` with C1's feed specifications retargeted and revalued; sink `k` is
    `U-SINK-<k>`. Everything else is C1's document (schema version, components, provenance)."""
    document = copy.deepcopy(_C1)
    document["revision_id"] = f"T05-W12-{name}"
    document["title"] = f"T05 W12 test fixture: {name}"
    feed, sink = _find(_C1["instances"], "U-FEED"), _find(_C1["instances"], "U-SINK-V")
    template = _find(_C1["connections"], "S1")
    specifications = {
        path: _find(_C1["specifications"], f"SPEC-feed-{path}")
        for path in ("n-A", "n-B", "n-C", "T", "P")
    }
    instances: list[Document] = [unit]
    connections: list[Document] = []
    pinned: list[Document] = []
    for k, entry in enumerate(feeds):
        feed_id = f"U-FEED-{k}"
        instances.append(dict(copy.deepcopy(feed), id=feed_id))
        connections.append(
            dict(
                copy.deepcopy(template),
                id=entry.stream,
                phase_capability=entry.capability,
                **{"from": {"instance": feed_id, "port": "outlet"}},
                to={"instance": unit["id"], "port": entry.port},
            )
        )
        values = {
            "n-A": entry.flows[0],
            "n-B": entry.flows[1],
            "n-C": entry.flows[2],
            "T": entry.temperature,
            "P": entry.pressure,
        }
        for path, specification in specifications.items():
            spec = copy.deepcopy(specification)
            spec["id"] = f"SPEC-{entry.stream}-{path}"
            spec["target"]["object_id"] = entry.stream
            spec["value"] = values[path]
            pinned.append(spec)
    for k, entry in enumerate(outlets):
        sink_id = f"U-SINK-{k}"
        instances.append(dict(copy.deepcopy(sink), id=sink_id))
        connections.append(
            dict(
                copy.deepcopy(template),
                id=entry.stream,
                phase_capability=entry.capability,
                **{"from": {"instance": unit["id"], "port": entry.port}},
                to={"instance": sink_id, "port": "inlet"},
            )
        )
    document.update(instances=instances, connections=connections, specifications=[*pinned, *pins])
    return document
