"""S10 WO-S10-6: the empirical validation of `wilson-ig-v1` against its pre-registered bands.

Authority: `docs/derivations/S10-spec.md` §9.6 (bands fixed before transcription; R-708: a result
outside a band is "not validated within band" and the band never moves), §15 A2-2 (VAL-1 is at
Table V's printed 101.3 kPa). Validation, not verification: the data are held out from every fit.

* VAL-1: bubble T and y at the measured x and P (`benchmarks/s10/vle/kurihara1993_ternary.csv`),
  through the provider's `evaluate_phase` on `benchmarks/s10/records.yaml`:
  sum_i x_i K_i(T) = 1, K_i = exp(lnphi_i).
* VAL-2: waits for the 1995 isothermal data. Reported as PENDING, never as met.
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
import json
import math
import sys
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
S10 = ROOT / "benchmarks" / "s10"
RECORDS = S10 / "records.yaml"
TERNARY = S10 / "vle" / "kurihara1993_ternary.csv"
EOS = S10 / "validation" / "val3-eos.json"
REPORT_JSON = S10 / "validation" / "report.json"
REPORT_MD = ROOT / "docs" / "s10-validation-report.md"

IDS = ("CH3OH", "C2H5OH", "H2O")
FLUIDS = ("Methanol", "Ethanol", "Water")
P_TABLE_V = 101300.0  # Pa, as Table V prints it (§15 A2-2)
P_REGISTERED = 101325.0  # Pa, VAL-3's T_b (§9.6)
COOLPROP_VERSION = "8.0.0"
VAL3_POINTS = 11  # build decision B-70

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
        "VAL-2": {
            "id": "VAL-2",
            "band": BANDS["VAL-2"],
            "verdict": "PENDING: VAL-2 data not yet supplied",
        },
        "VAL-3": val3(provider),
    }


def markdown(rep: dict[str, Any]) -> str:
    v1, v3 = rep["VAL-1"], rep["VAL-3"]
    out: list[str] = [
        "# S10 empirical validation report (WO-S10-6)",
        "",
        "Generated by `scripts/s10_validation.py --write`; do not edit. Validation against",
        "held-out data (spec §9.6), reported separately from verification. A result outside a band",
        'is "not validated within band"; the band is not moved (R-708). The `uncertainty` string',
        "of the records is not yet changed (it waits for the verdict on the bands and for VAL-2).",
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
        "## VAL-2",
        "",
        rep["VAL-2"]["verdict"] + ".",
        "",
        f"## VAL-3: Δh and c_p^0L against CoolProp {v3['coolprop_version']},"
        " T in [300 K, T_b(101325 Pa)]",
        "",
        "Maxima over the grid (B-70), signed means in brackets; relative to the EOS value.",
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
        print(f"VAL-1 {rep['VAL-1']['verdict']}; VAL-3 {rep['VAL-3']['verdict']}")
        return 0
    same = (
        REPORT_JSON.read_text(encoding="utf-8") == text_json
        and REPORT_MD.read_text(encoding="utf-8") == text_md
    )
    print("OK: the report matches" if same else "FAIL: the report differs from the committed files")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
