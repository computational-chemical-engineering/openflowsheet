"""Design-lane reference generator for the S07 specification (CoolProp 8.0.0 HEOS fluids, ADR 0046).

Everything here follows from the closed-form Helmholtz functions of ``docs/derivations/S07-spec.md``
§2.2 and §16.2, evaluated with mpmath at 50 significant digits over each fluid's ``EOS[0]``
coefficients as parsed from the pinned CoolProp's fluid JSON. It imports nothing from
``openflowsheet`` or ``benchmarks``.

**Independence (S05 D6).** Only α° and αʳ are written down here. Every partial of α, every (T, P)
derivative of a property, the saturation slope and Tsat are obtained by ``mp.diff`` (numerical
differentiation at raised precision) or by root-finding on those two functions. The identities
I1–I9 (S05 §3.4) are then *claims* checked against those numbers (C13). Newton steps use
Jacobians assembled from the same numerical partials; a Jacobian affects the iteration count,
never the converged value.

**CoolProp's role.** CoolProp supplies the fluid JSON (parsed, never written out), the seeds
(``T_critical``/``rhomolar_critical``; the saturation and density seeds of its own flashes), the
melting line (T_lo and C9), ``Ttriple``/``p_triple`` and, for claim C11 only, its own ``PropsSI``
values. None of these supplies an expectation (spec rule 1).

Each admitted fluid runs in a worker process (``--jobs``, default ``os.cpu_count()``); the parent
serializes the results with sorted keys, so the bytes do not depend on the number of workers.

    python docs/derivations/scripts/s07_reference.py --check
    python docs/derivations/scripts/s07_reference.py \\
        --emit docs/derivations/scripts/s07_reference.json \\
        --emit-fluid-table src/openflowsheet/thermo/_coolprop_heos_fluids.py

**Layout** (``docs/S07_DECISIONS.md`` B-10): per fluid under ``fluids[<id>]``; a jet is 20 floats,
α° then αʳ, each in ``PhiJet`` order; a TP state is ``[T, P, h, s, v, Z, cp, lnphi]`` (tier A adds
its T and P derivatives of h, s, v, Z, cp, lnphi); a refusal probe is ``[assertion, code, probe,
control]``. Floats are ``repr`` of the nearest double; keys are sorted.

The environment is ``requirements.lock`` (mpmath, PyYAML) plus ``requirements-coolprop.lock``.

``--check`` re-derives every claim and compares the result with the committed reference file and
the committed fluid table byte for byte (C19). ``--emit`` and ``--emit-fluid-table`` write only
when every claim of every fluid holds. ``--report PATH`` writes each fluid's status (passed, or the
first failing claim with its measured reason) whatever the outcome, for the Q-A1-4 record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import traceback
from collections.abc import Callable, Sequence
from decimal import ROUND_CEILING, Decimal, localcontext
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import CoolProp
import CoolProp.CoolProp
import yaml
from mpmath import mp, mpf

CP = CoolProp.CoolProp
mp.dps = 50
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_OUT = HERE / "s07_reference.json"
TABLE_OUT = ROOT / "src" / "openflowsheet" / "thermo" / "_coolprop_heos_fluids.py"
CHECKS_PATH = ROOT / "benchmarks" / "s07" / "published_checks.yaml"
S05_PATH = HERE / "s05_reference.json"

SCHEMA = "s07-reference-v1"
PINNED_VERSION = "8.0.0"
PINNED_GITREVISION = "ae81610e7d23efc57f9d051c8e70a4d66e87537f"

# -- the rules' numbers (spec §6.1, §16.4) --------------------------------------------------------

P_LO = 1.0e2
P_CAP = 1.0e8
T_CAP = 1273.15
P_FLOOR = 5.0e6
KAPPA = "1e-8"  # 1/Pa (§16.4)
EPS_SIGMA = 1e-6
T_SIGMA_FACTOR = "0.9998"  # T_sigma,max = T_c (1 - 2e-4)
NC_T_HI_FACTOR = "1.002"
NC_P_LO_FACTOR = "0.996"
NC_P_HI_FACTOR = "1.008"
PROBE_REL = "1e-9"  # the refusal probes' distance from a bound (§7)
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")

# -- the literal lists (spec §16.1, §16.3); C15 compares the computed lists with these ------------

#: (component id, CoolProp name, bound kind), in §16.3's order. The first nine are tier A.
FLUIDS: tuple[tuple[str, str, str], ...] = (
    ("H2O", "Water", "T"),
    ("CO2", "CarbonDioxide", "M"),
    ("N2", "Nitrogen", "M"),
    ("O2", "Oxygen", "M"),
    ("Ar", "Argon", "M"),
    ("CH4", "Methane", "M"),
    ("C2H6", "Ethane", "M"),
    ("C3H8", "n-Propane", "M"),
    ("H2", "Hydrogen", "M"),
    ("1-Butene", "1-Butene", "E"),
    ("Acetone", "Acetone", "E"),
    ("Ammonia", "Ammonia", "E"),
    ("Benzene", "Benzene", "E"),
    ("CarbonMonoxide", "CarbonMonoxide", "M"),
    ("CarbonylSulfide", "CarbonylSulfide", "E"),
    ("Chlorine", "Chlorine", "E"),
    ("cis-2-Butene", "cis-2-Butene", "E"),
    ("CycloHexane", "CycloHexane", "M"),
    ("Cyclopentane", "Cyclopentane", "E"),
    ("CycloPropane", "CycloPropane", "E"),
    ("D4", "D4", "E"),
    ("D5", "D5", "E"),
    ("Deuterium", "Deuterium", "M"),
    ("Dichloroethane", "Dichloroethane", "E"),
    ("DiethylEther", "DiethylEther", "E"),
    ("DimethylCarbonate", "DimethylCarbonate", "E"),
    ("DimethylEther", "DimethylEther", "E"),
    ("Ethanol", "Ethanol", "M"),
    ("EthylBenzene", "EthylBenzene", "E"),
    ("Ethylene", "Ethylene", "M"),
    ("EthyleneOxide", "EthyleneOxide", "E"),
    ("Fluorine", "Fluorine", "M"),
    ("HeavyWater", "HeavyWater", "T"),
    ("HFE143m", "HFE143m", "E"),
    ("HydrogenChloride", "HydrogenChloride", "E"),
    ("HydrogenSulfide", "HydrogenSulfide", "E"),
    ("IsoButane", "IsoButane", "M"),
    ("IsoButene", "IsoButene", "E"),
    ("Isohexane", "Isohexane", "E"),
    ("Isopentane", "Isopentane", "M"),
    ("Krypton", "Krypton", "M"),
    ("m-Xylene", "m-Xylene", "E"),
    ("MD3M", "MD3M", "E"),
    ("MD4M", "MD4M", "E"),
    ("MDM", "MDM", "E"),
    ("Methanol", "Methanol", "M"),
    ("MethylLinoleate", "MethylLinoleate", "E"),
    ("MethylLinolenate", "MethylLinolenate", "E"),
    ("MethylOleate", "MethylOleate", "E"),
    ("MethylPalmitate", "MethylPalmitate", "E"),
    ("MethylStearate", "MethylStearate", "E"),
    ("MM", "MM", "E"),
    ("n-Butane", "n-Butane", "M"),
    ("n-Decane", "n-Decane", "E"),
    ("n-Dodecane", "n-Dodecane", "E"),
    ("n-Hexane", "n-Hexane", "E"),
    ("n-Nonane", "n-Nonane", "E"),
    ("n-Octane", "n-Octane", "E"),
    ("n-Pentane", "n-Pentane", "M"),
    ("n-Perfluorobutane", "n-Perfluorobutane", "E"),
    ("n-Perfluorohexane", "n-Perfluorohexane", "E"),
    ("n-Perfluoropentane", "n-Perfluoropentane", "E"),
    ("n-Undecane", "n-Undecane", "E"),
    ("Neon", "Neon", "M"),
    ("Neopentane", "Neopentane", "E"),
    ("NitrousOxide", "NitrousOxide", "E"),
    ("Novec649", "Novec649", "E"),
    ("o-Xylene", "o-Xylene", "E"),
    ("OrthoDeuterium", "OrthoDeuterium", "M"),
    ("OrthoHydrogen", "OrthoHydrogen", "M"),
    ("p-Xylene", "p-Xylene", "E"),
    ("ParaDeuterium", "ParaDeuterium", "M"),
    ("Propylene", "Propylene", "M"),
    ("PropyleneGlycol", "PropyleneGlycol", "E"),
    ("Propyne", "Propyne", "E"),
    ("R11", "R11", "E"),
    ("R1123", "R1123", "E"),
    ("R113", "R113", "E"),
    ("R1130_E", "R1130(E)", "E"),
    ("R1132_E", "R1132(E)", "E"),
    ("R114", "R114", "E"),
    ("R115", "R115", "E"),
    ("R116", "R116", "E"),
    ("R12", "R12", "E"),
    ("R1224YDZ", "R1224YDZ", "E"),
    ("R123", "R123", "E"),
    ("R1233zd_E", "R1233zd(E)", "E"),
    ("R1234yf", "R1234yf", "E"),
    ("R1234ze_E", "R1234ze(E)", "E"),
    ("R1234ze_Z", "R1234ze(Z)", "E"),
    ("R124", "R124", "E"),
    ("R1243zf", "R1243zf", "E"),
    ("R125", "R125", "E"),
    ("R13", "R13", "E"),
    ("R1336mzz_E", "R1336mzz(E)", "E"),
    ("R1336mzz_Z", "R1336mzz(Z)", "E"),
    ("R134a", "R134a", "E"),
    ("R13I1", "R13I1", "E"),
    ("R14", "R14", "E"),
    ("R141b", "R141b", "E"),
    ("R142b", "R142b", "E"),
    ("R143a", "R143a", "E"),
    ("R152A", "R152A", "E"),
    ("R21", "R21", "E"),
    ("R218", "R218", "E"),
    ("R22", "R22", "E"),
    ("R227EA", "R227EA", "E"),
    ("R23", "R23", "E"),
    ("R236FA", "R236FA", "E"),
    ("R245ca", "R245ca", "E"),
    ("R245fa", "R245fa", "E"),
    ("R32", "R32", "E"),
    ("R365MFC", "R365MFC", "E"),
    ("R40", "R40", "E"),
    ("R41", "R41", "E"),
    ("RC318", "RC318", "E"),
    ("SulfurDioxide", "SulfurDioxide", "E"),
    ("SulfurHexafluoride", "SulfurHexafluoride", "E"),
    ("Tetrahydrofuran", "Tetrahydrofuran", "E"),
    ("Toluene", "Toluene", "E"),
    ("trans-2-Butene", "trans-2-Butene", "E"),
    ("VinylChloride", "VinylChloride", "E"),
    ("Xenon", "Xenon", "E"),
)
TIER_A: frozenset[str] = frozenset(f[0] for f in FLUIDS[:9])

#: The thirteen exclusions of §16.1 (CoolProp name -> rule, reason).
EXCLUDED: dict[str, tuple[str, str]] = {
    **{
        n: ("S1", "S1: EOS[0] is pseudo-pure (a mixture described as a pure fluid)")
        for n in ("Air", "R404A", "R407C", "R410A", "R507A", "SES36")
    },
    **{
        n: (
            "S2",
            "S2: EOS[0] uses IdealGasHelmholtzCP0AlyLee, which has no closed form in S07 "
            "§2.2/§16.2 (Q-A1-2)",
        )
        for n in ("n-Heptane", "D6")
    },
    **{
        n: ("S3", "S3: T_lo >= 0.99*T_c, so the saturation range is below 1 % of T_c")
        for n in ("Helium", "ParaHydrogen")
    },
    **{
        n: ("S4", "S4: the near-critical box does not lie inside the domain box")
        for n in ("MD2M", "R236EA", "R161")
    },
}

#: The expected ``dropped`` list per fluid (C10; fixed at WO-S07-1b's first run, §16.6).
EXPECTED_DROPPED: dict[str, tuple[str, ...]] = {}

A0_TYPES = frozenset(
    {
        "IdealGasHelmholtzLead",
        "IdealGasHelmholtzEnthalpyEntropyOffset",
        "IdealGasHelmholtzLogTau",
        "IdealGasHelmholtzPlanckEinstein",
        "IdealGasHelmholtzPlanckEinsteinFunctionT",
        "IdealGasHelmholtzPower",
        "IdealGasHelmholtzPlanckEinsteinGeneralized",
        "IdealGasHelmholtzCP0PolyT",
        "IdealGasHelmholtzCP0Constant",
    }
)
AR_TYPES = frozenset(
    {
        "ResidualHelmholtzPower",
        "ResidualHelmholtzGaussian",
        "ResidualHelmholtzNonAnalytic",
        "ResidualHelmholtzExponential",
        "ResidualHelmholtzDoubleExponential",
        "ResidualHelmholtzLemmon2005",
        "ResidualHelmholtzGaoB",
    }
)

#: The `PhiJet` slots as (delta order, tau order) (``iapws95.PhiJet``; spec §16.6's layout).
JET = ((0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (1, 1), (3, 0), (2, 1), (1, 2), (0, 3))
JET_NAMES = ("phi", "d", "dd", "t", "tt", "dt", "ddd", "ddt", "dtt", "ttt")
#: s05_reference.json's suffix for each `PhiJet` slot.
S05_SUFFIX = ("", "_d", "_dd", "_t", "_tt", "_dt", "_ddd", "_ddt", "_dtt", "_ttt")
TP_LAYOUT = ("T", "P", "h", "s", "v", "Z", "cp", "lnphi")
PROPS = ("h", "s", "v", "Z", "cp", "lnphi")

E_LIMITATION = (
    "lower temperature bound estimated from the triple point (no melting line in CoolProp 8.0.0): "
    "T_lo = T_t*(1 + 1e-8/Pa*P_hi); solid states lie inside the box if the melting slope exceeds "
    "0.01/MPa*T_t"
)

CLAIM_TEXT = {
    "C1": "EOS[0] is the EOS parsed, and every term type is in §2.2 or §16.2",
    "C2": "CoolProp 8.0.0 at the pinned gitrevision; each fluid_data_sha256 is stable across two "
    "reads",
    "C3": "no output key holds a coefficient array; the key set equals the schema whitelist",
    "C4": "the 50-digit partials at each phi state agree with a 30-digit recomputation to 1e-25",
    "C5": "the EOS critical point: |p_rho| rho_c/p_c and |p_rhorho| rho_c^2/p_c < 1e-20; "
    "T_c within 1e-3 of T_critical()",
    "C6": "p_sigma(T_sigma,max) > p_c (1 - 4e-3); the critical point lies inside the box",
    "C7": "at T_sigma,max both band-edge roots exist on their branches",
    "C8": "dp/drho > 0 on every bracket of the 31-temperature grid; p(rho_max, T) > P_hi",
    "C9": "the melting line: grid, monotonicity and T_m(P_hi) <= T_lo (§16.4)",
    "C10": "every rule state is in the box and outside the near-critical box, or dropped; "
    "tier A's states equal the unclamped rule; TP states pairwise distinct",
    "C11": "CoolProp's own flash agrees with the generator at every TP state (1e-7; NC 1e-5)",
    "C12": "water equals s05_reference.json within 1e-12 at S05's states with T <= 646.9 K",
    "C13": "identities I1-I9 hold to 1e-30 at every TP and saturation state",
    "C14": "the refusal probes cover every code of §6.5 except rows 4, 10 and 11, each with a "
    "control",
    "C15": "the admitted, excluded and bound lists equal the literal ones; ids and CAS are unique",
    "C16": "every published check row agrees within one unit in its last printed digit",
    "C17": "the output file is at most 1.5e6 bytes",
    "C18": "kappa >= 1.5 x the largest relative melting slope of the M fluids with T_t >= 20 K",
    "C19": "--emit-fluid-table reproduces the committed _coolprop_heos_fluids.py byte for byte",
}


class ClaimFailedError(Exception):
    """A claim failed; the generator refuses to emit."""


class Ledger:
    """Counts the claims that held, per claim id."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def __call__(self, cid: str, condition: Any, text: str) -> None:
        if not condition:
            raise ClaimFailedError(f"{cid}: {text}")
        self.counts[cid] = self.counts.get(cid, 0) + 1


claim = Ledger()


# -- numbers --------------------------------------------------------------------------------------


def dbl(x: Any) -> float:
    """The nearest double."""
    return float(x)


def scaled(x: float, factor: str) -> float:
    """The nearest double of the exact product of the double ``x`` and the decimal ``factor``."""
    return float(mpf(x) * mpf(factor))


def rel(a: Any, b: Any) -> Any:
    return abs(a - b) / max(abs(b), mpf("1e-300"))


def dec(x: float) -> Decimal:
    return Decimal(repr(x))


def ceil_tenth(x: Decimal) -> float:
    """⌈10 x⌉/10 on the exact decimal value (§16.4: no fudge term)."""
    with localcontext() as ctx:
        ctx.prec = 60
        return float((x * 10).to_integral_value(rounding=ROUND_CEILING) / 10)


def ceil_sig(x: Decimal, digits: int) -> float:
    """x rounded up to ``digits`` significant digits, on the exact decimal value."""
    with localcontext() as ctx:
        ctx.prec = 60
        quantum = Decimal(1).scaleb(x.adjusted() - (digits - 1))
        return float((x / quantum).to_integral_value(rounding=ROUND_CEILING) * quantum)


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def fluid_data_sha256(name: str) -> str:
    """§5.1: SHA-256 of the canonical re-serialization of the fluid JSON."""
    return hashlib.sha256(
        canonical(json.loads(CP.get_fluid_param_string(name, "JSON")))
    ).hexdigest()


def comp_id(name: str) -> str:
    for cid, n, _ in FLUIDS[:9]:
        if n == name:
            return cid
    return name.replace("(", "_").replace(")", "")


def partial(f: Callable[[Any, Any], Any], delta: Any, tau: Any, i: int, j: int) -> Any:
    """∂^{i+j} f / ∂δ^i ∂τ^j by mpmath's numerical differentiation."""
    if i == j == 0:
        return f(delta, tau)
    if j == 0:
        return mp.diff(lambda x: f(x, tau), delta, i)
    if i == 0:
        return mp.diff(lambda y: f(delta, y), tau, j)
    return mp.diff(f, (delta, tau), (i, j))


def diffs(g: Callable[[Any], Any], x: Any, n: int) -> list[Any]:
    """g, g', ..., g^(n) at x."""
    return list(mp.diffs(g, x, n))


# -- the closed forms (spec §2.2, §16.2) ----------------------------------------------------------


def _c(x: Any) -> Any:
    """A coefficient: the exact double CoolProp parses."""
    return mpf(float(x))


def _e(x: Any) -> Any:
    """An exponent: a Python int when integral (exact integer powers), else the exact double."""
    return int(x) if float(x).is_integer() else mpf(float(x))


class Eos:
    """One fluid's ``EOS[0]`` (spec §16.0 E4), parsed from the pinned CoolProp's fluid JSON."""

    def __init__(self, name: str) -> None:
        self.name = name
        raw = json.loads(CP.get_fluid_param_string(name, "JSON"))
        self.sha = hashlib.sha256(canonical(raw)).hexdigest()
        top = raw[0] if isinstance(raw, list) else raw
        e = top["EOS"][0]
        self.n_eos = len(top["EOS"])
        self.cas = top["INFO"].get("CAS", "")
        self.bibtex = e.get("BibTeX_EOS", "")
        self.pseudo_pure = bool(e["pseudo_pure"])
        self.types0 = [t["type"] for t in e["alpha0"]]
        self.typesr = [t["type"] for t in e["alphar"]]
        red = e["STATES"]["reducing"]
        self.T_red, self.rho_red = float(red["T"]), float(red["rhomolar"])
        self.R, self.M = float(e["gas_constant"]), float(e["molar_mass"])
        self.T_max, self.p_max = float(e["T_max"]), float(e["p_max"])
        self.supported = set(self.types0) <= A0_TYPES and set(self.typesr) <= AR_TYPES
        self.a0_terms = [self._parse(t) for t in e["alpha0"]] if self.supported else []
        self.ar_terms = [self._parse(t) for t in e["alphar"]] if self.supported else []
        self.Tr, self.rr, self.Rm = mpf(self.T_red), mpf(self.rho_red), mpf(self.R)

    @staticmethod
    def _parse(t: dict[str, Any]) -> tuple[str, Any]:
        k = t["type"]
        if k == "IdealGasHelmholtzLead":
            return k, (_c(t["a1"]), _c(t["a2"]))
        if k == "IdealGasHelmholtzEnthalpyEntropyOffset":
            return k, (_c(t["a1"]), _c(t["a2"]))
        if k == "IdealGasHelmholtzLogTau":
            return k, _c(t["a"])
        if k == "IdealGasHelmholtzPlanckEinstein":
            return k, [(_c(n), _c(th)) for n, th in zip(t["n"], t["t"], strict=True)]
        if k == "IdealGasHelmholtzPlanckEinsteinFunctionT":
            tc = _c(t["Tcrit"])
            return k, [(_c(n), _c(v) / tc) for n, v in zip(t["n"], t["v"], strict=True)]
        if k == "IdealGasHelmholtzPlanckEinsteinGeneralized":
            cols = zip(t["n"], t["t"], t["c"], t["d"], strict=True)
            return k, [(_c(n), _c(th), _c(c), _c(d)) for n, th, c, d in cols]
        if k == "IdealGasHelmholtzPower":
            return k, [(_c(n), _e(e)) for n, e in zip(t["n"], t["t"], strict=True)]
        if k == "IdealGasHelmholtzCP0PolyT":
            pairs = [(_c(c), _e(e)) for c, e in zip(t["c"], t["t"], strict=True)]
            return k, (_c(t["Tc"]), _c(t["T0"]), pairs)
        if k == "IdealGasHelmholtzCP0Constant":
            return k, (_c(t["Tc"]), _c(t["T0"]), [(_c(t["cp_over_R"]), 0)])
        if k in ("ResidualHelmholtzPower", "ResidualHelmholtzExponential"):
            gs = t["g"] if k == "ResidualHelmholtzExponential" else [None] * len(t["n"])
            cols = zip(t["n"], t["d"], t["t"], t["l"], gs, strict=True)
            return k, [(_c(n), _e(d), _e(e), _e(l_), g, l_) for n, d, e, l_, g in cols]
        if k == "ResidualHelmholtzLemmon2005":
            cols = zip(t["n"], t["d"], t["t"], t["l"], t["m"], strict=True)
            return k, [(_c(n), _e(d), _e(e), _e(l_), _e(m), l_, m) for n, d, e, l_, m in cols]
        if k == "ResidualHelmholtzDoubleExponential":
            cols = zip(*(t[x] for x in ("n", "d", "t", "gd", "ld", "gt", "lt")), strict=True)
            return k, [
                (_c(n), _e(d), _e(e), _c(gd), _e(ld), _c(gt), _e(lt))
                for n, d, e, gd, ld, gt, lt in cols
            ]
        if k == "ResidualHelmholtzGaussian":
            cols = zip(
                *(t[x] for x in ("n", "d", "t", "eta", "epsilon", "beta", "gamma")), strict=True
            )
            return k, [
                tuple([_c(n), _e(d), _e(e)] + [_c(x) for x in rest]) for n, d, e, *rest in cols
            ]
        if k == "ResidualHelmholtzGaoB":
            names = ("n", "d", "t", "eta", "epsilon", "beta", "gamma", "b")
            cols = zip(*(t[x] for x in names), strict=True)
            return k, [
                tuple([_c(n), _e(d), _e(e)] + [_c(x) for x in rest]) for n, d, e, *rest in cols
            ]
        if k == "ResidualHelmholtzNonAnalytic":
            names = ("n", "a", "b", "beta", "A", "B", "C", "D")
            cols = zip(*(t[x] for x in names), strict=True)
            return k, [tuple(_c(x) for x in row) for row in cols]
        raise ClaimFailedError(f"C1: term type {k} has no closed form")

    def a0(self, delta: Any, tau: Any) -> Any:
        out = mpf(0)
        for k, p in self.a0_terms:
            if k == "IdealGasHelmholtzLead":
                out += mp.log(delta) + p[0] + p[1] * tau
            elif k == "IdealGasHelmholtzEnthalpyEntropyOffset":
                out += p[0] + p[1] * tau
            elif k == "IdealGasHelmholtzLogTau":
                out += p * mp.log(tau)
            elif k in (
                "IdealGasHelmholtzPlanckEinstein",
                "IdealGasHelmholtzPlanckEinsteinFunctionT",
            ):
                out += sum(n * mp.log(1 - mp.exp(-th * tau)) for n, th in p)
            elif k == "IdealGasHelmholtzPlanckEinsteinGeneralized":
                out += sum(n * mp.log(c + d * mp.exp(th * tau)) for n, th, c, d in p)
            elif k == "IdealGasHelmholtzPower":
                out += sum(n * tau**e for n, e in p)
            else:  # CP0PolyT, CP0Constant: §16.2's A(c, t)
                tc, t0, pairs = p
                tau0 = tc / t0
                for c, e in pairs:
                    if e == 0:
                        out += c * (1 - tau / tau0 + mp.log(tau / tau0))
                    elif e == -1:
                        out += c * ((tau / tc) * mp.log(tau0 / tau) + (tau - tau0) / tc)
                    else:
                        out += (
                            -c * tc**e * tau ** (-e) / (e * (e + 1))
                            - c * t0 ** (e + 1) * tau / (tc * (e + 1))
                            + c * t0**e / e
                        )
        return out

    def ar(self, delta: Any, tau: Any, zero_jet: bool = False) -> Any:
        """αʳ; ``zero_jet`` applies S05 §3.2's rule to the non-analytic terms at δ = 1."""
        out = mpf(0)
        for k, p in self.ar_terms:
            if k in ("ResidualHelmholtzPower", "ResidualHelmholtzExponential"):
                for n, d, e, lx, g, l_raw in p:
                    term = n * delta**d * tau**e
                    if g is None:  # Power: exp(-δ^l) if l > 0
                        out += term * mp.exp(-(delta**lx)) if l_raw > 0 else term
                    else:  # Exponential, literally (g = 0 gives 1)
                        out += term * mp.exp(-_c(g) * delta**lx)
            elif k == "ResidualHelmholtzLemmon2005":
                for n, d, e, lx, mx, l_raw, m_raw in p:
                    term = n * delta**d * tau**e
                    if l_raw > 0:
                        term *= mp.exp(-(delta**lx))
                    if m_raw > 0:
                        term *= mp.exp(-(tau**mx))
                    out += term
            elif k == "ResidualHelmholtzDoubleExponential":
                for n, d, e, gd, ld, gt, lt in p:
                    out += n * delta**d * tau**e * mp.exp(-gd * delta**ld - gt * tau**lt)
            elif k == "ResidualHelmholtzGaussian":
                for n, d, e, eta, eps, be, ga in p:
                    out += (
                        n
                        * delta**d
                        * tau**e
                        * mp.exp(-eta * (delta - eps) ** 2 - be * (tau - ga) ** 2)
                    )
            elif k == "ResidualHelmholtzGaoB":
                for n, d, e, eta, eps, be, ga, b in p:
                    out += (
                        n
                        * delta**d
                        * tau**e
                        * mp.exp(eta * (delta - eps) ** 2 + 1 / (be * (tau - ga) ** 2 + b))
                    )
            else:  # NonAnalytic
                q = (delta - 1) ** 2
                for n, a, b, be, aa, bb, cc, dd in p:
                    if zero_jet:
                        big = (1 - tau) ** 2
                    else:
                        theta = (1 - tau) + aa * q ** (1 / (2 * be))
                        big = theta**2 + bb * q**a
                    out += n * big**b * delta * mp.exp(-cc * q - dd * (tau - 1) ** 2)
        return out

    def na_zero_jet_valid(self) -> bool:
        """S05 §3.2: the |δ−1| factors vanish with three derivatives iff 1/β > 3 and 2a > 3."""
        return all(
            1 / be > 3 and 2 * a > 3
            for k, p in self.ar_terms
            if k == "ResidualHelmholtzNonAnalytic"
            for _, a, _, be, *_ in p
        )

    # -- properties at (T, rho) (S05 §3.1, molar SI with the fluid's own R) --

    def jet(self, temp: Any, rho: Any, zero_jet: bool = False) -> list[Any]:
        """α° then αʳ, each in `PhiJet` order; α°'s mixed partials are 0 (separable, C1)."""
        tau, delta = self.Tr / temp, rho / self.rr
        out = []
        for i, j in JET:
            out.append(mpf(0) if (i and j) else partial(self.a0, delta, tau, i, j))
        for i, j in JET:
            out.append(partial(lambda x, y: self.ar(x, y, zero_jet), delta, tau, i, j))
        return out

    def pd(self, temp: Any, rho: Any) -> tuple[Any, Any]:
        """p and dp/drho."""
        tau, delta = self.Tr / temp, rho / self.rr
        _, r1, r2 = diffs(lambda x: self.ar(x, tau), delta, 2)
        rt = self.Rm * temp
        return rho * rt * (1 + delta * r1), rt * (1 + 2 * delta * r1 + delta**2 * r2)

    def sat_terms(self, temp: Any, rho: Any) -> tuple[Any, Any, Any]:
        """p/(RT), D = (dp/drho)/(RT) and g/(RT) at (T, rho)."""
        tau, delta = self.Tr / temp, rho / self.rr
        r0, r1, r2 = diffs(lambda x: self.ar(x, tau), delta, 2)
        z = 1 + delta * r1
        return rho * z, 1 + 2 * delta * r1 + delta**2 * r2, self.a0(delta, tau) + r0 + z

    def at_rho(self, temp: Any, rho: Any) -> dict[str, Any]:
        tau, delta = self.Tr / temp, rho / self.rr
        r0, r1, r2 = diffs(lambda x: self.ar(x, tau), delta, 2)
        _, rt1, rt2 = diffs(lambda y: self.ar(delta, y), tau, 2)
        r11 = partial(self.ar, delta, tau, 1, 1)
        o0, ot1, ot2 = diffs(lambda y: self.a0(delta, y), tau, 2)
        rg = self.Rm
        z = 1 + delta * r1
        den = 1 + 2 * delta * r1 + delta**2 * r2
        cv = -(tau**2) * (ot2 + rt2)
        return {
            "p": rho * rg * temp * z,
            "Z": z,
            "v": 1 / rho,
            "h": rg * temp * (1 + tau * (ot1 + rt1) + delta * r1),
            "s": rg * (tau * (ot1 + rt1) - o0 - r0),
            "cp": rg * (cv + (1 + delta * r1 - delta * tau * r11) ** 2 / den),
            "lnphi": r0 + delta * r1 - mp.log(z),
            "h_res": rg * temp * (tau * rt1 + z - 1),
            "D": den,
        }

    # -- roots (S05 §4.4, §3.5); converged to the working precision less a few digits --

    def rho_root(self, temp: Any, pres: Any, seed: Any, lo: Any, hi: Any) -> Any:
        tol = mpf(10) ** (6 - mp.dps)
        r = mpf(seed)
        if not lo < r < hi:
            r = (lo + hi) / 2
        for _ in range(300):
            p, dp = self.pd(temp, r)
            if p > pres:
                hi = min(hi, r)
            else:
                lo = max(lo, r)
            if dp > 0 and abs(p - pres) <= tol * r * dp:
                r -= (p - pres) / dp
                break
            nxt = r - (p - pres) / dp if dp > 0 else (lo + hi) / 2
            r = nxt if lo < nxt < hi else (lo + hi) / 2
        else:
            raise ClaimFailedError(
                f"density root at T={dbl(temp)!r}, P={dbl(pres)!r} did not converge"
            )
        p, dp = self.pd(temp, r)
        # The residual in density units: a liquid near p = 0 has Z ~ 1e-12, so p/P - 1 carries the
        # cancellation of p = rho R T Z while rho itself is converged to the working precision.
        err = abs(p - pres) / (r * dp)
        claim(
            "C13",
            dp > 0 and err < mpf(10) ** (8 - mp.dps),
            f"the density root at T={dbl(temp)!r}, P={dbl(pres)!r} converged "
            f"(dp/drho {dbl(dp):.3e}, relative density residual {dbl(err):.1e}, {mp.dps} digits)",
        )
        return r

    def saturation(self, temp: Any, seed_l: Any, seed_v: Any) -> tuple[Any, Any]:
        """Maxwell (I8) by Newton in (rho', rho'')."""
        tol = mpf(10) ** (6 - mp.dps)
        rl, rv = mpf(seed_l), mpf(seed_v)
        for _ in range(200):
            pl, dl, gl = self.sat_terms(temp, rl)
            pv, dv, gv = self.sat_terms(temp, rv)
            f1, f2 = pl - pv, gl - gv
            j11, j12, j21, j22 = dl, -dv, dl / rl, -dv / rv
            det = j11 * j22 - j12 * j21
            sl = (-f1 * j22 + f2 * j12) / det
            sv = (-f2 * j11 + f1 * j21) / det
            lam = mpf(1)
            while rv + lam * sv <= 0 or rl + lam * sl <= 0:
                lam /= 2
            rl, rv = rl + lam * sl, rv + lam * sv
            if abs(sl) <= tol * rl and abs(sv) <= tol * rv:
                break
        else:
            raise ClaimFailedError(f"saturation at T={dbl(temp)!r} did not converge")
        return rl, rv


# -- CoolProp seeds and admission (never an expectation) ------------------------------------------


class Seeds:
    def __init__(self, name: str) -> None:
        self.name = name
        self.a = CP.AbstractState("HEOS", name)

    def sat(self, temp: Any) -> tuple[float, float]:
        self.a.update(CP.QT_INPUTS, 0, float(temp))
        rl = self.a.rhomolar()
        self.a.update(CP.QT_INPUTS, 1, float(temp))
        return rl, self.a.rhomolar()

    def tsat(self, pres: Any) -> float:
        self.a.update(CP.PQ_INPUTS, float(pres), 0)
        return self.a.T()

    def rho(self, temp: Any, pres: Any) -> float:
        return CP.PropsSI("Dmolar", "T", float(temp), "P", float(pres), self.name)

    def flash(self, temp: float, pres: float) -> dict[str, float]:
        """CoolProp's own TP flash (C11): PropsSI, and its fugacity coefficient for lnphi."""
        out = {
            k: CP.PropsSI(q, "T", temp, "P", pres, self.name)
            for k, q in (
                ("h", "Hmolar"),
                ("s", "Smolar"),
                ("rho", "Dmolar"),
                ("Z", "Z"),
                ("cp", "Cpmolar"),
            )
        }
        b = CP.AbstractState("HEOS", self.name)
        b.update(CP.PT_INPUTS, pres, temp)
        out["lnphi"] = float(mp.log(b.fugacity_coefficient(0)))
        return out


# -- one fluid ------------------------------------------------------------------------------------


class Fluid:
    """Everything the generator computes for one CoolProp name."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.id = comp_id(name)
        self.eos = Eos(name)
        self.cp = CP.AbstractState("HEOS", name)
        self.seeds = Seeds(name)
        self.tier = "A" if self.id in TIER_A else "B"
        self._sat: dict[float, dict[str, Any]] = {}

    # -- §6.1 / §16.4 constants --

    def critical(self) -> None:
        e = self.eos
        a = self.cp
        tau, delta = e.Tr / mpf(a.T_critical()), mpf(a.rhomolar_critical()) / e.rr
        tol = mpf(10) ** (8 - mp.dps)
        for _ in range(100):
            r1, r2, r3, r4 = diffs(lambda x, t=tau: e.ar(x, t), delta, 4)[1:]
            r11, r21, r31 = (partial(e.ar, delta, tau, k, 1) for k in (1, 2, 3))
            f1 = 1 + 2 * delta * r1 + delta**2 * r2
            f2 = 2 * r1 + 4 * delta * r2 + delta**2 * r3
            j11, j12 = f2, 2 * delta * r11 + delta**2 * r21
            j21, j22 = (
                6 * r2 + 6 * delta * r3 + delta**2 * r4,
                2 * r11 + 4 * delta * r21 + delta**2 * r31,
            )
            det = j11 * j22 - j12 * j21
            dd = (-f1 * j22 + f2 * j12) / det
            dt = (-f2 * j11 + f1 * j21) / det
            delta, tau = delta + dd, tau + dt
            if abs(dd) <= tol * delta and abs(dt) <= tol * tau:
                break
        else:
            raise ClaimFailedError("C5: the critical-point Newton did not converge")
        tc, rc = e.Tr / tau, delta * e.rr
        r1, r2, r3 = diffs(lambda x: e.ar(x, tau), delta, 3)[1:]
        rt = e.Rm * tc
        pc = rc * rt * (1 + delta * r1)
        p_rho = rt * (1 + 2 * delta * r1 + delta**2 * r2)
        p_rhorho = rt / e.rr * (2 * r1 + 4 * delta * r2 + delta**2 * r3)
        self.crit_check = (
            abs(p_rho) * rc / pc,
            abs(p_rhorho) * rc**2 / pc,
            rel(tc, a.T_critical()),
        )
        self.Tc_mp, self.pc_mp, self.rhoc_mp = tc, pc, rc
        self.T_c, self.p_c, self.rho_c = dbl(tc), dbl(pc), dbl(rc)

    def bounds(self) -> None:
        """T_hi, P_hi, T_lo and the bound kind (§16.4), with C9's grid data."""
        e, a = self.eos, self.cp
        self.T_hi = min(e.T_max, T_CAP)
        self.T_t, self.p_t = a.Ttriple(), a.p_triple()
        self.melt: dict[str, Any] = {}
        if a.has_melting_line():
            self.P_hi = min(e.p_max, P_CAP)
            p_mmin = a.melting_line(CP.iP_min, -1, -1)
            p_mmax = a.melting_line(CP.iP_max, -1, -1)
            p0 = max(self.p_t, P_LO, p_mmin)
            grid = [float(mpf(p0) * (mpf(self.P_hi) / p0) ** (mpf(i) / 19)) for i in range(20)]
            grid[-1] = self.P_hi
            tm = [a.melting_line(CP.iT, CP.iP, p) for p in grid]
            self.melt = {"p_min": p_mmin, "p_max": p_mmax, "grid": grid, "T_m": tm}
            if max(tm) <= self.T_t:
                self.bound = "T"
                self.T_lo = self.T_t
            else:
                self.bound = "M"
                self.T_lo = ceil_tenth(dec(tm[-1]))
        else:
            self.bound = "E"
            self.P_hi = min(e.p_max, max(P_FLOOR, ceil_sig(dec(scaled(self.p_c, "1.1")), 2)))
            with localcontext() as ctx:
                ctx.prec = 60
                self.T_lo = ceil_tenth(dec(self.T_t) * (1 + Decimal(KAPPA) * dec(self.P_hi)))

    def exclusion(self) -> str | None:
        """S3 and S4 (§16.1)."""
        if not self.T_lo < scaled(self.T_c, "0.99"):
            return "S3"
        if not (
            self.T_hi > scaled(self.T_c, NC_T_HI_FACTOR)
            and self.P_hi > scaled(self.p_c, NC_P_HI_FACTOR)
        ):
            return "S4"
        return None

    def c9(self) -> list[float]:
        """C9 as amended (§16.4, E2); returns the relative melting slopes for C18."""
        if self.bound == "E":
            return []
        m = self.melt
        tm, grid = m["T_m"], m["grid"]
        claim(
            "C9",
            m["p_max"] >= self.P_hi,
            f"the melting line reaches P_hi ({m['p_max']!r} >= {self.P_hi!r})",
        )
        claim(
            "C9",
            grid[0] == max(self.p_t, P_LO, m["p_min"]),
            "the grid starts at max(p_t, P_lo, p_m,min)",
        )
        if self.bound == "M":
            claim(
                "C9",
                all(tm[i + 1] > tm[i] for i in range(19)),
                "M: T_m increases strictly on the grid",
            )
            claim("C9", tm[-1] <= self.T_lo, "M: T_m(P_hi) <= T_lo")
        else:
            claim("C9", all(t <= self.T_t for t in tm), "T: T_m <= T_t on the grid")
            claim(
                "C9",
                all(tm[i + 1] <= tm[i] for i in range(19)),
                "T: T_m non-increasing on the grid",
            )
        if self.bound != "M" or self.T_t < 20:
            return []
        return [
            (t / self.T_t - 1) / (p - self.p_t)
            for t, p in zip(tm, grid, strict=True)
            if p > self.p_t
        ]

    def constants(self) -> None:
        self.T_smax = scaled(self.T_c, T_SIGMA_FACTOR)
        self.nc_T = (self.T_smax, scaled(self.T_c, NC_T_HI_FACTOR))
        self.nc_P = (scaled(self.p_c, NC_P_LO_FACTOR), scaled(self.p_c, NC_P_HI_FACTOR))
        self.T_mid = dbl((mpf(self.T_lo) + mpf(self.T_smax)) / 2)

    # -- solves on doubles --

    def sat(self, temp: float) -> dict[str, Any]:
        """The 50-digit saturation state at the double T (memoized)."""
        if temp not in self._sat:
            e = self.eos
            t = mpf(temp)
            rl, rv = e.saturation(t, *self.seeds.sat(temp))
            liq, vap = e.at_rho(t, rl), e.at_rho(t, rv)
            self._sat[temp] = {"T": temp, "rl": rl, "rv": rv, "psat": liq["p"], "L": liq, "V": vap}
        return self._sat[temp]

    def psat_mp(self, t: Any, seed: tuple[Any, Any]) -> Any:
        rl, _ = self.eos.saturation(t, *seed)
        return self.eos.at_rho(t, rl)["p"]

    def phase_rule(self, temp: float, pres: float, ps: Any | None) -> tuple[str, ...] | str:
        """§6.3 (S05 §4.2 with §6.1's constants)."""
        if not (self.T_lo <= temp <= self.T_hi and P_LO <= pres <= self.P_hi):
            return "out_of_domain"
        if self.nc_T[0] < temp < self.nc_T[1] and self.nc_P[0] <= pres <= self.nc_P[1]:
            return "near_critical"
        if temp >= self.T_c:
            return ("VAPOR",)
        if temp > self.T_smax:
            if pres >= self.p_c:
                return ("LIQUID",)
            return ("VAPOR",) if pres < self.nc_P[0] else "near_critical"
        z = mp.log(mpf(pres) / ps)
        return tuple(
            ph for ph, ok in (("LIQUID", z >= -EPS_SIGMA), ("VAPOR", z <= EPS_SIGMA)) if ok
        )

    def ps_at(self, temp: float) -> Any | None:
        return self.sat(temp)["psat"] if self.T_lo <= temp <= self.T_smax else None

    def tp_values(self, temp: Any, pres: Any, seed: Any, lo: Any, hi: Any) -> dict[str, Any]:
        r = self.eos.rho_root(temp, pres, seed, lo, hi)
        out = self.eos.at_rho(temp, r)
        out["rho"] = r
        return out

    def cdiff(self, f: Callable[[Any], dict[str, Any]], x: Any) -> dict[str, Any]:
        """Central difference at 110 digits, h = 1e-45 relative (S05)."""
        with mp.workdps(110):
            h = abs(x) * mpf("1e-45")
            fp, fm = f(x + h), f(x - h)
            out = {k: (fp[k] - fm[k]) / (2 * h) for k in fp if k in PROPS}
        return {k: +v for k, v in out.items()}

    def compute(self) -> dict[str, Any]:  # noqa: C901 - the generator's plan, in order
        e = self.eos
        res: dict[str, Any] = {}
        claim("C1", e.n_eos >= 1 and e.supported, "EOS[0]'s term types are in §2.2/§16.2")
        claim(
            "C2", fluid_data_sha256(self.name) == e.sha, "fluid_data_sha256 stable across two reads"
        )
        claim(
            "C15",
            ID_PATTERN.match(self.id) is not None,
            f"id {self.id} matches the component pattern",
        )
        self.critical()
        k1, k2, k3 = self.crit_check
        claim(
            "C5",
            k1 < mpf("1e-20") and k2 < mpf("1e-20"),
            f"critical point ({dbl(k1):.2e}, {dbl(k2):.2e})",
        )
        claim("C5", k3 < mpf("1e-3"), f"T_c within 1e-3 of T_critical() ({dbl(k3):.2e})")
        self.bounds()
        ex = self.exclusion()
        if ex is not None:
            return {"excluded_by": ex}
        slopes = self.c9()
        self.constants()

        # rho_max: the LIQUID root at (T_lo, P_hi), seeded by CoolProp
        t_lo, p_hi = mpf(self.T_lo), mpf(self.P_hi)
        sat_lo = self.sat(self.T_lo)
        claim("C8", sat_lo["psat"] < p_hi, "p_sigma(T_lo) < P_hi")
        r_corner = e.rho_root(
            t_lo, p_hi, self.seeds.rho(self.T_lo, self.P_hi), sat_lo["rl"], 10 * sat_lo["rl"]
        )
        self.rho_max = ceil_sig(Decimal("1.10") * dec(dbl(r_corner)), 3)
        rmax = mpf(self.rho_max)

        # saturation at T_lo, T_mid, T_sigma,max (C6, C7)
        sat_mid, sat_hi = self.sat(self.T_mid), self.sat(self.T_smax)
        sats = {"sat_lo": sat_lo, "sat_mid": sat_mid, "sat_hi": sat_hi}
        for s in sats.values():
            claim("C13", s["rl"] > self.rhoc_mp > s["rv"], f"rho' > rho_c > rho'' at {s['T']!r} K")
        claim("C6", sat_hi["psat"] > mpf(self.nc_P[0]), "p_sigma(T_sigma,max) > p_c (1 - 4e-3)")
        claim(
            "C6",
            self.nc_T[0] < self.T_c < self.nc_T[1] and self.nc_P[0] <= self.p_c <= self.nc_P[1],
            "the critical point lies inside the near-critical box",
        )
        t_s = mpf(self.T_smax)
        for ph, k in (("LIQUID", -1), ("VAPOR", 1)):
            p = sat_hi["psat"] * mp.exp(k * mpf(EPS_SIGMA))
            if ph == "LIQUID":
                r = e.rho_root(t_s, p, sat_hi["rl"], self.rhoc_mp, rmax)
                ok = sat_hi["rl"] > r > self.rhoc_mp
            else:
                r = e.rho_root(t_s, p, sat_hi["rv"], mpf(0), self.rhoc_mp)
                ok = sat_hi["rv"] < r < self.rhoc_mp
            claim("C7", ok, f"the metastable {ph} root at T_sigma,max lies on its branch")

        # the registered TP states (§7; §16.6's clamps for every fluid)
        tc, pc = self.T_c, self.p_c
        ps_mid = sat_mid["psat"]
        rule_states = {
            "V_sup": (min(scaled(tc, "1.5"), self.T_hi), scaled(pc, "0.1"), "VAPOR"),
            "V_sub": (self.T_mid, dbl(ps_mid / 2), "VAPOR"),
            "L_sub": (self.T_mid, dbl(ps_mid * 2), "LIQUID"),
            "S_dense": (
                min(scaled(tc, "1.2"), self.T_hi),
                min(scaled(pc, "3"), self.P_hi),
                "VAPOR",
            ),
            "L_corner": (self.T_lo, self.P_hi, "LIQUID"),
            "V_corner": (self.T_hi, P_LO, "VAPOR"),
        }
        if self.tier == "A":
            unclamped = {
                "V_sup": (scaled(tc, "1.5"), scaled(pc, "0.1")),
                "S_dense": (scaled(tc, "1.2"), scaled(pc, "3")),
            }
            for k, (t_, p_) in unclamped.items():
                claim(
                    "C10", rule_states[k][:2] == (t_, p_), f"tier A: {k} equals §7's unclamped rule"
                )
            t_nc = scaled(tc, "0.9995")
            sat_nc = self.sat(t_nc)
            rule_states["NC_V"] = (t_nc, dbl(sat_nc["psat"] * mpf("0.995")), "VAPOR")
            rule_states["NC_L"] = (t_nc, dbl(sat_nc["psat"] * mpf("1.005")), "LIQUID")
        dropped, tp_out, agreement = [], {}, {}
        for name, (temp, pres, phase) in rule_states.items():
            nc = name.startswith("NC_")
            ps = None
            if temp <= self.T_smax:
                ps = (
                    sat_nc["psat"]
                    if nc
                    else (sat_mid["psat"] if temp == self.T_mid else self.ps_at(temp))
                )
            got = self.phase_rule(temp, pres, ps)
            if got in ("out_of_domain", "near_critical"):
                dropped.append(name)
                continue
            claim("C10", got == (phase,), f"{name}: the rule answers {phase} only (got {got})")
            t, p = mpf(temp), mpf(pres)
            if temp >= self.T_c:
                lo, hi = mpf(0), rmax
            else:
                s = sat_nc if nc else self.sat(temp)
                lo, hi = (s["rl"], rmax) if phase == "LIQUID" else (mpf(0), s["rv"])
            vals = self.tp_values(t, p, self.seeds.rho(temp, pres), lo, hi)
            r0 = vals["rho"]
            by_t = self.cdiff(
                lambda x, p=p, r0=r0, lo=lo, hi=hi: self.tp_values(x, p, r0, lo, hi), t
            )
            by_p = self.cdiff(
                lambda x, t=t, r0=r0, lo=lo, hi=hi: self.tp_values(t, x, r0, lo, hi), p
            )
            self.identities(name, t, p, vals, by_t, by_p)
            self.admit(name, temp, pres, vals, nc, agreement)
            row: dict[str, Any] = {
                "phase": phase,
                "values": [temp, pres] + [dbl(vals[k]) for k in PROPS],
            }
            if self.tier == "A":
                row["dT"] = [dbl(by_t[k]) for k in PROPS]
                row["dP"] = [dbl(by_p[k]) for k in PROPS]
            tp_out[name] = row
        claim(
            "C10",
            tuple(dropped) == EXPECTED_DROPPED.get(self.id, ()),
            f"dropped {dropped} equals the literal list",
        )
        claim(
            "C10",
            len({tuple(r["values"][:2]) for r in tp_out.values()}) == len(tp_out),
            "TP states pairwise distinct",
        )
        res["tp_states"], res["dropped"], res["agreement"] = tp_out, dropped, agreement

        # saturation states: I8, I9 (C13); values
        sat_out = {}
        for key, s in sats.items():
            if self.tier == "B" and key != "sat_mid":
                continue
            t = mpf(s["T"])
            seed = (s["rl"], s["rv"])
            slope = self.cdiff(lambda x, seed=seed: {"h": self.psat_mp(x, seed)}, t)["h"]
            liq, vap = s["L"], s["V"]
            claim(
                "C13",
                abs(liq["lnphi"] - vap["lnphi"]) < mpf("1e-30") * max(abs(vap["lnphi"]), 1),
                f"I8 at {s['T']!r} K",
            )
            cc = (vap["s"] - liq["s"]) / (vap["v"] - liq["v"])
            claim("C13", rel(cc, slope) < mpf("1e-30"), f"I9 (Clausius-Clapeyron) at {s['T']!r} K")
            cc_h = (vap["h"] - liq["h"]) / (t * (vap["v"] - liq["v"]))
            claim("C13", rel(cc_h, slope) < mpf("1e-30"), f"I9 (enthalpy form) at {s['T']!r} K")
            row = {"T": s["T"], "Psat": dbl(s["psat"]), "dh_vap": dbl(vap["h"] - liq["h"])}
            if self.tier == "A":
                row["dPsat_dT"] = dbl(slope)
                row["L"] = [s["T"], dbl(s["psat"])] + [dbl(liq[k]) for k in PROPS]
                row["V"] = [s["T"], dbl(s["psat"])] + [dbl(vap[k]) for k in PROPS]
            sat_out[key] = row
        res["saturation"] = sat_out

        # tsat_mid: P = p_sigma(T_mid) to 6 significant digits
        p6 = float(f"{dbl(ps_mid):.5e}")
        tsat = self.tsat_solve(mpf(p6), mpf(self.seeds.tsat(p6)), (sat_mid["rl"], sat_mid["rv"]))
        row = {"P": p6, "Tsat": dbl(tsat["T"])}
        if self.tier == "A":
            row["dTsat_dP"] = dbl(1 / tsat["slope"])
        res["tsat"] = {"tsat_mid": row}

        # band probes at T_mid (§7)
        band = {}
        expect = {
            "-2": ("VAPOR",),
            "-0.5": ("LIQUID", "VAPOR"),
            "0.5": ("LIQUID", "VAPOR"),
            "2": ("LIQUID",),
        }
        t = mpf(self.T_mid)
        for k, want in expect.items():
            pres = dbl(ps_mid * mp.exp(mpf(k) * mpf(EPS_SIGMA)))
            got = self.phase_rule(self.T_mid, pres, ps_mid)
            claim("C14", got == want, f"band {k}: answered {got}")
            row = {
                "P": pres,
                "answered": list(got),
                "refused": [ph for ph in ("LIQUID", "VAPOR") if ph not in got],
            }
            if self.tier == "A":
                for ph in got:
                    seed, lo, hi = (
                        (sat_mid["rl"], self.rhoc_mp, rmax)
                        if ph == "LIQUID"
                        else (sat_mid["rv"], mpf(0), self.rhoc_mp)
                    )
                    v = self.tp_values(t, mpf(pres), seed, lo, hi)
                    row[ph] = [self.T_mid, pres] + [dbl(v[q]) for q in PROPS]
            band[k] = row
        res["band"] = {"T": self.T_mid, "eps_sigma": EPS_SIGMA, "probes": band}

        # phi states (§7) and C4
        phi = {
            "phi_gas": (scaled(e.T_red, "1.5"), scaled(e.rho_red, "0.3")),
            "phi_liq": (scaled(e.T_red, "0.8"), scaled(e.rho_red, "2.4")),
            "phi_dilute": (scaled(e.T_red, "0.95"), scaled(e.rho_red, "0.02")),
        }
        if self.tier == "A" and any(k == "ResidualHelmholtzNonAnalytic" for k, _ in e.ar_terms):
            phi["delta_one"] = (scaled(e.T_red, "0.9"), e.rho_red)
        phi_out = {}
        for key, (temp, rho) in phi.items():
            zj = key == "delta_one"
            if zj:
                claim(
                    "C4",
                    mpf(rho) / e.rr == 1 and e.na_zero_jet_valid(),
                    "delta_one: delta = 1, zero-jet rule",
                )
            j50 = e.jet(mpf(temp), mpf(rho), zj)
            with mp.workdps(30):
                j30 = e.jet(mpf(temp), mpf(rho), zj)
            worst = max(abs(a - b) / max(abs(a), 1) for a, b in zip(j50, j30, strict=True))
            claim("C4", worst < mpf("1e-25"), f"{key}: 50 vs 30 digits ({dbl(worst):.1e})")
            phi_out[key] = {"T": temp, "rho": rho, "jet": [dbl(x) for x in j50]}
        res["phi_states"] = phi_out

        # canary (§6.1)
        ct, cr = phi["phi_gas"]
        cj = phi_out["phi_gas"]["jet"]
        res["canary"] = {
            "T": ct,
            "rho": cr,
            "alpha0": cj[0],
            "alpha0_t": cj[3],
            "alphar": cj[10],
            "alphar_d": cj[11],
        }

        # refusal probes (C14)
        res["probes"] = self.probes(sat_lo, sat_hi, rule_states)

        # brackets (C8), at 20 digits
        self.brackets(rmax)

        if self.tier == "A":
            res["s04_ig"] = {}
            for temp in (300.0, 600.0):
                ott = partial(e.a0, 1 / e.rr, e.Tr / mpf(temp), 0, 2)
                res["s04_ig"][repr(temp)] = dbl(e.Rm * (1 - (e.Tr / mpf(temp)) ** 2 * ott))
        if self.id == "H2O":
            res["agreement"].update({f"s05/{k}": v for k, v in self.c12().items()})

        res["constants"] = {
            "T_c": self.T_c,
            "p_c": self.p_c,
            "rho_c": self.rho_c,
            "T_lo": self.T_lo,
            "T_hi": self.T_hi,
            "P_lo": P_LO,
            "P_hi": self.P_hi,
            "T_sigma_max": self.T_smax,
            "nc_T": list(self.nc_T),
            "nc_P": list(self.nc_P),
            "rho_max": self.rho_max,
            "eps_sigma": EPS_SIGMA,
            "R": e.R,
            "M": e.M,
            "T_red": e.T_red,
            "rho_red": e.rho_red,
        }
        res["slopes"] = [dbl(x) for x in slopes]
        return res

    def tsat_solve(self, pres: Any, t0: Any, seed: tuple[Any, Any]) -> dict[str, Any]:
        e = self.eos
        t, (rl, rv) = t0, seed
        tol = mpf(10) ** (8 - mp.dps)
        for _ in range(100):
            rl, rv = e.saturation(t, rl, rv)
            liq, vap = e.at_rho(t, rl), e.at_rho(t, rv)
            slope = (vap["s"] - liq["s"]) / (vap["v"] - liq["v"])
            step = (liq["p"] - pres) / slope
            t -= step
            if abs(step) <= tol * t:
                break
        else:
            raise ClaimFailedError(f"Tsat at {dbl(pres)!r} Pa did not converge")
        rl, rv = e.saturation(t, rl, rv)
        p = e.at_rho(t, rl)["p"]
        claim("C13", rel(p, pres) < mpf(10) ** (10 - mp.dps), "Tsat converged")
        sl = self.cdiff(lambda x: {"h": self.psat_mp(x, (rl, rv))}, t)["h"]
        return {"T": t, "slope": sl}

    def identities(
        self, name: str, t: Any, p: Any, vals: dict[str, Any], by_t: Any, by_p: Any
    ) -> None:
        cp, z, v = vals["cp"], vals["Z"], vals["v"]
        rg = self.eos.Rm
        tol = mpf("1e-30")
        for text, lhs, rhs in (
            ("I1 dh/dT|P = cp", by_t["h"], cp),
            ("I2 ds/dT|P = cp/T", by_t["s"], cp / t),
            ("I3 ds/dP|T = -dv/dT|P", by_p["s"], -by_t["v"]),
            ("I4 dh/dP|T = v - T dv/dT|P", by_p["h"], v - t * by_t["v"]),
            ("I5 dlnphi/dP|T = (Z-1)/P", by_p["lnphi"], (z - 1) / p),
            ("I6 dlnphi/dT|P = -(h - h_ig)/(R T^2)", by_t["lnphi"], -vals["h_res"] / (rg * t**2)),
            ("I7 dZ/dP|T from Z = Pv/(RT)", by_p["Z"], (z / p) * (1 + p * by_p["v"] / v)),
        ):
            claim("C13", rel(lhs, rhs) < tol, f"{name}: {text} ({dbl(rel(lhs, rhs)):.1e})")
        claim("C13", by_p["v"] < 0 and cp > 0, f"{name}: mechanically and thermally stable")

    def admit(
        self, name: str, temp: float, pres: float, vals: dict[str, Any], nc: bool, agreement: dict
    ) -> None:
        """C11: CoolProp's own flash against the generator (never an expectation)."""
        try:
            got = self.seeds.flash(temp, pres)
        except Exception as ex:  # noqa: BLE001 - a CoolProp exception fails the claim
            raise ClaimFailedError(
                f"C11: {name}: CoolProp's flash raised: {str(ex)[:120]}"
            ) from None
        bound = mpf("1e-5") if nc else mpf("1e-7")
        rg = self.eos.Rm
        errs = {
            "h": abs(mpf(got["h"]) - vals["h"]) / (rg * mpf(temp)),
            "s": abs(mpf(got["s"]) - vals["s"]) / rg,
            "v": rel(1 / mpf(got["rho"]), vals["v"]),
            "Z": rel(mpf(got["Z"]), vals["Z"]),
            "cp": rel(mpf(got["cp"]), vals["cp"]),
            "lnphi": abs(mpf(got["lnphi"]) - vals["lnphi"]),
        }
        sec = "nc" if nc else "tp"
        for k, err in errs.items():
            claim(
                "C11",
                err <= bound,
                f"{name}: CoolProp's {k} within {dbl(bound)} (got {dbl(err):.2e})",
            )
            key = f"{sec}/{k}"
            agreement[key] = max(agreement.get(key, 0.0), float(mp.nstr(err, 3)))

    def probes(self, sat_lo: dict, sat_hi: dict, states: dict) -> list[dict[str, Any]]:
        """The refusal probes of §9 A14–A16, A18, A21 by rule from §6.1's constants (C14)."""
        t_lo, t_hi, p_hi, t_sm, t_c, pc = (
            self.T_lo,
            self.T_hi,
            self.P_hi,
            self.T_smax,
            self.T_c,
            self.p_c,
        )

        def below(x: float) -> float:
            return scaled(x, str(1 - Decimal(PROBE_REL)))

        def above(x: float) -> float:
            return scaled(x, str(1 + Decimal(PROBE_REL)))

        ps_lo, ps_hi = dbl(sat_lo["psat"]), dbl(sat_hi["psat"])
        t_strip = dbl((mpf(t_sm) + mpf(t_c)) / 2)
        t_nc = dbl((mpf(self.nc_T[0]) + mpf(self.nc_T[1])) / 2)
        claim(
            "C14",
            t_sm < t_strip < t_c and self.nc_T[0] < t_nc < self.nc_T[1],
            "strip and box probes inside",
        )
        tsat_lo_bound = max(ps_lo, P_LO)
        sd = states["S_dense"]
        mid = self.T_mid
        band_p = {
            k: dbl(self.sat(mid)["psat"] * mp.exp(mpf(k) * mpf(EPS_SIGMA)))
            for k in ("-2", "-0.5", "0.5", "2")
        }

        def ph(temp: float, pres: float, phase: str, **kw: Any) -> dict[str, Any]:
            return {"kind": "evaluate_phase", "T": temp, "P": pres, "phase": phase, **kw}

        def fl(temp: float, pres: float) -> dict[str, Any]:
            return {"kind": "flash", "T": temp, "P": pres}

        rows: list[tuple[str, dict, dict]] = [
            # A16: the four box edges, for evaluate_phase and flash; Psat and Tsat
            ("A16", ph(below(t_lo), p_hi, "LIQUID"), ph(t_lo, p_hi, "LIQUID")),
            ("A16", ph(above(t_hi), P_LO, "VAPOR"), ph(t_hi, P_LO, "VAPOR")),
            ("A16", ph(t_hi, below(P_LO), "VAPOR"), ph(t_hi, P_LO, "VAPOR")),
            ("A16", ph(t_lo, above(p_hi), "LIQUID"), ph(t_lo, p_hi, "LIQUID")),
            ("A16", fl(below(t_lo), p_hi), fl(t_lo, p_hi)),
            ("A16", fl(above(t_hi), P_LO), fl(t_hi, P_LO)),
            ("A16", fl(t_hi, below(P_LO)), fl(t_hi, P_LO)),
            ("A16", fl(t_lo, above(p_hi)), fl(t_lo, p_hi)),
            ("A16", {"kind": "Psat", "T": below(t_lo)}, {"kind": "Psat", "T": t_lo}),
            ("A16", {"kind": "Psat", "T": above(t_hi)}, {"kind": "Psat", "T": t_sm}),
            (
                "A16",
                {"kind": "Tsat", "P": below(P_LO)},
                {"kind": "Tsat", "P": above(tsat_lo_bound)},
            ),
            ("A16", {"kind": "Tsat", "P": above(p_hi)}, {"kind": "Tsat", "P": below(ps_hi)}),
            # A14: near_critical, both phases and the flash, and the strip's LIQUID side
            ("A14", ph(t_nc, pc, "VAPOR"), ph(self.nc_T[1], pc, "VAPOR")),
            ("A14", ph(t_nc, pc, "LIQUID"), ph(self.nc_T[1], pc, "VAPOR")),
            ("A14", fl(t_nc, pc), fl(self.nc_T[1], pc)),
            ("A14", ph(t_strip, self.nc_P[0], "LIQUID"), ph(t_strip, below(self.nc_P[0]), "VAPOR")),
            # A15: the T >= T_c label and the (T_sigma,max, T_c) strip; the edge at T_sigma,max
            ("A15", ph(sd[0], sd[1], "LIQUID"), ph(sd[0], sd[1], "VAPOR")),
            (
                "A15",
                ph(t_strip, below(self.nc_P[0]), "LIQUID"),
                ph(t_strip, below(self.nc_P[0]), "VAPOR"),
            ),
            (
                "A15",
                ph(t_strip, above(self.nc_P[1]), "VAPOR"),
                ph(t_strip, above(self.nc_P[1]), "LIQUID"),
            ),
            ("A15", ph(t_sm, pc, "VAPOR"), ph(t_sm, pc, "LIQUID")),
            ("A13", ph(mid, band_p["-2"], "LIQUID"), ph(mid, band_p["-0.5"], "LIQUID")),
            ("A13", ph(mid, band_p["2"], "VAPOR"), ph(mid, band_p["0.5"], "VAPOR")),
            # A18: no_saturation
            ("A18", {"kind": "Psat", "T": above(t_sm)}, {"kind": "Psat", "T": t_sm}),
            ("A18", {"kind": "Psat", "T": t_hi}, {"kind": "Psat", "T": t_sm}),
            ("A18", {"kind": "Tsat", "P": above(ps_hi)}, {"kind": "Tsat", "P": below(ps_hi)}),
        ]
        if below(ps_lo) >= P_LO:
            rows.append(
                ("A18", {"kind": "Tsat", "P": below(ps_lo)}, {"kind": "Tsat", "P": above(ps_lo)})
            )
        # A21: the contract refusals 1, 2, 3, 6 at V_sup, with valid controls
        vs = states["V_sup"]
        other = "n_N2" if self.id == "H2O" else "n_H2O"
        base = ph(vs[0], vs[1], "VAPOR")
        rows += [
            ("A21", {**base, "derivatives": [other]}, {**base, "derivatives": [f"n_{self.id}"]}),
            ("A21", {**base, "property": "g"}, {**base, "property": "h"}),
            ("A21", {**base, "n": [1.0, 0.0]}, {**base, "n": [1.0]}),
            ("A21", {**base, "n": [0.0]}, {**base, "n": [1.0]}),
        ]
        out = []
        for a, probe, control in rows:
            code = self.expect(probe)
            claim("C14", self.expect(control) == "ok", f"{a}: the control of {probe} is answered")
            claim("C14", code in INTENDED[a], f"{a}: {probe} expects {code}")
            out.append([a, code, compact_request(probe), compact_request(control)])
        codes = {r[1] for r in out}
        want = {
            "undeclared_derivative_input",
            "unknown_property",
            "state_length",
            "out_of_domain",
            "dormant_state",
            "no_saturation",
            "near_critical",
            "phase_not_stable",
        }
        claim("C14", codes == want, f"the probes cover §6.5 rows 1-3 and 5-9 ({sorted(codes)})")
        return out

    def expect(self, q: dict[str, Any]) -> str:
        """§6.5's precedence (rows 1-3 and 5-9) for one request; 'ok' when it is answered."""
        if any(d not in ("T", "P", f"n_{self.id}") for d in q.get("derivatives", [])):
            return "undeclared_derivative_input"
        if q.get("property", "h") not in (
            "h",
            "s",
            "v",
            "Z",
            "cp",
            f"lnphi_{self.id}",
            "Psat",
            "Tsat",
        ):
            return "unknown_property"
        n = q.get("n", [1.0])
        if len(n) != 1:
            return "state_length"
        kind = q["kind"]
        if kind == "Psat":
            temp = q["T"]
            if not self.T_lo <= temp <= self.T_hi:
                return "out_of_domain"
            return "ok" if temp <= self.T_smax else "no_saturation"
        if kind == "Tsat":
            pres = q["P"]
            if not P_LO <= pres <= self.P_hi:
                return "out_of_domain"
            lo = max(dbl(self.sat(self.T_lo)["psat"]), P_LO)
            hi = dbl(self.sat(self.T_smax)["psat"])
            return "ok" if lo <= pres <= hi else "no_saturation"
        temp, pres = q["T"], q["P"]
        got = self.phase_rule(
            temp, pres, None if not self.T_lo <= temp <= self.T_smax else self.sat(temp)["psat"]
        )
        if got == "out_of_domain":
            return got
        if n[0] == 0:
            return "dormant_state"
        if isinstance(got, str):
            return got
        if kind == "flash":
            return "ok"
        return "ok" if q["phase"] in got else "phase_not_stable"

    def brackets(self, rmax: Any) -> None:
        """C8 (§6.4, S05 §4.4): 41 points per bracket at 23 + 8 temperatures.

        The saturation and band-edge roots are solved at 50 digits: at T_lo a liquid's Z can be
        ~1e-12, so p(rho) cancels about 12 digits. The dp/drho signs are evaluated at 20 digits,
        as S05's grid was.
        """
        e = self.eos
        sub = [
            dbl(mpf(self.T_lo) + (mpf(self.T_smax) - mpf(self.T_lo)) * i / 22) for i in range(23)
        ]
        t0 = scaled(self.T_c, NC_T_HI_FACTOR)
        sup = [dbl(mpf(t0) + (mpf(self.T_hi) - mpf(t0)) * i / 7) for i in range(8)]
        sub[0], sub[-1], sup[-1] = self.T_lo, self.T_smax, self.T_hi
        ph = mpf(self.P_hi)
        grids: list[tuple[float, list[tuple[Any, Any]]]] = []
        for temp in sub:
            t = mpf(temp)
            s = self.sat(temp)
            rl, rv = s["rl"], s["rv"]
            hi_v = e.rho_root(t, s["psat"] * mp.exp(mpf(EPS_SIGMA)), rv, mpf(0), self.rhoc_mp)
            lo_l = e.rho_root(t, s["psat"] * mp.exp(-mpf(EPS_SIGMA)), rl, self.rhoc_mp, rmax)
            claim(
                "C8",
                rv < hi_v < self.rhoc_mp < lo_l < rl,
                f"band-edge roots on their branches at {temp!r} K",
            )
            grids.append((temp, [(hi_v / 40, hi_v), (lo_l, rmax)]))
        for temp in sup:
            grids.append((temp, [(rmax / 60, rmax)]))
        with mp.workdps(20):
            for temp, intervals in grids:
                t = mpf(temp)
                for a, b in intervals:
                    for i in range(41):
                        r = +a + (+b - a) * i / 40
                        claim(
                            "C8",
                            e.pd(t, r)[1] > 0,
                            f"dp/drho > 0 at {temp!r} K, {dbl(r):.6g} mol/m3",
                        )
                claim("C8", e.pd(t, rmax)[0] > ph, f"p(rho_max, {temp!r} K) > P_hi")

    def c12(self) -> dict[str, float]:
        """C12: water against s05_reference.json at S05's states with T <= 646.9 K."""
        s05 = json.loads(S05_PATH.read_text(encoding="utf-8"))
        e = self.eos
        worst: dict[str, float] = {}

        def check(key: str, mine: Any, ref: str) -> None:
            err = rel(mine, mpf(ref))
            claim(
                "C12", err < mpf("1e-12"), f"water {key} equals S05 within 1e-12 ({dbl(err):.1e})"
            )
            q = key.split("/")[-1]
            worst[q] = max(worst.get(q, 0.0), float(mp.nstr(err, 3)))

        m = mpf(e.M)
        for name, row in s05["phi_states"].items():
            t, rho = mpf(float(row["T"])), mpf(float(row["rho"])) / m
            if t > mpf("646.9"):
                continue
            zj = name == "delta_one"
            jet = e.jet(t, rho, zj)
            for slot, ((i, j), suf) in enumerate(zip(JET, S05_SUFFIX, strict=True)):
                for label, off in (("phi0", 0), ("phir", 10)):
                    k = label + suf
                    if k in row and not (label == "phi0" and i and j):
                        check(f"phi/{name}/{k}", jet[off + slot], row[k])
        for name, row in s05["tp_states"].items():
            temp, pres = float(row["T"]), float(row["P"])
            if temp > 646.9:
                continue
            v = self.tp_values(mpf(temp), mpf(pres), mpf(row["rho"]) / m, mpf(0), mpf(10) ** 9)
            for k in PROPS:
                check(f"tp/{name}/{k}", v[k], row["lnphi_H2O" if k == "lnphi" else k])
        for t_, row in s05["saturation"].items():
            temp = float(t_)
            if temp > 646.9:
                continue
            rl, rv = e.saturation(mpf(temp), mpf(row["rho_l"]) / m, mpf(row["rho_v"]) / m)
            check(f"sat/{t_}/Psat", e.at_rho(mpf(temp), rl)["p"], row["Psat"])
        return worst


#: The codes each probe family exists to reach (§9 A13–A16, A18, A21).
INTENDED: dict[str, frozenset[str]] = {
    "A13": frozenset({"phase_not_stable"}),
    "A14": frozenset({"near_critical"}),
    "A15": frozenset({"phase_not_stable"}),
    "A16": frozenset({"out_of_domain"}),
    "A18": frozenset({"no_saturation"}),
    "A21": frozenset(
        {"undeclared_derivative_input", "unknown_property", "state_length", "dormant_state"}
    ),
}


def compact_request(q: dict[str, Any]) -> list[Any]:
    """A probe or control as one list: [kind, T, P, phase] for evaluate_phase (A21's rows add a
    field name and its value), [kind, T, P] for flash, [kind, T] for Psat, [kind, P] for Tsat."""
    kind = q["kind"]
    if kind == "Psat":
        return [kind, q["T"]]
    if kind == "Tsat":
        return [kind, q["P"]]
    if kind == "flash":
        return [kind, q["T"], q["P"]]
    out = [kind, q["T"], q["P"], q["phase"]]
    for k in ("derivatives", "property", "n"):
        if k in q:
            out += [k, q[k]]
    return out


def run_fluid(name: str) -> tuple[str, str, Any]:
    """Worker: ('ok', result), ('excluded', rule) or ('failed', reason)."""
    claim.counts = {}
    try:
        f = Fluid(name)
        e = f.eos
        if e.pseudo_pure:
            return name, "excluded", {"rule": "S1", "claims": {}}
        if not e.supported:
            bad = sorted((set(e.types0) - A0_TYPES) | (set(e.typesr) - AR_TYPES))
            return name, "excluded", {"rule": "S2", "types": bad, "claims": {}}
        t0 = time.process_time()
        res = f.compute()
        if "excluded_by" in res:
            return name, "excluded", {"rule": res["excluded_by"], "claims": dict(claim.counts)}
        res["claims"] = dict(claim.counts)
        res["cpu_s"] = round(time.process_time() - t0, 1)
        res["meta"] = {
            "id": f.id,
            "name": name,
            "cas": e.cas,
            "bibtex_eos": e.bibtex,
            "tier": f.tier,
            "bound": f.bound,
            "fluid_data_sha256": e.sha,
            "n_eos": e.n_eos,
        }
        return name, "ok", res
    except ClaimFailedError as ex:
        return name, "failed", {"reason": str(ex)}
    except Exception as ex:  # noqa: BLE001 - every failure is reported with the fluid's name
        return (
            name,
            "failed",
            {"reason": f"exception: {ex!r}", "trace": traceback.format_exc()[-800:]},
        )


# -- assembly -------------------------------------------------------------------------------------


def verification(cid: str, tier: str, checks: dict[str, Any]) -> str:
    if cid == "H2O":
        return "independent:S05"
    if tier == "A":
        return "independent:S04-ig"
    return "published-check" if checks.get(cid, {}).get("qualifies") else "self-consistent"


def published_checks() -> tuple[str, dict[str, Any]]:
    raw = CHECKS_PATH.read_bytes()
    doc = yaml.safe_load(raw)
    rows = doc.get("rows")
    claim("C16", isinstance(rows, list), "published_checks.yaml has a rows list")
    claim("C16", rows == [], "no published check rows (Q-A1-3 default); C16 has nothing to judge")
    return hashlib.sha256(raw).hexdigest(), {}


TOP_KEYS = {
    "schema",
    "coolprop_version",
    "coolprop_gitrevision",
    "fluids",
    "excluded",
    "published_checks",
    "claims",
}
FLUID_KEYS_B = {
    "name",
    "cas",
    "bibtex_eos",
    "tier",
    "bound",
    "verification",
    "limitations",
    "fluid_data_sha256",
    "constants",
    "canary",
    "phi_states",
    "tp_states",
    "saturation",
    "tsat",
    "band",
    "probes",
    "dropped",
    "agreement",
}
FLUID_KEYS_A = FLUID_KEYS_B | {"s04_ig"}


def whitelist(doc: dict[str, Any]) -> None:
    """C3: the key set equals the schema's whitelist, and no list is a coefficient array."""
    claim("C3", set(doc) == TOP_KEYS, f"top-level keys {sorted(set(doc) ^ TOP_KEYS)}")
    for cid, f in doc["fluids"].items():
        want = FLUID_KEYS_A if f["tier"] == "A" else FLUID_KEYS_B
        claim("C3", set(f) == want, f"{cid}: fluid keys {sorted(set(f) ^ want)}")
        for k, row in f["phi_states"].items():
            ok = set(row) == {"T", "rho", "jet"} and len(row["jet"]) == 20
            claim("C3", ok, f"{cid}/{k}: jet layout")
        for k, row in f["tp_states"].items():
            keys = {"phase", "values", "dT", "dP"} if f["tier"] == "A" else {"phase", "values"}
            claim("C3", set(row) == keys and len(row["values"]) == 8, f"{cid}/{k}: TP layout")


def build(jobs: int, report: Path | None) -> tuple[bytes, bytes]:
    claim("C2", CoolProp.__version__ == PINNED_VERSION, "CoolProp 8.0.0")
    claim(
        "C2", CP.get_global_param_string("gitrevision") == PINNED_GITREVISION, "pinned gitrevision"
    )
    names = CP.get_global_param_string("FluidsList").split(",")
    t0 = time.time()
    with Pool(jobs) as pool:
        results = sorted(pool.imap_unordered(run_fluid, names, chunksize=1))
    wall = time.time() - t0
    status = {n: (st, r) for n, st, r in results}
    failed = {n: r for n, (st, r) in status.items() if st == "failed"}
    if report is not None:
        rep: dict[str, Any] = {}
        for n, (st, r) in status.items():
            row = {"status": st}
            for k in ("reason", "rule", "cpu_s", "trace"):
                if k in r:
                    row[k] = r[k]
            rep[n] = row
        text = json.dumps({"wall_s": round(wall, 1), "fluids": rep}, indent=1, sort_keys=True)
        report.write_text(text + "\n")
    if failed:
        lines = "\n".join(f"  {n}: {r['reason']}" for n, r in sorted(failed.items()))
        raise ClaimFailedError(f"S5: {len(failed)} fluid(s) failed a claim:\n{lines}")

    # C15: the admitted, excluded and bound lists
    admitted = {n for n in names if status[n][0] == "ok"}
    literal = {n for _, n, _ in FLUIDS}
    claim("C15", admitted == literal, f"admitted list ({sorted(admitted ^ literal)})")
    excl = {n: status[n][1]["rule"] for n in names if status[n][0] == "excluded"}
    claim("C15", excl == {n: r for n, (r, _) in EXCLUDED.items()}, f"excluded list {excl}")
    for cid, n, bound in FLUIDS:
        meta = status[n][1]["meta"]
        claim("C15", meta["id"] == cid and meta["bound"] == bound, f"{n}: id {cid}, bound {bound}")
    claim("C15", len({f[0] for f in FLUIDS}) == len(FLUIDS), "ids unique")
    cas = [status[n][1]["meta"]["cas"] for _, n, _ in FLUIDS]
    claim("C15", all(cas) and len(set(cas)) == len(cas), "CAS numbers present and unique")

    # C18: kappa against the M fluids' melting slopes
    slopes = {n: max(status[n][1]["slopes"]) for _, n, _ in FLUIDS if status[n][1]["slopes"]}
    worst = max(slopes, key=lambda n: slopes[n])
    claim("C18", float(KAPPA) >= 1.5 * slopes[worst], f"kappa {KAPPA} >= 1.5 x {slopes[worst]:.3e}")

    checks_sha, checks = published_checks()
    fluids: dict[str, Any] = {}
    for cid, n, bound in FLUIDS:
        r = status[n][1]
        m = r["meta"]
        entry = {
            "name": n,
            "cas": m["cas"],
            "bibtex_eos": m["bibtex_eos"],
            "tier": m["tier"],
            "bound": bound,
            "verification": verification(cid, m["tier"], checks),
            "limitations": [E_LIMITATION] if bound == "E" else [],
            "fluid_data_sha256": m["fluid_data_sha256"],
        }
        for k in FLUID_KEYS_A if m["tier"] == "A" else FLUID_KEYS_B:
            if k not in entry:
                entry[k] = r[k]
        fluids[cid] = entry
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "coolprop_version": PINNED_VERSION,
        "coolprop_gitrevision": PINNED_GITREVISION,
        "fluids": fluids,
        "excluded": {n: reason for n, (_, reason) in sorted(EXCLUDED.items())},
        "published_checks": {"sha256": checks_sha, "rows": checks},
    }
    doc["claims"] = {}
    whitelist(doc)
    claim("C17", True, "the output size is checked after encoding")  # counted once, asserted below
    counts = dict(claim.counts)
    for _, r in status.values():
        for k, v in r.get("claims", {}).items():
            counts[k] = counts.get(k, 0) + v
    statements = dict(CLAIM_TEXT)
    statements["C18"] += f" (measured: {slopes[worst]:.3e} /Pa, {worst})"
    order = sorted(CLAIM_TEXT, key=lambda x: int(x[1:]))
    doc["claims"] = {
        "count": sum(counts.values()),
        "names": {k: {"count": counts.get(k, 0), "statement": statements[k]} for k in order},
    }
    payload = encode(doc)
    claim("C17", len(payload) <= 1_500_000, f"output size {len(payload)} bytes <= 1.5e6")
    cpu = sum(r.get("cpu_s", 0) for _, r in status.values())
    print(
        f"wall {wall:.0f} s, CPU {cpu:.0f} s; {len(fluids)} fluids; {len(payload)} bytes",
        file=sys.stderr,
    )
    return payload, fluid_table(doc)


def _enc(obj: Any, level: int) -> str:
    """Sorted keys, one key per line; a list of scalars stays on one line (floats as repr)."""
    pad, inner = " " * level, " " * (level + 1)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = (
            f"{inner}{json.dumps(k, ensure_ascii=False)}: {_enc(obj[k], level + 1)}"
            for k in sorted(obj)
        )
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    nested = isinstance(obj, list) and any(isinstance(x, dict | list) for x in obj)
    if nested and (any(isinstance(x, dict) for x in obj) or len(json.dumps(obj)) > 200):
        return "[\n" + ",\n".join(inner + _enc(x, level + 1) for x in obj) + "\n" + pad + "]"
    return json.dumps(obj, ensure_ascii=False)


def encode(doc: dict[str, Any]) -> bytes:
    text = _enc(doc, 0) + "\n"
    if json.loads(text) != doc:
        raise ClaimFailedError("C3: the encoding does not round-trip")
    return text.encode("utf-8")


# -- the fluid table module (§16.8; C19) ----------------------------------------------------------


def _q(s: str) -> str:
    """A double-quoted Python string literal (the repository's ruff format style)."""
    return json.dumps(s, ensure_ascii=False)


def _pystr(s: str, indent: int) -> str:
    """A string literal, split into implicitly concatenated parts that keep lines <= 100."""
    width = 96 - indent
    if len(_q(s)) <= width:
        return _q(s)
    parts, cur = [], ""
    for word in s.split(" "):
        piece = word + " "
        if len(_q(cur + piece)) > width and cur:
            parts.append(cur)
            cur = ""
        cur += piece
    parts.append(cur[:-1])
    pad = " " * (indent + 4)
    return "(\n" + "".join(f"{pad}{_q(p)}\n" for p in parts) + " " * indent + ")"


def fluid_table(doc: dict[str, Any]) -> bytes:
    lines = [
        '"""The S07 CoolProp HEOS provider\'s per-fluid constants (spec §16.8). Data only.',
        "",
        "Generated by ``docs/derivations/scripts/s07_reference.py --emit-fluid-table``;",
        "do not edit.",
        "Every value equals ``s07_reference.json``'s bitwise (A01, C19).",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any, Final",
        "",
        "#: Per admitted fluid, in spec §16.3's order: identity, tier, bound kind,",
        "#: §6.1's constants, the canary (§5.2 G4) and the describe() strings (§16.8).",
        "FLUIDS: Final[tuple[dict[str, Any], ...]] = (",
    ]
    for cid, _, _ in FLUIDS:
        f = doc["fluids"][cid]
        c = f["constants"]
        entry = {
            "id": cid,
            "name": f["name"],
            "cas": f["cas"],
            "tier": f["tier"],
            "bound": f["bound"],
            "bibtex_eos": f["bibtex_eos"],
            "fluid_data_sha256": f["fluid_data_sha256"],
            **{k: c[k] for k in c},
            "canary": f["canary"],
            "verification": f["verification"],
            "limitations": f["limitations"],
        }
        lines.append("    {")
        for k in sorted(entry):
            v = entry[k]
            if isinstance(v, str):
                lit = _pystr(v, 8)
            elif isinstance(v, list) and v and isinstance(v[0], str):
                lit = "(\n" + "".join(f"            {_pystr(x, 12)},\n" for x in v) + "        )"
            elif isinstance(v, list):
                lit = "(" + ", ".join(repr(x) for x in v) + ("," if len(v) == 1 else "") + ")"
            elif isinstance(v, dict):
                lit = (
                    "{\n"
                    + "".join(f"            {_q(kk)}: {vv!r},\n" for kk, vv in sorted(v.items()))
                    + "        }"
                )
            else:
                lit = repr(v)
            lines.append(f"        {_q(k)}: {lit},")
        lines.append("    },")
    lines.append(")")
    lines.append("")
    lines.append("#: The excluded CoolProp fluids and why (spec §16.1).")
    lines.append("EXCLUDED: Final[dict[str, str]] = {")
    for n, reason in sorted(doc["excluded"].items()):
        lines.append(f"    {_q(n)}: {_pystr(reason, 4)},")
    lines.append("}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="re-derive and byte-compare (C19)")
    parser.add_argument("--emit", metavar="PATH", help="write the reference JSON")
    parser.add_argument("--emit-fluid-table", metavar="PATH", help="write _coolprop_heos_fluids.py")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--report", metavar="PATH", type=Path, help="write each fluid's status")
    parser.add_argument(
        "--fluid", action="append", help="development: run these CoolProp names only"
    )
    args = parser.parse_args(argv)
    if args.fluid:
        for n in args.fluid:
            name, st, r = run_fluid(n)
            info = r.get("reason") or r.get("rule") or f"{r['cpu_s']} s CPU, dropped {r['dropped']}"
            print(f"{name}: {st}: {info}")
            if st == "ok" and args.report:
                args.report.write_text(json.dumps(r, indent=1, sort_keys=True, default=str) + "\n")
        return 0
    if not (args.check or args.emit or args.emit_fluid_table):
        parser.error("choose --check, --emit PATH and/or --emit-fluid-table PATH")
    try:
        payload, table = build(args.jobs, args.report)
    except ClaimFailedError as ex:
        print(f"claim failed: {ex}", file=sys.stderr)
        return 1
    status = 0
    if args.check:
        for path, data in ((DEFAULT_OUT, payload), (TABLE_OUT, table)):
            committed = path.read_bytes() if path.exists() else b""
            if committed != data:
                print(f"{path} differs from the generator's output", file=sys.stderr)
                status = 1
        if status == 0:
            print(
                "all claims passed; s07_reference.json and _coolprop_heos_fluids.py "
                "are byte-identical"
            )
    if args.emit:
        Path(args.emit).write_bytes(payload)
        print("wrote", args.emit)
    if args.emit_fluid_table:
        Path(args.emit_fluid_table).write_bytes(table)
        print("wrote", args.emit_fluid_table)
    return status


if __name__ == "__main__":
    sys.exit(main())
