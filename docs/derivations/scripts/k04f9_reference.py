"""Closed-form reference generator for K04-F9: fresh-flash checks at a state converged to its row
tolerance (ADR 0013; ``docs/derivations/K04-F9-spec.md``; T04 §17 F9, F10, §15 Q8; T05b D9 (1)).

A sibling of the T04 and T05b twins, whose SYN-001 thermodynamics, A02 region, phase contract,
edge 3, saturation band and T05 row builders it imports (as they import theirs). It imports nothing
from ``process_runtime`` or ``benchmarks``: the numbers it emits are the expectations the tests
judge the implementation against, so they must not come from it. It modifies no other reference
file.

What it derives, at 40 digits:

* **D1, the verifier's Newton projection** on the A02 family scan of T04 §9.3 (all 180 runs,
  through T04's own contract and edge-3 twin): every converged final state's K04 §4.4/§4.7 S3
  values raw (T04 F9's counts, re-derived) and after one Newton step of the 47 x 47 bound target
  (T04 §4.8 item 3), which removes the first-order error and leaves the second-order one.
* **D3, the unresolved-split routing**: for every registered two-phase split and stream, its band
  width `w`, whether its temperature lies in the band, and the fresh flash's resolution floor
  `N ulp(T) / (w tau_flow)` against the routing threshold `1/10` (ADR 0007 D2.4's margin).
* **D2, the admissible phase reading**: the first-order amplification `A` of a saturated
  single-phase stream's fresh-flash enthalpy against its saturation excess, so that one ulp of
  excess is priced in `tau_E`.
* **The new registered states**: INJ-B2' (SC-1's root 2e-5 K off saturation), INJ-F10 (SYN-001
  once-through with the flash forced all-liquid), NP-GC (NP-G with its liquid product split in
  two), and the old INJ-B2 state re-registered as PRJ-B2.

Three classes of value are emitted and labelled: ``closed_form`` (expectations),
``generator_claims`` (every statement the specification makes about its own numbers, re-derived
by ``--check``; the script refuses to emit when one fails), and ``measured`` (the implementation's
numbers from the specification pass, 2026-09-25, recorded as data and never checked here).

Run from the repository root inside the project environment::

    python docs/derivations/scripts/k04f9_reference.py --check
    python docs/derivations/scripts/k04f9_reference.py --emit benchmarks/k04f9/reference_values.yaml

``--emit`` is byte-reproducible.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from mpmath import lu_solve, matrix, mp, mpf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import k04_reference as k04  # noqa: E402  (SYN-001's five registered variants, K04 §6)
import t04_reference as t04  # noqa: E402  (the A02 region, contract, edge 3; T04 §4.8's target)
import t05b_reference as t5b  # noqa: E402  (the saturation band, T05b's cases)

mp.dps = 40

t05 = t5b.t05
t03 = t04.t03
NC, P_R = t5b.NC, t5b.P_R

# ============================================================================================
# 1. Registered constants (nothing new is registered here)
# ============================================================================================

TAU_FLOW = t5b.TAU_FLOW  # 3.1e-8 mol/s (K04 §5.1)
TAU_EQ = t5b.TAU_EQ  # 9.3e-8 (mol/s)^2 (K04 §5.2)
TAU_E = t5b.TAU_E  # 1.01e-3 W
TAU_T = t5b.TAU_T  # 1e-6 K
EPS_ADM = t5b.EPS_ADM  # 1e-12 (K03 §8.2)
#: ADR 0007 D2.4: a quantity within this factor of its threshold is near threshold.
KAPPA = mpf(10)
#: IEEE 754 binary64: the spacing of doubles at 1, and the unit roundoff.
ULP_ONE = mpf(2) ** -52
#: D3's routing threshold on the fresh flash's resolution floor, in units of tau_flow.
ROUTING_THRESHOLD = 1 / KAPPA
#: The spec's projection assertion (F05): a fresh-flash value at the projection is at most this
#: fraction of its tolerance at every exposed family state.
PROJECTED_BOUND = mpf("1e-3")


def ulp(t: Any) -> Any:
    """The spacing of binary64 doubles at `t` (exact: a power of two)."""
    return mpf(math.ulp(float(t)))


def s(value: Any, digits: int = 20) -> Any:
    if value is None or isinstance(value, bool | str | int):
        return value
    if value == mp.inf:
        return "inf"
    return t05.s(value, digits)


def sv(values: Sequence[Any], digits: int = 20) -> list[Any]:
    return [s(v, digits) for v in values]


def dh(i: int, t: Any, p: Any) -> Any:
    """`h_i^V − h_i^L` at `(t, p)`."""
    e = tuple(mpf(1) if j == i else mpf(0) for j in range(NC))
    return t05.h_flow(e, t, p, "V") - t05.h_flow(e, t, p, "L")


# ============================================================================================
# 2. D3: the fresh flash's resolution at a split, and the routing
# ============================================================================================


def route(n: Sequence[Any], t: Any, p: Any, two_phase: bool) -> dict[str, Any]:
    """ADR 0013 D3 on one flowing split feed (or stream) `n` at `(t, p)`.

    Order: degenerate (ADR 0012 D7: `delta <= tau_T`); else unresolved iff the stored branch is
    two-phase, `T_b <= t <= T_d` and `N ulp(t) / (w tau_flow) >= 1/10`; else resolved."""
    total = sum(n, mpf(0))
    tb, td = t5b.band_ends(n, p)
    out: dict[str, Any] = {"N_mol_per_s": total, "T_K": t, "ulp_T_K": ulp(t)}
    if isinstance(tb, str) or isinstance(td, str):
        out.update(T_bubble_K=None, T_dew_K=None, width_K=None, inside=False)
        out.update(degeneracy_K=mp.inf, floor_over_tau_flow=None, route="resolved")
        return out
    width = td - tb
    delta = max(abs(t - tb), abs(t - td))
    inside = tb <= t <= td
    floor = total * ulp(t) / (width * TAU_FLOW) if width > 0 else mp.inf
    if delta <= TAU_T:
        kind = "degenerate"
    elif two_phase and inside and floor >= ROUTING_THRESHOLD:
        kind = "unresolved"
    else:
        kind = "resolved"
    out.update(
        T_bubble_K=tb,
        T_dew_K=td,
        width_K=width,
        inside=inside,
        degeneracy_K=delta,
        floor_over_tau_flow=floor if inside else None,
        route=kind,
    )
    return out


def doc_route(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "route": entry["route"],
        "T_K": s(entry["T_K"]),
        "N_mol_per_s": s(entry["N_mol_per_s"]),
        "T_bubble_K": s(entry["T_bubble_K"]),
        "T_dew_K": s(entry["T_dew_K"]),
        "width_K": s(entry["width_K"], 12),
        "inside_band": entry["inside"],
        "degeneracy_K": s(entry["degeneracy_K"], 12),
        "ulp_T_K": s(entry["ulp_T_K"], 12),
        "floor_over_tau_flow": s(entry["floor_over_tau_flow"], 6),
    }


def a02_mixed_feed() -> tuple[Any, ...]:
    """SYN-001 at r = 0.5, flash 360 K: the heater's feed S2 = fresh + recycle (K04 §6)."""
    v = k04.variant_state(mpf("0.5"), mpf(360))
    return tuple(v["S2"])


def routing_states() -> dict[str, dict[str, Any]]:
    """Every registered two-phase split feed (and, for the injections, the stream) by case."""
    out: dict[str, dict[str, Any]] = {}
    for name, r, tf in k04.VARIANTS:
        v = k04.variant_state(r, tf)
        s2 = tuple(v["S2"])
        out[f"{name}:U-HEAT.S3"] = route(s2, k04.T_HEATER, P_R, v["S3_regime"] == "TWO_PHASE")
        out[f"{name}:U-FLASH.S3"] = route(s2, tf, P_R, v["flash_regime"] == "TWO_PHASE")
    mixed = a02_mixed_feed()
    for target in t04.FAMILY_TARGETS:
        regime = t05.tp_split(mixed, mpf(target), P_R)["regime"]
        out[f"SYN-001-A02-{target}:U-HEAT.S3"] = route(
            mixed, mpf(target), P_R, regime == "TWO_PHASE"
        )
    npc = t5b.np_cases()
    for cid in ("NP-1", "NP-2", "NP-3", "NP-G"):
        ref = npc[cid]["ref"]
        out[f"{cid}:U-PHF.S1"] = route(npc[cid]["n"], ref["T"], P_R, True)
    out["NP-GC:U-PHF.S1"] = dict(out["NP-G:U-PHF.S1"])
    sc = t5b.sc_cases()
    for cid, key in (("SC-1", "valve"), ("SC-2", "phf"), ("SC-3", "phf")):
        root = sc[cid][key]
        out[f"{cid}:{key}"] = route(sc[cid]["feed"]["n"], root["T"], P_R, True)
    for cid, q in (("DZ-3", mpf(50000)), ("DZ-12", mpf(30000))):
        ref = t05.ph_solve((mpf(1), mpf(1), mpf(1)), P_R, q)
        out[f"{cid}:U-PHF.S1"] = route((mpf(1), mpf(1), mpf(1)), ref["T"], P_R, True)
    out["DZ-10:U-PHF.S1"] = dict(out["DZ-3:U-PHF.S1"])
    coupled = {"C1": t05.coupled_c1(), "C2": t05.coupled_c2(), "C3": t05.coupled_c3()}
    for cid, case in coupled.items():
        for name, st in case["streams"].items():
            if all(v == 0 for v in st["n"]):
                continue
            regime = t05.tp_split(st["n"], st["T"], st["P"])["regime"]
            out[f"SYN-001-UL-{cid}:{name}"] = route(
                st["n"], st["T"], st["P"], regime == "TWO_PHASE"
            )
    inj = t5b.pure_b(2)
    out["INJ-B2':S2"] = route(inj, mpf(360) + mpf("2e-5"), P_R, True)
    return out


# ============================================================================================
# 3. D2: the fresh flash of a saturated single-phase stream (the kink)
# ============================================================================================


def kink(n: Sequence[Any], t: Any, p: Any, phase: str) -> dict[str, Any]:
    """First-order `|Hdot_fresh − Hdot_phase|` per unit saturation excess at the boundary.

    Liquid past its bubble point by `b = Σ z K − 1`: `beta = b / Σ z (K − 1)^2`, vapour
    `N beta K z`, so `A = N Σ z K dh / Σ z (K − 1)^2`. Vapour past its dew point by
    `d = Σ z/K − 1`: liquid `N d z/K / Σ z (1 − 1/K)^2`, so
    `A = N Σ (z/K) dh / Σ z (1 − 1/K)^2`."""
    total = sum(n, mpf(0))
    z = [x / total for x in n]
    k = [t5b.TH.k(i, t, p) for i in range(NC)]
    d = [dh(i, t, p) for i in range(NC)]
    if phase == "L":
        num = sum((z[i] * k[i] * d[i] for i in range(NC)), mpf(0))
        den = sum((z[i] * (k[i] - 1) ** 2 for i in range(NC)), mpf(0))
        excess = sum((z[i] * k[i] for i in range(NC)), mpf(0)) - 1
    else:
        num = sum((z[i] / k[i] * d[i] for i in range(NC)), mpf(0))
        den = sum((z[i] * (1 - 1 / k[i]) ** 2 for i in range(NC)), mpf(0))
        excess = sum((z[i] / k[i] for i in range(NC)), mpf(0)) - 1
    a = total * num / den
    return {"A_W_per_unit_excess": a, "per_ulp_over_tau_E": a * ULP_ONE / TAU_E, "excess": excess}


def kink_states() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    npc = t5b.np_cases()
    for cid in ("NP-3", "NP-G"):
        ref = npc[cid]["ref"]
        out[f"{cid}:S2"] = kink(ref["v"], ref["T"], P_R, "V")
        out[f"{cid}:S3"] = kink(ref["l"], ref["T"], P_R, "L")
    ref = npc["NP-G"]["ref"]
    half = tuple(x / 2 for x in ref["l"])
    out["NP-GC:S4"] = kink(half, ref["T"], P_R, "L")
    out["NP-GC:S5"] = kink(half, ref["T"], P_R, "L")
    phf1 = t05.ph_solve((mpf(1), mpf(1), mpf(1)), P_R, mpf(50000))
    out["DZ-3:S2"] = kink(phf1["split"]["v"], phf1["T"], P_R, "V")
    out["DZ-3:S3"] = kink(phf1["split"]["l"], phf1["T"], P_R, "L")
    v = k04.variant_state(mpf("0.5"), mpf(360))
    out["SYN-001-nominal:S4"] = kink(v["S4"], mpf(360), P_R, "V")
    out["SYN-001-nominal:S5"] = kink(v["S5"], mpf(360), P_R, "L")
    out["SYN-001-nominal:S6"] = kink(v["S6"], mpf(360), P_R, "L")
    return out


# ============================================================================================
# 4. D1: the Newton projection on the A02 family scan (T04 §9.3), at 40 digits
# ============================================================================================


def scaled_residual(x47: Mapping[str, Any], fs: Any) -> list[Any]:
    out = t04.residual47(x47, fs)
    scale = t04.ROW_SCALE | t04.FEED_ROW_SCALE
    return [t04.value(out[r]) / scale[r] for r in t04.FEED_ROWS + fs.rows]


def project(x: Mapping[str, Any], fs: Any) -> tuple[dict[str, Any], Any, Any, Any]:
    """One Newton step of the 47 x 47 bound target (T04 §4.8 item 3), scaled as K04 §7.1 scales
    it: `x~ = x + S_x (−Ĵ⁻¹ F̂)`. Returns (x~, ‖F̂(x)‖∞, ‖F̂(x~)‖∞, ‖δ̂‖∞)."""
    x47 = t04.with_feed(dict(x))
    jac = t04.target47(x47, fs)
    f0 = scaled_residual(x47, fs)
    step = lu_solve(jac, -matrix(f0))
    xt = dict(x47)
    for j, name in enumerate(t04.TARGET_COLUMNS):
        xt[name] = x47[name] + t04.TARGET_COL_SCALE[name] * step[j]
    f1 = scaled_residual(xt, fs)
    return (
        xt,
        max(abs(v) for v in f0),
        max(abs(v) for v in f1),
        max(abs(step[j]) for j in range(len(t04.TARGET_COLUMNS))),
    )


def family() -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    q_cache: dict[int, Any] = {}
    for target in t04.FAMILY_TARGETS:
        q = q_cache.setdefault(target, t03.q_flash_at(mpf(target)))
        for guess in t04.FAMILY_GUESSES:
            x0, fs = t04.a02_open(guess, q)
            sol = t04.solve_with_edge3(x0, fs)
            entry: dict[str, Any] = {
                "T_target_K": target,
                "guess_K": mpf(guess),
                "outcome": sol.outcome,
                "recovered": sol.homotopy is not None,
            }
            if sol.outcome == "CONVERGED":
                raw = t04.band_ratio(t04.fresh_flash_checks(sol.x, fs))
                xt, f0, f1, step = project(sol.x, fs)
                fc = t04.fresh_flash_checks(xt, fs)
                entry.update(
                    raw=raw,
                    projected=t04.band_ratio(fc),
                    projected_flash_outlets=abs(fc["independent_split_flash_total"]) / TAU_FLOW,
                    F0=f0,
                    F1=f1,
                    step=step,
                    worst_row=fc["worst_row_over_tolerance"],
                )
            runs.append(entry)
    return {"runs": runs}


def t02_states() -> dict[str, Any]:
    """T02's A02 successes solved by Newton from 358 K (T04 §4.8 item 5, A30, A33)."""
    out: dict[str, Any] = {}
    for target in (355, 360, 365):
        x0, fs = t04.a02_open(358, t03.q_flash_at(mpf(target)))
        sol = t04.contract(x0, fs)
        raw_checks = t04.fresh_flash_checks(sol.x, fs)
        xt, f0, f1, step = project(sol.x, fs)
        fc = t04.fresh_flash_checks(xt, fs)
        out[f"SYN-001-A02-{target}"] = {
            "outcome": sol.outcome,
            "iterations": [a.run.iterations for a in sol.attempts],
            "worst_row": raw_checks["worst_row"],
            "worst_row_over_tolerance": raw_checks["worst_row_over_tolerance"],
            "raw": t04.band_ratio(raw_checks),
            "raw_split_total_over_tau_flow": abs(raw_checks["independent_split_S3_total"])
            / TAU_FLOW,
            "raw_heater_energy_over_tau_E": abs(raw_checks["energy_heater_W"]) / TAU_E,
            "projected": t04.band_ratio(fc),
            "F0": f0,
            "F1": f1,
            "step": step,
        }
    return out


# ============================================================================================
# 5. The new registered states
# ============================================================================================


def inj_b2_prime() -> dict[str, Any]:
    """SC-1's root with S2.T = 360 + 2e-5 K and the lever-rule split kept (spec §6)."""
    n = t5b.pure_b(2)
    h_in = t05.h_flow(n, 370, 180000, "L")
    beta = mpf(2016) / 60000
    v, liq = t5b.pure_b(2 * beta), t5b.pure_b(2 - 2 * beta)
    t = mpf(360) + mpf("2e-5")
    fresh = t05.tp_split(n, t, P_R)
    return {
        "T_K": t,
        "degeneracy_K": t5b.degeneracy_distance(n, t, P_R),
        "compiled_energy_row_W": h_in - (t05.h_flow(v, t, P_R, "V") + t05.h_flow(liq, t, P_R, "L")),
        "compiled_equilibrium_row_B": v[1] * sum(liq) - t5b.TH.k(1, t, P_R) * liq[1] * sum(v),
        "fresh_regime": fresh["regime"],
        "independent_split_total_mol_per_s": sum(v, mpf(0)) - sum(fresh["v"], mpf(0)),
        "independent_split_B_mol_per_s": v[1] - fresh["v"][1],
        "energy_balance_U-VLV_W": h_in - t05.h_split(fresh, t, P_R),
    }


def prj_b2() -> dict[str, Any]:
    """The old INJ-B2 state (2e-6 K above T_sat): every compiled row within its tolerance."""
    n = t5b.pure_b(2)
    h_in = t05.h_flow(n, 370, 180000, "L")
    beta = mpf(2016) / 60000
    v, liq = t5b.pure_b(2 * beta), t5b.pure_b(2 - 2 * beta)
    t = mpf(360) + mpf("2e-6")
    return {
        "T_K": t,
        "compiled_energy_row_W": h_in - (t05.h_flow(v, t, P_R, "V") + t05.h_flow(liq, t, P_R, "L")),
        "compiled_equilibrium_row_B": v[1] * sum(liq) - t5b.TH.k(1, t, P_R) * liq[1] * sum(v),
        "projection_target_T_K": mpf(360),
    }


def inj_f10() -> dict[str, Any]:
    """SYN-001 once-through: the flash's split forced all-liquid (S4 = 0, S5 = S3.n), its duty
    closed so FLASH-duty holds; the purge copies S5 (r = 0). The flash-outlet clause's case."""
    v = k04.variant_state(mpf(0), mpf(360))
    s3 = tuple(v["S2"])  # r = 0: S2 = S3.n = fresh feed
    t_f = mpf(360)
    fresh = t05.tp_split(s3, t_f, P_R)
    latent = sum((fresh["v"][i] * dh(i, t_f, P_R) for i in range(NC)), mpf(0))
    h5_liquid = t05.h_flow(s3, t_f, P_R, "L")
    h5_fresh = t05.h_split(fresh, t_f, P_R)
    # The compiled flash rows at the forced split: equilibrium S4.n_i S5.N − K S5.n_i S4.N with
    # S4 = 0 vanishes; the duty is closed by construction.
    q_f_forced = h5_liquid - v["H3"]
    return {
        "S3_n_mol_per_s": s3,
        "fresh_regime_S5_at_360K": fresh["regime"],
        "S5_bubble_excess": fresh["szk"] - 1,
        "Q_flash_true_W": v["Q_f"],
        "Q_flash_forced_W": q_f_forced,
        "energy_balance_flash_W": v["H3"] + q_f_forced - h5_fresh,
        "energy_balance_envelope_W": v["Q_h"] + q_f_forced - (h5_fresh - v["H1"]),
        "latent_of_the_missing_vapour_W": latent,
        "fresh_flash_vapour_mol_per_s": sum(fresh["v"], mpf(0)),
    }


def np_gc() -> dict[str, Any]:
    """NP-G with its liquid product through a splitter (`split_fraction = 0.5`) into two sinks."""
    ref = t5b.np_cases()["NP-G"]["ref"]
    half = tuple(x / 2 for x in ref["l"])
    return {
        "S2_n_mol_per_s": ref["v"],
        "S3_n_mol_per_s": ref["l"],
        "S4_n_mol_per_s": half,
        "S5_n_mol_per_s": half,
        "T_K": ref["T"],
    }


# ============================================================================================
# 6. Claims and the document
# ============================================================================================


class Claims:
    def __init__(self) -> None:
        self.passed: list[str] = []

    def __call__(self, name: str, condition: bool, detail: str = "") -> None:
        if not condition:
            raise AssertionError(f"generator claim failed: {name} {detail}")
        self.passed.append(name)


def imports_are_independent() -> bool:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            if name.split(".")[0] in ("openflowsheet", "benchmarks"):
                return False
    return True


#: The implementation's numbers from the specification pass (2026-09-25, `wp/T05b` at `ddbe446`),
#: recorded as data, never an expectation (spec §7, §13). Measured with a prototype of the rule
#: wrapped around the verifier; the build lane re-measures them on the implementation (W0).
MEASURED: dict[str, Any] = {
    "note": (
        "implementation, double precision, the rule prototyped around the verifier at ddbe446; "
        "regression data for tolerance arguments, never an expectation"
    ),
    "a02_family": {
        "converged": 179,
        "current_rule": {"fail": 15, "near": 9, "clear": 155, "worst_ratio": "27.28"},
        "new_rule": {
            "verified": 179,
            "states_with_a_near_threshold_flag": 15,
            "flags_all_on": "residual (29 flags, the heater's equilibrium rows at >= 0.1 tau_eq)",
            "worst_fresh_flash_ratio_at_projection": "2.0916e-5 (352 K from 360 K, S3.total)",
            "projection_applied": 179,
            "max_scaled_residual_at_projection": "3.1148e-15",
            "max_row_over_tolerance_at_projection": "3.0143e-7",
            "max_scaled_step": "4.6092e-8",
        },
    },
    "t05b": {
        "DZ-3": {
            "current": "FAILED: independent_split.U-PHF.S1.total -9.0870e-8 (2.931 tau), .A, .B; "
            "energy_balance.U-PHF and envelope -1.3272e-3 W (1.314 tau_E)",
            "new": "VERIFIED; worst fresh-flash ratio at projection 2.220e-6; residual flags "
            "PHF-equilibrium A/B/C at 0.173/0.197/0.119 tau_eq; bound 3.679e-8",
        },
        "DZ-10": {"new": "as DZ-3 to the printed digit (the same PH flash, 34 x 34 form)"},
        "NP-G": {
            "current": "VERIFIED (energy -4.0409e-4 W, split 0.0 at x_final)",
            "projection_only": "FAILED: energy_balance.U-PHF and envelope -2.78e-3 W at the "
            "projection (products' kink), independent split -1.35e-8 (0.44 tau)",
            "new": "VERIFIED; independent_split.U-PHF.S1 not_applicable(fresh_flash_unresolved); "
            "floor ratio 0.8896; residual PHF-duty flag 0.400; bound 6.978e-8",
        },
        "NP-3": {"new": "VERIFIED; floor ratio 0.01712 (resolved); worst 2.391e-3 at projection"},
        "PRJ-B2": {
            "new": "VERIFIED; saturation 5.68e-14 K at the projection; residual "
            "VLV-energy flag -4.0e-4 W at x_final"
        },
        "INJ-B2p": {"new": "VERIFIED; energy balance 3.6e-12 W at the projection (was -1e-4 W)"},
        "INJ-B2'": {
            "new": "FAILED at x_final (residual VLV-energy -4.0000e-3 W); fresh flash "
            "VAPOR; independent split -1.9328; energy -57984.004 W"
        },
        "INJ-F10": {
            "new": "FAILED; energy_balance.flash and envelope -38338.069446744 W; "
            "rcond_1 1.8508e-3; projection applied, values unchanged to 1e-13 relative"
        },
        "NP-GC": {
            "new": "VERIFIED, Newton at iteration 0; independent split not_applicable; "
            "energy balances <= 3.7e-12 W at the projection"
        },
    },
    "suite_under_the_prototype": (
        "2855 passed, 11 failed: exactly T04 A32 (5e-4 half), A33; T05 W1.d x3 (the pairing "
        "harness compares x_final with the projection); T05b B16 x2, B26 x2, B18 INJ-B2 and "
        "INJ-B2p. Without the exact-zero rule two more fail (K04 A31, K05 fixtures) and W1.d's "
        "pinned ids: SYN-001's S3 bubble check becomes a closure check"
    ),
    "identity_under_the_prototype": {
        "k05_identity_whole": "622463f5fbc8716f1196bc971633877e2d218e1c9744e3d4ad7d49608be0415b",
        "minus_t05": "b364bb3dc881402fd6e7982532b19f06dba60e5c6b01e70d1aab861bae030b5a",
        "t05": "ddbd0f7135ee5310a1ce65865fab69b69cafe542851a038086941740360687a3",
        "structural": "4ce030cab1e4b4a2402897f480e5194961a1dbe9b8705316ddd4776cbd2d0082",
    },
    "guards_over_the_suite": {
        "certificates_seen": 180,
        "refused_residual_not_passed": 16,
        "refused_other": 0,
        "max_dropped_delta_at_exact_zero_flows_mol_per_s": "2.87e-22",
    },
}


def run_claims(claim: Claims, rt, kinks, fam, t02s, b2p, b2, f10, gc) -> None:
    claim(
        "the script imports nothing from process_runtime or benchmarks", imports_are_independent()
    )

    # ---- D3 routing -------------------------------------------------------------------------
    npg, np3 = rt["NP-G:U-PHF.S1"], rt["NP-3:U-PHF.S1"]
    claim(
        "D3: NP-G's split is unresolved, its floor ratio >= 0.8 (8x the 1/10 threshold) and "
        "its temperature inside a band of 4.12 microkelvin, not within tau_T of both ends",
        npg["route"] == "unresolved"
        and npg["floor_over_tau_flow"] >= mpf("0.8")
        and mpf("4.12e-6") < npg["width_K"] < mpf("4.13e-6")
        and npg["degeneracy_K"] > 3 * TAU_T,
        s(npg["floor_over_tau_flow"], 6),
    )
    claim(
        "D3: NP-3's split is resolved with its floor ratio <= 0.02 (5x under the threshold)",
        np3["route"] == "resolved" and np3["floor_over_tau_flow"] <= mpf("0.02"),
        s(np3["floor_over_tau_flow"], 6),
    )
    claim(
        "D3: NP-1, NP-2 and SC-1…SC-3 are degenerate (ADR 0012 D7 takes precedence)",
        all(
            rt[k]["route"] == "degenerate"
            for k in ("NP-1:U-PHF.S1", "NP-2:U-PHF.S1", "SC-1:valve", "SC-2:phf", "SC-3:phf")
        ),
    )
    resolved_keys = [
        k
        for k in rt
        if k.split(":")[0]
        not in ("NP-1", "NP-2", "NP-3", "NP-G", "NP-GC", "SC-1", "SC-2", "SC-3", "INJ-B2'")
    ]
    worst_other = max(
        (rt[k]["floor_over_tau_flow"] for k in resolved_keys if rt[k]["floor_over_tau_flow"]),
        default=mpf(0),
    )
    claim(
        "D3: every other registered split and stream (SYN-001's five variants, the ten A02 "
        "targets, DZ-3, DZ-10, DZ-12, C1–C3) is resolved, with its floor ratio <= 1e-5 where "
        "its temperature lies inside its band",
        all(rt[k]["route"] == "resolved" for k in resolved_keys) and worst_other <= mpf("1e-5"),
        s(worst_other, 6),
    )
    inj = rt["INJ-B2':S2"]
    claim(
        "D3: INJ-B2' (pure B 2e-5 K above T_sat) is neither degenerate nor unresolved — its "
        "temperature is outside its zero-width band, so the fresh flash judges it",
        inj["route"] == "resolved" and not inj["inside"] and inj["degeneracy_K"] > 10 * TAU_T,
    )

    # ---- D2 kink amplification --------------------------------------------------------------
    claim(
        "D2: at NP-GC one ulp of bubble excess in each copy moves the envelope (which reads both) "
        "by >= 0.2 tau_E, inside ADR 0007 D2.4's band: without D2 the copies' checks measure "
        "roundoff",
        kinks["NP-GC:S4"]["per_ulp_over_tau_E"] + kinks["NP-GC:S5"]["per_ulp_over_tau_E"]
        >= mpf("0.2"),
        s(kinks["NP-GC:S4"]["per_ulp_over_tau_E"], 6),
    )
    claim(
        "D2: NP-G's liquid product has the largest amplification registered (>= 0.2 tau_E per "
        "ulp of excess)",
        kinks["NP-G:S3"]["per_ulp_over_tau_E"] >= mpf("0.2"),
    )
    inert = [k for k in kinks if not k.startswith(("NP-G", "NP-GC", "NP-3"))]
    claim(
        "D2: at NP-3's products one ulp of excess moves the enthalpy by <= 2e-3 tau_E, and at "
        "DZ-3's and SYN-001's products and copies by <= 1e-7 tau_E: D2 is inert there",
        all(kinks[k]["per_ulp_over_tau_E"] <= mpf("2e-3") for k in ("NP-3:S2", "NP-3:S3"))
        and all(kinks[k]["per_ulp_over_tau_E"] <= mpf("1e-7") for k in inert),
        str({k: s(kinks[k]["per_ulp_over_tau_E"], 3) for k in kinks}),
    )
    claim(
        "D2: the twin reproduces the recorded measurement: DZ-3's liquid product's "
        "amplification is 6.247e4 W per unit excess (the implementation's 1.3272e-3 W over "
        "2.125e-8, spec §4.2), to 1e-3 relative",
        abs(kinks["DZ-3:S3"]["A_W_per_unit_excess"] / mpf("6.2470e4") - 1) < mpf("1e-3"),
        s(kinks["DZ-3:S3"]["A_W_per_unit_excess"], 6),
    )
    claim(
        "D2: at every registered root the products and copies are exactly saturated "
        "(|excess| <= 1e-25): D2's reading and the fresh flash agree there",
        all(abs(kinks[k]["excess"]) <= mpf("1e-25") for k in kinks),
    )

    # ---- D1 on the A02 family ---------------------------------------------------------------
    runs = fam["runs"]
    conv = [r for r in runs if r["outcome"] == "CONVERGED"]

    def band(v: Any) -> str:
        return "fail" if v > 1 else "near" if v >= mpf("0.1") else "clear"

    counts = {k: sum(1 for r in conv if band(r["raw"]) == k) for k in ("clear", "near", "fail")}
    claim(
        "D1: the twin's family scan converges 179 of 180 runs, and the raw S3 checks classify "
        "155 clear, 9 near, 15 failing — T04 §17 F9's registered counts, re-derived",
        len(runs) == 180 and len(conv) == 179 and counts == {"clear": 155, "near": 9, "fail": 15},
        str(counts),
    )
    exposed = [r for r in conv if r["raw"] >= mpf("0.1")]
    claim(
        "D1: at every one of the 24 exposed states the projected S3 values are <= 1e-3 of their "
        "tolerances (the spec's F05 bound) and the raw ones >= 0.1: F05 discriminates by >= 100",
        len(exposed) == 24
        and all(r["projected"] <= PROJECTED_BOUND for r in exposed)
        and min(r["raw"] for r in exposed) >= mpf("0.1"),
    )
    worst_proj = max(r["projected"] for r in conv)
    claim(
        "D1: over all 179 states the projected S3 values are <= 3e-5 of their tolerances "
        "(second order; F05's 1e-3 is >= 30x above it)",
        worst_proj <= mpf("3e-5"),
        s(worst_proj, 6),
    )
    claim(
        "D1: the projection is second order: ‖F̂(x~)‖∞ <= 1e-13 at every converged state and "
        "<= ‖F̂(x)‖∞ wherever ‖F̂(x)‖∞ >= 1e-12",
        all(r["F1"] <= mpf("1e-13") for r in conv)
        and all(r["F1"] <= r["F0"] for r in conv if r["F0"] >= mpf("1e-12")),
    )
    claim(
        "D1: every compiled row at the projection is within 1e-6 of its tolerance (guard 5 holds "
        "with a margin of >= 1e6)",
        all(r["worst_row"] <= mpf("1e-6") for r in conv),
    )
    claim(
        "D1 and F10: the flash outlets' split at the projection is <= 1e-3 tau_flow at every "
        "converged state",
        all(r["projected_flash_outlets"] <= mpf("1e-3") for r in conv),
    )
    fails = sorted((r["T_target_K"], r["guess_K"]) for r in conv if r["raw"] > 1)
    registered = sorted(
        [
            (352, mpf(360)),
            (352, mpf(390)),
            (352, mpf(420)),
            (352, mpf(375)),
            (352, mpf(376)),
            (352, mpf(377)),
            (352, mpf("377.4")),
            (355, mpf(320)),
            (360, mpf(320)),
            (360, mpf(350)),
            (370, mpf(340)),
            (370, mpf(400)),
            (375, mpf(300)),
            (375, mpf(360)),
            (375, mpf(410)),
        ]
    )
    claim(
        "D1: the 15 raw failures are exactly T04's registered list "
        "(ref.bound.finding_F9.family_scan_converged_states.S3_failures)",
        fails == registered,
    )

    a355 = t02s["SYN-001-A02-355"]
    claim(
        "D1: T02's A02-355 from 358 K (T04 A33) — one attempt, 3 iterations, worst row "
        "U-HEAT:HEAT-equilibrium:A at 0.0813 tau (< 1/10: no residual flag), raw split 1.09 "
        "tau_flow and heater energy 0.94 tau_E (F9's evidence), projected S3 values <= 1e-3",
        a355["outcome"] == "CONVERGED"
        and a355["iterations"] == [3]
        and a355["worst_row"] == "U-HEAT:HEAT-equilibrium:A"
        and mpf("0.081") < a355["worst_row_over_tolerance"] < mpf("0.082")
        and mpf("1.09") < a355["raw_split_total_over_tau_flow"] < mpf("1.10")
        and mpf("0.93") < a355["raw_heater_energy_over_tau_E"] < mpf("0.94")
        and a355["projected"] <= PROJECTED_BOUND,
        s(a355["projected"], 6),
    )
    claim(
        "D1: A02-360 and A02-365 from 358 K stay clear raw (< 0.1) and projected (<= 1e-3)",
        all(
            t02s[k]["raw"] < mpf("0.1") and t02s[k]["projected"] <= PROJECTED_BOUND
            for k in ("SYN-001-A02-360", "SYN-001-A02-365")
        ),
    )

    # ---- the new registered states -------------------------------------------------------------
    claim(
        "INJ-B2': the compiled energy row fails (|row| > tau_E), the equilibrium row passes, the "
        "fresh flash says VAPOR, and the split and energy fail by >= 1e3 tau",
        abs(b2p["compiled_energy_row_W"]) > TAU_E
        and abs(b2p["compiled_equilibrium_row_B"]) < TAU_EQ
        and b2p["fresh_regime"] == "VAPOR"
        and abs(b2p["independent_split_total_mol_per_s"]) >= 1000 * TAU_FLOW
        and abs(b2p["energy_balance_U-VLV_W"]) >= 1000 * TAU_E,
    )
    claim(
        "PRJ-B2 (the old INJ-B2 state): every compiled row within its tolerance (energy 0.40 "
        "tau_E, equilibrium 0.078 tau_eq), so the certificate judges its projection",
        abs(b2["compiled_energy_row_W"]) < TAU_E and abs(b2["compiled_equilibrium_row_B"]) < TAU_EQ,
        f"{s(b2['compiled_energy_row_W'], 5)} {s(b2['compiled_equilibrium_row_B'], 5)}",
    )
    claim(
        "INJ-F10: the fresh flash of the forced liquid S5 at 360 K is two-phase; the flash and "
        "envelope balances both equal minus the latent heat of the missing vapour, >= 1e3 tau_E",
        f10["fresh_regime_S5_at_360K"] == "TWO_PHASE"
        and abs(f10["energy_balance_flash_W"] + f10["latent_of_the_missing_vapour_W"])
        < mpf("1e-25")
        and abs(f10["energy_balance_envelope_W"] + f10["latent_of_the_missing_vapour_W"])
        < mpf("1e-25")
        and f10["latent_of_the_missing_vapour_W"] >= 1000 * TAU_E
        and f10["S5_bubble_excess"] > 1000 * EPS_ADM,
    )
    claim(
        "INJ-F10: the twin reproduces the recorded measurement (-38 338.069 446 744 W, "
        "prototype pass) to 1e-9 relative",
        abs(f10["energy_balance_flash_W"] / mpf("-38338.069446744") - 1) < mpf("1e-9"),
        s(f10["energy_balance_flash_W"], 15),
    )
    claim(
        "NP-GC: the copies carry exactly half of NP-G's liquid product each",
        all(
            abs(gc["S4_n_mol_per_s"][i] + gc["S5_n_mol_per_s"][i] - gc["S3_n_mol_per_s"][i])
            < mpf("1e-35")
            for i in range(NC)
        ),
    )


def build() -> dict[str, Any]:
    claim = Claims()
    rt = routing_states()
    kinks = kink_states()
    fam = family()
    t02s = t02_states()
    b2p, b2, f10, gc = inj_b2_prime(), prj_b2(), inj_f10(), np_gc()
    run_claims(claim, rt, kinks, fam, t02s, b2p, b2, f10, gc)
    conv = [r for r in fam["runs"] if r["outcome"] == "CONVERGED"]
    exposed = [r for r in conv if r["raw"] >= mpf("0.1")]
    return {
        "document": "K04-F9 reference values (ADR 0013; docs/derivations/K04-F9-spec.md)",
        "generator": "docs/derivations/scripts/k04f9_reference.py",
        "precision": "mpmath 40 significant digits, written to 20 (ratios to 6)",
        "constants": {
            "tau_flow_mol_per_s": s(TAU_FLOW),
            "tau_eq_mol2_per_s2": s(TAU_EQ),
            "tau_E_W": s(TAU_E),
            "tau_T_K": s(TAU_T),
            "eps_adm": s(EPS_ADM),
            "near_threshold_margin": 10,
            "routing_threshold_floor_over_tau_flow": s(ROUTING_THRESHOLD),
            "ulp_one": s(ULP_ONE),
            "projected_bound_over_tolerance": s(PROJECTED_BOUND),
        },
        "closed_form": {
            "routing": {k: doc_route(v) for k, v in rt.items()},
            "kink": {
                k: {
                    "A_W_per_unit_excess": s(v["A_W_per_unit_excess"], 12),
                    "per_ulp_of_excess_over_tau_E": s(v["per_ulp_over_tau_E"], 6),
                    "excess_at_root": s(v["excess"], 6),
                }
                for k, v in kinks.items()
            },
            "a02_family_projection": {
                "runs": len(fam["runs"]),
                "converged": len(conv),
                "raw_counts": {
                    "fail": sum(1 for r in conv if r["raw"] > 1),
                    "near": sum(1 for r in conv if mpf("0.1") <= r["raw"] <= 1),
                    "clear": sum(1 for r in conv if r["raw"] < mpf("0.1")),
                },
                "exposed_states": [
                    {
                        "T_target_K": r["T_target_K"],
                        "guess_K": s(r["guess_K"], 6),
                        "recovered_by_edge3": r["recovered"],
                        "raw_largest_over_threshold": s(r["raw"], 6),
                        "projected_largest_over_threshold": s(r["projected"], 6),
                        "scaled_residual_before": s(r["F0"], 4),
                        "scaled_residual_after": s(r["F1"], 4),
                        "scaled_step": s(r["step"], 4),
                    }
                    for r in sorted(exposed, key=lambda r: (r["T_target_K"], r["guess_K"]))
                ],
                "projected_max_over_threshold": s(max(r["projected"] for r in conv), 6),
                "projected_flash_outlets_max_over_tau_flow": s(
                    max(r["projected_flash_outlets"] for r in conv), 6
                ),
            },
            "t02_states_from_358K": {
                k: {
                    "outcome": v["outcome"],
                    "iterations": v["iterations"],
                    "worst_row": v["worst_row"],
                    "worst_row_over_tolerance": s(v["worst_row_over_tolerance"], 6),
                    "raw_largest_over_threshold": s(v["raw"], 6),
                    "projected_largest_over_threshold": s(v["projected"], 6),
                    "scaled_residual_before": s(v["F0"], 4),
                    "scaled_residual_after": s(v["F1"], 4),
                }
                for k, v in t02s.items()
            },
            "injections": {
                "INJ-B2-prime": {
                    "state": "SC-1's root with S2.T = 360.00002 K (the lever-rule split kept)",
                    **{k: s(v) for k, v in b2p.items()},
                },
                "INJ-F10": {
                    "state": (
                        "SYN-001 once-through x(t*) with the flash split forced all-liquid "
                        "(S4 = 0, S4.N = 0, S5 = S3.n, S5.N = 3, S7 = S5, S6 = 0) and U-FLASH.Q "
                        "closed so FLASH-duty holds"
                    ),
                    "S3_n_mol_per_s": sv(f10["S3_n_mol_per_s"]),
                    **{k: s(v) for k, v in f10.items() if k != "S3_n_mol_per_s"},
                },
            },
            "cases": {
                "PRJ-B2": {
                    "state": "SC-1's root with S2.T = 360.000002 K (was INJ-B2)",
                    **{k: s(v) for k, v in b2.items()},
                },
                "NP-GC": {
                    "flowsheet": (
                        "NP-G (feed [0, 2, 1.5e-7] mol/s 300 K P_r liquid -> U-PHF, Q = 30 000 W, "
                        "S2 vapour -> sink) with S3 liquid -> U-SPLIT (split_fraction 0.5) -> S4 "
                        "(recycle port) -> sink, S5 (purge) -> sink"
                    ),
                    "T_K": s(gc["T_K"]),
                    **{k: sv(v) for k, v in gc.items() if k != "T_K"},
                },
            },
        },
        "measured": MEASURED,
        "generator_claims": {"count": len(claim.passed), "names": claim.passed},
    }


def emit(path: Path, document: Mapping[str, Any]) -> str:
    text = yaml.safe_dump(dict(document), sort_keys=False, width=200, allow_unicode=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="re-derive every claim")
    parser.add_argument("--emit", metavar="PATH", help="write the reference YAML")
    args = parser.parse_args(argv)
    if not args.check and not args.emit:
        parser.error("choose --check and/or --emit PATH")
    document = build()
    if args.check:
        for name in document["generator_claims"]["names"]:
            print(f"ok  {name}")
        print(f"{document['generator_claims']['count']} claims passed")
    if args.emit:
        digest = emit(Path(args.emit), document)
        print(f"wrote {args.emit}\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
