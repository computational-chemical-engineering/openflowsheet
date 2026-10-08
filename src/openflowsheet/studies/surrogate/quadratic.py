"""The surrogate function: a frozen full quadratic of the scaled inlet (M04 spec §3, ADR 0036 D7).

X̃(z) = β_Xᵀ φ(z) and ΔT̃(z) = β_Tᵀ φ(z), with z = (u(s) − c)/h the scaled inlet of `plan` and
φ the 36-term basis [1, z₁…z₇, z_i z_j (i ≤ j, lexicographic)] (spec §3.4). This module holds:

* the basis and its derivative, and the least-squares fit by Householder QR with M03's
  identifiability threshold (spec §3.4);
* prediction and ∇_z, both summed by `math.fsum` — correctly rounded, so a prediction (and hence a
  score) is the same binary64 value whatever the platform's BLAS;
* the chain rule to the inlet and the two rows the surrogate replaces in M02's extent-fixed
  embedding, R_ξ = ξ − X̃ n_N2,in and R_T = T_out − T_in − ΔT̃, with their closed-form partials
  (spec §3.2–§3.3), and the causal outlet n_out = n_in + ν ξ, T_out = T_in + ΔT̃;
* the admissible output set A(s) = {X̃ ∈ [0, min(0.95, r/3)]} × {ΔT̃ ∈ [−50, 250] K} (refused by the
  unit, never projected) and the empirical-domain status, the scaled excess max(0, ‖z‖∞ − 1)
  (spec §3.2, §3.6).

The parent's hard domain is the parent's own check, applied by the unit (spec §3.6); nothing here
re-implements it. Residual and Jacobian describe the same function wherever the input map is
defined (n_N2 ≠ 0, n_tot ≠ 0).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
from scipy.linalg import solve_triangular

from openflowsheet.models.c1 import NU
from openflowsheet.studies.surrogate.conformal import TAU_ID, TERMS
from openflowsheet.studies.surrogate.plan import BOX, DIMENSION, coordinates, scaled
from openflowsheet.thermo import StreamState

#: The basis (spec §3.4) and the fit method (spec §10.1).
BASIS_ID: Final = "full-quadratic-v1"
FIT_METHOD_ID: Final = "householder-qr-v1"
#: The outputs (spec §3.2): M02's coupling coordinates X = ξ/n_N2,in and ΔT = T_out − T_in.
OUTPUT_MAP_ID: Final = "extent-fixed-xdt-v1"

#: The quadratic terms z_i z_j, i ≤ j, in lexicographic order (spec §3.4).
PAIRS: Final[tuple[tuple[int, int], ...]] = tuple(
    (i, j) for i in range(DIMENSION) for j in range(i, DIMENSION)
)
#: The term names in basis order (`reference_values.json` → `constants.basis_order`).
BASIS_ORDER: Final[tuple[str, ...]] = (
    "1",
    *(f"z{k + 1}" for k in range(DIMENSION)),
    *(f"z{i + 1}*z{j + 1}" for i, j in PAIRS),
)
assert len(BASIS_ORDER) == TERMS

#: The admissible output set's fixed bounds (spec §3.2; M02's coupling bounds, ADR 0034 D2).
ADMISSIBLE_X: Final = (0.0, 0.95)
ADMISSIBLE_DT_K: Final = (-50.0, 250.0)

#: Column order of `extent_rows`' Jacobian: the inlet (n₁…n₅, T, P), then ξ and T_out.
ROW_COLUMNS: Final[tuple[str, ...]] = (
    "inlet.n.H2",
    "inlet.n.N2",
    "inlet.n.NH3",
    "inlet.n.Ar",
    "inlet.n.CH4",
    "inlet.T",
    "inlet.P",
    "xi",
    "outlet.T",
)
_N2: Final = 1
_T: Final = 5

ReferenceDomainStatus = Literal["within_reference_domain", "outside_reference_domain"]


# -- the basis (spec §3.4) ------------------------------------------------------------------------


def basis(z: Sequence[float]) -> tuple[float, ...]:
    """φ(z) = [1, z₁…z₇, z_i z_j for i ≤ j in lexicographic order]."""
    return (1.0, *(float(x) for x in z), *(z[i] * z[j] for i, j in PAIRS))


def basis_gradient(z: Sequence[float]) -> tuple[tuple[float, ...], ...]:
    """∂φ_m/∂z_k, 36 rows of 7: 1 for z_k; z_j δ_ik + z_i δ_jk for z_i z_j (2 z_k if i = j = k)."""
    rows: list[tuple[float, ...]] = [(0.0,) * DIMENSION]
    for k in range(DIMENSION):
        rows.append(tuple(1.0 if c == k else 0.0 for c in range(DIMENSION)))
    for i, j in PAIRS:
        row = [0.0] * DIMENSION
        row[i] += z[j]
        row[j] += z[i]
        rows.append(tuple(row))
    return tuple(rows)


def _finite(values: Sequence[float], what: str) -> tuple[float, ...]:
    out = tuple(float(v) for v in values)
    if not all(math.isfinite(v) for v in out):
        raise ValueError(f"{what} has a non-finite entry")
    return out


@dataclass(frozen=True)
class QuadraticSurrogate:
    """The frozen predictor: 36 coefficients per output, in basis order (spec §3.4)."""

    coefficients_x: tuple[float, ...]
    coefficients_dt: tuple[float, ...]

    def __post_init__(self) -> None:
        for name in ("coefficients_x", "coefficients_dt"):
            values = getattr(self, name)
            if len(values) != TERMS:
                raise ValueError(f"{name} has {len(values)} entries, not {TERMS}")
            object.__setattr__(self, name, _finite(values, name))

    def predict(self, z: Sequence[float]) -> tuple[float, float]:
        """(X̃(z), ΔT̃(z)), each Σ β_m φ_m(z) summed exactly rounded."""
        phi = basis(z)
        return (
            math.fsum(b * f for b, f in zip(self.coefficients_x, phi, strict=True)),
            math.fsum(b * f for b, f in zip(self.coefficients_dt, phi, strict=True)),
        )

    def gradient(self, z: Sequence[float]) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """(∇_z X̃, ∇_z ΔT̃) at z (spec §3.3)."""
        dphi = basis_gradient(z)

        def along(beta: tuple[float, ...]) -> tuple[float, ...]:
            return tuple(
                math.fsum(beta[m] * dphi[m][k] for m in range(TERMS)) for k in range(DIMENSION)
            )

        return along(self.coefficients_x), along(self.coefficients_dt)


# -- the fit (spec §3.4) --------------------------------------------------------------------------


@dataclass(frozen=True)
class QuadraticFit:
    """The fit of the `ok` training draws, or its refusal `training_unidentifiable`.

    `singular_value_ratio` is σ_min(Φ)/σ_max(Φ), `None` when N_ok < 36 refused it first;
    `training_rms` is (RMS e_X, RMS e_ΔT) over the training draws.
    """

    training_ok: int
    singular_value_ratio: float | None
    surrogate: QuadraticSurrogate | None
    training_rms: tuple[float, float] | None
    refusal: Literal["training_unidentifiable"] | None


def fit_quadratic(
    z_rows: Sequence[Sequence[float]], x: Sequence[float], dt: Sequence[float]
) -> QuadraticFit:
    """β minimizing ‖Φβ − y‖₂ by Householder QR (`numpy.linalg.qr`, reduced, then a triangular
    solve), X and ΔT sharing Φ; refused when N_ok < 36 or σ_min/σ_max < τ_id = 1e-8 (spec §3.4).

    The rows are the training draws whose experiments returned `ok`, in plan order.
    """
    n_ok = len(z_rows)
    if not len(x) == len(dt) == n_ok:
        raise ValueError(f"{n_ok} inputs, {len(x)} X values and {len(dt)} dT values")
    if n_ok < TERMS:
        return QuadraticFit(n_ok, None, None, None, "training_unidentifiable")
    phi = np.array([basis(_finite(z, "a training input")) for z in z_rows], dtype=np.float64)
    y = np.column_stack([_finite(x, "X"), _finite(dt, "dT")])
    singular = np.linalg.svd(phi, compute_uv=False)
    ratio = float(singular[-1] / singular[0])
    if not ratio >= TAU_ID:
        return QuadraticFit(n_ok, ratio, None, None, "training_unidentifiable")
    q, r = np.linalg.qr(phi, mode="reduced")
    beta = solve_triangular(r, q.T @ y, lower=False)
    residual = phi @ beta - y
    rms = np.sqrt(np.mean(residual * residual, axis=0))
    surrogate = QuadraticSurrogate(
        coefficients_x=tuple(float(b) for b in beta[:, 0]),
        coefficients_dt=tuple(float(b) for b in beta[:, 1]),
    )
    return QuadraticFit(n_ok, ratio, surrogate, (float(rms[0]), float(rms[1])), None)


# -- the chain rule to the inlet (spec §3.3) ------------------------------------------------------


def input_jacobian(n: Sequence[float], n_tubes: float) -> tuple[tuple[float, ...], ...]:
    """∂u/∂s: rows u₁…u₇, columns n₁…n₅, T, P (spec §3.3); n_N2 ≠ 0 and n_tot ≠ 0.

    ∂T/∂T = 1; ∂P/∂P = 1; ∂r/∂n_H2 = 1/n_N2, ∂r/∂n_N2 = −n_H2/n_N2²; ∂y_j/∂n_i = (δ_ij − y_j)/n_tot
    for j ∈ {NH3, Ar, CH4}; ∂F/∂n_i = 1/N_tubes.
    """
    n_tot = (((n[0] + n[1]) + n[2]) + n[3]) + n[4]
    rows: list[tuple[float, ...]] = [
        (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
        (1.0 / n[1], -n[0] / (n[1] * n[1]), 0.0, 0.0, 0.0, 0.0, 0.0),
    ]
    for j in (2, 3, 4):
        y_j = n[j] / n_tot
        rows.append((*(((1.0 if i == j else 0.0) - y_j) / n_tot for i in range(5)), 0.0, 0.0))
    rows.append((*(1.0 / n_tubes for _ in range(5)), 0.0, 0.0))
    return tuple(rows)


@dataclass(frozen=True)
class InletSensitivity:
    """X̃ and ΔT̃ at an inlet and their derivatives w.r.t. (n₁…n₅, T, P)."""

    z: tuple[float, ...]
    x: float
    dt: float
    dx_ds: tuple[float, ...]
    ddt_ds: tuple[float, ...]


def inlet_sensitivity(
    surrogate: QuadraticSurrogate, inlet: StreamState, n_tubes: float
) -> InletSensitivity | None:
    """∂X̃/∂s_c = Σ_k (g^X_k / h_k) ∂u_k/∂s_c, likewise ΔT̃; `None` where u(s) is undefined."""
    u = coordinates(inlet, n_tubes)
    if u is None:
        return None
    z = scaled(u)
    x, dt = surrogate.predict(z)
    g_x, g_dt = surrogate.gradient(z)
    du = input_jacobian(inlet.n, n_tubes)

    def chain(g: tuple[float, ...]) -> tuple[float, ...]:
        return tuple(
            math.fsum(g[k] / BOX[k].half_width * du[k][c] for k in range(DIMENSION))
            for c in range(7)
        )

    return InletSensitivity(z=z, x=x, dt=dt, dx_ds=chain(g_x), ddt_ds=chain(g_dt))


@dataclass(frozen=True)
class SurrogateRows:
    """The rows `C1RX-extent` and `C1RX-temperature` (spec §3.2) and their partials.

    `residuals` = (R_ξ, R_T); `jacobian` has two rows over `ROW_COLUMNS`.
    """

    residuals: tuple[float, float]
    jacobian: tuple[tuple[float, ...], tuple[float, ...]]


def extent_rows(
    surrogate: QuadraticSurrogate,
    inlet: StreamState,
    n_tubes: float,
    xi: float,
    outlet_temperature: float,
) -> SurrogateRows | None:
    """R_ξ = ξ − X̃ n_N2,in and R_T = T_out − T_in − ΔT̃ with (spec §3.3)

    ∂R_ξ/∂s_c = −n_N2 ∂X̃/∂s_c − X̃ δ_{c,N2}, ∂R_ξ/∂ξ = 1, ∂R_ξ/∂T_out = 0;
    ∂R_T/∂s_c = −∂ΔT̃/∂s_c − δ_{c,T}, ∂R_T/∂T_out = 1, ∂R_T/∂ξ = 0.

    `None` where the input map is undefined (the unit's `surrogate_input_undefined`).
    """
    sensitivity = inlet_sensitivity(surrogate, inlet, n_tubes)
    if sensitivity is None:
        return None
    n_n2 = inlet.n[_N2]
    row_xi = [-n_n2 * d for d in sensitivity.dx_ds]
    row_xi[_N2] -= sensitivity.x
    row_t = [-d for d in sensitivity.ddt_ds]
    row_t[_T] -= 1.0
    return SurrogateRows(
        residuals=(
            xi - sensitivity.x * n_n2,
            (outlet_temperature - inlet.temperature) - sensitivity.dt,
        ),
        jacobian=((*row_xi, 1.0, 0.0), (*row_t, 0.0, 1.0)),
    )


# -- admissibility and the empirical domain (spec §3.2, §3.6) -------------------------------------


def inadmissible_outputs(x: float, dt: float, h2_n2: float) -> tuple[str, ...]:
    """The outputs outside A(s): `X` unless 0 ≤ X̃ ≤ min(0.95, r/3), `dT` unless −50 ≤ ΔT̃ ≤ 250 K.

    r/3 is the H2 limit (n_out,H2 ≥ 0); r can be as low as 1 in the hard domain, so a test against
    [0, 0.95] alone is wrong (spec §3.2, M04.A15).
    """
    found = []
    if not (ADMISSIBLE_X[0] <= x <= ADMISSIBLE_X[1] and x <= h2_n2 / 3.0):
        found.append("X")
    if not ADMISSIBLE_DT_K[0] <= dt <= ADMISSIBLE_DT_K[1]:
        found.append("dT")
    return tuple(found)


@dataclass(frozen=True)
class ReferenceDomain:
    """The empirical domain (spec §3.6): the box z ∈ [−1, 1]⁷, its scaled excess and the
    coordinates outside it. Outside, no coverage claim applies (flagged, not refused)."""

    status: ReferenceDomainStatus
    scaled_excess: float
    coordinates: tuple[str, ...]


def reference_domain(z: Sequence[float]) -> ReferenceDomain:
    """e(z) = max(0, ‖z‖∞ − 1) and the coordinates with |z_k| > 1."""
    excess = max(0.0, max(abs(x) for x in z) - 1.0)
    outside = tuple(BOX[k].name for k, x in enumerate(z) if abs(x) > 1.0)
    status: ReferenceDomainStatus = (
        "outside_reference_domain" if outside else "within_reference_domain"
    )
    return ReferenceDomain(status, excess, outside)


# -- the causal outlet (spec §3.2, §3.7) ----------------------------------------------------------


@dataclass(frozen=True)
class SurrogateOutlet:
    """The surrogate's outlet at an inlet, with what the unit judges it by.

    `status` is `ok`, `dormant` (all flows zero: ξ = 0, T_out = T_in, the surrogate not evaluated;
    ADR 0001) or `input_undefined` (n_N2 = 0 with flow: no H2/N2 ratio). On `ok`, `inadmissible`
    lists the outputs outside A(s) and `domain` is the empirical-domain status.
    """

    status: Literal["ok", "dormant", "input_undefined"]
    xi: float | None
    outlet_temperature: float | None
    n_out: tuple[float, ...] | None
    x: float | None
    dt: float | None
    inadmissible: tuple[str, ...]
    domain: ReferenceDomain | None


def causal_outlet(
    surrogate: QuadraticSurrogate, inlet: StreamState, n_tubes: float
) -> SurrogateOutlet:
    """ξ = X̃ n_N2,in, T_out = T_in + ΔT̃, n_out = n_in + ν ξ (inerts copied bitwise)."""
    if inlet.is_dormant:
        return SurrogateOutlet(
            "dormant", 0.0, inlet.temperature, tuple(inlet.n), None, None, (), None
        )
    u = coordinates(inlet, n_tubes)
    if u is None:
        return SurrogateOutlet("input_undefined", None, None, None, None, None, (), None)
    z = scaled(u)
    x, dt = surrogate.predict(z)
    xi = x * inlet.n[_N2]
    n_out = tuple(n + nu * xi if nu else n for n, nu in zip(inlet.n, NU, strict=True))
    return SurrogateOutlet(
        status="ok",
        xi=xi,
        outlet_temperature=inlet.temperature + dt,
        n_out=n_out,
        x=x,
        dt=dt,
        inadmissible=inadmissible_outputs(x, dt, u[2]),
        domain=reference_domain(z),
    )
