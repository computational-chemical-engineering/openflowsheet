"""T05 W1.c: a revision-built flowsheet planned and solved as one EO region.

Design note `docs/design/T05-generalization.md` §2 and §7 (W1.c), register R-045. The reference is
SYN-001 itself, through the SYN-001-shaped revision (`t05_syn001_shaped`): the general start
(`initial_state`, `traversal-G0-v1`) must be the legacy start **bitwise**, variable by variable;
the general plan is one `solve_eo` step over the five units with rows; and the solve from it must
land on P01's 20-digit nominal values within T02 §6.4's allowances — an independent expectation,
not the tear path's output. What the general path does not run is refused, typed.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from t05_syn001_shaped import shaped_revision

from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import (
    MODEL_BUILDERS,
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.execution import (
    ExecutionPlan,
    build_execution_plan,
    declaration_identity,
)
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.mass import RegionMass, residence_time, resolve_mass
from openflowsheet.orchestrator.region import RegionResult, syn001_lifted_splits
from openflowsheet.orchestrator.revision import (
    INITIALIZER_ID,
    InitialStateFailure,
    initial_state,
    instances_of,
    plan_revision,
)
from openflowsheet.orchestrator.splits import SPLIT_RULES, check_agreement, lifted_splits
from openflowsheet.orchestrator.tear import Syn001TearProblem, solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.run.session import run_session, solve_and_bundle
from openflowsheet.thermo.syn001 import Syn001Provider

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE = REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml"
SCHEMA_BASE = "https://github.com/frankp/process-runtime/schemas/"
POLICY = SolvePolicy(policy_id="T05-W1c", residual_tolerances={}, scales={})
#: T02 §6.4: ten times each kind's residual tolerance.
AGREEMENT = {"molar_flow": 3.1e-7, "temperature": 1e-5, "pressure": 0.1, "heat_rate": 1e-2}
REGION_UNITS = ("U-FEED", "U-MIX", "U-HEAT", "U-FLASH", "U-SPLIT")


def _bind(document: Mapping[str, Any]) -> RevisionBinding:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    return binding


def _plan(binding: RevisionBinding) -> ExecutionPlan:
    plan, _ = plan_revision(binding, POLICY)
    assert isinstance(plan, ExecutionPlan), plan
    return plan


def _legacy() -> Syn001Flowsheet:
    return Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t05-w1c", constants_sha256="0" * 64, phase_signature=None
        ),
    )


def _bits(value: float) -> bytes:
    return struct.pack("<d", value)


@pytest.fixture(scope="module")
def solved() -> tuple[RevisionBinding, ExecutionPlan, PlanResult]:
    binding = _bind(shaped_revision())
    plan = _plan(binding)
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY)
    return binding, plan, run


def _reference() -> dict[str, float]:
    """P01's nominal state per stream coordinate and duty (`reference_values.yaml`)."""
    ref = yaml.safe_load(REFERENCE.read_text())
    (nominal,) = (v for v in ref["variants"] if v["case_id"] == "SYN-001-nominal")
    feed = ref["fresh_feed"]
    pressure = float(nominal["P_Pa"])
    flash, heater = float(nominal["T_flash_K"]), float(nominal["T_heater_K"])
    liquid = [
        float(a) + float(b)
        for a, b in zip(nominal["recycle_mol_per_s"], nominal["purge_mol_per_s"], strict=True)
    ]
    streams: dict[str, tuple[list[float], float]] = {
        "S1": ([float(x) for x in feed["F_mol_per_s"]], float(feed["T_K"])),
        "S2": ([float(x) for x in nominal["mixed_feed_mol_per_s"]], float(nominal["T_mix_K"])),
        "S3": ([float(x) for x in nominal["mixed_feed_mol_per_s"]], heater),
        "S4": ([float(x) for x in nominal["vapor_product_mol_per_s"]], flash),
        "S5": (liquid, flash),
        "S6": ([float(x) for x in nominal["recycle_mol_per_s"]], flash),
        "S7": ([float(x) for x in nominal["purge_mol_per_s"]], flash),
    }
    values: dict[str, float] = {}
    for stream, (flows, temperature) in streams.items():
        for component, flow in zip("ABC", flows, strict=True):
            values[f"{stream}.n.{component}"] = flow
        values[f"{stream}.T"] = temperature
        values[f"{stream}.P"] = pressure
    values["U-HEAT.Q"] = float(nominal["Q_heater_W"])
    values["U-FLASH.Q"] = float(nominal["Q_flash_W"])
    return values


# -- the start ---------------------------------------------------------------------------------


def test_initial_state_is_the_legacy_start_bitwise() -> None:
    """§2.2 against `Syn001TearProblem.reconstruct(initial_recycle())`, variable by variable."""
    binding = _bind(shaped_revision())
    start = initial_state(binding.flowsheet, binding.spec.variable_ids)
    assert not isinstance(start, InitialStateFailure), start
    legacy_flowsheet = _legacy()
    legacy = Syn001TearProblem(legacy_flowsheet).reconstruct(legacy_flowsheet.initial_recycle())
    assert list(start) == list(binding.spec.variable_ids)
    assert list(legacy) == list(start)
    differing = [
        f"{name}: {start[name]!r} vs {legacy[name]!r}"
        for name in start
        if _bits(start[name]) != _bits(legacy[name])
    ]
    assert differing == []
    # A real start, not zeros: the recycle is `G(0)`, the lifted split the kernel's.
    assert start["S6.n.A"] > 0.0 and start["S3.liq.A"] > 0.0


def test_initializer_id_is_registered() -> None:
    assert INITIALIZER_ID == "traversal-G0-v1"


class _Edited:
    """The bound flowsheet with each traversal's result passed through `edit(call, result)`: a
    test double for a unit or pass that breaks an invariant `initial_state` guards (review N3)."""

    def __init__(self, flowsheet: Any, edit: Any) -> None:
        self._flowsheet = flowsheet
        self._edit = edit
        self.calls = 0

    def traverse(self, guesses: Any) -> Any:
        result = self._flowsheet.traverse(guesses)
        self.calls += 1
        return self._edit(self.calls, result)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._flowsheet, name)


def test_a_second_traversal_that_tears_differently_is_a_defect() -> None:
    """Review N3's first guard (`orchestrator/revision.py`, §2.2): pass two must tear what pass
    one tore. The unedited double is the control."""
    binding = _bind(shaped_revision())
    columns = binding.spec.variable_ids
    control = _Edited(binding.flowsheet, lambda call, result: result)
    start = initial_state(control, columns)  # type: ignore[arg-type]
    assert not isinstance(start, InitialStateFailure) and control.calls == 2
    assert binding.flowsheet.traverse({}).torn == ("S6",)

    def retear(call: int, result: Any) -> Any:
        return replace(result, torn=("S5",)) if call == 2 else result

    with pytest.raises(
        ValueError, match=r"^the second traversal tore \['S5'\], the first \['S6'\]$"
    ):
        initial_state(_Edited(binding.flowsheet, retear), columns)  # type: ignore[arg-type]


@pytest.mark.parametrize("reported", ["both", "neither"])
def test_a_duty_column_needs_exactly_one_reported_duty(reported: str) -> None:
    """Review N3's second guard: a unit whose `<U>.Q` is a column reports exactly one of `duty`
    and `transferred_duty`. The heater's evaluation is edited to report both, or neither."""
    binding = _bind(shaped_revision())
    assert "U-HEAT.Q" in binding.spec.variable_ids

    def misreport(call: int, result: Any) -> Any:
        heater = result.evaluations["U-HEAT"]
        assert heater.duty is not None and heater.transferred_duty is None
        edited = (
            replace(heater, transferred_duty=heater.duty)
            if reported == "both"
            else replace(heater, duty=None)
        )
        return replace(result, evaluations={**result.evaluations, "U-HEAT": edited})

    with pytest.raises(ValueError, match=r"^U-HEAT reports duty=.*; U-HEAT\.Q needs exactly one$"):
        initial_state(
            _Edited(binding.flowsheet, misreport),  # type: ignore[arg-type]
            binding.spec.variable_ids,
        )


# -- the plan ----------------------------------------------------------------------------------


def test_plan_is_one_region_over_the_units_with_rows() -> None:
    binding = _bind(shaped_revision())
    plan = _plan(binding)
    (step,) = plan.steps
    assert step.kind == "solve_eo"
    assert step.units == REGION_UNITS
    assert step.region is not None and step.solve_plan is not None
    assert step.region.units == REGION_UNITS
    assert step.region.signature_units == ("U-HEAT", "U-FLASH")
    assert step.solve_plan.signature_units == ("U-HEAT", "U-FLASH")
    assert step.region.specification_rows == ()
    assert step.region.square

    documents = [json.loads(p.read_text()) for p in (REPO_ROOT / "schemas").glob("*.schema.json")]
    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document)) for document in documents
    )
    (schema,) = (d for d in documents if d["$id"] == SCHEMA_BASE + "execution-plan.schema.json")
    errors = list(Draft202012Validator(schema, registry=registry).iter_errors(plan.as_document()))
    assert errors == []


def test_the_region_resolves_the_registered_mass_mapping() -> None:
    """T04 §7.2 over the K02 heater's and flash's rows: every holdup row of the region is mapped."""
    binding = _bind(shaped_revision())
    (step,) = _plan(binding).steps
    assert step.region is not None
    flowsheet = binding.flowsheet
    resolved = resolve_mass(
        residence_time(flowsheet.wiring, flowsheet.components),
        spec=binding.spec,
        rows=step.region.row_ids,
        residence_time=POLICY.globalization.ptc.residence_time_s,
    )
    assert isinstance(resolved, RegionMass), resolved


def test_the_shaped_splits_are_syn001s_and_agree_with_the_rows() -> None:
    """§3.3 (a)–(e) on the SYN-001-shaped revision (`plan_revision` enforces them; asserted here
    directly), and the descriptors are SYN-001's hand-written two."""
    binding = _bind(shaped_revision())
    flowsheet = binding.flowsheet
    instances = instances_of(flowsheet)
    splits = lifted_splits(instances, flowsheet.components)
    assert splits == syn001_lifted_splits(flowsheet.components)
    model_version, constants = declaration_identity(binding.spec)
    declaration = trace_declaration(
        binding.spec,
        row_units=binding.row_units,
        model_version=model_version,
        constants_sha256=constants,
    )
    check_agreement(instances, splits, binding.spec, binding.row_units, declaration)


class _Lifter:
    """A K02 heater that reports a model id no split rule is registered for."""

    model_id = "test.lifter"

    def __init__(self, unit: Any) -> None:
        self._unit = unit

    def __getattr__(self, name: str) -> Any:
        return getattr(self._unit, name)


def test_an_unregistered_lifted_split_is_a_defect(monkeypatch: pytest.MonkeyPatch) -> None:
    """§3.3 (a) in `plan_revision`: equilibrium rows with no rule raise, before any region.

    Since the ruling round (note §1.3 R4, review S1) the binding refuses a lifted outlet from a
    model with no `outlet`-style rule, so the defect is reached as it would arise: a rule present
    when the flowsheet was bound and missing when it is planned."""
    heater = MODEL_BUILDERS["syn001.tp_heater"]

    def lifter(*arguments: Any) -> Any:
        unit, configuration = heater(*arguments)
        return _Lifter(unit), configuration

    monkeypatch.setitem(MODEL_BUILDERS, "test.lifter", lifter)  # type: ignore[arg-type]
    document = shaped_revision()
    (entry,) = (i for i in document["instances"] if i["id"] == "U-HEAT")
    entry["model"]["id"] = "test.lifter"
    assert bind_revision_flowsheet(document) == Unbound(
        "unsupported", "port_phase_unsupported(U-HEAT.outlet)"
    )
    with monkeypatch.context() as bound_with_a_rule:
        bound_with_a_rule.setitem(SPLIT_RULES, "test.lifter", SPLIT_RULES["syn001.tp_heater"])  # type: ignore[index]
        binding = _bind(document)
    with pytest.raises(ValueError, match=r"^lifted_split_unregistered\(test\.lifter\)$"):
        plan_revision(binding, POLICY)


# -- the solve ---------------------------------------------------------------------------------


def test_the_shaped_revision_converges_to_the_p01_nominal(
    solved: tuple[RevisionBinding, ExecutionPlan, PlanResult],
) -> None:
    binding, _, run = solved
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    reference = _reference()
    kinds = binding.spec.variable_kinds
    outside = [
        f"{name}: {run.state[name]!r} vs {value!r}"
        for name, value in reference.items()
        if abs(run.state[name] - value) > AGREEMENT[kinds[name]]
    ]
    assert outside == []


def test_the_root_is_on_the_registered_branch(
    solved: tuple[RevisionBinding, ExecutionPlan, PlanResult],
) -> None:
    _, _, run = solved
    (step,) = run.steps
    assert isinstance(step.detail, RegionResult)
    assert step.detail.root_fingerprint is not None
    found = [list(entry) for entry in step.detail.root_fingerprint["branch_found"]]
    assert found == [["U-HEAT", "LIQUID"], ["U-FLASH", "TWO_PHASE"]]
    assert step.detail.branch_provenance[0]["initializer_source"] == INITIALIZER_ID


# -- typed refusals ----------------------------------------------------------------------------


def test_a_converge_step_on_a_revision_flowsheet_is_refused() -> None:
    """T02's own plan for the revision has a loop; the tear path is SYN-001's (§2.3)."""
    binding = _bind(shaped_revision())
    spec = binding.spec
    model_version, constants = declaration_identity(spec)
    identity: dict[str, Any] = {
        "row_units": binding.row_units,
        "model_version": model_version,
        "constants_sha256": constants,
    }
    plan = build_execution_plan(
        spec=spec,
        declaration=trace_declaration(spec, **identity),
        graph=binding.graph,
        report=analyse(spec, binding.graph, **identity),
        manifests={u.unit_id: u.manifest() for u in binding.flowsheet.units()},
        policy=POLICY,
    )
    assert [step.kind for step in plan.steps] == ["evaluate", "converge"]
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=spec, policy=POLICY)
    assert run.outcome == "UNSUPPORTED_RANK_STRUCTURE"
    assert run.message == "tear_path_unsupported(revision_flowsheet)"
    assert run.steps[-1].kind == "converge"


def test_a_specification_region_on_a_revision_flowsheet_is_refused() -> None:
    """No cross-unit specification on a revision-built flowsheet in v0.1 (§2.3, §9)."""
    binding = _bind(shaped_revision())
    plan = _plan(binding)
    (step,) = plan.steps
    assert step.region is not None
    promoted = replace(step.region, specification_rows=(step.region.row_ids[0],))
    run = execute_plan(
        plan=replace(plan, steps=(replace(step, region=promoted),)),
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=POLICY,
    )
    assert run.outcome == "UNSUPPORTED_RANK_STRUCTURE"
    assert run.message == "specification_region_unsupported(revision_flowsheet)"
    assert not any(event.kind == "attempt_opened" for event in run.trace.events)


def test_the_syn001_only_entries_refuse_a_revision_flowsheet(tmp_path: Path) -> None:
    flowsheet = _bind(shaped_revision()).flowsheet
    with pytest.raises(TypeError, match=r"^syn001_only\(solve_tear\)$"):
        solve_tear(flowsheet)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^syn001_only\(run_session\)$"):
        run_session(flowsheet, tmp_path / "session")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^syn001_only\(run_session\)$"):
        solve_and_bundle(flowsheet, tmp_path / "bundle")  # type: ignore[arg-type]
    assert not (tmp_path / "session").exists() and not (tmp_path / "bundle").exists()


def test_an_initializer_failure_ends_the_solve_typed() -> None:
    """The feed at 400 K is above the equimolar bubble point (347.44 K): the K02 mixer refuses it
    as a liquid inlet (R-038), so the traversal cannot start the region."""
    document = shaped_revision()
    (entry,) = (s for s in document["specifications"] if s["id"] == "SPEC-feed-T")
    entry["value"] = 400.0
    binding = _bind(document)
    run = execute_plan(
        plan=_plan(binding), flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY
    )
    assert run.outcome == "INITIALIZATION_FAILED"
    assert run.message.startswith("initializer_failed(U-MIX): ")
    rejected = [event for event in run.trace.events if event.kind == "initializer_rejected"]
    assert [event.message for event in rejected] == [run.message]
    # Before any attempt: no attempt opened, no Jacobian evaluated.
    assert [event.kind for event in run.trace.events] == [
        "plan_built",
        "region_opened",
        "initializer_rejected",
        "region_closed",
        "solve_closed",
    ]
