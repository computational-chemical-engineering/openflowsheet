"""S07 measurement 8 (Amendment 1): the domain rule of Amendment 1 applied to every CoolProp 8.0.0 fluid, with a
double-precision forecast of the generator claims C6, C8 and C9 using CoolProp's own saturation and partials.

A forecast, not an expectation: the generator recomputes every number at 50 digits (claims C5-C9, C15). Writes argv[1]
(JSON) and argv[2] (the Markdown fluid table of spec A1.3). Scratch venv only.
"""

import json
import math
import re
import sys
from multiprocessing import Pool

import CoolProp.CoolProp as CP

S04 = {
    "Water": "H2O",
    "CarbonDioxide": "CO2",
    "Nitrogen": "N2",
    "Oxygen": "O2",
    "Argon": "Ar",
    "Methane": "CH4",
    "Ethane": "C2H6",
    "n-Propane": "C3H8",
    "Hydrogen": "H2",
}
P_LO = 1.0e2
KAPPA = 1.0e-8  # 1/Pa: assumed bound on (1/T_t) dT_m/dP for a fluid without a melting line (A1.4)
P_FLOOR = 5.0e6
# term types whose closed form (spec 2.2 and A1.2) reproduces CoolProp's partials at the floor (m7)
FORMS = {
    "IdealGasHelmholtzLead",
    "IdealGasHelmholtzEnthalpyEntropyOffset",
    "IdealGasHelmholtzLogTau",
    "IdealGasHelmholtzPlanckEinstein",
    "IdealGasHelmholtzPlanckEinsteinFunctionT",
    "IdealGasHelmholtzPlanckEinsteinGeneralized",
    "IdealGasHelmholtzPower",
    "IdealGasHelmholtzCP0PolyT",
    "IdealGasHelmholtzCP0Constant",
    "ResidualHelmholtzPower",
    "ResidualHelmholtzGaussian",
    "ResidualHelmholtzNonAnalytic",
    "ResidualHelmholtzExponential",
    "ResidualHelmholtzDoubleExponential",
    "ResidualHelmholtzLemmon2005",
    "ResidualHelmholtzGaoB",
}
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


def ceil_sig(x, n):
    e = math.floor(math.log10(x)) - (n - 1)
    return math.ceil(x / 10.0**e - 1e-9) * 10.0**e


def comp_id(name):
    return S04.get(name, name.replace("(", "_").replace(")", ""))


def dpdrho(a, rho, T):
    a.update(CP.DmolarT_INPUTS, rho, T)
    d = a.delta()
    return a.gas_constant() * T * (1 + 2 * d * a.dalphar_dDelta() + d * d * a.d2alphar_dDelta2())


def pressure(a, rho, T):
    a.update(CP.DmolarT_INPUTS, rho, T)
    return rho * a.gas_constant() * T * (1 + a.delta() * a.dalphar_dDelta())


def one(name):
    d = json.loads(CP.get_fluid_param_string(name, "JSON"))
    d = d[0] if isinstance(d, list) else d
    e = d["EOS"][0]
    r = {
        "id": comp_id(name),
        "cas": d["INFO"].get("CAS", ""),
        "eos": e.get("BibTeX_EOS", ""),
        "pseudo_pure": bool(e["pseudo_pure"]),
        "n_eos": len(d["EOS"]),
    }
    r["types"] = sorted({t["type"] for t in e["alpha0"] + e["alphar"]})
    r["superancillary"] = "SUPERANCILLARY" in e
    if r["pseudo_pure"]:
        r["admitted"], r["reason"] = False, "pseudo-pure mixture"
        return name, r
    if set(r["types"]) - FORMS:
        r["admitted"], r["reason"] = (
            False,
            "term type without a verified closed form: "
            + ",".join(sorted(set(r["types"]) - FORMS)),
        )
        return name, r
    a = CP.AbstractState("HEOS", name)
    Tt, pt, Tc, pc = (
        a.Ttriple(),
        a.trivial_keyed_output(CP.iP_triple),
        a.T_critical(),
        a.p_critical(),
    )
    T_hi = min(a.Tmax(), 1273.15)
    r.update(Tt=Tt, pt=pt, Tc=Tc, pc=pc, T_hi=T_hi, pmax=a.pmax())
    if a.has_melting_line():
        P_hi = min(a.pmax(), 1.0e8)
        p_mmin, p_mmax = a.melting_line(CP.iP_min, -1, -1), a.melting_line(CP.iP_max, -1, -1)
        r.update(melt_p_min=p_mmin, melt_p_max=p_mmax)
        if p_mmax < P_hi:
            r["admitted"], r["reason"] = False, "melting line ends below P_hi"
            return name, r
        p0 = max(pt, P_LO, p_mmin)
        grid = [p0 * (P_hi / p0) ** (i / 19) for i in range(20)]
        try:
            tm = [a.melting_line(CP.iT, CP.iP, p) for p in grid]
        except Exception as ex:  # noqa: BLE001
            r["admitted"], r["reason"] = False, "melting_line raises: " + str(ex)[:60]
            return name, r
        if max(tm) <= Tt:
            T_lo, bound = Tt, "triple (melting line below T_t)"
            mono = all(tm[i + 1] <= tm[i] for i in range(19))
        else:
            T_lo, bound = math.ceil(10 * tm[-1] - 1e-9) / 10, "melting line"
            mono = all(tm[i + 1] > tm[i] for i in range(19))
        r["C9_monotone"] = mono
    else:
        P_hi = min(a.pmax(), max(P_FLOOR, ceil_sig(1.1 * pc, 2)))
        T_lo, bound = math.ceil(10 * Tt * (1 + KAPPA * P_hi) - 1e-9) / 10, "triple-point estimate"
    r.update(P_hi=P_hi, T_lo=T_lo, bound=bound)
    reasons = []
    if not T_lo < Tc * (1 - 1e-2):
        reasons.append("T_lo >= 0.99 T_c (no saturation range)")
    if not T_hi > Tc * (1 + 2e-3):
        reasons.append("T_hi <= T_c(1+2e-3) (near-critical box not inside)")
    if not P_hi > pc * (1 + 8e-3):
        reasons.append("P_hi <= p_c(1+8e-3) (near-critical box not inside)")
    if reasons:
        r["admitted"], r["reason"] = False, "; ".join(reasons)
        return name, r
    # forecast C6, C8 with CoolProp's saturation (measurement only)
    fc = []
    try:
        Tsm = Tc * (1 - 2e-4)
        a.update(CP.QT_INPUTS, 0, Tsm)
        if not a.p() > pc * (1 - 4e-3):
            fc.append("C6: p_sigma(T_sigma,max) <= p_c(1-4e-3)")
        b = CP.AbstractState("HEOS", name)
        b.specify_phase(CP.iphase_liquid)
        b.update(CP.PT_INPUTS, P_hi, T_lo)
        rho_max = ceil_sig(1.10 * b.rhomolar(), 3)
        r["rho_max"] = rho_max
        g = CP.AbstractState("HEOS", name)
        g.specify_phase(CP.iphase_gas)
        Ts = [T_lo + (Tsm - T_lo) * i / 22 for i in range(23)]
        for T in Ts:
            a.update(CP.QT_INPUTS, 0, T)
            rl = a.rhomolar()
            a.update(CP.QT_INPUTS, 1, T)
            rv = a.rhomolar()
            for k in range(41):
                rho = rl + (rho_max - rl) * k / 40
                if not dpdrho(g, rho, T) > 0:
                    fc.append(f"C8: dp/drho <= 0 on LIQUID bracket at T={T:.3f} rho={rho:.4g}")
                    break
            for k in range(1, 42):
                rho = rv * k / 41
                if not dpdrho(g, rho, T) > 0:
                    fc.append(f"C8: dp/drho <= 0 on VAPOR bracket at T={T:.3f}")
                    break
            if not pressure(g, rho_max, T) > P_hi:
                fc.append(f"C8: p(rho_max) <= P_hi at T={T:.3f}")
        for i in range(8):
            T = Tc * (1 + 2e-3) + (T_hi - Tc * (1 + 2e-3)) * i / 7
            for k in range(1, 42):
                rho = rho_max * k / 41
                if not dpdrho(g, rho, T) > 0:
                    fc.append(f"C8: dp/drho <= 0 supercritical at T={T:.1f} rho={rho:.4g}")
                    break
            if not pressure(g, rho_max, T) > P_hi:
                fc.append(f"C8: p(rho_max) <= P_hi at T={T:.1f}")
    except Exception as ex:  # noqa: BLE001 - recorded as a forecast failure
        fc.append("forecast raised: " + str(ex)[:80])
    # forecast C10/C11 for the Amendment 1 TP-state rules (A1.6): inside the box, outside NC, distinct, and
    # CoolProp's own PropsSI answers there (it is C11's independent solve)
    try:
        Tsm = Tc * (1 - 2e-4)
        T_mid = (T_lo + Tsm) / 2
        a.update(CP.QT_INPUTS, 0, T_mid)
        ps = a.p()
        st = {
            "V_sup": (min(1.5 * Tc, T_hi), 0.1 * pc),
            "V_sub": (T_mid, 0.5 * ps),
            "L_sub": (T_mid, 2 * ps),
            "S_dense": (min(1.2 * Tc, T_hi), min(3 * pc, P_hi)),
            "L_corner": (T_lo, P_hi),
            "V_corner": (T_hi, P_LO),
        }
        r["clamped"] = sorted(
            k
            for k, v in {
                "V_sup": 1.5 * Tc > T_hi,
                "S_dense_T": 1.2 * Tc > T_hi,
                "S_dense_P": 3 * pc > P_hi,
            }.items()
            if v
        )
        if len(set(st.values())) != len(st):
            fc.append("C10: TP states not distinct")
        for k, (T, P) in st.items():
            inside = T_lo <= T <= T_hi and P_LO <= P <= P_hi
            nc = Tsm < T < Tc * (1 + 2e-3) and pc * (1 - 4e-3) <= P <= pc * (1 + 8e-3)
            if not inside or nc:
                fc.append(f"C10: {k} outside the box or in NC")
            try:
                CP.PropsSI("H", "T", T, "P", P, name)
            except Exception as ex:  # noqa: BLE001
                fc.append(f"C11: PropsSI raises at {k}: " + str(ex)[:50])
    except Exception as ex:  # noqa: BLE001
        fc.append("TP forecast raised: " + str(ex)[:80])
    if r.get("C9_monotone") is False:
        fc.append("C9: melting line not monotone on the grid")
    r["forecast"] = fc
    r["admitted"] = not fc
    r["reason"] = "; ".join(fc) if fc else ""
    return name, r


if __name__ == "__main__":
    names = sorted(CP.get_global_param_string("FluidsList").split(","))
    with Pool(40) as p:
        res = dict(p.map(one, names, chunksize=1))
    json.dump(res, open(sys.argv[1], "w"), indent=1, sort_keys=True)
    adm = [n for n in names if res[n]["admitted"]]
    ids = [res[n]["id"] for n in adm]
    assert all(ID_RE.match(i) for i in ids) and len(set(ids)) == len(ids), "component ids"
    assert len({res[n]["cas"] for n in adm}) == len(adm), "CAS numbers"
    order = [n for n in S04 if n in adm] + sorted((n for n in adm if n not in S04), key=str.lower)
    with open(sys.argv[2], "w") as f:
        f.write(
            "| # | id | CoolProp name | EOS (`BibTeX_EOS`) | T_lo bound | T_lo, K | T_hi, K | P_hi, Pa |\n"
        )
        f.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")
        for i, n in enumerate(order, 1):
            r = res[n]
            kind = {"melting line": "M", "triple-point estimate": "E"}.get(r["bound"], "T")
            f.write(
                f"| {i} | {r['id']} | {n} | {r['eos']} | {kind} | {r['T_lo']:g} | {r['T_hi']:g} | {r['P_hi']:.3g} |\n"
            )
    print("fluids", len(names), "admitted", len(adm))
    for n in names:
        if not res[n]["admitted"]:
            print("EXCLUDED", n, "|", res[n]["reason"])
