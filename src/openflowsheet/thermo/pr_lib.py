"""`pr-lib-v1`: the vapour-only Peng–Robinson library route (L01 spec §4, ADR 0043).

**The method is ADR 0026's, unchanged (ADR 0043 D4).** Peng–Robinson 1976 with the rounded
Ω_a = 0.45724, Ω_b = 0.07780, κ(ω) of 1976 for every component, van der Waals one-fluid mixing with
k_ij = 0 for every pair, and the reference convention `PR-C1-ref-v1`: the ideal gas of each
component at 298.15 K has h = Δ_fH°(298.15 K) of its record, and pressure enters only through the
departure. The closed forms, the cubic's root finder and the analytic derivatives are transcribed
from `pr-c1-v1`'s module (M01 spec §4, §5.2 as amended by F2), generalised from five components to
the record file's nine; nothing is imported from it, so this module's `implementation_sha256`
covers every line that computes a `pr-lib-v1` value. The expectations they are judged by are
`benchmarks/l01/reference_values.yaml`, produced at 50 digits by
`docs/derivations/scripts/l01_reference.py`, which this module neither imports nor mirrors.

**Phases (spec §4.2, ADR 0043 D5).** VAPOR only, for every component: a LIQUID request is refused
`phase_unsupported`, and `flash` is refused `flash_unsupported` (one phase kind, nothing to split).
A vapour takes the **largest** admissible root of the cubic and is refused, in this order,
`vapour_root_metastable` when three roots exist and the smallest has the lower G^dep/RT
(ADR 0026 D2's guard), and `vapour_root_liquid_like` when the chosen root has v < (Z_c/B_c)·b_mix
(R-523: ADR 0026 D2's single-root liquid test with the mixture's b), and then `vapour_unstable`
when a pure-component trial phase i (0 < y_i < 1) has tangent-plane distance
tm_i = ln φ_i^pure − ln y_i − ln φ_i(y) < −10⁻¹⁰, ln φ_i^pure taken at the pure fluid's stable root
(spec §12.3, R-540; for a pure fluid it is D2's guard). All three only refuse. A VAPOR answer is
certified stable against pure-component trial phases only, not against a mixed liquid.

**Derivatives are analytic**: the root is differentiated implicitly through the cubic, and the
n-derivatives are the derivatives in the mole fractions projected onto the simplex,
∂X/∂n_j = (∂X/∂y_j − Σ_k y_k ∂X/∂y_k)/n_tot, so homogeneity of degree zero holds by construction
(L01.A21 checks it, with Gibbs–Duhem and symmetry, on this implementation).

**The records are data, read at run time, never transcribed into code.**
`benchmarks/l01/components.yaml` holds nine ComponentRecords in the identity order of every
`pr-lib-v1` n-vector: H2, N2, Ar, CH4 (copied verbatim from C1's file, one datum per substance),
then H2O, CO2, O2, C2H6, C3H8, each value with its primary reference (spec §4.1, ADR 0043 D6). The
format, the units and the reference convention are C1's (`benchmarks/m01/components.yaml`,
unchanged). The package carries the file's bytes as package data (`openflowsheet.resources`), so a
checkout and an installed wheel read the same records. `load_records` refuses a file whose order,
units or reference convention are off the registration, with a `RecordError` naming the defect, and
hands over the parsed floats unchanged (bitwise). `data_sha256` is the SHA-256 of the file's bytes;
`implementation_sha256` that of this module's source, which holds the loader as well as the closed
forms.

**Every refusal is typed** (spec §4.2): `status` `unsupported` or `out_of_domain`, and a `message`
that begins with the reason code and a colon. No refusal carries values.

**Exposure is WO-L01-3's** (spec §4.3, held): until then the route is reachable only by direct
construction, and from tests.
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
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
    PropertyStatus,
    StreamState,
)

#: The records' repository path, one of `openflowsheet.resources.PACKAGED` (spec §4.1).
RECORDS_PATH: Final = "benchmarks/l01/components.yaml"

#: The identity order of every `pr-lib-v1` n-vector (spec §4.1, L01.A01).
COMPONENTS: Final[tuple[str, ...]] = (
    "H2",
    "N2",
    "Ar",
    "CH4",
    "H2O",
    "CO2",
    "O2",
    "C2H6",
    "C3H8",
)

#: The reference convention the records' formation enthalpies define, shared with `pr-c1-v1`
#: (ADR 0043 D4, ADR 0026 D4).
REFERENCE_CONVENTION: Final = "PR-C1-ref-v1"

#: Parameter name -> the unit the record must state. `ideal_gas_cp_b<k>` are dimensionless:
#: c_p^ig/R = sum_k b_k (T / 1000 K)^k (spec §4.1, C1's format).
_UNITS: Final[Mapping[str, str]] = {
    "critical_temperature": "K",
    "critical_pressure": "Pa",
    "acentric_factor": "1",
    "standard_formation_enthalpy": "J/mol",
    **{f"ideal_gas_cp_b{k}": "1" for k in range(5)},
    "ideal_gas_cp_lower_temperature": "K",
    "ideal_gas_cp_upper_temperature": "K",
}


class RecordError(ValueError):
    """A record file off the registration: the message names the defect and where it is."""


@dataclass(frozen=True)
class LibraryComponent:
    """One `pr-lib-v1` component record, as the route reads it. SI throughout."""

    id: str
    name: str
    #: kg/mol, the only route to a mass basis (ADR 0001 D1.4).
    molar_mass: float
    #: K, Pa and the Pitzer acentric factor of the component's reference equation of state.
    critical_temperature: float
    critical_pressure: float
    acentric_factor: float
    #: J/mol, ideal gas at 298.15 K: the `PR-C1-ref-v1` datum.
    formation_enthalpy: float
    #: b_0..b_4 of c_p^ig/R = sum_k b_k (T / 1000 K)^k (NASA TM-4513 low range).
    cp_coefficients: tuple[float, float, float, float, float]
    #: K, the c_p fit's validity range as recorded.
    cp_temperature_range: tuple[float, float]
    elemental_composition: Mapping[str, int]


@dataclass(frozen=True)
class LibraryRecords:
    """The nine records in `COMPONENTS` order, and the SHA-256 of the bytes they were read from."""

    components: tuple[LibraryComponent, ...]
    sha256: str


def _value(quantity: Mapping[str, Any], unit: str, where: str) -> float:
    if quantity.get("unit") != unit:
        raise RecordError(f"{where}: unit {quantity.get('unit')!r}, the record must state {unit!r}")
    value = quantity["value"]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RecordError(f"{where}: value {value!r} is not a number")
    return float(value)


def _component(record: Mapping[str, Any]) -> LibraryComponent:
    cid = record["id"]
    parameters = record["parameters"]
    if set(parameters) != set(_UNITS):
        raise RecordError(f"{cid}: parameters {sorted(parameters)} are not {sorted(_UNITS)}")
    value = {name: _value(parameters[name], unit, f"{cid}.{name}") for name, unit in _UNITS.items()}
    b0, b1, b2, b3, b4 = (value[f"ideal_gas_cp_b{k}"] for k in range(5))
    return LibraryComponent(
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


def parse_records(data: bytes) -> LibraryRecords:
    """The records in `data` (the bytes of the library's `components.yaml`), checked and typed."""
    document = yaml.safe_load(data.decode("utf-8"))
    if document.get("reference_convention") != REFERENCE_CONVENTION:
        raise RecordError(
            f"reference_convention {document.get('reference_convention')!r} is not "
            f"{REFERENCE_CONVENTION!r}"
        )
    ids = [record["id"] for record in document["components"]]
    if tuple(ids) != COMPONENTS:
        raise RecordError(f"component order {ids} is not the registered {list(COMPONENTS)}")
    components = tuple(_component(record) for record in document["components"])
    return LibraryRecords(components=components, sha256=hashlib.sha256(data).hexdigest())


def _checkout_records() -> Path | None:
    """The repository's single copy of the records when this module runs from a source checkout
    (`<root>/src/openflowsheet/thermo/pr_lib.py`), else `None`."""
    here = Path(__file__).resolve()
    root = here.parents[3]
    if here.parents[1] != root / "src" / "openflowsheet":
        return None
    copy = root / RECORDS_PATH
    return copy if copy.is_file() else None


@cache
def load_records() -> LibraryRecords:
    """The library records, read once per process (the file is data, not state).

    Package data (`PACKAGED`); where the package does not carry them, a source checkout reads its
    single repository copy instead, and an installed package without them says so on first use.
    """
    try:
        return parse_records(packaged(RECORDS_PATH).read_bytes())
    except KeyError:
        checkout = _checkout_records()
    if checkout is None:
        raise FileNotFoundError(f"{RECORDS_PATH} is neither package data nor in a source checkout")
    return parse_records(checkout.read_bytes())


# -- the method's constants (spec §4.2; ADR 0026 D1, transcribed from `pr-c1-v1`) ---------------

PROVIDER_ID: Final = "pr-lib-v1"
STATE_DEFINITION: Final = "nTP-v1"

#: J/(mol K), exact in the 2019 SI; used everywhere, the NASA polynomials included.
R: Final = 8.31446261815324
#: Peng and Robinson (1976), as rounded there and in IDAES 2.13 (ADR 0026 D1).
OMEGA_A: Final = 0.45724
OMEGA_B: Final = 0.07780
#: K, the datum's temperature (`PR-C1-ref-v1`).
T_REF: Final = 298.15
#: v_c/b = Z_c/B_c of the PR cubic's triple root (M01 spec §4.3, 20 digits; ADR 0026 D2): the
#: liquid-like guard's bound (spec §4.2, R-523).
V_C_OVER_B: Final = 3.951373035591441433
#: The `vapour_unstable` threshold on a pure-component trial phase's tangent-plane distance tm_i
#: (spec §12.3, R-540): 10³ above tm's rounding error (about 1e-13).
TM_THRESHOLD: Final = -1.0e-10

#: The declared domain, inclusive: C1's box (spec §4.2).
T_MIN: Final = 200.0
T_MAX: Final = 1000.0
P_MIN: Final = 1.0e4
P_MAX: Final = 3.0e7

#: The number of components, the length of every n-vector.
NC: Final = len(COMPONENTS)
LNPHI: Final[tuple[str, ...]] = tuple(f"lnphi_{c}" for c in COMPONENTS)
PROPERTIES: Final[tuple[str, ...]] = ("h", "Z", "v", *LNPHI)
DERIVATIVE_INPUTS: Final[tuple[str, ...]] = ("T", "P", *(f"n_{c}" for c in COMPONENTS))

#: 1 - k_ij: k_ij = 0 for every pair (ADR 0026 D3). Kept as a matrix so the mixing rule reads as
#: M01 spec §4.2 writes it.
_ONE_MINUS_K: Final[tuple[tuple[float, ...], ...]] = ((1.0,) * NC,) * NC

_SQRT2: Final = math.sqrt(2.0)
_C_PLUS: Final = 1.0 + _SQRT2
_C_MINUS: Final = 1.0 - _SQRT2
#: Newton steps polishing each closed-form cubic root; each step at least doubles the digits, so
#: a few reach the double floor from the closed form's ~1e-10, and the bound is declared, not a
#: `while`.
_POLISH_STEPS: Final = 8
#: A polished candidate counts as a root only if the cubic there is within this many unit
#: roundoffs of Σ|terms| (M01 review F2): Horner's own error is at most γ_6 Σ|terms|, and near a
#: double root the closed form's candidates sit at the cubic's extremum, where Newton jumps away.
_RESIDUAL_ROUNDOFFS: Final = 16.0


@dataclass(frozen=True)
class PRParameters:
    """The Peng–Robinson parameters of the nine components, in `COMPONENTS` order."""

    critical_temperature: tuple[float, ...]
    kappa: tuple[float, ...]
    #: a_c = Ω_a R² T_c² / P_c, Pa m⁶/mol²; and its square root, the mixing rule's building block.
    a_c: tuple[float, ...]
    sqrt_a_c: tuple[float, ...]
    #: b = Ω_b R T_c / P_c, m³/mol.
    b: tuple[float, ...]
    formation_enthalpy: tuple[float, ...]
    cp_coefficients: tuple[tuple[float, float, float, float, float], ...]


@cache
def parameters() -> PRParameters:
    """The parameters of the packaged records (computed once per process)."""
    records = load_records().components
    a_c = tuple(OMEGA_A * R**2 * c.critical_temperature**2 / c.critical_pressure for c in records)
    return PRParameters(
        critical_temperature=tuple(c.critical_temperature for c in records),
        kappa=tuple(
            0.37464 + 1.54226 * c.acentric_factor - 0.26992 * c.acentric_factor**2 for c in records
        ),
        a_c=a_c,
        sqrt_a_c=tuple(math.sqrt(value) for value in a_c),
        b=tuple(OMEGA_B * R * c.critical_temperature / c.critical_pressure for c in records),
        formation_enthalpy=tuple(c.formation_enthalpy for c in records),
        cp_coefficients=tuple(c.cp_coefficients for c in records),
    )


# -- ideal gas ----------------------------------------------------------------------------------


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


# -- the mixture and its cubic ------------------------------------------------------------------


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
        for i in range(NC)
    )
    dg = _dg(temperature)
    s = tuple(sum(y[j] * _ONE_MINUS_K[i][j] * g[i] * g[j] for j in range(NC)) for i in range(NC))
    a_m = sum(y[i] * s[i] for i in range(NC))
    b_m = sum(y[i] * par.b[i] for i in range(NC))
    da_m = sum(
        y[i] * y[j] * _ONE_MINUS_K[i][j] * (dg[i] * g[j] + g[i] * dg[j])
        for i in range(NC)
        for j in range(NC)
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
    """d√a_i/dT = −√a_c,i κ_i / (2 √(T T_c,i))."""
    par = parameters()
    return tuple(
        -par.sqrt_a_c[i]
        * par.kappa[i]
        / (2.0 * math.sqrt(temperature * par.critical_temperature[i]))
        for i in range(NC)
    )


def _d2g(temperature: float) -> tuple[float, ...]:
    """d²√a_i/dT² = √a_c,i κ_i / (4 T √(T T_c,i))."""
    par = parameters()
    return tuple(
        par.sqrt_a_c[i]
        * par.kappa[i]
        / (4.0 * temperature * math.sqrt(temperature * par.critical_temperature[i]))
        for i in range(NC)
    )


def _cubic(big_a: float, big_b: float) -> tuple[float, float, float]:
    """(c2, c1, c0) of Z³ + c2 Z² + c1 Z + c0: the PR cubic (M01 spec §4.3)."""
    return (
        -(1.0 - big_b),
        big_a - 3.0 * big_b * big_b - 2.0 * big_b,
        -(big_a * big_b - big_b * big_b - big_b * big_b * big_b),
    )


def _is_root(z: float, c2: float, c1: float, c0: float) -> bool:
    """Whether the cubic at z is zero to within its own evaluation error (M01 review F2)."""
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

    Z² + a1 Z + a0 with a1 = c2 + root and a0 = −c0/root, solved by the cancellation-free formula;
    a negative discriminant means the other two roots are a complex pair (M01 review F2).
    """
    a1 = c2 + root
    a0 = -c0 / root if root != 0.0 else c1
    discriminant = a1 * a1 - 4.0 * a0
    if discriminant < 0.0:
        return [root]
    t = -0.5 * (a1 + math.copysign(math.sqrt(discriminant), a1))
    return [root, t, a0 / t if t != 0.0 else 0.0]


def _isolated(candidates: list[tuple[float, bool]], c2: float, c1: float, c0: float) -> float:
    """The best-conditioned root among polished candidates: the converged one of largest |slope|;
    were none to converge, the one of smallest residual."""
    roots = [z for z, converged in candidates if converged]
    if roots:
        return max(roots, key=lambda z: abs((3.0 * z + 2.0 * c2) * z + c1))
    return min((z for z, _ in candidates), key=lambda z: abs(((z + c2) * z + c1) * z + c0))


def admissible_roots(big_a: float, big_b: float) -> tuple[float, ...]:
    """The cubic's real roots Z > B, ascending and distinct (M01 spec §5.2 as amended by F2).

    The discriminant's sign picks the trigonometric form (three candidates) or Cardano's (one).
    Each candidate is polished by Newton on the cubic and kept only if it is a root to rounding.
    Where the three-root branch keeps fewer than three distinct roots (a near-double root), the
    best-conditioned one is deflated out and the other two come from the quadratic.
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


# -- phase properties at one root ---------------------------------------------------------------


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
        for i in range(NC)
    )


def _g_dep(mix: _Mixture, z: float) -> float:
    """G^dep/RT of the phase at its composition: Σ y_i ln φ_i (the metastability measure)."""
    return sum(yi * value for yi, value in zip(mix.y, _ln_phi(mix, z), strict=True))


def _h_dep(mix: _Mixture, z: float) -> float:
    t = mix.temperature
    return R * t * (z - 1.0) + (t * mix.da_m - mix.a_m) / (2.0 * _SQRT2 * mix.b_m) * _log_term(
        z, mix.big_b
    )


def _values(mix: _Mixture, z: float) -> dict[str, float]:
    t, p = mix.temperature, mix.pressure
    h = sum(mix.y[i] * h_ig(t, i) for i in range(NC)) + _h_dep(mix, z)
    return {"h": h, "Z": z, "v": z * R * t / p, **dict(zip(LNPHI, _ln_phi(mix, z), strict=True))}


def _derivatives(mix: _Mixture, z: float) -> dict[str, tuple[float, float, tuple[float, ...]]]:
    """(∂X/∂T, ∂X/∂P, ∂X/∂y_k) of every property, the root differentiated through the cubic.

    The y_k are treated as independent (the caller projects onto the simplex). With F(Z, A, B) the
    cubic, dZ = −(F_A dA + F_B dB)/F_Z; every other derivative is the chain rule on the closed
    forms (M01 spec §4.6).
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
        sum(y[j] * _ONE_MINUS_K[i][j] * (dg[i] * g[j] + g[i] * dg[j]) for j in range(NC))
        for i in range(NC)
    )
    d2a_m = sum(
        y[i] * y[j] * _ONE_MINUS_K[i][j] * (d2g[i] * g[j] + 2.0 * dg[i] * dg[j] + g[i] * d2g[j])
        for i in range(NC)
        for j in range(NC)
    )
    a_ij = tuple(tuple(_ONE_MINUS_K[i][j] * g[i] * g[j] for j in range(NC)) for i in range(NC))

    # A and B: (T, P, y_k).
    a_t = p * da_m / (rt * rt) - 2.0 * big_a / t
    a_p = big_a / p
    a_y = tuple(2.0 * s[k] * p / (rt * rt) for k in range(NC))
    b_t = -big_b / t
    b_p = big_b / p
    b_y = tuple(b[k] * p / rt for k in range(NC))

    f_z = 3.0 * z * z - 2.0 * (1.0 - big_b) * z + (big_a - 3.0 * big_b * big_b - 2.0 * big_b)
    f_a = z - big_b
    f_b = z * z - (6.0 * big_b + 2.0) * z - big_a + 2.0 * big_b + 3.0 * big_b * big_b

    def dz(da: float, db: float) -> float:
        return -(f_a * da + f_b * db) / f_z

    z_t, z_p = dz(a_t, b_t), dz(a_p, b_p)
    z_y = tuple(dz(a_y[k], b_y[k]) for k in range(NC))

    plus, minus = z + _C_PLUS * big_b, z + _C_MINUS * big_b
    log_term = math.log(plus / minus)

    def dlog(dz_: float, db: float) -> float:
        return (dz_ + _C_PLUS * db) / plus - (dz_ + _C_MINUS * db) / minus

    l_t, l_p = dlog(z_t, b_t), dlog(z_p, b_p)
    l_y = tuple(dlog(z_y[k], b_y[k]) for k in range(NC))

    # ln φ_i = (b_i/b_m)(Z − 1) − ln(Z − B) − C E_i L,  C = A/(2√2 B),  E_i = 2S_i/a_m − b_i/b_m.
    c = big_a / (2.0 * _SQRT2 * big_b)

    def dc(da: float, db: float) -> float:
        return da / (2.0 * _SQRT2 * big_b) - c * db / big_b

    c_t, c_p = dc(a_t, b_t), dc(a_p, b_p)
    c_y = tuple(dc(a_y[k], b_y[k]) for k in range(NC))
    e = tuple(2.0 * s[i] / a_m - b[i] / b_m for i in range(NC))
    e_t = tuple(2.0 * d[i] / a_m - 2.0 * s[i] * da_m / (a_m * a_m) for i in range(NC))
    free = z - big_b

    out: dict[str, tuple[float, float, tuple[float, ...]]] = {}
    for i in range(NC):
        ratio = b[i] / b_m
        ln_t = ratio * z_t - (z_t - b_t) / free - (c_t * e[i] + c * e_t[i]) * log_term
        ln_t -= c * e[i] * l_t
        ln_p = ratio * z_p - (z_p - b_p) / free - c_p * e[i] * log_term - c * e[i] * l_p
        ln_y = []
        for k in range(NC):
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
        (2.0 * t * d[k] - 2.0 * s[k]) / (2.0 * _SQRT2 * b_m) - big_g * b[k] / b_m for k in range(NC)
    )
    h_t = sum(y[i] * cp_ig(t, i) for i in range(NC))
    h_t += R * (z - 1.0) + rt * z_t + g_t * log_term + big_g * l_t
    h_p = rt * z_p + big_g * l_p
    h_y = tuple(h_ig(t, k) + rt * z_y[k] + g_y[k] * log_term + big_g * l_y[k] for k in range(NC))
    out["h"] = (h_t, h_p, h_y)
    out["Z"] = (z_t, z_p, z_y)
    out["v"] = (
        R * (z + t * z_t) / p,
        rt * (z_p - z / p) / p,
        tuple(rt * z_y[k] / p for k in range(NC)),
    )
    return out


# -- the vapour root rule (spec §4.2, ADR 0043 D5) ----------------------------------------------


def _vapour_root(mix: _Mixture) -> tuple[float, str | None]:
    """The vapour's root, the largest admissible one, and the refusal code of its guards, if any.

    In order: `vapour_root_metastable` when three roots exist and the smallest has the lower
    G^dep/RT (ADR 0026 D2); then `vapour_root_liquid_like` when the root's molar volume is below
    (Z_c/B_c)·b_mix (R-523).
    """
    roots = admissible_roots(mix.big_a, mix.big_b)
    largest = roots[-1]
    if len(roots) > 1 and _g_dep(mix, roots[0]) < _g_dep(mix, largest):
        return largest, "vapour_root_metastable"
    if largest * R * mix.temperature / mix.pressure < V_C_OVER_B * mix.b_m:
        return largest, "vapour_root_liquid_like"
    return largest, None


def _pure_trial_tm(mix: _Mixture, z: float) -> tuple[float, int] | None:
    """The most negative tangent-plane distance of a pure-component trial phase, and its index.

    tm_i = ln φ_i^pure(T, P) − ln y_i − ln φ_i(T, P, y; Z) over the components with 0 < y_i < 1,
    ln φ_i^pure being the smallest ln φ_i over the admissible roots of the pure-i cubic (its stable
    root: a pure phase has G^dep/RT = ln φ). None when no component qualifies (a pure fluid,
    whose stability D2's guard has already settled). Spec §12.3, R-540.
    """
    mixture_ln_phi = _ln_phi(mix, z)
    worst: tuple[float, int] | None = None
    for i, yi in enumerate(mix.y):
        if not 0.0 < yi < 1.0:
            continue
        pure = _mixture(mix.temperature, mix.pressure, tuple(float(k == i) for k in range(NC)))
        stable = min(_ln_phi(pure, root)[i] for root in admissible_roots(pure.big_a, pure.big_b))
        tm = stable - math.log(yi) - mixture_ln_phi[i]
        if worst is None or tm < worst[0]:
            worst = (tm, i)
    return worst


def real_roots(temperature: float, pressure: float, n: Sequence[float]) -> tuple[float, ...]:
    """The admissible roots Z > B, ascending, of the composition n/n_tot at (T, P)."""
    total = sum(n)
    mix = _mixture(temperature, pressure, tuple(value / total for value in n))
    return admissible_roots(mix.big_a, mix.big_b)


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


class PrLibProvider:
    """A `PropertyProvider` for the library components, vapour only (`pr-lib-v1`, ADR 0043).

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
            phases=("VAPOR",),
            properties=PROPERTIES,
            flashes=(),
            derivative_order=dict.fromkeys(DERIVATIVE_INPUTS, 1),
            domain={"T": (T_MIN, T_MAX), "P": (P_MIN, P_MAX)},
            uncertainty=(
                "Peng-Robinson with k_ij = 0, vapour only: numerically verified against 50-digit "
                "closed forms (L01.A15-A21) and against pr-c1-v1 on the shared components "
                "(L01.A14). Not validated against measured mixture data; the method's validation "
                "is ADR 0026's, for pure-component behaviour of the C1 components."
            ),
            data_provenance=(
                "benchmarks/l01/components.yaml (L01 spec §4.1): H2, N2, Ar, CH4 copied from "
                "benchmarks/m01/components.yaml; T_c, P_c, omega of each component's reference "
                "equation of state via chemicals 1.5.2 HEOS; ideal-gas c_p from NASA TM-4513 "
                "(1993) low range via Cantera 3.2.0; formation enthalpies ATcT 1.112; "
                "cross-checked against CoolProp 8.0.0 (benchmarks/l01/components-crosscheck.json)."
            ),
            thread_safety="thread_safe",
            numerical_limitations=(
                "Vapour only: a LIQUID request is refused phase_unsupported and flash is refused "
                "flash_unsupported; no phase split is computed.",
                "A vapour takes the largest cubic root and is refused vapour_root_metastable "
                "where three roots exist and the smallest is the stable one, and "
                "vapour_root_liquid_like where the root's molar volume is below (Z_c/B_c) b_mix, "
                "and vapour_unstable where a pure-component trial phase has tangent-plane "
                "distance below -1e-10 (spec §12.3).",
                "No full phase-stability test: a VAPOR answer is certified stable only against "
                "pure-component trial phases. A vapour unstable only towards a mixed liquid (e.g. "
                "a C2H6-C3H8 condensate with no component supersaturated on its own) is not "
                "detected; dew points also carry the k_ij = 0 error (ADR 0026 D3).",
                "Within about 1e-14 (relative, in P) of a spinodal the cubic has a near-double "
                "root: only candidates that are roots to rounding are kept, and the pair comes "
                "from the deflated quadratic, so a complex pair leaves one root; such states' "
                "classification is not asserted.",
                "c_p is the NASA-7 low range only (200-1000 K), which bounds the temperature "
                "domain. No entropy, no k_ij.",
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
        if len(state.n) != NC:
            return _refused(
                "error", f"state_length: {len(state.n)} flows for the components {COMPONENTS}"
            )
        if request.phase != "VAPOR":
            return _refused(
                "unsupported",
                f"phase_unsupported: {request.phase}; {PROVIDER_ID} is vapour-only "
                "(L01 spec §4.2, ADR 0043 D5)",
            )
        outside = _domain_violation(state)
        if outside is not None:
            return _refused("out_of_domain", outside)
        if state.is_dormant:
            return _refused("unsupported", "dormant_state: composition undefined")

        t, p = state.temperature, state.pressure
        total = state.total_flow
        mix = _mixture(t, p, tuple(value / total for value in state.n))
        z, refusal = _vapour_root(mix)
        if refusal == "vapour_root_metastable":
            return _refused(
                "unsupported",
                "vapour_root_metastable: three roots and the smallest has the lower G^dep/RT "
                f"at {t!r} K, {p!r} Pa",
            )
        if refusal is not None:
            return _refused(
                "unsupported",
                f"vapour_root_liquid_like: the largest root has v/b_mix = "
                f"{z * R * t / (p * mix.b_m)!r} < Z_c/B_c = {V_C_OVER_B!r} at {t!r} K, {p!r} Pa",
            )
        worst = _pure_trial_tm(mix, z)
        if worst is not None and worst[0] < TM_THRESHOLD:
            tm, i = worst
            return _refused(
                "unsupported",
                f"vapour_unstable: pure-{COMPONENTS[i]} trial phase tm = {tm!r} < 0 "
                f"at {t!r} K, {p!r} Pa",
            )

        everything = _values(mix, z)
        values = {name: everything[name] for name in request.properties}
        derivatives: dict[str, dict[str, float]] = {}
        if request.derivatives:
            raw = _derivatives(mix, z)
            for name in request.properties:
                by_t, by_p, by_y = raw[name]
                mean = sum(mix.y[k] * by_y[k] for k in range(NC))
                entry: dict[str, float] = {}
                for wanted in request.derivatives:
                    if wanted == "T":
                        entry[wanted] = by_t
                    elif wanted == "P":
                        entry[wanted] = by_p
                    else:
                        k = COMPONENTS.index(wanted.removeprefix("n_"))
                        entry[wanted] = (by_y[k] - mean) / total
                derivatives[name] = entry

        return PropertyResult(
            status="ok",
            phase_signature="VAPOR",
            values=values,
            derivatives=derivatives,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    # -- flash ---------------------------------------------------------------------------------

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        """Refused `flash_unsupported` for every request: one phase kind, nothing to split."""
        del context
        return FlashResult(
            status="unsupported",
            phase_signature=None,
            vapor_fraction=None,
            vapor=None,
            liquid=None,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
            message=(
                f"flash_unsupported: {request.specification!r}; {PROVIDER_ID} has one phase kind, "
                "VAPOR, so there is nothing to split (L01 spec §4.2)"
            ),
        )


def _refused(status: PropertyStatus, message: str) -> PropertyResult:
    """A typed refusal: no phase signature, no values (spec §4.2)."""
    return PropertyResult(
        status=status,
        phase_signature=None,
        values={},
        provider_id=PROVIDER_ID,
        reference_convention=REFERENCE_CONVENTION,
        message=message,
    )


@cache
def _implementation_sha256() -> str:
    """SHA-256 of this module's source (blueprint §6.4 puts it in the exact cache key)."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
