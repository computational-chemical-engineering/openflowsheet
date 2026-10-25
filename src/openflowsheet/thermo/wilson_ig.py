"""`wilson-ig-v1`: γ–φ with a Wilson liquid and an ideal-gas vapour (S10 spec §3–§5, ADR 0047).

**The method is ADR 0047's, the text is the spec's.** The liquid is a Wilson liquid with constant
Λ_ij > 0 (Λ_ii = 1) over pure liquids whose fugacity is the vapour pressure: no Poynting factor,
φ^sat = 1. The vapour is an ideal gas. The vapour pressure is DIPPR-101 with E = 2 in θ = T/1000 K,
ln(P^sat/Pa) = a + b/θ + c ln θ + d θ², and the ideal-gas properties are NASA-7 low-range
polynomials, c_p^ig/R = Σ_k b_k θ^k. Every caloric term follows from the same potential: the latent
heat is Δh_i = R T² d ln P_i^sat/dT (Gibbs–Helmholtz), and h^E = 0, v^E = 0 hold because Λ is
constant (spec §3.3–§3.4). The closed forms are transcribed from spec §3; the expectations they are
judged by are `benchmarks/s10/reference_values.yaml`, produced at 50 digits by
`docs/derivations/scripts/s10_reference.py`, which this module neither imports nor mirrors.

**What `evaluate_phase` answers** (spec §3.5–§3.6, §5.3): `h`, the phase's molar enthalpy, and
`lnphi_<c>`, with ln φ_i^L = ln γ_i + ln P_i^sat − ln P and ln φ_i^V = 0, so K_i = γ_i P_i^sat/P and
a consumer written for φ–φ providers reads this method unchanged. Derivatives are order 1 in `T`,
`P` and every `n_<c>`, analytic, from the same intermediate quantities as the values at the same
state. The n-derivatives are the derivatives in the mole fractions projected onto the simplex,
∂X/∂n_j = (∂X/∂x_j − Σ_k x_k ∂X/∂x_k)/n_tot, so homogeneity holds by construction. Every
derivative that is an identity of the model (every vapour ln φ derivative, ∂h/∂P in both phases)
is returned as the answer `0.0`, never omitted (S10.A06). The phase is the one asked about:
`evaluate_phase` never decides phases, so a metastable liquid is answered.

**What `flash` and `stability` answer** (spec §4, §5.4–§5.5): the TP flash `S10-tp-flash-v1`, a
closed-form vapour trial, a liquid trial by successive substitution, then a two-phase successive
substitution on Rachford–Rice. Both phase models are strictly convex in composition (spec §4.1), so
a single phase whose other-model trial distance is ≥ −1e-10 and a converged split with 0 < β < 1
are global within the model: every `ok` result states `STABLE_WITHIN_TESTED_SCOPE` with scope
`S10-tpd-v1` and its distances in `message`, by spec §5.4's grammar. A loop that reaches its cap
is `not_converged` with label `UNKNOWN` and no outlets, never a split. `stability()`, outside the
frozen Protocol (ADR 0047 C1), judges one phase against the other model's trial and returns a
`StabilityReport`; it reports and never raises.

**The records are data, read at run time, never transcribed into code** (spec §5.1). The real
records are `benchmarks/s10/records.yaml`, read from a source checkout only: they are not package
data until their rights are vetted and Frank decides (R-706). Before WO-S10-3 the file does not
exist and construction refuses with `RecordError("records_missing: …")`. Any other record file of
the same format (the verification records, `benchmarks/s10/verification-records.yaml`) is passed
by path. `parse_records` refuses a file off the registration with a `RecordError` whose message
begins with one of the codes `record_structure`, `record_units`, `record_convention`,
`record_lambda`, `record_domain`, and hands over the parsed floats unchanged (S10.A02: bitwise).
`data_sha256` is the SHA-256 of the file's bytes; `implementation_sha256` that of this module's
source, which holds the loader, the closed forms, the flash and the stability search.

**Every refusal is typed** (spec §5.3): a status and a `message` that begins with the reason code
and a colon. No refusal carries values.

**Library-only** (R-568, R-569, R-709): no revision can select this provider; it is reachable by
direct construction and from tests.
"""

from __future__ import annotations

import hashlib
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from openflowsheet.compiled import EvaluationContext
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
from openflowsheet.thermo.stability import StabilityLabel, StabilityReport

PROVIDER_ID: Final = "wilson-ig-v1"
STATE_DEFINITION: Final = "nTP-v1"

#: The real records' repository path (spec §5.1); in no `openflowsheet.resources.PACKAGED` path
#: (R-706, S10.A28).
RECORDS_PATH: Final = "benchmarks/s10/records.yaml"

#: The two registered conventions and the `synthetic` flag each requires (spec §3.1, §5.1, R-704).
CONVENTIONS: Final[Mapping[str, bool]] = {"WILSON-IG-ref-v1": False, "S10-VER-ref-v1": True}

#: J/(mol K), exact in the 2019 SI (spec §2).
R: Final = 8.31446261815324
#: K, the unit of θ = T/(1000 K) (spec §2).
T_UNIT: Final = 1000.0
#: θ₀ = T₀/(1000 K) with T₀ = 298.15 K, the datum of h^ig (spec §2, eq. 3.2).
THETA_0: Final = 0.29815
#: K, the NASA-7 low range the records' T domain must lie in (spec §5.1 `record_domain`).
T_NASA: Final = (200.0, 1000.0)

#: The scope id of every stability label this provider states (spec §4.3): trial models
#: {LIQUID: Wilson, VAPOR: ideal gas}, the vapour trial in closed form, the liquid trial by
#: successive substitution to DELTA_SS within SS_MAX iterations, resolution EPS_TPD.
SCOPE: Final = "S10-tpd-v1"
#: The resolution in the tangent-plane distance (spec §4.3, §5.6; R-540's value).
EPS_TPD: Final = 1.0e-10
#: The stop of the two-phase successive substitution, in max |Δ ln K| (spec §5.4 step 4, §5.6).
DELTA_K: Final = 1.0e-13
#: The stop of the liquid-trial successive substitution, in max |Δ ln W| (spec §5.4 step 3, §5.6).
DELTA_SS: Final = 1.0e-13
#: Spec §5.6's cap, per loop: SS_MAX for the liquid trial, SS_MAX_TWO_PHASE for the two-phase
#: loop. Two names for one registered value, so S10.A20 can patch each loop's cap alone; there is
#: no production knob.
SS_MAX: Final = 1000
SS_MAX_TWO_PHASE: Final = 1000

#: The record file's top-level keys, exactly (spec §5.1).
_TOP_KEYS: Final = frozenset(
    {
        "schema_version",
        "record_schema",
        "data_set",
        "reference_convention",
        "synthetic",
        "uncertainty",
        "data_provenance",
        "domain",
        "components",
        "wilson_lambda",
    }
)
#: A component's keys: ComponentRecord's required keys plus `synthetic` (spec §5.1
#: `record_convention`), and ComponentRecord's optional ones.
_COMPONENT_REQUIRED: Final = frozenset(
    {"id", "name", "synthetic", "molecular_weight", "elemental_composition", "parameters", "rights"}
)
_COMPONENT_ALLOWED: Final = _COMPONENT_REQUIRED | {"identifiers", "elemental_verification"}
_LAMBDA_REQUIRED: Final = frozenset({"i", "j", "value"})
_LAMBDA_ALLOWED: Final = _LAMBDA_REQUIRED | {"provenance"}

_DIMENSIONLESS: Final = ("1", "dimensionless")
#: The eleven parameters, in this order, with the (unit, kind) each must state (spec §5.1).
_PARAMETERS: Final[Mapping[str, tuple[str, str]]] = {
    **{f"ideal_gas_cp_b{k}": _DIMENSIONLESS for k in range(5)},
    "standard_formation_enthalpy": ("J/mol", "molar_enthalpy"),
    **{f"vapour_pressure_{c}": _DIMENSIONLESS for c in "abcd"},
}


class RecordError(ValueError):
    """A record file off the registration: the message begins with its code and a colon."""


@dataclass(frozen=True)
class WilsonRecords:
    """A record file as the provider reads it: floats exactly as parsed, SI throughout."""

    #: Component ids in the file's order: the identity order of every n-vector.
    components: tuple[str, ...]
    #: b_0..b_4 of c_p^ig/R = Σ_k b_k θ^k, per component (eq. 3.1).
    cp: tuple[tuple[float, float, float, float, float], ...]
    #: J/mol, h^ig(T₀) per component: the convention's formation datum (eq. 3.2).
    formation_enthalpy: tuple[float, ...]
    #: (a, b, c, d) of ln(P^sat/Pa) = a + b/θ + c ln θ + d θ², per component (eq. 3.3).
    vapour_pressure: tuple[tuple[float, float, float, float], ...]
    #: Λ[i][j] in the components' order, with Λ[i][i] = 1.0 (spec §3.4).
    wilson_lambda: tuple[tuple[float, ...], ...]
    #: K and Pa, inclusive bounds (lo, hi).
    temperature_domain: tuple[float, float]
    pressure_domain: tuple[float, float]
    reference_convention: str
    synthetic: bool
    data_set: str
    uncertainty: str
    data_provenance: str
    #: SHA-256 of the bytes the records were parsed from.
    sha256: str


def _structure(message: str) -> RecordError:
    return RecordError(f"record_structure: {message}")


def _keys(entry: object, required: frozenset[str], allowed: frozenset[str], where: str) -> None:
    if not isinstance(entry, Mapping):
        raise _structure(f"{where} is not a mapping")
    missing, unknown = sorted(required - set(entry)), sorted(set(entry) - allowed)
    if missing or unknown:
        raise _structure(f"{where}: missing keys {missing}, unknown keys {unknown}")


def _number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int | float)


def _parameter(quantity: object, unit: str, kind: str, where: str) -> float:
    if not isinstance(quantity, Mapping) or "value" not in quantity:
        raise _structure(f"{where} is not a quantity with a value")
    if quantity.get("unit") != unit or quantity.get("kind") != kind:
        raise RecordError(
            f"record_units: {where} states unit {quantity.get('unit')!r} and kind "
            f"{quantity.get('kind')!r}; the registration is {unit!r} and {kind!r}"
        )
    value = quantity["value"]
    if not _number(value) or not math.isfinite(value):
        raise _structure(f"{where}: value {value!r} is not a finite number")
    return float(value)


def _bounds(document: Mapping[str, Any]) -> tuple[tuple[float, float], tuple[float, float]]:
    domain = document["domain"]
    if not isinstance(domain, Mapping) or set(domain) != {"T", "P"}:
        raise RecordError(f"record_domain: domain {domain!r} does not name exactly T and P")
    bounds = {}
    for variable in ("T", "P"):
        pair = domain[variable]
        if (
            not isinstance(pair, Sequence)
            or len(pair) != 2
            or not all(_number(v) and math.isfinite(v) for v in pair)
        ):
            raise RecordError(f"record_domain: {variable} {pair!r} is not two finite numbers")
        lo, hi = float(pair[0]), float(pair[1])
        if not lo < hi:
            raise RecordError(f"record_domain: {variable} lower bound {lo!r} >= upper {hi!r}")
        bounds[variable] = (lo, hi)
    if not (T_NASA[0] <= bounds["T"][0] and bounds["T"][1] <= T_NASA[1]):
        raise RecordError(f"record_domain: T {bounds['T']} outside the NASA range {T_NASA} K")
    if not bounds["P"][0] > 0.0:
        raise RecordError(f"record_domain: P lower bound {bounds['P'][0]!r} Pa is not positive")
    return bounds["T"], bounds["P"]


def _lambda(entries: object, ids: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
    if not isinstance(entries, list):
        raise _structure("wilson_lambda is not a list")
    matrix: dict[tuple[str, str], float] = {}
    for position, entry in enumerate(entries):
        _keys(entry, _LAMBDA_REQUIRED, _LAMBDA_ALLOWED, f"wilson_lambda[{position}]")
        assert isinstance(entry, Mapping)
        i, j, value = entry["i"], entry["j"], entry["value"]
        if i not in ids or j not in ids:
            raise RecordError(f"record_lambda: entry ({i!r}, {j!r}) names an unknown component")
        if i == j:
            raise RecordError(f"record_lambda: diagonal entry ({i}, {j}); Lambda_ii = 1 is implied")
        if (i, j) in matrix:
            raise RecordError(f"record_lambda: duplicate entry ({i}, {j})")
        if not _number(value) or not math.isfinite(value) or not value > 0.0:
            raise RecordError(
                f"record_lambda: ({i}, {j}) = {value!r} is not a finite positive number"
            )
        matrix[(i, j)] = float(value)
    missing = [(i, j) for i in ids for j in ids if i != j and (i, j) not in matrix]
    if missing:
        raise RecordError(f"record_lambda: missing entries {missing}")
    return tuple(tuple(1.0 if i == j else matrix[(i, j)] for j in ids) for i in ids)


def parse_records(data: bytes) -> WilsonRecords:
    """The records in `data` (the bytes of a record file in spec §5.1's format), checked."""
    try:
        document = yaml.safe_load(data.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise _structure(f"not a YAML document ({error})") from None
    _keys(document, _TOP_KEYS, _TOP_KEYS, "the file")
    if document["schema_version"] != 1 or isinstance(document["schema_version"], bool):
        raise _structure(f"schema_version {document['schema_version']!r} is not 1")
    for key in ("record_schema", "data_set", "uncertainty", "data_provenance"):
        if not isinstance(document[key], str):
            raise _structure(f"{key} is not a string")
    convention, synthetic = document["reference_convention"], document["synthetic"]
    if convention not in CONVENTIONS or synthetic is not CONVENTIONS[convention]:
        raise RecordError(
            f"record_convention: reference_convention {convention!r} with synthetic "
            f"{synthetic!r} is not one of {dict(CONVENTIONS)}"
        )
    records = document["components"]
    if not isinstance(records, list) or not records:
        raise _structure("components is not a non-empty list")
    ids: list[str] = []
    cp: list[tuple[float, float, float, float, float]] = []
    formation: list[float] = []
    psat: list[tuple[float, float, float, float]] = []
    for position, record in enumerate(records):
        _keys(record, _COMPONENT_REQUIRED, _COMPONENT_ALLOWED, f"components[{position}]")
        cid = record["id"]
        if not isinstance(cid, str) or cid in ids:
            raise _structure(f"components[{position}]: id {cid!r} is not a new string")
        ids.append(cid)
        if record["synthetic"] is not synthetic:
            raise RecordError(
                f"record_convention: {cid} has synthetic {record['synthetic']!r}, the file "
                f"{synthetic!r}"
            )
        parameters = record["parameters"]
        _keys(parameters, frozenset(_PARAMETERS), frozenset(_PARAMETERS), f"{cid}.parameters")
        value = {
            name: _parameter(parameters[name], unit, kind, f"{cid}.{name}")
            for name, (unit, kind) in _PARAMETERS.items()
        }
        b0, b1, b2, b3, b4 = (value[f"ideal_gas_cp_b{k}"] for k in range(5))
        cp.append((b0, b1, b2, b3, b4))
        formation.append(value["standard_formation_enthalpy"])
        a, b, c, d = (value[f"vapour_pressure_{name}"] for name in "abcd")
        psat.append((a, b, c, d))
    components = tuple(ids)
    wilson_lambda = _lambda(document["wilson_lambda"], components)
    temperature, pressure = _bounds(document)
    return WilsonRecords(
        components=components,
        cp=tuple(cp),
        formation_enthalpy=tuple(formation),
        vapour_pressure=tuple(psat),
        wilson_lambda=wilson_lambda,
        temperature_domain=temperature,
        pressure_domain=pressure,
        reference_convention=convention,
        synthetic=synthetic,
        data_set=document["data_set"],
        uncertainty=document["uncertainty"],
        data_provenance=document["data_provenance"],
        sha256=hashlib.sha256(data).hexdigest(),
    )


def _checkout_records() -> Path | None:
    """The repository's real records when this module runs from a source checkout
    (`<root>/src/openflowsheet/thermo/wilson_ig.py`), else `None`."""
    here = Path(__file__).resolve()
    root = here.parents[3]
    if here.parents[1] != root / "src" / "openflowsheet":
        return None
    return root / RECORDS_PATH


def load_records(path: str | os.PathLike[str] | None = None) -> WilsonRecords:
    """The records at `path`; `None` is the real records of a source checkout (spec §5.1).

    A missing file is `records_missing`, an explicit refusal, never a fallback to other data.
    """
    target = _checkout_records() if path is None else Path(path)
    if target is None or not target.is_file():
        where = RECORDS_PATH if target is None else str(target)
        raise RecordError(
            f"records_missing: {where} does not exist (the real records are WO-S10-3's, read "
            "from a source checkout only; R-706)"
        )
    return parse_records(target.read_bytes())


# -- the closed forms (spec §3) -----------------------------------------------------------------


@dataclass(frozen=True)
class _Pure:
    """The pure-component quantities at one temperature, every component (spec §3.1–§3.3)."""

    #: ln(P_i^sat/Pa) and d ln P_i^sat/dT in 1/K (eqs. 3.3, 3.4).
    ln_psat: tuple[float, ...]
    dln_psat_dt: tuple[float, ...]
    #: J/mol: h_i^ig (eq. 3.2) and h_i^0L = h_i^ig − Δh_i (eqs. 3.5, 3.6).
    h_ig: tuple[float, ...]
    h_liquid: tuple[float, ...]
    #: J/(mol K): c_p,i^ig (eq. 3.1) and c_p,i^0L = c_p,i^ig − R (c_i + 6 d_i θ²) (spec §3.3).
    cp_ig: tuple[float, ...]
    cp_liquid: tuple[float, ...]


def _pure(records: WilsonRecords, temperature: float) -> _Pure:
    theta = temperature / T_UNIT
    ln_theta = math.log(theta)
    ln_psat, dln_psat, h_ig, h_liquid, cp_ig, cp_liquid = [], [], [], [], [], []
    for (b0, b1, b2, b3, b4), formation, (a, b, c, d) in zip(
        records.cp, records.formation_enthalpy, records.vapour_pressure, strict=True
    ):
        cp_over_r = b0 + theta * (b1 + theta * (b2 + theta * (b3 + theta * b4)))
        integral = sum(
            bk * (theta ** (k + 1) - THETA_0 ** (k + 1)) / (k + 1)
            for k, bk in enumerate((b0, b1, b2, b3, b4))
        )
        h = formation + R * T_UNIT * integral
        latent = R * T_UNIT * (-b + c * theta + 2.0 * d * theta**3)
        ln_psat.append(a + b / theta + c * ln_theta + d * theta * theta)
        dln_psat.append((-b / (theta * theta) + c / theta + 2.0 * d * theta) / T_UNIT)
        h_ig.append(h)
        h_liquid.append(h - latent)
        cp_ig.append(R * cp_over_r)
        cp_liquid.append(R * cp_over_r - R * (c + 6.0 * d * theta * theta))
    return _Pure(
        ln_psat=tuple(ln_psat),
        dln_psat_dt=tuple(dln_psat),
        h_ig=tuple(h_ig),
        h_liquid=tuple(h_liquid),
        cp_ig=tuple(cp_ig),
        cp_liquid=tuple(cp_liquid),
    )


def _ln_gamma(
    lam: Sequence[Sequence[float]], x: Sequence[float]
) -> tuple[tuple[float, ...], list[float]]:
    """ln γ_i (eq. 3.8) and S_i = Σ_j x_j Λ_ij, at x on the simplex."""
    size = len(x)
    s = [sum(x[j] * lam[i][j] for j in range(size)) for i in range(size)]
    ln_gamma = tuple(
        1.0 - math.log(s[i]) - sum(x[k] * lam[k][i] / s[k] for k in range(size))
        for i in range(size)
    )
    return ln_gamma, s


def _wilson(
    lam: Sequence[Sequence[float]], x: Sequence[float]
) -> tuple[tuple[float, ...], tuple[tuple[float, ...], ...]]:
    """ln γ_i (eq. 3.8) and G_ij = ∂ln γ_i/∂x_j with x free (eq. 3.9), at x on the simplex."""
    size = len(x)
    ln_gamma, s = _ln_gamma(lam, x)
    g = tuple(
        tuple(
            -lam[i][j] / s[i]
            - lam[j][i] / s[j]
            + sum(x[k] * lam[k][i] * lam[k][j] / (s[k] * s[k]) for k in range(size))
            for j in range(size)
        )
        for i in range(size)
    )
    return ln_gamma, g


def _projected(by_x: Sequence[float], x: Sequence[float], total: float) -> tuple[float, ...]:
    """∂X/∂n_j = (∂X/∂x_j − Σ_k x_k ∂X/∂x_k)/n_tot (spec §3.6)."""
    mean = sum(xk * dk for xk, dk in zip(x, by_x, strict=True))
    return tuple((dj - mean) / total for dj in by_x)


# -- the provider --------------------------------------------------------------------------------


class WilsonIdealGasProvider:
    """A `PropertyProvider` on a Wilson liquid and an ideal-gas vapour (`wilson-ig-v1`, ADR 0047).

    It holds its records and the SHA-256 of this module, both read once at construction and never
    changed; every method is a pure function of them and its arguments, so it is declared
    thread-safe.
    """

    def __init__(self, records_path: str | os.PathLike[str] | None = None) -> None:
        self._records = load_records(records_path)
        self._implementation_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        ids = self._records.components
        self._lnphi = tuple(f"lnphi_{c}" for c in ids)
        self._properties = ("h", *self._lnphi)
        self._derivative_inputs = ("T", "P", *(f"n_{c}" for c in ids))

    @property
    def records(self) -> WilsonRecords:
        return self._records

    def describe(self) -> PropertyCapabilities:
        records = self._records
        return PropertyCapabilities(
            provider_id=PROVIDER_ID,
            implementation_sha256=self._implementation_sha256,
            data_sha256=records.sha256,
            reference_convention=records.reference_convention,
            state_definition=STATE_DEFINITION,
            components=records.components,
            phases=("LIQUID", "VAPOR"),
            properties=self._properties,
            flashes=("TP",),
            derivative_order=dict.fromkeys(self._derivative_inputs, 1),
            domain={"T": records.temperature_domain, "P": records.pressure_domain},
            uncertainty=records.uncertainty,
            data_provenance=records.data_provenance,
            thread_safety="thread_safe",
            numerical_limitations=NUMERICAL_LIMITATIONS,
        )

    # -- properties ----------------------------------------------------------------------------

    def _domain_violation(self, state: StreamState) -> str | None:
        """`out_of_domain: ...` when T or P leaves the records' box, or a flow leaves nTP-v1's
        (`pr-c1-v1`'s message forms)."""
        t, p = state.temperature, state.pressure
        (t_lo, t_hi), (p_lo, p_hi) = self._records.temperature_domain, self._records.pressure_domain
        if not (math.isfinite(t) and math.isfinite(p)):
            return f"out_of_domain: non-finite state (T = {t!r} K, P = {p!r} Pa)"
        if not t_lo <= t <= t_hi:
            return f"out_of_domain: temperature {t!r} K outside [{t_lo}, {t_hi}] K"
        if not p_lo <= p <= p_hi:
            return f"out_of_domain: pressure {p!r} Pa outside [{p_lo}, {p_hi}] Pa"
        ids = self._records.components
        bad = [c for c, value in zip(ids, state.n, strict=True) if not value >= 0.0]
        if bad:
            return (
                f"out_of_domain: component flows {bad} are not finite and non-negative "
                "(ADR 0001 D2)"
            )
        if not math.isfinite(state.total_flow):
            return "out_of_domain: the total flow is not finite"
        return None

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        """Values and derivatives of the requested phase at the request's state (spec §5.3)."""
        del context
        convention = self._records.reference_convention
        undeclared = [name for name in request.derivatives if name not in self._derivative_inputs]
        if undeclared:
            return _refused(
                "unsupported", f"undeclared_derivative_input: {undeclared[0]}", convention
            )
        unknown = [name for name in request.properties if name not in self._properties]
        if unknown:
            return _refused("unsupported", f"unknown_property: {unknown}", convention)
        state = request.state
        ids = self._records.components
        if len(state.n) != len(ids):
            return _refused(
                "error", f"state_length: {len(state.n)} flows for the components {ids}", convention
            )
        outside = self._domain_violation(state)
        if outside is not None:
            return _refused("out_of_domain", outside, convention)
        if state.is_dormant:
            return _refused("unsupported", "dormant_state: composition undefined", convention)

        size = len(ids)
        total = state.total_flow
        x = tuple(value / total for value in state.n)
        pure = _pure(self._records, state.temperature)
        liquid = request.phase == "LIQUID"
        # Per property: its value, d/dT, d/dP and d/dx_j with x free (spec §3.5-§3.6).
        rows: dict[str, tuple[float, float, float, tuple[float, ...]]] = {}
        if liquid:
            ln_gamma, g = _wilson(self._records.wilson_lambda, x)
            ln_p = math.log(state.pressure)
            for i, name in enumerate(self._lnphi):
                rows[name] = (
                    ln_gamma[i] + pure.ln_psat[i] - ln_p,
                    pure.dln_psat_dt[i],
                    -1.0 / state.pressure,
                    g[i],
                )
            h_i, cp_i = pure.h_liquid, pure.cp_liquid
        else:
            for name in self._lnphi:
                rows[name] = (0.0, 0.0, 0.0, (0.0,) * size)
            h_i, cp_i = pure.h_ig, pure.cp_ig
        rows["h"] = (
            sum(xi * hi for xi, hi in zip(x, h_i, strict=True)),
            sum(xi * ci for xi, ci in zip(x, cp_i, strict=True)),
            0.0,
            h_i,
        )

        values = {name: rows[name][0] for name in request.properties}
        derivatives: dict[str, dict[str, float]] = {}
        if request.derivatives:
            for name in request.properties:
                value, by_t, by_p, by_x = rows[name]
                identity_zero = not liquid and name != "h"
                by_n = (0.0,) * size if identity_zero else _projected(by_x, x, total)
                entry: dict[str, float] = {}
                for wanted in request.derivatives:
                    if wanted == "T":
                        entry[wanted] = by_t
                    elif wanted == "P":
                        entry[wanted] = by_p
                    else:
                        entry[wanted] = by_n[ids.index(wanted.removeprefix("n_"))]
                derivatives[name] = entry

        return PropertyResult(
            status="ok",
            phase_signature=request.phase,
            values=values,
            derivatives=derivatives,
            provider_id=PROVIDER_ID,
            reference_convention=convention,
        )

    # -- flash ---------------------------------------------------------------------------------

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        """The TP flash `S10-tp-flash-v1` (spec §5.4): the closed-form vapour trial, the liquid
        trial by successive substitution, then the two-phase successive substitution.

        By the strict convexity of both phase models (spec §4.1), a single phase whose other-model
        trial distance is ≥ −EPS_TPD and a converged two-phase split with 0 < β < 1 are global
        within the model, so every `ok` result is labelled `STABLE_WITHIN_TESTED_SCOPE` in
        `message`. A loop that reaches its cap, or a split without a Rachford–Rice bracket or with
        β ∉ (0, 1), is `not_converged` with label `UNKNOWN` and no outlets: never a split.
        """
        del context
        convention = self._records.reference_convention
        if request.specification != "TP":
            return _flash_refused(
                "unsupported",
                f"unsupported_specification: {request.specification!r}; "
                f"{PROVIDER_ID} offers TP only",
                convention,
            )
        if request.derivatives:
            return _flash_refused(
                "unsupported",
                f"flash_derivatives_unsupported: {list(request.derivatives)}; "
                "FlashResult carries no derivatives",
                convention,
            )
        state = request.state
        ids = self._records.components
        if len(state.n) != len(ids):
            return _flash_refused(
                "error", f"state_length: {len(state.n)} flows for the components {ids}", convention
            )
        outside = self._domain_violation(state)
        if outside is not None:
            return _flash_refused("out_of_domain", outside, convention)
        t, p = state.temperature, state.pressure
        if state.is_dormant:
            # Step 0.5 (ADR 0001 D3.4): two dormant outlets at T and P; a result, not a failure.
            dormant = StreamState(n=(0.0,) * len(ids), temperature=t, pressure=p)
            return FlashResult(
                status="ok",
                phase_signature="ZERO_FLOW",
                vapor_fraction=None,
                vapor=dormant,
                liquid=dormant,
                provider_id=PROVIDER_ID,
                reference_convention=convention,
                message=_unknown("dormant_state: composition undefined (ADR 0001 D3.1, D3.4)"),
            )

        search = _Search(self._records, state)
        tm_vapour, _ = search.vapour_trial()  # step 2
        if tm_vapour >= -EPS_TPD:
            return self._single_phase(
                state,
                "LIQUID",
                0,
                f"{_STABLE}; tm_vapour_trial: {tm_vapour!r}; tm_liquid_trial: not_evaluated",
            )
        trial = search.liquid_trial()  # step 3
        if trial.tm is None:
            return _flash_not_converged(
                _unknown(f"stability_not_converged: {_cap_text('liquid-trial', trial)}"),
                trial.iterations,
                convention,
            )
        if trial.tm >= -EPS_TPD:
            return self._single_phase(
                state,
                "VAPOR",
                trial.iterations,
                f"{_STABLE}; tm_vapour_trial: {tm_vapour!r}; tm_liquid_trial: {trial.tm!r}",
            )
        assert trial.ln_k is not None  # a converged trial carries ln K at its final w
        split = search.two_phase(trial.ln_k)  # step 4
        iterations = trial.iterations + split.iterations
        if split.failure is not None:
            return _flash_not_converged(
                _unknown(f"two_phase_not_converged: {split.failure}"), iterations, convention
            )
        total = state.total_flow
        beta = split.beta
        return FlashResult(
            status="ok",
            phase_signature="TWO_PHASE",
            vapor_fraction=beta,
            vapor=StreamState(
                n=tuple(beta * total * yi for yi in split.y), temperature=t, pressure=p
            ),
            liquid=StreamState(
                n=tuple((1.0 - beta) * total * xi for xi in split.x), temperature=t, pressure=p
            ),
            k_values=dict(zip(ids, split.k, strict=True)),
            iterations=iterations,
            provider_id=PROVIDER_ID,
            reference_convention=convention,
            message=(
                f"{_STABLE}; tm_vapour_trial: {tm_vapour!r}; tm_liquid_trial: {trial.tm!r}; "
                f"fugacity_residual: {split.residual!r}"
            ),
        )

    def _single_phase(
        self, state: StreamState, phase: Phase, iterations: int, message: str
    ) -> FlashResult:
        """The feed, bitwise, in `phase`; the other outlet dormant at the same T and P; no K-value
        (spec §5.4 steps 2 and 3)."""
        dormant = StreamState(
            n=(0.0,) * len(state.n), temperature=state.temperature, pressure=state.pressure
        )
        liquid = phase == "LIQUID"
        return FlashResult(
            status="ok",
            phase_signature=phase,
            vapor_fraction=0.0 if liquid else 1.0,
            vapor=dormant if liquid else state,
            liquid=state if liquid else dormant,
            iterations=iterations,
            provider_id=PROVIDER_ID,
            reference_convention=self._records.reference_convention,
            message=message,
        )

    # -- stability (outside the frozen Protocol, ADR 0047 C1) ----------------------------------

    def stability(
        self, state: StreamState, phase: Phase, context: EvaluationContext
    ) -> StabilityReport:
        """Judge `state` as `phase` against the other phase model's trials (spec §5.5).

        As LIQUID: the closed-form vapour trial (spec §5.4 step 2). As VAPOR: the liquid trial
        (step 3). STABLE_WITHIN_TESTED_SCOPE if the distance is ≥ −EPS_TPD, else UNSTABLE; UNKNOWN
        with a reason for a wrong length, an out-of-domain or dormant state, an unknown phase, or a
        liquid trial that reached its cap. It reports and never raises.
        """
        del context
        if phase not in ("LIQUID", "VAPOR"):
            return _report_unknown(
                phase, f"unsupported_phase: {phase!r}; {PROVIDER_ID} judges LIQUID or VAPOR"
            )
        ids = self._records.components
        if len(state.n) != len(ids):
            return _report_unknown(
                phase, f"state_length: {len(state.n)} flows for the components {ids}"
            )
        outside = self._domain_violation(state)
        if outside is not None:
            return _report_unknown(phase, outside)
        if state.is_dormant:
            return _report_unknown(phase, "dormant_state: composition undefined")

        search = _Search(self._records, state)
        if phase == "LIQUID":
            tm, ln_k = search.vapour_trial()
            weights = [
                search.z[i] * math.exp(ln_k[i]) if i in search.flowing else 0.0
                for i in range(len(ids))
            ]
            total = sum(weights)
            return StabilityReport(
                label=_label(tm),
                scope=SCOPE,
                phase=phase,
                tm={"VAPOR": tm, "LIQUID": None},
                trial_composition=tuple(wi / total for wi in weights),
                iterations=0,
                residual=None,
                epsilon=EPS_TPD,
                reason="",
            )
        trial = search.liquid_trial()
        if trial.tm is None:
            return StabilityReport(
                label="UNKNOWN",
                scope=SCOPE,
                phase=phase,
                tm={"VAPOR": None, "LIQUID": None},
                trial_composition=None,
                iterations=trial.iterations,
                residual=trial.residual,
                epsilon=EPS_TPD,
                reason=f"stability_not_converged: {_cap_text('liquid-trial', trial)}",
            )
        return StabilityReport(
            label=_label(trial.tm),
            scope=SCOPE,
            phase=phase,
            tm={"VAPOR": None, "LIQUID": trial.tm},
            trial_composition=trial.w,
            iterations=trial.iterations,
            residual=trial.residual,
            epsilon=EPS_TPD,
            reason="",
        )


# -- the flash and the stability search (spec §5.4-§5.5) -----------------------------------------

_STABLE: Final = f"stability: STABLE_WITHIN_TESTED_SCOPE; scope: {SCOPE}"


def _unknown(reason: str) -> str:
    """The message of a flash whose label is UNKNOWN (spec §5.4)."""
    return f"stability: UNKNOWN; scope: {SCOPE}; reason: {reason}"


def _label(tm: float) -> StabilityLabel:
    return "STABLE_WITHIN_TESTED_SCOPE" if tm >= -EPS_TPD else "UNSTABLE"


def _cap_text(loop: str, trial: _LiquidTrial) -> str:
    return (
        f"{loop} successive substitution reached its cap of {trial.iterations} iterations "
        f"(last step {trial.residual!r} > {DELTA_SS!r})"
    )


@dataclass(frozen=True)
class _LiquidTrial:
    """The liquid trial against a vapour of the feed composition (spec §5.4 step 3).

    `tm`, `w` and `ln_k` are None when the loop reached its cap without its stop.
    """

    iterations: int
    #: The last step max_{i∈F} |ln W'_i − ln W_i|.
    residual: float
    tm: float | None
    #: w = W/ΣW of the final W (0.0 for absent components) and ln K_i(w), every component.
    w: tuple[float, ...] | None
    ln_k: tuple[float, ...] | None


@dataclass(frozen=True)
class _Split:
    """The two-phase successive substitution (spec §5.4 step 4). `failure` is None on a converged
    split with 0 < β < 1, and otherwise says why there is none."""

    iterations: int
    failure: str | None
    beta: float = math.nan
    x: tuple[float, ...] = ()
    y: tuple[float, ...] = ()
    #: K_i for i ∈ F (the K of the stopping Rachford–Rice solve), K_i(x) for i ∉ F.
    k: tuple[float, ...] = ()
    #: The last step max_{i∈F} |ln K'_i − ln K_i|.
    residual: float = math.nan


class _Search:
    """The trials and the split at one non-dormant, in-domain state of known length."""

    def __init__(self, records: WilsonRecords, state: StreamState) -> None:
        self._lam = records.wilson_lambda
        self._size = len(state.n)
        total = state.total_flow
        self.z = tuple(value / total for value in state.n)  # step 1
        # F on z, not n: an n_i < 2^-1075 n_tot underflows to z_i = 0.0 (spec §14 E-1).
        self.flowing = tuple(i for i, value in enumerate(self.z) if value > 0.0)
        self._ln_z = {i: math.log(self.z[i]) for i in self.flowing}
        self._ln_psat = _pure(records, state.temperature).ln_psat
        self._ln_p = math.log(state.pressure)

    def ln_k(self, x: Sequence[float]) -> tuple[float, ...]:
        """ln K_i(x) = ln γ_i(x) + ln P_i^sat − ln P, every component (eq. 3.10)."""
        ln_gamma, _ = _ln_gamma(self._lam, x)
        return tuple(g + s - self._ln_p for g, s in zip(ln_gamma, self._ln_psat, strict=True))

    def _full(self, values: Mapping[int, float]) -> tuple[float, ...]:
        return tuple(values.get(i, 0.0) for i in range(self._size))

    def vapour_trial(self) -> tuple[float, tuple[float, ...]]:
        """tm_V = 1 − Σ_{i∈F} z_i K_i(z), and ln K(z) (step 2, closed form)."""
        ln_k = self.ln_k(self.z)
        return 1.0 - sum(self.z[i] * math.exp(ln_k[i]) for i in self.flowing), ln_k

    def liquid_trial(self) -> _LiquidTrial:
        """W_i = z_i/K_i(w), w = W/ΣW, from W = z/K(z), to max |Δ ln W| ≤ DELTA_SS (step 3).

        W is carried as ln W = ln z − ln K(w), the logarithm of the spec's W'_i = z_i/K_i(w).
        """
        flowing, ln_z = self.flowing, self._ln_z
        start = self.ln_k(self.z)
        ln_w = {i: ln_z[i] - start[i] for i in flowing}
        step = math.inf
        for m in range(1, SS_MAX + 1):
            ln_k = self.ln_k(self._normalised(ln_w))
            new = {i: ln_z[i] - ln_k[i] for i in flowing}
            step = max(abs(new[i] - ln_w[i]) for i in flowing)
            ln_w = new
            if step <= DELTA_SS:
                # tm at w = W/ΣW of the final W: second-order in the error of W, unlike 1 − ΣW.
                w = self._normalised(ln_w)
                ln_k = self.ln_k(w)
                tm = 1.0 + sum(
                    math.exp(ln_w[i]) * (ln_w[i] + ln_k[i] - ln_z[i] - 1.0) for i in flowing
                )
                return _LiquidTrial(m, step, tm, w, ln_k)
        return _LiquidTrial(SS_MAX, step, None, None, None)

    def _normalised(self, ln_w: Mapping[int, float]) -> tuple[float, ...]:
        weights = {i: math.exp(value) for i, value in ln_w.items()}
        total = sum(weights.values())
        return self._full({i: value / total for i, value in weights.items()})

    def two_phase(self, ln_k_start: Sequence[float]) -> _Split:
        """Rachford–Rice and K_i = K_i(x) by successive substitution to max |Δ ln K| ≤ DELTA_K,
        from K = K(w) of the liquid trial (step 4)."""
        flowing, z = self.flowing, self.z
        ln_k = {i: ln_k_start[i] for i in flowing}
        step = math.inf
        for m in range(1, SS_MAX_TWO_PHASE + 1):
            k = {i: math.exp(ln_k[i]) for i in flowing}
            k_max, k_min = max(k.values()), min(k.values())
            if not k_max > 1.0 > k_min:  # (a)
                return _Split(
                    m,
                    f"no Rachford-Rice bracket (K_max = {k_max!r}, K_min = {k_min!r} over the "
                    "flowing components)",
                )
            beta = _rachford_rice([z[i] for i in flowing], [k[i] for i in flowing])
            x = {i: z[i] / (1.0 + beta * (k[i] - 1.0)) for i in flowing}  # (b)
            y = {i: k[i] * x[i] for i in flowing}
            x_total, y_total = sum(x.values()), sum(y.values())
            x_full = self._full({i: value / x_total for i, value in x.items()})
            y_full = self._full({i: value / y_total for i, value in y.items()})
            ln_k_new = self.ln_k(x_full)  # (c)
            step = max(abs(ln_k_new[i] - ln_k[i]) for i in flowing)
            if step <= DELTA_K:
                if not 0.0 < beta < 1.0:
                    return _Split(m, f"vapour fraction {beta!r} outside (0, 1)")
                k_out = tuple(k[i] if i in k else math.exp(ln_k_new[i]) for i in range(self._size))
                return _Split(m, None, beta, x_full, y_full, k_out, step)
            ln_k = {i: ln_k_new[i] for i in flowing}
        return _Split(
            SS_MAX_TWO_PHASE,
            f"two-phase successive substitution reached its cap of {SS_MAX_TWO_PHASE} iterations "
            f"(last step {step!r} > {DELTA_K!r})",
        )


def _rachford_rice(z: Sequence[float], k: Sequence[float]) -> float:
    """β with Σ z_i (K_i − 1)/(1 + β(K_i − 1)) = 0 on (1/(1 − K_max), 1/(1 − K_min)), K_max > 1 >
    K_min (spec §5.4 step 4a): bisection with safeguarded Newton, from β = 0.5, until the bracket
    is ≤ 4 ulp(β) wide or f(β) = 0.

    f is strictly decreasing on the bracket, so its sign at each iterate moves one end. A Newton
    step is taken when it lands strictly inside the bracket and moves β; otherwise, and whenever two
    Newton steps have not halved the bracket, the step is the midpoint. The bracket therefore at
    least halves every three iterations, so the loop ends.
    """
    lo, hi = 1.0 / (1.0 - max(k)), 1.0 / (1.0 - min(k))
    beta = 0.5
    reference = hi - lo
    newton_left = 2
    while True:
        f = slope = 0.0
        for zi, ki in zip(z, k, strict=True):
            d = ki - 1.0
            denominator = 1.0 + beta * d
            term = zi * d / denominator
            f += term
            slope -= term * d / denominator
        if f == 0.0:
            return beta
        if f > 0.0:
            lo = beta
        else:
            hi = beta
        if hi - lo <= 4.0 * math.ulp(beta):
            return beta
        if hi - lo <= 0.5 * reference:
            reference, newton_left = hi - lo, 2
        candidate = beta - f / slope
        if newton_left > 0 and lo < candidate < hi and candidate != beta:
            newton_left -= 1
            beta = candidate
        else:
            newton_left = 2
            beta = lo + 0.5 * (hi - lo)


def _flash_refused(status: PropertyStatus, message: str, convention: str) -> FlashResult:
    """A typed flash refusal: no outlets, no vapour fraction (spec §5.4 step 0)."""
    return FlashResult(
        status=status,
        phase_signature=None,
        vapor_fraction=None,
        vapor=None,
        liquid=None,
        provider_id=PROVIDER_ID,
        reference_convention=convention,
        message=message,
    )


def _flash_not_converged(message: str, iterations: int, convention: str) -> FlashResult:
    """A search that reached its cap or has no split: label UNKNOWN, no outlets (spec §5.4)."""
    return FlashResult(
        status="not_converged",
        phase_signature=None,
        vapor_fraction=None,
        vapor=None,
        liquid=None,
        iterations=iterations,
        provider_id=PROVIDER_ID,
        reference_convention=convention,
        message=message,
    )


def _report_unknown(phase: Phase, reason: str) -> StabilityReport:
    """UNKNOWN before any trial ran (spec §5.5): no distance, no trial composition."""
    return StabilityReport(
        label="UNKNOWN",
        scope=SCOPE,
        phase=phase,
        tm={"VAPOR": None, "LIQUID": None},
        trial_composition=None,
        iterations=0,
        residual=None,
        epsilon=EPS_TPD,
        reason=reason,
    )


#: Spec §5.7, verbatim.
NUMERICAL_LIMITATIONS: Final[tuple[str, ...]] = (
    "Gamma-phi with a Wilson liquid (constant Lambda) and an ideal-gas vapour; no Poynting factor; "
    "h^E = 0; no liquid volume (v is not offered).",
    "One liquid phase only: the Wilson liquid cannot split (strict convexity, S10 spec section "
    "4.1); no LLE, and no statement that the real mixture has none.",
    "Stability: STABLE_WITHIN_TESTED_SCOPE is global within the model (one Wilson liquid, one "
    "ideal gas) at resolution 1e-10 in the tangent-plane distance; scope S10-tpd-v1.",
    "TP flash only; a flash that asks for derivatives is refused; PH flash is not a provider "
    "capability (FlashRequest carries no enthalpy).",
    "Successive substitution capped at 1000 iterations per loop; reaching the cap returns "
    "not_converged with stability UNKNOWN, never a split.",
)


def _refused(status: PropertyStatus, message: str, convention: str) -> PropertyResult:
    """A typed refusal: no phase signature, no values (spec §5.3)."""
    return PropertyResult(
        status=status,
        phase_signature=None,
        values={},
        provider_id=PROVIDER_ID,
        reference_convention=convention,
        message=message,
    )
