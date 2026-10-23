"""`coolprop-heos-v1`: pure fluids on CoolProp 8.0.0's Helmholtz equations of state (S07 spec,
ADR 0046).

**CoolProp is a Helmholtz evaluator only** (spec §4, R-621). Each instance holds one
`AbstractState("HEOS", <name>)` with the gas phase imposed once; an evaluation is
`update(DmolarT_INPUTS, ρ, T)` followed by the twenty partial getters of α° and αʳ, nothing else.
CoolProp's own flashes, phase determination, reference-state and configuration calls are never
made (spec A27). Every density root, saturation state, property and (T, P) derivative is this
module's, from those partials, so the residual and derivative paths describe the same function at
the same state.

**The algorithms are S05's, generalized over a fluid record** (spec §3.1, §6.3; ADR 0046 D6).
`iapws95.py`'s `_saturation`, `_bracketed_density`, `_metastable_density`, `_density` and `_rule`
are re-implemented here over the constants of `_coolprop_heos_fluids.py` (spec §16.8), with spec
§6.3's substitutions: 647.0 K → T_σ,max, the S05 box → the fluid's near-critical box, 1250 kg/m³ →
ρ_max, the domain → the fluid's box. The convergence rule is S05's (4ε on the relative Newton
correction, or the residual floor; R-595). This module contains no fluid name or component id: every
per-fluid value comes from the table (spec §16.8, A33(c)).

**Saturation seeds** (spec §6.3). The Maxwell solve is seeded by the saturation ancillaries
CoolProp ships inside the fluid JSON (`ANCILLARIES` → `pS`, `rhoL`, `rhoV`), read from the same
JSON string whose canonical hash the guard has just checked (G3), never from any other CoolProp
call. Their forms are CoolProp 8.0.0's `SaturationAncillaryFunction`: the exponential kind
(`pL`, `pV`, `rhoV`) gives y = y_r·exp(f·Σ nᵢθ^{tᵢ}) with f = T_r/T when `using_tau_r` and 1
otherwise, the `rhoLnoexp` kind y = y_r·(1 + Σ nᵢθ^{tᵢ}). One change is made: θ = 1 − T/T_c with
the EOS's critical temperature (spec §6.1) in place of the ancillary's own T_r, so that θ > 0 on
all of (T_lo, T_c), where the saturation is needed (the strip below T_c included); for some fluids
T_r < T_c (O2: 154.581 K against 154.599 K). A seed sets the iteration count, never the converged
value, which is judged by Maxwell's conditions alone. A fluid whose ancillary is of another kind is
refused `saturation_not_converged` with the kind named.

**The guard** (spec §5.2). At an instance's first evaluation: CoolProp importable (G1), the pinned
version and gitrevision (G2), the fluid JSON's canonical hash (G3), and the four canary values from
the instance's fresh `AbstractState` (G4). The outcome is cached for the instance. Measured for
spec §11 Q-3 (WO-S07-2a, A26(c)): a `set_reference_state` after the first evaluation leaves an
existing state's α° bitwise unchanged, so G4 runs once.

**The reference convention is `COOLPROP-DEF-ref-v1`** (spec §3.5): each fluid's α° exactly as its
pinned JSON gives it. It is not a formation datum, and it never mixes with another convention.

**Every refusal is typed** (spec §6.5): a status and a `message` that begins with the reason code
and a colon. No refusal carries values.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path
from typing import Any, Final

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
from openflowsheet.thermo import _coolprop_heos_fluids as _table
from openflowsheet.thermo.iapws95 import PhiJet

PROVIDER_ID: Final = "coolprop-heos-v1"
REFERENCE_CONVENTION: Final = "COOLPROP-DEF-ref-v1"
STATE_DEFINITION: Final = "nTP-v1"

#: The one CoolProp this provider evaluates under (spec §5.1, R-619).
PINNED_COOLPROP_VERSION: Final = "8.0.0"
PINNED_COOLPROP_GITREVISION: Final = "ae81610e7d23efc57f9d051c8e70a4d66e87537f"

#: Per admitted component id, the SHA-256 of its canonical fluid JSON (spec §5.1, A01).
FLUID_DATA_SHA256: Final[dict[str, str]] = {
    row["id"]: row["fluid_data_sha256"] for row in _table.FLUIDS
}

#: Newton's declared iteration bound and its convergence rule: relative steps ≤ 4ε, as S05.
MAX_ITERATIONS: Final = 50
STEP_TOLERANCE: Final = 4.0 * 2.0**-52
#: √ε: the onset of S05's residual-floor clause (R-595).
FLOOR_ONSET: Final = 2.0**-26
#: Entries of each instance's saturation cache, keyed on the exact double T (S05 §10 Q-3).
SATURATION_CACHE_SIZE: Final = 1024
#: G4's bound (spec §5.2): |Δ| ≤ 1e-12·max(|ref|, 1).
CANARY_TOLERANCE: Final = 1e-12

_SATURATION_PROPERTIES: Final[tuple[str, ...]] = ("Psat", "Tsat")
_NOT_CONVERGED_SAT: Final = "saturation_not_converged"


def _converged(step: float, previous: float) -> bool:
    """S05's rule (R-595) on two consecutive relative Newton corrections: `step` ≤ 4ε, or, at the
    residual floor, `previous` ≤ √ε and `previous` ≤ `step` ≤ √ε. The caller passes
    `previous = inf` after a bisection step."""
    return step <= STEP_TOLERANCE or previous <= step <= FLOOR_ONSET


class CoolPropUnavailable(RuntimeError):  # noqa: N818 - the name is spec §3.3's
    """`helmholtz_jet`'s guard failure (spec §3.3); `code` is the §5.2 refusal code."""

    def __init__(self, refusal: str) -> None:
        super().__init__(refusal)
        self.code = refusal.split(":", 1)[0]


class _EvaluationError(RuntimeError):
    """CoolProp raised during an evaluation; the message is the `coolprop_evaluation_failed:`
    refusal (spec §4, §6.5 row 11)."""


# -- the fluid record (spec §6.1, §16.8) ----------------------------------------------------------


@dataclass(frozen=True)
class _Fluid:
    """One row of `_coolprop_heos_fluids.FLUIDS`, under lower-case names."""

    component: str
    name: str
    cas: str
    tier: str
    bound: str
    bibtex_eos: str
    r: float
    m: float
    t_red: float
    rho_red: float
    t_c: float
    p_c: float
    rho_c: float
    t_lo: float
    t_hi: float
    p_lo: float
    p_hi: float
    t_sigma_max: float
    eps_sigma: float
    rho_max: float
    nc_t: tuple[float, float]
    nc_p: tuple[float, float]
    canary: dict[str, float]
    fluid_data_sha256: str
    verification: str
    limitations: tuple[str, ...]

    @classmethod
    def of(cls, row: dict[str, Any]) -> _Fluid:
        return cls(
            component=row["id"],
            name=row["name"],
            cas=row["cas"],
            tier=row["tier"],
            bound=row["bound"],
            bibtex_eos=row["bibtex_eos"],
            r=row["R"],
            m=row["M"],
            t_red=row["T_red"],
            rho_red=row["rho_red"],
            t_c=row["T_c"],
            p_c=row["p_c"],
            rho_c=row["rho_c"],
            t_lo=row["T_lo"],
            t_hi=row["T_hi"],
            p_lo=row["P_lo"],
            p_hi=row["P_hi"],
            t_sigma_max=row["T_sigma_max"],
            eps_sigma=row["eps_sigma"],
            rho_max=row["rho_max"],
            nc_t=tuple(row["nc_T"]),
            nc_p=tuple(row["nc_P"]),
            canary=dict(row["canary"]),
            fluid_data_sha256=row["fluid_data_sha256"],
            verification=row["verification"],
            limitations=tuple(row["limitations"]),
        )


_ROWS: Final[dict[str, dict[str, Any]]] = {row["id"]: row for row in _table.FLUIDS}


def _would_be_id(name: str) -> str:
    """Spec §16.3's id rule for a CoolProp name: `(` → `_`, `)` deleted."""
    return name.replace("(", "_").replace(")", "")


def _exclusion(component_id: str) -> str | None:
    for name, reason in _table.EXCLUDED.items():
        if component_id in (name, _would_be_id(name)):
            return f"{name}: {reason}"
    return None


# -- identity (spec §5.1, §16.9) -------------------------------------------------------------------


def _canonical(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fluid_json(library: Any, name: str) -> Any:
    return json.loads(library.get_fluid_param_string(name, "JSON"))


def fluid_data_sha256(name: str) -> str:
    """SHA-256 of the canonical re-serialization of CoolProp's fluid JSON (spec §5.1). Needs
    CoolProp."""
    library = importlib.import_module("CoolProp.CoolProp")
    return _sha256(_canonical(_fluid_json(library, name)))


@cache
def _implementation_sha256() -> str:
    here = Path(__file__)
    return _sha256(
        _canonical(
            {
                "module_sha256": hashlib.sha256(here.read_bytes()).hexdigest(),
                "fluid_table_sha256": hashlib.sha256(
                    (here.parent / "_coolprop_heos_fluids.py").read_bytes()
                ).hexdigest(),
                "coolprop_version": PINNED_COOLPROP_VERSION,
                "coolprop_gitrevision": PINNED_COOLPROP_GITREVISION,
            }
        )
    )


def _data_sha256(fluid: _Fluid) -> str:
    return _sha256(
        _canonical(
            {
                "coolprop_version": PINNED_COOLPROP_VERSION,
                "fluid": fluid.name,
                "fluid_data_sha256": fluid.fluid_data_sha256,
            }
        )
    )


# -- saturation ancillaries: seeds only (module docstring) -----------------------------------------


@dataclass(frozen=True)
class _Ancillary:
    """One of CoolProp's `SaturationAncillaryFunction`s, θ taken against the EOS's T_c."""

    exponential: bool
    using_tau_r: bool
    reducing_value: float
    t_r: float
    terms: tuple[tuple[float, float], ...]

    @classmethod
    def of(cls, data: dict[str, Any]) -> _Ancillary:
        kind = data.get("type")
        if kind not in ("pL", "pV", "rhoV", "rhoLnoexp"):
            raise ValueError(f"ancillary kind {kind!r} is not one of pL, pV, rhoV, rhoLnoexp")
        return cls(
            exponential=kind != "rhoLnoexp",
            using_tau_r=bool(data.get("using_tau_r", False)),
            reducing_value=float(data["reducing_value"]),
            t_r=float(data["T_r"]),
            terms=tuple(zip(map(float, data["n"]), map(float, data["t"]), strict=True)),
        )

    def __call__(self, temperature: float, t_c: float) -> float:
        theta = 1.0 - temperature / t_c
        summer = math.fsum(n * theta**t for n, t in self.terms)
        if not self.exponential:
            return self.reducing_value * (1.0 + summer)
        factor = self.t_r / temperature if self.using_tau_r else 1.0
        return self.reducing_value * math.exp(factor * summer)


@dataclass(frozen=True)
class _Seeds:
    pressure: _Ancillary
    rho_l: _Ancillary
    rho_v: _Ancillary


# -- states ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Saturation:
    """The converged coexisting densities at T and p_σ = p(ρ'', T)."""

    temperature: float
    rho_l: float
    rho_v: float
    pressure: float
    iterations: int


@dataclass(frozen=True)
class _Rule:
    """The phases S05 §4.2 answers at (T, P), and the saturation it used (T < T_c)."""

    answered: tuple[Phase, ...]
    saturation: _Saturation | None
    route: str


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

    def log(self) -> _Dual:
        return _Dual(math.log(self.v), self.d / self.v, self.t / self.v)


#: Property id -> (value, d/dT at constant P, d/dP at constant T).
_Answer = dict[str, tuple[float, float, float]]

_UNSET: Final = "unset"


# -- the provider ----------------------------------------------------------------------------------


class CoolPropHeosProvider:
    """A `PropertyProvider` for one pure fluid on its CoolProp HEOS equation (`coolprop-heos-v1`).

    One instance serves one fluid and holds one CoolProp `AbstractState`, so it is declared not
    thread-safe (spec §3.2). Constructing never fails for an admitted id and loads nothing from
    CoolProp; the guard runs at the first evaluation (spec §5.2).
    """

    def __init__(self, component_id: str) -> None:
        row = _ROWS.get(component_id)
        if row is None:
            reason = _exclusion(component_id)
            if reason is not None:
                raise ValueError(f"{component_id!r} is excluded from {PROVIDER_ID}: {reason}")
            raise ValueError(f"{component_id!r} is not a component id of {PROVIDER_ID}")
        self._fluid = _Fluid.of(row)
        self._outcome: str | None = _UNSET
        self._state: Any = None
        self._inputs: Any = None
        self._seeds: _Seeds | None = None
        self._seed_error: str | None = None
        self._saturation = lru_cache(maxsize=SATURATION_CACHE_SIZE)(self._solve_saturation)
        self._bounds: tuple[float, float] | None = None

    @classmethod
    def admitted(cls) -> tuple[dict[str, Any], ...]:
        """The admitted fluids in the table's order (spec §16.8, A33)."""
        return tuple(
            {key: row[key] for key in ("id", "name", "cas", "tier", "bound")}
            for row in _table.FLUIDS
        )

    @classmethod
    def excluded(cls) -> dict[str, str]:
        """CoolProp name → the reason it is excluded (spec §16.8, A33)."""
        return dict(_table.EXCLUDED)

    # -- names -------------------------------------------------------------------------------------

    @property
    def _lnphi(self) -> str:
        return f"lnphi_{self._fluid.component}"

    @property
    def _phase_properties(self) -> tuple[str, ...]:
        return ("h", "s", "v", "Z", "cp", self._lnphi)

    @property
    def _derivative_inputs(self) -> tuple[str, ...]:
        return ("T", "P", f"n_{self._fluid.component}")

    # -- the guard (spec §5.2) ---------------------------------------------------------------------

    def _guard(self) -> str | None:
        """`None` when G1-G4 pass, else the refusal; run once, cached for the instance."""
        if self._outcome == _UNSET:
            self._outcome = self._run_guard()
        return self._outcome

    def _run_guard(self) -> str | None:
        fluid = self._fluid
        try:
            coolprop = importlib.import_module("CoolProp")
            library = importlib.import_module("CoolProp.CoolProp")
        except ImportError as error:
            return f"coolprop_unavailable: import CoolProp failed ({error})"
        try:
            installed = (coolprop.__version__, library.get_global_param_string("gitrevision"))
        except Exception as error:  # any failure here is G2's
            return f"coolprop_version_mismatch: the version could not be read ({error!r})"
        pinned = (PINNED_COOLPROP_VERSION, PINNED_COOLPROP_GITREVISION)
        if installed != pinned:
            return f"coolprop_version_mismatch: installed {installed}, pinned {pinned}"
        try:
            document = _fluid_json(library, fluid.name)
            digest = _sha256(_canonical(document))
        except Exception as error:  # any failure here is G3's
            return f"coolprop_data_mismatch: the {fluid.name} JSON could not be read ({error!r})"
        if digest != fluid.fluid_data_sha256:
            return (
                f"coolprop_data_mismatch: {fluid.name} JSON hashes to {digest}, pinned "
                f"{fluid.fluid_data_sha256}"
            )
        try:
            heos = library.AbstractState("HEOS", fluid.name)
            heos.specify_phase(library.iphase_gas)
            self._state, self._inputs = heos, library.DmolarT_INPUTS
            canary = fluid.canary
            ideal, residual = self._jet(canary["T"], canary["rho"])
        except Exception as error:  # any failure here is G4's
            self._state = None
            return f"coolprop_state_mutated: the canary could not be evaluated ({error!r})"
        got = {
            "alpha0": ideal.phi,
            "alpha0_t": ideal.t,
            "alphar": residual.phi,
            "alphar_d": residual.d,
        }
        for key, value in got.items():
            expected = canary[key]
            if not abs(value - expected) <= CANARY_TOLERANCE * max(abs(expected), 1.0):
                self._state = None
                return (
                    f"coolprop_state_mutated: {key} at the canary is {value!r}, pinned "
                    f"{expected!r} ({fluid.name}; a changed reference heos or configuration)"
                )
        try:
            ancillaries = document[0]["ANCILLARIES"]
            self._seeds = _Seeds(
                _Ancillary.of(ancillaries["pS"]),
                _Ancillary.of(ancillaries["rhoL"]),
                _Ancillary.of(ancillaries["rhoV"]),
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            self._seed_error = f"no usable saturation ancillary in the {fluid.name} JSON ({error})"
        return None

    # -- the jet (spec §3.3, §4) -------------------------------------------------------------------

    def _jet(self, temperature: float, density: float) -> tuple[PhiJet, PhiJet]:
        """(α°, αʳ) at (T, ρ) from one `update` and the twenty partial getters."""
        heos = self._state
        try:
            heos.update(self._inputs, density, temperature)
            ideal = PhiJet(
                heos.alpha0(),
                heos.dalpha0_dDelta(),
                heos.d2alpha0_dDelta2(),
                heos.dalpha0_dTau(),
                heos.d2alpha0_dTau2(),
                heos.d2alpha0_dDelta_dTau(),
                heos.d3alpha0_dDelta3(),
                heos.d3alpha0_dDelta2_dTau(),
                heos.d3alpha0_dDelta_dTau2(),
                heos.d3alpha0_dTau3(),
            )
            residual = PhiJet(
                heos.alphar(),
                heos.dalphar_dDelta(),
                heos.d2alphar_dDelta2(),
                heos.dalphar_dTau(),
                heos.d2alphar_dTau2(),
                heos.d2alphar_dDelta_dTau(),
                heos.d3alphar_dDelta3(),
                heos.d3alphar_dDelta2_dTau(),
                heos.d3alphar_dDelta_dTau2(),
                heos.d3alphar_dTau3(),
            )
        except Exception as error:  # spec §4: any CoolProp exception
            raise _EvaluationError(
                f"coolprop_evaluation_failed: {type(error).__name__}: {error} at "
                f"T = {temperature!r} K, rho = {density!r} mol/m3"
            ) from error
        return ideal, residual

    # -- properties at (T, ρ) (S05 §3.1, §3.3) -----------------------------------------------------

    def _at(
        self, temperature: float, density: float, root_pressure: float | None = None
    ) -> _Answer:
        """The six phase properties at (T, ρ) with their (T, P) derivatives."""
        fluid = self._fluid
        r = fluid.r
        tau_v, delta_v = fluid.t_red / temperature, density / fluid.rho_red
        ideal, res = self._jet(temperature, density)
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
        if root_pressure is not None:
            # At a solved root Z ≡ P/(ρRT), exact to rounding, while 1 + δαʳ_δ is a difference of
            # O(1) terms when Z ≪ 1 (S05, C10_DECISIONS WO-S05-1). The partials stay the jet's.
            z = _Dual(root_pressure / (density * r * temperature), z.d, z.t)
        tau_phi_t = tau * (phi0_t + phir_t)
        values = {
            "h": r * temp * (1.0 + tau_phi_t + delta_phir_d),
            "s": r * (tau_phi_t - phi0 - phir),
            "v": 1.0 / (fluid.rho_red * delta),
            "Z": z,
            "cp": -r * (tau * tau) * (phi0_tt + phir_tt)
            + r
            * (z - delta * tau * phir_dt)
            * (z - delta * tau * phir_dt)
            / (1.0 + 2.0 * delta_phir_d + delta * delta * phir_dd),
            self._lnphi: phir + delta_phir_d - z.log(),
        }
        pressure = (fluid.rho_red * r) * delta * temp * z
        by_t = -tau_v / temperature  # dτ/dT at constant ρ
        p_rho, p_t = pressure.d / fluid.rho_red, pressure.t * by_t
        answer: _Answer = {}
        for name, x in values.items():
            x_rho = x.d / fluid.rho_red
            answer[name] = (x.v, x.t * by_t - x_rho * p_t / p_rho, x_rho / p_rho)
        return answer

    def _pressure(self, temperature: float, density: float) -> tuple[float, float]:
        """p and (∂p/∂ρ)_T at (T, ρ), from the same αʳ jet as every property."""
        fluid = self._fluid
        delta = density / fluid.rho_red
        _, res = self._jet(temperature, density)
        rt = fluid.r * temperature
        return (
            density * rt * (1.0 + delta * res.d),
            rt * (1.0 + 2.0 * delta * res.d + delta * delta * res.dd),
        )

    # -- saturation (S05 §3.5) ---------------------------------------------------------------------

    def _solve_saturation(self, temperature: float) -> _Saturation | None:
        """Maxwell's conditions by two-variable Newton in (δ', δ''), T < T_c; `None` if not
        converged in `MAX_ITERATIONS` or if an iterate leaves ρ' > ρ_c > ρ'' (S05 §3.5)."""
        fluid, seeds = self._fluid, self._seeds
        if seeds is None:
            return None
        dc = fluid.rho_c / fluid.rho_red
        dl = seeds.rho_l(temperature, fluid.t_c) / fluid.rho_red
        dv = seeds.rho_v(temperature, fluid.t_c) / fluid.rho_red
        previous = math.inf
        for iteration in range(1, MAX_ITERATIONS + 1):
            (_, rl), (_, rv) = (
                self._jet(temperature, dl * fluid.rho_red),
                self._jet(temperature, dv * fluid.rho_red),
            )
            kl = 1.0 + 2.0 * dl * rl.d + dl * dl * rl.dd
            kv = 1.0 + 2.0 * dv * rv.d + dv * dv * rv.dd
            # F1 = p/(ρ_red R T) and F2 = g/(RT) less its δ-free part, each liquid minus vapour.
            f1 = dl * (1.0 + dl * rl.d) - dv * (1.0 + dv * rv.d)
            f2 = (rl.phi + dl * rl.d + math.log(dl)) - (rv.phi + dv * rv.d + math.log(dv))
            spread = 1.0 / dl - 1.0 / dv
            step_l = -(f2 - f1 / dv) / (kl * spread)
            step_v = -(f2 - f1 / dl) / (kv * spread)
            dl, dv = dl + step_l, dv + step_v
            if not dl > dc > dv > 0.0:
                return None
            step = max(abs(step_l) / dl, abs(step_v) / dv)
            if _converged(step, previous):
                # p_σ from the vapour (S05; spec review finding 3): p(ρ', T) is a difference of
                # O(1) terms where Z' ≪ 1 (C3H8 at T_lo: Z' = 3.8e-10); at the root both are p_σ.
                rho_v = dv * fluid.rho_red
                return _Saturation(
                    temperature,
                    dl * fluid.rho_red,
                    rho_v,
                    self._pressure(temperature, rho_v)[0],
                    iteration,
                )
            previous = step
        return None

    def _saturation_slope(self, saturation: _Saturation) -> float:
        """dp_σ/dT by Clausius-Clapeyron on the converged phases (S05 §3.5)."""
        liquid = self._at(saturation.temperature, saturation.rho_l)
        vapour = self._at(saturation.temperature, saturation.rho_v)
        return (vapour["s"][0] - liquid["s"][0]) / (vapour["v"][0] - liquid["v"][0])

    def _tsat(self, pressure: float) -> tuple[float, float] | None:
        """T_σ(P) and dT_σ/dP: Newton on p_σ(T) = P with the Clausius-Clapeyron slope, seeded by
        bisection on the vapour-pressure ancillary in [T_lo − 1 K, T_σ,max] (S05 §3.5)."""
        fluid, seeds = self._fluid, self._seeds
        if seeds is None:
            return None
        low, high = fluid.t_lo - 1.0, fluid.t_sigma_max
        for _ in range(64):
            middle = 0.5 * (low + high)
            if seeds.pressure(middle, fluid.t_c) < pressure:
                low = middle
            else:
                high = middle
        temperature = 0.5 * (low + high)
        previous = math.inf
        for _ in range(MAX_ITERATIONS):
            saturation = self._saturation(temperature)
            if saturation is None:
                return None
            slope = self._saturation_slope(saturation)
            step = (saturation.pressure - pressure) / slope
            relative = abs(step) / temperature
            if _converged(relative, previous):
                return temperature, 1.0 / slope
            temperature -= step
            previous = relative
        return None

    def _tsat_bounds(self) -> tuple[float, float] | None:
        """[max(p_σ(T_lo), P_lo), p_σ(T_σ,max)], computed by this provider (spec §6.3)."""
        if self._bounds is None:
            fluid = self._fluid
            low, high = self._saturation(fluid.t_lo), self._saturation(fluid.t_sigma_max)
            if low is None or high is None:
                return None
            self._bounds = (max(low.pressure, fluid.p_lo), high.pressure)
        return self._bounds

    # -- density roots (S05 §4.4) ------------------------------------------------------------------

    def _bracketed_density(
        self, temperature: float, pressure: float, low: float, high: float, start: float
    ) -> float | None:
        """Safeguarded Newton on p(ρ, T) = P in (low, high]: bisection whenever a step leaves the
        bracket; only a Newton correction converges, tested before the safeguard (S05 §4.4,
        R-595). p(low) < P ≤ p(high) is the caller's."""
        rho, previous = start, math.inf
        for _ in range(MAX_ITERATIONS):
            p, p_rho = self._pressure(temperature, rho)
            residual = p - pressure
            if residual == 0.0:
                return rho
            if residual < 0.0:
                low = rho
            else:
                high = rho
            if not p_rho > 0.0:
                rho, previous = 0.5 * (low + high), math.inf
                continue
            new = rho - residual / p_rho
            step = abs(new - rho) / rho
            if _converged(step, previous):
                return new
            rho, previous = (new if low < new < high else 0.5 * (low + high)), step
        return None

    def _metastable_density(
        self, temperature: float, pressure: float, start: float, low: float, high: float
    ) -> float | None:
        """Newton from the saturated density, accepted only while it stays in (low, high] (S05
        §4.4's band roots)."""
        rho, previous = start, math.inf
        for _ in range(MAX_ITERATIONS):
            p, p_rho = self._pressure(temperature, rho)
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
        self, temperature: float, pressure: float, phase: Phase, saturation: _Saturation | None
    ) -> float | None:
        """The root of the answered phase on its bracket (S05 §4.4, ρ_max for 1250 kg/m³)."""
        fluid = self._fluid
        top = fluid.rho_max
        ideal = pressure / (fluid.r * temperature)
        if saturation is None:  # T ≥ T_c
            return self._bracketed_density(temperature, pressure, 0.0, top, min(ideal, top))
        if phase == "VAPOR":
            if pressure <= saturation.pressure:
                rho_v = saturation.rho_v
                return self._bracketed_density(temperature, pressure, 0.0, rho_v, min(ideal, rho_v))
            return self._metastable_density(
                temperature, pressure, saturation.rho_v, 0.0, fluid.rho_c
            )
        if pressure >= saturation.pressure:
            bottom = saturation.rho_l
            return self._bracketed_density(temperature, pressure, bottom, top, bottom)
        return self._metastable_density(temperature, pressure, saturation.rho_l, fluid.rho_c, top)

    # -- the phase rule (S05 §4.2, spec §6.3) ------------------------------------------------------

    def _near_critical(self, temperature: float, pressure: float) -> bool:
        (t_low, t_high), (p_low, p_high) = self._fluid.nc_t, self._fluid.nc_p
        return t_low < temperature < t_high and p_low <= pressure <= p_high

    def _rule(self, temperature: float, pressure: float) -> _Rule | None:
        """Steps 2-4 of S05 §4.2 (step 1 is the caller's); `None` when the saturation needed for
        the label does not converge."""
        fluid = self._fluid
        if temperature >= fluid.t_c:
            return _Rule(("VAPOR",), None, "supercritical")
        if temperature > fluid.t_sigma_max:
            answered: tuple[Phase, ...] = (
                ("LIQUID",)
                if pressure >= fluid.p_c
                else ("VAPOR",)
                if pressure < fluid.nc_p[0]
                else ()
            )
            return _Rule(answered, None, "near_critical_edge")
        saturation = self._saturation(temperature)
        if saturation is None:
            return None
        s_sigma = math.log(pressure / saturation.pressure)
        liquid: tuple[Phase, ...] = ("LIQUID",) if s_sigma >= -fluid.eps_sigma else ()
        vapour: tuple[Phase, ...] = ("VAPOR",) if s_sigma <= fluid.eps_sigma else ()
        return _Rule(liquid + vapour, saturation, "saturation")

    def _domain_violation(self, state: StreamState) -> str | None:
        """`out_of_domain: ...` when T or P leaves the fluid's box, or the flow leaves nTP-v1's."""
        fluid = self._fluid
        t, p = state.temperature, state.pressure
        if not (math.isfinite(t) and math.isfinite(p)):
            return f"out_of_domain: non-finite state (T = {t!r} K, P = {p!r} Pa)"
        if not fluid.t_lo <= t <= fluid.t_hi:
            return f"out_of_domain: temperature {t!r} K outside [{fluid.t_lo}, {fluid.t_hi}] K"
        if not fluid.p_lo <= p <= fluid.p_hi:
            return f"out_of_domain: pressure {p!r} Pa outside [{fluid.p_lo}, {fluid.p_hi}] Pa"
        if not (state.n[0] >= 0.0 and math.isfinite(state.n[0])):
            return (
                f"out_of_domain: the {fluid.component} flow {state.n[0]!r} is not finite and "
                "non-negative"
            )
        return None

    # -- describe ----------------------------------------------------------------------------------

    def describe(self) -> PropertyCapabilities:
        """Computed from constants: needs no CoolProp (spec §5.1)."""
        fluid = self._fluid
        nc_t, nc_p = fluid.nc_t, fluid.nc_p
        return PropertyCapabilities(
            provider_id=PROVIDER_ID,
            implementation_sha256=_implementation_sha256(),
            data_sha256=_data_sha256(fluid),
            reference_convention=REFERENCE_CONVENTION,
            state_definition=STATE_DEFINITION,
            components=(fluid.component,),
            phases=("LIQUID", "VAPOR"),
            properties=(*self._phase_properties, *_SATURATION_PROPERTIES),
            flashes=("TP",),
            derivative_order=dict.fromkeys(self._derivative_inputs, 1),
            domain={"T": (fluid.t_lo, fluid.t_hi), "P": (fluid.p_lo, fluid.p_hi)},
            uncertainty=(
                f"verification: {fluid.verification}; EOS {fluid.bibtex_eos} as evaluated by "
                f"CoolProp {PINNED_COOLPROP_VERSION}; the EOS's own uncertainty is not "
                "re-validated"
            ),
            data_provenance=(
                f"CoolProp {PINNED_COOLPROP_VERSION} (MIT), fluid {fluid.name}, not "
                f"redistributed; {fluid.bibtex_eos}"
            ),
            thread_safety="not_thread_safe",
            numerical_limitations=(
                f"near_critical: T in ({nc_t[0]!r}, {nc_t[1]!r}) K with P in [{nc_p[0]!r}, "
                f"{nc_p[1]!r}] Pa is refused for every phase and for the flash.",
                f"Below T_sigma_max = {fluid.t_sigma_max!r} K the phase follows saturation with a "
                f"band eps_sigma = {fluid.eps_sigma!r} in ln(P/Psat): inside it both phases are "
                "answered on their own roots, and the TP flash is refused tp_flash_degenerate; "
                "metastable states beyond the band are refused phase_not_stable.",
                f"T >= T_c = {fluid.t_c!r} K is answered VAPOR only; in (T_sigma_max, T_c) LIQUID "
                f"needs P >= p_c = {fluid.p_c!r} Pa and VAPOR P < {nc_p[0]!r} Pa.",
                f"Psat is answered for T in [{fluid.t_lo!r}, {fluid.t_sigma_max!r}] K and Tsat "
                "for P in [max(Psat(T_lo), P_lo), Psat(T_sigma_max)]; elsewhere no_saturation.",
                "No PH flash, no g, cv or speed of sound, no solid, no state outside the box; "
                "requires the coolprop extra (CoolProp 8.0.0 at the pinned gitrevision).",
                *fluid.limitations,
            ),
        )

    # -- properties --------------------------------------------------------------------------------

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        del context
        fluid = self._fluid
        undeclared = [name for name in request.derivatives if name not in self._derivative_inputs]
        if undeclared:
            return _refused("unsupported", f"undeclared_derivative_input: {undeclared[0]}")
        phase_properties = self._phase_properties
        known = (*phase_properties, *_SATURATION_PROPERTIES)
        unknown = [name for name in request.properties if name not in known]
        if unknown:
            return _refused("unsupported", f"unknown_property: {unknown}")
        state = request.state
        if len(state.n) != 1:
            return _refused(
                "error", f"state_length: {len(state.n)} flows for ({fluid.component!r},)"
            )
        guard = self._guard()
        if guard is not None:
            return _refused("unsupported", guard)
        outside = self._domain_violation(state)
        if outside is not None:
            return _refused("out_of_domain", outside)
        if state.is_dormant:
            return _refused("unsupported", "dormant_state: composition undefined")
        try:
            return self._evaluate(request, set(phase_properties))
        except _EvaluationError as error:
            return _refused("error", str(error))

    def _evaluate(self, request: PropertyRequest, phase_properties: set[str]) -> PropertyResult:
        fluid = self._fluid
        state = request.state
        t, p = state.temperature, state.pressure
        asked = set(request.properties)
        if "Psat" in asked and t > fluid.t_sigma_max:
            return _refused(
                "unsupported",
                f"no_saturation: Psat at {t!r} K outside [{fluid.t_lo}, {fluid.t_sigma_max}] K",
            )
        if "Tsat" in asked:
            bounds = self._tsat_bounds()
            if bounds is None:
                return self._not_converged("the Tsat bounds")
            low, high = bounds
            if not low <= p <= high:
                return _refused(
                    "unsupported",
                    f"no_saturation: Tsat at {p!r} Pa outside [{low!r}, {high!r}] Pa",
                )

        answer: _Answer = {}
        saturation: _Saturation | None = None
        if asked & phase_properties:
            if self._near_critical(t, p):
                return _refused(
                    "unsupported", f"near_critical: {t!r} K, {p!r} Pa is inside the refused box"
                )
            rule = self._rule(t, p)
            if rule is None:
                return self._not_converged(f"at {t!r} K")
            if request.phase not in rule.answered:
                return _refused(
                    "unsupported",
                    f"phase_not_stable: {request.phase} at {t!r} K, {p!r} Pa; answered "
                    f"{list(rule.answered)}",
                )
            saturation = rule.saturation
            if saturation is None and t < fluid.t_c:
                saturation = self._saturation(t)
                if saturation is None:
                    return self._not_converged(f"at {t!r} K")
            rho = self._density(t, p, request.phase, saturation)
            if rho is None:
                return _refused(
                    "not_converged",
                    f"density_not_converged: {request.phase} at {t!r} K, {p!r} Pa",
                )
            answer = self._at(t, rho, p)
        if "Psat" in asked:
            if saturation is None or saturation.temperature != t:
                saturation = self._saturation(t)
            if saturation is None:
                return self._not_converged(f"Psat at {t!r} K")
            answer["Psat"] = (saturation.pressure, self._saturation_slope(saturation), 0.0)
        if "Tsat" in asked:
            solved = self._tsat(p)
            if solved is None:
                return self._not_converged(f"Tsat at {p!r} Pa")
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
            phase_signature=request.phase,
            values=values,
            derivatives=derivatives,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    def _not_converged(self, where: str) -> PropertyResult:
        detail = f"{_NOT_CONVERGED_SAT}: {where}"
        if self._seed_error is not None:
            detail += f"; {self._seed_error}"
        return _refused("not_converged", detail)

    # -- flash -------------------------------------------------------------------------------------

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        """The TP flash of S05 §4.5: single-phase outside the band, refused inside it."""
        del context
        fluid = self._fluid
        if request.specification != "TP":
            return _flash_refused(
                "unsupported",
                f"unsupported_specification: {request.specification!r}; {PROVIDER_ID} offers TP "
                "only",
            )
        if request.derivatives:
            return _flash_refused(
                "unsupported",
                f"flash_derivatives_unsupported: {list(request.derivatives)}; "
                "FlashResult carries no derivatives",
            )
        state = request.state
        if len(state.n) != 1:
            return _flash_refused(
                "error", f"state_length: {len(state.n)} flows for ({fluid.component!r},)"
            )
        guard = self._guard()
        if guard is not None:
            return _flash_refused("unsupported", guard)
        outside = self._domain_violation(state)
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
        if self._near_critical(t, p):
            return _flash_refused(
                "unsupported", f"near_critical: {t!r} K, {p!r} Pa is inside the refused box"
            )
        try:
            rule = self._rule(t, p)
        except _EvaluationError as error:
            return _flash_refused("error", str(error))
        if rule is None:
            return _flash_refused("not_converged", self._not_converged(f"at {t!r} K").message)
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


# -- the module-level jet (spec §3.3) --------------------------------------------------------------

_JET_PROVIDERS: dict[str, CoolPropHeosProvider] = {}


def helmholtz_jet(component_id: str, temperature: float, density: float) -> tuple[PhiJet, PhiJet]:
    """(α°, αʳ) with their ten partials each, in S05 §3.2's order, at (T, ρ) in K and mol/m³.

    Raises `ValueError` for an id that is not admitted, `CoolPropUnavailable` on a guard failure,
    and `RuntimeError` (`coolprop_evaluation_failed:`) when CoolProp raises.
    """
    provider = _JET_PROVIDERS.get(component_id)
    if provider is None:
        provider = _JET_PROVIDERS.setdefault(component_id, CoolPropHeosProvider(component_id))
    refusal = provider._guard()
    if refusal is not None:
        raise CoolPropUnavailable(refusal)
    return provider._jet(temperature, density)


def _refused(status: PropertyStatus, message: str) -> PropertyResult:
    """A typed refusal: no phase signature, no values (spec §6.5)."""
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
