"""K04 amendment WIT (§4.8.2-§4.8.3): what the certificate's witness did, observed from outside.

`spy(monkeypatch)` wraps `checks.derivative_witness` (which `_issue` imports at call time) and
`certificate.witness_classes` (which `verify_revision` calls), and records each call: the classes,
the sets and components the witness received, its result, and each escalated column's
`Escalation`. Nothing here changes what the certificate computes; the certificate itself records
no escalation (§4.8.3 (g)).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

import openflowsheet.verify.certificate as certificate_module
import openflowsheet.verify.checks as checks_module
from openflowsheet.compile.reference import state_vector
from openflowsheet.verify import CheckResult
from openflowsheet.verify.checks import _FORWARD_OFFSETS, Escalation


@dataclass
class Witnessed:
    """One witness run inside a certificate."""

    target: Any
    state: dict[str, float]
    unstenciled: frozenset[str]
    one_sided: frozenset[str]
    components: tuple[str, ...]
    checks: list[CheckResult]
    escalations: dict[str, Escalation] = field(default_factory=dict)
    classes: dict[str, int] | None = None
    basis: str | None = None

    def check(self, which: str) -> CheckResult:
        (found,) = (c for c in self.checks if c.id == f"derivative_witness.{which}")
        return found

    def of_class(self, k: int) -> set[str]:
        assert self.classes is not None
        return {name for name, c in self.classes.items() if c == k}

    def scaled_jacobian(self) -> dict[tuple[str, str], float]:
        """The AD Jacobian at the state, scaled as §4.8 compares it (row id, column id)."""
        base = np.array(state_vector(self.target.spec, self.state))
        jacobian = self.target.compiled.jacobian(base, self.target.context)
        scaling = self.target.scaling
        out: dict[tuple[str, str], float] = {}
        for j, column in enumerate(jacobian.col_ids):
            for offset in range(jacobian.indptr[j], jacobian.indptr[j + 1]):
                row = jacobian.row_ids[int(jacobian.indices[offset])]
                out[(row, column)] = (
                    float(jacobian.data[offset]) * scaling.column[column] / scaling.row[row]
                )
        return out

    def row_ids(self) -> tuple[str, ...]:
        base = np.array(state_vector(self.target.spec, self.state))
        return tuple(self.target.compiled.jacobian(base, self.target.context).row_ids)

    def escalated_discrepancy(self, column: str) -> float:
        """max over every row of |J-hat - D-hat_k*| (an off-pattern entry is 0) for a resolved
        column."""
        escalation = self.escalations[column]
        assert escalation.scaled is not None, column
        jacobian = self.scaled_jacobian()
        return max(
            abs(jacobian.get((row, column), 0.0) - value)
            for row, value in zip(self.row_ids(), escalation.scaled, strict=True)
        )

    def forward(self, column: str) -> dict[str, float]:
        """R-831's forward five-point difference of `column` at the registered step, scaled."""
        target = self.target
        base = np.array(state_vector(target.spec, self.state))
        j = list(target.spec.variable_ids).index(column)
        step = checks_module.FD_RELATIVE_STEP * target.scaling.column[column]
        points = []
        for shift in _FORWARD_OFFSETS:
            point = base.copy()
            if shift:
                point[j] += shift * step
            value = target.compiled.residual(point, target.context)
            assert value.status == "ok", (column, shift, value.status)
            points.append(value.values)
        out = {}
        for i, row in enumerate(self.row_ids()):
            difference = (
                -25.0 * points[0][i]
                + 48.0 * points[1][i]
                - 36.0 * points[2][i]
                + 16.0 * points[3][i]
                - 3.0 * points[4][i]
            ) / (12.0 * step)
            out[row] = difference * target.scaling.column[column] / target.scaling.row[row]
        return out


def spy(monkeypatch: pytest.MonkeyPatch) -> list[Witnessed]:
    """Record every witness run (and the revision path's classes) while the test runs."""
    runs: list[Witnessed] = []
    pending: list[tuple[str, dict[str, int]]] = []
    witness = checks_module.derivative_witness
    classify = certificate_module.witness_classes

    def classes(
        columns: Sequence[str],
        state: Mapping[str, float],
        components: Sequence[str],
        **kwargs: Any,
    ) -> dict[str, int]:
        found = classify(columns, state, components, **kwargs)
        pending.append((kwargs["basis"], found))
        return found

    def witnessed(tear: Any, state: Mapping[str, float], **kwargs: Any) -> list[CheckResult]:
        escalations: dict[str, Escalation] = {}
        result = witness(tear, state, escalations=escalations, **kwargs)
        basis, found = pending.pop() if pending else (None, None)
        runs.append(
            Witnessed(
                target=tear,
                state=dict(state),
                unstenciled=kwargs.get("unstenciled", frozenset()),
                one_sided=kwargs.get("one_sided", frozenset()),
                components=tuple(kwargs.get("components", ())),
                checks=result,
                escalations=escalations,
                classes=found,
                basis=basis,
            )
        )
        return result

    monkeypatch.setattr(checks_module, "derivative_witness", witnessed)
    monkeypatch.setattr(certificate_module, "witness_classes", classes)
    return runs
