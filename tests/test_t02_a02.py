"""T02 §7: the cross-unit specification [A02] inside SYN-001 — plan, DOF validation, and solve.

The heater outlet temperature `S3.T` is freed (a `role: free` specification carries its guess) and
the flash duty `U-FLASH.Q` is specified instead. The heater's `HEAT-T` row is removed, the
revision's duty specification is promoted to a row attributed to the flash, and the heater, every
unit between it and the flash, and the loop they sit in become one EO region (A25). Expectations
are Fable's closed forms (`benchmarks/t02/reference_values.yaml`, `syn001.a02_sweep` and
`syn001.branch_roots`), never this code's own output.

The two liquid-guess cases are registered expected failures handed to T03 (spec §7.6, F2): every
fact on their path is a closed form, and they are the appearance rule's injected failures.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from openflowsheet.application.binding import Binding, bind_revision
from openflowsheet.application.validation import validate
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.report import StructuralReport
from openflowsheet.graph.trace import Declaration, trace_declaration
from openflowsheet.orchestrator.execution import (
    ExecutionPlan,
    PlanRefusal,
    Region,
    UnsupportedRankStructureError,
    build_execution_plan,
    declaration_identity,
    plan_or_refusal,
    specification_regions,
)
from openflowsheet.orchestrator.region import RegionResult, solve_region, syn001_lifted_splits
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify.failure import refusal_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES = REPO_ROOT / "benchmarks" / "syn001" / "cases"
POLICY = SolvePolicy(policy_id="T02", residual_tolerances={}, scales={})
# §6.4: ten times each kind's residual tolerance.
FLOW, TEMPERATURE, DUTY = 3.1e-7, 1e-5, 1e-2
REGION_UNITS = ("U-MIX", "U-HEAT", "U-FLASH", "U-SPLIT")
CERTIFIED = ("U-FLASH:FLASH-P:inlet", "U-SPLIT:SPLIT-P:recycle")
COMPONENTS = ("A", "B", "C")


@pytest.fixture(scope="module")
def ref() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t02" / "reference_values.yaml").read_text()
    )
    return loaded


def revision(case_id: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((CASES / f"{case_id}.yaml").read_text())
    return loaded


@dataclass(frozen=True)
class Structure:
    binding: Binding
    declaration: Declaration
    report: StructuralReport


def structure(document: Mapping[str, Any]) -> Structure:
    binding = bind_revision(document)
    assert isinstance(binding, Binding), binding
    model_version, constants = declaration_identity(binding.spec)
    identity = {
        "row_units": binding.row_units,
        "specification_ids": binding.specification_ids,
        "model_version": model_version,
        "constants_sha256": constants,
    }
    return Structure(
        binding,
        trace_declaration(binding.spec, **identity),
        analyse(binding.spec, binding.graph, **identity),
    )


def the_region(item: Structure) -> Region:
    (region,) = specification_regions(
        item.declaration,
        item.binding.graph,
        item.report,
        freed=item.binding.freed,
        promoted=item.binding.promoted,
        missing_guesses=item.binding.missing_guesses,
    )
    return region


def plan_for(item: Structure, specifications: tuple[Region, ...] | None = None) -> ExecutionPlan:
    flowsheet = item.binding.flowsheet
    return build_execution_plan(
        spec=item.binding.spec,
        declaration=item.declaration,
        graph=item.binding.graph,
        report=item.report,
        manifests={unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=POLICY,
        specifications=(the_region(item),) if specifications is None else specifications,
    )


def solve(case_id: str) -> RegionResult:
    """§7.5: the sequential pre-solve with `S3.T` pinned at the guess, then the region."""
    item = structure(revision(case_id))
    flowsheet = item.binding.flowsheet
    pre, _ = solve_tear(flowsheet)
    assert pre.final_state is not None
    return solve_region(
        compiled=compile_problem(item.binding.spec),
        spec=item.binding.spec,
        region=the_region(item),
        state=dict(pre.final_state),
        splits=syn001_lifted_splits(flowsheet.components),
        provider=flowsheet.provider,
        policy=POLICY,
        initializer_source="user_guess",
    )


def refuse_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    import openflowsheet.compile.casadi_backend as backend

    def refuse(*arguments: object, **keywords: object) -> Any:
        raise AssertionError("a structural step evaluated something")

    monkeypatch.setattr(backend, "compile_problem", refuse)
    monkeypatch.setattr(Syn001Provider, "flash", refuse)
    monkeypatch.setattr(Syn001Provider, "evaluate_phase", refuse)


# --------------------------------------------------------------------------- A25: plan shape

SPECIFIED = ("SYN-001-A02-360", "SYN-001-A02-365", "SYN-001-A02-355")


@pytest.mark.parametrize("case_id", SPECIFIED)
def test_a25_the_a02_plan_equals_the_registered_plan(
    case_id: str, ref: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The heater, every intervening unit and the specification equation in one region; no
    `converge` step anywhere, so no nested loop; built without evaluating anything."""
    item = structure(revision(case_id))
    assert item.report.finding == "STRUCTURALLY_CLOSED"
    refuse_evaluation(monkeypatch)
    plan = plan_for(item)

    registered = ref["syn001"]["plans"]["SYN-001-A02-*"]
    assert [step.kind for step in plan.steps] == [step["kind"] for step in registered]
    evaluate, solve_eo = plan.steps
    assert evaluate.units == (registered[0]["unit"],)
    region = solve_eo.region
    assert region is not None and solve_eo.solve_plan is not None
    expected = registered[1]
    assert list(solve_eo.units) == expected["region_units"] == list(REGION_UNITS)
    assert list(region.specification_rows) == expected["specification_rows"]
    assert region.adjusted_variables == (expected["adjusted_variable"],)
    assert region.target_variables == (expected["target_variable"],)
    assert region.removed_specification_rows == (expected["removed_specification_row"],)
    assert list(region.signature_units) == expected["signature_units"]
    assert len(region.row_ids) == len(region.variable_ids) == expected["square"]

    solve_plan = solve_eo.solve_plan
    assert list(solve_plan.tear_variable_ids) == []
    eliminated = {row.row_id for row in solve_plan.eliminated_rows}
    assert eliminated == set(ref["syn001"]["certified_rows"])
    assert list(solve_plan.signature_units) == expected["signature_units"]


def test_a25_the_region_rows_and_columns_are_the_registered_sets(ref: dict[str, Any]) -> None:
    """`ref.syn001.a02_region`: every row of the four units (HEAT-T removed, the promoted duty row
    added) minus the two certificates; every free column minus S1's five."""
    item = structure(revision("SYN-001-A02-360"))
    region = the_region(item)
    registered = ref["syn001"]["a02_region"]
    assert region.units == tuple(registered["units"])
    assert region.fixed_upstream == tuple(registered["fixed_upstream"])

    rows = {
        row for row in item.declaration.row_ids if item.declaration.rows[row].unit in REGION_UNITS
    }
    assert "U-HEAT:HEAT-T" not in rows
    assert "SPEC:SPEC-flash-duty" in rows
    assert len(rows) == 44
    assert set(region.row_ids) == rows - set(CERTIFIED)
    assert set(region.eliminated_rows) == set(CERTIFIED)

    free = set(item.declaration.column_ids)
    assert len(free) == 47
    assert set(region.variable_ids) == free - set(registered["fixed_upstream"])
    assert "S3.T" in region.variable_ids and "U-FLASH.Q" in region.variable_ids


def test_a25_the_revision_is_ready_for_simulation() -> None:
    report = validate(revision("SYN-001-A02-360"))
    assert report.status == "READY_FOR_SIMULATION"
    assert report.structural_counts is not None


# --------------------------------------------------------------------------- A26: DOF


def over_specified() -> dict[str, Any]:
    """The A02 revision with the heater's temperature specification *retained*."""
    document = revision("SYN-001-A02-360")
    heater_t = next(
        entry
        for entry in revision("SYN-001-nominal")["specifications"]
        if entry["id"] == "SPEC-heater-outlet-T"
    )
    document["specifications"] = [
        entry for entry in document["specifications"] if entry["id"] != "GUESS-heater-outlet-T"
    ] + [copy.deepcopy(heater_t)]
    return document


def under_specified() -> dict[str, Any]:
    """The A02 revision with `HEAT-T` removed and no promotion row: nothing pins the flash duty."""
    document = revision("SYN-001-A02-360")
    document["specifications"] = [
        entry for entry in document["specifications"] if entry["id"] != "SPEC-flash-duty"
    ]
    return document


def test_a26_heat_t_retained_is_over_specification_and_no_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measured localization: T01's over-specified-unit list names `U-FLASH` (the unit the
    promoted duty row is attributed to) and the candidate specifications name the heater's
    `SPEC-heater-outlet-T`. The spec's A26 reads "naming U-HEAT"; the heater is named through its
    specification, not through the unit list — recorded for the review in `docs/T02_STATE.md`."""
    document = over_specified()
    item = structure(document)
    refuse_evaluation(monkeypatch)
    report = validate(document)
    assert report.status == "INVALID"
    check = next(check for check in report.checks if check.id == "STR-03")
    assert check.result == "FAIL"
    assert "STRUCTURAL_OVER_SPECIFICATION" in check.message
    assert {"SPEC-heater-outlet-T", "SPEC-flash-duty"} <= set(item.report.candidate_specifications)
    assert item.report.finding == "STRUCTURAL_OVER_SPECIFICATION"
    with pytest.raises(ValueError, match="structurally closed"):
        plan_for(item, specifications=())


def test_a26_nothing_pinning_the_duty_is_under_specification_and_a_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`S3.T` among `C⁻`. The status is `DRAFT`, not T01 §12.3's `INVALID`: a revision one
    specification short is incomplete (R-022, blueprint §4.3); the check itself stays `FAIL`."""
    document = under_specified()
    item = structure(document)
    refuse_evaluation(monkeypatch)
    report = validate(document)
    assert report.status == "DRAFT"
    check = next(check for check in report.checks if check.id == "STR-02")
    assert check.result == "FAIL"
    assert "STRUCTURAL_UNDER_SPECIFICATION" in check.message
    assert "S3.T" in check.implicated_objects
    assert item.report.finding == "STRUCTURAL_UNDER_SPECIFICATION"
    assert not [c for c in report.checks if c.result == "FAIL" and c.id != "STR-02"]
    with pytest.raises(ValueError, match="structurally closed"):
        plan_for(item, specifications=())


def test_a26_a_closed_but_non_square_region_is_refused_at_plan_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A synthetic region one row short: `UNSUPPORTED_RANK_STRUCTURE`, and nothing evaluated."""
    item = structure(revision("SYN-001-A02-360"))
    region = the_region(item)
    short = replace(region, row_ids=region.row_ids[:-1])
    assert not short.square
    refuse_evaluation(monkeypatch)
    with pytest.raises(UnsupportedRankStructureError, match="UNSUPPORTED_RANK_STRUCTURE"):
        plan_for(item, specifications=(short,))


def test_a26_more_than_one_freed_variable_is_a_typed_refusal() -> None:
    item = structure(revision("SYN-001-A02-360"))
    with pytest.raises(UnsupportedRankStructureError):
        specification_regions(
            item.declaration,
            item.binding.graph,
            item.report,
            freed={**item.binding.freed, "U-FLASH:FLASH-T": "S4.T"},
            promoted=item.binding.promoted,
            missing_guesses=(),
        )


# --------------------------------------------------------------------------- A28–A29: solves


@pytest.mark.parametrize(
    ("case_id", "row", "iterations"),
    [
        ("SYN-001-A02-360", "T_heater=360K", 6),
        ("SYN-001-A02-365", "T_heater=365K", 6),
        ("SYN-001-A02-355", "T_heater=355K", 6),
    ],
)
def test_a28_a29_the_specified_duty_is_met_at_the_registered_heater_temperature(
    case_id: str, row: str, iterations: int, ref: dict[str, Any]
) -> None:
    """One attempt, both lifted units two-phase. A wrong branch moves `Q_heater` by ≥ 1e4 W."""
    sweep = ref["syn001"]["a02_sweep"][row]
    result = solve(case_id)
    assert result.outcome == "CONVERGED"
    assert len(result.attempts) == 1
    assert result.iterations <= iterations
    state = result.state
    assert abs(state["S3.T"] - float(row.split("=")[1].rstrip("K"))) <= TEMPERATURE
    assert abs(state["U-HEAT.Q"] - float(sweep["Q_heater_W"])) <= DUTY
    assert abs(state["U-FLASH.Q"] - float(sweep["Q_flash_W"])) <= DUTY
    for index, component in enumerate(COMPONENTS):
        vapor, liquid = sweep["S3_vapor_mol_per_s"][index], sweep["S3_liquid_mol_per_s"][index]
        assert abs(state[f"S3.vap.{component}"] - float(vapor)) <= FLOW
        assert abs(state[f"S3.liq.{component}"] - float(liquid)) <= FLOW
        t_star = float(ref["syn001"]["t_star_nominal_mol_per_s"][index])
        assert abs(state[f"S6.n.{component}"] - t_star) <= FLOW


# --------------------------------------------------------------------------- A30–A31: failures


# T02 A30 and A31 (the liquid-guess cases ending ACTIVE_SET_CYCLING) are superseded by T03
# A06–A09, which re-register them as CONVERGED under ADR 0005's contract (T03 §10.1); their
# tests are `tests/test_t03_phase.py`.


# --------------------------------------------------------------------------- A27: CAP-1


def cap1_manifests(item: Structure) -> dict[str, Any]:
    """The test double: the SYN-001 heater with its `residuals` derivative declared unavailable."""
    manifests: dict[str, Any] = {
        unit.unit_id: unit.manifest() for unit in item.binding.flowsheet.units()
    }
    heater = dict(manifests["U-HEAT"])
    heater["derivatives"] = [
        {**entry, "method": "unavailable"} if entry["output"] == "residuals" else entry
        for entry in heater["derivatives"]
    ]
    manifests["U-HEAT"] = heater
    return manifests


def test_a27_cap_1_the_plan_is_refused_and_no_loop_is_built_in_its_place(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = structure(revision("SYN-001-A02-360"))
    region = the_region(item)
    refuse_evaluation(monkeypatch)
    outcome = plan_or_refusal(
        spec=item.binding.spec,
        declaration=item.declaration,
        graph=item.binding.graph,
        report=item.report,
        manifests=cap1_manifests(item),
        policy=POLICY,
        specifications=(region,),
        specification_ids=item.binding.specification_ids,
    )
    assert isinstance(outcome, PlanRefusal), "no plan, so no `converge` step anywhere"
    assert outcome.outcome == "CAPABILITY_UNAVAILABLE"
    message = str(outcome.error)
    for named in ("U-HEAT", "'unavailable'", *REGION_UNITS, "SPEC-flash-duty"):
        assert named in message, named
    assert outcome.specifications == ("SPEC-flash-duty",)

    (closing,) = outcome.trace.events
    assert closing.kind == "solve_closed" and closing.outcome == "CAPABILITY_UNAVAILABLE"
    assert not outcome.trace.of_kind("plan_built")
    assert not outcome.trace.of_kind("attempt_opened")
    counters = closing.counters
    assert counters.residual_calls == counters.jacobian_calls == counters.property_calls == 0

    bundle = refusal_bundle(outcome)
    document = bundle.as_document()
    assert document["taxonomy"] == "model domain/conservation/derivative defects"
    actions = [entry["action"] for entry in document["suggested_actions"]]
    assert actions == ["provide_derivatives"]
    assert "report_defect" not in actions
    assert document["implicated_sources"][0] == "U-HEAT"
    assert "SPEC-flash-duty" in document["implicated_sources"]
    assert document["attempt_tree"] == []
    assert all(value == 0 for value in document["observations"]["counters"].values())
    assert not list(failure_bundle_validator().iter_errors(document))


def test_a27_the_capable_manifests_build_the_plan_through_the_same_entry() -> None:
    item = structure(revision("SYN-001-A02-360"))
    outcome = plan_or_refusal(
        spec=item.binding.spec,
        declaration=item.declaration,
        graph=item.binding.graph,
        report=item.report,
        manifests={unit.unit_id: unit.manifest() for unit in item.binding.flowsheet.units()},
        policy=POLICY,
        specifications=(the_region(item),),
    )
    assert isinstance(outcome, ExecutionPlan)
    assert [step.kind for step in outcome.steps] == ["evaluate", "solve_eo"]


def test_d6_every_other_outcome_keeps_its_class_action() -> None:
    """ADR 0009 D6 adds one value for one outcome; `EVALUATION_ERROR`, in the same class, is
    still `report_defect`."""
    from openflowsheet.verify.failure import ACTIONS, OUTCOME_ACTIONS, TAXONOMY

    # ADR 0005 D6 (T03) adds the second override: an incompatible opening state is a defect.
    assert OUTCOME_ACTIONS == {
        "CAPABILITY_UNAVAILABLE": "provide_derivatives",
        "CHECKPOINT_INCOMPATIBLE": "report_defect",
    }
    assert ACTIONS[TAXONOMY["EVALUATION_ERROR"]] == "report_defect"


def failure_bundle_validator() -> Any:
    import json

    from jsonschema import Draft202012Validator

    schema = json.loads((REPO_ROOT / "schemas" / "failure-bundle.schema.json").read_text())
    return Draft202012Validator(schema)
