"""T05 W12: lifted-split discovery on the coupled cases (A26's descriptor half) and PTC's refusal of
a region with a T05 holdup row (A27).

Spec `docs/derivations/T05-unit-models-spec.md` §12.3, §12.4 and §15 A26, A27; design note
`docs/design/T05-generalization.md` §3.1 (the descriptor fields by style) and §5 (PTC mass
mapping). A26's other half — the root fingerprints' `branch_found` — needs the converged coupled
solves and is W13's.

A27: `residence_time` over a revision flowsheet's wiring carries only T04's registered rules (the
K02 heater and flash); T05 registers none, so ADR 0010 D4's V1 refuses the first `holdup_balance`
row of a T05 model in region row order — before any attempt, and with no residual or Jacobian
call. The calls are counted as T04's A14 test counts them (`SpiedCompiled`), on the region solve
directly and on `execute_plan` end to end.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

import pytest
from t05_w12_support import bind, planned_step
from test_t04_ptc_region import SpiedCompiled, eo_policy
from test_t05_w11_cases import case_document

import openflowsheet.orchestrator.executor as executor_module
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.mass import residence_time
from openflowsheet.orchestrator.region import LiftedSplit, solve_region
from openflowsheet.orchestrator.revision import (
    InitialStateFailure,
    initial_state,
    instances_of,
    plan_revision,
)
from openflowsheet.orchestrator.splits import lifted_splits
from openflowsheet.orchestrator.trace import Trace

SOLVABLE = ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3")


def _abc(prefix: str) -> tuple[str, str, str]:
    return (f"{prefix}.A", f"{prefix}.B", f"{prefix}.C")


def _outlet_style(unit: str, stream: str, equation: str) -> LiftedSplit:
    """§3.1's `outlet` column: the unit's lifted outlet `S`."""
    return LiftedSplit(
        unit=unit,
        stream=stream,
        feed=_abc(f"{stream}.n"),
        temperature=f"{stream}.T",
        pressure=f"{stream}.P",
        vapor=_abc(f"{stream}.vap"),
        liquid=_abc(f"{stream}.liq"),
        vapor_total=f"{stream}.V",
        liquid_total=f"{stream}.L",
        equilibrium_rows=tuple(f"{unit}:{equation}:{c}" for c in "ABC"),
        vapor_definition=f"{unit}:Vdef",
        liquid_definition=f"{unit}:Ldef",
    )


def _products_style(unit: str, inlet: str, vapor: str, liquid: str) -> LiftedSplit:
    """§3.1's `products` column: inlet `I`, vapour product `V`, liquid product `L`."""
    return LiftedSplit(
        unit=unit,
        stream=inlet,
        feed=_abc(f"{inlet}.n"),
        temperature=f"{vapor}.T",
        pressure=f"{vapor}.P",
        vapor=_abc(f"{vapor}.n"),
        liquid=_abc(f"{liquid}.n"),
        vapor_total=f"{vapor}.N",
        liquid_total=f"{liquid}.N",
        equilibrium_rows=tuple(f"{unit}:PHF-equilibrium:{c}" for c in "ABC"),
        vapor_definition=f"{unit}:Ndef:vapor",
        liquid_definition=f"{unit}:Ndef:liquid",
    )


#: §3.1 applied to each case's wiring (design note §2.4), in declaration order. C1's K02 heater
#: is on the list: the registry covers it, and its descriptor is SYN-001's shape on `S3`.
DESCRIPTORS: dict[str, tuple[LiftedSplit, ...]] = {
    "SYN-001-UL-C1": (
        _outlet_style("U-HEAT", "S3", "HEAT-equilibrium"),
        _outlet_style("U-VLV", "S4", "VLV-equilibrium"),
        _products_style("U-PHF", "S4", "S5", "S6"),
    ),
    "SYN-001-UL-C2": (_outlet_style("U-RX", "S3", "RX-equilibrium"),),
    "SYN-001-UL-C3": (_products_style("U-PHF", "S3", "S4", "S5"),),
}


@pytest.mark.parametrize("case", SOLVABLE)
def test_the_descriptors_are_the_designs_field_by_field(case: str) -> None:
    binding = bind(case_document(case))
    flowsheet = binding.flowsheet
    found = lifted_splits(instances_of(flowsheet), flowsheet.components)
    expected = DESCRIPTORS[case]
    assert [split.unit for split in found] == [split.unit for split in expected]
    for got, want in zip(found, expected, strict=True):
        for field in fields(LiftedSplit):
            assert getattr(got, field.name) == getattr(want, field.name), (
                f"{case} {got.unit}.{field.name}"
            )
    assert found == expected


# -- A27: PTC refuses a region with an unmapped T05 holdup row --------------------------------

#: Design note §5's expectation, and the row each solve is measured to name (the same).
FIRST_UNMAPPED_ROW = {
    "SYN-001-UL-C1": "U-PHF:PHF-mole:A",
    "SYN-001-UL-C2": "U-RX:RX-mole:A",
    "SYN-001-UL-C3": "U-HX:HX-mole-hot:A",
}


@pytest.mark.parametrize("case", SOLVABLE)
def test_ptc_over_a_t05_region_is_refused_before_any_call(case: str) -> None:
    """The region solve itself, as T04's A14: `PTC_MAPPING_INVALID`, the R0 message naming the
    row, no attempt, no event, no residual or Jacobian call."""
    policy = eo_policy("ptc")
    binding = bind(case_document(case))
    flowsheet, spec = binding.flowsheet, binding.spec
    step = planned_step(binding, policy)
    assert step.region is not None
    start = initial_state(flowsheet, spec.variable_ids)
    assert not isinstance(start, InitialStateFailure), start
    trace = Trace()
    spied = SpiedCompiled(compile_problem(spec), trace)
    result = solve_region(
        compiled=spied,
        spec=spec,
        region=step.region,
        state=start,
        splits=lifted_splits(instances_of(flowsheet), flowsheet.components),
        provider=flowsheet.provider,
        policy=policy,
        trace=trace,
        initializer_source="traversal-G0-v1",
        mass_mapping=residence_time(flowsheet.wiring, flowsheet.components),
    )
    row = FIRST_UNMAPPED_ROW[case]
    assert row in step.region.row_ids
    assert (result.outcome, result.message) == (
        "PTC_MAPPING_INVALID",
        f"ptc_mapping_invalid({row}, missing)",
    )
    assert result.attempts == () and result.branch_provenance == ()
    assert len(trace) == 0 and spied.calls == []


@pytest.mark.parametrize("case", SOLVABLE)
def test_ptc_through_the_plan_ends_with_the_same_refusal(
    case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end: `plan_revision` then `execute_plan` under a PTC policy. The traversal's start
    makes no compiled call (design note §5), and the step's compiled problem — the executor's own,
    spied — is never evaluated."""
    policy = eo_policy("ptc")
    binding = bind(case_document(case))
    spies: list[Any] = []

    def spied_compile(spec: Any) -> Any:
        spies.append(SpiedCompiled(compile_problem(spec)))
        return spies[-1]

    monkeypatch.setattr(executor_module, "compile_problem", spied_compile)
    plan, _ = plan_revision(binding, policy)
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    row = FIRST_UNMAPPED_ROW[case]
    assert [(step.outcome, step.message) for step in run.steps] == [
        ("PTC_MAPPING_INVALID", f"ptc_mapping_invalid({row}, missing)")
    ]
    assert spies, "the executor compiled no problem for the step"
    assert [call for spy in spies for call in spy.calls] == []
