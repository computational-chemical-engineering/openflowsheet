"""M04's test-only synthetic parents (spec §9.1, WO-4): in-process variants with exactly known maps.

Never shipped and never registered: each variant is built from a document by
`variants.variant_from_document` (`synthetic: true`, the stand-in's `boundary` block verbatim), and
it is evaluated by `SyntheticBackend`, which a test hands to `ExperimentRunner(backend_for=...)`.
Nothing reachable from a request resolves one (M02's rule for test variants).

Per tube, with z the scaled seven coordinates of the tube's own (T, P, y, F) (spec §3.1),

    X = 0.16 · exp(A · a·z),  ΔT = 80 K · exp(A · b·z),

the tube returns the raw outlet n_raw = n_tube + ν X n_N2,tube and T_out = T + ΔT, and
`NotAccepted("synthetic_failure_region")` iff z_T + z_F > 1.6. `m04-synthetic-smooth-v1` has
A = 1 and `m04-synthetic-rough-v1` A = 4. The box, a, b and the threshold are the specification's
literals, restated here rather than imported from `studies.surrogate`: the parent is the exactly
known answer the study is checked against, so it shares no code with the study.

`transient` (M04.A21): requests, by their exact (n, T, P) at N_tubes = 1, for which every attempt
returns `ExecutionFailure("crashed")` — a transient failure the runner retries (`max_retries` 1)
and never caches. A backend with a non-empty `transient` set has its own variant id and
fingerprint, so its records can never be mistaken for the plain parent's.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Mapping
from pathlib import Path
from typing import Any, Final

import openflowsheet
from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.backends import (
    Backend,
    Environment,
    Execution,
    ExecutionKind,
    InProcessBackend,
    tube_document,
)
from openflowsheet.adapters.external.launcher import LaunchProgress
from openflowsheet.canonical import document_sha256, file_sha256
from openflowsheet.models.c1 import boundary as boundary_module
from openflowsheet.models.c1.boundary import (
    ExecutionFailure,
    NotAccepted,
    TubeInlet,
    TubeOutlet,
    tube_inlet,
)
from openflowsheet.thermo import StreamState

__all__ = [
    "AMPLITUDE",
    "ROUGH_ID",
    "SMOOTH_ID",
    "STAGE",
    "SyntheticBackend",
    "backend_for",
    "synthetic_truth",
    "synthetic_variant",
]

SMOOTH_ID: Final = "m04-synthetic-smooth-v1"
ROUGH_ID: Final = "m04-synthetic-rough-v1"
#: M04.A21's parent: the smooth map with one request failing transiently on every attempt.
TRANSIENT_ID: Final = "m04-synthetic-smooth-transient-v1"
AMPLITUDE: Final[Mapping[str, float]] = {SMOOTH_ID: 1.0, ROUGH_ID: 4.0, TRANSIENT_ID: 1.0}
#: Spec §9.1.
A_X: Final = (-0.06, 0.04, 0.03, -0.05, -0.01, -0.015, -0.08)
B_DT: Final = (-0.10, 0.03, 0.02, -0.04, -0.01, -0.01, -0.04)
X0: Final = 0.16
DT0_K: Final = 80.0
FAILURE_THRESHOLD: Final = 1.6
STAGE: Final = "synthetic_failure_region"
#: Spec §3.1's box, (lo, hi) per coordinate as decimal literals: T, P, H2/N2, y_NH3, y_Ar, y_CH4, F.
BOX: Final = (
    (653.15, 693.15),
    (9.0e6, 1.0e7),
    (2.5, 3.0),
    (0.02, 0.04),
    (0.01, 0.03),
    (0.01, 0.04),
    (0.0057, 0.0086),
)
#: ν of N2 + 3 H2 -> 2 NH3 in COMPONENTS order (H2, N2, NH3, Ar, CH4).
NU: Final = (-3.0, -1.0, 2.0, 0.0, 0.0)
MODULE: Final = "tests/support/m04_synthetic_parents.py"


def _scaled(u: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(
        (value - (lo + hi) * 0.5) / ((hi - lo) * 0.5)
        for value, (lo, hi) in zip(u, BOX, strict=True)
    )


def tube_z(tube: TubeInlet) -> tuple[float, ...]:
    """z of a tube's own inlet: (T, P, y_H2/y_N2, y_NH3, y_Ar, y_CH4, F), scaled (spec §3.1)."""
    y = tube.composition
    return _scaled(
        (tube.temperature, tube.outlet_pressure, y[0] / y[1], y[2], y[3], y[4], tube.flow)
    )


def synthetic_truth(z: tuple[float, ...], amplitude: float) -> tuple[float, float] | None:
    """(X, ΔT) at z, or `None` in the failure region z_T + z_F > 1.6 (spec §9.1)."""
    if z[0] + z[6] > FAILURE_THRESHOLD:
        return None
    eta_x = math.fsum(a * x for a, x in zip(A_X, z, strict=True))
    eta_t = math.fsum(b * x for b, x in zip(B_DT, z, strict=True))
    return X0 * math.exp(amplitude * eta_x), DT0_K * math.exp(amplitude * eta_t)


def synthetic_variant(variant_id: str) -> variants.Variant:
    """The test-only variant `variant_id` (one of `AMPLITUDE`): the stand-in's document with its
    own id, `model_id` `c1.reactor` (as M02's test-only variants), and one retry."""
    if variant_id not in AMPLITUDE:
        raise ValueError(f"{variant_id!r} is not an M04 synthetic parent")
    standin = variants.registered_variant("standin-x025-v1").document
    document = {
        **standin,
        "model_id": "c1.reactor",
        "variant_id": variant_id,
        "synthetic": True,
        "evaluation": {"kind": "in_process", "module": MODULE, "conversion_N2": X0},
        "execution": {"timeout_s": None, "max_retries": 1, "kill_grace_s": None},
    }
    return variants.variant_from_document(document)


def _tube_key(tube: TubeInlet) -> tuple[float, ...]:
    return (tube.flow, *tube.composition, tube.temperature, tube.outlet_pressure)


class SyntheticBackend:
    """`Backend` for one synthetic variant, in the worker."""

    kind: ExecutionKind = "in_process"

    def __init__(self, variant: variants.Variant, transient: Collection[StreamState] = ()) -> None:
        if variant.variant_id not in AMPLITUDE:
            raise ValueError(f"{variant.variant_id!r} is not an M04 synthetic parent")
        if bool(transient) != (variant.variant_id == TRANSIENT_ID):
            raise ValueError("transient failures belong to the transient parent only")
        self.variant = variant
        self.amplitude = AMPLITUDE[variant.variant_id]
        # Keyed exactly on the tube inlet each request becomes at N_tubes = 1 (the boundary's map).
        self._transient = frozenset(_tube_key(tube_inlet(state, 1.0)) for state in transient)

    def _configuration(self) -> dict[str, Any]:
        return {
            "amplitude": self.amplitude,
            "a": list(A_X),
            "b": list(B_DT),
            "x0": X0,
            "dt0_K": DT0_K,
            "failure_threshold": FAILURE_THRESHOLD,
            "transient": sorted(list(key) for key in self._transient),
        }

    def environment(self, directory: Path) -> Environment:
        assert boundary_module.__file__ is not None
        fingerprint = {
            "kind": "in_process",
            "boundary_sha256": file_sha256(Path(boundary_module.__file__)),
            "module": MODULE,
            "module_sha256": file_sha256(Path(__file__)),
            "configuration": self._configuration(),
            "openflowsheet_version": openflowsheet.__version__,
        }
        return Environment(fingerprint, document_sha256(fingerprint))

    def identity(self, n_tubes: float) -> Mapping[str, Any]:
        return {
            "model_id": self.variant.model_id,
            "synthetic": True,
            "reactor_commit": None,
            "pymrm_version": None,
            "overlay_sha256": None,
            "configuration_sha256": document_sha256({**self._configuration(), "n_tubes": n_tubes}),
            "profile": None,
        }

    def evaluate(
        self,
        tube: TubeInlet,
        directory: Path,
        progress: LaunchProgress,
        check: Callable[[], None] | None,
    ) -> Execution:
        if _tube_key(tube) in self._transient:
            message = "synthetic transient failure (M04.A21)"
            return Execution(
                kind="in_process",
                status="crashed",
                answer=ExecutionFailure("crashed", message),
                message=message,
            )
        truth = synthetic_truth(tube_z(tube), self.amplitude)
        if truth is None:
            return Execution(
                kind="in_process", status="completed", answer=NotAccepted(STAGE), stage=STAGE
            )
        x, dt = truth
        flows = tuple(tube.flow * y for y in tube.composition)
        reacted = x * flows[1]
        outlet = TubeOutlet(
            flows=tuple(value + nu * reacted for value, nu in zip(flows, NU, strict=True)),
            temperature=tube.temperature + dt,
            pressure_drop=0.0,
        )
        return Execution(
            kind="in_process", status="completed", answer=outlet, tube_outlet=tube_document(outlet)
        )


def backend_for(
    transient: Collection[StreamState] = (),
) -> Callable[[variants.Variant], Backend]:
    """`ExperimentRunner(backend_for=...)`: the synthetic parents by id, the stand-in in process."""

    def make(variant: variants.Variant) -> Backend:
        if variant.variant_id in AMPLITUDE:
            return SyntheticBackend(
                variant, transient if variant.variant_id == TRANSIENT_ID else ()
            )
        return InProcessBackend(variant)

    return make
