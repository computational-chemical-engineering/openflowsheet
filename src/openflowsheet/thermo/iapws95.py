"""`iapws95-v1`: pure water by the IAPWS-95 formulation (S05 spec, ADR 0045 Proposed).

**The method is the release's, the text is the spec's.** The dimensionless Helmholtz energy
φ(δ, τ) = φ°(δ, τ) + φʳ(δ, τ) of R6-95(2018), with 8 ideal-gas coefficients and 56 residual terms
(spec §2), R_s = 461.51805 J/(kg K) and M = 0.018015268 kg/mol, so the molar R = R_s·M is the
formulation's 8.314371357587 J/(mol K), not CODATA's (R-587). The closed forms are transcribed from
spec §3; the expectations they are judged by are `docs/derivations/scripts/s05_reference.json`,
produced at 50 digits by `s05_reference.py`, which this module neither imports nor mirrors.

**The coefficients are data, read at run time, never transcribed into code.**
`benchmarks/s05/iapws95_coefficients.json` is byte-identical to the design lane's
`docs/derivations/scripts/s05_iapws95_coefficients.json` (S05.A01); `load_coefficients` refuses a
file whose SHA-256 is not `COEFFICIENTS_SHA256` or whose constants are not this module's. The file
sits in no `PACKAGED` path until C10-Q1 is answered (R-594), so only a source checkout reads it; an
installed package says so on first use.

**One jet, order 3** (spec §3.2). `phi_jet(tau, delta)` evaluates φ° and φʳ with every partial in
(δ, τ) up to total order 3 in one pass: the polynomial, exponential and Gaussian terms are products
of a function of δ and a function of τ, so their partials are products of univariate derivatives;
the two non-analytic terms are evaluated in truncated bivariate Taylor arithmetic. Values, the
density and saturation Newton steps and every (T, P) derivative come from those partials, so the
residual and derivative paths describe the same function at the same state. At δ = 1 exactly the
|δ − 1|^{10/3} and |δ − 1|^7 factors are zero jets; ln((δ − 1)²) is never formed.

**Phases** (spec §4). Below 647.0 K the saturation pressure p_σ(T) decides, with a two-sided band
ε_σ = 1e-6 in ln P inside which both phases are answered on their own roots; T ≥ T_c is VAPOR
(C10-Q2's default); (647.0 K, T_c) is labelled by pressure; the box (647.0, 648.0) K ×
[22.0, 22.2] MPa is refused `near_critical`. The density root is a bracketed, safeguarded Newton
(spec §4.4), the saturated densities a two-variable Newton on Maxwell's conditions (spec §3.5).

**Saturation seeds.** The Maxwell solve is seeded by the saturated-density and vapour-pressure
ancillaries of IAPWS SR1-86(1992) (Wagner and Pruss, J. Phys. Chem. Ref. Data 22 (1993) 783,
eqs. 2.5-2.7, as repeated in Wagner and Pruss (2002) eqs. 2.5-2.7). The values below were checked
equal to those carried by `iapws` 1.5.5's `iapws/iapws95.py` (SHA-256
`89edb7c0e3b77533319d253819cdb4c1da50775d2e7b324249574607d6790520`, class `IAPWS95`, `_Pv`,
`_rhoL`, `_rhoG`); neither that package nor the ancillaries' accuracy is a runtime dependency: a
seed only starts Newton, and the converged root is judged by Maxwell's conditions alone.

**The reference convention is `IAPWS95-ref-v1`** (spec §3.6): u = 0 and s = 0 for the saturated
liquid at the triple point, to the rounding of n°₁ and n°₂. It is not a formation datum.

**Every refusal is typed** (spec §4.5): a status and a `message` that begins with the reason code
and a colon. No refusal carries values.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final, NamedTuple

from openflowsheet.compiled import EvaluationContext
from openflowsheet.resources import packaged
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    Phase,
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
    PropertyStatus,
    StreamState,
)

#: The coefficient file's repository path and its registered hash (spec §2.1, S05.A01).
COEFFICIENTS_PATH: Final = "benchmarks/s05/iapws95_coefficients.json"
COEFFICIENTS_SHA256: Final = "b9e93877e37874f1b3a483e298a45692e264d70686d4c158372084b96abbe6ed"

PROVIDER_ID: Final = "iapws95-v1"
REFERENCE_CONVENTION: Final = "IAPWS95-ref-v1"
STATE_DEFINITION: Final = "nTP-v1"
COMPONENTS: Final[tuple[str, ...]] = ("H2O",)

# -- the formulation's constants (spec §2.1); `load_coefficients` checks the file states these ----

#: J/(kg K), the formulation's specific gas constant.
R_S: Final = 461.51805
#: kg/mol.
M: Final = 0.018015268
#: J/(mol K): R_s·M, used everywhere in this provider (R-587).
R: Final = R_S * M
#: K and kg/m³, the reducing state: τ = T_c/T, δ = ρ/ρ_c.
T_C: Final = 647.096
RHO_C: Final = 322.0
#: Pa, the registered critical pressure (a constant, not an output of the EOS).
P_C: Final = 22064000.0
#: K, the triple point and the domain's lower bound.
T_T: Final = 273.16

# -- domain, phase rule and solver constants (spec §4) --------------------------------------------

T_MIN: Final = T_T
T_MAX: Final = 1273.15
P_MIN: Final = 1.0e2
P_MAX: Final = 1.0e8
#: K, the last temperature at which saturation is answered and decides the phase (spec §4.2).
T_SIGMA_MAX: Final = 647.0
#: The two-sided band in ln(P/p_σ) inside which both phases are answered (spec §4.2 step 4).
EPS_SIGMA: Final = 1.0e-6
#: The `near_critical` box: T in the open interval, P in the closed one (spec §4.2 step 1).
NEAR_CRITICAL_T: Final = (647.0, 648.0)
NEAR_CRITICAL_P: Final = (2.20e7, 2.22e7)
#: kg/m³, the liquid bracket's upper end (spec §4.4; p(1250, T) > 100 MPa on the grid, claim C10).
RHO_MAX: Final = 1250.0
#: Newton's declared iteration bound and its convergence rule: relative steps ≤ 4ε (spec §3.5).
MAX_ITERATIONS: Final = 50
STEP_TOLERANCE: Final = 4.0 * 2.0**-52
#: √ε. Once Newton's relative step is this small, quadratic convergence makes the next step
#: ε-sized unless rounding stops it; a step that then fails to shrink means the residuals are at
#: their floor, which is converged too (C10_DECISIONS, WO-S05-1: the 4ε step alone is not
#: reachable where the residual's rounding floor is above it, e.g. Maxwell at 273.16 K and 647.0 K).
FLOOR_ONSET: Final = 2.0**-26


def _converged(step: float, previous: float) -> bool:
    """Spec §3.5's rule on relative steps: ≤ 4ε, or no longer shrinking once below √ε."""
    return step <= STEP_TOLERANCE or (previous <= FLOOR_ONSET and step >= previous)


PHASE_PROPERTIES: Final[tuple[str, ...]] = ("h", "s", "v", "Z", "cp", "lnphi_H2O")
SATURATION_PROPERTIES: Final[tuple[str, ...]] = ("Psat", "Tsat")
PROPERTIES: Final[tuple[str, ...]] = (*PHASE_PROPERTIES, *SATURATION_PROPERTIES)
DERIVATIVE_INPUTS: Final[tuple[str, ...]] = ("T", "P", "n_H2O")

# -- the coefficients -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Coefficients:
    """The file's terms as doubles, in file order (spec §2.2-§2.3)."""

    #: n°₁…n°₈ and γ°₄…γ°₈.
    ideal_n: tuple[float, ...]
    ideal_gamma: tuple[float, ...]
    #: (n, d, t, c) of terms 1-51; c = 0 means no exponential factor.
    power: tuple[tuple[float, int, float, int], ...]
    #: (n, d, t, α, β, γ, ε) of terms 52-54.
    gaussian: tuple[tuple[float, int, float, float, float, float, float], ...]
    #: (n, a, b, B, C, D, A, β) of terms 55-56.
    nonanalytic: tuple[tuple[float, float, float, float, float, float, float, float], ...]
    sha256: str


def parse_coefficients(data: bytes) -> Coefficients:
    """The coefficient file's terms, refused unless it is the registered file (S05.A01)."""
    digest = hashlib.sha256(data).hexdigest()
    if digest != COEFFICIENTS_SHA256:
        raise ValueError(f"coefficient file SHA-256 {digest} is not the registered one")
    raw = json.loads(data)
    stated = (raw["R_specific"], raw["M"], raw["T_c"], raw["rho_c"], raw["p_c"], raw["T_t"])
    if stated != (R_S, M, T_C, RHO_C, P_C, T_T):
        raise ValueError(f"coefficient file constants {stated} are not this module's")
    ideal, power, gauss, na = raw["ideal"], raw["power"], raw["gaussian"], raw["nonanalytic"]
    coefficients = Coefficients(
        ideal_n=tuple(float(x) for x in ideal["n"]),
        ideal_gamma=tuple(float(x) for x in ideal["gamma"]),
        power=tuple(
            (float(n), int(d), float(t), int(c))
            for n, d, t, c in zip(power["n"], power["d"], power["t"], power["c"], strict=True)
        ),
        gaussian=tuple(
            (float(n), int(d), float(t), float(al), float(be), float(ga), float(ep))
            for n, d, t, al, be, ga, ep in zip(
                gauss["n"],
                gauss["d"],
                gauss["t"],
                gauss["alpha"],
                gauss["beta"],
                gauss["gamma"],
                gauss["epsilon"],
                strict=True,
            )
        ),
        nonanalytic=tuple(
            (float(n), float(a), float(b), float(bb), float(cc), float(dd), float(aa), float(be))
            for n, a, b, bb, cc, dd, aa, be in zip(
                na["n"],
                na["a"],
                na["b"],
                na["B"],
                na["C"],
                na["D"],
                na["A"],
                na["beta"],
                strict=True,
            )
        ),
        sha256=digest,
    )
    counts = (
        len(coefficients.ideal_n),
        len(coefficients.ideal_gamma),
        len(coefficients.power),
        len(coefficients.gaussian),
        len(coefficients.nonanalytic),
    )
    if counts != (8, 5, 51, 3, 2):
        raise ValueError(f"coefficient file term counts {counts} are not (8, 5, 51, 3, 2)")
    if any((term[3] == 0) != (k < 7) for k, term in enumerate(coefficients.power)):
        raise ValueError("power terms 1-7 must have c = 0 and terms 8-51 c >= 1")
    return coefficients


def _checkout_coefficients() -> Path | None:
    """The repository's copy when this module runs from a source checkout, else `None`."""
    here = Path(__file__).resolve()
    root = here.parents[3]
    if here.parents[1] != root / "src" / "openflowsheet":
        return None
    copy = root / COEFFICIENTS_PATH
    return copy if copy.is_file() else None


@cache
def load_coefficients() -> Coefficients:
    """The IAPWS-95 coefficients, read once per process (the file is data, not state).

    Package data if `PACKAGED` ever carries the file (it does not until C10-Q1 is answered,
    R-594); otherwise a source checkout reads its single repository copy.
    """
    try:
        return parse_coefficients(packaged(COEFFICIENTS_PATH).read_bytes())
    except KeyError:
        checkout = _checkout_coefficients()
    if checkout is None:
        raise FileNotFoundError(
            f"{COEFFICIENTS_PATH} is neither package data nor in a source checkout (R-594)"
        )
    return parse_coefficients(checkout.read_bytes())


# -- the φ jet (spec §3.2) -----------------------------------------------------------------------


class PhiJet(NamedTuple):
    """φ and its partials in (δ, τ) up to total order 3, in spec §3.2's order."""

    phi: float
    d: float
    dd: float
    t: float
    tt: float
    dt: float
    ddd: float
    ddt: float
    dtt: float
    ttt: float


_Derivs = tuple[float, float, float, float]
#: The constant function 1 of one variable.
_ONE: Final[_Derivs] = (1.0, 0.0, 0.0, 0.0)

#: The bivariate Taylor index (i, j) of each `PhiJet` slot, and i!·j!, which turns a Taylor
#: coefficient into the partial ∂^{i+j}/∂δ^i ∂τ^j.
_INDEX: Final = ((0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (1, 1), (3, 0), (2, 1), (1, 2), (0, 3))
_FACTORIAL: Final = tuple(math.factorial(i) * math.factorial(j) for i, j in _INDEX)
#: (out, a, b) for every product of Taylor coefficients that survives truncation at order 3.
_PRODUCTS: Final = tuple(
    (k, _INDEX.index((i1, j1)), _INDEX.index((i - i1, j - j1)))
    for k, (i, j) in enumerate(_INDEX)
    for i1 in range(i + 1)
    for j1 in range(j + 1)
)


def _power(x: float, e: float) -> _Derivs:
    """x^e and its first three derivatives in x, for x > 0."""
    v0 = x**e
    v1 = e * v0 / x
    v2 = (e - 1.0) * v1 / x
    return v0, v1, v2, (e - 2.0) * v2 / x


def _exp(u: _Derivs) -> _Derivs:
    """exp(u) and its first three derivatives, from u's."""
    u0, u1, u2, u3 = u
    e0 = math.exp(u0)
    return e0, e0 * u1, e0 * (u2 + u1 * u1), e0 * (u3 + 3.0 * u1 * u2 + u1 * u1 * u1)


def _leibniz(f: _Derivs, g: _Derivs) -> _Derivs:
    """The product f·g and its first three derivatives (one variable)."""
    return (
        f[0] * g[0],
        f[1] * g[0] + f[0] * g[1],
        f[2] * g[0] + 2.0 * f[1] * g[1] + f[0] * g[2],
        f[3] * g[0] + 3.0 * (f[2] * g[1] + f[1] * g[2]) + f[0] * g[3],
    )


def _accumulate(acc: list[float], n: float, f: _Derivs, g: _Derivs) -> None:
    """Add n·f(δ)·g(τ)'s partials, slot by slot in `PhiJet` order."""
    acc[0] += n * f[0] * g[0]
    acc[1] += n * f[1] * g[0]
    acc[2] += n * f[2] * g[0]
    acc[3] += n * f[0] * g[1]
    acc[4] += n * f[0] * g[2]
    acc[5] += n * f[1] * g[1]
    acc[6] += n * f[3] * g[0]
    acc[7] += n * f[2] * g[1]
    acc[8] += n * f[1] * g[2]
    acc[9] += n * f[0] * g[3]


def _jet_mul(a: Sequence[float], b: Sequence[float]) -> list[float]:
    """The product of two truncated bivariate Taylor series."""
    out = [0.0] * 10
    for k, i, j in _PRODUCTS:
        out[k] += a[i] * b[j]
    return out


def _separable(f: _Derivs, g: _Derivs) -> list[float]:
    """The Taylor series of f(δ)·g(τ) from univariate derivatives."""
    return [(f[i] / math.factorial(i)) * (g[j] / math.factorial(j)) for i, j in _INDEX]


def _jet_power(a: Sequence[float], e: float) -> list[float]:
    """a^e by composition: Σ_k (x^e)^{(k)}(a₀)/k! · (a − a₀)^k, k ≤ 3."""
    f0, f1, f2, f3 = _power(a[0], e)
    h = [0.0, *a[1:]]
    h2 = _jet_mul(h, h)
    h3 = _jet_mul(h2, h)
    out = [f1 * h[k] + (f2 / 2.0) * h2[k] + (f3 / 6.0) * h3[k] for k in range(10)]
    out[0] = f0
    return out


def _abs_power(x: float, e: float) -> _Derivs:
    """|x|^e and its first three derivatives in x; the zero jet at x = 0 (e > 3, spec §3.2)."""
    if x == 0.0:
        return 0.0, 0.0, 0.0, 0.0
    v0, v1, v2, v3 = _power(abs(x), e)
    sign = 1.0 if x > 0.0 else -1.0
    return v0, sign * v1, v2, sign * v3


def _ideal_jet(tau: float, delta: float, coefficients: Coefficients) -> PhiJet:
    """φ° = ln δ + n°₁ + n°₂τ + n°₃ ln τ + Σ n°ᵢ ln(1 − e^{−γ°ᵢτ}) and its partials (spec §2.2)."""
    n = coefficients.ideal_n
    phi_tau = n[0] + n[1] * tau + n[2] * math.log(tau)
    d1 = n[1] + n[2] / tau
    d2 = -n[2] / (tau * tau)
    d3 = 2.0 * n[2] / (tau * tau * tau)
    for ni, gamma in zip(n[3:], coefficients.ideal_gamma, strict=True):
        x = gamma * tau
        w = 1.0 / math.expm1(x)  # L' = γw, w' = −γw(1 + w) for L = ln(1 − e^{−γτ})
        phi_tau += ni * math.log1p(-math.exp(-x))
        d1 += ni * gamma * w
        d2 -= ni * gamma * gamma * w * (1.0 + w)
        d3 += ni * gamma * gamma * gamma * w * (1.0 + w) * (1.0 + 2.0 * w)
    inverse = 1.0 / delta
    return PhiJet(
        phi=math.log(delta) + phi_tau,
        d=inverse,
        dd=-inverse * inverse,
        t=d1,
        tt=d2,
        dt=0.0,
        ddd=2.0 * inverse * inverse * inverse,
        ddt=0.0,
        dtt=0.0,
        ttt=d3,
    )


def _residual_jet(tau: float, delta: float, coefficients: Coefficients) -> PhiJet:
    """φʳ and its partials (spec §2.3): the terms in file order, summed in that order."""
    acc = [0.0] * 10
    powers: dict[int, _Derivs] = {}
    damping: dict[int, _Derivs] = {}
    for n, d, t, c in coefficients.power:
        f = powers.get(d)
        if f is None:
            f = powers[d] = _power(delta, d)
        if c:
            e = damping.get(c)
            if e is None:
                u0, u1, u2, u3 = _power(delta, c)
                e = damping[c] = _exp((-u0, -u1, -u2, -u3))
            f = _leibniz(f, e)
        _accumulate(acc, n, f, _power(tau, t))
    for n, d, t, alpha, beta, gamma, epsilon in coefficients.gaussian:
        x, y = delta - epsilon, tau - gamma
        f = _leibniz(_power(delta, d), _exp((-alpha * x * x, -2.0 * alpha * x, -2.0 * alpha, 0.0)))
        g = _leibniz(_power(tau, t), _exp((-beta * y * y, -2.0 * beta * y, -2.0 * beta, 0.0)))
        _accumulate(acc, n, f, g)
    x = delta - 1.0
    for n, a, b, big_b, big_c, big_d, big_a, beta in coefficients.nonanalytic:
        # θ = (1 − τ) + A[(δ − 1)²]^{1/(2β)}, Δ = θ² + B[(δ − 1)²]^a, ψ = e^{−C(δ−1)² − D(τ−1)²}.
        q = _abs_power(x, 1.0 / beta)
        r = _abs_power(x, 2.0 * a)
        theta = [
            aq + one_minus
            for aq, one_minus in zip(
                _separable((big_a * q[0], big_a * q[1], big_a * q[2], big_a * q[3]), _ONE),
                _separable(_ONE, (1.0 - tau, -1.0, 0.0, 0.0)),
                strict=True,
            )
        ]
        square = _jet_mul(theta, theta)
        rr = _separable((big_b * r[0], big_b * r[1], big_b * r[2], big_b * r[3]), _ONE)
        big_delta = [square[k] + rr[k] for k in range(10)]
        y = tau - 1.0
        delta_psi = _leibniz(
            (delta, 1.0, 0.0, 0.0), _exp((-big_c * x * x, -2.0 * big_c * x, -2.0 * big_c, 0.0))
        )
        psi_tau = _exp((-big_d * y * y, -2.0 * big_d * y, -2.0 * big_d, 0.0))
        term = _jet_mul(_jet_power(big_delta, b), _separable(delta_psi, psi_tau))
        for k in range(10):
            acc[k] += n * term[k] * _FACTORIAL[k]
    return PhiJet(*acc)


def phi_jet(tau: float, delta: float) -> tuple[PhiJet, PhiJet]:
    """(φ°, φʳ) with every partial up to total order 3 at (τ, δ), in one evaluation (spec §3.2)."""
    coefficients = load_coefficients()
    return _ideal_jet(tau, delta, coefficients), _residual_jet(tau, delta, coefficients)


# -- properties at (T, ρ) and their (T, P) derivatives (spec §3.1, §3.3) -------------------------


class _Dual:
    """A value with its first partials in (δ, τ): first-order dual arithmetic over the jet."""

    __slots__ = ("v", "d", "t")

    def __init__(self, v: float, d: float = 0.0, t: float = 0.0) -> None:
        self.v, self.d, self.t = v, d, t

    def __add__(self, other: _Dual | float) -> _Dual:
        if isinstance(other, _Dual):
            return _Dual(self.v + other.v, self.d + other.d, self.t + other.t)
        return _Dual(self.v + other, self.d, self.t)

    __radd__ = __add__

    def __sub__(self, other: _Dual | float) -> _Dual:
        if isinstance(other, _Dual):
            return _Dual(self.v - other.v, self.d - other.d, self.t - other.t)
        return _Dual(self.v - other, self.d, self.t)

    def __rsub__(self, other: float) -> _Dual:
        return _Dual(other - self.v, -self.d, -self.t)

    def __mul__(self, other: _Dual | float) -> _Dual:
        if isinstance(other, _Dual):
            return _Dual(
                self.v * other.v,
                self.d * other.v + self.v * other.d,
                self.t * other.v + self.v * other.t,
            )
        return _Dual(self.v * other, self.d * other, self.t * other)

    __rmul__ = __mul__

    def __truediv__(self, other: _Dual) -> _Dual:
        q = self.v / other.v
        return _Dual(q, (self.d - q * other.d) / other.v, (self.t - q * other.t) / other.v)

    def __rtruediv__(self, other: float) -> _Dual:
        q = other / self.v
        return _Dual(q, -q * self.d / self.v, -q * self.t / self.v)

    def log1p(self) -> _Dual:
        scale = 1.0 / (1.0 + self.v)
        return _Dual(math.log1p(self.v), self.d * scale, self.t * scale)


#: Property id -> (value, d/dT at constant P, d/dP at constant T).
_Answer = dict[str, tuple[float, float, float]]


def _at(temperature: float, density: float) -> tuple[_Answer, float]:
    """The six phase properties at (T, ρ) with their (T, P) derivatives, and p (spec §3.1, §3.3).

    Every quantity is a `_Dual` in (δ, τ); (∂/∂T)_ρ = −(τ/T)∂/∂τ, (∂/∂ρ)_T = (1/ρ_c)∂/∂δ, and the
    chain rule of spec §3.3 moves them to (T, P) on the branch the density belongs to.
    """
    tau_v, delta_v = T_C / temperature, density / RHO_C
    ideal, res = phi_jet(tau_v, delta_v)
    delta, tau = _Dual(delta_v, 1.0), _Dual(tau_v, 0.0, 1.0)
    phir = _Dual(res.phi, res.d, res.t)
    phir_d = _Dual(res.d, res.dd, res.dt)
    phir_t = _Dual(res.t, res.dt, res.tt)
    phir_dd = _Dual(res.dd, res.ddd, res.ddt)
    phir_dt = _Dual(res.dt, res.ddt, res.dtt)
    phir_tt = _Dual(res.tt, res.dtt, res.ttt)
    phi0 = _Dual(ideal.phi, ideal.d, ideal.t)
    phi0_t = _Dual(ideal.t, ideal.dt, ideal.tt)
    phi0_tt = _Dual(ideal.tt, ideal.dtt, ideal.ttt)
    temp = _Dual(temperature, 0.0, -temperature / tau_v)

    delta_phir_d = delta * phir_d
    z = 1.0 + delta_phir_d
    tau_phi_t = tau * (phi0_t + phir_t)
    values = {
        "h": R * temp * (1.0 + tau_phi_t + delta_phir_d),
        "s": R * (tau_phi_t - phi0 - phir),
        "v": M / (RHO_C * delta),
        "Z": z,
        "cp": -R * (tau * tau) * (phi0_tt + phir_tt)
        + R
        * (z - delta * tau * phir_dt)
        * (z - delta * tau * phir_dt)
        / (1.0 + 2.0 * delta_phir_d + delta * delta * phir_dd),
        "lnphi_H2O": phir + delta_phir_d - delta_phir_d.log1p(),
    }
    pressure = (RHO_C * R_S) * delta * temp * z
    by_t = -tau_v / temperature  # dτ/dT at constant ρ
    p_rho, p_t = pressure.d / RHO_C, pressure.t * by_t
    answer: _Answer = {}
    for name, x in values.items():
        x_rho = x.d / RHO_C
        answer[name] = (x.v, x.t * by_t - x_rho * p_t / p_rho, x_rho / p_rho)
    return answer, pressure.v


def _pressure(temperature: float, density: float) -> tuple[float, float]:
    """p and (∂p/∂ρ)_T at (T, ρ), from the same φʳ jet as every property (spec §3.1)."""
    tau, delta = T_C / temperature, density / RHO_C
    res = _residual_jet(tau, delta, load_coefficients())
    rt = R_S * temperature
    return (
        density * rt * (1.0 + delta * res.d),
        rt * (1.0 + 2.0 * delta * res.d + delta * delta * res.dd),
    )


# -- saturation (spec §3.5) ----------------------------------------------------------------------

#: IAPWS SR1-86(1992) ancillaries (module docstring): ln(p_σ/p_c) = (T_c/T) Σ aᵢ θ^{eᵢ},
#: ρ'/ρ_c = 1 + Σ bᵢ θ^{eᵢ}, ln(ρ''/ρ_c) = Σ cᵢ θ^{eᵢ}, θ = 1 − T/T_c. Seeds only.
_ANC_P: Final = (
    (-7.85951783, 1.0),
    (1.84408259, 1.5),
    (-11.7866497, 3.0),
    (22.6807411, 3.5),
    (-15.9618719, 4.0),
    (1.80122502, 7.5),
)
_ANC_RHO_L: Final = (
    (1.99274064, 1.0 / 3.0),
    (1.09965342, 2.0 / 3.0),
    (-0.510839303, 5.0 / 3.0),
    (-1.75493479, 16.0 / 3.0),
    (-45.5170352, 43.0 / 3.0),
    (-6.74694450e5, 110.0 / 3.0),
)
_ANC_RHO_V: Final = (
    (-2.0315024, 2.0 / 6.0),
    (-2.6830294, 4.0 / 6.0),
    (-5.38626492, 8.0 / 6.0),
    (-17.2991605, 18.0 / 6.0),
    (-44.7586581, 37.0 / 6.0),
    (-63.9201063, 71.0 / 6.0),
)


def _ancillary_pressure(temperature: float) -> float:
    theta = 1.0 - temperature / T_C
    return P_C * math.exp(T_C / temperature * sum(a * theta**e for a, e in _ANC_P))


@dataclass(frozen=True)
class _Saturation:
    """The converged coexisting densities at T and p_σ = p(ρ', T)."""

    temperature: float
    rho_l: float
    rho_v: float
    pressure: float
    iterations: int


def _saturation(temperature: float) -> _Saturation | None:
    """Maxwell's conditions (I8) by two-variable Newton in (δ', δ''), T < T_c; `None` if not
    converged in `MAX_ITERATIONS` or if an iterate leaves ρ' > ρ_c > ρ'' (spec §3.5)."""
    coefficients = load_coefficients()
    theta = 1.0 - temperature / T_C
    tau = T_C / temperature
    dl = 1.0 + sum(b * theta**e for b, e in _ANC_RHO_L)
    dv = math.exp(sum(c * theta**e for c, e in _ANC_RHO_V))
    previous = math.inf
    for iteration in range(1, MAX_ITERATIONS + 1):
        rl, rv = _residual_jet(tau, dl, coefficients), _residual_jet(tau, dv, coefficients)
        kl = 1.0 + 2.0 * dl * rl.d + dl * dl * rl.dd
        kv = 1.0 + 2.0 * dv * rv.d + dv * dv * rv.dd
        # F1 = p/(ρ_c R_s T) and F2 = g/(RT) less its δ-free part, each liquid minus vapour.
        f1 = dl * (1.0 + dl * rl.d) - dv * (1.0 + dv * rv.d)
        f2 = (rl.phi + dl * rl.d + math.log(dl)) - (rv.phi + dv * rv.d + math.log(dv))
        spread = 1.0 / dl - 1.0 / dv
        step_l = -(f2 - f1 / dv) / (kl * spread)
        step_v = -(f2 - f1 / dl) / (kv * spread)
        dl, dv = dl + step_l, dv + step_v
        if not dl > 1.0 > dv > 0.0:
            return None
        step = max(abs(step_l) / dl, abs(step_v) / dv)
        if _converged(step, previous):
            rho_l = dl * RHO_C
            return _Saturation(
                temperature, rho_l, dv * RHO_C, _pressure(temperature, rho_l)[0], iteration
            )
        previous = step
    return None


def _saturation_slope(saturation: _Saturation) -> float:
    """dp_σ/dT by Clausius-Clapeyron (I9) on the converged phases (spec §3.5)."""
    liquid, _ = _at(saturation.temperature, saturation.rho_l)
    vapour, _ = _at(saturation.temperature, saturation.rho_v)
    return (vapour["s"][0] - liquid["s"][0]) / (vapour["v"][0] - liquid["v"][0])


def _tsat(pressure: float) -> tuple[float, float] | None:
    """T_σ(P) and dT_σ/dP: Newton on p_σ(T) = P with I9's slope, seeded by bisection on the
    vapour-pressure ancillary; `None` if not converged (spec §3.5)."""
    low, high = T_T - 1.0, T_C
    for _ in range(64):
        middle = 0.5 * (low + high)
        if _ancillary_pressure(middle) < pressure:
            low = middle
        else:
            high = middle
    temperature = 0.5 * (low + high)
    previous = math.inf
    for _ in range(MAX_ITERATIONS):
        saturation = _saturation(temperature)
        if saturation is None:
            return None
        slope = _saturation_slope(saturation)
        step = (saturation.pressure - pressure) / slope
        relative = abs(step) / temperature
        if _converged(relative, previous):
            return temperature, 1.0 / slope
        temperature -= step
        previous = relative
    return None


@cache
def _tsat_bounds() -> tuple[float, float]:
    """[p_σ(T_t), p_σ(647.0 K)], computed by this provider (spec §3.5); constants of the file."""
    low, high = _saturation(T_T), _saturation(T_SIGMA_MAX)
    if low is None or high is None:
        raise RuntimeError("the saturation bounds did not converge")
    return low.pressure, high.pressure


# -- density roots (spec §4.4) -------------------------------------------------------------------


def _bracketed_density(
    temperature: float, pressure: float, low: float, high: float, start: float
) -> float | None:
    """Safeguarded Newton on p(ρ, T) = P in (low, high]: bisection whenever a step leaves the
    bracket; converged by `_converged`. p(low) < P ≤ p(high) is the caller's."""
    rho, previous = start, math.inf
    for _ in range(MAX_ITERATIONS):
        p, p_rho = _pressure(temperature, rho)
        residual = p - pressure
        if residual == 0.0:
            return rho
        if residual < 0.0:
            low = rho
        else:
            high = rho
        new = rho - residual / p_rho if p_rho > 0.0 else -1.0
        if not low < new < high:
            new = 0.5 * (low + high)
        step = abs(new - rho) / rho
        if _converged(step, previous):
            return new
        rho, previous = new, step
    return None


def _metastable_density(
    temperature: float, pressure: float, start: float, low: float, high: float
) -> float | None:
    """Newton from the saturated density, accepted only while it stays in (low, high] (spec
    §4.4's band roots)."""
    rho, previous = start, math.inf
    for _ in range(MAX_ITERATIONS):
        p, p_rho = _pressure(temperature, rho)
        if not p_rho > 0.0:
            return None
        new = rho - (p - pressure) / p_rho
        if not low < new <= high:
            return None
        step = abs(new - rho) / rho
        if _converged(step, previous):
            return new
        rho, previous = new, step
    return None


def _density(
    temperature: float, pressure: float, phase: Phase, saturation: _Saturation | None
) -> float | None:
    """The root of the answered phase on its bracket (spec §4.4)."""
    ideal = pressure / (R_S * temperature)
    if saturation is None:  # T ≥ T_c
        return _bracketed_density(temperature, pressure, 0.0, RHO_MAX, min(ideal, RHO_MAX))
    if phase == "VAPOR":
        if pressure <= saturation.pressure:
            top = saturation.rho_v
            return _bracketed_density(temperature, pressure, 0.0, top, min(ideal, top))
        return _metastable_density(temperature, pressure, saturation.rho_v, 0.0, RHO_C)
    if pressure >= saturation.pressure:
        bottom = saturation.rho_l
        return _bracketed_density(temperature, pressure, bottom, RHO_MAX, bottom)
    return _metastable_density(temperature, pressure, saturation.rho_l, RHO_C, RHO_MAX)


# -- the phase rule (spec §4.2) ------------------------------------------------------------------


def _near_critical(temperature: float, pressure: float) -> bool:
    return (
        NEAR_CRITICAL_T[0] < temperature < NEAR_CRITICAL_T[1]
        and NEAR_CRITICAL_P[0] <= pressure <= NEAR_CRITICAL_P[1]
    )


@dataclass(frozen=True)
class _Rule:
    """The phases spec §4.2 answers at (T, P), and the saturation it used (T < T_c)."""

    answered: tuple[Phase, ...]
    saturation: _Saturation | None
    route: str


def _rule(temperature: float, pressure: float) -> _Rule | None:
    """Steps 2-4 of spec §4.2 (step 1 is the caller's); `None` when the saturation needed for the
    label does not converge."""
    if temperature >= T_C:
        return _Rule(("VAPOR",), None, "supercritical")
    if temperature > T_SIGMA_MAX:
        answered: tuple[Phase, ...] = (
            ("LIQUID",) if pressure >= P_C else ("VAPOR",) if pressure < 2.20e7 else ()
        )
        return _Rule(answered, None, "near_critical_edge")
    saturation = _saturation(temperature)
    if saturation is None:
        return None
    s_sigma = math.log(pressure / saturation.pressure)
    liquid: tuple[Phase, ...] = ("LIQUID",) if s_sigma >= -EPS_SIGMA else ()
    vapour: tuple[Phase, ...] = ("VAPOR",) if s_sigma <= EPS_SIGMA else ()
    answered = liquid + vapour
    return _Rule(answered, saturation, "saturation")


# -- the provider --------------------------------------------------------------------------------


def _domain_violation(state: StreamState) -> str | None:
    """`out_of_domain: ...` when T or P leaves spec §4.1's box, or the flow leaves nTP-v1's."""
    t, p = state.temperature, state.pressure
    if not (math.isfinite(t) and math.isfinite(p)):
        return f"out_of_domain: non-finite state (T = {t!r} K, P = {p!r} Pa)"
    if not T_MIN <= t <= T_MAX:
        return f"out_of_domain: temperature {t!r} K outside [{T_MIN}, {T_MAX}] K"
    if not P_MIN <= p <= P_MAX:
        return f"out_of_domain: pressure {p!r} Pa outside [{P_MIN}, {P_MAX}] Pa"
    if not (state.n[0] >= 0.0 and math.isfinite(state.n[0])):
        return f"out_of_domain: the H2O flow {state.n[0]!r} is not finite and non-negative"
    return None


_NOT_CONVERGED_SAT: Final = "saturation_not_converged"


class Iapws95Provider:
    """A `PropertyProvider` for pure water on IAPWS-95 (`iapws95-v1`, ADR 0045).

    Stateless apart from the per-process coefficient and saturation-bound caches, which are pure
    functions of the coefficient file; every method is a pure function of its arguments, so it is
    declared thread-safe.
    """

    def describe(self) -> PropertyCapabilities:
        return PropertyCapabilities(
            provider_id=PROVIDER_ID,
            implementation_sha256=_implementation_sha256(),
            data_sha256=load_coefficients().sha256,
            reference_convention=REFERENCE_CONVENTION,
            state_definition=STATE_DEFINITION,
            components=COMPONENTS,
            phases=("LIQUID", "VAPOR"),
            properties=PROPERTIES,
            flashes=("TP",),
            derivative_order=dict.fromkeys(DERIVATIVE_INPUTS, 1),
            domain={"T": (T_MIN, T_MAX), "P": (P_MIN, P_MAX)},
            uncertainty=(
                "IAPWS-95 (R6-95(2018)): numerically verified against a 50-digit evaluation of "
                "the same closed form (S05.A03-A13), whose values CoolProp 8.0.0 and iapws 1.5.5 "
                "both reproduce within the spec's admission bounds. The release's printed "
                "verification tables are not compared (C10-Q1), and accuracy against experiment "
                "is the release's statement, not re-validated here."
            ),
            data_provenance=(
                "benchmarks/s05/iapws95_coefficients.json: transcribed from CoolProp 8.0.0's "
                "Water fluid string and checked equal to iapws 1.5.5's coefficients "
                "(docs/derivations/scripts/s05_crosscheck.py); IAPWS terms of use unresolved, so "
                "the file is not packaged (R-594)."
            ),
            thread_safety="thread_safe",
            numerical_limitations=(
                "near_critical: T in (647.0, 648.0) K with P in [2.20e7, 2.22e7] Pa is refused "
                "for every phase and for the flash.",
                "Below 647.0 K the phase follows saturation with a band eps_sigma = 1e-6 in "
                "ln(P/Psat): inside it both phases are answered on their own roots, and the TP "
                "flash is refused tp_flash_degenerate; metastable states beyond the band are "
                "refused phase_not_stable.",
                "T >= T_c = 647.096 K is answered VAPOR only (C10-Q2's default); in (647.0 K, "
                "T_c) LIQUID needs P >= p_c and VAPOR P < 2.20e7 Pa.",
                "Psat is answered for T in [273.16, 647.0] K and Tsat for P in "
                "[Psat(273.16 K), Psat(647.0 K)]; elsewhere no_saturation.",
                "No PH flash, no g, cv or speed of sound, no ice, no P above 100 MPa.",
            ),
        )

    # -- properties -------------------------------------------------------------------------------

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        del context
        undeclared = [name for name in request.derivatives if name not in DERIVATIVE_INPUTS]
        if undeclared:
            return _refused("unsupported", f"undeclared_derivative_input: {undeclared[0]}")
        unknown = [name for name in request.properties if name not in PROPERTIES]
        if unknown:
            return _refused("unsupported", f"unknown_property: {unknown}")
        state = request.state
        if len(state.n) != 1:
            return _refused("error", f"state_length: {len(state.n)} flows for {COMPONENTS}")
        outside = _domain_violation(state)
        if outside is not None:
            return _refused("out_of_domain", outside)
        if state.is_dormant:
            return _refused("unsupported", "dormant_state: composition undefined")

        t, p = state.temperature, state.pressure
        asked = set(request.properties)
        if "Psat" in asked and t > T_SIGMA_MAX:
            return _refused(
                "unsupported", f"no_saturation: Psat at {t!r} K outside [{T_T}, {T_SIGMA_MAX}] K"
            )
        if "Tsat" in asked:
            low, high = _tsat_bounds()
            if not low <= p <= high:
                return _refused(
                    "unsupported",
                    f"no_saturation: Tsat at {p!r} Pa outside [{low!r}, {high!r}] Pa",
                )

        answer: _Answer = {}
        saturation: _Saturation | None = None
        signature: Phase = request.phase
        if asked & set(PHASE_PROPERTIES):
            if _near_critical(t, p):
                return _refused(
                    "unsupported", f"near_critical: {t!r} K, {p!r} Pa is inside the refused box"
                )
            rule = _rule(t, p)
            if rule is None:
                return _refused("not_converged", f"{_NOT_CONVERGED_SAT}: at {t!r} K")
            if request.phase not in rule.answered:
                return _refused(
                    "unsupported",
                    f"phase_not_stable: {request.phase} at {t!r} K, {p!r} Pa; answered "
                    f"{list(rule.answered)}",
                )
            saturation = rule.saturation
            if saturation is None and t < T_C:
                saturation = _saturation(t)
                if saturation is None:
                    return _refused("not_converged", f"{_NOT_CONVERGED_SAT}: at {t!r} K")
            rho = _density(t, p, request.phase, saturation)
            if rho is None:
                return _refused(
                    "not_converged",
                    f"density_not_converged: {request.phase} at {t!r} K, {p!r} Pa",
                )
            answer, _ = _at(t, rho)
        if "Psat" in asked:
            if saturation is None or saturation.temperature != t:
                saturation = _saturation(t)
            if saturation is None:
                return _refused("not_converged", f"{_NOT_CONVERGED_SAT}: Psat at {t!r} K")
            answer["Psat"] = (saturation.pressure, _saturation_slope(saturation), 0.0)
        if "Tsat" in asked:
            solved = _tsat(p)
            if solved is None:
                return _refused("not_converged", f"{_NOT_CONVERGED_SAT}: Tsat at {p!r} Pa")
            answer["Tsat"] = (solved[0], 0.0, solved[1])

        values = {name: answer[name][0] for name in request.properties}
        derivatives: dict[str, dict[str, float]] = {}
        if request.derivatives:
            slot = {"T": 1, "P": 2}
            for name in request.properties:
                derivatives[name] = {
                    wanted: answer[name][slot[wanted]] if wanted in slot else 0.0
                    for wanted in request.derivatives
                }
        return PropertyResult(
            status="ok",
            phase_signature=signature,
            values=values,
            derivatives=derivatives,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    # -- flash ------------------------------------------------------------------------------------

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        """The TP flash of spec §4.5: single-phase outside the band, refused inside it."""
        del context
        if request.specification != "TP":
            return _flash_refused(
                "unsupported",
                f"unsupported_specification: {request.specification!r}; iapws95-v1 offers TP only",
            )
        if request.derivatives:
            return _flash_refused(
                "unsupported",
                f"flash_derivatives_unsupported: {list(request.derivatives)}; "
                "FlashResult carries no derivatives",
            )
        state = request.state
        if len(state.n) != 1:
            return _flash_refused("error", f"state_length: {len(state.n)} flows for {COMPONENTS}")
        outside = _domain_violation(state)
        if outside is not None:
            return _flash_refused("out_of_domain", outside)
        t, p = state.temperature, state.pressure
        if state.is_dormant:
            dormant = StreamState(n=(0.0,), temperature=t, pressure=p)
            return FlashResult(
                status="ok",
                phase_signature="ZERO_FLOW",
                vapor_fraction=None,
                vapor=dormant,
                liquid=dormant,
                provider_id=PROVIDER_ID,
                reference_convention=REFERENCE_CONVENTION,
                message="route: zero_flow",
            )
        if _near_critical(t, p):
            return _flash_refused(
                "unsupported", f"near_critical: {t!r} K, {p!r} Pa is inside the refused box"
            )
        rule = _rule(t, p)
        if rule is None:
            return _flash_refused("not_converged", f"{_NOT_CONVERGED_SAT}: at {t!r} K")
        if len(rule.answered) != 1:
            return _flash_refused(
                "unsupported",
                f"tp_flash_degenerate: {t!r} K, {p!r} Pa is within eps_sigma of saturation; the "
                "split of a pure fluid at fixed T and P is undetermined",
            )
        (phase,) = rule.answered
        iterations = rule.saturation.iterations if rule.saturation is not None else 0
        empty = StreamState(n=(0.0,), temperature=t, pressure=p)
        return FlashResult(
            status="ok",
            phase_signature=phase,
            vapor_fraction=1.0 if phase == "VAPOR" else 0.0,
            vapor=state if phase == "VAPOR" else empty,
            liquid=state if phase == "LIQUID" else empty,
            iterations=iterations,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
            message=f"route: {rule.route}",
        )


def _refused(status: PropertyStatus, message: str) -> PropertyResult:
    """A typed refusal: no phase signature, no values (spec §4.5)."""
    return PropertyResult(
        status=status,
        phase_signature=None,
        values={},
        provider_id=PROVIDER_ID,
        reference_convention=REFERENCE_CONVENTION,
        message=message,
    )


def _flash_refused(status: PropertyStatus, message: str) -> FlashResult:
    """No outlets and no vapour fraction: a refused flash reports absence, not a split."""
    return FlashResult(
        status=status,
        phase_signature=None,
        vapor_fraction=None,
        vapor=None,
        liquid=None,
        provider_id=PROVIDER_ID,
        reference_convention=REFERENCE_CONVENTION,
        message=message,
    )


@cache
def _implementation_sha256() -> str:
    """SHA-256 of this module's source (S05.A24; blueprint §6.4 puts it in the exact cache key)."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
