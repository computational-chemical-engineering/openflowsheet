"""Test support for M02 WO-8: C1 flowsheets around the PR units, solved through the revision path
(design note §8, §14.2). Not collected.

`flash_revision` is the flash in its smallest flowsheet: a feed fully specified at `(n, T_feed, P)`
into `c1.tp_flash` at `(T, P)`, its products into two sinks. `solve` binds, plans and executes a
revision under `T06-revision-v2` (`T05b-phase-contract-v2`, which M01 §7's PR units use), and
`recording` captures every full state the compiled residual is evaluated at — every Newton iterate
and every line-search trial of every attempt.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from unittest import mock

import numpy as np
from m02_c1_support import connection, feed_specifications, instance, revision, specification

from openflowsheet.application.policies import APPLICATION_POLICIES
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.compile.casadi_backend import CasadiCompiledProblem
from openflowsheet.graph.report import StructuralReport
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import SolvePolicy

#: The revision path's registered policy (`revision_eo`'s default): phase contract v2.
POLICY: SolvePolicy = APPLICATION_POLICIES["T06-revision-v2"]
P = 1.0e7
LIGHT = ("H2", "N2", "Ar", "CH4")


def flash_revision(
    n: Sequence[float],
    temperature: float,
    pressure: float = P,
    *,
    feed_temperature: float | None = None,
) -> dict[str, Any]:
    """F → U (`c1.tp_flash` at `(T, P)`) → K (vapour, S2), L (liquid, S3); the feed S1 at
    `(n, T_feed, P)`, `T_feed` the flash's `T` unless given."""
    feed_t = temperature if feed_temperature is None else feed_temperature
    return revision(
        [
            instance("F", "c1.feed_source"),
            instance("U", "c1.tp_flash"),
            instance("K", "c1.product_sink"),
            instance("L", "c1.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("U", "inlet")),
            connection("S2", ("U", "vapor"), ("K", "inlet")),
            connection("S3", ("U", "liquid"), ("L", "inlet"), "liquid"),
        ],
        [
            *feed_specifications("S1", n, feed_t, pressure),
            specification("SPEC-S2-T", "connection", "S2", "state.T", temperature, "temperature"),
            specification("SPEC-S2-P", "connection", "S2", "state.P", pressure, "pressure"),
            specification("SPEC-S3-T", "connection", "S3", "state.T", temperature, "temperature"),
            specification("SPEC-S3-P", "connection", "S3", "state.P", pressure, "pressure"),
        ],
    )


@dataclass(frozen=True)
class Solved:
    binding: RevisionBinding
    plan: ExecutionPlan
    report: StructuralReport
    run: PlanResult


def bind(document: Mapping[str, Any]) -> RevisionBinding:
    bound = bind_revision_flowsheet(document)
    assert isinstance(bound, RevisionBinding), bound
    return bound


def solve(document: Mapping[str, Any], policy: SolvePolicy = POLICY) -> Solved:
    binding = bind(document)
    plan, report = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    return Solved(binding, plan, report, run)


@contextmanager
def recording() -> Iterator[list[dict[str, float]]]:
    """Every full state a compiled residual is evaluated at, by variable id, in call order."""
    states: list[dict[str, float]] = []
    original = CasadiCompiledProblem.residual

    def residual(self: CasadiCompiledProblem, x: Any, context: Any) -> Any:
        ids = self._spec.variable_ids  # noqa: SLF001 - the test's window on the evaluated state
        states.append(dict(zip(ids, np.asarray(x, dtype=np.float64).tolist(), strict=True)))
        return original(self, x, context)

    with mock.patch.object(CasadiCompiledProblem, "residual", residual):
        yield states


def light_liquid_columns(liquid: str = "S3") -> tuple[str, ...]:
    return tuple(f"{liquid}.n.{c}" for c in LIGHT)


def is_positive_zero(value: float) -> bool:
    """Bitwise `+0.0`: zero, and its sign bit clear."""
    return value == 0.0 and np.copysign(1.0, value) == 1.0
