"""S10 WO-S10-6: the empirical validation of `wilson-ig-v1` against its pre-registered bands.

Authority: `docs/derivations/S10-spec.md` §9.6 (bands fixed before transcription; R-708: a result
outside a band is "not validated within band" and the band never moves), §15 A2-2 (VAL-1 is at
Table V's printed 101.3 kPa). Validation, not verification: the data are held out from every fit.

* VAL-1: bubble T and y at the measured x and P (`benchmarks/s10/vle/kurihara1993_ternary.csv`),
  through the provider's `evaluate_phase` on `benchmarks/s10/records.yaml`:
  sum_i x_i K_i(T) = 1, K_i = exp(lnphi_i).
* VAL-2 (§19, Amendment 6): bubble P and y_1 of the two water binaries at the measured T and x
  (`benchmarks/s10/vle/kurihara1995_binaries.csv`, pinned by SHA-256 and checked by claims C1-C5
  before any provider call), by the closed form P = P_eval sum_i n_i K_i(T, P_eval) through
  `evaluate_phase` at the one in-domain P_eval = 101325 Pa (A6-3). Judged per binary on the AADs
  of dP/P = (P_calc - P_exp) / P_exp and of y_1, both binaries within band (A6-4); all 159 points
  enter (A6-5). A refusal or a non-finite value is a defect: nothing is written and the run exits 1.
* VAL-3: the provider's dh_i = h_i^ig - h_i^0L and c_p,i^0L against CoolProp 8.0.0's dH_vap and
  saturated-liquid c_p on `benchmarks/s10/validation/val3-eos.json` (tool output, written by
  `--emit-eos` in an environment with CoolProp 8.0.0; `--write` and `--check` never need CoolProp).

    python scripts/s10_validation.py --emit-eos | --write | --check

Outputs: `benchmarks/s10/validation/report.json` and `docs/s10-validation-report.md`. `--check`
recomputes both and fails unless they equal the committed files. Nothing here chooses a band or a
parameter.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
S10 = ROOT / "benchmarks" / "s10"
RECORDS = S10 / "records.yaml"
TERNARY = S10 / "vle" / "kurihara1993_ternary.csv"
VAL2_CSV = S10 / "vle" / "kurihara1995_binaries.csv"
EOS = S10 / "validation" / "val3-eos.json"
REPORT_JSON = S10 / "validation" / "report.json"
REPORT_MD = ROOT / "docs" / "s10-validation-report.md"

IDS = ("CH3OH", "C2H5OH", "H2O")
FLUIDS = ("Methanol", "Ethanol", "Water")
P_TABLE_V = 101300.0  # Pa, as Table V prints it (§15 A2-2)
P_REGISTERED = 101325.0  # Pa, VAL-3's T_b (§9.6)
COOLPROP_VERSION = "8.0.0"
VAL3_POINTS = 11  # build decision B-70

#: §19 A6-1: the double-entered transcription's SHA-256 (A6-7 claim C1).
VAL2_SHA256 = "e129027986fa9c15ebf8e00d5fa040497708cb0c7a9d483263eefe2ba98090bb"
VAL2_HEADER = "system,table,row,T_K,P_kPa,x1,y1"
P_EVAL_VAL2 = 101325.0  # Pa, the one in-domain pressure of VAL-2's closed form (§19 A6-3)
#: §19 A6-1: (system, table, T_K, rows) of the six blocks, in file order.
VAL2_BLOCKS = (
    ("methanol+water", "2", "323.15", 14),
    ("methanol+water", "2", "328.15", 20),
    ("methanol+water", "2", "333.15", 18),
    ("ethanol+water", "3", "323.15", 37),
    ("ethanol+water", "3", "328.15", 34),
    ("ethanol+water", "3", "333.15", 36),
)
#: §19 A6-3 step 2: the alcohol's slot in the records' order (CH3OH, C2H5OH, H2O); water is slot 2.
VAL2_SLOT = {"methanol+water": 0, "ethanol+water": 1}

#: §9.6, verbatim. Never edited (R-708).
BANDS = {
    "VAL-1": {"aad_T_K": 1.0, "aad_y": 0.015, "max_abs_dy": 0.05},
    "VAL-2": {"aad_dP_over_P": 0.03, "aad_y": 0.015},
    "VAL-3": {"dh_relative": 0.05, "cp_relative": 0.25},
}


def sig(v: float, digits: int = 10) -> float:
    return float(f"{v:.{digits}g}")


def emit_eos() -> dict[str, Any]:
    import CoolProp  # type: ignore[import-not-found]
    import CoolProp.CoolProp as CP  # type: ignore[import-not-found]  # noqa: N817

    if CoolProp.__version__ != COOLPROP_VERSION:
        raise SystemExit(f"UNAVAILABLE: CoolProp {COOLPROP_VERSION} not importable")
    comps = []
    for cid, fluid in zip(IDS, FLUIDS, strict=True):
        tb = CP.PropsSI("T", "P", P_REGISTERED, "Q", 0, fluid)
        points = []
        for k in range(VAL3_POINTS):
            t = 300.0 + (tb - 300.0) * k / (VAL3_POINTS - 1)
            hv = CP.PropsSI("HMOLAR", "T", t, "Q", 1, fluid)
            hl = CP.PropsSI("HMOLAR", "T", t, "Q", 0, fluid)
            cp = CP.PropsSI("CPMOLAR", "T", t, "Q", 0, fluid)
            points.append([sig(t, 12), sig(hv - hl, 12), sig(cp, 12)])
        comps.append(
            {
                "id": cid,
                "coolprop_fluid": fluid,
                "eos_bibtex_key": CP.get_BibTeXKey(fluid, "EOS"),
                "T_b_K": sig(tb, 12),
                "points_T_K_dHvap_J_mol_cpL_J_mol_K": points,
            }
        )
    return {
        "coolprop_version": CoolProp.__version__,
        "coolprop_gitrevision": CoolProp.__gitrevision__,
        "note": "tool output; no equation-of-state coefficient is reproduced (S10-RC-03)",
        "components": comps,
    }


def _provider() -> Any:
    from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

    return WilsonIdealGasProvider(RECORDS)


def _eval(
    provider: Any,
    phase: Literal["LIQUID", "VAPOR"],
    props: tuple[str, ...],
    n: tuple[float, ...],
    t: float,
    p: float,
) -> dict[str, float]:
    from openflowsheet.thermo import PropertyRequest, StreamState

    res = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=n, temperature=t, pressure=p), phase=phase, properties=props
        ),
        None,
    )
    assert res.status == "ok", res
    return dict(res.values)


def _k(provider: Any, x: tuple[float, ...], t: float, p: float) -> list[float]:
    v = _eval(provider, "LIQUID", tuple(f"lnphi_{c}" for c in IDS), x, t, p)
    return [math.exp(v[f"lnphi_{c}"]) for c in IDS]


def bubble(provider: Any, x: tuple[float, ...], p: float) -> tuple[float, tuple[float, ...]]:
    """Bubble T (bisection on sum x_i K_i = 1, monotone in T) and y, at x and p."""
    lo, hi = 300.0, 400.0  # the provider's domain (§9.5)

    def f(t: float) -> float:
        return sum(xi * ki for xi, ki in zip(x, _k(provider, x, t, p), strict=True)) - 1.0

    if not (f(lo) < 0.0 < f(hi)):
        raise SystemExit(f"bubble point not bracketed in [300, 400] K at x={x}")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < 0.0 else (lo, mid)
        if hi - lo < 1e-12:
            break
    t = 0.5 * (lo + hi)
    y = tuple(xi * ki for xi, ki in zip(x, _k(provider, x, t, p), strict=True))
    s = sum(y)
    return t, tuple(v / s for v in y)


def val1(provider: Any) -> dict[str, Any]:
    with TERNARY.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    per: list[dict[str, Any]] = []
    dt: list[float] = []
    dy: list[list[float]] = [[], [], []]
    for r in rows:
        x1, x2 = float(r["x1"]), float(r["x2"])
        x = (x1, x2, 1.0 - x1 - x2)
        t, y = bubble(provider, x, P_TABLE_V)
        meas = (float(r["y1"]), float(r["y2"]), 1.0 - float(r["y1"]) - float(r["y2"]))
        dt.append(t - float(r["T_K"]))
        for i in range(3):
            dy[i].append(y[i] - meas[i])
        per.append(
            {
                "row": int(r["row"]),
                "x": [sig(v) for v in x],
                "T_exp_K": float(r["T_K"]),
                "T_calc_K": sig(t),
                "dT_K": sig(dt[-1]),
                "y_exp": [sig(v) for v in meas],
                "y_calc": [sig(v) for v in y],
                "dy": [sig(dy[i][-1]) for i in range(3)],
            }
        )
    n = len(rows)
    aad_y = [sum(abs(v) for v in d) / n for d in dy]
    max_y = [max(abs(v) for v in d) for d in dy]
    b = BANDS["VAL-1"]
    # Judged on the two measured fractions (y1, y2); water is the closure, reported beside them.
    meas_aad, meas_max = aad_y[:2], max_y[:2]
    checks = {
        "aad_T_K": sum(abs(v) for v in dt) / n <= b["aad_T_K"],
        "aad_y": all(v <= b["aad_y"] for v in meas_aad),
        "max_abs_dy": max(meas_max) <= b["max_abs_dy"],
    }
    closure = {
        "aad_y": all(v <= b["aad_y"] for v in aad_y),
        "max_abs_dy": max(max_y) <= b["max_abs_dy"],
    }
    return {
        "id": "VAL-1",
        "data": "Kurihara, Nakamichi and Kojima (1993), Table V, ternary, 101.3 kPa",
        "rows": n,
        "P_Pa": P_TABLE_V,
        "band": b,
        "aad_T_K": sig(sum(abs(v) for v in dt) / n),
        "max_abs_dT_K": sig(max(abs(v) for v in dt)),
        "mean_dT_K": sig(sum(dt) / n),
        "aad_y_by_component": {c: sig(v) for c, v in zip(IDS, aad_y, strict=True)},
        "max_abs_dy_by_component": {c: sig(v) for c, v in zip(IDS, max_y, strict=True)},
        "water_y_is_closure": True,
        "within_band": checks,
        "within_band_if_closure_water_judged": closure,
        "verdict": "within band" if all(checks.values()) else "not validated within band",
        "per_row": per,
    }


def read_val2(provider: Any) -> list[dict[str, str]]:
    """VAL-2's rows, after claims C1-C5 of §19 A6-7; a failed claim is a `SystemExit` naming it."""
    raw = VAL2_CSV.read_bytes()
    if hashlib.sha256(raw).hexdigest() != VAL2_SHA256:
        raise SystemExit(f"VAL-2 claim C1 failed: {VAL2_CSV} does not hash to {VAL2_SHA256}")
    text = raw.decode("utf-8")
    if text.split("\n", 1)[0] != VAL2_HEADER:
        raise SystemExit(f"VAL-2 claim C2 failed: the header is not {VAL2_HEADER!r}")
    rows = list(csv.DictReader(text.splitlines()))
    expected = [(s, tab, t, str(k)) for s, tab, t, n in VAL2_BLOCKS for k in range(1, n + 1)]
    got = [(r["system"], r["table"], r["T_K"], r["row"]) for r in rows]
    if got != expected or any(None in r or None in r.values() for r in rows):
        raise SystemExit("VAL-2 claim C3 failed: the rows do not fall into VAL2_BLOCKS")
    p_form, frac_form = re.compile(r"[0-9]+\.[0-9]{3}"), re.compile(r"0\.[0-9]{4}")
    t_lo, t_hi = provider.describe().domain["T"]
    for r in rows:
        where = f"{r['system']} T={r['T_K']} row={r['row']}"
        if not (
            p_form.fullmatch(r["P_kPa"])
            and frac_form.fullmatch(r["x1"])
            and frac_form.fullmatch(r["y1"])
            and 0.0 < float(r["x1"]) < 1.0
            and 0.0 < float(r["y1"]) < 1.0
        ):
            raise SystemExit(f"VAL-2 claim C4 failed at {where}")
        if not t_lo <= float(r["T_K"]) <= t_hi:
            raise SystemExit(f"VAL-2 claim C5 failed at {where}: T outside [{t_lo}, {t_hi}] K")
    return rows


class Val2RefusedError(Exception):
    """The provider refused VAL-2's state: a defect, never a validation outcome (§19 A6-3)."""


def bubble_p(
    provider: Any, n: tuple[float, float, float], t: float, p_eval: float = P_EVAL_VAL2
) -> tuple[float, tuple[float, float, float]]:
    """Bubble P and y at n and t by §19 A6-3's closed form: one `evaluate_phase` call at p_eval,
    K_i = exp(lnphi_i), S = n_1 K_1 + n_2 K_2 + n_3 K_3, P = p_eval S, y_i = n_i K_i / S."""
    from openflowsheet.thermo import PropertyRequest, StreamState

    names = tuple(f"lnphi_{c}" for c in provider.describe().components)
    res = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=n, temperature=t, pressure=p_eval),
            phase="LIQUID",
            properties=names,
        ),
        None,
    )
    if res.status != "ok":
        raise Val2RefusedError(f"{res.status}: {res.message}")
    k1, k2, k3 = (math.exp(res.values[name]) for name in names)
    s = n[0] * k1 + n[1] * k2 + n[2] * k3
    return p_eval * s, (n[0] * k1 / s, n[1] * k2 / s, n[2] * k3 / s)


def _val2_stats(pts: list[dict[str, Any]]) -> dict[str, float]:
    """The unrounded AADs, maxima and signed means of §19 A6-4 over pts, in the report's order."""
    m = len(pts)
    return {
        "aad_dP_over_P": sum(abs(q["r"]) for q in pts) / m,
        "aad_y1": sum(abs(q["dy1"]) for q in pts) / m,
        "max_abs_dP_over_P": max(abs(q["r"]) for q in pts),
        "max_abs_dy1": max(abs(q["dy1"]) for q in pts),
        "mean_dP_over_P": sum(q["r"] for q in pts) / m,
        "mean_dy1": sum(q["dy1"] for q in pts) / m,
        "aad_y_water": sum(abs(q["dyw"]) for q in pts) / m,
    }


def val2(provider: Any) -> dict[str, Any]:
    rows = read_val2(provider)
    p_domain = provider.describe().domain["P"]
    bound = p_domain[0]
    band = BANDS["VAL-2"]
    pts: list[dict[str, Any]] = []
    per: list[dict[str, Any]] = []
    for r in rows:
        where = f"{r['system']} T={r['T_K']} row={r['row']}"
        t, x1 = float(r["T_K"]), float(r["x1"])
        p_exp, y1_exp = 1000.0 * float(r["P_kPa"]), float(r["y1"])
        slot = VAL2_SLOT[r["system"]]
        n = (x1, 0.0, 1.0 - x1) if slot == 0 else (0.0, x1, 1.0 - x1)
        try:
            p_calc, y = bubble_p(provider, n, t)
        except Val2RefusedError as exc:
            raise SystemExit(f"VAL-2 refused at {where}: {exc}") from None
        if not (math.isfinite(p_calc) and all(math.isfinite(v) for v in y)):
            raise SystemExit(f"VAL-2 non-finite at {where}")
        q = {
            "system": r["system"],
            "T_K": r["T_K"],
            "r": (p_calc - p_exp) / p_exp,
            "dy1": y[slot] - y1_exp,
            "dyw": y[2] - (1.0 - y1_exp),
            "exp_below": p_exp < bound,
            "calc_below": p_calc < bound,
        }
        pts.append(q)
        per.append(
            {
                "system": r["system"],
                "T_K": t,
                "row": int(r["row"]),
                "x1": x1,
                "P_exp_Pa": sig(p_exp),
                "P_calc_Pa": sig(p_calc),
                "dP_over_P": sig(q["r"]),
                "y1_exp": y1_exp,
                "y1_calc": sig(y[slot]),
                "dy1": sig(q["dy1"]),
                "y_water_calc": sig(y[2]),
                "P_exp_below_domain": q["exp_below"],
                "P_calc_below_domain": q["calc_below"],
            }
        )
    binaries = []
    for system in VAL2_SLOT:
        blocks = [blk for blk in VAL2_BLOCKS if blk[0] == system]
        mine = [q for q in pts if q["system"] == system]
        st = {key: sig(v) for key, v in _val2_stats(mine).items()}
        within = {
            "aad_dP_over_P": st["aad_dP_over_P"] <= band["aad_dP_over_P"],
            "aad_y": st["aad_y1"] <= band["aad_y"],
        }
        isotherms = []
        for _, _, t_k, n_rows in blocks:
            iso = _val2_stats([q for q in mine if q["T_K"] == t_k])
            isotherms.append(
                {
                    "T_K": float(t_k),
                    "rows": n_rows,
                    "aad_dP_over_P": sig(iso["aad_dP_over_P"]),
                    "aad_y1": sig(iso["aad_y1"]),
                    "mean_dP_over_P": sig(iso["mean_dP_over_P"]),
                    "mean_dy1": sig(iso["mean_dy1"]),
                }
            )
        binaries.append(
            {
                "system": system,
                "table": int(blocks[0][1]),
                "rows": len(mine),
                **st,
                "n_P_exp_below_domain": sum(q["exp_below"] for q in mine),
                "n_P_calc_below_domain": sum(q["calc_below"] for q in mine),
                "within_band": within,
                "verdict": "within band" if all(within.values()) else "not validated within band",
                "isotherms": isotherms,
            }
        )
    pooled = _val2_stats(pts)
    ok = all(b["verdict"] == "within band" for b in binaries)
    return {
        "id": "VAL-2",
        "data": "Kurihara, Minoura, Takeda and Kojima (1995), Tables 2 and 3, isothermal binaries",
        "transcription": "benchmarks/s10/vle/kurihara1995_binaries.csv",
        "transcription_sha256": VAL2_SHA256,
        "rows": len(rows),
        "P_eval_Pa": P_EVAL_VAL2,
        "records_P_domain_Pa": [p_domain[0], p_domain[1]],
        "band": band,
        "judged": "per binary on y_1; both binaries within band (S10 spec §19 A6-4)",
        "dP_over_P": "(P_calc - P_exp) / P_exp",
        "binaries": binaries,
        "pooled_not_judged": {
            "rows": len(pts),
            "aad_dP_over_P": sig(pooled["aad_dP_over_P"]),
            "aad_y1": sig(pooled["aad_y1"]),
        },
        "verdict": "within band" if ok else "not validated within band",
        "per_row": per,
    }


def val3(provider: Any) -> dict[str, Any]:
    eos = json.loads(EOS.read_text(encoding="utf-8"))
    b = BANDS["VAL-3"]
    comps, ok_all = [], True
    for k, comp in enumerate(eos["components"]):
        assert comp["id"] == IDS[k]
        n = tuple(1.0 if j == k else 0.0 for j in range(3))
        pts, dh_rel, cp_rel = [], [], []
        for t, dhv, cpl in comp["points_T_K_dHvap_J_mol_cpL_J_mol_K"]:
            hl = _eval(provider, "LIQUID", ("h",), n, t, P_REGISTERED)["h"]
            hv = _eval(provider, "VAPOR", ("h",), n, t, P_REGISTERED)["h"]
            # c_p^0L is d h^L / dT of the pure liquid, the provider's `h` T-derivative.
            from openflowsheet.thermo import PropertyRequest, StreamState

            res = provider.evaluate_phase(
                PropertyRequest(
                    state=StreamState(n=n, temperature=t, pressure=P_REGISTERED),
                    phase="LIQUID",
                    properties=("h",),
                    derivatives=("T",),
                ),
                None,
            )
            cp = res.derivatives["h"]["T"]
            dh_rel.append((hv - hl) / dhv - 1.0)
            cp_rel.append(cp / cpl - 1.0)
            pts.append(
                {
                    "T_K": t,
                    "dh_model_J_mol": sig(hv - hl),
                    "dHvap_eos_J_mol": dhv,
                    "dh_relative": sig(dh_rel[-1]),
                    "cp_model_J_mol_K": sig(cp),
                    "cpL_eos_J_mol_K": cpl,
                    "cp_relative": sig(cp_rel[-1]),
                }
            )
        within = {
            "dh_relative": max(abs(v) for v in dh_rel) <= b["dh_relative"],
            "cp_relative": max(abs(v) for v in cp_rel) <= b["cp_relative"],
        }
        ok_all = ok_all and all(within.values())
        comps.append(
            {
                "id": comp["id"],
                "T_range_K": [comp["points_T_K_dHvap_J_mol_cpL_J_mol_K"][0][0], comp["T_b_K"]],
                "max_abs_dh_relative": sig(max(abs(v) for v in dh_rel)),
                "mean_dh_relative": sig(sum(dh_rel) / len(dh_rel)),
                "max_abs_cp_relative": sig(max(abs(v) for v in cp_rel)),
                "mean_cp_relative": sig(sum(cp_rel) / len(cp_rel)),
                "within_band": within,
                "verdict": "within band" if all(within.values()) else "not validated within band",
                "points": pts,
            }
        )
    return {
        "id": "VAL-3",
        "coolprop_version": eos["coolprop_version"],
        "P_Pa": P_REGISTERED,
        "band": b,
        "components": comps,
        "verdict": "within band" if ok_all else "not validated within band",
    }


def build() -> dict[str, Any]:
    provider = _provider()
    return {
        "convention": "validation, not verification (spec §9.6); bands never move (R-708)",
        "records": "benchmarks/s10/records.yaml",
        "VAL-1": val1(provider),
        "VAL-2": val2(provider),
        "VAL-3": val3(provider),
    }


def _markdown_val2(v2: dict[str, Any]) -> list[str]:
    """VAL-2's section: §19 A6-7's template."""

    def pct(v: float) -> str:
        return f"{100 * v:.4g} %"

    band = v2["band"]
    temps = [iso["T_K"] for b in v2["binaries"] for iso in b["isotherms"]]
    out = [
        f"## VAL-2: isothermal binaries, bubble P and y, {v2['rows']} rows,"
        f" {min(temps)}-{max(temps)} K (Kurihara et al. 1995)",
        "",
        "Judged per binary on y_1; both binaries must be within band (spec §19 A6-4)."
        f" dP/P = {v2['dP_over_P']}.",
        f"P_calc from the closed form through the provider at {v2['P_eval_Pa']:.0f} Pa"
        " (spec §19 A6-3).",
        "",
        "| Binary | Rows | AAD(dP/P) | Band | AAD(y_1) | Band | Verdict |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for b in v2["binaries"]:
        out.append(
            f"| {b['system']} | {b['rows']} | {pct(b['aad_dP_over_P'])} |"
            f" <= {pct(band['aad_dP_over_P'])} | {b['aad_y1']:.4g} | <= {band['aad_y']} |"
            f" {b['verdict']} |"
        )
    out += [
        "",
        "Per isotherm, reported and not judged:",
        "",
        "| Binary | T (K) | Rows | AAD(dP/P) | mean dP/P | AAD(y_1) | mean dy_1 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for b in v2["binaries"]:
        for iso in b["isotherms"]:
            out.append(
                f"| {b['system']} | {iso['T_K']} | {iso['rows']} | {pct(iso['aad_dP_over_P'])} |"
                f" {pct(iso['mean_dP_over_P'])} | {iso['aad_y1']:.4g} | {iso['mean_dy1']:.4g} |"
            )
    pooled = v2["pooled_not_judged"]
    n_exp = sum(b["n_P_exp_below_domain"] for b in v2["binaries"])
    n_calc = sum(b["n_P_calc_below_domain"] for b in v2["binaries"])
    out += [
        "",
        f"Pooled over {pooled['rows']} rows, reported and not judged:"
        f" AAD(dP/P) {pct(pooled['aad_dP_over_P'])}, AAD(y_1) {pooled['aad_y1']:.4g}.",
        f"Measured pressures below the records' P domain ({v2['records_P_domain_Pa'][0]:.0f} Pa):"
        f" {n_exp} of {v2['rows']}; computed: {n_calc} of {v2['rows']}.",
        "",
        f"VAL-2 verdict: **{v2['verdict']}**.",
    ]
    return out


def markdown(rep: dict[str, Any]) -> str:
    v1, v2, v3 = rep["VAL-1"], rep["VAL-2"], rep["VAL-3"]
    out: list[str] = [
        "# S10 empirical validation report (WO-S10-6)",
        "",
        "Generated by `scripts/s10_validation.py --write`; do not edit. Validation against",
        "held-out data (spec §9.6), reported separately from verification. A result outside a band",
        'is "not validated within band"; the band is not moved (R-708). The records\'',
        "`uncertainty` string states these results (S10 spec §17 A4-3).",
        "",
        f"## VAL-1: ternary bubble T and y, {v1['rows']} rows, {v1['P_Pa']:.0f} Pa (Table V)",
        "",
        "| Quantity | Result | Band | Within |",
        "| --- | --- | --- | --- |",
        f"| AAD(T) | {v1['aad_T_K']:.4g} K | <= {v1['band']['aad_T_K']} K |"
        f" {v1['within_band']['aad_T_K']} |",
    ]
    for c in IDS:
        meas = c != "H2O"
        out.append(
            f"| AAD(y_{c}){'' if meas else ' (closure, not judged)'} |"
            f" {v1['aad_y_by_component'][c]:.4g} |"
            f" <= {v1['band']['aad_y']} | {v1['aad_y_by_component'][c] <= v1['band']['aad_y']} |"
        )
    for c in IDS:
        out.append(
            f"| max abs dy_{c}{'' if c != 'H2O' else ' (closure, not judged)'} |"
            f" {v1['max_abs_dy_by_component'][c]:.4g} | <= {v1['band']['max_abs_dy']} |"
            f" {v1['max_abs_dy_by_component'][c] <= v1['band']['max_abs_dy']} |"
        )
    out += [
        "",
        f"Max |dT| {v1['max_abs_dT_K']:.4g} K; mean dT (calc - exp) {v1['mean_dT_K']:.4g} K.",
        f"Verdict, judged on the measured y_1, y_2: **{v1['verdict']}**. If the closure fraction of"
        f" water were judged too: {v1['within_band_if_closure_water_judged']}.",
        "",
        *_markdown_val2(v2),
        "",
        f"## VAL-3: Δh and c_p^0L against CoolProp {v3['coolprop_version']},"
        " T in [300 K, T_b(101325 Pa)]",
        "",
        "Maxima over the grid (B-71), signed means in brackets; relative to the EOS value.",
        "",
        f"| Component | max abs dh (band {v3['band']['dh_relative']:.0%}) | max abs cp (band"
        f" {v3['band']['cp_relative']:.0%}) | Verdict |",
        "| --- | --- | --- | --- |",
    ]
    for comp in v3["components"]:
        out.append(
            f"| {comp['id']} | {comp['max_abs_dh_relative']:.4g}"
            f" ({comp['mean_dh_relative']:+.4g}) | {comp['max_abs_cp_relative']:.4g}"
            f" ({comp['mean_cp_relative']:+.4g}) | {comp['verdict']} |"
        )
    out += ["", f"VAL-3 verdict: **{v3['verdict']}**.", ""]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--emit-eos", action="store_true")
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.emit_eos:
        EOS.write_text(json.dumps(emit_eos(), indent=1) + "\n", encoding="utf-8")
        print(f"wrote {EOS}")
        return 0
    rep = build()
    text_json = json.dumps(rep, indent=1) + "\n"
    text_md = markdown(rep)
    if a.write:
        REPORT_JSON.write_text(text_json, encoding="utf-8")
        REPORT_MD.write_text(text_md, encoding="utf-8")
        print(
            f"VAL-1 {rep['VAL-1']['verdict']}; VAL-2 {rep['VAL-2']['verdict']};"
            f" VAL-3 {rep['VAL-3']['verdict']}"
        )
        return 0
    same = (
        REPORT_JSON.read_text(encoding="utf-8") == text_json
        and REPORT_MD.read_text(encoding="utf-8") == text_md
    )
    print("OK: the report matches" if same else "FAIL: the report differs from the committed files")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
