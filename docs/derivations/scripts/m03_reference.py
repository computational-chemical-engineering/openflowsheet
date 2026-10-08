"""Design-lane closed-form reference generator for the M03 specification.

Everything here follows from the SYN-001 definitions (``docs/derivations/SYN-001.md`` §1-§6) and the
M03 specification (``docs/derivations/M03-studies-spec.md``) alone, evaluated with mpmath at 60
significant digits. It imports nothing from ``openflowsheet`` or ``benchmarks``: the numbers it
emits are the *expectations* the M03 tests judge the implementation against, so they must not
come from the implementation.

What it produces (spec §13):

* the closed-form SYN-001 flowsheet map ``p -> y(p)`` (spec §4.1) and its parameter derivatives at
  the registered sensitivity states P1-P3, with the registered structural zeros (spec §4.3);
* the phase-regime margins of spec §3.4 at every registered state, and the refusal states B1-B3;
* the two toy problems of spec §5 (``x^2 - p`` and the 2 x 2 linear system);
* the registered sweep (spec §6);
* the synthetic data set, the two weighted least-squares fits and their identifiability evidence
  (spec §7), from a SplitMix64 stream implemented here so that the data are byte-reproducible;
* the NLP-1 optimum, its multiplier and its curvature, and the NLP-INF infeasibility (spec §8).

Run from the repository root inside the project environment::

    python docs/derivations/scripts/m03_reference.py --check
    python docs/derivations/scripts/m03_reference.py --emit benchmarks/m03/reference_values.json

``--check`` re-derives every claim the specification makes about its own numbers (spec §13.2),
refuses to continue when one fails, and compares the result with the committed file byte for
byte. ``--emit`` runs the same claims and writes the file only when all of them hold.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from mpmath import mp, mpf

mp.dps = 60

SPEC = "docs/derivations/M03-studies-spec.md"
GENERATOR = "docs/derivations/scripts/m03_reference.py"
DEFAULT_OUT = Path("benchmarks/m03/reference_values.json")

# -- SYN-001 constants (derivation §1, verbatim) -----------------------------------------------
R_GAS = mpf("8.31446261815324")
T_REF = mpf(300)
P_REF = mpf(100000)
CP = mpf(100)
T_BOIL = (mpf(320), mpf(360), mpf(400))
L_VAP = (mpf(25000), mpf(30000), mpf(35000))
V_LIQ = (mpf("0.0001"),) * 3
NAMES = ("A", "B", "C")
DOMAIN_T = (mpf(280), mpf(440))

# -- M03 registered constants (spec §3.5, §4.2, §7, §8) -----------------------------------------
TAU_REGIME = mpf("1e-4")
TAU_ROOT = mpf("1e-10")
TAU_ALIAS = mpf("1e-8")
TAU_ID = mpf("1e-8")
TAU_ABS = mpf("1e-11")
TAU_REL = mpf("1e-10")
TAU_FD = mpf("1e-9")
FD_EPS = mpf("1e-4")
ZERO = mpf(10) ** -35

#: Registered scales (SYN-001 §9; `numerics/scaling.py` REGISTERED_NOMINALS): the normalization of
#: every sensitivity assertion. Parameters: r is dimensionless with scale 1.
SCALE_KIND = {"molar_flow": mpf(3), "temperature": mpf(100), "heat_rate": mpf(100000)}

PARAMETERS: tuple[tuple[str, str, str], ...] = (
    # (parameter id, key in `flowsheet`, scale kind or "unit")
    ("U-SPLIT.split_fraction", "r", "unit"),
    ("U-FLASH.T_spec", "t_f", "temperature"),
    ("U-HEAT.T_spec", "t_h", "temperature"),
    ("U-FEED.T_spec", "t_feed", "temperature"),
    ("U-FEED.n_spec.A", "f_a", "molar_flow"),
)
OUTPUTS: tuple[tuple[str, str], ...] = (
    ("S4.N", "molar_flow"),
    ("S5.N", "molar_flow"),
    ("S6.n.A", "molar_flow"),
    ("S6.n.B", "molar_flow"),
    ("S6.n.C", "molar_flow"),
    ("S7.n.A", "molar_flow"),
    ("S4.n.A", "molar_flow"),
    ("S2.T", "temperature"),
    ("U-HEAT.Q", "heat_rate"),
    ("U-FLASH.Q", "heat_rate"),
    ("S3.V", "molar_flow"),
)
#: The derived output of spec §4.4 (a linear functional, not a variable).
Q_TOTAL = ("Q_total", {"U-HEAT.Q": 1, "U-FLASH.Q": 1}, "heat_rate")

NOMINAL: dict[str, Any] = {
    "r": mpf("0.5"),
    "t_f": mpf(360),
    "t_h": mpf(350),
    "t_feed": mpf(300),
    "f_a": mpf(1),
    "f_b": mpf(1),
    "f_c": mpf(1),
}

Vec = tuple[Any, ...]
Params = Mapping[str, Any]


class ClaimFailedError(RuntimeError):
    """A claim the specification makes about its own numbers no longer holds."""


CLAIMS: list[str] = []
JACOBIANS: dict[str, list[list[Any]]] = {}


def claim(condition: bool, text: str) -> None:
    if not condition:
        raise ClaimFailedError(text)
    CLAIMS.append(text)


# -- closed forms --------------------------------------------------------------------------------


def k_values(t: Any, p: Any = P_REF) -> Vec:
    """Derivation §3: K_i(T, P) = (P_r/P) exp[(L_i/R)(1/T_b,i - 1/T) + v_i (P - P_r)/(R T)]."""
    return tuple(
        (P_REF / p)
        * mp.exp(L_VAP[i] / R_GAS * (1 / T_BOIL[i] - 1 / t) + V_LIQ[i] * (p - P_REF) / (R_GAS * t))
        for i in range(3)
    )


def bisect(fun: Callable[[Any], Any], lo: Any, hi: Any) -> Any:
    """Bisection to the working precision on a bracket with fun(lo) > 0 > fun(hi)."""
    f_lo, f_hi = fun(lo), fun(hi)
    if not (f_lo > 0 > f_hi):
        raise ClaimFailedError(f"bisection bracket does not change sign: {f_lo}, {f_hi}")
    for _ in range(int(mp.prec) + 12):
        mid = (lo + hi) / 2
        if fun(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def classify(z: Sequence[Any], k: Sequence[Any]) -> dict[str, Any]:
    """Spec §3.4: the regime of a TP split of composition z and its dimensionless margin."""
    s1 = sum(z[i] * k[i] for i in range(3)) - 1
    s2 = sum(z[i] / k[i] for i in range(3)) - 1
    if s1 <= 0:
        return {"regime": "LIQUID", "margin": -s1, "beta": mpf(0), "s1": s1, "s2": s2}
    if s2 <= 0:
        return {"regime": "VAPOR", "margin": -s2, "beta": mpf(1), "s1": s1, "s2": s2}

    def rr(beta: Any) -> Any:
        return sum(z[i] * (k[i] - 1) / (1 + beta * (k[i] - 1)) for i in range(3))

    beta = bisect(rr, mpf(0), mpf(1))
    return {"regime": "TWO_PHASE", "margin": min(s1, s2), "beta": beta, "s1": s1, "s2": s2}


def split(n: Sequence[Any], t: Any) -> tuple[dict[str, Any], Vec, Vec]:
    """A TP split of the component flows n at (t, P_r): classification, vapour and liquid flows."""
    total = sum(n)
    z = tuple(v / total for v in n)
    k = k_values(t)
    c = classify(z, k)
    beta = c["beta"]
    if c["regime"] == "LIQUID":
        return c, (mpf(0),) * 3, tuple(n)
    if c["regime"] == "VAPOR":
        return c, tuple(n), (mpf(0),) * 3
    d = tuple(1 + beta * (k[i] - 1) for i in range(3))
    x = tuple(z[i] / d[i] for i in range(3))
    vap = tuple(total * beta * k[i] * x[i] for i in range(3))
    liq = tuple(total * (1 - beta) * x[i] for i in range(3))
    return c, vap, liq


def h_liquid(t: Any) -> Any:
    return CP * (t - T_REF)


def h_vapor(i: int, t: Any) -> Any:
    return CP * (t - T_REF) + L_VAP[i]


def flowsheet(params: Params) -> dict[str, Any]:
    """Spec §4.1: the SYN-001 flowsheet's outputs as closed forms of its pinned inputs.

    The flash products are those of a single TP flash of the fresh feed (derivation §5.1, which
    holds in every regime: §7's single-phase variants are its special cases); the recycle is
    r L x; the mixer is the analytic adiabatic mix of two liquids (§4.1); the heater outlet is
    the TP split of the mixed stream at T_h; every enthalpy is §2's.
    """
    r, t_f, t_h, t_feed = params["r"], params["t_f"], params["t_h"], params["t_feed"]
    fresh = (params["f_a"], params["f_b"], params["f_c"])
    f_tot = sum(fresh)
    fresh_c, fresh_vap, fresh_liq = split(fresh, t_f)
    v_tot = sum(fresh_vap)
    purge = fresh_liq  # (1 - r) L x = the fresh feed's liquid (derivation §5.1)
    liquid = tuple(v / (1 - r) for v in purge)
    recycle = tuple(r * v for v in liquid)
    t_tot = sum(recycle)
    mixed = tuple(fresh[i] + recycle[i] for i in range(3))
    m_tot = sum(mixed)
    t_mix = (f_tot * t_feed + t_tot * t_f) / (f_tot + t_tot)
    z_mix = tuple(v / m_tot for v in mixed)
    mixer_margin = 1 - sum(z_mix[i] * k_values(t_mix)[i] for i in range(3))
    feed_margin = 1 - sum(fresh[i] / f_tot * k_values(t_feed)[i] for i in range(3))
    heater_c, heater_vap, heater_liq = split(mixed, t_h)
    flash_c = classify(z_mix, k_values(t_f))
    h1 = h_liquid(t_feed) * f_tot
    h6 = h_liquid(t_f) * t_tot
    h3 = sum(h_vapor(i, t_h) * heater_vap[i] + h_liquid(t_h) * heater_liq[i] for i in range(3))
    h4 = sum(h_vapor(i, t_f) * fresh_vap[i] for i in range(3))
    h5 = h_liquid(t_f) * sum(liquid)
    q_heater = h3 - (h1 + h6)
    q_flash = h4 + h5 - h3
    return {
        "S1.n.A": fresh[0],
        "S4.N": v_tot,
        "S5.N": sum(liquid),
        "S6.n.A": recycle[0],
        "S6.n.B": recycle[1],
        "S6.n.C": recycle[2],
        "S7.n.A": purge[0],
        "S7.n.B": purge[1],
        "S7.n.C": purge[2],
        "S4.n.A": fresh_vap[0],
        "S4.n.B": fresh_vap[1],
        "S4.n.C": fresh_vap[2],
        "S2.T": t_mix,
        "U-HEAT.Q": q_heater,
        "U-FLASH.Q": q_flash,
        "S3.V": sum(heater_vap),
        "S5.n": liquid,
        "recycle_total": t_tot,
        "Q_total": q_heater + q_flash,
        "fresh_regime": fresh_c,
        "heater": heater_c,
        "flash": flash_c,
        "mixer_margin": mixer_margin,
        "feed_margin": feed_margin,
    }


def with_param(params: Params, key: str, value: Any) -> dict[str, Any]:
    out = dict(params)
    out[key] = value
    return out


def scale_of(kind: str) -> Any:
    return mpf(1) if kind == "unit" else SCALE_KIND[kind]


def derivative(fun: Callable[[Any], Any], at: Any, scale: Any, order: int = 4) -> Any:
    """A central difference at h = 1e-20 * scale in 60-digit arithmetic (spec §13.1).

    Truncation is O(h^order) and roundoff O(10^-60 / h): both below 1e-38 relative, so the result
    carries more than the 20 digits printed. Claim C1 checks the 2nd- against the 4th-order form.
    """
    h = mpf("1e-20") * scale
    if order == 2:
        return (fun(at + h) - fun(at - h)) / (2 * h)
    return (-fun(at + 2 * h) + 8 * fun(at + h) - 8 * fun(at - h) + fun(at - 2 * h)) / (12 * h)


def jacobian(
    params: Params, outputs: Sequence[str], keys: Sequence[tuple[str, Any]], order: int = 4
) -> list[list[Any]]:
    """d outputs / d params, every output from the same flowsheet evaluations."""
    columns: list[list[Any]] = []
    for key, scale in keys:
        h = mpf("1e-20") * scale
        base = params[key]
        if order == 2:
            plus, minus = (
                flowsheet(with_param(params, key, base + h)),
                flowsheet(with_param(params, key, base - h)),
            )
            columns.append([(plus[o] - minus[o]) / (2 * h) for o in outputs])
        else:
            evaluations = [flowsheet(with_param(params, key, base + j * h)) for j in (2, 1, -1, -2)]
            columns.append(
                [
                    (
                        -evaluations[0][o]
                        + 8 * evaluations[1][o]
                        - 8 * evaluations[2][o]
                        + evaluations[3][o]
                    )
                    / (12 * h)
                    for o in outputs
                ]
            )
    return [[columns[j][i] for j in range(len(keys))] for i in range(len(outputs))]


def s(x: Any, digits: int = 20) -> str:
    """20 significant digits; a magnitude below 1e-35 is an exact zero of the closed forms."""
    if abs(x) < ZERO:
        return "0.0"
    return str(mp.nstr(x, digits))


def double(x: Any) -> float:
    """The binary64 value nearest x (Python float conversion of an mpf rounds to nearest)."""
    return float(x)


def exact(value: float) -> Any:
    """A binary64 value as an exact mpf."""
    return mpf(value)


# -- sensitivity states (spec §4) -----------------------------------------------------------------

STATES: dict[str, dict[str, Any]] = {
    "P1": {
        "case": "SYN-001-nominal",
        "params": dict(NOMINAL),
        "why": (
            "The nominal case. K_B(360 K) = 1 exactly, so x_B = y_B = 1/3 and several couplings "
            "through B vanish here; they are registered as zeros because they vanish here and "
            "are non-zero at P3. Heater outlet LIQUID, flash TWO_PHASE."
        ),
    },
    "P2": {
        "case": "SYN-001-high-recycle",
        "params": with_param(NOMINAL, "r", mpf("0.95")),
        "why": (
            "r = 0.95: the recycle derivatives carry 1/(1 - r) = 20 and 1/(1 - r)^2 = 400, so a "
            "dropped or mis-scaled factor of (1 - r) is visible; the heater duty is negative."
        ),
    },
    "P3": {
        "case": None,
        "params": with_param(with_param(NOMINAL, "r", mpf("0.3")), "t_f", mpf(365)),
        "why": (
            "Off the K_B = 1 point (T_f = 365 K) and at a heater outlet that is TWO_PHASE, so the "
            "heater's lifted split rows and their property derivatives enter the sensitivity, and "
            "the couplings that vanish at P1 through K_B = 1 do not vanish here."
        ),
    },
}


def bubble_temperature(z: Sequence[Any]) -> Any:
    """The bubble temperature of composition z at P_r: sum z_i K_i(T) = 1."""
    return bisect(lambda t: 1 - sum(z[i] * k_values(t)[i] for i in range(3)), mpf(300), mpf(374))


def dew_temperature(z: Sequence[Any]) -> Any:
    return bisect(lambda t: sum(z[i] / k_values(t)[i] for i in range(3)) - 1, mpf(340), mpf(440))


def margins_record(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "U-HEAT": {
            "split": "S3",
            "regime": values["heater"]["regime"],
            "margin": s(values["heater"]["margin"]),
        },
        "U-FLASH": {
            "split": "S4/S5",
            "regime": values["flash"]["regime"],
            "margin": s(values["flash"]["margin"]),
        },
        "mixer_subcooling_margin": s(values["mixer_margin"]),
    }


def sensitivity_state(label: str, entry: Mapping[str, Any]) -> dict[str, Any]:
    params = entry["params"]
    values = flowsheet(params)
    keys = [(key, scale_of(kind)) for _, key, kind in PARAMETERS]
    outputs = [o for o, _ in OUTPUTS]
    jac4 = jacobian(params, outputs + ["Q_total"], keys, order=4)
    jac2 = jacobian(params, outputs + ["Q_total"], keys, order=2)
    out_scales = [SCALE_KIND[kind] for _, kind in OUTPUTS] + [SCALE_KIND["heat_rate"]]
    par_scales = [scale for _, scale in keys]
    worst = mpf(0)
    for i in range(len(jac4)):
        for j in range(len(keys)):
            worst = max(worst, abs(jac4[i][j] - jac2[i][j]) * par_scales[j] / out_scales[i])
    claim(
        worst < mpf("1e-30"),
        f"C1[{label}] 2nd- and 4th-order closed-form derivatives agree to {mp.nstr(worst, 3)} < "
        "1e-30 (scaled)",
    )
    # C1': the implicit-function derivative of the fresh-feed Rachford-Rice root in T_f.
    if values["fresh_regime"]["regime"] == "TWO_PHASE":
        f_tot = params["f_a"] + params["f_b"] + params["f_c"]
        z = (params["f_a"] / f_tot, params["f_b"] / f_tot, params["f_c"] / f_tot)
        k = k_values(params["t_f"])
        beta = values["fresh_regime"]["beta"]
        d = [1 + beta * (k[i] - 1) for i in range(3)]
        rr_beta = -sum(z[i] * (k[i] - 1) ** 2 / d[i] ** 2 for i in range(3))
        dk = [k[i] * L_VAP[i] / (R_GAS * params["t_f"] ** 2) for i in range(3)]
        rr_t = sum(z[i] * dk[i] / d[i] ** 2 for i in range(3))
        analytic = -rr_t / rr_beta * f_tot  # dV/dT_f = F_tot d(beta)/dT_f
        numeric = jac4[0][1]
        claim(
            abs(analytic - numeric) < mpf("1e-30"),
            f"C1'[{label}] dV/dT_f by the implicit function theorem equals the difference "
            "derivative to 1e-30",
        )
    sens: dict[str, dict[str, str]] = {}
    zeros: list[list[str]] = []
    for i, name in enumerate(outputs + ["Q_total"]):
        sens[name] = {}
        for j, (pid, _, _) in enumerate(PARAMETERS):
            sens[name][pid] = s(jac4[i][j])
            if abs(jac4[i][j]) < ZERO:
                zeros.append([name, pid])
    JACOBIANS[label] = jac4
    # Regime health: every split of a regular state is outside the refusal band by a factor 10.
    for unit in ("heater", "flash"):
        claim(
            values[unit]["margin"] > 10 * TAU_REGIME,
            f"C3[{label}] {unit} margin {mp.nstr(values[unit]['margin'], 6)} > 10 tau_regime",
        )
    claim(
        values["mixer_margin"] > mpf("1e-2"),
        f"C3[{label}] mixer outlet subcooled by {mp.nstr(values['mixer_margin'], 6)}",
    )
    claim(
        values["feed_margin"] > mpf("1e-2"), f"C3[{label}] fresh feed subcooled at its temperature"
    )
    claim(
        values["flash"]["regime"] == values["fresh_regime"]["regime"],
        f"C3[{label}] flash feed and fresh feed share the regime (derivation §5.1)",
    )
    record: dict[str, Any] = {
        "case": entry["case"],
        "why": entry["why"],
        "pinned": {pid: s(params[key]) for pid, key, _ in PARAMETERS},
        "pinned_doubles": {pid: repr(double(params[key])) for pid, key, _ in PARAMETERS},
        "values": {
            name: s(values[name])
            for name in outputs + ["Q_total", "S4.n.B", "S4.n.C", "S7.n.B", "S7.n.C"]
        },
        "liquid_S5_n": [s(v) for v in values["S5.n"]],
        "regime_margins": margins_record(values),
        "sensitivity": sens,
        "structural_zeros": zeros,
    }
    if label in ("P1", "P3"):
        record["fd_oracle"] = fd_stencil(label, params)
    return record


def classify_zeros(states: Mapping[str, Any]) -> dict[tuple[str, str, str], str]:
    """C2 (rule 3): no registered zero comes from a dead parameter, and none from an output that
    is dead at every registered state. A zero is `state_specific` when the same entry is non-zero
    at another registered state, and `universal` (structural, derived in spec §4.3) otherwise."""
    names = [o for o, _ in OUTPUTS] + ["Q_total"]
    pids = [p for p, _, _ in PARAMETERS]
    live = mpf("1e-6")
    kinds: dict[tuple[str, str, str], str] = {}
    for label, record in states.items():
        jac = JACOBIANS[label]
        for name, pid in record["structural_zeros"]:
            i, j = names.index(name), pids.index(pid)
            column_alive = any(abs(jac[ii][j]) > live for ii in range(len(names)))
            row_alive = any(
                abs(JACOBIANS[other][i][jj]) > live for other in states for jj in range(len(pids))
            )
            claim(
                column_alive and row_alive,
                f"C2[{label}] the zero d{name}/d{pid} has a live column here and a live row at "
                "some registered state",
            )
            elsewhere = any(
                abs(JACOBIANS[other][i][j]) > live for other in states if other != label
            )
            kinds[(label, name, pid)] = "state_specific" if elsewhere else "universal"
    return kinds


def fd_stencil(label: str, params: Params) -> dict[str, Any]:
    """C4: every point of the registered 4th-order stencil stays inside its regimes (spec §4.5)."""
    worst = mpf(1)
    for pid, key, kind in PARAMETERS:
        h = FD_EPS * scale_of(kind)
        for j in (-2, -1, 1, 2):
            moved = with_param(params, key, params[key] + j * h)
            if key == "r":
                claim(0 < moved["r"] < 1, f"C4[{label}] stencil r stays in (0, 1)")
            values = flowsheet(moved)
            base = flowsheet(params)
            for unit in ("heater", "flash"):
                claim(
                    values[unit]["regime"] == base[unit]["regime"],
                    f"C4[{label}] {unit} regime unchanged at {pid} {j:+d}h",
                )
                worst = min(worst, values[unit]["margin"])
    claim(
        worst > 10 * TAU_REGIME,
        f"C4[{label}] smallest margin on the stencil {mp.nstr(worst, 6)} > 10 tau_regime",
    )
    return {
        "order": 4,
        "relative_step": s(FD_EPS),
        "steps": {pid: s(FD_EPS * scale_of(kind)) for pid, _, kind in PARAMETERS},
        "smallest_stencil_margin": s(worst),
    }


# -- refusal states (spec §4.6) --------------------------------------------------------------------


def boundary_states() -> dict[str, Any]:
    z = (mpf(1) / 3,) * 3
    t_bubble = bubble_temperature(z)
    t_dew = dew_temperature(z)
    claim(
        abs(t_bubble - mpf("347.44118198144020")) < mpf("1e-13"),
        "C5 the equimolar bubble point is SYN-001 §3.1's 347.44118198144020 K",
    )
    claim(
        abs(t_dew - mpf("374.27030411847760")) < mpf("1e-13"),
        "C5 the equimolar dew point is SYN-001 §3.1's 374.27030411847760 K",
    )
    tb = double(t_bubble)
    out: dict[str, Any] = {
        "equimolar_bubble_K": s(t_bubble),
        "equimolar_bubble_double": repr(tb),
        "equimolar_dew_K": s(t_dew),
    }
    registered = {
        "B1": (
            tb + 1e-3,
            "TWO_PHASE",
            "two-phase side, 1e-3 K above the bubble point: margin below tau_regime, Jacobian "
            "still regular (measured rcond_1 2.9e-7), certificate VERIFIED",
        ),
        "B2": (
            tb - 1e-3,
            "LIQUID",
            "liquid side, 1e-3 K below the bubble point: the same, from the other regime",
        ),
        "B3": (
            tb + 1e-5,
            "TWO_PHASE",
            "1e-5 K above the bubble point: the margin, the [A08] screen (ILL_CONDITIONED, "
            "measured rcond_1 2.9e-9) and the certificate (UNVERIFIED) all refuse; every reason "
            "is listed",
        ),
    }
    for label, (t_f, regime, why) in registered.items():
        params = with_param(NOMINAL, "t_f", exact(t_f))
        values = flowsheet(params)
        margin = values["flash"]["margin"]
        claim(values["flash"]["regime"] == regime, f"C5[{label}] flash regime is {regime}")
        claim(
            0 < margin < TAU_REGIME / 2,
            f"C5[{label}] flash margin {mp.nstr(margin, 6)} lies in (0, tau_regime/2)",
        )
        claim(
            values["heater"]["margin"] > 10 * TAU_REGIME,
            f"C5[{label}] the heater is not the refusing split",
        )
        out[label] = {
            "why": why,
            "pinned_doubles": {"U-FLASH.T_spec": repr(t_f), "U-SPLIT.split_fraction": "0.5"},
            "flash_regime": regime,
            "flash_margin": s(margin),
            "heater_regime": values["heater"]["regime"],
            "heater_margin": s(values["heater"]["margin"]),
            "expected_refusal": "PHASE_BOUNDARY",
            "S4.N": s(values["S4.N"]),
        }
    return out


# -- toys (spec §5) --------------------------------------------------------------------------------


def toys() -> dict[str, Any]:
    a1 = mp.matrix([[1, 2], [3, 7]])
    inv = a1**-1
    claim(
        mp.norm(inv - mp.matrix([[7, -2], [-3, 1]])) < mpf("1e-50"),
        "C6 A(1)^-1 = [[7, -2], [-3, 1]]",
    )
    c = mp.matrix([[1, 10]])
    adjoint_value = c * inv
    wrong = (inv * c.T).T
    claim(list(adjoint_value) == [mpf(-23), mpf(8)], "C6 C A(1)^-1 = [-23, 8]")
    claim(
        list(wrong) == [mpf(-13), mpf(7)],
        "C6 the missing-transpose value is [-13, 7], which differs",
    )
    return {
        "x_squared": {
            "residual": "x^2 - p",
            "states": [
                {
                    "p": "0.25",
                    "x": "0.5",
                    "expected": "QUALIFIED",
                    "dx_dp": "1.0",
                    "residual": "0.0",
                },
                {
                    "p": "1e-20",
                    "x": "1e-10",
                    "expected": "ILL_CONDITIONED",
                    "screen_reason": "absolute",
                    "residual": "0.0",
                },
                {"p": "0.0", "x": "0.0", "expected": "RANK_DEFICIENT", "residual": "0.0"},
            ],
        },
        "linear_2x2": {
            "residual": "A(delta) x - p, A(delta) = [[1, 2], [3, 6 + delta]], F_p = -I",
            "p": ["1.0", "3.0"],
            "x": ["1.0", "0.0"],
            "states": [
                {
                    "delta": "1.0",
                    "expected": "QUALIFIED",
                    "dx_dp": [["7.0", "-2.0"], ["-3.0", "1.0"]],
                    "output_C": [["1.0", "10.0"]],
                    "dy_dp": [["-23.0", "8.0"]],
                    "missing_transpose_value": [["-13.0", "7.0"]],
                },
                {"delta": "1e-12", "expected": "ILL_CONDITIONED", "screen_reason": "relative"},
                {"delta": "0.0", "expected": "RANK_DEFICIENT"},
            ],
        },
    }


# -- sweep (spec §6) -------------------------------------------------------------------------------

SWEEP_T = (310.0, 340.0, 355.0, 360.0, 365.0, 374.0, 380.0, 420.0, 445.0)


def sweep() -> dict[str, Any]:
    points = []
    for t_f in SWEEP_T:
        params = with_param(NOMINAL, "t_f", exact(t_f))
        if not (DOMAIN_T[0] <= params["t_f"] <= DOMAIN_T[1]):
            points.append(
                {
                    "U-FLASH.T_spec": repr(t_f),
                    "expected_outcome": "SPECIFICATION_REFUSED",
                    "reason": (
                        "flash temperature outside the provider's declared domain [280, 440] K"
                    ),
                }
            )
            continue
        values = flowsheet(params)
        dv = derivative(
            lambda t, at=params: flowsheet(with_param(at, "t_f", t))["S4.N"],
            params["t_f"],
            mpf(100),
        )
        for unit in ("heater", "flash"):
            claim(
                values[unit]["margin"] > 10 * TAU_REGIME,
                f"C7 sweep {t_f} K {unit} margin > 10 tau_regime",
            )
        claim(values["mixer_margin"] > mpf("1e-2"), f"C7 sweep {t_f} K mixer subcooled")
        claim(
            (abs(dv) < ZERO) == (values["flash"]["regime"] != "TWO_PHASE"),
            f"C7 sweep {t_f} K: dV/dT_f vanishes iff the flash is single-phase",
        )
        points.append(
            {
                "U-FLASH.T_spec": repr(t_f),
                "expected_outcome": "CONVERGED",
                "expected_certificate": "VERIFIED",
                "flash_regime": values["flash"]["regime"],
                "heater_regime": values["heater"]["regime"],
                "S4.N": s(values["S4.N"]),
                "S5.N": s(values["S5.N"]),
                "dS4.N_dT_f": s(dv),
                "expected_sensitivity": "QUALIFIED",
            }
        )
    return {"split_fraction": "0.5", "parameter": "U-FLASH.T_spec", "points": points}


# -- estimation (spec §7) --------------------------------------------------------------------------

SEED = 20261008
MASK = (1 << 64) - 1


def splitmix64(seed: int, count: int) -> list[int]:
    state = seed & MASK
    out = []
    for _ in range(count):
        state = (state + 0x9E3779B97F4A7C15) & MASK
        z = state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        out.append(z ^ (z >> 31))
    return out


def standard_normals(seed: int, count: int) -> list[Any]:
    """Spec §7.2: u = ((w >> 11) + 1/2) 2^-53 in (0, 1), e = sqrt(2) erfinv(2u - 1)."""
    out = []
    for word in splitmix64(seed, count):
        u = (mpf(word >> 11) + mpf("0.5")) / mpf(2) ** 53
        out.append(mp.sqrt(2) * mp.erfinv(2 * u - 1))
    return out


MEASUREMENTS: tuple[tuple[str, dict[str, int], str], ...] = (
    ("S4.n.A", {"S4.n.A": 1}, "0.002"),
    ("S4.n.B", {"S4.n.B": 1}, "0.002"),
    ("S4.n.C", {"S4.n.C": 1}, "0.002"),
    ("S7.n.A", {"S7.n.A": 1}, "0.002"),
    ("S7.n.B", {"S7.n.B": 1}, "0.002"),
    ("S7.n.C", {"S7.n.C": 1}, "0.002"),
    ("recycle_total", {"S6.n.A": 1, "S6.n.B": 1, "S6.n.C": 1}, "0.005"),
    ("S2.T", {"S2.T": 1}, "0.05"),
)
VALIDATION: tuple[tuple[str, dict[str, int], str], ...] = (
    ("U-HEAT.Q", {"U-HEAT.Q": 1}, "20"),
    ("S4.N", {"S4.N": 1}, "0.002"),
)
FIT_I = tuple(m[0] for m in MEASUREMENTS)
FIT_U = FIT_I[:6]
THETA = (("U-SPLIT.split_fraction", "r", mpf(1)), ("U-FLASH.T_spec", "t_f", mpf(100)))
BOX = {"r": (mpf("0.50"), mpf("0.97")), "t_f": (mpf(356), mpf(366))}
THETA_TRUE = (mpf("0.7"), mpf(361))
THETA_START = (mpf("0.6"), mpf(358))


def model_at(theta: Sequence[Any]) -> dict[str, Any]:
    return flowsheet(with_param(with_param(NOMINAL, "r", theta[0]), "t_f", theta[1]))


def predict(theta: Sequence[Any], names: Sequence[str]) -> list[Any]:
    values = model_at(theta)
    return [values[name] for name in names]


def jac_theta(theta: Sequence[Any], names: Sequence[str]) -> Any:
    rows = len(names)
    out = mp.matrix(rows, 2)
    for j, (_, _, scale) in enumerate(THETA):
        h = mpf("1e-20") * scale
        plus = list(theta)
        minus = list(theta)
        plus2 = list(theta)
        minus2 = list(theta)
        plus[j] += h
        minus[j] -= h
        plus2[j] += 2 * h
        minus2[j] -= 2 * h
        a, b, c, d = (
            predict(plus2, names),
            predict(plus, names),
            predict(minus, names),
            predict(minus2, names),
        )
        for i in range(rows):
            out[i, j] = (-a[i] + 8 * b[i] - 8 * c[i] + d[i]) / (12 * h)
    return out


def gauss_newton(
    names: Sequence[str],
    obs: Sequence[Any],
    sigma: Sequence[Any],
    start: Sequence[Any],
    free: Sequence[int],
) -> list[Any]:
    """Weighted least squares by Gauss-Newton on the free components, to 1e-45 in the step."""
    theta = list(start)
    for _ in range(60):
        y = predict(theta, names)
        jac = jac_theta(theta, names)
        n = len(free)
        a = mp.matrix(n, n)
        g = mp.matrix(n, 1)
        for i in range(len(names)):
            w = 1 / sigma[i] ** 2
            res = y[i] - obs[i]
            for p, fp in enumerate(free):
                g[p] += jac[i, fp] * w * res
                for q, fq in enumerate(free):
                    a[p, q] += jac[i, fp] * w * jac[i, fq]
        step = mp.lu_solve(a, -g)
        for p, fp in enumerate(free):
            theta[fp] += step[p]
        if max(abs(step[p]) / THETA[free[p]][2] for p in range(n)) < mpf("1e-45"):
            return theta
    raise ClaimFailedError("Gauss-Newton did not converge")


def weighted_scaled_jacobian(
    theta: Sequence[Any], names: Sequence[str], sigma: Sequence[Any]
) -> Any:
    jac = jac_theta(theta, names)
    out = mp.matrix(len(names), 2)
    for i in range(len(names)):
        for j in range(2):
            out[i, j] = jac[i, j] * THETA[j][2] / sigma[i]
    return out


def estimation() -> dict[str, Any]:
    names_all = [m[0] for m in MEASUREMENTS] + [v[0] for v in VALIDATION]
    sigma_all = [mpf(m[2]) for m in MEASUREMENTS] + [mpf(v[2]) for v in VALIDATION]
    normals = standard_normals(SEED, len(names_all))
    claim(
        all(abs(e) < 4 for e in normals),
        "C8 every registered standard normal draw lies within 4 sigma",
    )
    truth = predict(THETA_TRUE, names_all)
    observed = [double(truth[i] + sigma_all[i] * normals[i]) for i in range(len(names_all))]
    obs_exact = [exact(v) for v in observed]
    record: dict[str, Any] = {
        "evidence_class": "numerical_verification",
        "statement": (
            "Synthetic data generated from the model itself: a numerical verification of the "
            "estimation machinery, not empirical validation."
        ),
        "data": {
            "generator": "SplitMix64",
            "seed": SEED,
            "uniform": "u_k = ((w_k >> 11) + 1/2) * 2^-53",
            "normal": "e_k = sqrt(2) * erfinv(2 u_k - 1)",
            "observation": "y_obs_k = binary64(y_k(theta_true) + sigma_k e_k)",
            "theta_true": {THETA[0][0]: s(THETA_TRUE[0]), THETA[1][0]: s(THETA_TRUE[1])},
            "measurements": [
                {
                    "id": n,
                    "coefficients": c,
                    "sigma": sg,
                    "true": s(truth[i]),
                    "normal_draw": s(normals[i]),
                    "observed": repr(observed[i]),
                }
                for i, (n, c, sg) in enumerate(MEASUREMENTS)
            ],
            "validation": [
                {
                    "id": n,
                    "coefficients": c,
                    "sigma": sg,
                    "true": s(truth[len(MEASUREMENTS) + i]),
                    "normal_draw": s(normals[len(MEASUREMENTS) + i]),
                    "observed": repr(observed[len(MEASUREMENTS) + i]),
                }
                for i, (n, c, sg) in enumerate(VALIDATION)
            ],
        },
        "theta": [
            {
                "id": pid,
                "scale": s(scale),
                "lower": s(BOX[key][0]),
                "upper": s(BOX[key][1]),
                "start": s(THETA_START[j]),
            }
            for j, (pid, key, scale) in enumerate(THETA)
        ],
        "tau_id": s(TAU_ID),
    }
    m = len(MEASUREMENTS)
    fits: dict[str, Any] = {}
    estimates: dict[str, list[Any]] = {}
    for label, names in (("FIT-I", FIT_I), ("FIT-U", FIT_U)):
        idx = [names_all.index(n) for n in names]
        obs = [obs_exact[i] for i in idx]
        sig = [sigma_all[i] for i in idx]
        jw0 = weighted_scaled_jacobian(THETA_START, names, sig)
        svd0 = mp.svd_r(jw0, compute_uv=False)
        identifiable_at_start = min(svd0) / max(svd0) > TAU_ID
        free = [0, 1] if identifiable_at_start else [1]
        theta = gauss_newton(names, obs, sig, THETA_START, free)
        estimates[label] = theta
        jw = weighted_scaled_jacobian(theta, names, sig)
        u, sv, v = mp.svd_r(jw)
        ratio = min(sv) / max(sv)
        y = predict(theta, names)
        chi2 = sum(((y[i] - obs[i]) / sig[i]) ** 2 for i in range(len(names)))
        grad = [
            sum(jw[i, j] * (y[i] - obs[i]) / sig[i] for i in range(len(names))) for j in range(2)
        ]
        fit: dict[str, Any] = {
            "measurements": list(names),
            "singular_values_scaled": [s(x) for x in sv],
            "singular_value_ratio": s(ratio),
            "chi2": s(chi2),
            "degrees_of_freedom": len(names) - (2 if identifiable_at_start else 1),
        }
        for j, (pid, key, scale) in enumerate(THETA):
            margin = min(theta[j] - BOX[key][0], BOX[key][1] - theta[j]) / scale
            if j in free:
                claim(
                    margin > mpf("0.02"),
                    f"C9[{label}] {pid} estimate is interior to its bounds by "
                    f"{mp.nstr(margin, 4)} scaled",
                )
                claim(
                    abs(grad[j]) < mpf("1e-30"),
                    f"C9[{label}] the normal equation for {pid} holds to 1e-30 "
                    f"({mp.nstr(abs(grad[j]), 3)})",
                )
        if label == "FIT-I":
            claim(
                identifiable_at_start and ratio > mpf("1e-3"),
                f"C9[FIT-I] identifiable: singular value ratio {mp.nstr(ratio, 6)} > 1e-3",
            )
            info = jw.T * jw
            cov_scaled = info**-1
            cov = mp.matrix(2, 2)
            for a in range(2):
                for b in range(2):
                    cov[a, b] = cov_scaled[a, b] * THETA[a][2] * THETA[b][2]
            se = [mp.sqrt(cov[a, a]) for a in range(2)]
            corr = cov[0, 1] / (se[0] * se[1])
            fit.update(
                {
                    "expected_status": "IDENTIFIABLE",
                    "estimate": {THETA[j][0]: s(theta[j]) for j in range(2)},
                    "covariance": [[s(cov[a, b]) for b in range(2)] for a in range(2)],
                    "standard_errors": {THETA[j][0]: s(se[j]) for j in range(2)},
                    "correlation": s(corr),
                }
            )
            preds = []
            for vi, (vname, _, vsig) in enumerate(VALIDATION):
                jv = jac_theta(theta, [vname])
                pred = predict(theta, [vname])[0]
                var = sum(jv[0, a] * cov[a, b] * jv[0, b] for a in range(2) for b in range(2))
                obs_v = obs_exact[m + vi]
                preds.append(
                    {
                        "id": vname,
                        "determined": True,
                        "predicted": s(pred),
                        "prediction_standard_error": s(mp.sqrt(var)),
                        "observed": repr(observed[m + vi]),
                        "normalized_residual": s((obs_v - pred) / mp.sqrt(var + mpf(vsig) ** 2)),
                    }
                )
            fit["validation"] = preds
            fit["numerical_tolerance_scaled"] = "1e-8"
            claim(
                all(mpf("1e-8") * THETA[j][2] < se[j] * mpf("1e-3") for j in range(2)),
                "C9[FIT-I] the numerical tolerance on the estimate is below 1e-3 of its standard "
                "error",
            )
        else:
            claim(not identifiable_at_start, "C9[FIT-U] unidentifiable at the start")
            claim(
                ratio < mpf("1e-40"),
                f"C9[FIT-U] the smaller singular value vanishes in closed form "
                f"({mp.nstr(ratio, 3)})",
            )
            null = [v[1, 0], v[1, 1]] if sv[1] < sv[0] else [v[0, 0], v[0, 1]]
            sign = 1 if null[0] > 0 else -1
            null = [sign * x for x in null]
            claim(
                abs(null[0] - 1) < mpf("1e-40") and abs(null[1]) < mpf("1e-40"),
                "C9[FIT-U] the null direction is the split fraction alone",
            )
            fit.update(
                {
                    "expected_status": "UNIDENTIFIABLE",
                    "estimate": {THETA[1][0]: s(theta[1])},
                    "not_determined": [THETA[0][0]],
                    "null_direction_scaled": [s(x) for x in null],
                }
            )
            preds = []
            for vname, _, _ in VALIDATION:
                jv = jac_theta(theta, [vname])
                along = jv[0, 0] * THETA[0][2] * null[0] + jv[0, 1] * THETA[1][2] * null[1]
                norm = mp.sqrt((jv[0, 0] * THETA[0][2]) ** 2 + (jv[0, 1] * THETA[1][2]) ** 2)
                determined = abs(along) <= mpf("1e-3") * norm
                preds.append(
                    {
                        "id": vname,
                        "determined": bool(determined),
                        "null_projection_relative": s(abs(along) / norm),
                    }
                )
            claim(
                [p["determined"] for p in preds] == [False, True],
                "C9[FIT-U] the heater-duty prediction is not determined and the vapour-flow "
                "prediction is",
            )
            fit["validation"] = preds
            fit["numerical_tolerance_scaled"] = "1e-8"
        fits[label] = fit
    claim(
        abs(estimates["FIT-I"][1] - estimates["FIT-U"][1]) > mpf("1e-6"),
        "C9 the two fits' flash-temperature estimates differ (the recycle and mixer data move it)",
    )
    # C10: the decision box keeps every regime (spec §7.1, §8.1), on a 21 x 21 grid.
    worst = box_margins()
    record["box_smallest_margins"] = {k: s(v) for k, v in worst.items()}
    record["fits"] = fits
    return record


def box_margins() -> dict[str, Any]:
    worst = {"heater": mpf(1), "flash": mpf(1), "mixer": mpf(1)}
    with mp.workdps(30):
        for a in range(21):
            r = BOX["r"][0] + (BOX["r"][1] - BOX["r"][0]) * a / 20
            for b in range(21):
                t_f = BOX["t_f"][0] + (BOX["t_f"][1] - BOX["t_f"][0]) * b / 20
                values = model_at((r, t_f))
                if (
                    values["heater"]["regime"] != "LIQUID"
                    or values["flash"]["regime"] != "TWO_PHASE"
                ):
                    raise ClaimFailedError(f"C10 the box leaves its regimes at r={r}, T_f={t_f}")
                worst["heater"] = min(worst["heater"], values["heater"]["margin"])
                worst["flash"] = min(worst["flash"], values["flash"]["margin"])
                worst["mixer"] = min(worst["mixer"], values["mixer_margin"])
    claim(
        all(v > mpf("1e-3") for v in worst.values()),
        "C10 on the 21 x 21 grid of the box every margin exceeds 1e-3 (smallest "
        f"{mp.nstr(min(worst.values()), 4)})",
    )
    return worst


# -- NLP (spec §8) ---------------------------------------------------------------------------------

RECOVERY = mpf("0.75")
RECOVERY_INFEASIBLE = mpf("1.05")
W_HEATER = mpf(100)
S_Q = mpf(100000)
STARTS = ((mpf("0.6"), mpf(360)), (mpf("0.85"), mpf(357)), (mpf("0.55"), mpf(365)))


def objective(values: Mapping[str, Any]) -> Any:
    return values["Q_total"] / S_Q + W_HEATER * (values["U-HEAT.Q"] / S_Q) ** 2


def constraint(values: Mapping[str, Any], rho: Any) -> Any:
    """g = (S4.n.A - rho S1.n.A) / 3 mol/s >= 0."""
    return (values["S4.n.A"] - rho * values["S1.n.A"]) / SCALE_KIND["molar_flow"]


def nlp() -> dict[str, Any]:
    t_star = bisect(
        lambda t: -constraint(model_at((mpf("0.5"), t)), RECOVERY), BOX["t_f"][0], BOX["t_f"][1]
    )
    r_star = bisect(lambda r: model_at((r, t_star))["U-HEAT.Q"], BOX["r"][0], BOX["r"][1])
    at = model_at((r_star, t_star))
    claim(
        abs(constraint(at, RECOVERY)) < mpf("1e-45"),
        "C11 the recovery constraint is active at the reference optimum",
    )
    claim(abs(at["U-HEAT.Q"]) < mpf("1e-40"), "C11 the heater is idle at the reference optimum")

    def phi(theta: Sequence[Any]) -> Any:
        return objective(model_at(theta))

    def g(theta: Sequence[Any]) -> Any:
        return constraint(model_at(theta), RECOVERY)

    scales = (mpf(1), mpf(100))

    def grad(fun: Callable[[Sequence[Any]], Any], theta: Sequence[Any]) -> list[Any]:
        out = []
        for j in range(2):

            def along(x: Any, j: int = j) -> Any:
                moved = list(theta)
                moved[j] = x
                return fun(moved)

            out.append(derivative(along, theta[j], scales[j]) * scales[j])
        return out

    theta = (r_star, t_star)
    gphi = grad(phi, theta)
    gg = grad(g, theta)
    claim(abs(gg[0]) < mpf("1e-40"), "C11 the constraint does not depend on the split fraction")
    mu = gphi[1] / gg[1]
    claim(
        abs(gphi[0]) < mpf("1e-35"), "C11 stationarity in the split fraction holds in closed form"
    )
    claim(mu > mpf("1e-3"), f"C11 strict complementarity: mu = {mp.nstr(mu, 8)} > 0")

    def phi_r(x: Any) -> Any:
        return phi((x, t_star))

    curvature = (
        phi_r(r_star + mpf("1e-15")) - 2 * phi_r(r_star) + phi_r(r_star - mpf("1e-15"))
    ) / mpf("1e-30")
    claim(
        curvature > mpf("1e-3"),
        f"C11 the reduced Hessian (d2 phi/d r2) is positive: {mp.nstr(curvature, 8)}",
    )
    # C12: uniqueness on the box (grid claim, spec §8.1): S4.n.A increases in T_f, the heater duty
    # decreases in r, Q_total increases in T_f, and the idle-heater split fraction lies inside the
    # box for every feasible T_f.
    with mp.workdps(30):
        prev_s4 = None
        prev_q = None
        for b in range(41):
            t_f = BOX["t_f"][0] + (BOX["t_f"][1] - BOX["t_f"][0]) * b / 40
            v = model_at((mpf("0.5"), t_f))
            if prev_s4 is not None and prev_q is not None:
                if not (v["S4.n.A"] > prev_s4 and v["Q_total"] > prev_q):
                    raise ClaimFailedError("C12 monotonicity in T_f fails")
            prev_s4, prev_q = v["S4.n.A"], v["Q_total"]
            if t_f >= t_star:
                lo = model_at((BOX["r"][0], t_f))["U-HEAT.Q"]
                hi = model_at((BOX["r"][1], t_f))["U-HEAT.Q"]
                if not (lo > 0 > hi):
                    raise ClaimFailedError("C12 the idle-heater split fraction leaves the box")
            for a in range(1, 21):
                r0 = BOX["r"][0] + (BOX["r"][1] - BOX["r"][0]) * (a - 1) / 20
                r1 = BOX["r"][0] + (BOX["r"][1] - BOX["r"][0]) * a / 20
                if not model_at((r1, t_f))["U-HEAT.Q"] < model_at((r0, t_f))["U-HEAT.Q"]:
                    raise ClaimFailedError("C12 the heater duty is not decreasing in r on the grid")
    claim(
        True,
        "C12 on a 41 x 21 grid: S4.n.A and Q_total increase in T_f, U-HEAT.Q decreases in r, and "
        "the idle-heater r stays inside the box for every feasible T_f",
    )
    starts = []
    for d0 in STARTS:
        v = model_at(d0)
        claim(
            v["heater"]["margin"] > mpf("1e-3") and v["flash"]["margin"] > mpf("1e-3"),
            "C13 every start is inside the regimes",
        )
        starts.append(
            {
                "U-SPLIT.split_fraction": s(d0[0]),
                "U-FLASH.T_spec": s(d0[1]),
                "constraint_scaled": s(constraint(v, RECOVERY)),
                "objective": s(objective(v)),
            }
        )
    # C14: NLP-INF is infeasible: S4.n.A <= S1.n.A for every state with nonnegative flows.
    claim(
        RECOVERY_INFEASIBLE > 1, "C14 NLP-INF asks for more A in the vapour than the feed carries"
    )
    reference = {
        "U-SPLIT.split_fraction": s(r_star),
        "U-FLASH.T_spec": s(t_star),
        "objective": s(objective(at)),
        "Q_total": s(at["Q_total"]),
        "S4.n.A": s(at["S4.n.A"]),
        "U-HEAT.Q": "0.0",
        "multiplier_recovery_scaled": s(mu),
        "reduced_gradient_scaled": [s(gphi[0]), s(gphi[1] - mu * gg[1])],
        "objective_gradient_scaled": [s(x) for x in gphi],
        "constraint_gradient_scaled": [s(x) for x in gg],
        "reduced_hessian_r": s(curvature),
        "heater_margin": s(at["heater"]["margin"]),
        "flash_margin": s(at["flash"]["margin"]),
        "mixer_margin": s(at["mixer_margin"]),
    }
    return {
        "NLP-1": {
            "decisions": [
                {
                    "id": "U-SPLIT.split_fraction",
                    "lower": s(BOX["r"][0]),
                    "upper": s(BOX["r"][1]),
                    "scale": "1.0",
                },
                {
                    "id": "U-FLASH.T_spec",
                    "lower": s(BOX["t_f"][0]),
                    "upper": s(BOX["t_f"][1]),
                    "scale": "100.0",
                },
            ],
            "objective": "(U-HEAT.Q + U-FLASH.Q)/1e5 + 100 (U-HEAT.Q/1e5)^2",
            "constraints": [
                {
                    "id": "recovery_A",
                    "expression": "(S4.n.A - 0.75 S1.n.A)/3",
                    "lower": "0.0",
                    "upper": None,
                }
            ],
            "starts": starts,
            "reference_optimum": reference,
            "active_set": ["recovery_A"],
            "second_order_expected_report": "not_assessed",
        },
        "NLP-INF": {
            "as": "NLP-1",
            "constraints": [
                {
                    "id": "recovery_A",
                    "expression": "(S4.n.A - 1.05 S1.n.A)/3",
                    "lower": "0.0",
                    "upper": None,
                }
            ],
            "expected_status_in": ["INFEASIBLE_REPORTED", "NOT_VERIFIED", "SOLVER_FAILED"],
        },
    }


# -- assembly --------------------------------------------------------------------------------------


def build() -> dict[str, Any]:
    CLAIMS.clear()
    states = {label: sensitivity_state(label, entry) for label, entry in STATES.items()}
    zero_kinds = classify_zeros(states)
    for label, record in states.items():
        record["structural_zeros"] = [
            [o, p, zero_kinds[(label, o, p)]] for o, p in record["structural_zeros"]
        ]
    p1 = flowsheet(STATES["P1"]["params"])
    document: dict[str, Any] = {
        "schema": "m03-reference-v1",
        "generator": GENERATOR,
        "specification": SPEC,
        "note": (
            "Every number is a decimal string at 20 significant digits from mpmath at 60 digits, "
            "or the repr of a registered binary64 input; none is produced by openflowsheet."
        ),
        "constants": {
            "tau_regime": s(TAU_REGIME),
            "tau_root": s(TAU_ROOT),
            "tau_alias": s(TAU_ALIAS),
            "tau_id": s(TAU_ID),
            "tau_abs_scaled": s(TAU_ABS),
            "tau_rel": s(TAU_REL),
            "tau_fd_scaled": s(TAU_FD),
            "scales": {k: s(v) for k, v in SCALE_KIND.items()},
            "parameters": [{"id": pid, "scale": s(scale_of(kind))} for pid, _, kind in PARAMETERS],
            "outputs": [{"id": o, "scale": s(SCALE_KIND[kind])} for o, kind in OUTPUTS]
            + [{"id": Q_TOTAL[0], "coefficients": Q_TOTAL[1], "scale": s(SCALE_KIND[Q_TOTAL[2]])}],
        },
        "sensitivity_states": states,
        "parameter_jacobian_P1": {
            "U-SPLIT.split_fraction": {
                **{f"U-SPLIT:SPLIT-recycle:{n}": s(-p1["S5.n"][i]) for i, n in enumerate(NAMES)},
                **{f"U-SPLIT:SPLIT-purge:{n}": s(p1["S5.n"][i]) for i, n in enumerate(NAMES)},
            },
            "U-FLASH.T_spec": {"U-FLASH:FLASH-T:vapor": "-1.0", "U-FLASH:FLASH-T:liquid": "-1.0"},
            "U-HEAT.T_spec": {"U-HEAT:HEAT-T": "-1.0"},
            "U-FEED.T_spec": {"U-FEED:FEED-T": "-1.0"},
            "U-FEED.n_spec.A": {"U-FEED:FEED-n:A": "-1.0"},
        },
        "alias_refusals": {
            "state": "P1",
            "eliminated_rows": ["U-FLASH:FLASH-P:inlet", "U-SPLIT:SPLIT-P:recycle"],
            "refused_columns": ["U-FLASH.P_spec", "U-FEED.P_spec"],
            "expected_refusal": "INCONSISTENT_WITH_ELIMINATED_ROWS",
            "note": (
                "Each pressure specification alone moves a pressure that an eliminated alias row "
                "ties to the other; the scaled tangent residual of the eliminated rows is 1 "
                "(measured 1.0 exactly for both, 0.0 for the five registered parameters)."
            ),
        },
        "boundary_states": boundary_states(),
        "toys": toys(),
        "sweep": sweep(),
        "estimation": estimation(),
        "nlp": nlp(),
    }
    document["generator_claims"] = list(CLAIMS)
    return document


def encode(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="re-derive every claim and compare with the committed file",
    )
    parser.add_argument("--emit", metavar="PATH", help="write the reference JSON")
    args = parser.parse_args(argv)
    if not (args.check or args.emit):
        parser.error("choose --check and/or --emit PATH")
    payload = encode(build())
    if args.check:
        print(f"{len(CLAIMS)} claims passed")
        committed = DEFAULT_OUT.read_bytes() if DEFAULT_OUT.exists() else b""
        if committed != payload:
            print(f"{DEFAULT_OUT} differs from the generator's output", file=sys.stderr)
            return 1
        print(f"{DEFAULT_OUT} is byte-identical to the generator's output")
    if args.emit:
        Path(args.emit).parent.mkdir(parents=True, exist_ok=True)
        Path(args.emit).write_bytes(payload)
        print("wrote", args.emit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
