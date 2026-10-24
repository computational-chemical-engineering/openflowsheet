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

**The records are data, read at run time, never transcribed into code** (spec §5.1). The real
records are `benchmarks/s10/records.yaml`, read from a source checkout only: they are not package
data until their rights are vetted and Frank decides (R-706). Before WO-S10-3 the file does not
exist and construction refuses with `RecordError("records_missing: …")`. Any other record file of
the same format (the verification records, `benchmarks/s10/verification-records.yaml`) is passed
by path. `parse_records` refuses a file off the registration with a `RecordError` whose message
begins with one of the codes `record_structure`, `record_units`, `record_convention`,
`record_lambda`, `record_domain`, and hands over the parsed floats unchanged (S10.A02: bitwise).
`data_sha256` is the SHA-256 of the file's bytes; `implementation_sha256` that of this module's
source, which holds the loader, the closed forms, and (WO-S10-2) the flash and the stability search.

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
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
    PropertyStatus,
    StreamState,
)

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
        """The TP flash `S10-tp-flash-v1` (spec §5.4) is WO-S10-2's; until then every flash is
        refused `unsupported`, never answered."""
        del request, context
        return FlashResult(
            status="unsupported",
            phase_signature=None,
            vapor_fraction=None,
            vapor=None,
            liquid=None,
            provider_id=PROVIDER_ID,
            reference_convention=self._records.reference_convention,
            message="flash_not_implemented: the TP flash S10-tp-flash-v1 is WO-S10-2's",
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
