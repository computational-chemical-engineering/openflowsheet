"""Fable's verification of the Opus oracle against plan §3 (run from repo root, in .venv).

Checks (plan §8.1 day 2, Fable column): K-values at 360 K/P_r; r = 0.5 oracle values;
phase state of every registered variant; recycle invariance; energy closure. Independent of
Opus's tests: expectations are typed here from plan §3 and from Fable's mpmath derivation.
"""

from __future__ import annotations

import math
import sys

import yaml

from benchmarks.syn001 import oracle as o

PLAN_K360 = (2.8406442066, 1.0, 0.3105797512)
PLAN_NOMINAL = {"q": 0.4150855900, "L": 3.2783818616, "V": 1.3608090692}
PLAN_X = (0.1816607866, 0.3333333333, 0.4850058800)
PLAN_L_BY_R = {0.0: 1.639, 0.5: 3.278, 0.95: 32.78}
PLAN_SUMZK_350 = {0.0: 1.070, 0.5: 0.962, 0.95: 0.792}
FABLE_TOTAL_DUTY_360 = 56338.0694467435
FABLE_QH_095 = -16144.6276847601
EXPECTED_STATES = {
    "SYN-001-nominal": ("TWO_PHASE", "LIQUID", "LIQUID", "VAPOR", "LIQUID", "LIQUID"),
    "SYN-001-once-through": ("TWO_PHASE", "ZERO_FLOW", "LIQUID", "VAPOR", "LIQUID", "TWO_PHASE"),
    "SYN-001-high-recycle": ("TWO_PHASE", "LIQUID", "LIQUID", "VAPOR", "LIQUID", "LIQUID"),
    "SYN-001-all-liquid-310K": ("LIQUID", "LIQUID", "LIQUID", "ZERO_FLOW", "LIQUID", "TWO_PHASE"),
    "SYN-001-all-vapor-420K": ("VAPOR", "ZERO_FLOW", "ZERO_FLOW", "VAPOR", "LIQUID", "TWO_PHASE"),
}
VARIANTS = {
    "SYN-001-nominal": (0.5, 360.0),
    "SYN-001-once-through": (0.0, 360.0),
    "SYN-001-high-recycle": (0.95, 360.0),
    "SYN-001-all-liquid-310K": (0.5, 310.0),
    "SYN-001-all-vapor-420K": (0.5, 420.0),
}

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


k = o.k_values(360.0, 100_000.0)
for i in range(3):
    check(
        abs(k[i] - PLAN_K360[i]) < 5e-11,
        f"K_{'ABC'[i]}(360 K, P_r) = {k[i]!r} vs plan {PLAN_K360[i]}",
    )

F = (1.0, 1.0, 1.0)
nom = o.recycle_oracle(F, 0.5, 360.0, case_id="SYN-001-nominal")
L = nom.recycle[0] / nom.flash.x[0] / 0.5 if nom.flash.x else float("nan")
V = nom.flash.V
q = nom.q
check(
    q is not None and abs(q - PLAN_NOMINAL["q"]) < 5e-11, f"q = {q!r} vs plan {PLAN_NOMINAL['q']}"
)
check(abs(V - PLAN_NOMINAL["V"]) < 5e-11, f"V = {V!r} vs plan {PLAN_NOMINAL['V']}")
Ltot = sum(nom.recycle) + sum(nom.purge)
check(abs(Ltot - PLAN_NOMINAL["L"]) < 5e-11, f"L = {Ltot!r} vs plan {PLAN_NOMINAL['L']}")
assert nom.flash.x is not None
for i in range(3):
    check(
        abs(nom.flash.x[i] - PLAN_X[i]) < 5e-11,
        f"x_{'ABC'[i]} = {nom.flash.x[i]!r} vs plan {PLAN_X[i]}",
    )
check(
    abs(nom.Q_heater + nom.Q_flash - FABLE_TOTAL_DUTY_360) < 1e-6,
    f"Q_h + Q_f = {nom.Q_heater + nom.Q_flash!r} vs Fable 56338.0694467435 W",
)
check(abs(nom.energy_residual) < 1e-9, f"energy residual {nom.energy_residual!r}")
check(
    max(abs(b) for b in nom.balance_residual) < 1e-14, f"balance residual {nom.balance_residual!r}"
)

ref = yaml.safe_load(open("benchmarks/syn001/reference_values.yaml", encoding="utf-8"))
refv = {v["case_id"]: v for v in ref["variants"]}
results = {}
for cid, (r, tf) in VARIANTS.items():
    res = o.recycle_oracle(F, r, tf, case_id=cid)
    results[cid] = res
    got = (
        res.flash.state,
        res.recycle_state,
        res.purge_state,
        res.vapor_product_state,
        res.mixer_outlet_state,
        res.heater_outlet.state,
    )
    check(
        got == EXPECTED_STATES[cid],
        f"{cid} states (flash, recycle, purge, vapor, mixer, heater) = {got}",
    )
    rv = refv[cid]
    rstates = (
        rv["flash_phase_state"],
        rv["recycle_phase_signature"],
        rv["purge_phase_signature"],
        rv["vapor_product_phase_signature"],
        rv["mixer_outlet_state"],
        rv["heater_outlet_state"],
    )
    check(
        rstates == EXPECTED_STATES[cid],
        f"{cid} reference_values.yaml states agree with plan-derived expectation",
    )
    for name, val in (
        ("Q_heater_W", res.Q_heater),
        ("Q_flash_W", res.Q_flash),
        ("T_mix_K", res.T_mix),
    ):
        exp = float(rv[name])
        check(
            math.isclose(val, exp, rel_tol=1e-13, abs_tol=1e-9),
            f"{cid} {name} = {val!r} vs ref {exp!r}",
        )
    if tf == 360.0:
        Lr = sum(res.recycle) + sum(res.purge)
        check(
            abs(Lr - PLAN_L_BY_R[r]) <= 0.5 * 10 ** (-3 if r < 0.95 else -2),
            f"{cid} L = {Lr:.4f} vs plan {PLAN_L_BY_R[r]} (plan rounding window)",
        )
        szk = res.heater_outlet.sum_zK
        check(
            abs(szk - PLAN_SUMZK_350[r]) < 5e-4,
            f"{cid} sum zK(350 K) of mixed feed = {szk:.4f} vs plan {PLAN_SUMZK_350[r]}",
        )
        check(
            abs(res.Q_heater + res.Q_flash - FABLE_TOTAL_DUTY_360) < 1e-6,
            f"{cid} total duty r-invariant",
        )
    for stream, name in (
        (res.recycle, "recycle"),
        (res.purge, "purge"),
        (res.vapor_product, "vapor"),
    ):
        if sum(stream) == 0.0:
            check(all(c == 0.0 for c in stream), f"{cid} {name} zero-flow stream is exactly zero")

hr = results["SYN-001-high-recycle"]
check(
    hr.Q_heater < 0 and abs(hr.Q_heater - FABLE_QH_095) < 1e-6,
    f"r=0.95 Q_heater = {hr.Q_heater!r} (negative, Fable −16144.6276847601)",
)
al = results["SYN-001-all-liquid-310K"]
check(abs(al.flash.sum_zK - 0.328) < 5e-4, f"310 K sum zK = {al.flash.sum_zK:.4f} vs plan 0.328")
av = results["SYN-001-all-vapor-420K"]
check(
    abs(av.flash.sum_z_over_K - 0.317) < 5e-4,
    f"420 K sum z/K = {av.flash.sum_z_over_K:.4f} vs plan 0.317",
)
# recycle invariance
n0, n5, n95 = (
    results[c] for c in ("SYN-001-once-through", "SYN-001-nominal", "SYN-001-high-recycle")
)
for a, b in ((n0, n5), (n5, n95)):
    check(
        all(
            math.isclose(p, q_, rel_tol=1e-13)
            for p, q_ in zip(a.vapor_product, b.vapor_product, strict=True)
        ),
        "recycle invariance: vapor product identical across r",
    )
    assert a.flash.x and b.flash.x
    check(
        all(math.isclose(p, q_, rel_tol=1e-13) for p, q_ in zip(a.flash.x, b.flash.x, strict=True)),
        "recycle invariance: x identical across r",
    )
# linear recycle
check(o.linear_recycle((1.0, 1.0, 1.0), 0.5) == (2.0, 2.0, 2.0), "linear recycle r=0.5")
check(
    o.linear_recycle((1.0, 1.0, 1.0), 0.95) == (20.0, 20.0, 20.0)
    or all(abs(t - 20) < 1e-13 for t in o.linear_recycle((1.0, 1.0, 1.0), 0.95)),
    "linear recycle r=0.95",
)
# zero feed and zero component
zf = o.tp_flash((0.0, 0.0, 0.0), 360.0, 100_000.0)
check(
    zf.state == "ZERO_FLOW" and zf.x is None and zf.y is None,
    "zero feed -> ZERO_FLOW, undefined composition",
)
zc = o.tp_flash((1.0, 0.0, 1.0), 360.0, 100_000.0)
check(
    zc.state == "TWO_PHASE"
    and zc.x is not None
    and zc.y is not None
    and zc.x[1] == 0.0
    and zc.y[1] == 0.0,
    "zero component stays exactly zero in both phases",
)
try:
    o.k_values(279.999, 100_000.0)
    check(False, "domain error raised below 280 K")
except o.DomainError:
    check(True, "domain error raised below 280 K")

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
