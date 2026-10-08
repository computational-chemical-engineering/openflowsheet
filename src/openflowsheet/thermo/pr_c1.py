"""`pr-c1-v1`: Peng–Robinson for the C1 loop, the light gases vapour-only (M01 spec §3–§6).

**The method is R-143's and ADR 0026's, not this module's.** Peng–Robinson 1976 with the rounded
Ω_a = 0.45724, Ω_b = 0.07780, κ(ω) of 1976 for every component, van der Waals one-fluid mixing with
k_ij = 0 for every pair (ADR 0026 D1, D3). H2, N2, Ar and CH4 exist only in the vapour; the only
liquid is pure NH3 (R-143). The closed forms are transcribed from spec §4; the expectations they are
judged by are `benchmarks/m01/reference_values.yaml`, produced at 50 digits by
`docs/derivations/scripts/m01_reference.py`, which this module neither imports nor mirrors.

**Roots and phases (spec §5.2).** Pure NH3 (a LIQUID request, or a VAPOR request with no light gas
flowing): above NH3's EOS critical temperature T_c,EOS there is one root, the vapour; below it,
three admissible roots give liquid = smallest and vapour = largest, and a single root is liquid iff
its molar volume is below v_c,EOS. A phase carrying any light gas takes the **largest** admissible
root and is refused `vapour_root_metastable` when three roots exist and the smallest has the lower
G^dep/RT (the guard). Deciding which phases exist is `flash`'s job; `evaluate_phase` answers for the
phase it is asked about, so a metastable pure liquid is evaluable (state L2).

**Derivatives are analytic** (spec §4.6): the root is differentiated implicitly through the cubic,
and the n-derivatives are the derivatives in the mole fractions projected onto the simplex,
∂X/∂n_j = (∂X/∂y_j − Σ_k y_k ∂X/∂y_k)/n_tot, so homogeneity of degree zero holds by construction
(M01.A12 checks it, with Gibbs–Duhem and symmetry, on this implementation). Pure-liquid properties
are composition-free: their n-derivatives are exactly 0.0, an answer, not an omission.

**The reference convention is `PR-C1-ref-v1`** (spec §6, ADR 0026 D4): the ideal gas of each
component at 298.15 K has h = Δ_fH°(298.15 K) of its record; pressure enters only through the
departure. It is a formation datum, so `Σ ν_i h_i` is an enthalpy of reaction.

**The records are data, read at run time, never transcribed into code.**
`benchmarks/m01/components.yaml` holds the five ComponentRecords (H2, N2, NH3, Ar, CH4, in that
order: the identity order of every n-vector), each value with its primary reference (spec §3.1,
ADR 0026 D5). The package carries the file's bytes as package data (`openflowsheet.resources`), so
a checkout and an installed wheel read the same records. `load_records` refuses a file whose order,
units or reference convention are off the registration, and hands over the parsed floats unchanged
(M01.A03: bitwise). `data_sha256` is the SHA-256 of the file's bytes; `implementation_sha256` that
of this module's source, which holds the loader as well as the closed forms.

**Every refusal is typed** (spec §5.3): `status` `unsupported` or `out_of_domain`, and a `message`
that begins with the reason code and a colon. No refusal carries values.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

import yaml

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

#: The records' repository path, one of `openflowsheet.resources.PACKAGED` (spec Q-N4's default).
RECORDS_PATH: Final = "benchmarks/m01/components.yaml"

#: The identity order of every C1 n-vector (spec §3.1).
COMPONENTS: Final[tuple[str, ...]] = ("H2", "N2", "NH3", "Ar", "CH4")

#: The reference convention the records' formation enthalpies define (spec §6, ADR 0026 D4).
REFERENCE_CONVENTION: Final = "PR-C1-ref-v1"

#: Parameter name -> the unit the record must state. `ideal_gas_cp_b<k>` are dimensionless:
#: c_p^ig/R = sum_k b_k (T / 1000 K)^k (spec §3.1).
_UNITS: Final[Mapping[str, str]] = {
    "critical_temperature": "K",
    "critical_pressure": "Pa",
    "acentric_factor": "1",
    "standard_formation_enthalpy": "J/mol",
    **{f"ideal_gas_cp_b{k}": "1" for k in range(5)},
    "ideal_gas_cp_lower_temperature": "K",
    "ideal_gas_cp_upper_temperature": "K",
}


@dataclass(frozen=True)
class C1Component:
    """One C1 component record, as the provider reads it. SI throughout."""

    id: str
    name: str
    #: kg/mol, the only route to a mass basis (ADR 0001 D1.4).
    molar_mass: float
    #: K, Pa and the Pitzer acentric factor of the component's reference equation of state.
    critical_temperature: float
    critical_pressure: float
    acentric_factor: float
    #: J/mol, ideal gas at 298.15 K: the `PR-C1-ref-v1` datum (spec §6).
    formation_enthalpy: float
    #: b_0..b_4 of c_p^ig/R = sum_k b_k (T / 1000 K)^k (NASA TM-4513 low range, spec §3.1).
    cp_coefficients: tuple[float, float, float, float, float]
    #: K, the c_p fit's validity range as recorded.
    cp_temperature_range: tuple[float, float]
    elemental_composition: Mapping[str, int]


@dataclass(frozen=True)
class C1Records:
    """The five records in `COMPONENTS` order, and the SHA-256 of the bytes they were read from."""

    components: tuple[C1Component, ...]
    sha256: str


def _value(quantity: Mapping[str, Any], unit: str, where: str) -> float:
    if quantity.get("unit") != unit:
        raise ValueError(f"{where}: unit {quantity.get('unit')!r}, the record must state {unit!r}")
    value = quantity["value"]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{where}: value {value!r} is not a number")
    return float(value)


def _component(record: Mapping[str, Any]) -> C1Component:
    cid = record["id"]
    parameters = record["parameters"]
    if set(parameters) != set(_UNITS):
        raise ValueError(f"{cid}: parameters {sorted(parameters)} are not {sorted(_UNITS)}")
    value = {name: _value(parameters[name], unit, f"{cid}.{name}") for name, unit in _UNITS.items()}
    b0, b1, b2, b3, b4 = (value[f"ideal_gas_cp_b{k}"] for k in range(5))
    return C1Component(
        id=cid,
        name=record["name"],
        molar_mass=_value(record["molecular_weight"], "kg/mol", f"{cid}.molecular_weight"),
        critical_temperature=value["critical_temperature"],
        critical_pressure=value["critical_pressure"],
        acentric_factor=value["acentric_factor"],
        formation_enthalpy=value["standard_formation_enthalpy"],
        cp_coefficients=(b0, b1, b2, b3, b4),
        cp_temperature_range=(
            value["ideal_gas_cp_lower_temperature"],
            value["ideal_gas_cp_upper_temperature"],
        ),
        elemental_composition=dict(record["elemental_composition"]),
    )


def parse_records(data: bytes) -> C1Records:
    """The records in `data` (the bytes of a `components.yaml`), checked and typed."""
    document = yaml.safe_load(data.decode("utf-8"))
    if document.get("reference_convention") != REFERENCE_CONVENTION:
        raise ValueError(
            f"reference_convention {document.get('reference_convention')!r} is not "
            f"{REFERENCE_CONVENTION!r}"
        )
    components = tuple(_component(record) for record in document["components"])
    if tuple(component.id for component in components) != COMPONENTS:
        raise ValueError(
            f"component order {[c.id for c in components]} is not the registered {list(COMPONENTS)}"
        )
    return C1Records(components=components, sha256=hashlib.sha256(data).hexdigest())


def _checkout_records() -> Path | None:
    """The repository's single copy of the records when this module runs from a source checkout
    (`<root>/src/openflowsheet/thermo/pr_c1.py`), else `None` (`run/manifest.py`'s lock lookup)."""
    here = Path(__file__).resolve()
    root = here.parents[3]
    if here.parents[1] != root / "src" / "openflowsheet":
        return None
    copy = root / RECORDS_PATH
    return copy if copy.is_file() else None


@cache
def load_records() -> C1Records:
    """The C1 records, read once per process (the file is data, not state).

    Package data, spec §15 Q-N4's default. Where the package does not carry them (`PACKAGED`
    without the entry: Q-N4 declined, which is a revert of commit `1621d65`), a source checkout
    reads its single repository copy instead (review F4); an installed package without them has
    no records and says so on first use.
    """
    try:
        return parse_records(packaged(RECORDS_PATH).read_bytes())
    except KeyError:
        checkout = _checkout_records()
    if checkout is None:
        raise FileNotFoundError(
            f"{RECORDS_PATH} is neither package data nor in a source checkout (spec §15 Q-N4)"
        )
    return parse_records(checkout.read_bytes())


# -- the method's constants (spec §3.2, §4) -----------------------------------------------------

PROVIDER_ID: Final = "pr-c1-v1"
STATE_DEFINITION: Final = "nTP-v1"

#: J/(mol K), exact in the 2019 SI; used everywhere, the NASA polynomials included (spec §3.2).
R: Final = 8.31446261815324
#: Peng and Robinson (1976), as rounded there and in IDAES 2.13 (ADR 0026 D1).
OMEGA_A: Final = 0.45724
OMEGA_B: Final = 0.07780
#: K, the datum's temperature (spec §6).
T_REF: Final = 298.15
#: The exact PR critical constants, the cubic's triple root (spec §4.3, 20 digits).
B_C: Final = 0.077796073903888455972
Z_C: Final = 0.30740130869870384801
THETA_C: Final = 5.8773599486044029529
#: v_c/b = Z_c/B_c (spec §4.3).
V_C_OVER_B: Final = 3.951373035591441433

#: The declared domain, inclusive (spec §5.3).
T_MIN: Final = 200.0
T_MAX: Final = 1000.0
P_MIN: Final = 1.0e4
P_MAX: Final = 3.0e7

I_NH3: Final = 2
#: Indices of the vapour-only light gases H2, N2, Ar, CH4 (R-143).
LIGHT: Final[tuple[int, ...]] = (0, 1, 3, 4)
LNPHI: Final[tuple[str, ...]] = tuple(f"lnphi_{c}" for c in COMPONENTS)
PROPERTIES: Final[tuple[str, ...]] = ("h", "Z", "v", *LNPHI)
DERIVATIVE_INPUTS: Final[tuple[str, ...]] = ("T", "P", *(f"n_{c}" for c in COMPONENTS))
_LIQUID_PROPERTIES: Final = frozenset({"h", "Z", "v", "lnphi_NH3"})

#: 1 - k_ij: k_ij = 0 for every pair (ADR 0026 D3; its effect is stated in spec §4.2). Kept as a
#: matrix so the mixing rule reads as spec §4.2 writes it.
_ONE_MINUS_K: Final[tuple[tuple[float, ...], ...]] = ((1.0,) * 5,) * 5

_SQRT2: Final = math.sqrt(2.0)
_C_PLUS: Final = 1.0 + _SQRT2
_C_MINUS: Final = 1.0 - _SQRT2
#: Newton steps polishing each closed-form cubic root; each step at least doubles the digits, so
#: a few reach the double floor from the closed form's ~1e-10, and the bound is declared, not a
#: `while`.
_POLISH_STEPS: Final = 8
#: A polished candidate counts as a root only if the cubic there is within this many unit
#: roundoffs of Σ|terms| (M01 review F2). Horner's own error is at most γ_6 Σ|terms| ≈ 6u Σ|terms|,
#: and Newton's last few steps oscillate at that level, a few ulp of z, rather than stopping; near a
#: double root the closed form puts candidates at the cubic's extremum, where Newton jumps away
#: and its iterate after `_POLISH_STEPS` has a residual of order 10⁻².
_RESIDUAL_ROUNDOFFS: Final = 16.0


#: The flash's fixed bracket samples (spec §5.4 step 6): k/64 for k = 1..63, then 1 − 2^−j for
#: j = 7..40, in that order. Each is exact in binary.
SAMPLES: Final[tuple[float, ...]] = (
    *(k / 64.0 for k in range(1, 64)),
    *(1.0 - 2.0**-j for j in range(7, 41)),
)
#: The bisection's declared bound (spec §5.4 step 6); 2 ulp is reached in ~50 halvings.
_MAX_HALVINGS: Final = 200


@dataclass(frozen=True)
class PRParameters:
    """The Peng–Robinson parameters of the five components (spec §4.1), in `COMPONENTS` order."""

    critical_temperature: tuple[float, ...]
    kappa: tuple[float, ...]
    #: a_c = Ω_a R² T_c² / P_c, Pa m⁶/mol²; and its square root, the mixing rule's building block.
    a_c: tuple[float, ...]
    sqrt_a_c: tuple[float, ...]
    #: b = Ω_b R T_c / P_c, m³/mol.
    b: tuple[float, ...]
    formation_enthalpy: tuple[float, ...]
    cp_coefficients: tuple[tuple[float, float, float, float, float], ...]
    #: NH3's EOS critical point with the rounded Ω's (spec §4.3): T_c,EOS = T_c ((1+κ)/(r+κ))²,
    #: r = √(θ_c Ω_b/Ω_a); P_c,EOS = B_c R T_c,EOS / b; v_c,EOS = (Z_c/B_c) b.
    nh3_critical_temperature: float
    nh3_critical_pressure: float
    nh3_critical_volume: float


@cache
def parameters() -> PRParameters:
    """The parameters of the packaged records (computed once per process)."""
    records = load_records().components
    tc = tuple(c.critical_temperature for c in records)
    kappa = tuple(
        0.37464 + 1.54226 * c.acentric_factor - 0.26992 * c.acentric_factor**2 for c in records
    )
    a_c = tuple(OMEGA_A * R**2 * c.critical_temperature**2 / c.critical_pressure for c in records)
    b = tuple(OMEGA_B * R * c.critical_temperature / c.critical_pressure for c in records)
    r = math.sqrt(THETA_C * OMEGA_B / OMEGA_A)
    t_c_eos = tc[I_NH3] * ((1.0 + kappa[I_NH3]) / (r + kappa[I_NH3])) ** 2
    return PRParameters(
        critical_temperature=tc,
        kappa=kappa,
        a_c=a_c,
        sqrt_a_c=tuple(math.sqrt(value) for value in a_c),
        b=b,
        formation_enthalpy=tuple(c.formation_enthalpy for c in records),
        cp_coefficients=tuple(c.cp_coefficients for c in records),
        nh3_critical_temperature=t_c_eos,
        nh3_critical_pressure=B_C * R * t_c_eos / b[I_NH3],
        nh3_critical_volume=V_C_OVER_B * b[I_NH3],
    )


# -- ideal gas (spec §4.5) ----------------------------------------------------------------------


def cp_ig(temperature: float, index: int) -> float:
    """c_p^ig = R Σ_k b_k τ^k, τ = T/1000 K, J/(mol K)."""
    tau = temperature / 1000.0
    b = parameters().cp_coefficients[index]
    return R * (b[0] + tau * (b[1] + tau * (b[2] + tau * (b[3] + tau * b[4]))))


def h_ig(temperature: float, index: int) -> float:
    """h^ig = Δ_fH° + 1000 R Σ_k b_k (τ^(k+1) − τ_0^(k+1))/(k+1), J/mol; exactly Δ_fH° at T_ref."""
    tau, tau0 = temperature / 1000.0, T_REF / 1000.0
    b = parameters().cp_coefficients[index]
    integral = sum(b[k] * (tau ** (k + 1) - tau0 ** (k + 1)) / (k + 1) for k in range(5))
    return parameters().formation_enthalpy[index] + 1000.0 * R * integral


# -- the mixture and its cubic (spec §4.2, §4.3) ------------------------------------------------


@dataclass(frozen=True)
class _Mixture:
    """A composition at (T, P): the mixing-rule quantities every property needs."""

    temperature: float
    pressure: float
    y: tuple[float, ...]
    g: tuple[float, ...]  # √a_i(T) = √a_c,i (1 + κ_i (1 − √(T/T_c,i)))
    s: tuple[float, ...]  # S_i = Σ_j y_j a_ij
    a_m: float
    b_m: float
    da_m: float  # da_m/dT
    big_a: float  # A = a_m P/(RT)²
    big_b: float  # B = b_m P/(RT)


def _mixture(temperature: float, pressure: float, y: Sequence[float]) -> _Mixture:
    par = parameters()
    g = tuple(
        par.sqrt_a_c[i]
        * (1.0 + par.kappa[i] * (1.0 - math.sqrt(temperature / par.critical_temperature[i])))
        for i in range(5)
    )
    dg = _dg(temperature)
    s = tuple(sum(y[j] * _ONE_MINUS_K[i][j] * g[i] * g[j] for j in range(5)) for i in range(5))
    a_m = sum(y[i] * s[i] for i in range(5))
    b_m = sum(y[i] * par.b[i] for i in range(5))
    da_m = sum(
        y[i] * y[j] * _ONE_MINUS_K[i][j] * (dg[i] * g[j] + g[i] * dg[j])
        for i in range(5)
        for j in range(5)
    )
    rt = R * temperature
    return _Mixture(
        temperature=temperature,
        pressure=pressure,
        y=tuple(y),
        g=g,
        s=s,
        a_m=a_m,
        b_m=b_m,
        da_m=da_m,
        big_a=a_m * pressure / (rt * rt),
        big_b=b_m * pressure / rt,
    )


def _dg(temperature: float) -> tuple[float, ...]:
    """d√a_i/dT = −√a_c,i κ_i / (2 √(T T_c,i)); so da_i/dT = −a_c,i κ_i √α_i/√(T T_c,i) (§4.1)."""
    par = parameters()
    return tuple(
        -par.sqrt_a_c[i]
        * par.kappa[i]
        / (2.0 * math.sqrt(temperature * par.critical_temperature[i]))
        for i in range(5)
    )


def _d2g(temperature: float) -> tuple[float, ...]:
    """d²√a_i/dT² = √a_c,i κ_i / (4 T √(T T_c,i))."""
    par = parameters()
    return tuple(
        par.sqrt_a_c[i]
        * par.kappa[i]
        / (4.0 * temperature * math.sqrt(temperature * par.critical_temperature[i]))
        for i in range(5)
    )


def _cubic(big_a: float, big_b: float) -> tuple[float, float, float]:
    """(c2, c1, c0) of Z³ + c2 Z² + c1 Z + c0: the PR cubic of spec §4.3."""
    return (
        -(1.0 - big_b),
        big_a - 3.0 * big_b * big_b - 2.0 * big_b,
        -(big_a * big_b - big_b * big_b - big_b * big_b * big_b),
    )


def _is_root(z: float, c2: float, c1: float, c0: float) -> bool:
    """Whether the cubic at z is zero to within its own evaluation error (review F2)."""
    residual = ((z + c2) * z + c1) * z + c0
    size = ((abs(z) + abs(c2)) * abs(z) + abs(c1)) * abs(z) + abs(c0)
    return abs(residual) <= _RESIDUAL_ROUNDOFFS * (2.0**-53) * size


def _polish(z: float, c2: float, c1: float, c0: float) -> tuple[float, bool]:
    """Newton on the cubic from z: the polished value, and whether it is a root (`_is_root`)."""
    for _ in range(_POLISH_STEPS):
        slope = (3.0 * z + 2.0 * c2) * z + c1
        if slope == 0.0:
            break
        moved = z - (((z + c2) * z + c1) * z + c0) / slope
        if moved == z:
            break
        z = moved
    return z, _is_root(z, c2, c1, c0)


def _deflated(root: float, c2: float, c1: float, c0: float) -> list[float]:
    """`root` and the real roots of the quadratic left after dividing the cubic by (Z − root).

    Z² + a1 Z + a0 with a1 = c2 + root (the roots sum to −c2) and a0 = −c0/root (their product is
    −c0), which carries root's relative accuracy; solved by the cancellation-free formula. A
    negative discriminant means the cubic's other two roots are a complex pair (review F2).
    """
    a1 = c2 + root
    a0 = -c0 / root if root != 0.0 else c1
    discriminant = a1 * a1 - 4.0 * a0
    if discriminant < 0.0:
        return [root]
    t = -0.5 * (a1 + math.copysign(math.sqrt(discriminant), a1))
    return [root, t, a0 / t if t != 0.0 else 0.0]


def _isolated(candidates: list[tuple[float, bool]], c2: float, c1: float, c0: float) -> float:
    """The best-conditioned root among polished candidates: the converged one of largest |slope|.

    Near a double root the trigonometric form's isolated candidate is accurate (its cosine sits at
    an extremum in θ) and simple, so it converges; were none to, the smallest residual is taken.
    """
    roots = [z for z, converged in candidates if converged]
    if roots:
        return max(roots, key=lambda z: abs((3.0 * z + 2.0 * c2) * z + c1))
    return min((z for z, _ in candidates), key=lambda z: abs(((z + c2) * z + c1) * z + c0))


def admissible_roots(big_a: float, big_b: float) -> tuple[float, ...]:
    """The cubic's real roots Z > B, ascending and distinct (spec §4.3, §5.2 as amended by F2).

    The branch is chosen by the discriminant's sign: the trigonometric form gives three candidates,
    Cardano's one. Each candidate is polished by Newton on the cubic itself and kept only if Newton
    converged (`_polish`). Where the three-root branch keeps fewer than three distinct roots (a
    near-double root, where the discriminant's sign is not resolved), the best-conditioned
    root (`_isolated`) is deflated out and the other two come from the quadratic (`_deflated`); a
    complex pair then leaves one root. Cardano's single root lies
    outside the extremum interval and is simple, so it is kept as polished.
    """
    c2, c1, c0 = _cubic(big_a, big_b)
    discriminant = (
        18.0 * c2 * c1 * c0 - 4.0 * c2**3 * c0 + c2 * c2 * c1 * c1 - 4.0 * c1**3 - 27.0 * c0 * c0
    )
    shift = c2 / 3.0
    p = c1 - c2 * c2 / 3.0
    q = 2.0 * c2**3 / 27.0 - c2 * c1 / 3.0 + c0
    if discriminant > 0.0 and p < 0.0:
        m = 2.0 * math.sqrt(-p / 3.0)
        theta = math.acos(max(-1.0, min(1.0, 3.0 * q / (p * m)))) / 3.0
        raw = [m * math.cos(theta - 2.0 * math.pi * k / 3.0) - shift for k in range(3)]
        polished = [_polish(z, c2, c1, c0) for z in raw]
        roots = sorted({z for z, converged in polished if converged})
        if len(roots) < 3:
            roots = sorted(set(_deflated(_isolated(polished, c2, c1, c0), c2, c1, c0)))
    else:
        half = math.sqrt(max(q * q / 4.0 + p**3 / 27.0, 0.0))
        u = math.cbrt(-q / 2.0 - math.copysign(half, q))
        z, _ = _polish((u - p / (3.0 * u) if u != 0.0 else 0.0) - shift, c2, c1, c0)
        roots = [z]
    return tuple(z for z in roots if z > big_b)


# -- phase properties at one root (spec §4.4, §4.5) ---------------------------------------------


def _log_term(z: float, big_b: float) -> float:
    return math.log((z + _C_PLUS * big_b) / (z + _C_MINUS * big_b))


def _ln_phi(mix: _Mixture, z: float) -> tuple[float, ...]:
    """ln φ_i for every component, present or not (an absent one's is its infinite dilution)."""
    b = parameters().b
    big_a, big_b, a_m, b_m = mix.big_a, mix.big_b, mix.a_m, mix.b_m
    log_term = _log_term(z, big_b)
    c = big_a / (2.0 * _SQRT2 * big_b)
    log_free = math.log(z - big_b)
    return tuple(
        b[i] / b_m * (z - 1.0) - log_free - c * (2.0 * mix.s[i] / a_m - b[i] / b_m) * log_term
        for i in range(5)
    )


def _g_dep(mix: _Mixture, z: float) -> float:
    """G^dep/RT of the phase at its composition: Σ y_i ln φ_i (the guard's measure, §5.2)."""
    return sum(yi * value for yi, value in zip(mix.y, _ln_phi(mix, z), strict=True))


def _h_dep(mix: _Mixture, z: float) -> float:
    t = mix.temperature
    return R * t * (z - 1.0) + (t * mix.da_m - mix.a_m) / (2.0 * _SQRT2 * mix.b_m) * _log_term(
        z, mix.big_b
    )


def _values(mix: _Mixture, z: float) -> dict[str, float]:
    t, p = mix.temperature, mix.pressure
    h = sum(mix.y[i] * h_ig(t, i) for i in range(5)) + _h_dep(mix, z)
    return {"h": h, "Z": z, "v": z * R * t / p, **dict(zip(LNPHI, _ln_phi(mix, z), strict=True))}


def _derivatives(mix: _Mixture, z: float) -> dict[str, tuple[float, float, tuple[float, ...]]]:
    """(∂X/∂T, ∂X/∂P, ∂X/∂y_k) of every property, the root differentiated through the cubic.

    The y_k are treated as independent (the caller projects onto the simplex). With F(Z, A, B) the
    cubic, dZ = −(F_A dA + F_B dB)/F_Z; every other derivative is the chain rule on §4.4–§4.5.
    """
    par = parameters()
    b, t, p, y = par.b, mix.temperature, mix.pressure, mix.y
    big_a, big_b, a_m, b_m, da_m, s, g = (
        mix.big_a,
        mix.big_b,
        mix.a_m,
        mix.b_m,
        mix.da_m,
        mix.s,
        mix.g,
    )
    rt = R * t
    dg, d2g = _dg(t), _d2g(t)
    # Σ_j y_j da_ij/dT and d²a_m/dT².
    d = tuple(
        sum(y[j] * _ONE_MINUS_K[i][j] * (dg[i] * g[j] + g[i] * dg[j]) for j in range(5))
        for i in range(5)
    )
    d2a_m = sum(
        y[i] * y[j] * _ONE_MINUS_K[i][j] * (d2g[i] * g[j] + 2.0 * dg[i] * dg[j] + g[i] * d2g[j])
        for i in range(5)
        for j in range(5)
    )
    a_ij = tuple(tuple(_ONE_MINUS_K[i][j] * g[i] * g[j] for j in range(5)) for i in range(5))

    # A and B: (T, P, y_k).
    a_t = p * da_m / (rt * rt) - 2.0 * big_a / t
    a_p = big_a / p
    a_y = tuple(2.0 * s[k] * p / (rt * rt) for k in range(5))
    b_t = -big_b / t
    b_p = big_b / p
    b_y = tuple(b[k] * p / rt for k in range(5))

    f_z = 3.0 * z * z - 2.0 * (1.0 - big_b) * z + (big_a - 3.0 * big_b * big_b - 2.0 * big_b)
    f_a = z - big_b
    f_b = z * z - (6.0 * big_b + 2.0) * z - big_a + 2.0 * big_b + 3.0 * big_b * big_b

    def dz(da: float, db: float) -> float:
        return -(f_a * da + f_b * db) / f_z

    z_t, z_p = dz(a_t, b_t), dz(a_p, b_p)
    z_y = tuple(dz(a_y[k], b_y[k]) for k in range(5))

    plus, minus = z + _C_PLUS * big_b, z + _C_MINUS * big_b
    log_term = math.log(plus / minus)

    def dlog(dz_: float, db: float) -> float:
        return (dz_ + _C_PLUS * db) / plus - (dz_ + _C_MINUS * db) / minus

    l_t, l_p = dlog(z_t, b_t), dlog(z_p, b_p)
    l_y = tuple(dlog(z_y[k], b_y[k]) for k in range(5))

    # ln φ_i = (b_i/b_m)(Z − 1) − ln(Z − B) − C E_i L,  C = A/(2√2 B),  E_i = 2S_i/a_m − b_i/b_m.
    c = big_a / (2.0 * _SQRT2 * big_b)

    def dc(da: float, db: float) -> float:
        return da / (2.0 * _SQRT2 * big_b) - c * db / big_b

    c_t, c_p = dc(a_t, b_t), dc(a_p, b_p)
    c_y = tuple(dc(a_y[k], b_y[k]) for k in range(5))
    e = tuple(2.0 * s[i] / a_m - b[i] / b_m for i in range(5))
    e_t = tuple(2.0 * d[i] / a_m - 2.0 * s[i] * da_m / (a_m * a_m) for i in range(5))
    free = z - big_b

    out: dict[str, tuple[float, float, tuple[float, ...]]] = {}
    for i in range(5):
        ratio = b[i] / b_m
        ln_t = ratio * z_t - (z_t - b_t) / free - (c_t * e[i] + c * e_t[i]) * log_term
        ln_t -= c * e[i] * l_t
        ln_p = ratio * z_p - (z_p - b_p) / free - c_p * e[i] * log_term - c * e[i] * l_p
        ln_y = []
        for k in range(5):
            e_ik = (
                2.0 * a_ij[i][k] / a_m - 4.0 * s[i] * s[k] / (a_m * a_m) + b[i] * b[k] / (b_m * b_m)
            )
            ln_y.append(
                ratio * z_y[k]
                - b[i] * b[k] / (b_m * b_m) * (z - 1.0)
                - (z_y[k] - b_y[k]) / free
                - (c_y[k] * e[i] + c * e_ik) * log_term
                - c * e[i] * l_y[k]
            )
        out[LNPHI[i]] = (ln_t, ln_p, tuple(ln_y))

    # h = Σ y_i h_i^ig + RT(Z − 1) + G L,  G = (T da_m/dT − a_m)/(2√2 b_m).
    big_g = (t * da_m - a_m) / (2.0 * _SQRT2 * b_m)
    g_t = t * d2a_m / (2.0 * _SQRT2 * b_m)
    g_y = tuple(
        (2.0 * t * d[k] - 2.0 * s[k]) / (2.0 * _SQRT2 * b_m) - big_g * b[k] / b_m for k in range(5)
    )
    h_t = sum(y[i] * cp_ig(t, i) for i in range(5))
    h_t += R * (z - 1.0) + rt * z_t + g_t * log_term + big_g * l_t
    h_p = rt * z_p + big_g * l_p
    h_y = tuple(h_ig(t, k) + rt * z_y[k] + g_y[k] * log_term + big_g * l_y[k] for k in range(5))
    out["h"] = (h_t, h_p, h_y)
    out["Z"] = (z_t, z_p, z_y)
    out["v"] = (
        R * (z + t * z_t) / p,
        rt * (z_p - z / p) / p,
        tuple(rt * z_y[k] / p for k in range(5)),
    )
    return out


# -- root and phase rules (spec §5.2) -----------------------------------------------------------

_PURE_NH3: Final[tuple[float, ...]] = (0.0, 0.0, 1.0, 0.0, 0.0)


@dataclass(frozen=True)
class _PureRoots:
    mixture: _Mixture
    liquid: float | None
    vapour: float | None


def _pure_nh3(temperature: float, pressure: float) -> _PureRoots:
    """Pure NH3's liquid and vapour roots at (T, P), either possibly absent (spec §5.2, 1–3)."""
    par = parameters()
    mix = _mixture(temperature, pressure, _PURE_NH3)
    roots = admissible_roots(mix.big_a, mix.big_b)
    if temperature >= par.nh3_critical_temperature:
        return _PureRoots(mix, None, roots[-1])
    if len(roots) > 1:
        return _PureRoots(mix, roots[0], roots[-1])
    (z,) = roots
    if z * R * temperature / pressure < par.nh3_critical_volume:
        return _PureRoots(mix, z, None)
    return _PureRoots(mix, None, z)


def _pure_stable_phase(roots: _PureRoots) -> Phase:
    """The existing root of lower ln φ_NH3; ties go to the liquid (spec §5.2 item 4)."""
    if roots.liquid is None:
        return "VAPOR"
    if roots.vapour is None:
        return "LIQUID"
    liquid = _ln_phi(roots.mixture, roots.liquid)[I_NH3]
    vapour = _ln_phi(roots.mixture, roots.vapour)[I_NH3]
    return "LIQUID" if liquid <= vapour else "VAPOR"


def _vapour_root(mix: _Mixture) -> tuple[float, bool]:
    """A light-gas phase's root, the largest, and whether the guard refuses it (spec §5.2)."""
    roots = admissible_roots(mix.big_a, mix.big_b)
    largest = roots[-1]
    metastable = len(roots) > 1 and _g_dep(mix, roots[0]) < _g_dep(mix, largest)
    return largest, metastable


def real_roots(temperature: float, pressure: float, n: Sequence[float]) -> tuple[float, ...]:
    """The admissible roots Z > B, ascending, of the composition n/n_tot at (T, P) (§4.3)."""
    total = sum(n)
    mix = _mixture(temperature, pressure, tuple(value / total for value in n))
    return admissible_roots(mix.big_a, mix.big_b)


def _light_flow(n: Sequence[float]) -> float:
    return n[0] + n[1] + n[3] + n[4]


def _domain_violation(state: StreamState) -> str | None:
    """`out_of_domain: ...` when T or P leaves the declared box, or a flow leaves nTP-v1's."""
    t, p = state.temperature, state.pressure
    if not (math.isfinite(t) and math.isfinite(p)):
        return f"out_of_domain: non-finite state (T = {t!r} K, P = {p!r} Pa)"
    if not T_MIN <= t <= T_MAX:
        return f"out_of_domain: temperature {t!r} K outside [{T_MIN}, {T_MAX}] K"
    if not P_MIN <= p <= P_MAX:
        return f"out_of_domain: pressure {p!r} Pa outside [{P_MIN}, {P_MAX}] Pa"
    bad = [c for c, value in zip(COMPONENTS, state.n, strict=True) if not value >= 0.0]
    if bad:
        return f"out_of_domain: component flows {bad} are not finite and non-negative (ADR 0001 D2)"
    if not math.isfinite(state.total_flow):
        return "out_of_domain: the total flow is not finite"
    return None


# -- the provider --------------------------------------------------------------------------------


class PrC1Provider:
    """A `PropertyProvider` for the C1 components on Peng–Robinson (`pr-c1-v1`, ADR 0026).

    Stateless apart from the per-process parameter cache, which is a pure function of the packaged
    records; every method is a pure function of its arguments, so it is declared thread-safe.
    """

    def describe(self) -> PropertyCapabilities:
        return PropertyCapabilities(
            provider_id=PROVIDER_ID,
            implementation_sha256=_implementation_sha256(),
            data_sha256=load_records().sha256,
            reference_convention=REFERENCE_CONVENTION,
            state_definition=STATE_DEFINITION,
            components=COMPONENTS,
            phases=("LIQUID", "VAPOR"),
            properties=PROPERTIES,
            flashes=("TP",),
            derivative_order=dict.fromkeys(DERIVATIVE_INPUTS, 1),
            domain={"T": (T_MIN, T_MAX), "P": (P_MIN, P_MAX)},
            uncertainty=(
                "Peng-Robinson with k_ij = 0: numerically verified against 50-digit closed forms "
                "(M01.A05-A22); validated for pure-component behaviour only (M01 spec §11, W22: "
                "NH3 saturation pressure within 2 %, liquid NH3 and light-gas fugacity "
                "coefficients within 0.05 in ln phi of the reference equations of state). No "
                "mixture VLE validation; k_ij = 0.1 for H2-NH3 would move the separator's vapour "
                "NH3 by about 3 % (spec §4.2)."
            ),
            data_provenance=(
                "benchmarks/m01/components.yaml (M01 spec §3): T_c, P_c, omega of each "
                "component's reference equation of state via chemicals 1.5.2 HEOS; ideal-gas c_p "
                "from NASA TM-4513 (1993) via Cantera 3.2.0; formation enthalpies ATcT 1.112; "
                "cross-checked against CoolProp 8.0.0 (benchmarks/m01/external-crosscheck.json)."
            ),
            thread_safety="thread_safe",
            numerical_limitations=(
                "H2, N2, Ar and CH4 are vapour-only; the only liquid is pure NH3 (R-143): no "
                "dissolved gases, and a liquid carrying a light gas is refused.",
                "A light-gas phase takes the largest cubic root and is refused "
                "vapour_root_metastable where three roots exist and the smallest is the stable "
                "one.",
                "The TP flash solves for the equilibrium vapour's NH3 fraction by fixed samples "
                "and bisection; near NH3's EOS critical temperature a positive excursion narrower "
                "than the samples' spacing can be missed: measured at T = 362.5-401 K and "
                "P = 1.00e7-1.38e7 Pa, where a feed with more NH3 than the missed y* (0.71-0.998) "
                "comes back VAPOR instead of TWO_PHASE (spec §17).",
                "Within about 1e-14 (relative, in P) of a spinodal the cubic has a near-double "
                "root: only candidates that are roots to rounding are kept, and the pair comes "
                "from the deflated quadratic, so a complex pair leaves one root; such states' "
                "classification is not asserted (spec §5.2, Amendment 2).",
                "No PH flash, no entropy, no k_ij.",
            ),
        )

    # -- properties ----------------------------------------------------------------------------

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
        if len(state.n) != len(COMPONENTS):
            return _refused(
                "error", f"state_length: {len(state.n)} flows for the components {COMPONENTS}"
            )
        outside = _domain_violation(state)
        if outside is not None:
            return _refused("out_of_domain", outside)
        if state.is_dormant:
            return _refused("unsupported", "dormant_state: composition undefined")

        t, p = state.temperature, state.pressure
        light = _light_flow(state.n)
        if request.phase == "LIQUID":
            if light > 0.0:
                return _refused(
                    "unsupported",
                    "light_gas_in_liquid: the liquid is pure NH3 (R-143); "
                    f"light-gas flow {light!r} mol/s",
                )
            asked = [name for name in request.properties if name not in _LIQUID_PROPERTIES]
            if asked:
                return _refused(
                    "unsupported",
                    f"light_gas_in_liquid: {asked} of a liquid that holds NH3 only (R-143)",
                )
            pure = _pure_nh3(t, p)
            if pure.liquid is None:
                return _refused(
                    "unsupported",
                    f"no_liquid_root: pure NH3 has no liquid root at {t!r} K, {p!r} Pa",
                )
            mix, z = pure.mixture, pure.liquid
        elif light == 0.0:
            pure = _pure_nh3(t, p)
            if pure.vapour is None:
                return _refused(
                    "unsupported",
                    f"no_vapour_root: pure NH3 has no vapour root at {t!r} K, {p!r} Pa",
                )
            mix, z = pure.mixture, pure.vapour
        else:
            total = state.total_flow
            mix = _mixture(t, p, tuple(value / total for value in state.n))
            z, metastable = _vapour_root(mix)
            if metastable:
                return _refused(
                    "unsupported",
                    "vapour_root_metastable: three roots and the smallest has the lower G^dep/RT "
                    f"at {t!r} K, {p!r} Pa",
                )

        everything = _values(mix, z)
        values = {name: everything[name] for name in request.properties}
        derivatives: dict[str, dict[str, float]] = {}
        if request.derivatives:
            raw = _derivatives(mix, z)
            composition_free = request.phase == "LIQUID"
            total = state.total_flow
            for name in request.properties:
                by_t, by_p, by_y = raw[name]
                mean = sum(mix.y[k] * by_y[k] for k in range(5))
                entry: dict[str, float] = {}
                for wanted in request.derivatives:
                    if wanted == "T":
                        entry[wanted] = by_t
                    elif wanted == "P":
                        entry[wanted] = by_p
                    elif composition_free:
                        entry[wanted] = 0.0
                    else:
                        k = COMPONENTS.index(wanted.removeprefix("n_"))
                        entry[wanted] = (by_y[k] - mean) / total
                derivatives[name] = entry

        return PropertyResult(
            status="ok",
            phase_signature=request.phase,
            values=values,
            derivatives=derivatives,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    # -- flash ---------------------------------------------------------------------------------

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        """The TP flash of spec §5.4: the equilibrium vapour's NH3 fraction y*, then the split.

        y* solves h(y) = ln y + ln φ_NH3^V(T, P; y, (1 − y) w) − ln φ_NH3^L = 0 for the light-gas
        proportions w alone, so it never depends on the feed's NH3 (M01.A21) and the trivial
        solution does not exist in this formulation (spec §5.5). Flash derivatives are
        refused; `FlashResult` has no field to carry them (R-197).
        """
        del context
        if request.specification != "TP":
            return _flash_refused(
                "unsupported",
                f"unsupported_specification: {request.specification!r}; pr-c1-v1 offers TP only",
            )
        if request.derivatives:
            # Amendment 1 (R-197): silence would read as an answer.
            return _flash_refused(
                "unsupported",
                f"flash_derivatives_unsupported: {list(request.derivatives)}; "
                "FlashResult carries no derivatives",
            )
        state = request.state
        if len(state.n) != len(COMPONENTS):
            return _flash_refused(
                "error", f"state_length: {len(state.n)} flows for the components {COMPONENTS}"
            )
        outside = _domain_violation(state)
        if outside is not None:
            return _flash_refused("out_of_domain", outside)
        t, p, n = state.temperature, state.pressure, state.n
        if state.is_dormant:
            # ADR 0001 D3.4: two dormant outlets labelled T and P, no K-value (composition
            # undefined); a valid result, not a failure (step 1).
            dormant = StreamState(n=(0.0,) * 5, temperature=t, pressure=p)
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

        critical = parameters().nh3_critical_temperature
        light = _light_flow(n)
        if light == 0.0:  # step 2
            if t >= critical:
                return _single_phase(state, "VAPOR", "pure_nh3")
            return _single_phase(state, _pure_stable_phase(_pure_nh3(t, p)), "pure_nh3")
        if n[I_NH3] == 0.0:  # step 3
            return _single_phase(state, "VAPOR", "no_nh3")
        if t >= critical:  # step 4
            return _single_phase(state, "VAPOR", "supercritical")
        pure = _pure_nh3(t, p)
        if _pure_stable_phase(pure) == "VAPOR":
            return _single_phase(state, "VAPOR", "no_liquid")

        # Step 5: h(y) on (0, 1) with the vapour's largest root and no guard.
        assert pure.liquid is not None  # the stable pure phase is the liquid
        ln_phi_liquid = _ln_phi(pure.mixture, pure.liquid)[I_NH3]
        proportions = tuple(n[k] / light for k in LIGHT)

        def equilibrium_mixture(fraction: float) -> _Mixture:
            rest = 1.0 - fraction
            w0, w1, w3, w4 = proportions
            return _mixture(t, p, (rest * w0, rest * w1, fraction, rest * w3, rest * w4))

        def h(fraction: float) -> float:
            mix = equilibrium_mixture(fraction)
            z = admissible_roots(mix.big_a, mix.big_b)[-1]
            return math.log(fraction) + _ln_phi(mix, z)[I_NH3] - ln_phi_liquid

        # Step 6: bracket on the fixed samples, then bisect.
        low, high, samples = 0.0, -1.0, 0
        for sample in SAMPLES:
            samples += 1
            if h(sample) >= 0.0:
                high = sample
                break
            low = sample
        if high < 0.0:
            return _single_phase(state, "VAPOR", "no_liquid", samples)
        halvings = 0
        while high - low > 2.0 * math.ulp(high) and halvings < _MAX_HALVINGS:
            middle = (low + high) / 2.0
            halvings += 1
            if h(middle) >= 0.0:
                high = middle
            else:
                low = middle
        y_star = (low + high) / 2.0
        iterations = samples + halvings

        # Step 7: the guard on the converged vapour, then the split.
        if _vapour_root(equilibrium_mixture(y_star))[1]:
            return _flash_refused(
                "unsupported",
                "vapour_root_metastable: the equilibrium vapour's largest root is not its stable "
                f"one (y* = {y_star!r} at {t!r} K, {p!r} Pa)",
            )
        vapour_nh3 = light * y_star / (1.0 - y_star)
        if n[I_NH3] <= vapour_nh3:
            return _single_phase(state, "VAPOR", "undersaturated", iterations)
        return FlashResult(
            status="ok",
            phase_signature="TWO_PHASE",
            vapor_fraction=(light + vapour_nh3) / state.total_flow,
            vapor=StreamState(n=(n[0], n[1], vapour_nh3, n[3], n[4]), temperature=t, pressure=p),
            liquid=StreamState(
                n=(0.0, 0.0, n[I_NH3] - vapour_nh3, 0.0, 0.0), temperature=t, pressure=p
            ),
            # x_NH3 = 1, so K_NH3 = y*; a light gas has no K and is absent ("not computed").
            k_values={"NH3": y_star},
            iterations=iterations,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
            message="route: two_phase",
        )


def _single_phase(state: StreamState, phase: Phase, route: str, iterations: int = 0) -> FlashResult:
    """The present phase carries the feed bitwise; the other is dormant, labelled T and P."""
    empty = StreamState(n=(0.0,) * 5, temperature=state.temperature, pressure=state.pressure)
    return FlashResult(
        status="ok",
        phase_signature=phase,
        vapor_fraction=1.0 if phase == "VAPOR" else 0.0,
        vapor=state if phase == "VAPOR" else empty,
        liquid=state if phase == "LIQUID" else empty,
        iterations=iterations,
        provider_id=PROVIDER_ID,
        reference_convention=REFERENCE_CONVENTION,
        message=f"route: {route}",
    )


def _refused(status: PropertyStatus, message: str) -> PropertyResult:
    """A typed refusal: no phase signature, no values (spec §5.3, M01.A14)."""
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
    """SHA-256 of this module's source (M01.A03; blueprint §6.4 puts it in the exact cache key)."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
