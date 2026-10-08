"""Sweeps of one pinned input: independent certified solves whose failed points are results.

M03 spec §6; ADR 0031 D5. A sweep is a study over one declared parameter and an ordered list of
values, on SYN-001's tear path:

1. Each point is an independent solve of the flowsheet with that pinned input replaced, from the
   case's registered initializer (`start = "registered_initializer"`). No point's start depends on
   another's, so the result does not depend on the order of the list (A23).
2. Each point is certified (K04 `verify`) and, when the sweep asks for one, given a sensitivity
   (`studies/syn001.syn001_sensitivity`, under `M03-sensitivity-v1`).
3. **A failed point is a result**: a specification the units refuse, a solve that does not
   converge, or a certificate that is not `VERIFIED` is recorded with its typed outcome and the
   first line of its message, and its outputs are `None`. A sweep never drops, interpolates or
   repeats a point, and stops early only on its budget, which makes it `INCOMPLETE` with every
   unrun point recorded `NOT_RUN`.
4. A sweep claims, per point, what that point's records claim, and nothing between points — no
   continuity, monotonicity or branch connectivity. Each point carries its root fingerprint
   (`orchestrator/roots.py`), so a branch change is visible rather than inferred.

Nothing here is timed or counted across points, so a point's record is a function of the flowsheet,
the parameter value and the request only, and a reordered sweep reproduces it bit for bit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.studies.sensitivity import (
    Mode,
    OutputFunctional,
    SensitivityResult,
    StudyParameter,
)
from openflowsheet.studies.syn001 import (
    output_values,
    pinned_value,
    solve_certified,
    syn001_sensitivity,
    with_pinned,
)

#: Spec §6 item 1: the only start a sweep point takes. A chaining mode would be a new value.
START: Final = "registered_initializer"
NOT_RUN: Final = "NOT_RUN"

SweepStatus = Literal["COMPLETE", "INCOMPLETE"]


@dataclass(frozen=True)
class SweepSensitivity:
    """The sensitivity a sweep requests at every converged, verified point."""

    parameters: tuple[StudyParameter, ...]
    outputs: tuple[OutputFunctional, ...]
    mode: Mode = "forward"


@dataclass(frozen=True)
class SweepPoint:
    """One point's record (spec §6). Every field but `value` and `outcome` is `None` where the
    point did not get that far; a failed point's `outputs` and `sensitivity` are always `None`."""

    value: float
    #: `CONVERGED` (solved and certified `VERIFIED`), a K03 solve outcome,
    #: `SPECIFICATION_REFUSED`, `CERTIFICATE_NOT_VERIFIED`, or `NOT_RUN`.
    outcome: str
    message: str
    solve_outcome: str | None
    certificate_status: str | None
    state_sha256: str | None
    constants_sha256: str | None
    root_fingerprint: Mapping[str, Any] | None
    outputs: Mapping[str, float] | None
    sensitivity: SensitivityResult | None

    def as_document(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "outcome": self.outcome,
            "message": self.message,
            "solve_outcome": self.solve_outcome,
            "certificate_status": self.certificate_status,
            "state_sha256": self.state_sha256,
            "constants_sha256": self.constants_sha256,
            "root_fingerprint": (
                dict(self.root_fingerprint) if self.root_fingerprint is not None else None
            ),
            "outputs": dict(self.outputs) if self.outputs is not None else None,
            "sensitivity": self.sensitivity.as_document() if self.sensitivity else None,
        }


@dataclass(frozen=True)
class SweepResult:
    """Spec §6's `sweep_result`: the points in input order, the counts and the status."""

    parameter_id: str
    values: tuple[float, ...]
    start: str
    outputs: tuple[OutputFunctional, ...]
    sensitivity: SweepSensitivity | None
    points: tuple[SweepPoint, ...]
    status: SweepStatus

    @property
    def summary(self) -> dict[str, int]:
        """`{total, converged, verified, sensitivity_qualified, failed, not_run}`. `converged`
        counts solves that converged (a certificate that then failed still converged); `failed`
        counts every run point whose outcome is not `CONVERGED`."""
        return {
            "total": len(self.points),
            "converged": sum(point.solve_outcome == "CONVERGED" for point in self.points),
            "verified": sum(point.certificate_status == "VERIFIED" for point in self.points),
            "sensitivity_qualified": sum(
                point.sensitivity is not None and point.sensitivity.status == "QUALIFIED"
                for point in self.points
            ),
            "failed": sum(point.outcome not in ("CONVERGED", NOT_RUN) for point in self.points),
            "not_run": sum(point.outcome == NOT_RUN for point in self.points),
        }

    def as_document(self) -> dict[str, Any]:
        return {
            "parameter_id": self.parameter_id,
            "values": list(self.values),
            "start": self.start,
            "outputs": [
                {
                    "output_id": output.output_id,
                    "coefficients": dict(output.coefficients),
                    "scale": output.scale,
                }
                for output in self.outputs
            ],
            "sensitivity_request": (
                {
                    "parameters": [
                        parameter.parameter_id for parameter in self.sensitivity.parameters
                    ],
                    "outputs": [output.output_id for output in self.sensitivity.outputs],
                    "mode": self.sensitivity.mode,
                }
                if self.sensitivity is not None
                else None
            ),
            "points": [point.as_document() for point in self.points],
            "summary": self.summary,
            "status": self.status,
        }


def run_sweep(
    flowsheet: Syn001Flowsheet,
    parameter_id: str,
    values: Sequence[float],
    outputs: Sequence[OutputFunctional],
    *,
    sensitivity: SweepSensitivity | None = None,
    max_points: int | None = None,
) -> SweepResult:
    """Sweep `parameter_id` over `values` (spec §6), in the order given.

    `max_points` is the sweep's budget: once that many points have run, the rest are recorded
    `NOT_RUN` and the sweep is `INCOMPLETE`. The request itself is checked before any point runs —
    an id that is not a pinned input SYN-001 can move alone is an ill-formed sweep, not a failed
    point — and raises.
    """
    pinned_value(flowsheet, parameter_id)  # KeyError for an unknown id
    if not values:
        raise ValueError("a sweep needs at least one value")
    if max_points is not None and max_points < 0:
        raise ValueError("max_points must be >= 0")
    resolved = tuple(float(value) for value in values)
    for value in resolved:
        with_pinned(flowsheet, {parameter_id: value})  # ValueError for an immovable input
    points: list[SweepPoint] = []
    for index, value in enumerate(resolved):
        if max_points is not None and index >= max_points:
            points.append(_not_run(value))
            continue
        points.append(_point(flowsheet, parameter_id, value, tuple(outputs), sensitivity))
    status: SweepStatus = (
        "INCOMPLETE" if any(point.outcome == NOT_RUN for point in points) else "COMPLETE"
    )
    return SweepResult(
        parameter_id=parameter_id,
        values=resolved,
        start=START,
        outputs=tuple(outputs),
        sensitivity=sensitivity,
        points=tuple(points),
        status=status,
    )


def _point(
    flowsheet: Syn001Flowsheet,
    parameter_id: str,
    value: float,
    outputs: tuple[OutputFunctional, ...],
    request: SweepSensitivity | None,
) -> SweepPoint:
    sheet = with_pinned(flowsheet, {parameter_id: value})
    solve = solve_certified(sheet)
    result, certificate = solve.result, solve.certificate
    common: dict[str, Any] = {
        "value": value,
        "outcome": solve.outcome,
        "message": solve.message,
        "solve_outcome": result.outcome if result is not None else None,
        "certificate_status": certificate.verification_status if certificate else None,
        "state_sha256": certificate.target_state_sha256 if certificate else None,
        "constants_sha256": certificate.constants_sha256 if certificate else None,
        "root_fingerprint": result.root_fingerprint if result is not None else None,
    }
    state = solve.final_state
    if not solve.verified or state is None:
        return SweepPoint(**common, outputs=None, sensitivity=None)
    values = output_values(state, outputs)
    sensitivity = None
    if request is not None:
        sensitivity = syn001_sensitivity(
            sheet,
            result,
            parameters=request.parameters,
            outputs=request.outputs,
            mode=request.mode,
            certificate=certificate,
        )
    return SweepPoint(
        **common,
        outputs={output.output_id: number for output, number in zip(outputs, values, strict=True)},
        sensitivity=sensitivity,
    )


def _not_run(value: float) -> SweepPoint:
    return SweepPoint(
        value=value,
        outcome=NOT_RUN,
        message="not run: the sweep's point budget was spent",
        solve_outcome=None,
        certificate_status=None,
        state_sha256=None,
        constants_sha256=None,
        root_fingerprint=None,
        outputs=None,
        sensitivity=None,
    )
