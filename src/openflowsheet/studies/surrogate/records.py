"""The study's record vocabulary: the surrogate's model id, one request's observation, a gradient
centre's evidence, and the evaluation of a completed plan (M04 spec §7, §8.1).

A leaf below `study` and `manifest`: the study produces these records and the manifest writes
them, so both import them here. `studies.surrogate.study` re-exports every name.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

from openflowsheet.studies.surrogate.conformal import StudyVerdict
from openflowsheet.studies.surrogate.plan import (
    PLAN_N_TUBES,
    SamplePlan,
    Scaling,
    Split,
    coordinates,
    scaled,
)
from openflowsheet.studies.surrogate.quadratic import QuadraticFit
from openflowsheet.thermo import StreamState

#: The surrogate unit's model id (spec §8.1).
MODEL_ID: Final = "c1.reactor_surrogate"

ObservationStatus = Literal["ok", "failed", "incomplete"]
CentreStatus = Literal["ok", "parent_failed", "incomplete", "not_evaluated"]


@dataclass(frozen=True)
class Observation:
    """What the study reads from one experiment of the plan.

    `ok`: a deterministic `ok` result, with X = ξ/n_N2,in and ΔT = T_out − T_in (M02's coupling
    coordinates, ADR 0034 D1). `failed`: a deterministic result that is not `ok` (refused, not
    converged, not accepted) — scored +∞, never fitted. `incomplete`: no deterministic result.
    `status`/`code` are the reactor envelope's; `fingerprint_sha256` the result's environment.
    """

    label: str
    key: str
    request: StreamState
    status: ObservationStatus
    envelope_status: str
    code: str
    x: float | None
    dt: float | None
    extrapolated: bool
    fingerprint_sha256: str | None

    def z(self, scaling: Scaling) -> tuple[float, ...]:
        """The request's scaled inlet under `scaling` (the plan's box, spec §19 A2.3)."""
        u = coordinates(self.request, PLAN_N_TUBES)
        assert u is not None  # every plan request has a defined input map (the plan guard)
        return scaled(u, scaling)


@dataclass(frozen=True)
class CentreEvidence:
    """One gradient centre (spec §7.2): its stencil observations and, when every stencil
    experiment is `ok` and a predictor exists, the errors e_X and e_ΔT."""

    index: int
    status: CentreStatus
    stencil: tuple[Observation, ...]
    errors: tuple[float, float] | None


@dataclass(frozen=True)
class SurrogateEvaluation:
    """Everything the records hold about a completed plan, and the verdict (spec §7)."""

    plan: SamplePlan
    observations: Mapping[Split, tuple[Observation, ...]]
    fit: QuadraticFit
    calibration_scores: tuple[float | None, ...]
    test_scores: tuple[float | None, ...]
    #: |e_X| and |e_ΔT| of the `ok` test draws, in plan order (reported, not judged; spec §7.1).
    test_errors: tuple[tuple[float, float], ...]
    inadmissible: int
    #: The smallest distance of a calibration or test prediction to a bound of A(s), over w_o;
    #: `None` without a predictor (spec §18 A1.3: the gap of the admissibility decisions).
    admissibility_margin: float | None
    extrapolated: int
    centres: tuple[CentreEvidence, ...]
    verdict: StudyVerdict
