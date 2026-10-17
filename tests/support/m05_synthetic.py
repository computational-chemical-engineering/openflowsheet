"""M05's test-only smooth reactor `m05-synthetic-interior-v1`, TR-E2's truth (M05 design note §5.2;
ADR 0039 D2; R-266).

Never shipped and never registered: the variant is built from a document by
`variants.variant_from_document` (`synthetic: true`, the stand-in's `boundary` block verbatim),
and is evaluated by `InteriorBackend`, which a test hands to `ExperimentRunner(backend_for=...)`,
so every evaluation is an M02 experiment with its key and records. It is shaped like M04's
synthetic parents (M04 spec §9.1). Per tube, with z the scaled seven coordinates of the tube's own
(T, P, r, y_NH₃, y_Ar, y_CH₄, F) in M04 spec §3.1's box,

    X = 0.16 · exp(a·z − z_T²),  ΔT = 80 K · exp(b·z),
    a = (0.05, 0.04, 0.03, −0.05, −0.01, −0.015, −0.08),
    b = (−0.10, 0.03, 0.02, −0.04, −0.01, −0.01, −0.04),

and the tube returns the raw outlet n_raw = n_tube + ν X n_N₂,tube and T_out = T + ΔT. It has no
failure region. Its standalone maximizer in T is z_T = a_T / 2 = 0.025 (T ≈ 673.65 K).

The box, a and b are the specifications' literals, restated rather than imported from M04's
`studies.surrogate` (which this branch does not carry): the truth is the exactly known answer TR-E2
is checked against, so it shares no code with what is checked.

`SyntheticTruth` is `ParentExperimentTruth` with the closed-form gradient (§5.2): values through
the runner (records and keys), ∂X/∂z_k = X (a_k − 2 z_T δ_kT), ∂ΔT/∂z_k = ΔT b_k, chained to the
process inlet by ∂u/∂s (M04 spec §3.3) and 1/h_k.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
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
from openflowsheet.models.c1.boundary import TubeInlet, TubeOutlet
from openflowsheet.studies.trust_region.truths import ParentExperimentTruth

__all__ = [
    "A_X",
    "B_DT",
    "BOX",
    "VARIANT_ID",
    "InteriorBackend",
    "SyntheticTruth",
    "backend_for",
    "interior",
    "interior_gradient",
    "synthetic_variant",
]

VARIANT_ID: Final = "m05-synthetic-interior-v1"
#: §5.2.
A_X: Final = (0.05, 0.04, 0.03, -0.05, -0.01, -0.015, -0.08)
B_DT: Final = (-0.10, 0.03, 0.02, -0.04, -0.01, -0.01, -0.04)
X0: Final = 0.16
DT0_K: Final = 80.0
#: M04 spec §3.1's box, (lo, hi) per coordinate as decimal literals: T, P, H2/N2, y_NH3, y_Ar,
#: y_CH4, F.
BOX: Final = (
    (653.15, 693.15),
    (9.0e6, 1.0e7),
    (2.5, 3.0),
    (0.02, 0.04),
    (0.01, 0.03),
    (0.01, 0.04),
    (0.0057, 0.0086),
)
CENTERS: Final = tuple((lo + hi) * 0.5 for lo, hi in BOX)
HALF_WIDTHS: Final = tuple((hi - lo) * 0.5 for lo, hi in BOX)
#: ν of N2 + 3 H2 -> 2 NH3 in COMPONENTS order (H2, N2, NH3, Ar, CH4).
NU: Final = (-3.0, -1.0, 2.0, 0.0, 0.0)
MODULE: Final = "tests/support/m05_synthetic.py"


def _scaled(u: Sequence[float]) -> tuple[float, ...]:
    return tuple(
        (value - center) / half for value, center, half in zip(u, CENTERS, HALF_WIDTHS, strict=True)
    )


def tube_z(tube: TubeInlet) -> tuple[float, ...]:
    """z of a tube's own inlet: (T, P, y_H2/y_N2, y_NH3, y_Ar, y_CH4, F), scaled."""
    y = tube.composition
    return _scaled(
        (tube.temperature, tube.outlet_pressure, y[0] / y[1], y[2], y[3], y[4], tube.flow)
    )


def interior(z: Sequence[float]) -> tuple[float, float]:
    """(X, ΔT) at z (§5.2)."""
    eta_x = math.fsum(a * x for a, x in zip(A_X, z, strict=True)) - z[0] * z[0]
    eta_t = math.fsum(b * x for b, x in zip(B_DT, z, strict=True))
    return X0 * math.exp(eta_x), DT0_K * math.exp(eta_t)


def process_z(inlet: Sequence[float], n_tubes: float) -> tuple[float, ...]:
    """z of a process inlet (n₁…n₅, T, P) at `n_tubes`, from the process coordinates."""
    n = inlet[:5]
    total = math.fsum(n)
    return _scaled(
        (inlet[5], inlet[6], n[0] / n[1], n[2] / total, n[3] / total, n[4] / total, total / n_tubes)
    )


def interior_gradient(inlet: Sequence[float], n_tubes: float) -> tuple[tuple[float, ...], ...]:
    """∂(X, ΔT)/∂(n₁…n₅, T, P), closed form (§5.2; M04 spec §3.3's ∂u/∂s)."""
    n = [float(value) for value in inlet[:5]]
    total = math.fsum(n)
    z = process_z(inlet, n_tubes)
    conversion, rise = interior(z)
    g_x = [conversion * (a - (2.0 * z[0] if k == 0 else 0.0)) for k, a in enumerate(A_X)]
    g_t = [rise * b for b in B_DT]
    # ∂u_k/∂s_c, rows u = (T, P, r, y_NH3, y_Ar, y_CH4, F), columns s = (n1..n5, T, P).
    du = [[0.0] * 7 for _ in range(7)]
    du[0][5] = 1.0
    du[1][6] = 1.0
    du[2][0] = 1.0 / n[1]
    du[2][1] = -n[0] / (n[1] * n[1])
    for row, j in ((3, 2), (4, 3), (5, 4)):
        y = n[j] / total
        for i in range(5):
            du[row][i] = ((1.0 if i == j else 0.0) - y) / total
    for i in range(5):
        du[6][i] = 1.0 / n_tubes
    return tuple(
        tuple(math.fsum(g[k] / HALF_WIDTHS[k] * du[k][c] for k in range(7)) for c in range(7))
        for g in (g_x, g_t)
    )


def synthetic_variant() -> variants.Variant:
    """The test-only variant: the stand-in's document with its own id and `model_id` `c1.reactor`
    (as M02's and M04's test-only variants)."""
    standin = variants.registered_variant("standin-x025-v1").document
    document = {
        **standin,
        "model_id": "c1.reactor",
        "variant_id": VARIANT_ID,
        "synthetic": True,
        "evaluation": {"kind": "in_process", "module": MODULE, "conversion_N2": X0},
    }
    return variants.variant_from_document(document)


class InteriorBackend:
    """`Backend` for `m05-synthetic-interior-v1`, in the worker."""

    kind: ExecutionKind = "in_process"

    def __init__(self, variant: variants.Variant) -> None:
        if variant.variant_id != VARIANT_ID:
            raise ValueError(f"{variant.variant_id!r} is not {VARIANT_ID}")
        self.variant = variant

    @staticmethod
    def _configuration() -> dict[str, Any]:
        return {"a": list(A_X), "b": list(B_DT), "x0": X0, "dt0_K": DT0_K}

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
        conversion, rise = interior(tube_z(tube))
        flows = tuple(tube.flow * y for y in tube.composition)
        reacted = conversion * flows[1]
        outlet = TubeOutlet(
            flows=tuple(value + nu * reacted for value, nu in zip(flows, NU, strict=True)),
            temperature=tube.temperature + rise,
            pressure_drop=0.0,
        )
        return Execution(
            kind="in_process", status="completed", answer=outlet, tube_outlet=tube_document(outlet)
        )


def backend_for(variant: variants.Variant) -> Backend:
    """`ExperimentRunner(backend_for=...)`: the interior truth by id, the stand-in in process."""
    if variant.variant_id == VARIANT_ID:
        return InteriorBackend(variant)
    return InProcessBackend(variant)


class SyntheticTruth(ParentExperimentTruth):
    """TR-E2's truth (§6.4): values through the runner, the closed-form gradient."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.finite_difference = None

    def gradient(self, inlet: Sequence[float]) -> Sequence[Sequence[float]]:
        return interior_gradient(inlet, self.n_tubes)
