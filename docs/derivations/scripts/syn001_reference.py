"""Fable's independent derivation check and reference-value generator for SYN-001 (P01).

Everything here follows from the plan §3.1 definitions alone, evaluated with mpmath at
40 significant digits. It is NOT the oracle (``benchmarks/syn001/oracle.py``) and imports
nothing from ``process_runtime`` or ``benchmarks``. It exists so that the numbers in
``docs/derivations/SYN-001.md`` and ``benchmarks/syn001/reference_values.yaml`` have an
executable provenance that is independent of the implementation they are used to test.

Run from the repository root inside the project environment (mpmath is in the ``dev`` extra)::

    python docs/derivations/scripts/syn001_reference.py --check      # identities and sanity values
    python docs/derivations/scripts/syn001_reference.py --emit PATH  # write reference_values.yaml
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import Any

import yaml
from mpmath import diff, mp, mpf

mp.dps = 40

R_GAS = mpf("8.31446261815324")
T_REF = mpf(300)
P_REF = mpf(100000)
CP = mpf(100)
T_BOIL = (mpf(320), mpf(360), mpf(400))
L_VAP = (mpf(25000), mpf(30000), mpf(35000))
V_LIQ = (mpf("0.0001"),) * 3
NAMES = "ABC"
FRESH = (mpf(1), mpf(1), mpf(1))
T_FEED = mpf(300)
T_HEATER = mpf(350)
Vec = tuple[Any, ...]


# ---------------------------------------------------------------- pure-component potentials
def a_of_t(t: Any) -> Any:
    return CP * ((t - T_REF) - t * mp.log(t / T_REF))


def g_liquid(i: int, t: Any, p: Any) -> Any:
    return a_of_t(t) + V_LIQ[i] * (p - P_REF)


def g_vapor(i: int, t: Any, p: Any) -> Any:
    return a_of_t(t) + L_VAP[i] - t * L_VAP[i] / T_BOIL[i] + R_GAS * t * mp.log(p / P_REF)


def h_liquid(i: int, t: Any, p: Any) -> Any:
    return CP * (t - T_REF) + V_LIQ[i] * (p - P_REF)


def h_vapor(i: int, t: Any, p: Any) -> Any:
    return CP * (t - T_REF) + L_VAP[i]


def k_value(i: int, t: Any, p: Any) -> Any:
    expo = L_VAP[i] / R_GAS * (1 / T_BOIL[i] - 1 / t) + V_LIQ[i] * (p - P_REF) / (R_GAS * t)
    return P_REF / p * mp.exp(expo)


def k_vec(t: Any, p: Any) -> Vec:
    return tuple(k_value(i, t, p) for i in range(3))


def enthalpy_flow(n: Sequence[Any], t: Any, p: Any, phase: str) -> Any:
    h = h_liquid if phase == "L" else h_vapor
    return sum(n[i] * h(i, t, p) for i in range(3))


# ---------------------------------------------------------------- Rachford-Rice on a feed
def rr_function(z: Sequence[Any], k: Sequence[Any], beta: Any) -> Any:
    return sum(z[i] * (k[i] - 1) / (1 + beta * (k[i] - 1)) for i in range(3) if z[i] > 0)


def tp_flash(n: Sequence[Any], t: Any, p: Any) -> dict[str, Any]:
    """Single TP flash of feed n at (t, p); derivation §5.1 classification order."""
    total = sum(n)
    k = k_vec(t, p)
    if total == 0:
        return {"state": "ZERO_FLOW", "beta": None, "x": None, "y": None, "K": k}
    z = tuple(n[i] / total for i in range(3))
    szk = sum(z[i] * k[i] for i in range(3))
    szik = sum(z[i] / k[i] for i in range(3))
    if szk <= 1:
        return {
            "state": "LIQUID",
            "beta": mpf(0),
            "x": z,
            "y": None,
            "K": k,
            "szk": szk,
            "szik": szik,
        }
    if szik <= 1:
        return {
            "state": "VAPOR",
            "beta": mpf(1),
            "x": None,
            "y": z,
            "K": k,
            "szk": szk,
            "szik": szik,
        }
    active = [k[i] for i in range(3) if z[i] > 0]
    lo = max(mpf(0), 1 / (1 - max(active)) + mpf("1e-30"))
    hi = min(mpf(1), 1 / (1 - min(active)) - mpf("1e-30"))
    for _ in range(300):
        mid = (lo + hi) / 2
        if rr_function(z, k, mid) > 0:
            lo = mid
        else:
            hi = mid
    beta = (lo + hi) / 2
    x = tuple(z[i] / (1 + beta * (k[i] - 1)) for i in range(3))
    y = tuple(k[i] * x[i] for i in range(3))
    return {"state": "TWO_PHASE", "beta": beta, "x": x, "y": y, "K": k, "szk": szk, "szik": szik}


def bisect(fn: Any, lo: Any, hi: Any, iters: int = 200) -> Any:
    flo = fn(lo)
    for _ in range(iters):
        mid = (lo + hi) / 2
        if (fn(mid) > 0) == (flo > 0):
            lo, flo = mid, fn(mid)
        else:
            hi = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------- recycle flowsheet reference
def recycle_reference(r: Any, t_flash: Any, case_id: str) -> dict[str, Any]:
    """Derivation §5-§7: oracle values plus every stream and duty of the reference flowsheet."""
    total = sum(FRESH)
    fl = tp_flash(FRESH, t_flash, P_REF)
    beta = fl["beta"]
    vap = tuple(beta * total * yi for yi in fl["y"]) if fl["y"] else (mpf(0),) * 3
    liq_total = total * (1 - beta) / (1 - r)
    x = fl["x"]
    liquid = tuple(liq_total * xi for xi in x) if x else (mpf(0),) * 3
    rec = tuple(r * li for li in liquid)
    purge = tuple((1 - r) * li for li in liquid)
    vflow = beta * total
    mixed = tuple(FRESH[i] + rec[i] for i in range(3))
    mixed_total = sum(mixed)
    zmix = tuple(m / mixed_total for m in mixed)
    h_fresh = enthalpy_flow(FRESH, T_FEED, P_REF, "L")
    h_rec = enthalpy_flow(rec, t_flash, P_REF, "L") if sum(rec) > 0 else mpf(0)
    t_mix = (total * T_FEED + sum(rec) * t_flash) / mixed_total
    assert abs(enthalpy_flow(mixed, t_mix, P_REF, "L") - (h_fresh + h_rec)) < mpf("1e-30")
    mix = tp_flash(mixed, t_mix, P_REF)
    heat = tp_flash(mixed, T_HEATER, P_REF)
    if heat["state"] == "TWO_PHASE":
        vh = heat["beta"] * mixed_total
        lh = mixed_total - vh
        h_heat = enthalpy_flow([vh * t for t in heat["y"]], T_HEATER, P_REF, "V")
        h_heat += enthalpy_flow([lh * t for t in heat["x"]], T_HEATER, P_REF, "L")
    else:
        h_heat = enthalpy_flow(mixed, T_HEATER, P_REF, "L" if heat["state"] == "LIQUID" else "V")
    q_heater = h_heat - (h_fresh + h_rec)
    h_flash = enthalpy_flow(vap, t_flash, P_REF, "V") + enthalpy_flow(liquid, t_flash, P_REF, "L")
    q_flash = h_flash - h_heat
    h_prod = enthalpy_flow(vap, t_flash, P_REF, "V") + enthalpy_flow(purge, t_flash, P_REF, "L")
    assert abs(q_heater + q_flash - (h_prod - h_fresh)) < mpf("1e-30")
    for i in range(3):
        assert abs(FRESH[i] - vap[i] - purge[i]) < mpf("1e-30")

    def sig(stream: Sequence[Any], flowing: str) -> str:
        return "ZERO_FLOW" if sum(stream) == 0 else flowing

    return {
        "case_id": case_id,
        "r": s(r, 3),
        "T_heater_K": "350",
        "T_flash_K": s(t_flash, 5),
        "P_Pa": "100000",
        "K_at_flash": [s(k) for k in fl["K"]],
        "sum_zK_fresh": s(fl["szk"]),
        "sum_z_over_K_fresh": s(fl["szik"]),
        "flash_phase_state": fl["state"],
        "beta_fresh_feed_vapor_fraction": s(beta),
        "q_V_over_L": s(vflow / liq_total) if liq_total > 0 else "undefined (L = 0)",
        "V_mol_per_s": s(vflow),
        "L_mol_per_s": s(liq_total),
        "x": [s(t) for t in x] if x else "undefined (zero liquid flow)",
        "y": [s(t) for t in fl["y"]] if fl["y"] else "undefined (zero vapor flow)",
        "vapor_product_mol_per_s": [s(t) for t in vap],
        "purge_mol_per_s": [s(t) for t in purge],
        "recycle_mol_per_s": [s(t) for t in rec],
        "recycle_phase_signature": sig(rec, "LIQUID"),
        "vapor_product_phase_signature": sig(vap, "VAPOR"),
        "purge_phase_signature": sig(purge, "LIQUID"),
        "mixed_feed_mol_per_s": [s(t) for t in mixed],
        "T_mix_K": s(t_mix),
        "sum_zK_at_T_mix": s(mix["szk"]),
        "mixer_outlet_state": mix["state"],
        "heater_outlet_state": heat["state"],
        "sum_zK_at_350K_mixed": s(heat["szk"]),
        "sum_z_over_K_at_350K_mixed": s(heat["szik"]),
        "heater_outlet_vapor_fraction": s(heat["beta"]),
        "heater_outlet_x": [s(t) for t in heat["x"]] if heat["x"] else "undefined",
        "heater_outlet_y": [s(t) for t in heat["y"]] if heat["y"] else "undefined",
        "Q_heater_W": s(q_heater),
        "Q_flash_W": s(q_flash),
        "Q_total_W": s(q_heater + q_flash),
        "H_products_minus_H_fresh_W": s(h_prod - h_fresh),
        "H_fresh_W": s(h_fresh),
        "H_recycle_W": s(h_rec),
        "H_mixed_W": s(h_fresh + h_rec),
        "H_heater_out_W": s(h_heat),
        "H_flash_out_W": s(h_flash),
        "_zmix": zmix,
        "_t_mix": t_mix,
    }


def s(value: Any, digits: int = 20) -> str:
    """Decimal string with fixed significant digits (kept as a string so YAML preserves it)."""
    return str(mp.nstr(value, digits, strip_zeros=False))


VARIANTS = (
    ("SYN-001-nominal", mpf("0.5"), mpf(360)),
    ("SYN-001-once-through", mpf(0), mpf(360)),
    ("SYN-001-high-recycle", mpf("0.95"), mpf(360)),
    ("SYN-001-all-liquid-310K", mpf("0.5"), mpf(310)),
    ("SYN-001-all-vapor-420K", mpf("0.5"), mpf(420)),
)


def equimolar_sum_zk(t: Any) -> Any:
    return sum(k_value(i, t, P_REF) for i in range(3)) / 3


def run_checks() -> int:
    """Identities and plan §3 sanity values; returns a process exit code."""
    failures = 0
    worst_gh = mpf(0)
    worst_k = mpf(0)
    for t in (mpf(280), mpf(300), mpf(347), mpf(360), mpf(440)):
        for p in (mpf(50000), P_REF, mpf(200000)):
            for i in range(3):
                for g, h in ((g_liquid, h_liquid), (g_vapor, h_vapor)):
                    g_t = diff(lambda tt, i=i, p=p, g=g: g(i, tt, p), t)
                    worst_gh = max(worst_gh, abs(h(i, t, p) - (g(i, t, p) - t * g_t)))
                k_mu = mp.exp((g_liquid(i, t, p) - g_vapor(i, t, p)) / (R_GAS * t))
                worst_k = max(worst_k, abs(k_mu / k_value(i, t, p) - 1))
    print("max |h - (g - T dg/dT)| over domain grid:", s(worst_gh, 5))
    print("max relative |K_closed_form / exp((gL-gV)/RT) - 1|:", s(worst_k, 5))
    failures += worst_gh > mpf("1e-30") or worst_k > mpf("1e-30")
    for i in range(3):
        kb = k_value(i, T_BOIL[i], P_REF)
        print(f"K_{NAMES[i]}(T_b, P_r) =", s(kb))
        failures += abs(kb - 1) > mpf("1e-35")
    k360 = k_vec(mpf(360), P_REF)
    print("K(360 K, P_r) =", [s(k, 25) for k in k360])
    plan_k = (mpf("2.8406442066"), mpf(1), mpf("0.3105797512"))
    failures += any(abs(k360[i] - plan_k[i]) > mpf("5e-11") for i in range(3))
    t_bub = bisect(lambda t: equimolar_sum_zk(t) - 1, mpf(340), mpf(355))
    t_dew = bisect(
        lambda t: sum(1 / k_value(i, t, P_REF) for i in range(3)) / 3 - 1, mpf(365), mpf(385)
    )
    print("equimolar feed at P_r: bubble", s(t_bub), "K; dew", s(t_dew), "K")
    print("sum zK(350 K) =", s(equimolar_sum_zk(mpf(350))))
    failures += abs(t_bub - mpf("347.44")) > mpf("0.005")
    for case_id, r, t_flash in VARIANTS:
        ref = recycle_reference(r, t_flash, case_id)
        print(
            f"{case_id}: flash {ref['flash_phase_state']}, V={ref['V_mol_per_s']}, "
            f"L={ref['L_mol_per_s']}, mixer {ref['mixer_outlet_state']} at T_mix={ref['T_mix_K']}, "
            f"heater outlet {ref['heater_outlet_state']}, Q_h={ref['Q_heater_W']}, "
            f"Q_f={ref['Q_flash_W']}"
        )
    nominal = recycle_reference(mpf("0.5"), mpf(360), "SYN-001-nominal")
    plan_nominal = {
        "q_V_over_L": "0.4150855900",
        "L_mol_per_s": "3.2783818616",
        "V_mol_per_s": "1.3608090692",
    }
    for key, val in plan_nominal.items():
        failures += abs(mpf(nominal[key]) - mpf(val)) > mpf("5e-11")
    plan_x = ("0.1816607866", "0.3333333333", "0.4850058800")
    failures += any(abs(mpf(nominal["x"][i]) - mpf(plan_x[i])) > mpf("5e-11") for i in range(3))
    print("plan §3 sanity values:", "all reproduced" if not failures else "MISMATCH")
    return 1 if failures else 0


def build_reference() -> dict[str, Any]:
    out: dict[str, Any] = {
        "generated_by": "Fable 5.1, mpmath 1.3.0 at 40 significant digits, from plan §3.1 "
        "definitions only",
        "precision_note": "Values are decimal strings with 20 significant digits; the last digit "
        "may differ by rounding. Tests should parse as float and compare at 1e-13 relative or "
        "1e-14 absolute unless a tighter check is registered.",
        "constants": {
            "R": s(R_GAS),
            "T_r_K": s(T_REF),
            "P_r_Pa": s(P_REF),
            "c_p_J_per_mol_K": s(CP),
            "T_b_K": [s(t) for t in T_BOIL],
            "L_J_per_mol": [s(t) for t in L_VAP],
            "v_m3_per_mol": [s(t) for t in V_LIQ],
            "M_kg_per_mol": ["0.100", "0.100", "0.100"],
        },
        "K_values": {},
        "pure_component_checks": {},
    }
    for t in (280, 300, 310, 320, 347, 350, 360, 400, 420, 440):
        for p in (50000, 100000, 200000):
            out["K_values"][f"T={t}K,P={p}Pa"] = [s(k) for k in k_vec(mpf(t), mpf(p))]
    for i in range(3):
        n = NAMES[i]
        checks = out["pure_component_checks"]
        checks[f"K_{n}(T_b,P_r)"] = s(k_value(i, T_BOIL[i], P_REF))
        checks[f"h_vap_{n}_at_P_r_J_per_mol"] = s(
            h_vapor(i, T_BOIL[i], P_REF) - h_liquid(i, T_BOIL[i], P_REF)
        )
        checks[f"gV_minus_gL_{n}(T_b,P_r)"] = s(
            g_vapor(i, T_BOIL[i], P_REF) - g_liquid(i, T_BOIL[i], P_REF)
        )
    t_bub = bisect(lambda t: equimolar_sum_zk(t) - 1, mpf(340), mpf(355))
    t_dew = bisect(
        lambda t: sum(1 / k_value(i, t, P_REF) for i in range(3)) / 3 - 1, mpf(365), mpf(385)
    )
    out["fresh_feed"] = {
        "F_mol_per_s": ["1", "1", "1"],
        "T_K": "300",
        "P_Pa": "100000",
        "phase": "LIQUID",
        "bubble_point_K_at_P_r": s(t_bub),
        "dew_point_K_at_P_r": s(t_dew),
        "sum_zK_at_350K": s(equimolar_sum_zk(mpf(350))),
        "sum_zK_at_310K": s(equimolar_sum_zk(mpf(310))),
        "sum_z_over_K_at_420K": s(sum(1 / k_value(i, mpf(420), P_REF) for i in range(3)) / 3),
    }
    variants = []
    for case_id, r, t_flash in VARIANTS:
        ref = recycle_reference(r, t_flash, case_id)
        variants.append({k: v for k, v in ref.items() if not k.startswith("_")})
    out["variants"] = variants
    margins: dict[str, Any] = {}
    for rr in ("0", "0.5", "0.9", "0.95", "0.99", "0.999", "0.9999"):
        ref = recycle_reference(mpf(rr), mpf(360), "probe")
        zmix, t_mix = ref["_zmix"], ref["_t_mix"]
        margin = 1 - sum(zmix[i] * k_value(i, t_mix, P_REF) for i in range(3))
        margins[f"r={rr}"] = {"margin": s(margin, 12), "T_mix_K": s(t_mix, 15)}
    out["domain_boundaries"] = {
        "mixer_outlet_subcooling_margin_vs_r_at_T_flash_360K": margins,
        "note": "1 - sum z_mix K(T_mix) stays positive for every r < 1 and tends to 0+ as r -> 1 "
        "(T_mix -> 360 K, z_mix -> x). No registered r-variant leaves the v0.0 subcooled-liquid "
        "mixer domain (plan §3.2); K02 needs a separate case (e.g. hotter fresh feed) to exercise "
        "the typed mixer-domain failure.",
    }
    out["linear_recycle"] = {
        "equation": "t = f + r t",
        "solution": "t = f/(1-r)",
        "f": ["1", "1", "1"],
        "values": {"r=0.5": "2", "r=0.95": "20"},
    }
    t360 = mpf(360)
    out["lnK_derivatives_at_360K_P_r"] = {
        "dlnK_dT_per_K": [s(L_VAP[i] / (R_GAS * t360**2)) for i in range(3)],
        "dlnK_dP_per_Pa": [s(-1 / P_REF + V_LIQ[i] / (R_GAS * t360)) for i in range(3)],
        "formula": "dlnK_i/dT = (L_i - v_i (P - P_r))/(R T^2); dlnK_i/dP = -1/P + v_i/(R T)",
    }
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="run identity and sanity checks")
    parser.add_argument("--emit", metavar="PATH", help="write reference_values.yaml to PATH")
    args = parser.parse_args(argv)
    code = 0
    if args.check:
        code = run_checks()
    if args.emit:
        header = (
            "# SYN-001 reference values. Authored by Fable 5.1 (P01) from plan §3.1 definitions "
            "using mpmath at 40 digits.\n# Generated by "
            "docs/derivations/scripts/syn001_reference.py --emit; independent of the oracle in "
            "benchmarks/syn001/oracle.py. Do not regenerate from the oracle.\n"
        )
        with open(args.emit, "w", encoding="utf-8") as fh:
            fh.write(header)
            yaml.safe_dump(build_reference(), fh, sort_keys=False, width=200, allow_unicode=True)
        print("wrote", args.emit)
    if not (args.check or args.emit):
        parser.print_help()
    return code


if __name__ == "__main__":
    sys.exit(main())
