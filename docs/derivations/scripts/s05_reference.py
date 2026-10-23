"""Design-lane reference generator for the S05 specification (IAPWS-95 pure water, ADR 0045).

Everything here follows from the closed-form Helmholtz function of
``docs/derivations/S05-IAPWS95-spec.md``
§2, evaluated with mpmath at 50 significant digits over the committed coefficient file
``s05_iapws95_coefficients.json``. It imports nothing from ``openflowsheet`` or ``benchmarks``.

**Independence.** Only φ° and φʳ are written down here. Every partial derivative of φ, every (T, P)
derivative of a property, the saturation slope and Tsat are obtained by ``mp.diff`` (numerical
differentiation at raised precision) or by root-finding on that one function. The implementation
uses closed-form derivatives (spec §3), so a wrong derivative there disagrees with a number here.
The spec's identities (spec §3.4) are then *claims* checked against those numbers.

**Admission.** A value is registered only when CoolProp 8.0.0 and ``iapws`` 1.5.5 both agree with it
within the per-quantity admission bound of spec §6.2. Their values come from the committed
``s05_crosscheck.json``, written by ``s05_crosscheck.py`` in a scratch venv; they also seed the root
solves, and the converged roots are claimed independent of the seed.

    python docs/derivations/scripts/s05_reference.py --check
    python docs/derivations/scripts/s05_reference.py --emit <path of the committed JSON>

``--check`` re-derives every claim, refuses to continue when one fails, and compares the result with
the committed file byte for byte. ``--emit`` runs the same claims and writes the file only when all
of them hold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from mpmath import mp, mpf

mp.dps = 50
HERE = Path(__file__).resolve().parent
COEFF_PATH = HERE / "s05_iapws95_coefficients.json"
CROSS_PATH = HERE / "s05_crosscheck.json"
DEFAULT_OUT = HERE / "s05_reference.json"
#: SHA-256 of the committed coefficient file (spec §2.1, S05.A01).
COEFF_SHA256 = "b9e93877e37874f1b3a483e298a45692e264d70686d4c158372084b96abbe6ed"
DIGITS = 25

# -- registration (spec §5); every input is evaluated at its nearest double ----------------------

#: (name, T [K], rho [kg/m3], why). Spec §5.1.
PHI_STATES: tuple[tuple[str, str, str, str], ...] = (
    (
        "R6_500",
        "500",
        "838.025",
        "R6-95 Table 6 (its only state), liquid-like; every phi term is non-zero",
    ),
    (
        "R6_647",
        "647",
        "358",
        "R6-95 Table 7 row (no printed phi values), near-critical; "
        "the non-analytic terms are large",
    ),
    (
        "delta_one",
        "700",
        "322",
        "delta = 1 exactly: |delta-1|^q vanishes with its derivatives (spec §3.2)",
    ),
)
#: (name, T [K], P [Pa], answered phase, why). Spec §5.2.
TP_STATES: tuple[tuple[str, str, str, str, str], ...] = (
    ("L_ambient", "300", "1.0e5", "LIQUID", "the common liquid; Z << 1, lnphi << 0"),
    (
        "L_corner",
        "273.16",
        "1.0e8",
        "LIQUID",
        "domain corner T_min, P_max; densest registered liquid",
    ),
    ("L_hot", "600", "2.0e7", "LIQUID", "hot compressed liquid, large dv/dT"),
    ("V_dilute", "400", "1.0e4", "VAPOR", "dilute vapour; Z - 1 small but non-zero"),
    ("V_nearsat", "500", "2.0e6", "VAPOR", "vapour at 0.76 p_sigma; strongly non-ideal"),
    ("V_corner", "273.16", "1.0e2", "VAPOR", "domain corner T_min, P_min (below p_t)"),
    ("SC_dense", "700", "3.0e7", "VAPOR", "supercritical, liquid-like density, labelled VAPOR"),
    ("SC_corner", "1273.15", "1.0e8", "VAPOR", "domain corner T_max, P_max"),
    ("SC_ideal", "1273.15", "1.0e2", "VAPOR", "domain corner T_max, P_min; nearly ideal gas"),
    (
        "NC_vapour",
        "647.05",
        "2.19e7",
        "VAPOR",
        "T in (647.0 K, T_c), just below the near_critical box",
    ),
    ("NC_liquid", "647.05", "2.23e7", "LIQUID", "T in (647.0 K, T_c), just above the box"),
)
#: Saturation temperatures [K] (spec §5.3).
SAT_T: tuple[str, ...] = ("273.16", "275", "450", "625", "647")
#: Saturation pressures [Pa] for Tsat (spec §5.3).
SAT_P: tuple[str, ...] = ("101325", "1.0e6", "1.0e7")
#: Band probes at 450 K: P = p_sigma(450 K) * exp(k * EPS_SIGMA) (spec §4.2).
BAND_T = "450"
BAND_K: tuple[tuple[str, str], ...] = (
    ("out_lo", "-2"),
    ("in_lo", "-0.5"),
    ("at", "0"),
    ("in_hi", "0.5"),
    ("out_hi", "2"),
)

# -- the phase rule's constants (C10_DECISIONS, spec §4) ------------------------------------------

T_MIN, T_MAX, P_MIN, P_MAX = (mpf(float(x)) for x in ("273.16", "1273.15", "1.0e2", "1.0e8"))
T_SIGMA_MAX = mpf(float("647.0"))
EPS_SIGMA = mpf(float("1e-6"))
BOX_T = (mpf(float("647.0")), mpf(float("648.0")))
BOX_P = (mpf(float("2.20e7")), mpf(float("2.22e7")))
RHO_LIQ_MAX = mpf(float("1250"))

#: Spec §6.3 / Q-6: S05.A17's default tolerance in value units. CoolProp 8.0.0's central-difference
#: floor is recorded for information only: its solver noise (about 1e-10) is not a 4-eps solve.
FD_TOL = "1e-10 value units (spec §6.3, Q-6)"
#: Spec §6.2: every admission bound sits at least this factor above the measured worst agreement.
ADMISSION_MARGIN = 10
FLOOR: dict[str, Any] = {}

CLAIMS: list[str] = []


def claim(condition: bool, text: str) -> None:
    if not condition:
        raise SystemExit(f"claim failed: {text}")
    CLAIMS.append(text)


def d(x: str) -> Any:
    """The nearest double of the decimal ``x``, exactly, as an mpf."""
    return mpf(float(x))


def s(x: Any, digits: int = DIGITS) -> str:
    return mp.nstr(x, digits, min_fixed=-mp.inf, max_fixed=mp.inf) if x else "0.0"


# -- the coefficients (spec §2.1) ----------------------------------------------------------------


def load_coefficients() -> dict[str, Any]:
    raw = COEFF_PATH.read_bytes()
    claim(
        COEFF_SHA256 == "PENDING" or hashlib.sha256(raw).hexdigest() == COEFF_SHA256,
        "the coefficient file's SHA-256 equals the recorded one",
    )
    c = json.loads(raw, parse_float=mpf, parse_int=mpf)
    claim([len(c["ideal"]["n"]), len(c["ideal"]["gamma"])] == [8, 5], "8 n0 and 5 gamma0")
    claim(all(len(v) == 51 for v in c["power"].values()), "51 power terms (7 with c = 0)")
    claim(
        [x for x in c["power"]["c"][:7]] == [0] * 7 and min(c["power"]["c"][7:]) >= 1,
        "power terms 1-7 carry no exponential, 8-51 do",
    )
    claim(all(len(v) == 3 for v in c["gaussian"].values()), "3 Gaussian terms")
    claim(all(len(v) == 2 for v in c["nonanalytic"].values()), "2 non-analytic terms")
    return c


C = load_coefficients()
R_S, MOLAR_MASS = C["R_specific"], C["M"]
R = R_S * MOLAR_MASS
T_C, RHO_C = C["T_c"], C["rho_c"]
claim(mp.nstr(R, 13) == "8.314371357587", "molar R = R_s * M rounds to 8.314371357587 J/(mol K)")


def phi0(tau: Any, delta: Any) -> Any:
    n, g = C["ideal"]["n"], C["ideal"]["gamma"]
    out = mp.log(delta) + n[0] + n[1] * tau + n[2] * mp.log(tau)
    return out + sum(n[3 + i] * mp.log(1 - mp.exp(-g[i] * tau)) for i in range(5))


def phir(tau: Any, delta: Any) -> Any:
    p, g, a = C["power"], C["gaussian"], C["nonanalytic"]
    out = mpf(0)
    for n, dd, t, c in zip(p["n"], p["d"], p["t"], p["c"], strict=True):
        term = n * delta**dd * tau**t
        out += term * mp.exp(-(delta**c)) if c else term
    for n, dd, t, al, be, ga, ep in zip(
        g["n"], g["d"], g["t"], g["alpha"], g["beta"], g["gamma"], g["epsilon"], strict=True
    ):
        out += n * delta**dd * tau**t * mp.exp(-al * (delta - ep) ** 2 - be * (tau - ga) ** 2)
    sq = (delta - 1) ** 2
    for n, aa, b, bb, cc, dd, aa_, be in zip(
        a["n"], a["a"], a["b"], a["B"], a["C"], a["D"], a["A"], a["beta"], strict=True
    ):
        theta = (1 - tau) + aa_ * sq ** (1 / (2 * be))
        big = theta**2 + bb * sq**aa
        psi = mp.exp(-cc * sq - dd * (tau - 1) ** 2)
        out += n * big**b * delta * psi
    return out


def dphi(f: Callable[[Any, Any], Any], tau: Any, delta: Any, i: int, j: int) -> Any:
    """d^(i+j) f / d tau^i d delta^j by mpmath's numerical differentiation."""
    return f(tau, delta) if i == j == 0 else mp.diff(f, (tau, delta), (i, j))


# -- properties at (T, rho) (spec §3.1) ----------------------------------------------------------


def at_rho(t: Any, rho: Any) -> dict[str, Any]:
    tau, delta = T_C / t, rho / RHO_C
    r = {k: dphi(phir, tau, delta, *k) for k in ((0, 0), (0, 1), (0, 2), (1, 0), (2, 0), (1, 1))}
    o = {k: dphi(phi0, tau, delta, *k) for k in ((0, 0), (1, 0), (2, 0))}
    z = 1 + delta * r[0, 1]
    cv = -(tau**2) * (o[2, 0] + r[2, 0])
    num = (1 + delta * r[0, 1] - delta * tau * r[1, 1]) ** 2
    den = 1 + 2 * delta * r[0, 1] + delta**2 * r[0, 2]
    return {
        "p": rho * R_S * t * z,
        "Z": z,
        "v": MOLAR_MASS / rho,
        "h": R * t * (1 + tau * (o[1, 0] + r[1, 0]) + delta * r[0, 1]),
        "s": R * (tau * (o[1, 0] + r[1, 0]) - o[0, 0] - r[0, 0]),
        "cp": R * (cv + num / den),
        "lnphi_H2O": r[0, 0] + delta * r[0, 1] - mp.log(z),
        "g": R * t * (o[0, 0] + r[0, 0] + z),
        "dp_drho": R_S * t * den,
    }


def pressure(t: Any, rho: Any) -> Any:
    return rho * R_S * t * (1 + rho / RHO_C * dphi(phir, T_C / t, rho / RHO_C, 0, 1))


def dp_drho(t: Any, rho: Any) -> Any:
    tau, delta = T_C / t, rho / RHO_C
    return (
        R_S
        * t
        * (1 + 2 * delta * dphi(phir, tau, delta, 0, 1) + delta**2 * dphi(phir, tau, delta, 0, 2))
    )


def rho_root(t: Any, p: Any, seed: Any, check: bool = True) -> Any:
    rho = mp.findroot(lambda r: pressure(t, r) / p - 1, mpf(seed), tol=mpf(10) ** (-2 * mp.dps + 8))
    if check:
        claim(
            dp_drho(t, rho) > 0 and rel(pressure(t, rho), p) < mpf(10) ** (4 - mp.dps),
            f"the root at {s(t, 8)} K, {s(p, 8)} Pa converged with dp/drho > 0",
        )
    return rho


def cdiff(f: Callable[[Any], dict[str, Any]], x: Any) -> dict[str, Any]:
    """Central difference at 110 digits, h = 1e-45 relative: truncation ~1e-90, roundoff ~1e-65."""
    with mp.workdps(110):
        h = abs(x) * mpf("1e-45")
        fp, fm = f(x + h), f(x - h)
        out = {k: (fp[k] - fm[k]) / (2 * h) for k in fp}
    return {k: +v for k, v in out.items()}


PROPS = ("h", "s", "v", "Z", "cp", "lnphi_H2O")


def tp_values(t: Any, p: Any, seed: Any, check: bool = True) -> dict[str, Any]:
    rho = rho_root(t, p, seed, check)
    out = {k: at_rho(t, rho)[k] for k in PROPS}
    out["rho"] = rho
    return out


# -- saturation (spec §3.5) ----------------------------------------------------------------------


def saturation(t: Any, seed_l: Any, seed_v: Any) -> dict[str, Any]:
    def eqs(rl: Any, rv: Any) -> list[Any]:
        a, b = at_rho(t, rl), at_rho(t, rv)
        return [a["p"] / b["p"] - 1, (a["g"] - b["g"]) / (R * t)]

    rl, rv = mp.findroot(eqs, (mpf(seed_l), mpf(seed_v)), tol=mpf(10) ** (-2 * mp.dps + 8))
    a, b = at_rho(t, rl), at_rho(t, rv)
    return {"psat": a["p"], "rho_l": rl, "rho_v": rv, "liq": a, "vap": b}


SEEDS: dict[str, Any] = {}


def psat(t: Any) -> Any:
    sl, sv = SEEDS["sat_seed"]
    return saturation(t, sl, sv)["psat"]


# -- the phase rule (spec §4); returns the answered phases or the refusal code --------------------


def rule(t: Any, p: Any, ps: Any | None) -> tuple[str, ...] | str:
    if not (T_MIN <= t <= T_MAX and P_MIN <= p <= P_MAX):
        return "out_of_domain"
    if BOX_T[0] < t < BOX_T[1] and BOX_P[0] <= p <= BOX_P[1]:
        return "near_critical"
    if t >= T_C:
        return ("VAPOR",)
    if t > T_SIGMA_MAX:
        if p >= C["p_c"]:
            return ("LIQUID",)
        return ("VAPOR",) if p < BOX_P[0] else "near_critical"
    z = mp.log(p / ps)
    return tuple(ph for ph, ok in (("LIQUID", z >= -EPS_SIGMA), ("VAPOR", z <= EPS_SIGMA)) if ok)


# -- the build -----------------------------------------------------------------------------------


def rel(a: Any, b: Any) -> Any:
    return abs(a - b) / max(abs(b), mpf("1e-300"))


def admit(
    section: str,
    key: str,
    value: Any,
    cross: dict[str, Any],
    bound: str,
    agreement: dict[str, Any],
    scale: Any = None,
) -> None:
    """Claim CoolProp and iapws agree with ``value`` within ``bound`` (relative, or absolute in
    units of ``scale``) and record the worst disagreement per (section, quantity)."""
    q = key.split("/")[-1]
    worst = agreement.setdefault(
        f"{section}/{q}", {"bound": bound, "CoolProp": "0.0", "iapws": "0.0"}
    )
    for impl in ("CoolProp", "iapws"):
        other = cross[impl].get(key)
        if other is None:
            continue
        err = abs(mpf(other) - value) / scale if scale is not None else rel(mpf(other), value)
        claim(err <= mpf(bound), f"{impl} agrees with {key} within {bound}")
        worst[impl] = s(max(mpf(worst[impl]), err), 3)


def build() -> dict[str, Any]:
    cross = json.loads(CROSS_PATH.read_text(encoding="utf-8"))
    claim(cross["versions"] == {"CoolProp": "8.0.0", "iapws": "1.5.5"}, "cross-check versions")
    claim(
        cross["coefficients_sha256"] == hashlib.sha256(COEFF_PATH.read_bytes()).hexdigest(),
        "the cross-check ran on the committed coefficient file",
    )
    claim(
        cross["iapws_coefficients_equal"] is True,
        "iapws 1.5.5 carries the same coefficients exactly",
    )
    agreement: dict[str, Any] = {}
    bounds = cross["admission_bounds"]
    doc: dict[str, Any] = {
        "generator": "s05_reference.py",
        "mp_dps": mp.dps,
        "digits": DIGITS,
        "coefficients_sha256": cross["coefficients_sha256"],
        "R_molar": s(R),
    }

    # §5.1 phi and its derivatives at (T, rho)
    names = {
        (0, 0): "",
        (0, 1): "_d",
        (0, 2): "_dd",
        (1, 0): "_t",
        (2, 0): "_tt",
        (1, 1): "_dt",
        (0, 3): "_ddd",
        (1, 2): "_ddt",
        (2, 1): "_dtt",
        (3, 0): "_ttt",
    }
    phi_out: dict[str, Any] = {}
    for name, t_, rho_, why in PHI_STATES:
        t, rho = d(t_), d(rho_)
        tau, delta = T_C / t, rho / RHO_C
        row: dict[str, Any] = {"T": t_, "rho": rho_, "why": why, "tau": s(tau), "delta": s(delta)}
        for (i, j), suf in names.items():
            if i + j == 3 and name == "delta_one":
                continue  # |delta-1|^(10/3) is only C^3 there; mp.diff's third order is not exact
            for label, f in (("phi0", phi0), ("phir", phir)):
                if label == "phi0" and (i, j) not in (
                    (0, 0),
                    (0, 1),
                    (0, 2),
                    (1, 0),
                    (2, 0),
                    (1, 1),
                ):
                    continue
                val = dphi(f, tau, delta, i, j) if not (label == "phi0" and i and j) else mpf(0)
                row[label + suf] = s(val)
                if (i + j) <= 2:
                    row[label + suf + "_9"] = mp.nstr(val, 9)
                    admit(
                        "phi",
                        f"phi/{name}/{label}{suf}",
                        val,
                        cross,
                        bounds["phi"],
                        agreement,
                        scale=max(abs(val), mpf(1)),
                    )
        props = at_rho(t, rho)
        for k in ("p", "h", "s", "cp", "lnphi_H2O"):
            row[k] = s(props[k])
        phi_out[name] = row
    claim(abs(mpf(phi_out["delta_one"]["delta"]) - 1) == 0, "delta_one has delta = 1 exactly")
    claim(
        all(mpf(phi_out["delta_one"]["phir" + suf]) != 0 for suf in ("", "_d", "_dd", "_t")),
        "phir and its derivatives stay non-zero at delta = 1 (only the |delta-1|^q factors vanish)",
    )
    doc["phi_states"] = phi_out

    # §5.3 saturation, first, since the phase rule needs p_sigma
    sat_out: dict[str, Any] = {}
    for t_ in SAT_T:
        t = d(t_)
        sl, sv = (mpf(x) for x in cross["seeds"][f"sat/{t_}"])
        SEEDS["sat_seed"] = (sl, sv)
        sat = saturation(t, sl, sv)
        slope = cdiff(lambda x: {"p": psat(x)}, t)["p"]
        liq, vap = sat["liq"], sat["vap"]
        cc = (vap["s"] - liq["s"]) / (vap["v"] - liq["v"])
        claim(rel(cc, slope) < mpf("1e-20"), f"Clausius-Clapeyron holds at {t_} K")
        claim(
            rel(liq["lnphi_H2O"], vap["lnphi_H2O"]) < mpf("1e-30")
            or abs(liq["lnphi_H2O"] - vap["lnphi_H2O"]) < mpf("1e-35"),
            f"lnphi_L = lnphi_V at {t_} K",
        )
        claim(sat["rho_l"] > RHO_C > sat["rho_v"], f"rho' > rho_c > rho'' at {t_} K")
        row = {
            "T": t_,
            "Psat": s(sat["psat"]),
            "dPsat_dT": s(slope),
            "rho_l": s(sat["rho_l"]),
            "rho_v": s(sat["rho_v"]),
        }
        for ph, pr in (("l", liq), ("v", vap)):
            for k in PROPS:
                row[f"{k}_{ph}"] = s(pr[k])
        for k in ("Psat", "rho_l", "rho_v", "h_l", "h_v", "s_l", "s_v"):
            scale = R if k[0] == "s" else (R * t if k[0] == "h" else None)
            admit(
                "sat",
                f"sat/{t_}/{k}",
                mpf(row[k]),
                cross,
                bounds["sat_" + k.split("_")[0]],
                agreement,
                scale,
            )
        sat_out[t_] = row
    tt = sat_out["273.16"]
    u_t = mpf(tt["h_l"]) - mpf(tt["Psat"]) * mpf(tt["v_l"])
    claim(
        abs(u_t) < mpf("1e-6") and abs(mpf(tt["s_l"])) < mpf("1e-8"),
        "datum: u' and s' vanish at the triple point to the rounding of n0_1, n0_2",
    )
    claim(
        abs(mpf(sat_out["450"]["h_l"])) > 1000 and abs(mpf(sat_out["450"]["s_l"])) > 10,
        "control: h' and s' do not vanish at 450 K",
    )
    doc["datum"] = {"u_l_triple": s(u_t, 6), "s_l_triple": s(mpf(tt["s_l"]), 6)}
    doc["saturation"] = sat_out

    tsat_out: dict[str, Any] = {}
    for p_ in SAT_P:
        p = d(p_)
        t0 = mpf(cross["seeds"][f"tsat/{p_}"][0])
        SEEDS["sat_seed"] = tuple(mpf(x) for x in cross["seeds"][f"tsat/{p_}"][1:])
        t = mp.findroot(lambda x, p=p: psat(x) / p - 1, t0, tol=mpf(10) ** (-2 * mp.dps + 10))
        slope = cdiff(lambda x: {"p": psat(x)}, t)["p"]
        tsat_out[p_] = {"P": p_, "Tsat": s(t), "dTsat_dP": s(1 / slope)}
        admit("sat", f"tsat/{p_}/Tsat", t, cross, bounds["sat_Tsat"], agreement)
    doc["tsat"] = tsat_out

    # §4 the critical box and the 647.0 K edge
    SEEDS["sat_seed"] = tuple(mpf(x) for x in cross["seeds"]["sat/647"])
    p647 = psat(T_SIGMA_MAX)
    pc_eos = pressure(T_C, RHO_C)
    claim(p647 > BOX_P[0], "p_sigma(647.0 K) > 22.0 MPa")
    claim(
        BOX_T[0] < T_C < BOX_T[1] and BOX_P[0] <= C["p_c"] <= BOX_P[1],
        "the critical point is in the box",
    )
    claim(rel(pc_eos, C["p_c"]) < mpf("1e-5"), "p(rho_c, T_c) = 22.064 MPa within 1e-5")
    doc["critical"] = {"p_eos_at_rhoc_Tc": s(pc_eos), "psat_647": s(p647)}

    # §4.2 the band at 450 K and at the 647.0 K edge
    ps450 = mpf(sat_out[BAND_T]["Psat"])
    band: dict[str, Any] = {}
    for label, k in BAND_K:
        p = mpf(float(ps450 * mp.exp(mpf(k) * EPS_SIGMA)))
        answered = rule(d(BAND_T), p, ps450)
        row = {"P": repr(float(p)), "answered": list(answered)}
        for ph in answered:
            seed = sat_out[BAND_T]["rho_l" if ph == "LIQUID" else "rho_v"]
            vals = tp_values(d(BAND_T), p, seed)
            row[ph] = {k2: s(vals[k2]) for k2 in (*PROPS, "rho")}
        band[label] = row
    claim(
        [band[x]["answered"] for x, _ in BAND_K]
        == [["VAPOR"], ["LIQUID", "VAPOR"], ["LIQUID", "VAPOR"], ["LIQUID", "VAPOR"], ["LIQUID"]],
        "band: out_lo vapour only, in_lo/at/in_hi both, out_hi liquid only",
    )
    at_ = band["at"]
    claim(
        abs(mpf(at_["LIQUID"]["lnphi_H2O"]) - mpf(at_["VAPOR"]["lnphi_H2O"])) < mpf("1e-14"),
        "at P = p_sigma (as a double) both roots have equal lnphi to 1e-14",
    )
    for ph, k in (("LIQUID", "-1"), ("VAPOR", "1")):
        p = p647 * mp.exp(mpf(k) * EPS_SIGMA)
        seed = cross["seeds"]["sat/647"][0 if ph == "LIQUID" else 1]
        r = rho_root(T_SIGMA_MAX, p, seed)
        claim(
            (r > RHO_C) == (ph == "LIQUID"),
            f"the metastable {ph} root exists at 647.0 K at the band edge",
        )
    doc["band"] = {"T": BAND_T, "eps_sigma": "1e-6", "probes": band}

    # §5.2 single-phase states: values, (T, P) derivatives, and the identities of spec §3.4
    tp_out: dict[str, Any] = {}
    for name, t_, p_, phase, why in TP_STATES:
        t, p = d(t_), d(p_)
        seed = mpf(cross["seeds"][f"tp/{name}"])
        ps = None
        if t <= T_SIGMA_MAX:
            SEEDS["sat_seed"] = tuple(mpf(x) for x in cross["seeds"][f"tp_sat/{name}"])
            ps = psat(t)
        claim(rule(t, p, ps) == (phase,), f"{name}: the rule answers {phase} only")
        vals = tp_values(t, p, seed)
        row: dict[str, Any] = {"T": t_, "P": p_, "phase": phase, "why": why, "rho": s(vals["rho"])}
        nc = name.startswith("NC_")
        sec, fac = ("tp_nc", mpf(bounds["near_critical_factor"])) if nc else ("tp", mpf(1))

        def bound(key: str) -> str:
            return mp.nstr(mpf(bounds[key]) * fac, 3)  # noqa: B023

        r0 = vals["rho"]
        by_t = cdiff(lambda x, p=p, r0=r0: tp_values(x, p, r0, False), t)
        by_p = cdiff(lambda x, t=t, r0=r0: tp_values(t, x, r0, False), p)
        for k in PROPS:
            row[k] = s(vals[k])
            row[f"d{k}_dT"], row[f"d{k}_dP"] = s(by_t[k]), s(by_p[k])
            if k in ("h", "s", "cp", "v", "Z"):
                admit(
                    sec,
                    f"tp/{name}/{k}",
                    vals[k],
                    cross,
                    bound("tp_" + k),
                    agreement,
                    scale=R * t if k == "h" else (R if k == "s" else None),
                )
        for k in ("h", "s", "v"):
            for var, src in (("T", by_t), ("P", by_p)):
                admit(
                    sec + "d",
                    f"dtp/{name}/d{k}_d{var}",
                    src[k],
                    cross,
                    bound("tp_deriv"),
                    agreement,
                )
                fd = mpf(cross["CoolProp_fd"][f"fd/{name}/d{k}_d{var}"])
                key = f"d{k}_d{var}"
                FLOOR[key] = max(FLOOR.get(key, mpf(0)), rel(fd, src[k]))
        for k in ("Z", "cp", "lnphi_H2O"):
            for var, src in (("T", by_t), ("P", by_p)):
                fd = mpf(cross["CoolProp_fd"][f"fd/{name}/d{k}_d{var}"])
                key = f"d{k}_d{var}"
                FLOOR[key] = max(FLOOR.get(key, mpf(0)), rel(fd, src[k]))
        admit(sec, f"tp/{name}/rho", vals["rho"], cross, bound("tp_rho"), agreement)
        admit(
            sec,
            f"tp/{name}/lnphi_H2O",
            vals["lnphi_H2O"],
            cross,
            bound("tp_lnphi"),
            agreement,
            scale=mpf(1),
        )
        cp, z, v = vals["cp"], vals["Z"], vals["v"]
        h_res = R * t * ((T_C / t) * dphi(phir, T_C / t, vals["rho"] / RHO_C, 1, 0) + z - 1)
        tol = mpf("1e-20")
        for text, lhs, rhs in (
            ("I1 dh/dT|P = cp", by_t["h"], cp),
            ("I2 ds/dT|P = cp/T", by_t["s"], cp / t),
            ("I3 ds/dP|T = -dv/dT|P", by_p["s"], -by_t["v"]),
            ("I4 dh/dP|T = v - T dv/dT|P", by_p["h"], v - t * by_t["v"]),
            ("I5 dlnphi/dP|T = (Z-1)/P", by_p["lnphi_H2O"], (z - 1) / p),
            ("I6 dlnphi/dT|P = -(h - h_ig)/(R T^2)", by_t["lnphi_H2O"], -h_res / (R * t**2)),
            ("I7 dZ/dP|T from Z = Pv/(RT)", by_p["Z"], (z / p) * (1 + p * by_p["v"] / v)),
        ):
            claim(rel(lhs, rhs) < tol, f"{name}: {text} to 1e-20")
        claim(by_p["v"] < 0 and cp > 0, f"{name}: mechanically and thermally stable")
        tp_out[name] = row
    claim(
        len({(r["T"], r["P"]) for r in tp_out.values()}) == len(tp_out),
        "TP states pairwise distinct",
    )
    for k in ("h", "s", "v", "Z", "cp", "lnphi_H2O"):
        claim(
            len({tp_out[n][f"d{k}_dP"] for n in tp_out}) == len(tp_out),
            f"d{k}/dP pairwise distinct",
        )
    claim(
        abs(mpf(tp_out["SC_ideal"]["Z"]) - 1) > 10 * mpf(bounds["tp_Z"])
        and abs(mpf(tp_out["SC_ideal"]["lnphi_H2O"])) > 10 * mpf(bounds["tp_lnphi"]),
        "SC_ideal: |Z - 1| and |lnphi| exceed 10x their bounds (an ideal-gas answer fails)",
    )
    doc["tp_states"] = tp_out
    doc["fd_floor"] = {
        "step": cross["fd_step"],
        "tolerance": FD_TOL,
        "measured_CoolProp": {k: s(v, 3) for k, v in sorted(FLOOR.items())},
    }

    # §4.4 bracket claims over the grid (dp/drho > 0) at 20 digits
    doc["brackets"] = brackets(cross)
    for key, row in agreement.items():
        worst = max(mpf(row["CoolProp"]), mpf(row["iapws"]))
        claim(
            worst * ADMISSION_MARGIN <= mpf(row["bound"]),
            f"{key}: the bound {row['bound']} sits {ADMISSION_MARGIN}x above the worst agreement",
        )
    doc["agreement"] = agreement
    doc["claims"] = list(CLAIMS)
    doc["claim_count"] = len(CLAIMS)
    return doc


#: The bracket grid (spec §4.4): below T_c the band-extended branch brackets bounded by the
#: saturated
#: densities (647.05 K lies in (647.0 K, T_c), where Psat is not answered but bounds the brackets);
#: at and above T_c the single bracket (0, 1250] kg/m3.
GRID_SUB: tuple[str, ...] = (
    "273.16",
    "280",
    "300",
    "320",
    "340",
    "360",
    "380",
    "400",
    "420",
    "440",
    "460",
    "480",
    "500",
    "520",
    "540",
    "560",
    "580",
    "600",
    "620",
    "640",
    "645",
    "647",
    "647.05",
)
GRID_SUPER: tuple[str, ...] = ("647.1", "647.5", "648", "650", "700", "800", "1000", "1273.15")


def grid_claims(t: Any, intervals: Sequence[tuple[Any, Any]], label: str) -> int:
    for lo, hi in intervals:
        for i in range(41):
            r = lo + (hi - lo) * i / 40
            claim(dp_drho(t, r) > 0, f"dp/drho > 0 at {label} K, {s(r, 8)} kg/m3")
    claim(pressure(t, RHO_LIQ_MAX) > P_MAX, f"p(1250 kg/m3, {label} K) > 100 MPa")
    return 41 * len(intervals)


def brackets(cross: dict[str, Any]) -> dict[str, Any]:
    count = 0
    with mp.workdps(20):
        for t_ in GRID_SUB:
            t = d(t_)
            sat = saturation(t, *(mpf(x) for x in cross["seeds"][f"grid/{t_}"]))
            hi_v = rho_root(t, sat["psat"] * mp.exp(EPS_SIGMA), sat["rho_v"], False)
            lo_l = rho_root(t, sat["psat"] * mp.exp(-EPS_SIGMA), sat["rho_l"], False)
            claim(
                sat["rho_v"] < hi_v < RHO_C < lo_l < sat["rho_l"],
                f"band-edge roots on their branches at {t_} K",
            )
            count += grid_claims(t, ((hi_v / 40, hi_v), (lo_l, RHO_LIQ_MAX)), t_)
        claim(
            d(GRID_SUB[-1]) < T_C <= d(GRID_SUPER[0]), "the grid's last subcritical T is below T_c"
        )
        for t_ in GRID_SUPER:
            count += grid_claims(d(t_), ((RHO_LIQ_MAX / 60, RHO_LIQ_MAX),), t_)
    return {"points": count, "T_subcritical": list(GRID_SUB), "T_supercritical": list(GRID_SUPER)}


def encode(document: dict[str, Any]) -> bytes:
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
    claim(COEFF_SHA256 != "PENDING", "the coefficient file's SHA-256 is recorded")
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
