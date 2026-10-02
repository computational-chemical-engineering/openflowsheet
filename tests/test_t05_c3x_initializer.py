"""T05 C3X through the general path: a refused second traversal is a typed initializer failure.

Regression for W1.c's `initial_state`, which compared the two passes' torn streams before asking
whether the second pass had been refused. A refused pass stops at the refusing unit, so it has torn
only a prefix of the first pass's streams; C3X's second pass stops at U-HX after tearing S7, and
the comparison raised `ValueError` where design note §2.4 requires A20's first branch.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import InitialStateFailure, initial_state, plan_revision
from openflowsheet.orchestrator.trace import SolvePolicy

CASES = Path(__file__).resolve().parent.parent / "benchmarks" / "t05" / "cases"
POLICY = SolvePolicy(policy_id="T05-C3X", residual_tolerances={}, scales={})


def _binding(case: str) -> RevisionBinding:
    binding = bind_revision_flowsheet(yaml.safe_load((CASES / f"{case}.yaml").read_text()))
    assert isinstance(binding, RevisionBinding)
    return binding


def test_c3x_initial_state_is_the_exchangers_typed_refusal() -> None:
    binding = _binding("SYN-001-UL-C3X")
    failure = initial_state(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(failure, InitialStateFailure)
    assert (failure.unit, failure.code) == ("U-HX", "temperature_cross(cold_end)")


def test_c3x_solve_ends_initialization_failed_at_u_hx() -> None:
    binding = _binding("SYN-001-UL-C3X")
    plan, _ = plan_revision(binding, POLICY)
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY)
    assert [(step.outcome, step.message) for step in run.steps] == [
        ("INITIALIZATION_FAILED", "initializer_failed(U-HX): temperature_cross(cold_end)")
    ]
