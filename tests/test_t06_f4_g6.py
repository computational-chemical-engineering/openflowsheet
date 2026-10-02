"""T06 F4 WO7, gate G6: the restart initializer is sound on the registered corpus.

Design note `docs/design/T06-F4-recovery.md` §8 G6, §9 Q4: every registered cyclic revision case
is `CONVERGED` from `traversal-G0-pass8-v1`, and its state is within T02 §6.4's allowances of its
registered twin root. The start replaces `traversal-G0-v1` on the ordinary region path (§6.2's
projection, the band-route records, the contract), under both registered contracts. A failure
here is a stop-and-report to the design lane: `RESTART_PASSES` is never tuned against it.

The cyclic cases are those whose traversal tears a stream, among every registered revision case:
T05's C2 and C3 (C3X's traversal refuses at pass 2; C1 is acyclic), T06's STA-02, NET-02, NET-03,
NET-06, NET-09, NET-10 and NET-11. T05b's cases and REF-01…REF-07 tear nothing — asserted below,
so a newly registered cyclic case cannot be missed.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import t05b_support as t05b
import yaml
from t06_support import (
    ALLOWANCE,
    CORPUS,
    T05_COUPLED,
    T06_CASES,
    case_document,
    registered_root,
    worst_ratio,
)
from test_t05_coupled import POLICY as POLICY_W13
from test_t05_w11_cases import case_document as t05_case

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.trace import SolvePolicy

T05_CYCLIC = ("SYN-001-UL-C2", "SYN-001-UL-C3")
T06_CYCLIC = tuple(
    f"SYN-001-T06-{name}"
    for name in (
        "STA02",
        "STA03-degC",
        "STA03-kgs",
        "STA04",
        "NET02",
        "NET03",
        "NET06",
        "NET09",
        "NET10",
        "NET11",
    )
)
POLICIES = {"T05b-v2": t05b.POLICY_V2, "T05-W13": POLICY_W13}


def _registered_revisions() -> dict[str, Callable[[], dict[str, Any]]]:
    """Every registered revision case: T05's four, T05b's, and every T06 case file."""
    out: dict[str, Callable[[], dict[str, Any]]] = {}
    for case in ("SYN-001-UL-C1", *T05_CYCLIC, "SYN-001-UL-C3X"):
        out[case] = lambda case=case: t05_case(case)
    for table in (
        t05b.SINGLE_COMPONENT_CASES,
        t05b.DORMANT_CASES,
        t05b.DORMANT_NON_LIFTED_CASES,
    ):
        out.update(table)
    for name in t05b.NEAR_PURE_CASES:
        out[name] = lambda name=name: t05b.near_pure(name)
    out["NP-GC"] = t05b.np_gc
    for path in sorted(Path(T06_CASES).glob("*.yaml")):
        out[path.stem] = lambda path=path: yaml.safe_load(path.read_text("utf-8"))
    return out


def test_g6_the_cyclic_registered_cases_are_the_listed_ones() -> None:
    torn: list[str] = []
    for case, build in _registered_revisions().items():
        binding = bind_revision_flowsheet(build())
        if isinstance(binding, RevisionBinding) and binding.flowsheet.traverse({}).torn:
            torn.append(case)
    assert sorted(torn) == sorted((*T05_CYCLIC, "SYN-001-UL-C3X", *T06_CYCLIC))


def _document(case: str) -> dict[str, Any]:
    return t05_case(case) if case in T05_CYCLIC else case_document(case)


#: Metamorphic restatements (T06 spec Amendment 1): STA-03's two unit-converted revisions are
#: SYN-001-nominal, STA-04 (components `[C, A, B]`) is C2. Their expected roots are their twins':
#: P01's 20-digit SYN-001 oracle (stream coordinates) and T05's registered C2 root.
SYN001_TWINS = ("SYN-001-T06-STA03-degC", "SYN-001-T06-STA03-kgs")
C2_TWINS = ("SYN-001-T06-STA04",)


def _syn001_nominal_root() -> dict[str, tuple[Decimal, float]]:
    from test_t05_w1c_executor import _reference

    return {
        column: (Decimal(repr(value)), ALLOWANCE["n" if ".n." in column else column[-1]])
        for column, value in _reference().items()
        if column.startswith("S")
    }


def _expected(case: str) -> dict[str, tuple[Decimal, float]]:
    if case in SYN001_TWINS:
        return _syn001_nominal_root()
    if case in C2_TWINS:
        return registered_root(T05_COUPLED["SYN-001-UL-C2"])
    return registered_root(T05_COUPLED[case] if case in T05_CYCLIC else CORPUS[case])


@pytest.mark.parametrize("label", sorted(POLICIES))
@pytest.mark.parametrize("case", [*T05_CYCLIC, *T06_CYCLIC])
def test_g6_the_restart_start_converges_to_the_registered_root(
    case: str, label: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy: SolvePolicy = POLICIES[label]
    binding = bind_revision_flowsheet(_document(case))
    assert isinstance(binding, RevisionBinding)
    start = revision.restart_start(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(start, revision.RestartStart), start
    # Every case keeps all eight passes; C3 since ADR 0017 removed F6's refusal of its pass 4 in
    # `U-MIX` (T06 spec A77).
    assert (start.passes_used, start.rejected) == (revision.RESTART_PASSES, ())
    monkeypatch.setattr(
        revision,
        "traversal_start",
        lambda *_: revision.TraversalStart(start.values, start.band_routes),
    )
    plan, _ = revision.plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan)
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    assert run.outcome == "CONVERGED", (run.outcome, run.message)
    assert run.state is not None
    ratio, column = worst_ratio(run.state, _expected(case))
    assert ratio <= 1.0, (ratio, column)
