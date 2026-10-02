"""Closed-form reference generator for T06: the v0.1 corpus, the robustness ensemble's sampling law,
the reference comparisons and the gate arithmetic.

Everything here follows from definitions: SYN-001's thermodynamics (``docs/derivations/SYN-001.md``)
through the sibling twin ``t05_reference.py`` (whose causal evaluators it reuses, never the
implementation's), the flowsheets registered in ``docs/derivations/T06-corpus-spec.md`` §4, the
sampling law of §6, the comparison rules of §9 and the gate of §7. It imports nothing from
``process_runtime`` or ``benchmarks``: the numbers it emits are the expectations T06's tests judge
the implementation and the reference tools against, so they must not come from either.

Emitted, and labelled as such in the YAML:

* ``closed_form`` -- expectations: the roots of the new corpus flowsheets, the reference-comparison
  fixtures' values, the positive controls' effect sizes, the sampling law's known-answer draws and
  the gate's Clopper-Pearson table. mpmath at 40 significant digits, written to 20.
* ``generator_claims`` -- every statement the specification makes about its own numbers,
  re-derived by ``--check``. The script refuses to emit when one fails.

Amendment 1 (2026-09-26; spec "Amendment 1"): STA-03 and STA-04 become solved cases (Frank's Q3/Q4),
``unit_conversion_v1``'s known answers (Python binary64, the one place this script does not use
mpmath, because the conversion is defined as one binary64 operation), the reference tools'
registered settings (M6), and the corpus's metamorphic restatements.

Amendment 2 (2026-09-26; spec "Amendment 2"): the draw's bit patterns (``u_hex``,
``delta_hex``; ``δ = (2u − 1)/5`` in one division), ``unit_conversion_v2`` (ADR 0016: the exact
image of the decimal as written, rounded once — exact rationals via ``fractions.Fraction``, checked
nearest by an independent test), ADR 0017's F6 states evaluated at 40 digits, and IDAES's SmoothVLE
settings with their bound. ``unit_conversion_v1`` stays in the YAML as the record of v1.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/t06_reference.py --check
    python docs/derivations/scripts/t06_reference.py --emit benchmarks/t06/reference_values.yaml

``--emit`` is byte-reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import sys
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml
from mpmath import betainc, findroot, mp, mpf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t05_reference as t5  # noqa: E402  (SYN-001 thermodynamics and T05 causal evaluators, mpmath)

mp.dps = 40

NC = 3
COMPONENTS = ("A", "B", "C")
P_R = t5.P_R
TH = t5.TH
CP = TH.b.CP
V_LIQ = TH.b.V_LIQ
T_MIN, T_MAX = t5.T_MIN, t5.T_MAX
P_MIN, P_MAX = t5.P_MIN, t5.P_MAX
ZERO = mpf(0)

#: T05 §11.5 / T02 §6.4 per-kind allowances for a converged state against its reference root.
ALLOWANCE = {
    "molar_flow": mpf("3.1e-7"),
    "temperature": mpf("1e-5"),
    "pressure": mpf("0.1"),
    "heat_rate": mpf("1e-2"),
}
#: §9.4: the comparison tolerance is ALLOWANCE[kind] + REF_REL * |twin value|.
REF_REL = mpf("1e-6")
#: K04 §4.8: the derivative witness's step (fraction of the column scale) and tolerance (scaled).
WITNESS_STEP = mpf("1e-5")
WITNESS_TOL = mpf("1e-7")
#: K04 §5.3: the smallest scaled residual tolerance.
TAU_HAT_MIN = mpf("1e-8")
#: Registered scales (SYN-001.md §9): flow, temperature, pressure, heat rate.
SCALE = {
    "molar_flow": mpf(3),
    "temperature": mpf(100),
    "pressure": mpf(10) ** 5,
    "heat_rate": mpf(10) ** 5,
}
#: Classification margins every registered state keeps (§4.4 claims).
SUBCOOL_MARGIN = mpf("1e-2")  # K02 mixer outlets: sum z K <= 1 - margin
PHASE_MARGIN = mpf(
    "1e-3"
)  # a two-phase lifted split: beta in [m, 1 - m]; a declared liquid: szk <= 1 - m
TERMINAL_MARGIN_K = mpf(1)  # exchangers: both terminal differences >= 1 K
STENCIL_STEPS = 10  # every state is >= 10 witness stencil steps inside the property domain


# =============================================================================================
# 1. Small helpers over the T05 twin
# =============================================================================================


def st(n: Sequence[Any], t: Any, p: Any = P_R) -> dict[str, Any]:
    return {"n": tuple(mpf(v) for v in n), "T": mpf(t), "P": mpf(p)}


def total(n: Sequence[Any]) -> Any:
    return sum((mpf(v) for v in n), ZERO)


def szk(
    n: Sequence[Any], t: Any, p: Any, k_fn: Callable[[int, Any, Any], Any] | None = None
) -> Any:
    k_fn = k_fn or TH.k
    tot = total(n)
    return sum((n[i] / tot * k_fn(i, t, p) for i in range(NC) if n[i] != 0), ZERO)


def sz_over_k(n: Sequence[Any], t: Any, p: Any) -> Any:
    tot = total(n)
    return sum((n[i] / tot / TH.k(i, t, p) for i in range(NC) if n[i] != 0), ZERO)


def h_liq(n: Sequence[Any], t: Any, p: Any) -> Any:
    return t5.h_flow(n, t, p, "L")


def h_vap(n: Sequence[Any], t: Any, p: Any) -> Any:
    return t5.h_flow(n, t, p, "V")


def tp(n: Sequence[Any], t: Any, p: Any) -> dict[str, Any]:
    return t5.tp_split(tuple(n), t, p)


def mixer(*inlets: Mapping[str, Any]) -> dict[str, Any]:
    return t5.eval_mixer(tuple(inlets))["outlet"]


def heater_tp(inlet: Mapping[str, Any], t_out: Any, inlet_phase: str | None) -> dict[str, Any]:
    """K02 `syn001.tp_heater` with a declared or lifted inlet: TP split at (T_out, P_in)."""
    n, p = inlet["n"], inlet["P"]
    if inlet_phase is None:
        h_in = t5.h_tp(n, inlet["T"], p)
    else:
        h_in = t5.h_flow(n, inlet["T"], p, inlet_phase)
    split = tp(n, t_out, p)
    return {
        "duty": t5.h_split(split, t_out, p) - h_in,
        "split": split,
        "T": mpf(t_out),
        "P": p,
        "n": tuple(n),
    }


def tp_flash(
    inlet: Mapping[str, Any], t_out: Any, p_out: Any, inlet_phase: str | None
) -> dict[str, Any]:
    """K02 `syn001.tp_flash`: products at (T, P) from the TP split; duty by the energy balance."""
    n = inlet["n"]
    if inlet_phase is None:
        h_in = t5.h_tp(n, inlet["T"], inlet["P"])
    else:
        h_in = t5.h_flow(n, inlet["T"], inlet["P"], inlet_phase)
    split = tp(n, t_out, p_out)
    return {
        "duty": t5.h_split(split, t_out, p_out) - h_in,
        "split": split,
        "vapor": st(split["v"], t_out, p_out),
        "liquid": st(split["l"], t_out, p_out),
    }


def stream_doc(s: Mapping[str, Any], split: Mapping[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"n": tuple(s["n"]), "T": s["T"], "P": s["P"]}
    if split is not None:
        out["regime"] = split["regime"]
        out["beta"] = split["beta"]
        out["v"] = tuple(split["v"])
        out["l"] = tuple(split["l"])
    return out


def two_stage_root(f: Callable[..., list[Any]], start: Sequence[str]) -> list[Any]:
    """A root of `f` near `start`: findroot at 20 digits, refined at 40 (deterministic)."""
    saved = mp.dps
    try:
        mp.dps = 20
        x = findroot(f, [mpf(v) for v in start], tol=mpf("1e-16"))
        mp.dps = 40
        x = findroot(f, [mpf(x[i]) for i in range(len(start))], tol=mpf("1e-36"))
        return [x[i] for i in range(len(start))]
    finally:
        mp.dps = saved


# =============================================================================================
# 2. The new corpus flowsheets (spec §4.3). Each returns streams, duties, work, extent,
#    signatures and the diagnostics its claims read.
# =============================================================================================

F_EQ = (mpf(1), mpf(1), mpf(1))
NU = (mpf(-2), mpf(-1), mpf(3))


def case_thm01() -> dict[str, Any]:
    """THM-01: feed (1,1,1) 300 K 1.2e5 Pa liquid -> TP flash at 365 K, 1.2e5 Pa."""
    p = mpf(120000)
    s1 = st(F_EQ, 300, p)
    fl = tp_flash(s1, mpf(365), p, "L")
    return {
        "streams": {
            "S1": stream_doc(s1),
            "S2": stream_doc(fl["vapor"]),
            "S3": stream_doc(fl["liquid"]),
        },
        "duty": {"U-FLASH": fl["duty"]},
        "signatures": {"U-FLASH": fl["split"]["regime"]},
        "lifted": {"U-FLASH": fl["split"]},
        "feeds": [s1],
        "products": [(fl["vapor"], "V"), (fl["liquid"], "L")],
        "external_heat": fl["duty"],
    }


def case_thm02() -> dict[str, Any]:
    """THM-02: feed (1,1,1) 300 K 1.5e5 Pa liquid -> PH flash, Q = 40 000 W, dP = 0."""
    p = mpf(150000)
    s1 = st(F_EQ, 300, p)
    ph = t5.eval_ph_flash(s1, "L", mpf(40000), ZERO)
    split = {
        "regime": ph["signature"],
        "beta": ph["beta"],
        "v": ph["vapor"]["n"],
        "l": ph["liquid"]["n"],
    }
    return {
        "streams": {
            "S1": stream_doc(s1),
            "S2": stream_doc(ph["vapor"]),
            "S3": stream_doc(ph["liquid"]),
        },
        "duty": {"U-PHF": mpf(40000)},
        "signatures": {"U-PHF": ph["signature"]},
        "lifted": {"U-PHF": split},
        "feeds": [s1],
        "products": [(ph["vapor"], "V"), (ph["liquid"], "L")],
        "external_heat": mpf(40000),
    }


def case_thm10() -> dict[str, Any]:
    """THM-10: feed (1,1,1) vapour 400 K P_r -> PH flash, Q = -40 000 W (partial condenser)."""
    s1 = st(F_EQ, 400, P_R)
    ph = t5.eval_ph_flash(s1, "V", mpf(-40000), ZERO)
    split = {
        "regime": ph["signature"],
        "beta": ph["beta"],
        "v": ph["vapor"]["n"],
        "l": ph["liquid"]["n"],
    }
    return {
        "streams": {
            "S1": stream_doc(s1),
            "S2": stream_doc(ph["vapor"]),
            "S3": stream_doc(ph["liquid"]),
        },
        "duty": {"U-PHF": mpf(-40000)},
        "signatures": {"U-PHF": ph["signature"]},
        "lifted": {"U-PHF": split},
        "feeds": [(s1, "V")],
        "products": [(ph["vapor"], "V"), (ph["liquid"], "L")],
        "external_heat": mpf(-40000),
        "declared_vapor": [s1],
    }


def c3_family(name: str, feed: Sequence[Any], q: Any, t_ho: Any, r: Any) -> dict[str, Any]:
    """C3's topology (T05 §11.3): feed -> HX cold -> mixer (+ recycle) -> PH flash -> splitter;
    purge -> HX hot (hot outlet T pinned). Reduction: T_f solves one scalar equation (the vapour
    and the purge are a TP flash of the fresh feed at T_f; the exchanger duty is
    L(T_f) c_p (T_f - T_ho))."""
    f = tuple(mpf(v) for v in feed)

    def g(tf: Any) -> Any:
        sp = tp(f, tf, P_R)
        return t5.h_split(sp, tf, P_R) - h_liq(f, 300, P_R) - q - total(sp["l"]) * CP * (tf - t_ho)

    tf = t5.bisect(g, mpf(330), mpf(430), 200)
    single = tp(f, tf, P_R)
    l_single = total(single["l"])
    loop = tuple(v / (1 - r) for v in single["l"])
    s6 = tuple(r * v for v in loop)
    s7 = tuple((1 - r) * v for v in loop)
    q_hx = total(s7) * CP * (tf - t_ho)
    s1 = st(f, 300, P_R)
    t_co = t5.invert_single_phase(f, P_R, h_liq(f, 300, P_R) + q_hx, "L")
    s2 = st(f, t_co, P_R)
    s3 = mixer(s2, st(s6, tf))
    ph = t5.eval_ph_flash(s3, "L", q, ZERO)
    hx = t5.eval_exchanger(st(s7, tf), s1, "L", "L", "hot_outlet_temperature", t_ho)
    split = {
        "regime": ph["signature"],
        "beta": ph["beta"],
        "v": ph["vapor"]["n"],
        "l": ph["liquid"]["n"],
    }
    return {
        "streams": {
            "S1": stream_doc(s1),
            "S2": stream_doc(hx["cold_outlet"]),
            "S3": stream_doc(s3),
            "S4": stream_doc(ph["vapor"]),
            "S5": stream_doc(ph["liquid"]),
            "S6": stream_doc(st(s6, tf)),
            "S7": stream_doc(st(s7, tf)),
            "S8": stream_doc(hx["hot_outlet"]),
        },
        "duty": {"U-PHF": q, "U-HX": hx["duty"]},
        "signatures": {"U-PHF": ph["signature"]},
        "lifted": {"U-PHF": split},
        "feeds": [s1],
        "products": [(ph["vapor"], "V"), (hx["hot_outlet"], "L")],
        "external_heat": q,
        "mixers": [s3],
        "exchangers": [hx],
        "declared_liquid": [s2, st(s6, tf), st(s7, tf), hx["hot_outlet"]],
        "fixed_point": {
            "flash_T_minus_reduction_K": abs(ph["T"] - tf),
            "flash_liquid_minus_loop": max(abs(ph["liquid"]["n"][i] - loop[i]) for i in range(NC)),
        },
        "T_flash": tf,
        "fresh_feed_liquid": l_single,
    }


def case_sta02() -> dict[str, Any]:
    """STA-02: C3's topology, B absent from the feed (1, 0, 2); Q 50 kW, T_ho 320 K, r 0.6."""
    return c3_family("STA-02", (1, 0, 2), mpf(50000), mpf(320), mpf("0.6"))


def net02_parts(tf: Any, q: Any, th: Any, r: Any) -> dict[str, Any]:
    single = tp(F_EQ, tf, P_R)
    rec = tuple(r * v / (1 - r) for v in single["l"])
    s2 = mixer(st(F_EQ, 300), st(rec, tf))
    heat = heater_tp(s2, th, "L")
    h_in = t5.h_split(heat["split"], th, P_R)
    return {
        "single": single,
        "rec": rec,
        "s2": s2,
        "heat": heat,
        "h_in": h_in,
        "residual": t5.h_tp(s2["n"], tf, P_R) - h_in - q,
    }


NET02_R = mpf("0.95")


def case_net02(r: Any = NET02_R) -> dict[str, Any]:
    """NET-02: feed -> mixer (+ recycle) -> TP heater 358 K -> PH flash (20 000 W, lifted inlet) ->
    splitter r = 0.95. The vapour and the purge are a TP flash of the fresh feed at T_f (all
    recycled
    material is flash liquid at T_f); T_f solves one scalar energy equation that contains r."""
    q, th = mpf(20000), mpf(358)
    tf = t5.bisect(lambda t: net02_parts(t, q, th, r)["residual"], mpf(345), mpf(420), 200)
    p = net02_parts(tf, q, th, r)
    s3n = p["s2"]["n"]
    ph = t5.eval_ph_flash({"n": s3n, "T": th, "P": P_R}, None, q, ZERO)
    s6 = st(p["rec"], tf)
    s7 = st(tuple((1 - r) * v for v in ph["liquid"]["n"]), tf)
    split = {
        "regime": ph["signature"],
        "beta": ph["beta"],
        "v": ph["vapor"]["n"],
        "l": ph["liquid"]["n"],
    }
    return {
        "streams": {
            "S1": stream_doc(st(F_EQ, 300)),
            "S2": stream_doc(p["s2"]),
            "S3": stream_doc({"n": s3n, "T": th, "P": P_R}, p["heat"]["split"]),
            "S4": stream_doc(ph["vapor"]),
            "S5": stream_doc(ph["liquid"]),
            "S6": stream_doc(s6),
            "S7": stream_doc(s7),
        },
        "duty": {"U-HEAT": p["heat"]["duty"], "U-PHF": q},
        "signatures": {"U-HEAT": p["heat"]["split"]["regime"], "U-PHF": ph["signature"]},
        "lifted": {"U-HEAT": p["heat"]["split"], "U-PHF": split},
        "feeds": [st(F_EQ, 300)],
        "products": [(ph["vapor"], "V"), (s7, "L")],
        "external_heat": p["heat"]["duty"] + q,
        "mixers": [p["s2"]],
        "declared_liquid": [s6, s7],
        "fixed_point": {
            "flash_T_minus_root_K": abs(ph["T"] - tf),
            "recycle_closure": max(abs(r * ph["liquid"]["n"][i] - p["rec"][i]) for i in range(NC)),
        },
        "T_flash": tf,
    }


def net03_residual(x: Sequence[Any]) -> tuple[list[Any], dict[str, Any]]:
    """NET-03's tear residual over (S7.n, S10.n, T_f): inner recycle, condensate, flash energy."""
    q, th, r2, tc = mpf(20000), mpf(358), mpf("0.5"), mpf(340)
    ri, ro, tf = x[0:3], x[3:6], x[6]
    s2 = mixer(st(F_EQ, 300), st(ro, tc))
    s3 = mixer(s2, st(ri, tf))
    h_heat = t5.h_tp(s3["n"], th, P_R)
    sp = tp(s3["n"], tf, P_R)
    energy = (t5.h_split(sp, tf, P_R) - h_heat - q) / 10**4
    cond = tp(sp["v"], tc, P_R)
    res = (
        [r2 * sp["l"][i] - ri[i] for i in range(NC)]
        + [cond["l"][i] - ro[i] for i in range(NC)]
        + [energy]
    )
    return res, {
        "s2": s2,
        "s3": s3,
        "sp": sp,
        "cond": cond,
        "tf": tf,
        "q": q,
        "th": th,
        "r2": r2,
        "tc": tc,
    }


NET03_START = ("0.372", "0.812", "0.979", "1.73", "1.62", "0.655", "359.8")


def case_net03() -> dict[str, Any]:
    """NET-03 (nested): feed -> MIX1 (+ condensate S10) -> MIX2 (+ inner recycle S7) -> TP heater
    358 K
    -> PH flash 20 000 W -> liquid S6 -> splitter r = 0.5 (S7 back to MIX2, S8 purge); vapour S5 ->
    TP heater 340 K (cooler) -> TP flash 340 K -> S11 vapour product, S10 condensate to MIX1."""
    x = two_stage_root(lambda *v: net03_residual(list(v))[0], NET03_START)
    res, d = net03_residual(x)
    tf, tc, th, r2, q = d["tf"], d["tc"], d["th"], d["r2"], d["q"]
    s3, sp = d["s3"], d["sp"]
    heat = heater_tp(s3, th, "L")
    s5 = st(sp["v"], tf)
    cool = heater_tp(s5, tc, "V")
    fl2 = tp_flash({"n": sp["v"], "T": tc, "P": P_R}, tc, P_R, None)
    s7 = st(x[0:3], tf)
    s8 = st(tuple((1 - r2) * v for v in sp["l"]), tf)
    s10 = st(x[3:6], tc)
    split = {"regime": sp["regime"], "beta": sp["beta"], "v": sp["v"], "l": sp["l"]}
    return {
        "streams": {
            "S1": stream_doc(st(F_EQ, 300)),
            "S2": stream_doc(d["s2"]),
            "S3": stream_doc(s3),
            "S4": stream_doc({"n": s3["n"], "T": th, "P": P_R}, heat["split"]),
            "S5": stream_doc(s5),
            "S6": stream_doc(st(sp["l"], tf)),
            "S7": stream_doc(s7),
            "S8": stream_doc(s8),
            "S9": stream_doc({"n": sp["v"], "T": tc, "P": P_R}, cool["split"]),
            "S10": stream_doc(s10),
            "S11": stream_doc(fl2["vapor"]),
        },
        "duty": {"U-HEAT": heat["duty"], "U-PHF": q, "U-COOL": cool["duty"], "U-FL2": fl2["duty"]},
        "signatures": {
            "U-HEAT": heat["split"]["regime"],
            "U-PHF": sp["regime"],
            "U-COOL": cool["split"]["regime"],
            "U-FL2": fl2["split"]["regime"],
        },
        "lifted": {
            "U-HEAT": heat["split"],
            "U-PHF": split,
            "U-COOL": cool["split"],
            "U-FL2": fl2["split"],
        },
        "feeds": [st(F_EQ, 300)],
        "products": [(s8, "L"), (fl2["vapor"], "V")],
        "external_heat": heat["duty"] + q + cool["duty"] + fl2["duty"],
        "mixers": [d["s2"], s3],
        "declared_liquid": [s7, s8, s10],
        "declared_vapor": [s5],
        "fixed_point": {"tear_residual": max(abs(v) for v in res)},
        "T_flash": tf,
    }


def case_net06() -> dict[str, Any]:
    """NET-06: feed -> HX cold -> PH flash (40 000 W, inlet LIQUID) -> vapour product; liquid ->
    HX hot (hot outlet pinned 320 K). An energy loop with no material recycle; one scalar equation
    in T_f."""
    q, t_ho = mpf(40000), mpf(320)

    def g(tf: Any) -> Any:
        sp = tp(F_EQ, tf, P_R)
        return (
            t5.h_split(sp, tf, P_R) - h_liq(F_EQ, 300, P_R) - q - total(sp["l"]) * CP * (tf - t_ho)
        )

    tf = t5.bisect(g, mpf(330), mpf(430), 200)
    sp = tp(F_EQ, tf, P_R)
    q_hx = total(sp["l"]) * CP * (tf - t_ho)
    s1 = st(F_EQ, 300)
    t_co = t5.invert_single_phase(F_EQ, P_R, h_liq(F_EQ, 300, P_R) + q_hx, "L")
    s2 = st(F_EQ, t_co)
    ph = t5.eval_ph_flash(s2, "L", q, ZERO)
    hx = t5.eval_exchanger(ph["liquid"], s1, "L", "L", "hot_outlet_temperature", t_ho)
    split = {
        "regime": ph["signature"],
        "beta": ph["beta"],
        "v": ph["vapor"]["n"],
        "l": ph["liquid"]["n"],
    }
    return {
        "streams": {
            "S1": stream_doc(s1),
            "S2": stream_doc(s2),
            "S3": stream_doc(ph["vapor"]),
            "S4": stream_doc(ph["liquid"]),
            "S5": stream_doc(hx["hot_outlet"]),
        },
        "duty": {"U-PHF": q, "U-HX": hx["duty"]},
        "signatures": {"U-PHF": ph["signature"]},
        "lifted": {"U-PHF": split},
        "feeds": [s1],
        "products": [(ph["vapor"], "V"), (hx["hot_outlet"], "L")],
        "external_heat": q,
        "exchangers": [hx],
        "declared_liquid": [s2, ph["liquid"], hx["hot_outlet"]],
        "fixed_point": {
            "flash_T_minus_root_K": abs(ph["T"] - tf),
            "exchanger_duty_minus_reduction_W": abs(hx["duty"] - q_hx),
        },
        "T_flash": tf,
    }


def net09_residual(x: Sequence[Any]) -> tuple[list[Any], dict[str, Any]]:
    f, t_rx, t_fl, r, conv = (mpf(2), mpf(1), mpf(0)), mpf(380), mpf(370), mpf("0.5"), mpf("0.5")
    s2 = mixer(st(f, 300), st(x, t_fl))
    rx = t5.eval_reactor(s2, "L", NU, 0, conv, "outlet_temperature", t_rx)
    fl = tp_flash(rx["outlet"], t_fl, P_R, None)
    return [r * fl["split"]["l"][i] - x[i] for i in range(NC)], {
        "f": f,
        "s2": s2,
        "rx": rx,
        "fl": fl,
        "r": r,
        "t_fl": t_fl,
        "t_rx": t_rx,
    }


NET09_START = ("0.2756", "0.2417", "1.3603")


def case_net09() -> dict[str, Any]:
    """NET-09: feed (2,1,0) -> mixer (+ recycle) -> conversion reactor (2A + B -> 3C, X_A = 1/2,
    outlet 380 K) -> TP flash 370 K -> vapour product; liquid -> splitter r = 0.5."""
    x = two_stage_root(lambda *v: net09_residual(list(v))[0], NET09_START)
    res, d = net09_residual(x)
    fl, rx, r, t_fl = d["fl"], d["rx"], d["r"], d["t_fl"]
    s6 = st(x, t_fl)
    s7 = st(tuple((1 - r) * v for v in fl["split"]["l"]), t_fl)
    rx_split = {
        "regime": rx["signature"],
        "beta": rx["outlet"]["beta"],
        "v": rx["outlet"]["v"],
        "l": rx["outlet"]["l"],
    }
    return {
        "streams": {
            "S1": stream_doc(st(d["f"], 300)),
            "S2": stream_doc(d["s2"]),
            "S3": stream_doc(rx["outlet"], rx_split),
            "S4": stream_doc(fl["vapor"]),
            "S5": stream_doc(fl["liquid"]),
            "S6": stream_doc(s6),
            "S7": stream_doc(s7),
        },
        "duty": {"U-RX": rx["duty"], "U-FLASH": fl["duty"]},
        "extent": {"U-RX": rx["extent"]},
        "signatures": {"U-RX": rx["signature"], "U-FLASH": fl["split"]["regime"]},
        "lifted": {"U-RX": rx_split, "U-FLASH": fl["split"]},
        "feeds": [st(d["f"], 300)],
        "products": [(fl["vapor"], "V"), (s7, "L")],
        "reaction": [(NU, rx["extent"])],
        "external_heat": rx["duty"] + fl["duty"],
        "mixers": [d["s2"]],
        "declared_liquid": [s6, s7],
        "fixed_point": {"tear_residual": max(abs(v) for v in res)},
    }


def net10_residual(x: Sequence[Any]) -> tuple[list[Any], dict[str, Any]]:
    t1, t2, r = mpf(360), mpf(340), mpf("0.6")
    s2 = mixer(st(F_EQ, 300), st(x, t2))
    f1 = tp(s2["n"], t1, P_R)
    f2 = tp(f1["v"], t2, P_R)
    return [r * f2["l"][i] - x[i] for i in range(NC)], {
        "s2": s2,
        "f1": f1,
        "f2": f2,
        "t1": t1,
        "t2": t2,
        "r": r,
    }


NET10_START = ("0.4668", "0.4087", "0.1924")


def case_net10() -> dict[str, Any]:
    """NET-10: feed -> mixer (+ reflux S8) -> TP flash 360 K -> vapour S3 -> TP heater 340 K
    (cooler, VAPOR inlet) -> TP flash 340 K -> vapour product S6; condensate S7 -> splitter r = 0.6
    -> reflux S8."""
    x = two_stage_root(lambda *v: net10_residual(list(v))[0], NET10_START)
    res, d = net10_residual(x)
    t1, t2, r, s2 = d["t1"], d["t2"], d["r"], d["s2"]
    fl1 = tp_flash(s2, t1, P_R, "L")
    s3 = fl1["vapor"]
    cool = heater_tp(s3, t2, "V")
    fl2 = tp_flash({"n": s3["n"], "T": t2, "P": P_R}, t2, P_R, None)
    s8 = st(x, t2)
    s9 = st(tuple((1 - r) * v for v in fl2["split"]["l"]), t2)
    return {
        "streams": {
            "S1": stream_doc(st(F_EQ, 300)),
            "S2": stream_doc(s2),
            "S3": stream_doc(s3),
            "S4": stream_doc(fl1["liquid"]),
            "S5": stream_doc({"n": s3["n"], "T": t2, "P": P_R}, cool["split"]),
            "S6": stream_doc(fl2["vapor"]),
            "S7": stream_doc(fl2["liquid"]),
            "S8": stream_doc(s8),
            "S9": stream_doc(s9),
        },
        "duty": {"U-FL1": fl1["duty"], "U-COOL": cool["duty"], "U-FL2": fl2["duty"]},
        "signatures": {
            "U-FL1": fl1["split"]["regime"],
            "U-COOL": cool["split"]["regime"],
            "U-FL2": fl2["split"]["regime"],
        },
        "lifted": {"U-FL1": fl1["split"], "U-COOL": cool["split"], "U-FL2": fl2["split"]},
        "feeds": [st(F_EQ, 300)],
        "products": [(fl1["liquid"], "L"), (fl2["vapor"], "V"), (s9, "L")],
        "external_heat": fl1["duty"] + cool["duty"] + fl2["duty"],
        "mixers": [s2],
        "declared_liquid": [fl1["liquid"], fl2["liquid"], s8, s9],
        "declared_vapor": [s3],
        "fixed_point": {"tear_residual": max(abs(v) for v in res)},
    }


def net11_residual(x: Sequence[Any]) -> tuple[list[Any], dict[str, Any]]:
    q, th, r, ph_hi = mpf(10000), mpf(370), mpf("0.5"), mpf(180000)
    s8, tv, tf = x[0:3], x[3], x[4]
    s2 = mixer(st(F_EQ, 300), st(s8, tf))
    pump = t5.eval_pump(s2, ph_hi, mpf("0.75"))
    s3 = pump["outlet"]
    hs = tp(s3["n"], th, ph_hi)
    hh = t5.h_split(hs, th, ph_hi)
    vs = tp(s3["n"], tv, P_R)
    fs = tp(s3["n"], tf, P_R)
    res = [r * fs["l"][i] - s8[i] for i in range(NC)]
    res += [(t5.h_split(vs, tv, P_R) - hh) / 10**4, (t5.h_split(fs, tf, P_R) - hh - q) / 10**4]
    return res, {
        "s2": s2,
        "pump": pump,
        "hs": hs,
        "hh": hh,
        "vs": vs,
        "fs": fs,
        "q": q,
        "th": th,
        "r": r,
        "ph_hi": ph_hi,
    }


NET11_START = ("0.5809", "0.8024", "0.9309", "351.756", "353.476")


def case_net11() -> dict[str, Any]:
    """NET-11: feed -> mixer (+ recycle) -> pump (1.8e5 Pa, eta 0.75) -> TP heater 370 K at
    1.8e5 Pa -> valve (P_r) -> PH flash (10 000 W, lifted inlet) -> vapour product; liquid ->
    splitter r = 0.5."""
    x = two_stage_root(lambda *v: net11_residual(list(v))[0], NET11_START)
    res, d = net11_residual(x)
    tv, tf, r, ph_hi, th = x[3], x[4], d["r"], d["ph_hi"], d["th"]
    s3 = d["pump"]["outlet"]
    heat = heater_tp(s3, th, "L")
    s4 = {"n": s3["n"], "T": th, "P": ph_hi}
    valve = t5.eval_valve(s4, None, P_R)
    s5 = valve["outlet"]
    ph = t5.eval_ph_flash({"n": s5["n"], "T": s5["T"], "P": P_R}, None, d["q"], ZERO)
    s8 = st(x[0:3], tf)
    s9 = st(tuple((1 - r) * v for v in ph["liquid"]["n"]), tf)
    split = {
        "regime": ph["signature"],
        "beta": ph["beta"],
        "v": ph["vapor"]["n"],
        "l": ph["liquid"]["n"],
    }
    vsplit = {"regime": valve["signature"], "beta": s5["beta"], "v": s5["v"], "l": s5["l"]}
    return {
        "streams": {
            "S1": stream_doc(st(F_EQ, 300)),
            "S2": stream_doc(d["s2"]),
            "S3": stream_doc(s3),
            "S4": stream_doc(s4, heat["split"]),
            "S5": stream_doc(s5, vsplit),
            "S6": stream_doc(ph["vapor"]),
            "S7": stream_doc(ph["liquid"]),
            "S8": stream_doc(s8),
            "S9": stream_doc(s9),
        },
        "duty": {"U-HEAT": heat["duty"], "U-PHF": d["q"]},
        "work": {"U-PUMP": d["pump"]["work"]},
        "signatures": {
            "U-HEAT": heat["split"]["regime"],
            "U-VLV": valve["signature"],
            "U-PHF": ph["signature"],
        },
        "lifted": {"U-HEAT": heat["split"], "U-VLV": vsplit, "U-PHF": split},
        "feeds": [st(F_EQ, 300)],
        "products": [(ph["vapor"], "V"), (s9, "L")],
        "external_heat": heat["duty"] + d["q"] + d["pump"]["work"],
        "mixers": [d["s2"]],
        "declared_liquid": [d["s2"], s3, s8, s9],
        "fixed_point": {
            "tear_residual": max(abs(v) for v in res),
            "valve_T_minus_root_K": abs(s5["T"] - tv),
            "flash_T_minus_root_K": abs(ph["T"] - tf),
        },
        "high_pressure_liquid_szk": szk(s3["n"], th, ph_hi),
    }


NEW_CASES: dict[str, Callable[[], dict[str, Any]]] = {
    "SYN-001-T06-THM01": case_thm01,
    "SYN-001-T06-THM02": case_thm02,
    "SYN-001-T06-THM10": case_thm10,
    "SYN-001-T06-STA02": case_sta02,
    "SYN-001-T06-NET02": case_net02,
    "SYN-001-T06-NET03": case_net03,
    "SYN-001-T06-NET06": case_net06,
    "SYN-001-T06-NET09": case_net09,
    "SYN-001-T06-NET10": case_net10,
    "SYN-001-T06-NET11": case_net11,
}


# =============================================================================================
# 3. The eight reference-comparison fixtures (spec §9.2), the recycle included
# =============================================================================================


def ref_fixtures() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    # REF-01 mixer: two liquids at P_r; equal c_p, so T_out is the flow-weighted mean.
    a, b = st((1, "0.5", "0.2"), 300), st(("0.2", "0.5", 1), 340)
    m = mixer(a, b)
    out["REF-01"] = {
        "quantities": {
            "S3.n.A": m["n"][0],
            "S3.n.B": m["n"][1],
            "S3.n.C": m["n"][2],
            "S3.T": m["T"],
        },
        "mixer_szk": szk(m["n"], m["T"], P_R),
    }
    # REF-02 splitter: (1, 2, 3) at 330 K, fraction 0.3 to `recycle`.
    n = (mpf(1), mpf(2), mpf(3))
    fr = mpf("0.3")
    q2 = {f"S2.n.{c}": fr * n[i] for i, c in enumerate(COMPONENTS)}
    q2.update({f"S3.n.{c}": (1 - fr) * n[i] for i, c in enumerate(COMPONENTS)})
    q2.update({"S2.T": mpf(330), "S3.T": mpf(330)})
    out["REF-02"] = {"quantities": q2, "inlet_szk": szk(n, 330, P_R)}
    # REF-03 heater: (1,1,1) 300 K liquid -> 350 K at P_r (two-phase outlet).
    h = heater_tp(st(F_EQ, 300), mpf(350), "L")
    q3 = {"U-HEAT.Q": h["duty"]}
    q3.update({f"S2.vap.{c}": h["split"]["v"][i] for i, c in enumerate(COMPONENTS)})
    out["REF-03"] = {"quantities": q3, "beta": h["split"]["beta"], "regime": h["split"]["regime"]}
    # REF-04 flash: (1,1,1) 300 K liquid -> TP flash 360 K, P_r.
    fl = tp_flash(st(F_EQ, 300), mpf(360), P_R, "L")
    q4 = {"U-FLASH.Q": fl["duty"]}
    q4.update({f"S2.n.{c}": fl["split"]["v"][i] for i, c in enumerate(COMPONENTS)})
    q4.update({f"S3.n.{c}": fl["split"]["l"][i] for i, c in enumerate(COMPONENTS)})
    out["REF-04"] = {"quantities": q4, "beta": fl["split"]["beta"], "V": total(fl["split"]["v"])}
    # REF-05 valve: (1,1,1) liquid 360 K 1.8e5 Pa -> P_r (isenthalpic, flashing).
    vin = st(F_EQ, 360, 180000)
    v = t5.eval_valve(vin, "L", P_R)
    q5 = {"S2.T": v["outlet"]["T"]}
    q5.update({f"S2.vap.{c}": v["outlet"]["v"][i] for i, c in enumerate(COMPONENTS)})
    out["REF-05"] = {
        "quantities": q5,
        "inlet_szk_no_poynting": szk(F_EQ, 360, 180000, lambda i, t, p: TH.k(i, t, P_R) * P_R / p),
        "inlet_szk": szk(F_EQ, 360, 180000),
        "beta": v["outlet"]["beta"],
    }
    # REF-06 pump: (1,1,1) 300 K P_r -> 1.8e5 Pa, eta 0.75.
    pu = t5.eval_pump(st(F_EQ, 300), mpf(180000), mpf("0.75"))
    out["REF-06"] = {"quantities": {"U-PUMP.W": pu["work"], "S2.T": pu["outlet"]["T"]}}
    # REF-07 conversion reactor: (1.2, 0.9, 0.3) 300 K -> X_A = 1/2, nu = (-2,-1,3), outlet 315 K.
    rin = st(("1.2", "0.9", "0.3"), 300)
    rx = t5.eval_reactor(rin, "L", NU, 0, mpf("0.5"), "outlet_temperature", mpf(315))
    q7 = {f"S2.n.{c}": rx["outlet"]["n"][i] for i, c in enumerate(COMPONENTS)}
    q7["U-RX.Q"] = rx["duty"]
    out["REF-07"] = {
        "quantities": q7,
        "extent": rx["extent"],
        "regime": rx["signature"],
        "outlet_szk": szk(rx["outlet"]["n"], 315, P_R),
    }
    # REF-08 recycle: SYN-001 nominal (r = 0.5): the vapour and the purge are a TP flash of the
    # feed at 360 K; the loop liquid is L'/(1 - r); heater 350 K, flash 360 K (plan §3.2).
    r = mpf("0.5")
    single = tp(F_EQ, 360, P_R)
    loop = tuple(vv / (1 - r) for vv in single["l"])
    rec = tuple(r * vv for vv in loop)
    s2 = mixer(st(F_EQ, 300), st(rec, 360))
    heat = heater_tp(s2, mpf(350), "L")
    q_flash = t5.h_split(tp(s2["n"], 360, P_R), 360, P_R) - t5.h_split(heat["split"], 350, P_R)
    q8 = {f"S4.n.{c}": single["v"][i] for i, c in enumerate(COMPONENTS)}
    q8.update({f"S6.n.{c}": rec[i] for i, c in enumerate(COMPONENTS)})
    q8.update({f"S7.n.{c}": (1 - r) * loop[i] for i, c in enumerate(COMPONENTS)})
    q8.update({"U-HEAT.Q": heat["duty"], "U-FLASH.Q": q_flash, "S2.T": s2["T"]})
    out["REF-08"] = {"quantities": q8, "V": total(single["v"]), "L": total(loop)}
    return out


def kind_of(quantity: str) -> str:
    tail = quantity.split(".")[-1]
    if tail == "T":
        return "temperature"
    if tail in ("Q", "W"):
        return "heat_rate"
    if tail == "P":
        return "pressure"
    return "molar_flow"


def comparison_tolerance(quantity: str, value: Any) -> Any:
    return ALLOWANCE[kind_of(quantity)] + REF_REL * abs(value)


def positive_controls(refs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """PC-1: DWSIM with the unmapped vaporization enthalpy (dH_vap = L_i) differs from SYN-001 by
    -P_r v_i per mole vaporized (spec §9.3 derivation); on REF-04 the flash duty moves by -P_r v V.
    PC-2: a TP flash at 1.5e5 Pa and 370 K without the Poynting factor (IDAES's and DWSIM's K)."""
    v_total = refs["REF-04"]["V"]
    effect_duty = -P_R * V_LIQ[0] * v_total  # equal v_i for every component
    q = refs["REF-04"]["quantities"]["U-FLASH.Q"]
    pc1 = {
        "quantity": "U-FLASH.Q",
        "effect_W": effect_duty,
        "tolerance_W": comparison_tolerance("U-FLASH.Q", q),
    }
    p, t = mpf(150000), mpf(370)
    ours = tp(F_EQ, t, p)

    def k_no_poynting(i: int, tt: Any, pp: Any) -> Any:
        return TH.k(i, tt, P_R) * P_R / pp

    theirs = split_with_k(F_EQ, t, p, k_no_poynting)
    effects = {f"S2.n.{c}": theirs["v"][i] - ours["v"][i] for i, c in enumerate(COMPONENTS)}
    worst = max(
        effects,
        key=lambda k: abs(effects[k]) / comparison_tolerance(k, ours["v"][COMPONENTS.index(k[-1])]),
    )
    pc2 = {
        "T_K": t,
        "P_Pa": p,
        "ours_vapor": tuple(ours["v"]),
        "no_poynting_vapor": tuple(theirs["v"]),
        "effects": effects,
        "worst_quantity": worst,
        "worst_ratio": abs(effects[worst])
        / comparison_tolerance(worst, ours["v"][COMPONENTS.index(worst[-1])]),
        "regime": ours["regime"],
    }
    # The same latent offset on REF-05's valve outlet temperature (reported: caught, by < 10x).
    vin = st(F_EQ, 360, 180000)
    h_in = h_liq(F_EQ, 360, 180000)

    def g(tt: Any) -> Any:  # DWSIM-unmapped: H_out(T) = H_in + P_r v V(T)
        s = tp(F_EQ, tt, P_R)
        return t5.h_split(s, tt, P_R) - h_in - P_R * V_LIQ[0] * total(s["v"])

    t_unmapped = t5.bisect(g, mpf(330), mpf(360), 200)
    t_ours = refs["REF-05"]["quantities"]["S2.T"]
    valve = {"effect_K": t_unmapped - t_ours, "tolerance_K": comparison_tolerance("S2.T", t_ours)}
    _ = vin
    return {"PC-1": pc1, "PC-2": pc2, "REF-05-latent-offset": valve}


def dwsim_mapping() -> dict[str, Any]:
    """Spec §9.3: DWSIM's Raoult enthalpies are h^V = c_p (T - 298.15) and
    h^L = c_p (T - 298.15) - dH_vap + P v.
    With dH_vap,i := L_i + P_r v_i its h^V - h^L equals SYN-001's L_i - v_i (P - P_r) at every P;
    with dH_f,ig,i := dH_vap,i its liquid formation enthalpy dH_f,ig - dH_vap is zero, as
    SYN-001-ref-v1 declares."""
    dh = tuple(TH.b.L_VAP[i] + P_R * V_LIQ[i] for i in range(NC))
    gaps = []
    for p in (mpf(50000), P_R, mpf(180000), mpf(200000)):
        for t in (mpf(300), mpf(360), mpf(440)):
            for i in range(NC):
                dwsim = (CP * (t - mpf("298.15"))) - (
                    CP * (t - mpf("298.15")) - dh[i] + p * V_LIQ[i]
                )
                ours = TH.h("V", i, t, p) - TH.h("L", i, t, p)
                gaps.append(abs(dwsim - ours))
    unmapped = tuple(TH.b.L_VAP[i] for i in range(NC))
    # Unmapped (dH_vap = L_i): DWSIM's latent at P_r is L_i - P_r v_i; SYN-001's is L_i.
    t_any = mpf(360)
    offset = [
        (unmapped[i] - P_R * V_LIQ[i]) - (TH.h("V", i, t_any, P_R) - TH.h("L", i, t_any, P_R))
        for i in range(NC)
    ]
    return {
        "dH_vap_J_per_mol": dh,
        "dH_f_ig_J_per_mol": dh,
        "max_latent_gap": max(gaps),
        "unmapped_latent_offset_J_per_mol": tuple(offset),
    }


def split_with_k(
    n: Sequence[Any], t: Any, p: Any, k_fn: Callable[[int, Any, Any], Any]
) -> dict[str, Any]:
    """A Rachford-Rice split with an arbitrary K (the tools' K has no Poynting factor)."""
    tot = total(n)
    k = [k_fn(i, t, p) for i in range(NC)]
    z = [n[i] / tot for i in range(NC)]
    kmax, kmin = max(k), min(k)
    lo, hi = max(ZERO, 1 / (1 - kmax)), min(mpf(1), 1 / (1 - kmin))

    def rr(beta: Any) -> Any:
        return sum((z[i] * (k[i] - 1) / (1 + beta * (k[i] - 1)) for i in range(NC)), ZERO)

    beta = t5.bisect(lambda b_: -rr(b_), lo, hi, 200)
    x = [z[i] / (1 + beta * (k[i] - 1)) for i in range(NC)]
    v = tuple(beta * tot * k[i] * x[i] for i in range(NC))
    return {"beta": beta, "v": v, "l": tuple(n[i] - v[i] for i in range(NC))}


# =============================================================================================
# 4. The sampling law's draw (spec §6.3): SHA-256 in counter mode. Known-answer tests.
# =============================================================================================


def uniform(key: str) -> tuple[int, Any]:
    """u in [0, 1): SHA-256(key, UTF-8)'s first 8 bytes, big-endian, top 53 bits, times 2^-53."""
    word = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big")
    k = word >> 11
    return k, mpf(k) / mpf(2) ** 53


def draw_key(profile: str, case: str, start: int, joint: int, coordinate: str, attempt: int) -> str:
    return f"T06-ens-v1|{profile}|{case}|{start:02d}|{joint:02d}|{coordinate}|{attempt:02d}"


KAT_KEYS = (
    ("nominal", "SYN-001-nominal", 0, 0, "S6.n.A", 0),
    ("nominal", "SYN-001-nominal", 0, 0, "S6.n.B", 0),
    ("nominal", "SYN-001-nominal", 19, 3, "S6.n.C", 7),
    ("nominal", "SYN-001-A02-360", 5, 0, "S3.T", 0),
    ("nominal", "SYN-001-UL-C1", 0, 0, "S2.n.A", 0),
    ("nominal", "SYN-001-UL-C1", 0, 0, "U-HEAT.Q", 0),
    ("nominal", "SYN-001-T06-NET03", 12, 0, "S10.T", 1),
    ("box", "SYN-001-UL-C3", 7, 0, "S6.n.B", 0),
    ("log", "SYN-001-UL-C2", 0, 0, "S4.n.C", 0),
    ("trivial-split", "SYN-001-UL-C1", 3, 0, "split:U-VLV", 0),
)


def delta_generator(k53: int) -> float:
    """Amendment 2 (spec §6.3): the generator's arithmetic, stated as code. `u = k·2⁻⁵³` and
    `w = 2u − 1` are exact in binary64; `w / 5` is ONE correctly rounded division, so it is the
    exact `0.2·(2u − 1)` rounded once. The literal `0.2 * w` multiplies by the binary64 nearest
    0.2 and is off by an ulp at some keys (35 % of keys, measured on 100 000)."""
    u = k53 * 2.0**-53
    return (2.0 * u - 1.0) / 5.0


def delta_exact_rounded(k53: int) -> float:
    """The exact `(2k − 2⁵³)/(5·2⁵³)` rounded once to binary64 (CPython's int/int division is
    correctly rounded): the expectation, computed without binary64 arithmetic."""
    return float(Fraction(2 * k53 - 2**53, 5 * 2**53))


def kats() -> list[dict[str, Any]]:
    out = []
    for args in KAT_KEYS:
        key = draw_key(*args)
        k, u = uniform(key)
        delta = mpf("0.2") * (2 * u - 1)
        exact = delta_exact_rounded(k)
        w = 2.0 * (k * 2.0**-53) - 1.0
        out.append(
            {
                "key": key,
                "k53": k,
                "u": u,
                "delta": delta,
                # Amendment 2: the binary64 bit patterns A21 compares.
                "u_hex": (k * 2.0**-53).hex(),
                "delta_hex": exact.hex(),
                "literal_0p2_product_differs": 0.2 * w != exact,
                "decimal17_differs": float(s(delta, 17)) != exact,
            }
        )
    return out


# =============================================================================================
# 5. The gate (spec §7): N, the threshold, and one-sided 95 % Clopper-Pearson lower bounds
# =============================================================================================

ELIGIBLE_CASES = 22
STARTS_PER_CASE = 20
N_STARTS = ELIGIBLE_CASES * STARTS_PER_CASE
GATE_FRACTION = mpf("0.95")


def s_min() -> int:
    s = int(mp.ceil(GATE_FRACTION * N_STARTS))
    return s


CP_ALPHA = mpf("0.05")


def cp_lower(s: int, n: int, alpha: Any = CP_ALPHA) -> Any:
    """The one-sided (1 - alpha) Clopper-Pearson lower bound: p with P(Bin(n, p) >= s) = alpha."""
    if s == 0:
        return ZERO
    # P(X >= s | p) = I_p(s, n - s + 1), increasing in p; the bound is where it equals alpha.
    return t5.bisect(
        lambda p: betainc(s, n - s + 1, 0, p, regularized=True) - alpha, mpf(0), mpf(1), 200
    )


def cp_table() -> dict[int, Any]:
    return {s: cp_lower(s, N_STARTS) for s in range(N_STARTS - 30, N_STARTS + 1)}


# =============================================================================================
# 6. ADV-06: the noisy callback's three amplitudes (spec §4.8), argued on C1's registered flows
# =============================================================================================

NOISE_LEVELS = {
    "H": {"eta_h_J_per_mol": mpf(10), "eta_lnK": mpf("1e-3")},
    "M": {"eta_h_J_per_mol": mpf("1e-5"), "eta_lnK": mpf("1e-11")},
    "L": {"eta_h_J_per_mol": mpf("1e-10"), "eta_lnK": mpf("1e-15")},
}
#: The largest flow summed in one C1 energy row (U-PHF: S4's split plus both products, 3 + 3 mol/s).
C1_ROW_FLOW_MAX = mpf(6)
#: The smallest flowing component flow in a C1 energy row is read from the T05 twin's root.


def noise_bands(c1_min_flow: Any) -> dict[str, Any]:
    out = {}
    for level, eta in NOISE_LEVELS.items():
        row_max = C1_ROW_FLOW_MAX * eta["eta_h_J_per_mol"] / SCALE["heat_rate"]
        row_min = c1_min_flow * eta["eta_h_J_per_mol"] / SCALE["heat_rate"]
        out[level] = {
            **eta,
            "energy_row_noise_scaled_max": row_max,
            "energy_row_noise_scaled_typical_min": row_min,
            "witness_error_scaled_typical_min": row_min / WITNESS_STEP,
            "witness_error_scaled_max": row_max / WITNESS_STEP,
        }
    return out


# =============================================================================================
# 7. The corpus (spec §3): machine-readable registration, with its counting claims
# =============================================================================================

PLAN_IDS = {
    "STR": 6,
    "STA": 4,
    "NUM": 6,
    "THM": 6,
    "NET": 7,
    "ADV": 6,
    "VER": 5,
}

CORPUS: tuple[tuple[str, str, str, str, bool], ...] = (
    # (corpus id, fixture, expected-outcome kind, solve path, ensemble eligible)
    ("STR-01", "SYN-001-UL-C1", "verified_at_reference", "revision_eo", True),
    ("STR-02", "SYN-001-T06-STR02", "validation", "none", False),
    ("STR-03", "SYN-001-conflicting-heater-spec", "validation", "none", False),
    ("STR-04", "T01:SQ-1", "structural_finding", "none", False),
    ("STR-05", "T05b:CH-UP", "certificate_unverified_rank", "revision_eo", False),
    ("STR-06", "SYN-001-T06-STR06", "validation", "none", False),
    ("STA-01", "T05b:DZ-3", "verified_at_reference", "revision_eo", True),
    ("STA-02", "SYN-001-T06-STA02", "verified_at_reference", "revision_eo", True),
    # Amendment 1 (2026-09-26, Frank's Q3/Q4): STA-03 converts, STA-04 maps; both are solved and
    # certified at their unpermuted, SI twins' roots, and neither is eligible (METAMORPHIC below).
    ("STA-03", "SYN-001-T06-STA03", "verified_at_reference", "tear", False),
    ("STA-04", "SYN-001-T06-STA04", "verified_at_reference", "revision_eo", False),
    ("STA-05", "T05b:DZ-7", "verified_at_reference", "revision_eo", True),
    ("NUM-01", "K03:BND-01", "converged_to_closed_form", "newton_core", False),
    ("NUM-02", "NUM-02-linear-recycle", "converged_to_closed_form", "newton_core", False),
    ("NUM-03", "T05b:NP-1", "verified_at_reference", "revision_eo", True),
    ("NUM-04", "T02:A23-nominal-eo-from-root", "verified_at_reference", "legacy_eo", False),
    ("NUM-05", "K03:NUM-05", "typed_failure", "newton_core", False),
    ("NUM-06", "K03:NUM-06", "typed_failure", "newton_core", False),
    ("THM-01", "SYN-001-T06-THM01", "verified_at_reference", "revision_eo", True),
    ("THM-02", "SYN-001-T06-THM02", "verified_at_reference", "revision_eo", True),
    ("THM-03", "SYN-001-all-liquid-310K", "verified_at_reference", "tear", True),
    ("THM-04", "SYN-001-all-vapor-420K", "verified_at_reference", "tear", False),
    ("THM-05", "T05:RX-S-convention", "construction_refusal", "none", False),
    ("THM-06", "K02:exact-cache", "invariant", "none", False),
    ("THM-07", "T05b:SC-2", "verified_at_reference", "revision_eo", True),
    ("THM-08", "T05b:SC-1", "verified_at_reference", "revision_eo", True),
    ("THM-09", "T05b:SC-3", "verified_at_reference", "revision_eo", True),
    ("THM-10", "SYN-001-T06-THM10", "verified_at_reference", "revision_eo", True),
    ("NET-01", "SYN-001-nominal", "verified_at_reference", "tear", True),
    ("NET-02", "SYN-001-T06-NET02", "verified_at_reference", "revision_eo", True),
    ("NET-03", "SYN-001-T06-NET03", "verified_at_reference", "revision_eo", True),
    ("NET-04", "T02:REC-01", "converged_to_closed_form", "tear_synthetic", False),
    ("NET-05", "SYN-001-A02-360", "verified_at_reference", "legacy_eo", True),
    ("NET-06", "SYN-001-T06-NET06", "verified_at_reference", "revision_eo", True),
    ("NET-07", "SYN-001-UL-C3", "verified_at_reference", "revision_eo", True),
    ("NET-08", "SYN-001-UL-C2", "verified_at_reference", "revision_eo", True),
    ("NET-09", "SYN-001-T06-NET09", "verified_at_reference", "revision_eo", True),
    ("NET-10", "SYN-001-T06-NET10", "verified_at_reference", "revision_eo", True),
    ("NET-11", "SYN-001-T06-NET11", "verified_at_reference", "revision_eo", True),
    ("ADV-01", "T03:PHS-05-default-policy", "verified_at_reference", "legacy_eo", False),
    ("ADV-02", "T04:HOM-03", "typed_failure", "legacy_eo", False),
    ("ADV-03", "T04:HOM-04", "typed_failure", "legacy_eo", False),
    ("ADV-04", "T04:ADV-04-mapping-doubles", "typed_failure", "ptc_synthetic", False),
    ("ADV-05", "T03:MR-A/MR-B/MR-C", "multiple_roots", "tear_synthetic", False),
    ("ADV-06", "SYN-001-T06-ADV06", "noise_levels", "revision_eo", False),
    ("VER-01", "K04:INJ-1", "certificate_failed", "injected", False),
    ("VER-02", "K04:REG-eps", "regularity_inconclusive", "injected", False),
    ("VER-03", "K04:REG-eps-identity", "regularity_inconclusive", "injected", False),
    ("VER-04", "K04:SQ-0/SQ-1/SQ-2", "regularity_fixtures", "newton_core", False),
    ("VER-05", "K04:INJ-4", "certificate_relaxed", "injected", False),
)

SUCCESS_KINDS = ("verified_at_reference", "converged_to_closed_form")

#: Spec §6.1 clause (e), amended 2026-09-26: a case whose compiled problem and start restate another
#: case's exactly is not eligible; the case it restates is. NUM-04 starts at NET-01's root; STA-03's
#: converted revision is SYN-001-nominal's declaration; STA-04's mapped revision is C2's.
METAMORPHIC = {"NUM-04": "NET-01", "STA-03": "NET-01", "STA-04": "NET-08"}
SUCCESS_DENOMINATOR = 30


def corpus_doc() -> dict[str, Any]:
    rows = [
        {
            "id": cid,
            "class": cid[:3],
            "fixture": fx,
            "expected": kind,
            "path": path,
            "eligible": elig,
            "in_success_denominator": kind in SUCCESS_KINDS,
        }
        for cid, fx, kind, path, elig in CORPUS
    ]
    return {
        "cases": rows,
        "counted": len(rows),
        "eligible": sum(1 for r in rows if r["eligible"]),
        "in_success_denominator": sum(1 for r in rows if r["in_success_denominator"]),
    }


# =============================================================================================
# 7b. Amendment 1 (2026-09-26): unit conversion, component order, reference-tool settings
# =============================================================================================

#: Spec §8.5 (A1): `unit-conversion-v1` is exactly ADR 0001 D1.3-D1.4's two input conversions.
#: Each is ONE IEEE-754 binary64 operation on binary64 operands (Python floats here, deliberately,
#: not mpmath): the result is platform-independent, so the known answers are bit patterns.
UNIT_CONVERSION_ID = "unit-conversion-v1"
#: The binary64 nearest 273.15 (ADR 0001 D1.3: converting a temperature from degC adds 273.15).
DEGC_OFFSET = 273.15
#: plan v1.1 §3.1 = benchmarks/syn001/components.yaml `molecular_weight`, kg/mol, keyed by id.
SYN001_MOLAR_MASS = {"A": 0.1, "B": 0.1, "C": 0.1}
#: Distinct masses: SYN-001's three are equal, so only a synthetic table can see a component-index
#: error in the mass-basis conversion (spec §15, A1).
SYNTHETIC_MOLAR_MASS = {"A": 0.1, "B": 0.2, "C": 0.04401}
#: (value in degC). 26.85 is STA-03-degC; 86.85 and 84.85 are the verify_bound control (A02-360's
#: 360 K and 358 K); -40, 12.34 and 0.01 separate the binary64 sum from the decimal one.
DEGC_KATS = (26.85, 86.85, 84.85, -40.0, 12.34, 0.01)
#: (value in kg/s, component, table). The first is STA-03-kgs.
MASS_KATS = (
    (0.1, "A", "SYN-001"),
    (0.3, "A", "synthetic"),
    (0.3, "B", "synthetic"),
    (0.3, "C", "synthetic"),
)


def degc_to_k(value: float) -> float:
    """`unit-conversion-v1`, rule `degC_to_K`: one binary64 addition."""
    return value + DEGC_OFFSET


def mass_to_molar(value: float, molar_mass: float) -> float:
    """`unit-conversion-v1`, rule `mass_to_molar`: one binary64 division by `M_c` (kg/mol)."""
    return value / molar_mass


def decimal_degc(value: float) -> float:
    """What a decimal implementation would give: the correctly rounded exact decimal sum."""
    from decimal import Decimal

    return float(Decimal(repr(value)) + Decimal("273.15"))


def unit_known_answers() -> dict[str, Any]:
    tables = {"SYN-001": SYN001_MOLAR_MASS, "synthetic": SYNTHETIC_MOLAR_MASS}
    degc = [
        {
            "value": v,
            "unit": "degC",
            "required_kind": "temperature",
            "rule": "degC_to_K",
            "si_value": repr(degc_to_k(v)),
            "si_value_hex": degc_to_k(v).hex(),
            "si_unit": "K",
            "decimal_sum_differs": degc_to_k(v) != decimal_degc(v),
        }
        for v in DEGC_KATS
    ]
    mass = [
        {
            "value": v,
            "unit": "kg/s",
            "required_kind": "molar_flow",
            "component": c,
            "molar_mass_table": table,
            "molar_mass_kg_per_mol": tables[table][c],
            "rule": "mass_to_molar",
            "si_value": repr(mass_to_molar(v, tables[table][c])),
            "si_value_hex": mass_to_molar(v, tables[table][c]).hex(),
            "si_unit": "mol/s",
            "reciprocal_product_differs": mass_to_molar(v, tables[table][c])
            != v * (1.0 / tables[table][c]),
        }
        for v, c, table in MASS_KATS
    ]
    return {"degC": degc, "mass_basis": mass}


#: Spec §9.3 (A1): the registered tool settings, machine-readable for A49. IDAES's constr_viol_tol
#: is 1e-9 (M6 measured 1e-10 below the Pa-row floor; spec §18 finding 7).
REFERENCE_TOOL_SETTINGS: dict[str, Any] = {
    "IDAES": {
        "final_solve": {
            "linear_solver": "mumps",
            "tol": "1e-10",
            "constr_viol_tol": "1e-9",
            "max_iter": 500,
        },
        "initializers": {"linear_solver": "mumps", "other_options": "IDAES defaults"},
        "converged_iff_termination": "Optimal Solution Found",
        # Amendment 2 (spec §9.3): SmoothVLE's smoothing parameters on every state block of every
        # fixture and control (IDAES's defaults are eps_1 = 0.01 K, eps_2 = 5e-4 K).
        "smooth_vle": {"eps_1_K": "1e-8", "eps_2_K": "1e-8"},
    },
    "DWSIM": {
        "flash_loop_tolerances": "1e-10",
        "flash_loop_iterations": 1000,
        "recycle": {
            "mass_flow_kg_per_s": "1e-12",
            "temperature_K": "1e-8",
            "pressure_Pa": "1e-6",
            "iterations": 1000,
            "acceleration": "none",
            "legacy_mode": True,
        },
    },
    "REF-08_tool_recycle_guess": {
        "n_mol_per_s": ["0.2", "0.6", "0.8"],
        "T_K": "360",
        "P_Pa": "1e5",
    },
    "PC-1": {"tools": ["DWSIM"], "IDAES": "not_applicable"},
    "PC-2": {
        "tools": ["DWSIM", "IDAES"],
        "feed": {"n_mol_per_s": ["1", "1", "1"], "T_K": "300", "P_Pa": "1.5e5", "phase": "liquid"},
        "fixture_ours": "SYN-001-T06-PC2",
    },
}
IDAES_CONSTR_VIOL_TOL = mpf("1e-9")
#: The Pa rows sit at up to 1.8e5 Pa (REF-05's inlet) inside a domain that ends at 2e5 Pa.
ULP_2E5_PA = mpf(2) ** -35


# =============================================================================================
# 7c. Amendment 2 (2026-09-26): unit-conversion-v2 (ADR 0016), F6's registered states (ADR 0017),
#     IDAES's SmoothVLE semantics (spec §9.3)
# =============================================================================================

#: ADR 0016: `unit-conversion-v2`. SI = RN(a·D(v) + b): D(v) is the shortest decimal that rounds to
#: the binary64 `v` (Python's `repr`), a and b are exact rationals from the unit's definition, the
#: arithmetic is exact (Fraction) and RN is ONE round-to-nearest-even to binary64. Two inputs that
#: denote the same exact quantity therefore bind to the same double (unit invariance).
UNIT_CONVERSION_V2_ID = "unit-conversion-v2"
#: International foot-pound (1959): 1 lb = 0.45359237 kg, g_n = 9.80665 m/s², 1 in = 0.0254 m.
PSI_PA = Fraction("0.45359237") * Fraction("9.80665") / Fraction("0.0254") ** 2
#: The dimensionless parameters that are fractions of one, by name up to the first `.`
#: (T05 §1.3's table); `%` is refused on every other dimensionless target (`nu.<c>`).
FRACTION_PARAMETERS = ("split_fraction", "efficiency", "conversion", "split")
#: (required kind, unit, rule, a, b, declared kinds admitted, target class). Target classes:
#: `any` — every target of the kind; `component` — a one-component flow; `mass` — a one-component
#: flow whose component has a molecular weight (a is then per kg/mol: SI = RN(a·D(v)/D(M_c)));
#: `fraction` — a parameter in FRACTION_PARAMETERS. The SI unit of each kind is the identity row
#: (no record) and is not listed.
V2_ROWS: tuple[tuple[str, str, str, Fraction, Fraction, tuple[str, ...], str], ...] = (
    ("temperature", "degC", "degC_to_K", Fraction(1), Fraction("273.15"), ("temperature",), "any"),
    (
        "temperature",
        "degF",
        "degF_to_K",
        Fraction(5, 9),
        Fraction("273.15") - Fraction(160, 9),
        ("temperature",),
        "any",
    ),
    (
        "temperature_difference",
        "degC",
        "scale",
        Fraction(1),
        Fraction(0),
        ("temperature_difference",),
        "any",
    ),
    (
        "temperature_difference",
        "degF",
        "scale",
        Fraction(5, 9),
        Fraction(0),
        ("temperature_difference",),
        "any",
    ),
    ("pressure", "kPa", "scale", Fraction(10**3), Fraction(0), ("pressure",), "any"),
    ("pressure", "MPa", "scale", Fraction(10**6), Fraction(0), ("pressure",), "any"),
    ("pressure", "bar", "scale", Fraction(10**5), Fraction(0), ("pressure",), "any"),
    ("pressure", "atm", "scale", Fraction(101325), Fraction(0), ("pressure",), "any"),
    ("pressure", "psi", "scale", PSI_PA, Fraction(0), ("pressure",), "any"),
    ("heat_rate", "kW", "scale", Fraction(10**3), Fraction(0), ("heat_rate",), "any"),
    ("heat_rate", "MW", "scale", Fraction(10**6), Fraction(0), ("heat_rate",), "any"),
    ("power", "kW", "scale", Fraction(10**3), Fraction(0), ("power",), "any"),
    ("power", "MW", "scale", Fraction(10**6), Fraction(0), ("power",), "any"),
    ("molar_flow", "kmol/s", "scale", Fraction(10**3), Fraction(0), ("molar_flow",), "component"),
    (
        "molar_flow",
        "mmol/s",
        "scale",
        Fraction(1, 10**3),
        Fraction(0),
        ("molar_flow",),
        "component",
    ),
    ("molar_flow", "mol/h", "scale", Fraction(1, 3600), Fraction(0), ("molar_flow",), "component"),
    (
        "molar_flow",
        "kmol/h",
        "scale",
        Fraction(1000, 3600),
        Fraction(0),
        ("molar_flow",),
        "component",
    ),
    (
        "molar_flow",
        "kg/s",
        "mass_to_molar",
        Fraction(1),
        Fraction(0),
        ("molar_flow", "mass_flow"),
        "mass",
    ),
    (
        "molar_flow",
        "g/s",
        "mass_to_molar",
        Fraction(1, 10**3),
        Fraction(0),
        ("molar_flow", "mass_flow"),
        "mass",
    ),
    (
        "molar_flow",
        "kg/h",
        "mass_to_molar",
        Fraction(1, 3600),
        Fraction(0),
        ("molar_flow", "mass_flow"),
        "mass",
    ),
    ("dimensionless", "%", "scale", Fraction(1, 100), Fraction(0), ("dimensionless",), "fraction"),
    ("mole_fraction", "%", "scale", Fraction(1, 100), Fraction(0), ("mole_fraction",), "any"),
)
SI_UNIT = {
    "temperature": "K",
    "temperature_difference": "K",
    "pressure": "Pa",
    "heat_rate": "W",
    "power": "W",
    "molar_flow": "mol/s",
    "mass_flow": "kg/s",
    "dimensionless": "1",
    "mole_fraction": "1",
}


class RefusedError(Exception):
    """`unit-conversion-v2` refuses: `reason` is "value", "kind" or "unit" (ADR 0016, V0-V5)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def decimal_of(value: float) -> Fraction:
    """D(v): the shortest decimal that rounds to `v` (CPython's `repr`, David Gay's algorithm)."""
    return Fraction(repr(value))


def round_once(exact: Fraction) -> float:
    """RN: exact rational to the nearest binary64, ties to even; a zero result is +0.0 (ADR 0001
    D1.5); a result outside the binary64 range is refused (ADR 0016 V5)."""
    try:
        result = float(exact)
    except OverflowError:
        raise RefusedError("value") from None
    if math.isinf(result):
        raise RefusedError("value")
    return 0.0 if result == 0.0 else result


def target_admits(
    target_class: str, target: str, component: str | None, masses: Mapping[str, float]
) -> bool:
    if target_class == "any":
        return True
    if target_class == "component":
        return component is not None
    if target_class == "mass":
        return component is not None and component in masses
    if target_class == "fraction":
        return target.removeprefix("parameters.").split(".")[0] in FRACTION_PARAMETERS
    raise AssertionError(target_class)


def convert_v2(
    value: float,
    unit: str,
    required_kind: str,
    declared_kind: str,
    target: str,
    component: str | None = None,
    masses: Mapping[str, float] | None = None,
) -> tuple[float, str | None]:
    """ADR 0016's steps V0-V5 for a target whose required kind is known; returns (SI value, rule),
    rule None for the identity. Raises `RefusedError`."""
    masses = masses or {}
    if not math.isfinite(value):  # V0
        raise RefusedError("value")
    admitted = {required_kind}  # V2
    if required_kind == "molar_flow" and component is not None:
        admitted.add("mass_flow")
    if declared_kind not in admitted:
        raise RefusedError("kind")
    if declared_kind == required_kind and unit == SI_UNIT[required_kind]:  # V3: identity
        return value, None
    for kind, row_unit, rule, a, b, kinds, target_class in V2_ROWS:  # V4
        if (
            kind == required_kind
            and row_unit == unit
            and declared_kind in kinds
            and target_admits(target_class, target, component, masses)
        ):
            scale = a / decimal_of(masses[component]) if target_class == "mass" else a  # type: ignore[index]
            return round_once(scale * decimal_of(value) + b), rule  # V5
    raise RefusedError("unit")


def binary_reading(
    value: float, unit: str, kind: str, component: str | None, masses: Mapping[str, float]
) -> float:
    """The rejected alternative: the same exact map applied to the binary64 `v` (and `M_c`), not
    to their decimals, rounded once. v1's two rules are this reading."""
    for row_kind, row_unit, _rule, a, b, _kinds, cls in V2_ROWS:
        if row_kind == kind and row_unit == unit:
            scale = a / Fraction(masses[component]) if cls == "mass" else a  # type: ignore[index]
            return float(scale * Fraction(value) + b)
    raise AssertionError((kind, unit))


def nearest_binary64(result: float, exact: Fraction) -> bool:
    """Independent check of RN: `result` is at least as close to `exact` as both neighbours, and
    on a tie its significand is even."""
    here = abs(Fraction(result) - exact)
    for direction in (math.inf, -math.inf):
        other = math.nextafter(result, direction)
        there = abs(Fraction(other) - exact)
        if there < here:
            return False
        if there == here and (int(result.hex().split("p")[0].split(".")[1] or "0", 16) & 1):
            return False
    return True


#: Operands searched, in this order, for one where the naive binary64 chain differs from RN(exact);
#: fixed so the emission is reproducible.
DISCRIMINATING_CANDIDATES = (
    0.1,
    0.3,
    0.7,
    1.1,
    1.3,
    2.3,
    3.3,
    4.4,
    7.7,
    8.1,
    9.9,
    12.34,
    33.3,
    55.55,
    98.6,
    123.456,
    0.07,
    0.013,
    5.1,
    75.1,
    14.7,
    -40.0,
    0.2,
    0.6,
    2.9,
    6.1,
    17.3,
    250.1,
    3.7,
    0.9,
)
#: The naive chain a hand implementation would write, per (required kind, unit), on binary64 `v`
#: (and M = the component's binary64 molecular weight for the mass rows).
NAIVE_CHAINS: dict[tuple[str, str], Callable[[float, float], float]] = {
    ("temperature", "degC"): lambda v, m: v + 273.15,
    ("temperature", "degF"): lambda v, m: (v - 32.0) * 5.0 / 9.0 + 273.15,
    ("temperature_difference", "degF"): lambda v, m: v * 5.0 / 9.0,
    ("pressure", "kPa"): lambda v, m: v * 1e3,
    ("pressure", "MPa"): lambda v, m: v * 1e6,
    ("pressure", "bar"): lambda v, m: v * 1e5,
    ("pressure", "atm"): lambda v, m: v * 101325.0,
    ("pressure", "psi"): lambda v, m: v * 6894.757293168361,
    ("heat_rate", "kW"): lambda v, m: v * 1e3,
    ("heat_rate", "MW"): lambda v, m: v * 1e6,
    ("molar_flow", "kmol/s"): lambda v, m: v * 1e3,
    ("molar_flow", "mmol/s"): lambda v, m: v * 1e-3,
    ("molar_flow", "mol/h"): lambda v, m: v / 3600.0,
    ("molar_flow", "kmol/h"): lambda v, m: v / 3.6,
    ("molar_flow", "kg/s"): lambda v, m: v / m,
    ("molar_flow", "g/s"): lambda v, m: v / 1000.0 / m,
    ("molar_flow", "kg/h"): lambda v, m: v / 3600.0 / m,
    ("dimensionless", "%"): lambda v, m: v * 0.01,
}
#: Where the naive chain fails, every row's first discriminating operand is a known answer.
ROW_TARGET = {
    "temperature": ("state.T", None),
    "temperature_difference": ("parameters.none", None),
    "pressure": ("state.P", None),
    "heat_rate": ("duty.Q", None),
    "power": ("work.W", None),
    "molar_flow": ("state.n", "A"),
    "dimensionless": ("parameters.split_fraction", None),
    "mole_fraction": ("parameters.none", None),
}
#: Metamorphic pairs (ADR 0016; spec A69-A71): (case, input id, source, value as written, unit,
#: required kind, target, component, the registered SI value it must bind to, bit for bit).
V2_PAIRS: tuple[tuple[str, str, str, float, str, str, str, str | None, float], ...] = (
    (
        "SYN-001-nominal",
        "SPEC-feed-n-A",
        "specification",
        3.6,
        "kmol/h",
        "molar_flow",
        "state.n",
        "A",
        1.0,
    ),
    (
        "SYN-001-nominal",
        "SPEC-feed-n-A",
        "specification",
        3600.0,
        "mol/h",
        "molar_flow",
        "state.n",
        "A",
        1.0,
    ),
    (
        "SYN-001-nominal",
        "SPEC-feed-n-A",
        "specification",
        1000.0,
        "mmol/s",
        "molar_flow",
        "state.n",
        "A",
        1.0,
    ),
    (
        "SYN-001-nominal",
        "SPEC-feed-n-A",
        "specification",
        0.001,
        "kmol/s",
        "molar_flow",
        "state.n",
        "A",
        1.0,
    ),
    (
        "SYN-001-nominal",
        "SPEC-feed-n-A",
        "specification",
        360.0,
        "kg/h",
        "molar_flow",
        "state.n",
        "A",
        1.0,
    ),
    (
        "SYN-001-nominal",
        "SPEC-feed-n-A",
        "specification",
        100.0,
        "g/s",
        "molar_flow",
        "state.n",
        "A",
        1.0,
    ),
    (
        "SYN-001-nominal",
        "SPEC-feed-T",
        "specification",
        80.33,
        "degF",
        "temperature",
        "state.T",
        None,
        300.0,
    ),
    (
        "SYN-001-nominal",
        "SPEC-feed-P",
        "specification",
        1.0,
        "bar",
        "pressure",
        "state.P",
        None,
        100000.0,
    ),
    (
        "SYN-001-nominal",
        "SPEC-feed-P",
        "specification",
        100.0,
        "kPa",
        "pressure",
        "state.P",
        None,
        100000.0,
    ),
    (
        "SYN-001-nominal",
        "SPEC-feed-P",
        "specification",
        0.1,
        "MPa",
        "pressure",
        "state.P",
        None,
        100000.0,
    ),
    (
        "SYN-001-UL-C1",
        "SPEC-pump-P",
        "specification",
        180.0,
        "kPa",
        "pressure",
        "state.P",
        None,
        180000.0,
    ),
    (
        "SYN-001-UL-C1",
        "SPEC-pump-P",
        "specification",
        1.8,
        "bar",
        "pressure",
        "state.P",
        None,
        180000.0,
    ),
    (
        "SYN-001-UL-C1",
        "SPEC-pump-P",
        "specification",
        0.18,
        "MPa",
        "pressure",
        "state.P",
        None,
        180000.0,
    ),
    (
        "SYN-001-UL-C1",
        "SPEC-phf-Q",
        "specification",
        10.0,
        "kW",
        "heat_rate",
        "duty.Q",
        None,
        10000.0,
    ),
    (
        "SYN-001-UL-C1",
        "SPEC-phf-Q",
        "specification",
        0.01,
        "MW",
        "heat_rate",
        "duty.Q",
        None,
        10000.0,
    ),
    (
        "SYN-001-UL-C1",
        "U-PUMP.efficiency",
        "parameter",
        75.1,
        "%",
        "dimensionless",
        "parameters.efficiency",
        None,
        0.751,
    ),
    (
        "SYN-001-UL-C2",
        "U-RX.conversion.A",
        "parameter",
        51.0,
        "%",
        "dimensionless",
        "parameters.conversion.A",
        None,
        0.51,
    ),
    (
        "SYN-001-UL-C2",
        "U-SEP.split.C",
        "parameter",
        5.1,
        "%",
        "dimensionless",
        "parameters.split.C",
        None,
        0.051,
    ),
    (
        "SYN-001-UL-C2",
        "U-RX.pressure_drop",
        "parameter",
        2.5,
        "kPa",
        "pressure",
        "parameters.pressure_drop",
        None,
        2500.0,
    ),
    (
        "SYN-001-UL-C3",
        "U-SPLIT.split_fraction",
        "parameter",
        61.0,
        "%",
        "dimensionless",
        "parameters.split_fraction",
        None,
        0.61,
    ),
    (
        "SYN-001-UL-C3",
        "SPEC-phf-Q",
        "specification",
        48.0,
        "kW",
        "heat_rate",
        "duty.Q",
        None,
        48000.0,
    ),
    (
        "SYN-001-T06-THM10",
        "SPEC-phf-Q",
        "specification",
        -40.0,
        "kW",
        "heat_rate",
        "duty.Q",
        None,
        -40000.0,
    ),
    (
        "SYN-001-A02-360",
        "SPEC-flash-T",
        "specification",
        188.33,
        "degF",
        "temperature",
        "outlet.T",
        None,
        360.0,
    ),
)
#: Groups of inputs that denote one exact quantity (ADR 0016 unit invariance): each group binds to
#: one double. (value, unit, required kind, target, component).
V2_INVARIANCE_GROUPS: tuple[tuple[tuple[float, str, str, str, str | None], ...], ...] = (
    (
        (-40.0, "degC", "temperature", "state.T", None),
        (-40.0, "degF", "temperature", "state.T", None),
        (233.15, "K", "temperature", "state.T", None),
    ),
    (
        (75.1, "%", "dimensionless", "parameters.efficiency", None),
        (0.751, "1", "dimensionless", "parameters.efficiency", None),
    ),
    (
        (180.0, "kPa", "pressure", "state.P", None),
        (1.8, "bar", "pressure", "state.P", None),
        (0.18, "MPa", "pressure", "state.P", None),
        (180000.0, "Pa", "pressure", "state.P", None),
    ),
    (
        (3.6, "kmol/h", "molar_flow", "state.n", "A"),
        (3600.0, "mol/h", "molar_flow", "state.n", "A"),
        (0.001, "kmol/s", "molar_flow", "state.n", "A"),
        (1.0, "mol/s", "molar_flow", "state.n", "A"),
    ),
    (
        (0.3, "kg/s", "molar_flow", "state.n", "A"),
        (1080.0, "kg/h", "molar_flow", "state.n", "A"),
        (300.0, "g/s", "molar_flow", "state.n", "A"),
        (3.0, "mol/s", "molar_flow", "state.n", "A"),
    ),
)
#: The refusals A68 registers: (value, unit, required kind, declared kind, target, component,
#: reason). Readers turn `unit`/`kind`/`value` into their codes.
V2_REFUSALS: tuple[tuple[float, str, str, str, str, str | None, str], ...] = (
    (26.85, "°C", "temperature", "temperature", "state.T", None, "unit"),
    (26.85, "C", "temperature", "temperature", "state.T", None, "unit"),
    (26.85, "degc", "temperature", "temperature", "state.T", None, "unit"),
    (80.33, "degF", "pressure", "pressure", "state.P", None, "unit"),
    (1.0, "barg", "pressure", "pressure", "state.P", None, "unit"),
    (14.7, "psig", "pressure", "pressure", "state.P", None, "unit"),
    (14.7, "psia", "pressure", "pressure", "state.P", None, "unit"),
    (760.0, "mmHg", "pressure", "pressure", "state.P", None, "unit"),
    (-200.0, "%", "dimensionless", "dimensionless", "parameters.nu.A", None, "unit"),
    (50.0, "%", "temperature", "temperature", "state.T", None, "unit"),
    (1.0, "ppm", "dimensionless", "dimensionless", "parameters.split_fraction", None, "unit"),
    (0.1, "K", "molar_flow", "molar_flow", "state.n", "A", "unit"),
    (1.0, "mol/s", "molar_flow", "mass_flow", "state.n", "A", "unit"),
    (0.1, "kg/s", "molar_flow", "temperature", "state.n", "A", "kind"),
    (0.1, "kg/h", "molar_flow", "molar_flow", "state.n", "D", "unit"),
    (math.nan, "K", "temperature", "temperature", "state.T", None, "value"),
    (math.inf, "kPa", "pressure", "pressure", "state.P", None, "value"),
    (1e306, "kPa", "pressure", "pressure", "state.P", None, "value"),
)


def unit_v2_known_answers() -> dict[str, Any]:
    """Every non-identity row's known answers: its first discriminating operand, the metamorphic
    pairs, the invariance groups, the synthetic-mass component check and the refusals."""
    rows_out = []
    discriminated: dict[str, bool] = {}
    for kind, unit, _rule, _a, _b, kinds, target_class in V2_ROWS:
        target, component = ROW_TARGET[kind]
        if target_class == "fraction":
            target = "parameters.split_fraction"
        masses = SYN001_MOLAR_MASS if target_class == "mass" else {}
        chain = NAIVE_CHAINS.get((kind, unit))
        chosen = DISCRIMINATING_CANDIDATES[0]
        found = False
        if chain is not None:
            for v in (*DISCRIMINATING_CANDIDATES, *(i / 1000 for i in range(1, 100_001))):
                si, _ = convert_v2(v, unit, kind, kinds[0], target, component, masses)
                if chain(v, masses.get(component or "", 1.0)) != si:
                    chosen, found = v, True
                    break
        discriminated[f"{kind}:{unit}"] = found
        si, got_rule = convert_v2(chosen, unit, kind, kinds[0], target, component, masses)
        rows_out.append(
            {
                "required_kind": kind,
                "unit": unit,
                "rule": got_rule,
                "declared_kinds": list(kinds),
                "target_class": target_class,
                "value": repr(chosen),
                "target": target,
                "component": component,
                "si_value": repr(si),
                "si_value_hex": si.hex(),
                "si_unit": SI_UNIT[kind],
                "naive_chain_differs": found,
            }
        )
    pairs_out = []
    for case, ident, source, v, unit, kind, target, component, registered in V2_PAIRS:
        declared = kind
        masses = SYN001_MOLAR_MASS
        si, rule = convert_v2(v, unit, kind, declared, target, component, masses)
        pairs_out.append(
            {
                "case": case,
                "input": ident,
                "source": source,
                "value": repr(v),
                "unit": unit,
                "required_kind": kind,
                "target": target,
                "component": component,
                "rule": rule,
                "si_value": repr(si),
                "si_value_hex": si.hex(),
                "registered_si_value": repr(registered),
                "binds_to_registered_value": si == registered,
                # What RN(a*v + b) on the binary64 v itself (v1's reading) would give.
                "binary_reading_value": repr(binary_reading(v, unit, kind, component, masses)),
            }
        )
    groups_out = []
    for group in V2_INVARIANCE_GROUPS:
        results = [
            convert_v2(v, unit, kind, kind, target, component, SYN001_MOLAR_MASS)[0]
            for v, unit, kind, target, component in group
        ]
        groups_out.append(
            {
                "inputs": [f"{v!r} {unit}" for v, unit, _k, _t, _c in group],
                "si_value_hex": results[0].hex(),
                "all_equal": len({r.hex() for r in results}) == 1,
            }
        )
    synthetic = [
        convert_v2(0.3, "kg/h", "molar_flow", "molar_flow", "state.n", c, SYNTHETIC_MOLAR_MASS)[0]
        for c in COMPONENTS
    ]
    refusals_out = []
    for v, unit, kind, declared, target, component, reason in V2_REFUSALS:
        try:
            convert_v2(v, unit, kind, declared, target, component, SYN001_MOLAR_MASS)
            got = "converted"
        except RefusedError as error:
            got = error.reason
        refusals_out.append(
            {
                "value": repr(v),
                "unit": unit,
                "required_kind": kind,
                "declared_kind": declared,
                "target": target,
                "component": component,
                "reason": reason,
                "refused_as_registered": got == reason,
            }
        )
    # v1's known answers under v2: STA-03 and the A02 control keep their values; the three degC
    # operands v1 chose because the binary64 sum differs from the decimal one, and 0.3 kg/s over
    # the synthetic table, now take the decimal's value (ADR 0016 reverses R-077's arithmetic).
    v1_under_v2 = [
        {
            "value": repr(v),
            "unit": "degC",
            "v1_hex": degc_to_k(v).hex(),
            "v2_hex": convert_v2(v, "degC", "temperature", "temperature", "state.T")[0].hex(),
        }
        for v in DEGC_KATS
    ] + [
        {
            "value": repr(v),
            "unit": "kg/s",
            "component": c,
            "molar_mass_table": table,
            "v1_hex": mass_to_molar(
                v, {"SYN-001": SYN001_MOLAR_MASS, "synthetic": SYNTHETIC_MOLAR_MASS}[table][c]
            ).hex(),
            "v2_hex": convert_v2(
                v,
                "kg/s",
                "molar_flow",
                "molar_flow",
                "state.n",
                c,
                {"SYN-001": SYN001_MOLAR_MASS, "synthetic": SYNTHETIC_MOLAR_MASS}[table],
            )[0].hex(),
        }
        for v, c, table in MASS_KATS
    ]
    return {
        "rows": rows_out,
        "discriminated": discriminated,
        "metamorphic_pairs": pairs_out,
        "invariance_groups": groups_out,
        "synthetic_mass_kg_per_h_0p3": [r.hex() for r in synthetic],
        "refusals": refusals_out,
        "v1_known_answers_under_v2": v1_under_v2,
    }


#: ADR 0017 (F6): two saturated product streams at which `Syn001Provider.flash` returned
#: `not_converged` before the fix (measured 2026-09-26: the classification's binary64 sum puts
#: them two-phase, the Rachford-Rice bracket's signs agree, f(0)·f(1) > 0). The liquid product and
#: the vapour product of two seeded random two-phase flashes; every component flows. Stored as
#: binary64 bit patterns; the twin evaluates them exactly.
F6_STATES: dict[str, dict[str, Any]] = {
    "F6-liquid": {
        "n_hex": ("0x1.1162dac4dbaedp-10", "0x1.401b6924b775fp-2", "0x1.20bb90837f1b3p-2"),
        "T_hex": "0x1.73414197f5766p+8",
        "P_hex": "0x1.6a18d5991c1d6p+16",
        "fixed_signature": "LIQUID",
    },
    "F6-vapour": {
        "n_hex": ("0x1.f031da3db7e0bp-2", "0x1.0887a2b9d0178p-4", "0x1.0dc6dc8dd710ep-3"),
        "T_hex": "0x1.52fe0d0f214c0p+8",
        "P_hex": "0x1.9e4a8ae0e7679p+15",
        "fixed_signature": "VAPOR",
    },
}
#: ADR 0017's bound on the fixed provider's answer at these states: |β − β_exact| ≤ 1e-14.
F6_BETA_BOUND = mpf("1e-14")
#: And their distance from saturation, in K.
F6_SATURATION_BOUND_K = mpf("1e-12")


def f6_facts() -> dict[str, dict[str, Any]]:
    out = {}
    for name, state in F6_STATES.items():
        n = [mpf(float.fromhex(h)) for h in state["n_hex"]]
        t = mpf(float.fromhex(state["T_hex"]))
        p = mpf(float.fromhex(state["P_hex"]))
        total_ = sum(n)
        z = [v / total_ for v in n]
        k = [TH.k(i, t, p) for i in range(NC)]

        def rr(beta: Any, z: list[Any] = z, k: list[Any] = k) -> Any:
            return sum(z[i] * (k[i] - 1) / (1 + beta * (k[i] - 1)) for i in range(NC))

        f0, f1 = rr(ZERO), rr(mpf(1))
        if f0 > 0 and f1 < 0:
            beta = findroot(rr, (ZERO, mpf(1)), solver="anderson")
        else:
            beta = ZERO if f0 <= 0 else mpf(1)
        bubble = findroot(lambda tt, z=z, p=p: sum(z[i] * TH.k(i, tt, p) for i in range(NC)) - 1, t)
        dew = findroot(lambda tt, z=z, p=p: sum(z[i] / TH.k(i, tt, p) for i in range(NC)) - 1, t)
        fixed_beta = ZERO if state["fixed_signature"] == "LIQUID" else mpf(1)
        out[name] = {
            "T_K": t,
            "P_Pa": p,
            "f0": f0,
            "f1": f1,
            "beta_exact": beta,
            "fixed_beta": fixed_beta,
            "T_minus_bubble_K": t - bubble,
            "T_minus_dew_K": t - dew,
            "all_components_flow": all(v > 0 for v in n),
        }
    return out


#: Spec §9.3 (A2): IDAES SmoothVLE's equilibrium temperature is
#: T_eq = smooth_min(smooth_max(T, T_bub, eps_1), T_dew, eps_2) with
#: smooth_max(a, b, e) = (a + b + sqrt((a - b)^2 + e^2))/2 (idaes.core.util.math), so
#: |T_eq - min(max(T, T_bub), T_dew)| <= (eps_1 + eps_2)/2, with equality-limit eps_1/2 at a stream
#: exactly at its bubble point (REF-08's recycle: 5.0e-3 K measured at IDAES's defaults).
SMOOTH_VLE_DEFAULT_EPS = (mpf("0.01"), mpf("0.0005"))
SMOOTH_VLE_EPS = (mpf("1e-8"), mpf("1e-8"))
#: The self-check bound (spec §9.5 rule 2b): a_T / 100.
SMOOTH_VLE_SHIFT_BOUND = ALLOWANCE["temperature"] / 100


def smooth_max(a: Any, b: Any, eps: Any) -> Any:
    return (a + b + mp.sqrt((a - b) ** 2 + eps**2)) / 2


#: Spec Amendment 4 (§7.1 (A4), §8.8 (A4)): the scoring run's measured THM-09 start 1 (run 1,
#: `ref-x86-64`, records `S3.T = S4.T`, `S3.n.B`, `S4.n.B` as printed by the harness). Inputs to a
#: reproduction, not expectations: the claims below re-derive the row value the build lane
#: measured (1.863e-8) from the closed form, which is what makes the mechanism executable.
A4_THM09_START1 = {
    "T_K": mpf("359.9999899491406"),
    "vapor_B": mpf("0.03386673367239595"),
    "liquid_B": mpf("1.966133266327604"),
    "measured_row": mpf("1.863e-8"),
}


def a4_facts() -> dict[str, Any]:
    """Amendment 4: (i) the temperature window THM-09's U-PHF equilibrium row admits at its
    registered root (T05b SC-3: pure B, S1 370 K 1.8e5 Pa liquid -> valve to P_r -> U-PHF with
    Q = -1000 W), `tau_eq / (V L dlnK_B/dT)`, K04 §5.2's row tolerance; (ii) the saturation
    closure's two anchors: zero at a registered equilibrium split (THM-01) and 3.34 K at NET-11's
    registered liquid heater outlet, where run 1's start 16 carried a vanishing vapour."""
    n = (ZERO, mpf(2), ZERO)
    h_s1 = t5.h_flow(n, mpf(370), mpf(180000), "L")
    valve = t5.ph_solve(n, P_R, h_s1)
    phf = t5.ph_solve(n, P_R, h_s1 - 1000)
    v, l_ = phf["split"]["v"][1], phf["split"]["l"][1]
    t_sat = phf["T"]
    dlnk_dt = mp.diff(lambda t: TH.lnk(1, t, P_R), t_sat)
    tau_eq = t5.TOL["molar_flow_squared"]
    window = tau_eq / (v * l_ * dlnk_dt)
    s1 = A4_THM09_START1
    row1 = s1["vapor_B"] * s1["liquid_B"] * (1 - TH.k(1, s1["T_K"], P_R))
    cases = {name: fn() for name, fn in NEW_CASES.items()}
    thm01 = cases["SYN-001-T06-THM01"]["streams"]
    p01 = thm01["S2"]["P"]
    thm01_closure = max(
        abs(t5.bubble_dew(thm01["S3"]["n"], p01)[0] - thm01["S3"]["T"]),
        abs(t5.bubble_dew(thm01["S2"]["n"], p01)[1] - thm01["S2"]["T"]),
    )
    s4 = cases["SYN-001-T06-NET11"]["streams"]["S4"]
    net11_bubble_excess = t5.bubble_dew(s4["n"], s4["P"])[0] - s4["T"]
    return {
        "valve_T_K": valve["T"],
        "valve_vapor_B": valve["split"]["v"][1],
        "T_sat_K": t_sat,
        "vapor_B": v,
        "liquid_B": l_,
        "VL": v * l_,
        "dlnK_B_dT": dlnk_dt,
        "tau_eq": tau_eq,
        "row_window_K": window,
        "window_over_T_allowance": window / ALLOWANCE["temperature"],
        "start1_T_offset_K": s1["T_K"] - t_sat,
        "start1_lnK_B": TH.lnk(1, s1["T_K"], P_R),
        "start1_row": row1,
        "start1_row_over_tau_eq": row1 / tau_eq,
        "allowance_over_kind_tolerance": {
            kind: ALLOWANCE[kind] / t5.TOL[kind] for kind in ALLOWANCE
        },
        "thm01_closure_K": thm01_closure,
        "net11_heater_bubble_excess_K": net11_bubble_excess,
        "net11_heater_regime": s4["regime"],
    }


# =============================================================================================
# 8. Claims: every statement the specification makes about its own numbers
# =============================================================================================


class Claims:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, detail: Any = "") -> None:
        self.results.append((name, bool(ok), str(detail)))

    @property
    def failed(self) -> list[tuple[str, bool, str]]:
        return [r for r in self.results if not r[1]]


def in_domain_with_stencil(t: Any, p: Any) -> bool:
    dt = STENCIL_STEPS * WITNESS_STEP * SCALE["temperature"]
    dp = STENCIL_STEPS * WITNESS_STEP * SCALE["pressure"]
    return bool(T_MIN + dt <= t <= T_MAX - dt and P_MIN + dp <= p <= P_MAX - dp)


def case_claims(c: Claims, name: str, case: Mapping[str, Any]) -> None:
    # Material balance: feeds (+ nu * extent) = products, per component.
    feeds = [f[0] if isinstance(f, tuple) else f for f in case["feeds"]]
    produced = [ZERO] * NC
    for nu, xi in case.get("reaction", []):
        for i in range(NC):
            produced[i] += nu[i] * xi
    for i in range(NC):
        lhs = sum((f["n"][i] for f in feeds), ZERO) + produced[i]
        rhs = sum((p[0]["n"][i] for p in case["products"]), ZERO)
        c.check(
            f"{name}.material_balance.{COMPONENTS[i]}",
            abs(lhs - rhs) <= mpf("1e-30"),
            abs(lhs - rhs),
        )
    # Energy envelope: external duties and work = H(products) - H(feeds), total-enthalpy form.
    h_feeds = ZERO
    for f in case["feeds"]:
        s, phase = f if isinstance(f, tuple) else (f, "L")
        h_feeds += t5.h_flow(s["n"], s["T"], s["P"], phase)
    h_prod = sum((t5.h_flow(p[0]["n"], p[0]["T"], p[0]["P"], p[1]) for p in case["products"]), ZERO)
    gap = case["external_heat"] - (h_prod - h_feeds)
    c.check(f"{name}.energy_envelope", abs(gap) <= mpf("1e-25"), gap)
    # Fixed-point diagnostics.
    for key, value in case.get("fixed_point", {}).items():
        c.check(f"{name}.fixed_point.{key}", abs(value) <= mpf("1e-25"), value)
    # Domain with the witness stencil; non-negative flows.
    for sid, s in case["streams"].items():
        c.check(
            f"{name}.{sid}.in_domain_with_stencil",
            in_domain_with_stencil(s["T"], s["P"]),
            (s["T"], s["P"]),
        )
        c.check(f"{name}.{sid}.flows_nonnegative", all(v >= 0 for v in s["n"]), s["n"])
    # Mixer outlets subcooled with margin (K02 mixer domain, R-007).
    for k, m in enumerate(case.get("mixers", [])):
        value = szk(m["n"], m["T"], m["P"])
        c.check(f"{name}.mixer{k}.subcooled", value <= 1 - SUBCOOL_MARGIN, value)
    # Lifted splits: two-phase with margin, or single-phase with margin from the boundary.
    for unit, split in case.get("lifted", {}).items():
        if split["regime"] == "TWO_PHASE":
            c.check(
                f"{name}.{unit}.two_phase_margin",
                PHASE_MARGIN <= split["beta"] <= 1 - PHASE_MARGIN,
                split["beta"],
            )
        elif split["regime"] == "LIQUID":
            c.check(
                f"{name}.{unit}.liquid_margin",
                split.get("szk", ZERO) <= 1 - PHASE_MARGIN,
                split.get("szk"),
            )
    # Declared-liquid ports: subcooled or saturated (R-007 admits saturation); declared-vapour
    # ports: superheated or saturated.
    for k, s in enumerate(case.get("declared_liquid", [])):
        if total(s["n"]) > 0:
            value = szk(s["n"], s["T"], s["P"])
            c.check(f"{name}.declared_liquid{k}", value <= 1 + mpf("1e-30"), value)
    for k, s in enumerate(case.get("declared_vapor", [])):
        if total(s["n"]) > 0:
            value = sz_over_k(s["n"], s["T"], s["P"])
            c.check(f"{name}.declared_vapor{k}", value <= 1 + mpf("1e-30"), value)
    # Exchangers: both terminal differences at least 1 K, heat flows hot to cold, no failure.
    for k, hx in enumerate(case.get("exchangers", [])):
        c.check(f"{name}.hx{k}.no_failure", not hx["failures"], hx["failures"])
        c.check(
            f"{name}.hx{k}.terminal",
            min(hx["hot_end_K"], hx["cold_end_K"]) >= TERMINAL_MARGIN_K,
            (hx["hot_end_K"], hx["cold_end_K"]),
        )


def run_claims() -> tuple[Claims, dict[str, Any]]:
    c = Claims()
    cases = {name: fn() for name, fn in NEW_CASES.items()}
    for name, case in cases.items():
        case_claims(c, name, case)
    # Case-specific registered facts (spec §4.3).
    c.check("THM-01.two_phase", cases["SYN-001-T06-THM01"]["signatures"]["U-FLASH"] == "TWO_PHASE")
    th01 = cases["SYN-001-T06-THM01"]["streams"]["S2"]["n"]
    no_poy = split_with_k(F_EQ, mpf(365), mpf(120000), lambda i, t, p: TH.k(i, t, P_R) * P_R / p)
    poy_effect = max(abs(no_poy["v"][i] - th01[i]) for i in range(NC))
    c.check(
        "THM-01.poynting_effect_exceeds_100_allowances",
        poy_effect >= 100 * ALLOWANCE["molar_flow"],
        poy_effect,
    )
    net02 = cases["SYN-001-T06-NET02"]
    c.check("NET-02.heater_two_phase", net02["signatures"]["U-HEAT"] == "TWO_PHASE")
    c.check(
        "NET-02.recycle_over_feed_at_least_10",
        total(net02["streams"]["S6"]["n"]) >= 10 * 3,
        total(net02["streams"]["S6"]["n"]),
    )
    tf_half = t5.bisect(
        lambda t: net02_parts(t, mpf(20000), mpf(358), mpf("0.5"))["residual"],
        mpf(345),
        mpf(420),
        200,
    )
    c.check(
        "NET-02.T_flash_depends_on_r",
        abs(net02["T_flash"] - tf_half) >= 1,
        (net02["T_flash"], tf_half),
    )
    net11 = cases["SYN-001-T06-NET11"]
    c.check(
        "NET-11.heater_outlet_liquid_with_margin",
        net11["high_pressure_liquid_szk"] <= 1 - PHASE_MARGIN,
        net11["high_pressure_liquid_szk"],
    )
    c.check("NET-11.heater_signature", net11["signatures"]["U-HEAT"] == "LIQUID")
    c.check(
        "NET-11.valve_and_flash_two_phase",
        net11["signatures"]["U-VLV"] == "TWO_PHASE" and net11["signatures"]["U-PHF"] == "TWO_PHASE",
    )
    sta02 = cases["SYN-001-T06-STA02"]
    c.check("STA-02.B_absent_everywhere", all(s["n"][1] == 0 for s in sta02["streams"].values()))
    c.check(
        "NET-03.every_lifted_two_phase",
        all(v == "TWO_PHASE" for v in cases["SYN-001-T06-NET03"]["signatures"].values()),
        cases["SYN-001-T06-NET03"]["signatures"],
    )
    c.check(
        "NET-10.both_flashes_two_phase",
        all(cases["SYN-001-T06-NET10"]["signatures"][u] == "TWO_PHASE" for u in ("U-FL1", "U-FL2")),
    )
    c.check(
        "NET-09.reactor_and_flash_two_phase",
        all(v == "TWO_PHASE" for v in cases["SYN-001-T06-NET09"]["signatures"].values()),
    )
    # Distinctness: no two new cases share their registered root on a common coordinate set.
    tflashes = [round(float(cases[k]["T_flash"]), 6) for k in cases if "T_flash" in cases[k]]
    c.check(
        "new_cases.flash_temperatures_pairwise_distinct",
        len(set(tflashes)) == len(tflashes),
        tflashes,
    )
    # THM-04 is ineligible: at 420 K and P_r every K_i > 1, so any nonzero liquid-labelled tear
    # stream is inadmissible (R-007) and the tear-path start space is the single point t = 0.
    kmin_420 = min(TH.k(i, mpf(420), P_R) for i in range(NC))
    c.check("THM-04.min_K_at_420K_above_1", kmin_420 > 1, kmin_420)
    # Reference fixtures.
    refs = ref_fixtures()
    c.check("REF-01.T_out_exactly_320", refs["REF-01"]["quantities"]["S3.T"] == 320)
    c.check(
        "REF-01.subcooled",
        refs["REF-01"]["mixer_szk"] <= 1 - SUBCOOL_MARGIN,
        refs["REF-01"]["mixer_szk"],
    )
    c.check(
        "REF-02.inlet_subcooled",
        refs["REF-02"]["inlet_szk"] <= 1 - SUBCOOL_MARGIN,
        refs["REF-02"]["inlet_szk"],
    )
    c.check("REF-03.two_phase", refs["REF-03"]["regime"] == "TWO_PHASE", refs["REF-03"]["beta"])
    c.check(
        "REF-05.inlet_liquid_in_both_K_forms",
        refs["REF-05"]["inlet_szk"] <= 1 - SUBCOOL_MARGIN
        and refs["REF-05"]["inlet_szk_no_poynting"] <= 1 - SUBCOOL_MARGIN,
        (refs["REF-05"]["inlet_szk"], refs["REF-05"]["inlet_szk_no_poynting"]),
    )
    c.check(
        "REF-06.work_exactly_32",
        abs(refs["REF-06"]["quantities"]["U-PUMP.W"] - 32) <= mpf("1e-35"),
        refs["REF-06"]["quantities"]["U-PUMP.W"],
    )
    c.check(
        "REF-06.T_out",
        abs(refs["REF-06"]["quantities"]["S2.T"] - (300 + mpf(8) / 300)) <= mpf("1e-35"),
    )
    c.check(
        "REF-07.duty_exactly_3600",
        abs(refs["REF-07"]["quantities"]["U-RX.Q"] - 3600) <= mpf("1e-30"),
        refs["REF-07"]["quantities"]["U-RX.Q"],
    )
    gas_datum = refs["REF-07"]["extent"] * sum((NU[i] * TH.b.L_VAP[i] for i in range(NC)), ZERO)
    c.check("REF-07.gas_datum_error_is_7500_W", abs(gas_datum - 7500) <= mpf("1e-30"), gas_datum)
    c.check(
        "REF-07.liquid",
        refs["REF-07"]["regime"] == "LIQUID" and refs["REF-07"]["outlet_szk"] <= 1 - SUBCOOL_MARGIN,
        refs["REF-07"]["outlet_szk"],
    )
    c.check(
        "REF-08.V_is_the_plan_value",
        abs(refs["REF-08"]["V"] - mpf("1.3608090692")) <= mpf("1e-10"),
        refs["REF-08"]["V"],
    )
    c.check(
        "REF-08.L_is_the_plan_value",
        abs(refs["REF-08"]["L"] - mpf("3.2783818616")) <= mpf("1e-10"),
        refs["REF-08"]["L"],
    )
    pcs = positive_controls(refs)
    c.check(
        "PC-1.effect_exceeds_100_tolerances",
        abs(pcs["PC-1"]["effect_W"]) >= 100 * pcs["PC-1"]["tolerance_W"],
        (pcs["PC-1"]["effect_W"], pcs["PC-1"]["tolerance_W"]),
    )
    c.check(
        "PC-2.effect_exceeds_100_tolerances",
        pcs["PC-2"]["worst_ratio"] >= 100,
        pcs["PC-2"]["worst_ratio"],
    )
    c.check("PC-2.two_phase", pcs["PC-2"]["regime"] == "TWO_PHASE")
    mapping = dwsim_mapping()
    c.check(
        "DWSIM.mapped_latent_equals_ours_at_every_P",
        mapping["max_latent_gap"] <= mpf("1e-30"),
        mapping["max_latent_gap"],
    )
    c.check(
        "DWSIM.unmapped_offset_is_minus_Pr_v",
        all(
            abs(o + P_R * V_LIQ[i]) <= mpf("1e-30")
            for i, o in enumerate(mapping["unmapped_latent_offset_J_per_mol"])
        ),
        mapping["unmapped_latent_offset_J_per_mol"],
    )
    lat = pcs["REF-05-latent-offset"]
    c.check(
        "REF-05.latent_offset_is_caught",
        abs(lat["effect_K"]) > lat["tolerance_K"],
        (lat["effect_K"], lat["tolerance_K"]),
    )
    # The comparison tolerance sits below every positive control and far above double roundoff.
    worst_rel_floor = mpf(2) ** -52 * 10
    c.check(
        "REF.tolerance_above_roundoff",
        REF_REL >= 10**4 * worst_rel_floor,
        REF_REL / worst_rel_floor,
    )
    # Draws: k53 in [0, 2^53); delta in [-0.2, 0.2); distinct keys give distinct words.
    ks = kats()
    c.check(
        "KAT.range",
        all(0 <= k["k53"] < 2**53 and -mpf("0.2") <= k["delta"] < mpf("0.2") for k in ks),
    )
    c.check("KAT.distinct", len({k["k53"] for k in ks}) == len(ks))
    # Gate arithmetic.
    c.check("gate.N", N_STARTS == 440, N_STARTS)
    c.check("gate.S_min", s_min() == 418, s_min())
    table = cp_table()
    c.check(
        "gate.cp_monotone", all(table[s] < table[s + 1] for s in range(N_STARTS - 30, N_STARTS))
    )
    c.check(
        "gate.cp_at_all_successes",
        abs(table[N_STARTS] - mpf("0.05") ** (mpf(1) / N_STARTS)) <= mpf("1e-30"),
        table[N_STARTS],
    )
    c.check("gate.cp_at_threshold_below_095", table[s_min()] < GATE_FRACTION, table[s_min()])
    # Spec §7.4 and ADR 0014 D3: gating on the bound instead would demand S >= 426 of 440.
    s_bound = min(k for k, v in table.items() if v >= GATE_FRACTION)
    c.check("gate.bound_gate_would_need_426", s_bound == 426, s_bound)
    # ADV-06 bands, on C1's registered root read from the T05 twin.
    c1 = t5.coupled_c1()
    min_flow = min(v for sid in ("S5", "S6") for v in c1["streams"][sid]["n"] if v > 0)
    bands = noise_bands(min_flow)
    c.check(
        "ADV-06.H.residual_noise_above_100_tau",
        bands["H"]["energy_row_noise_scaled_typical_min"] >= 100 * TAU_HAT_MIN,
        bands["H"],
    )
    c.check(
        "ADV-06.M.residual_noise_below_tau_by_10",
        bands["M"]["energy_row_noise_scaled_max"] <= TAU_HAT_MIN / 10,
        bands["M"],
    )
    # The witness takes the largest entry over every (row, column) stencil pair, so the scale that
    # decides it is the largest row's noise over the step; spec §4.8 bounds the chance that every
    # pair escapes (independent draws at the 2m stencil states of one row with m >= 10 columns).
    c.check(
        "ADV-06.M.witness_error_scale_above_tol_by_100",
        bands["M"]["witness_error_scaled_max"] >= 100 * WITNESS_TOL,
        bands["M"],
    )
    escape = (2 * WITNESS_TOL * WITNESS_STEP / bands["M"]["energy_row_noise_scaled_max"]) ** 10
    c.check("ADV-06.M.escape_probability_below_1e-20", escape <= mpf("1e-20"), escape)
    c.check(
        "ADV-06.L.witness_error_below_tol_by_100",
        bands["L"]["witness_error_scaled_max"] <= WITNESS_TOL / 100,
        bands["L"],
    )
    # Corpus counts.
    corpus = corpus_doc()
    ids = [r["id"] for r in corpus["cases"]]
    c.check("corpus.ids_unique", len(ids) == len(set(ids)))
    fixtures = [r["fixture"] for r in corpus["cases"]]
    c.check("corpus.fixtures_unique", len(fixtures) == len(set(fixtures)))
    c.check("corpus.at_least_30", corpus["counted"] >= 30, corpus["counted"])
    c.check(
        "corpus.eligible_matches_gate", corpus["eligible"] == ELIGIBLE_CASES, corpus["eligible"]
    )
    for cls, count in PLAN_IDS.items():
        present = {f"{cls}-{k:02d}" for k in range(1, count + 1)}
        c.check(f"corpus.plan_ids.{cls}", present <= set(ids), sorted(present - set(ids)))
    c.check(
        "corpus.eligible_are_success_kind",
        all(r["expected"] == "verified_at_reference" for r in corpus["cases"] if r["eligible"]),
    )
    # Amendment 1 (2026-09-26).
    c.check("corpus.counted_is_49", corpus["counted"] == 49, corpus["counted"])
    c.check(
        "corpus.denominator_is_30",
        corpus["in_success_denominator"] == SUCCESS_DENOMINATOR,
        corpus["in_success_denominator"],
    )
    by_id = {r["id"]: r for r in corpus["cases"]}
    c.check(
        "corpus.metamorphic_cases_ineligible_their_twins_eligible",
        all(
            not by_id[case]["eligible"]
            and by_id[case]["expected"] == "verified_at_reference"
            and by_id[twin]["eligible"]
            for case, twin in METAMORPHIC.items()
        ),
    )
    # Unit conversion (spec §8.5, A1): STA-03's converted values are SYN-001-nominal's, bit for bit.
    c.check("units.sta03_degC_is_nominal_exactly", degc_to_k(26.85) == 300.0, degc_to_k(26.85))
    c.check(
        "units.sta03_kgs_is_nominal_exactly",
        mass_to_molar(0.1, SYN001_MOLAR_MASS["A"]) == 1.0,
        mass_to_molar(0.1, SYN001_MOLAR_MASS["A"]),
    )
    c.check(
        "units.a02_degC_control_is_exact",
        degc_to_k(86.85) == 360.0 and degc_to_k(84.85) == 358.0,
        (degc_to_k(86.85), degc_to_k(84.85)),
    )
    unit_kats = unit_known_answers()
    c.check(
        "units.kats_pin_binary64_addition",
        any(k["decimal_sum_differs"] for k in unit_kats["degC"]),
    )
    c.check(
        "units.kats_pin_binary64_division",
        any(k["reciprocal_product_differs"] for k in unit_kats["mass_basis"]),
    )
    synthetic = [
        k["si_value"] for k in unit_kats["mass_basis"] if k["molar_mass_table"] == "synthetic"
    ]
    c.check(
        "units.synthetic_component_results_distinct",
        len(synthetic) == NC and len(set(synthetic)) == NC,
        synthetic,
    )
    c.check("units.syn001_masses_equal", len(set(SYN001_MOLAR_MASS.values())) == 1)
    c.check(
        "units.sta03_dropped_offset_leaves_domain",
        mpf("26.85") < T_MIN,
        (mpf("26.85"), T_MIN),
    )
    # A 273 K offset instead of 273.15 moves the heater duty by sum(n) c_p 0.15 K (the feed enters
    # the heater through the adiabatic mixer): caught with a factor >= 100 at the duty allowance.
    offset_effect = sum(F_EQ) * CP * mpf("0.15")
    c.check(
        "units.sta03_wrong_offset_caught",
        offset_effect >= 100 * ALLOWANCE["heat_rate"],
        offset_effect,
    )
    # Component order (spec §4.2, A1): every non-identity permutation, applied positionally, changes
    # C2's feed, stoichiometry and separator splits, so a positional mapping error moves the root.
    import itertools

    perms = [p for p in itertools.permutations(range(NC)) if p != tuple(range(NC))]
    c.check(
        "STA-04.every_permutation_changes_c2_inputs",
        len(perms) == 5
        and all(
            tuple(vec[p[i]] for i in range(NC)) != tuple(vec)
            for p in perms
            for vec in (t5.C2_FEED, NU, t5.C2_SPLIT)
        ),
    )
    k360 = [TH.k(i, mpf(360), P_R) for i in range(NC)]
    c.check(
        "STA-04.nominal_K_pairwise_distinct",
        min(abs(k360[i] - k360[j]) for i in range(NC) for j in range(i + 1, NC)) > mpf("0.1"),
        k360,
    )
    # Reference-tool settings (spec §9.3, A1; M6).
    c.check(
        "IDAES.constr_viol_tol_below_allowances_by_100",
        all(
            100 * IDAES_CONSTR_VIOL_TOL <= ALLOWANCE[k]
            for k in ("molar_flow", "pressure", "heat_rate")
        ),
    )
    c.check(
        "IDAES.constr_viol_tol_above_Pa_row_floor_by_30_ulps",
        IDAES_CONSTR_VIOL_TOL >= 30 * ULP_2E5_PA,
        IDAES_CONSTR_VIOL_TOL / ULP_2E5_PA,
    )
    c.check(
        "IDAES.old_1e-10_within_4_ulps_of_Pa_row",
        mpf("1e-10") <= 4 * ULP_2E5_PA,
        mpf("1e-10") / ULP_2E5_PA,
    )
    c.check(
        "PC-2.feed_is_flash_pressure_and_equimolar",
        REFERENCE_TOOL_SETTINGS["PC-2"]["feed"]["P_Pa"] == "1.5e5"
        and pcs["PC-2"]["P_Pa"] == mpf("1.5e5")
        and tuple(mpf(v) for v in REFERENCE_TOOL_SETTINGS["PC-2"]["feed"]["n_mol_per_s"]) == F_EQ,
    )

    # ---- Amendment 2 (2026-09-26) ----------------------------------------------------------
    # §6.3: the draw's binary64 arithmetic.
    c.check(
        "draw.u_hex_is_k_times_2^-53_and_its_17_digits_round_trip",
        all(
            float.fromhex(k["u_hex"]) == k["k53"] * 2.0**-53
            and float(s(k["u"], 17)) == float.fromhex(k["u_hex"])
            for k in ks
        ),
    )
    c.check(
        "draw.delta_hex_is_w_over_5_one_rounding",
        all(delta_generator(k["k53"]) == float.fromhex(k["delta_hex"]) for k in ks),
    )
    c.check(
        "draw.delta_hex_is_nearest_to_exact",
        all(
            nearest_binary64(
                float.fromhex(k["delta_hex"]), Fraction(2 * k["k53"] - 2**53, 5 * 2**53)
            )
            for k in ks
        ),
    )
    c.check(
        "draw.kats_refuse_the_literal_0.2_product",
        sum(k["literal_0p2_product_differs"] for k in ks) >= 1,
        [k["key"] for k in ks if k["literal_0p2_product_differs"]],
    )
    c.check(
        "draw.decimal_delta_is_not_a_binary64_expectation",
        sum(k["decimal17_differs"] for k in ks) >= 1,
        [k["key"] for k in ks if k["decimal17_differs"]],
    )
    # ADR 0016: unit-conversion-v2.
    units2 = unit_v2_known_answers()
    c.check(
        "units_v2.psi_is_the_1959_definition",
        PSI_PA == Fraction(44482216152605, 6451600000)
        and abs(PSI_PA - Fraction("6894.757293168361")) < Fraction(1, 10**11),
        float(PSI_PA),
    )
    c.check(
        "units_v2.every_row_known_answer_is_nearest",
        all(
            nearest_binary64(
                float.fromhex(r["si_value_hex"]),
                next(
                    (
                        (a / decimal_of(SYN001_MOLAR_MASS[r["component"]]) if cls == "mass" else a)
                        * decimal_of(float(r["value"]))
                        + b
                    )
                    for kind, unit, _rule, a, b, _kinds, cls in V2_ROWS
                    if kind == r["required_kind"] and unit == r["unit"]
                ),
            )
            for r in units2["rows"]
        ),
    )
    c.check(
        "units_v2.every_naive_chain_is_refused_by_a_known_answer",
        all(units2["discriminated"][f"{kind}:{unit}"] for kind, unit in NAIVE_CHAINS),
        [
            f"{kind}:{unit}"
            for kind, unit in NAIVE_CHAINS
            if not units2["discriminated"][f"{kind}:{unit}"]
        ],
    )
    c.check(
        "units_v2.metamorphic_pairs_bind_to_the_registered_value",
        all(p["binds_to_registered_value"] for p in units2["metamorphic_pairs"]),
        [
            (p["case"], p["input"], p["value"], p["unit"], p["si_value"])
            for p in units2["metamorphic_pairs"]
            if not p["binds_to_registered_value"]
        ],
    )
    c.check(
        "units_v2.metamorphic_pairs_are_not_the_identity",
        all(
            float(p["value"]) != float(p["si_value"]) and float(p["si_value"]) != 0.0
            for p in units2["metamorphic_pairs"]
        ),
    )
    c.check(
        "units_v2.the_binary_reading_would_break_a_pair",
        any(p["binary_reading_value"] != p["si_value"] for p in units2["metamorphic_pairs"]),
        [
            (p["input"], p["value"], p["unit"], p["binary_reading_value"])
            for p in units2["metamorphic_pairs"]
            if p["binary_reading_value"] != p["si_value"]
        ],
    )
    c.check(
        "units_v2.unit_invariance",
        all(g["all_equal"] for g in units2["invariance_groups"]),
        [g["inputs"] for g in units2["invariance_groups"] if not g["all_equal"]],
    )
    c.check(
        "units_v2.synthetic_masses_separate_components",
        len(set(units2["synthetic_mass_kg_per_h_0p3"])) == NC,
    )
    c.check(
        "units_v2.refusals_as_registered",
        all(r["refused_as_registered"] for r in units2["refusals"]),
        [
            (r["value"], r["unit"], r["reason"])
            for r in units2["refusals"]
            if not r["refused_as_registered"]
        ],
    )
    c.check(
        "units_v2.sta03_and_a02_control_unchanged_from_v1",
        all(
            e["v1_hex"] == e["v2_hex"]
            for e in units2["v1_known_answers_under_v2"]
            if (e["unit"], e["value"])
            in {("degC", "26.85"), ("degC", "86.85"), ("degC", "84.85"), ("kg/s", "0.1")}
        ),
    )
    c.check(
        "units_v2.reverses_v1_where_v1_was_not_unit_invariant",
        any(e["v1_hex"] != e["v2_hex"] for e in units2["v1_known_answers_under_v2"]),
        [
            (e["value"], e["unit"])
            for e in units2["v1_known_answers_under_v2"]
            if e["v1_hex"] != e["v2_hex"]
        ],
    )
    c.check(
        "units_v2.minus_zero_converts_to_plus_zero",
        convert_v2(-0.0, "kg/s", "molar_flow", "molar_flow", "state.n", "A", SYN001_MOLAR_MASS)[
            0
        ].hex()
        == "0x0.0p+0",
    )
    c.check(
        "units_v2.degF_agrees_with_degC_at_exact_celsius",
        all(
            convert_v2(f, "degF", "temperature", "temperature", "state.T")[0]
            == convert_v2(cc, "degC", "temperature", "temperature", "state.T")[0]
            for f, cc in (
                (32.0, 0.0),
                (212.0, 100.0),
                (-40.0, -40.0),
                (50.0, 10.0),
                (98.6, 37.0),
                (80.33, 26.85),
            )
        ),
    )
    # ADR 0017 (F6): the registered states are saturated to roundoff, and the fixed provider's
    # single-phase answer is within 1e-14 of the exact vapour fraction.
    f6 = f6_facts()
    c.check(
        "F6.states_in_domain_and_every_component_flows",
        all(
            T_MIN <= fact["T_K"] <= T_MAX
            and P_MIN <= fact["P_Pa"] <= P_MAX
            and fact["all_components_flow"]
            for fact in f6.values()
        ),
    )
    c.check(
        "F6.liquid_state_is_at_its_bubble_point",
        abs(f6["F6-liquid"]["T_minus_bubble_K"]) <= F6_SATURATION_BOUND_K
        and abs(f6["F6-liquid"]["f0"]) <= mpf("1e-15")
        and f6["F6-liquid"]["f1"] < -mpf("0.1"),
        (f6["F6-liquid"]["T_minus_bubble_K"], f6["F6-liquid"]["f0"]),
    )
    c.check(
        "F6.vapour_state_is_at_its_dew_point",
        abs(f6["F6-vapour"]["T_minus_dew_K"]) <= F6_SATURATION_BOUND_K
        and abs(f6["F6-vapour"]["f1"]) <= mpf("1e-15")
        and f6["F6-vapour"]["f0"] > mpf("0.1"),
        (f6["F6-vapour"]["T_minus_dew_K"], f6["F6-vapour"]["f1"]),
    )
    c.check(
        "F6.fixed_answer_within_1e-14_of_exact_beta",
        all(abs(fact["beta_exact"] - fact["fixed_beta"]) <= F6_BETA_BOUND for fact in f6.values()),
        {name: fact["beta_exact"] for name, fact in f6.items()},
    )
    c.check(
        "F6.a_wrong_phase_is_caught",
        all(
            abs(fact["beta_exact"] - (1 - fact["fixed_beta"])) >= mpf("0.99")
            for fact in f6.values()
        ),
    )
    # Spec §9.3 (A2): IDAES SmoothVLE.
    t_probe = mpf(360)
    c.check(
        "IDAES.smooth_vle_shift_at_a_bubble_point_is_eps1_over_2",
        abs(smooth_max(t_probe, t_probe, SMOOTH_VLE_DEFAULT_EPS[0]) - t_probe - mpf("0.005"))
        <= mpf("1e-30"),
    )
    c.check(
        "IDAES.default_smoothing_is_500_temperature_allowances",
        sum(SMOOTH_VLE_DEFAULT_EPS) / 2 >= 500 * ALLOWANCE["temperature"],
        sum(SMOOTH_VLE_DEFAULT_EPS) / 2,
    )
    c.check(
        "IDAES.registered_smoothing_worst_shift_below_half_the_self_check_bound",
        sum(SMOOTH_VLE_EPS) / 2 <= SMOOTH_VLE_SHIFT_BOUND / 2
        and SMOOTH_VLE_SHIFT_BOUND == ALLOWANCE["temperature"] / 100
        and tuple(
            mpf(REFERENCE_TOOL_SETTINGS["IDAES"]["smooth_vle"][k]) for k in ("eps_1_K", "eps_2_K")
        )
        == SMOOTH_VLE_EPS,
        (sum(SMOOTH_VLE_EPS) / 2, SMOOTH_VLE_SHIFT_BOUND),
    )
    c.check(
        "IDAES.registered_smoothing_resolved_in_binary64_at_440_K",
        min(SMOOTH_VLE_EPS) >= 10**4 * mpf(2) ** -44,
        min(SMOOTH_VLE_EPS) / mpf(2) ** -44,
    )
    # Spec Amendment 4 (§7.1 (A4), §8.8 (A4), finding 19).
    a4 = a4_facts()
    c.check(
        "A4.THM-09.root_is_T05b_SC-3",
        abs(a4["T_sat_K"] - 360) <= mpf("1e-30")
        and abs(a4["valve_vapor_B"] - mpf("0.0672")) <= mpf("1e-30")
        and abs(a4["vapor_B"] - mpf("0.033866666666666666667")) <= mpf("1e-20"),
        (a4["T_sat_K"], a4["valve_vapor_B"], a4["vapor_B"]),
    )
    c.check(
        "A4.THM-09.row_window_exceeds_the_S3_temperature_allowance_4x",
        a4["window_over_T_allowance"] >= 4,
        a4["window_over_T_allowance"],
    )
    c.check(
        "A4.THM-09.start1_row_reproduces_the_measured_1.863e-8",
        abs(a4["start1_row"] - A4_THM09_START1["measured_row"]) <= mpf("5e-12"),
        a4["start1_row"],
    )
    c.check(
        "A4.THM-09.start1_is_inside_the_row_window_and_outside_the_allowance",
        ALLOWANCE["temperature"] < abs(a4["start1_T_offset_K"]) < a4["row_window_K"]
        and a4["start1_row_over_tau_eq"] < 1,
        (a4["start1_T_offset_K"], a4["start1_row_over_tau_eq"]),
    )
    c.check(
        "A4.refinement_threshold_leaves_a_margin_of_at_least_9.9_below_every_allowance",
        all(ratio >= mpf("9.9") for ratio in a4["allowance_over_kind_tolerance"].values()),
        a4["allowance_over_kind_tolerance"],
    )
    c.check(
        "A4.closure_vanishes_at_a_registered_equilibrium_split",
        a4["thm01_closure_K"] <= mpf("1e-25"),
        a4["thm01_closure_K"],
    )
    c.check(
        "A4.closure_catches_a_vanishing_vapour_at_NET-11s_liquid_heater_outlet",
        a4["net11_heater_regime"] == "LIQUID"
        and a4["net11_heater_bubble_excess_K"] >= 10**6 * t5.TOL["temperature"],
        a4["net11_heater_bubble_excess_K"],
    )
    return c, {
        "cases": cases,
        "refs": refs,
        "controls": pcs,
        "kats": ks,
        "cp": table,
        "bands": bands,
        "corpus": corpus,
        "mapping": mapping,
        "units": unit_kats,
        "units_v2": units2,
        "f6": f6,
        "a4": a4,
    }


# =============================================================================================
# 9. Emission
# =============================================================================================


def s(value: Any, digits: int = 20) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    return mp.nstr(mpf(value), digits, strip_zeros=False, min_fixed=-30, max_fixed=30)


def doc_stream(stream: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "n_mol_per_s": [s(v) for v in stream["n"]],
        "T_K": s(stream["T"]),
        "P_Pa": s(stream["P"]),
    }
    if "regime" in stream:
        out["regime"] = stream["regime"]
        out["beta"] = s(stream["beta"]) if stream["beta"] is not None else None
        out["vapor_mol_per_s"] = [s(v) for v in stream["v"]]
        out["liquid_mol_per_s"] = [s(v) for v in stream["l"]]
    return out


def build() -> dict[str, Any]:
    claims, data = run_claims()
    if claims.failed:
        raise SystemExit("claims failed:\n" + "\n".join(f"  {n}: {d}" for n, _, d in claims.failed))
    cases_out = {}
    for name, case in data["cases"].items():
        cases_out[name] = {
            "streams": {sid: doc_stream(st_) for sid, st_ in case["streams"].items()},
            "duty_W": {k: s(v) for k, v in case["duty"].items()},
            "work_W": {k: s(v) for k, v in case.get("work", {}).items()},
            "extent_mol_per_s": {k: s(v) for k, v in case.get("extent", {}).items()},
            "signatures": dict(case["signatures"]),
        }
    refs_out = {
        fid: {
            "quantities": {
                q: {
                    "value": s(v),
                    "kind": kind_of(q),
                    "tolerance": s(comparison_tolerance(q, v), 6),
                }
                for q, v in fx["quantities"].items()
            }
        }
        for fid, fx in data["refs"].items()
    }
    pcs = data["controls"]
    controls_out = {
        "PC-1": {
            "quantity": pcs["PC-1"]["quantity"],
            "effect_W": s(pcs["PC-1"]["effect_W"]),
            "tolerance_W": s(pcs["PC-1"]["tolerance_W"], 6),
        },
        "PC-2": {
            "T_K": s(pcs["PC-2"]["T_K"]),
            "P_Pa": s(pcs["PC-2"]["P_Pa"]),
            "ours_vapor_mol_per_s": [s(v) for v in pcs["PC-2"]["ours_vapor"]],
            "no_poynting_vapor_mol_per_s": [s(v) for v in pcs["PC-2"]["no_poynting_vapor"]],
            "worst_quantity": pcs["PC-2"]["worst_quantity"],
            "worst_effect_over_tolerance": s(pcs["PC-2"]["worst_ratio"], 6),
        },
        "REF-05-latent-offset": {
            "effect_K": s(pcs["REF-05-latent-offset"]["effect_K"], 8),
            "tolerance_K": s(pcs["REF-05-latent-offset"]["tolerance_K"], 6),
        },
    }
    kat_out = [
        {
            "key": k["key"],
            "k53": k["k53"],
            "u": s(k["u"], 17),
            "delta": s(k["delta"], 17),
            # Amendment 2: the bit patterns A21 compares; `delta` above is informational.
            "u_hex": k["u_hex"],
            "delta_hex": k["delta_hex"],
            "literal_0p2_product_differs": k["literal_0p2_product_differs"],
            "decimal17_differs": k["decimal17_differs"],
        }
        for k in data["kats"]
    ]
    f6_out = {
        name: {
            "n_hex": list(F6_STATES[name]["n_hex"]),
            "T_hex": F6_STATES[name]["T_hex"],
            "P_hex": F6_STATES[name]["P_hex"],
            "fixed_signature": F6_STATES[name]["fixed_signature"],
            "fixed_vapor_fraction": s(fact["fixed_beta"], 1),
            "rachford_rice_f0": s(fact["f0"], 6),
            "rachford_rice_f1": s(fact["f1"], 6),
            "beta_exact": s(fact["beta_exact"], 20),
            "T_minus_bubble_K": s(fact["T_minus_bubble_K"], 6),
            "T_minus_dew_K": s(fact["T_minus_dew_K"], 6),
            "beta_bound": s(F6_BETA_BOUND, 1),
        }
        for name, fact in data["f6"].items()
    }
    gate_out = {
        "eligible_cases": ELIGIBLE_CASES,
        "starts_per_case": STARTS_PER_CASE,
        "N": N_STARTS,
        "fraction": s(GATE_FRACTION, 3),
        "S_min": s_min(),
        "clopper_pearson_one_sided_95_lower": {str(k): s(v, 12) for k, v in data["cp"].items()},
    }
    bands_out = {lvl: {k: s(v, 6) for k, v in b.items()} for lvl, b in data["bands"].items()}
    a4 = data["a4"]
    return {
        "schema_version": 1,
        "generator": "docs/derivations/scripts/t06_reference.py",
        "specification": "docs/derivations/T06-corpus-spec.md",
        "precision": "mpmath 40 significant digits, written to 20",
        "independence": (
            "imports t05_reference (the T05 twin) only; nothing from process_runtime or benchmarks"
        ),
        "closed_form": {
            "corpus_cases": cases_out,
            "reference_fixtures": refs_out,
            "positive_controls": controls_out,
            "draw_known_answers": kat_out,
            "gate": gate_out,
            "adv06_noise_bands": bands_out,
            "dwsim_input_mapping": {
                "dH_vap_J_per_mol": [s(v) for v in data["mapping"]["dH_vap_J_per_mol"]],
                "dH_f_ig_J_per_mol": [s(v) for v in data["mapping"]["dH_f_ig_J_per_mol"]],
                "unmapped_latent_offset_J_per_mol": [
                    s(v) for v in data["mapping"]["unmapped_latent_offset_J_per_mol"]
                ],
            },
            # Amendment 1 (2026-09-26).
            "unit_conversion_v1": {
                "id": UNIT_CONVERSION_ID,
                "authority": "ADR 0001 D1.3-D1.4; T06 spec §8.5 (amendment 1)",
                "operation": "one IEEE-754 binary64 operation on binary64 operands",
                "rules": [
                    {
                        "rule": "degC_to_K",
                        "required_kind": "temperature",
                        "declared_kinds": ["temperature"],
                        "unit": "degC",
                        "si": "value + 273.15",
                    },
                    {
                        "rule": "mass_to_molar",
                        "required_kind": "molar_flow",
                        "declared_kinds": ["molar_flow", "mass_flow"],
                        "unit": "kg/s",
                        "si": "value / M_c (the target component's molecular weight, kg/mol)",
                    },
                ],
                "syn001_molar_mass_kg_per_mol": dict(SYN001_MOLAR_MASS),
                "synthetic_molar_mass_kg_per_mol": dict(SYNTHETIC_MOLAR_MASS),
                "known_answers": data["units"],
            },
            "reference_tool_settings": REFERENCE_TOOL_SETTINGS,
            "metamorphic_restatements": dict(METAMORPHIC),
            # Amendment 2 (2026-09-26).
            "unit_conversion_v2": {
                "id": UNIT_CONVERSION_V2_ID,
                "authority": "ADR 0016; T06 spec §8.5 (amendment 2)",
                "operation": (
                    "SI = RN(a * D(v) + b): D(v) the shortest decimal that rounds to v (repr), "
                    "a and b exact, one round-to-nearest-even to binary64; a zero result is +0.0"
                ),
                "rows": [
                    {
                        "required_kind": kind,
                        "unit": unit,
                        "rule": rule,
                        "a": str(a),
                        "b": str(b),
                        "declared_kinds": list(kinds),
                        "target_class": cls,
                    }
                    for kind, unit, rule, a, b, kinds, cls in V2_ROWS
                ],
                "fraction_parameters": list(FRACTION_PARAMETERS),
                "psi_Pa_exact": str(PSI_PA),
                "known_answers": data["units_v2"],
            },
            "f6_states": f6_out,
            "smooth_vle": {
                "default_eps_K": [s(e, 3) for e in SMOOTH_VLE_DEFAULT_EPS],
                "registered_eps_K": [s(e, 3) for e in SMOOTH_VLE_EPS],
                "self_check_bound_K": s(SMOOTH_VLE_SHIFT_BOUND, 3),
            },
            # Amendment 4 (2026-09-26): THM-09's row window and the saturation closure's anchors.
            "amendment_4": {
                "thm09_row_window": {
                    "T_sat_K": s(a4["T_sat_K"]),
                    "vapor_B_mol_per_s": s(a4["vapor_B"]),
                    "liquid_B_mol_per_s": s(a4["liquid_B"]),
                    "VL_mol2_per_s2": s(a4["VL"]),
                    "dlnK_B_dT_per_K": s(a4["dlnK_B_dT"]),
                    "tau_eq_mol2_per_s2": s(a4["tau_eq"], 6),
                    "row_window_K": s(a4["row_window_K"], 8),
                    "window_over_T_allowance": s(a4["window_over_T_allowance"], 6),
                    "run1_start1_T_offset_K": s(a4["start1_T_offset_K"], 8),
                    "run1_start1_lnK_B": s(a4["start1_lnK_B"], 8),
                    "run1_start1_row": s(a4["start1_row"], 8),
                    "run1_start1_row_over_tau_eq": s(a4["start1_row_over_tau_eq"], 6),
                },
                "allowance_over_kind_tolerance": {
                    k: s(v, 6) for k, v in a4["allowance_over_kind_tolerance"].items()
                },
                "saturation_closure": {
                    "THM-01_registered_split_K": s(a4["thm01_closure_K"], 3),
                    "NET-11_heater_outlet_bubble_excess_K": s(
                        a4["net11_heater_bubble_excess_K"], 8
                    ),
                },
            },
        },
        "corpus": data["corpus"],
        "generator_claims": {
            "count": len(claims.results),
            "all_pass": True,
            "names": [n for n, _, _ in claims.results],
        },
    }


def dump(document: Mapping[str, Any]) -> str:
    return yaml.safe_dump(document, sort_keys=False, width=100, allow_unicode=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="re-derive every claim")
    parser.add_argument("--emit", metavar="PATH", help="write the reference YAML")
    args = parser.parse_args(argv)
    if not args.check and not args.emit:
        parser.error("choose --check and/or --emit PATH")
    if args.check:
        claims, _ = run_claims()
        for name, ok, detail in claims.results:
            if not ok:
                print(f"FAIL {name}: {detail}")
        print(f"{len(claims.results) - len(claims.failed)} of {len(claims.results)} claims pass")
        if claims.failed:
            return 1
    if args.emit:
        text = dump(build())
        path = Path(args.emit)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = text.encode("utf-8")  # A1: explicit, so the bytes never depend on the locale
        path.write_bytes(data)
        print(f"wrote {path} ({len(data)} bytes, sha256 {hashlib.sha256(data).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
