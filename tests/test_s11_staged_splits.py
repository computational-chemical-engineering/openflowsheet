"""S11 WO-B3a: staged splits in a flowsheet region (design note §10.2–§10.3, R-822, R-823).

S11.A87 (inert on registered revisions), A88 (placement of the column's stage splits), A89 (the
agreement defects) and A90 (the `signature_units` guard). The column is registered for the test
only (`s11_column_support.column_registered`), as I1 has not registered it yet.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import replace
from typing import Any

import pytest
from s11_column_support import column_registered, column_revision
from test_s02_column_wo1 import SPECS
from test_s06_column_wo1 import J_CASES
from test_s11_column_face import view_of
from test_t05_w11_cases import case_document

from openflowsheet.application import column_binding, revision_binding
from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.models.syn001.cascade_solve import S01_DEFAULT_V1
from openflowsheet.models.syn001.column_solve import stage_unit
from openflowsheet.models.syn001.column_unit import (
    ColumnStructure,
    column_staged_splits,
    column_structure,
)
from openflowsheet.orchestrator import execution
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.region import StagedSplits
from openflowsheet.orchestrator.revision import instances_of, plan_revision
from openflowsheet.orchestrator.splits import (
    closure_types,
    lifted_splits,
    region_splits,
    split_temperatures,
    vapour_only_forms,
    zero_flow_forms,
)

M1 = SPECS["M1"]


def _bind(document: dict[str, Any]) -> RevisionBinding:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    return binding


@pytest.fixture
def registered(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    with column_registered(monkeypatch):
        yield monkeypatch


def _staged_by(
    monkeypatch: pytest.MonkeyPatch, edit: Callable[[StagedSplits], StagedSplits]
) -> None:
    """The builder's `column_staged_splits`, edited: a defective staged unit for one test."""

    def edited(structure: ColumnStructure) -> StagedSplits:
        return edit(column_staged_splits(structure))

    monkeypatch.setattr(column_binding, "column_staged_splits", edited)


# -- S11.A87 --------------------------------------------------------------------------------------


def _m02_flash() -> dict[str, Any]:
    from m02_wo8_support import flash_revision

    return flash_revision((0.6, 0.2, 0.165, 0.015, 0.02), 268.15)


@pytest.mark.parametrize(
    "document", [_m02_flash, lambda: case_document("SYN-001-UL-C1")], ids=["M02-F1", "T05-C1"]
)
def test_region_splits_is_the_registry_without_a_staged_unit(
    document: Callable[[], dict[str, Any]],
) -> None:
    """S11.A87: no staged unit — every field is the registry function's output, same key order."""
    flowsheet = _bind(document()).flowsheet
    instances, units, components = instances_of(flowsheet), flowsheet.units(), flowsheet.components
    rs = region_splits(instances, units, components)
    registry = lifted_splits(instances, components)
    types = closure_types(units)
    assert registry, "the revision has lifted splits"
    assert rs.splits == registry
    assert rs.owners == {} and rs.staged == {}
    expected: dict[str, Mapping[str, Any]] = {
        "closure_types": types,
        "zero_flow_forms": zero_flow_forms(instances, registry, types, components),
        "split_temperatures": split_temperatures(instances, registry),
        "vapour_only_forms": vapour_only_forms(instances, registry, components),
    }
    for name, value in expected.items():
        found = getattr(rs, name)
        assert list(found.items()) == list(value.items()), name


# -- S11.A88 --------------------------------------------------------------------------------------


def test_the_column_stage_splits_are_placed_in_the_region(
    registered: pytest.MonkeyPatch,
) -> None:
    """S11.A88: stage keys in `signature_units` and the attempt signature, never in `units`."""
    binding = _bind(column_revision(M1))
    plan, _ = plan_revision(binding, S01_DEFAULT_V1)
    assert isinstance(plan, ExecutionPlan), plan
    (step,) = plan.steps
    assert step.kind == "solve_eo" and step.region is not None
    keys = tuple(stage_unit("UCOL", j) for j in M1.equilibrium_stages())
    assert not set(keys) & set(step.units)
    assert "UCOL" in step.units and "UCOL" in step.region.units
    assert step.region.signature_units == keys
    run = execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=S01_DEFAULT_V1
    )
    assert run.outcome == "CONVERGED", run.message
    (result,) = run.steps
    first = result.detail.attempts[0]
    lifted = tuple(key for key, _ in first.signature)
    assert len(lifted) == len(M1.equilibrium_stages())
    assert lifted == keys


# -- S11.A89 --------------------------------------------------------------------------------------


def test_a_staged_unit_missing_one_stage_is_refused(registered: pytest.MonkeyPatch) -> None:
    """S11.A89 (1): the omitted stage's equilibrium rows are unclaimed."""

    def without_stage_3(given: StagedSplits) -> StagedSplits:
        dropped = stage_unit("UCOL", 3)
        return replace(
            given,
            splits=tuple(s for s in given.splits if s.unit != dropped),
            closure_types={k: v for k, v in given.closure_types.items() if k != dropped},
            zero_flow_forms={k: v for k, v in given.zero_flow_forms.items() if k != dropped},
            split_temperatures={k: v for k, v in given.split_temperatures.items() if k != dropped},
        )

    _staged_by(registered, without_stage_3)
    binding = _bind(column_revision(M1))
    with pytest.raises(ValueError, match=r"staged_split_rows_disagree\(UCOL\).*UCOL:stage:3:eq"):
        plan_revision(binding, S01_DEFAULT_V1)


@pytest.mark.parametrize("name", ["J2", "J8"])
def test_a_recovery_definition_row_must_be_claimed(
    name: str, registered: pytest.MonkeyPatch
) -> None:
    """S11.A89 (2): a recovery end whose definition row is not in `other_squared_rows`."""
    _staged_by(registered, lambda given: replace(given, other_squared_rows=()))
    binding = _bind(column_revision(J_CASES[name]))
    with pytest.raises(
        ValueError, match=r"staged_split_rows_disagree\(UCOL\).*spec:recovery_definition"
    ):
        plan_revision(binding, S01_DEFAULT_V1)


def test_a_staged_key_equal_to_an_instance_id_is_refused(registered: pytest.MonkeyPatch) -> None:
    """S11.A89 (3): a staged key that names another instance. The revision reader refuses a
    dotted instance id (`id_unsupported`), so no document can name one of the column's
    `stage_unit` keys; the checks are exercised with a staged unit whose key is `U-BOT`: the
    binder's guard (§10.2 step 9, R-838's A91), then the planner's (a'') behind it."""

    def keyed_u_bot(given: StagedSplits) -> StagedSplits:
        old = stage_unit("UCOL", 3)

        def key(name: str) -> str:
            return "U-BOT" if name == old else name

        return replace(
            given,
            splits=tuple(replace(s, unit=key(s.unit)) for s in given.splits),
            closure_types={key(k): v for k, v in given.closure_types.items()},
            zero_flow_forms={key(k): v for k, v in given.zero_flow_forms.items()},
            split_temperatures={key(k): v for k, v in given.split_temperatures.items()},
        )

    _staged_by(registered, keyed_u_bot)
    # The binder's own guard (§10.2 step 9, registered at I1): the key names an instance.
    refused = bind_revision_flowsheet(column_revision(M1))
    assert isinstance(refused, Unbound), refused
    assert (refused.kind, refused.detail) == ("unsupported", "id_unsupported(U-BOT)")
    assert refused.hint == (
        "Instance id `U-BOT` is a lifted-split key of instance `UCOL`; rename the instance."
    )
    # And the planner's check (a'') behind it, with the binder's guard bypassed.
    registered.setattr(revision_binding, "split_owners", lambda staged: {})
    binding = _bind(column_revision(M1))
    with pytest.raises(ValueError, match=r"lifted_split_key_collision\(U-BOT\)"):
        plan_revision(binding, S01_DEFAULT_V1)


def test_an_instance_in_both_registries_is_refused() -> None:
    """S11.A89 (4): a registry instance supplied as a staged unit too."""
    flowsheet = _bind(case_document("SYN-001-UL-C1")).flowsheet
    instances, components = instances_of(flowsheet), flowsheet.components
    (heater,) = (split for split in lifted_splits(instances, components) if split.unit == "U-HEAT")
    staged = StagedSplits(
        splits=(heater,),
        closure_types={"U-HEAT": "TP"},
        zero_flow_forms=zero_flow_forms(instances, (heater,), {}, components),
        split_temperatures={"U-HEAT": (heater.temperature,)},
    )
    with pytest.raises(ValueError, match=r"staged_unit_has_rule\(U-HEAT\)"):
        lifted_splits(instances, components, staged={"U-HEAT": staged})


def test_staged_splits_holds_its_own_invariants() -> None:
    """`StagedSplits.__post_init__`: non-empty, distinct keys, every map keyed by the splits."""
    given = column_staged_splits(column_structure(view_of(M1), M1.components))
    with pytest.raises(ValueError, match="staged_splits_empty"):
        replace(given, splits=())
    with pytest.raises(ValueError, match="staged_split_keys_repeated"):
        replace(given, splits=(given.splits[0], given.splits[0]))
    with pytest.raises(ValueError, match=r"staged_split_map_disagrees\(closure_types\)"):
        replace(given, closure_types={})


# -- S11.A90 --------------------------------------------------------------------------------------


def test_the_guard_refuses_a_region_without_its_stage_keys(registered: pytest.MonkeyPatch) -> None:
    """S11.A90: `build_region` without `staged_units` lists `UCOL`, not its stages."""
    build = execution.build_region

    def unstaged(*args: Any, staged_units: Any = None, **kwargs: Any) -> Any:
        return build(*args, **kwargs)

    registered.setattr("openflowsheet.orchestrator.revision.build_region", unstaged)
    binding = _bind(column_revision(M1))
    with pytest.raises(ValueError, match=r"signature_units_disagree: plan \['UCOL'\]"):
        plan_revision(binding, S01_DEFAULT_V1)
