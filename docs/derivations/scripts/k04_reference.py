"""Fable's closed-form reference generator for the K04 certificate specification.

Everything here follows from the plan §3.1 definitions and the SYN-001 derivation (§2, §4.1,
§5.1, §6) alone, evaluated with mpmath at 40 significant digits, plus exact rational arithmetic
for the constructed regularity matrices. It imports nothing from ``process_runtime`` or
``benchmarks``: the numbers it emits are the *expectations* the K04 verifier is judged against,
so they must not come from the verifier, the solver or the oracle. It *reads* the P01 reference
file once, in ``--check``, to prove that two independent derivations of the certified quantities
agree; it never copies a number from it.

What it produces (``docs/derivations/K04-certificate-spec.md`` §6, §9, §13):

* the certified quantities of every registered variant — product and purge flows, both duties,
  the mixer temperature, the heater-outlet split — as closed forms, cross-checked against the
  P01 20-digit reference in ``--check``;
* the registered injections with their closed-form row shifts, each with a twin state just
  below the threshold, so that every tolerance is shown to bite on one side and not the other;
* the closed forms of the regularity fixtures: the unit-diagonal triangular matrices with
  ``rcond_1 = 1/(n 2^(n-1))`` exactly and their singular-value bounds, and ``x^2 = 0`` under the
  K03 Newton;
* the declared numerical policy (ADR 0007 D2) and the per-kind check tolerances as data;
* the measured floors, labelled *measured*, that the tolerance arguments cite.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/k04_reference.py --check
    python docs/derivations/scripts/k04_reference.py --emit benchmarks/k04/reference_values.yaml

``--check`` re-derives every identity the specification claims about its own numbers and refuses
to emit when one stops holding (K04-certificate-spec §14.2).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml
from mpmath import mp, mpf

mp.dps = 40

R_GAS = mpf("8.31446261815324")
T_REF = mpf(300)
P_REF = mpf(100000)
CP = mpf(100)
T_BOIL = (mpf(320), mpf(360), mpf(400))
L_VAP = (mpf(25000), mpf(30000), mpf(35000))
V_LIQ = (mpf("0.0001"),) * 3
NAMES = ("A", "B", "C")
FRESH = (mpf(1), mpf(1), mpf(1))
T_FEED = mpf(300)
T_HEATER = mpf(350)
Vec = tuple[Any, ...]

#: ADR 0001 D6, registered for SYN-001 only, as (absolute, relative, scale).
TOLERANCES = {
    "molar_flow": (mpf("1e-9"), mpf("1e-8"), mpf(3)),
    "heat_rate": (mpf("1e-5"), mpf("1e-8"), mpf(100000)),
    "temperature": (mpf("1e-6"), mpf(0), mpf(100)),
    "pressure": (mpf("1e-2"), mpf(0), mpf(100000)),
    "normalized_composition": (mpf("1e-10"), mpf(0), mpf(1)),
    # K04 §5.1: the lifted equilibrium row `v_i L - K_i l_i V` has kind molar_flow_squared; its
    # tolerance is the component-flow rule applied at the flow scale, i.e. the flow rule times
    # the flow scale: a = 1e-9 * 3, r s = 1e-8 * 9.
    "molar_flow_squared": (mpf("1e-9") * 3, mpf("1e-8"), mpf(9)),
}
#: The registered scales (derivation §9), by row kind.
SCALES = {
    "molar_flow": mpf(3),
    "heat_rate": mpf(100000),
    "temperature": mpf(100),
    "pressure": mpf(100000),
    "molar_flow_squared": mpf(9),
}

VARIANTS = (
    ("SYN-001-nominal", mpf("0.5"), mpf(360)),
    ("SYN-001-once-through", mpf(0), mpf(360)),
    ("SYN-001-high-recycle", mpf("0.95"), mpf(360)),
    ("SYN-001-all-liquid-310K", mpf("0.5"), mpf(310)),
    ("SYN-001-all-vapor-420K", mpf("0.5"), mpf(420)),
)


# ------------------------------------------------------------------ thermodynamics (plan §3.1)


def k_value(i: int, t: Any, p: Any) -> Any:
    expo = L_VAP[i] / R_GAS * (1 / T_BOIL[i] - 1 / t) + V_LIQ[i] * (p - P_REF) / (R_GAS * t)
    return P_REF / p * mp.exp(expo)


def k_vec(t: Any, p: Any) -> Vec:
    return tuple(k_value(i, t, p) for i in range(3))


def h_liquid(i: int, t: Any, p: Any) -> Any:
    return CP * (t - T_REF) + V_LIQ[i] * (p - P_REF)


def h_vapor(i: int, t: Any) -> Any:
    return CP * (t - T_REF) + L_VAP[i]


def enthalpy_flow(liquid: Sequence[Any], vapor: Sequence[Any], t: Any, p: Any) -> Any:
    return sum(liquid[i] * h_liquid(i, t, p) for i in range(3)) + sum(
        vapor[i] * h_vapor(i, t) for i in range(3)
    )


def flash(n: Sequence[Any], t: Any, p: Any) -> tuple[str, Any, Vec, Vec, Vec, Any, Any]:
    """TP flash of component flows n. Returns (regime, beta, vapor, liquid, K, sum zK, sum z/K).

    Regime by the derivation §5.1 order: liquid test, then vapor test, else two-phase.
    """
    k = k_vec(t, p)
    total = sum(n)
    if total == 0:
        raise ValueError("a dormant feed has no flash regime")
    z = [ni / total for ni in n]
    szk = sum(z[i] * k[i] for i in range(3))
    szok = sum(z[i] / k[i] for i in range(3) if z[i] > 0)
    zero: Vec = (mpf(0),) * 3
    if szk <= 1:
        return "LIQUID", mpf(0), zero, tuple(n), k, szk, szok
    if szok <= 1:
        return "VAPOR", mpf(1), tuple(n), zero, k, szk, szok

    def rr(beta: Any) -> Any:
        return sum(z[i] * (k[i] - 1) / (1 + beta * (k[i] - 1)) for i in range(3) if z[i] > 0)

    lo, hi = mpf(0), mpf(1)
    for _ in range(140):
        mid = (lo + hi) / 2
        if rr(mid) > 0:
            lo = mid
        else:
            hi = mid
    beta = (lo + hi) / 2
    for _ in range(6):  # Newton polish to working precision
        d = sum(
            -z[i] * (k[i] - 1) ** 2 / (1 + beta * (k[i] - 1)) ** 2 for i in range(3) if z[i] > 0
        )
        beta -= rr(beta) / d
    liquid = tuple(n[i] * (1 - beta) / (1 + beta * (k[i] - 1)) for i in range(3))
    vapor = tuple(n[i] - liquid[i] for i in range(3))
    return "TWO_PHASE", beta, vapor, liquid, k, szk, szok


def tear_residual(t: Sequence[Any], r: Any, t_flash: Any) -> Vec:
    """R(t) = r l(F + t) - t (K03 §3.2), the closed form of the tear residual."""
    n = tuple(FRESH[i] + t[i] for i in range(3))
    _, _, _, liquid, _, _, _ = flash(n, t_flash, P_REF)
    return tuple(r * liquid[i] - t[i] for i in range(3))


# ------------------------------------------------------------------ formatting


def s(x: Any, digits: int = 20) -> str:
    """20 significant digits; a magnitude below 1e-30 is an exact zero of the closed forms."""
    if abs(x) < mpf(10) ** -30:
        return "0.0"
    return str(mp.nstr(x, digits, strip_zeros=False))


def vec(v: Sequence[Any]) -> list[str]:
    return [s(x) for x in v]


def tolerance(kind: str) -> Any:
    a, r, scale = TOLERANCES[kind]
    return a + r * scale


# ------------------------------------------------------------------ the registered variants


def variant_state(r: Any, t_flash: Any) -> dict[str, Any]:
    """Every certified quantity of one variant, from derivation §5.1, §4.1 and §6."""
    # Derivation §5.1 (recycle invariance): the loop is one flash of the fresh feed; V, x and y do
    # not depend on r, the flash liquid scales as 1/(1 - r), and the purge is the fresh-feed
    # flash's liquid itself.
    regime, beta, vapor, liquid_fresh, k, szk, szok = flash(FRESH, t_flash, P_REF)
    s4 = vapor
    s7 = liquid_fresh
    s5 = tuple(v / (1 - r) for v in liquid_fresh)
    s6 = tuple(r * v for v in s5)
    big_v, big_l = sum(s4), sum(s5)
    s2 = tuple(FRESH[i] + s6[i] for i in range(3))
    n1, n6 = sum(FRESH), sum(s6)
    # §4.1: both inlets liquid at P_r with equal c_p, so the closure is linear in T.
    t_mix = (n1 * T_FEED + n6 * t_flash) / (n1 + n6)
    h1 = enthalpy_flow(FRESH, (mpf(0),) * 3, T_FEED, P_REF)  # exactly 0 at T_r, P_r
    h6 = enthalpy_flow(s6, (mpf(0),) * 3, t_flash, P_REF)
    h2 = h1 + h6
    h_regime, beta_h, s3_vap, s3_liq, _, szk_350, _ = flash(s2, T_HEATER, P_REF)
    h3 = enthalpy_flow(s3_liq, s3_vap, T_HEATER, P_REF)
    h4 = enthalpy_flow((mpf(0),) * 3, s4, t_flash, P_REF)
    h5 = enthalpy_flow(s5, (mpf(0),) * 3, t_flash, P_REF)
    h7 = enthalpy_flow(s7, (mpf(0),) * 3, t_flash, P_REF)
    q_h = h3 - h2
    q_f = h4 + h5 - h3
    closed_total = CP * (t_flash - T_FEED) * sum(FRESH) + sum(s4[i] * L_VAP[i] for i in range(3))
    return {
        "r": r,
        "T_flash_K": t_flash,
        "flash_regime": regime,
        "beta": beta,
        "V": big_v,
        "L": big_l,
        "K": k,
        "sum_zK": szk,
        "sum_z_over_K": szok,
        "S2": s2,
        "S3_vapor": s3_vap,
        "S3_liquid": s3_liq,
        "S3_regime": h_regime,
        "beta_heater": beta_h,
        "S3_sum_zK_350K": szk_350,
        "S4": s4,
        "S5": s5,
        "S6": s6,
        "S7": s7,
        "t_star": s6,
        "T_mix": t_mix,
        "H1": h1,
        "H2": h2,
        "H3": h3,
        "H4": h4,
        "H5": h5,
        "H6": h6,
        "H7": h7,
        "Q_h": q_h,
        "Q_f": q_f,
        "Q_total": q_h + q_f,
        "Q_total_closed_form": closed_total,
        "H_products_minus_fresh": h4 + h7 - h1,
    }


def variant_document(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "r": s(v["r"], 3),
        "T_flash_K": s(v["T_flash_K"], 5),
        "flash_regime": v["flash_regime"],
        "t_star_mol_per_s": vec(v["t_star"]),
        "vapor_product_S4_mol_per_s": vec(v["S4"]),
        "flash_liquid_S5_mol_per_s": vec(v["S5"]),
        "purge_S7_mol_per_s": vec(v["S7"]),
        "V_mol_per_s": s(v["V"]),
        "L_mol_per_s": s(v["L"]),
        "T_mix_K": s(v["T_mix"]),
        "heater_outlet_regime": v["S3_regime"],
        "heater_outlet_beta": s(v["beta_heater"]),
        "heater_outlet_sum_zK_350K": s(v["S3_sum_zK_350K"]),
        "S3_vapor_mol_per_s": vec(v["S3_vapor"]),
        "S3_liquid_mol_per_s": vec(v["S3_liquid"]),
        "Q_heater_W": s(v["Q_h"]),
        "Q_flash_W": s(v["Q_f"]),
        "Q_total_W": s(v["Q_total"]),
        "H_S2_W": s(v["H2"]),
        "H_S3_W": s(v["H3"]),
        "H_S4_W": s(v["H4"]),
        "H_S5_W": s(v["H5"]),
        "H_S7_W": s(v["H7"]),
        "overall_energy_identity_W": s(v["Q_total"] - v["H_products_minus_fresh"]),
    }


# ------------------------------------------------------------------ regularity fixtures


def as_mpf(q: Fraction) -> Any:
    return mpf(q.numerator) / mpf(q.denominator)


def triangular_closed_forms(n: int) -> dict[str, Any]:
    """U = I - N, N strictly upper triangular of ones. Exact: U^-1_ij = 2^(j-i-1) for j > i,
    1 on the diagonal; ||U||_1 = n; ||U^-1||_1 = 2^(n-1); rcond_1 = 1/(n 2^(n-1))."""
    inv = [[Fraction(0)] * n for _ in range(n)]
    for i in range(n):
        inv[i][i] = Fraction(1)
        for j in range(i + 1, n):
            inv[i][j] = Fraction(2) ** (j - i - 1)
    # exact check U * inv = I
    for i in range(n):
        for j in range(n):
            total = inv[i][j] - sum(inv[k][j] for k in range(i + 1, n))
            assert total == (1 if i == j else 0), (n, i, j)

    def u_entry(i: int, j: int) -> Fraction:
        return Fraction(1 if i == j else (-1 if j > i else 0))

    one_norm_u = max(sum(abs(u_entry(i, j)) for i in range(n)) for j in range(n))
    one_norm_inv = max(sum(abs(inv[i][j]) for i in range(n)) for j in range(n))
    assert one_norm_u == n and one_norm_inv == Fraction(2) ** (n - 1)
    rcond = Fraction(1, n) / one_norm_inv
    sqrt_n = mp.sqrt(n)
    # ||A||_2 >= ||A||_1 / sqrt(n)  and  ||A||_2 <= sqrt(n) ||A||_1  for any n x n A, so
    # sigma_min = 1/||U^-1||_2 lies in [1/(sqrt(n) ||U^-1||_1), sqrt(n)/||U^-1||_1].
    sigma_min_upper = sqrt_n / as_mpf(one_norm_inv)
    sigma_min_lower = 1 / (sqrt_n * as_mpf(one_norm_inv))
    sigma_max_lower = mpf(n) / sqrt_n
    sigma_max_upper = mpf(n)  # sqrt(||U||_1 ||U||_inf) = sqrt(n * n)
    eps = mpf(2) ** -52
    return {
        "n": n,
        "rcond_1_exact": as_mpf(rcond),
        "rcond_1_exact_rational": f"1/({n} * 2^{n - 1})",
        "sigma_min_upper_bound": sigma_min_upper,
        "sigma_min_lower_bound": sigma_min_lower,
        "svd_rank_tolerance_lower_bound": n * eps * sigma_max_lower,
        "svd_rank_tolerance_upper_bound": n * eps * sigma_max_upper,
    }


# ------------------------------------------------------------------ build


def build() -> dict[str, Any]:
    checks: list[str] = []
    variants = {cid: variant_state(r, t) for cid, r, t in VARIANTS}
    tiny = mpf(10) ** -35
    small = mpf(10) ** -30

    # Executable claims about the variants.
    for cid, v in variants.items():
        res = tear_residual(v["t_star"], v["r"], v["T_flash_K"])
        assert max(abs(x) for x in res) < tiny, (cid, res)
        checks.append(f"{cid}: R(t*) = 0 to 1e-35")
        assert abs(v["Q_total"] - v["H_products_minus_fresh"]) < small, cid
        assert abs(v["Q_total"] - v["Q_total_closed_form"]) < small, cid
        checks.append(
            f"{cid}: Q_h + Q_f = H(S4) + H(S7) - H(S1) = c_p (T_f - 300) F_tot + V sum y_i L_i "
            "to 1e-30"
        )
        for name in ("S2", "S3_vapor", "S3_liquid", "S4", "S5", "S6", "S7"):
            # K_B(360 K) = 1 makes the vapor of B an exact zero computed as n_B - n_B: noise
            # at 1e-40.
            assert all(x >= -small for x in v[name]), (cid, name, v[name])
        # material closure of every unit and the envelope, exactly in the closed forms
        assert all(abs(FRESH[i] + v["S6"][i] - v["S2"][i]) < tiny for i in range(3))
        assert all(abs(v["S2"][i] - v["S4"][i] - v["S5"][i]) < tiny for i in range(3))
        assert all(abs(FRESH[i] - v["S4"][i] - v["S7"][i]) < tiny for i in range(3))
        checks.append(f"{cid}: mixer, flash and envelope component balances close to 1e-35")
    # recycle invariance across the 360 K variants (derivation §5.1)
    nominal = variants["SYN-001-nominal"]
    for other in ("SYN-001-once-through", "SYN-001-high-recycle"):
        assert all(abs(nominal["S4"][i] - variants[other]["S4"][i]) < tiny for i in range(3))
        assert abs(nominal["Q_total"] - variants[other]["Q_total"]) < small
    checks.append("360 K variants: vapor product and total duty invariant in r to 1e-35 / 1e-30")

    # ---- the registered injections (K04 §9) ----
    once = variants["SYN-001-once-through"]
    flow_tol = tolerance("molar_flow")
    energy_tol = tolerance("heat_rate")
    t_tol = tolerance("temperature")

    # INJ-2, the trivial root: S3 of the once-through variant forced all-liquid, both duties
    # closed.
    s3_all_liquid_h = enthalpy_flow(once["S2"], (mpf(0),) * 3, T_HEATER, P_REF)
    q_h_spurious = s3_all_liquid_h - once["H2"]
    offset = once["Q_h"] - q_h_spurious
    q_f_spurious = once["Q_f"] + offset
    assert q_h_spurious == CP * (T_HEATER - T_FEED) * sum(FRESH), q_h_spurious  # 15000 W
    assert abs(offset - sum(once["S3_vapor"][i] * L_VAP[i] for i in range(3))) < small
    assert abs(q_h_spurious + q_f_spurious - once["Q_total"]) < small
    assert once["S3_sum_zK_350K"] > 1 + mpf("1e-3")
    assert offset > 8000
    checks.append(
        "INJ-2: forcing S3 all-liquid at once-through gives Q_h = c_p (350 - 300) F_tot = "
        "15000 W exactly; the offset V_h sum y_h,i L_i exceeds 8000 W; the duty sum is "
        "invariant; sum x K(350 K) > 1 + 1e-3"
    )

    # INJ-3, the consistent near-state: t* + 1e-6 e_C at the nominal variant, through the tear
    # map.
    near = tuple(nominal["t_star"][i] + (mpf("1e-6") if i == 2 else 0) for i in range(3))
    r_near = tear_residual(near, nominal["r"], nominal["T_flash_K"])
    assert max(abs(x) for x in r_near) > 10 * flow_tol, r_near
    assert len({s(x, 12) for x in r_near}) == 3
    # and the near-state's recycle stream is subcooled at 360 K (the mixer's intensive criterion,
    # K03 §10.1: t* itself is saturated with margin 0; adding the heavy component subcools it)
    k360 = k_vec(mpf(360), P_REF)
    margin = 1 - sum(near[i] / sum(near) * k360[i] for i in range(3))
    assert margin > 0, margin
    checks.append(
        "INJ-3: |R(t* + 1e-6 e_C)| exceeds 10x the flow tolerance; the three rows are "
        "distinct; the mixer admits the state"
    )

    # INJ-6, one coordinate: S6.n.A += delta shifts MIX-mole:A and SPLIT-recycle:A by delta and
    # MIX-energy by delta * h_A^L(360 K, P_r) = delta * c_p * 60 exactly.
    h_a_360 = h_liquid(0, mpf(360), P_REF)
    assert h_a_360 == CP * 60
    assert mpf("1e-6") > 10 * flow_tol and mpf("1e-6") * h_a_360 > 5 * energy_tol
    assert mpf("1e-8") < flow_tol / 3 and mpf("1e-8") * h_a_360 < energy_tol / 10
    checks.append(
        "INJ-6: +1e-6 mol/s on S6.n.A fails two flow rows by > 10x and MIX-energy by > 5x; "
        "+1e-8 passes every row by > 3x"
    )

    # INJ-7, a tampered specification: S3.T += delta shifts HEAT-T by delta and HEAT-duty by
    # -c_p * n_S3,tot * delta (liquid S3 at the nominal variant), FLASH-duty by the opposite.
    n_s3 = sum(nominal["S2"])
    assert nominal["S3_regime"] == "LIQUID"
    duty_shift = CP * n_s3 * mpf("1e-5")
    assert mpf("1e-5") > 9 * t_tol and duty_shift > 4 * energy_tol
    assert mpf("1e-7") < t_tol / 9 and CP * n_s3 * mpf("1e-7") < energy_tol / 20
    checks.append(
        "INJ-7: +1e-5 K on S3.T fails HEAT-T by > 9x and both duty rows by > 4x; +1e-7 K "
        "passes by > 9x"
    )

    # INJ-1, energy bookkeeping: +1 W on U-HEAT.Q; +5e-4 W passes.
    assert mpf(1) > 900 * energy_tol and mpf("5e-4") < energy_tol / 2
    checks.append(
        "INJ-1: +1 W on the heater duty fails HEAT-duty by > 900x; +5e-4 W passes by > 2x"
    )

    # ---- regularity closed forms (K04 §7) ----
    tri = {n: triangular_closed_forms(n) for n in (16, 32, 64)}
    tau_ill = mpf("1e-8")
    assert tri[16]["rcond_1_exact"] > 100 * tau_ill
    assert tri[32]["rcond_1_exact"] < tau_ill / 100
    assert tri[32]["sigma_min_lower_bound"] > 100 * tri[32]["svd_rank_tolerance_upper_bound"]
    assert tri[64]["rcond_1_exact"] < tau_ill / 10**10
    assert tri[64]["sigma_min_upper_bound"] < tri[64]["svd_rank_tolerance_lower_bound"] / 10**4
    checks.append(
        "triangular fixtures: n=16 rcond_1 > 100 tau_ill; n=32 rcond_1 < tau_ill/100 with "
        "sigma_min > 100x the SVD rank tolerance (full rank); n=64 sigma_min < 1e-4 x the SVD "
        "rank tolerance (rank deficient)"
    )
    # ---- the scaled tolerance minimum (K04 §7.4) ----
    scaled = {kind: tolerance(kind) / SCALES[kind] for kind in SCALES}
    tau_hat_min = min(scaled.values())
    assert tau_hat_min == mpf("1e-8") and min(scaled, key=scaled.get) == "temperature"
    checks.append("scaled tolerance minimum over row kinds is 1e-8 (temperature rows)")

    # ---- the absolute-conditioning threshold (K04 §7.4, amended 2026-09-22) ----
    # ||J^-1||_1 <= tau_hat_min / (n eps): residual evaluation noise n eps, amplified through the
    # Jacobian, stays below the tolerance in solution terms. n = 47 for SYN-001, 1 for the seeds.
    eps = mpf(2) ** -52
    abs_threshold_syn001 = tau_hat_min / (47 * eps)
    abs_threshold_seed_1e8 = mpf("1e-8") / eps
    abs_threshold_seed_1e12 = mpf("1e-12") / eps
    assert abs_threshold_syn001 > 2000 * 477  # measured max ||J^-1||_1 = 476.1 (high recycle)
    checks.append(
        "absolute-conditioning threshold for SYN-001 exceeds 2000x the measured maximum "
        "||J^-1||_1 of 476.1"
    )

    # x^2 = 0 under the K03 Newton (scale 1, alpha = 1 accepted: merit ratio 1/16), at the
    # seed tolerance 1e-8 (SQ-1) and at 1e-12 (SQ-2).
    def halvings(tol: Any) -> tuple[int, Any]:
        x, steps = mpf(1), 0
        while x * x > tol:
            x /= 2
            steps += 1
        return steps, x

    steps, x = halvings(mpf("1e-8"))
    assert steps == 14 and x == mpf(2) ** -14
    bound = (x * x) / (2 * x)
    assert bound == mpf(2) ** -15 and bound > 1000 * tau_hat_min
    assert 1 / (2 * x) == mpf(2) ** 13 < abs_threshold_seed_1e8 / 5000
    checks.append(
        "SQ-1: x^2 = 0 from x0 = 1 at tolerance 1e-8: 14 halvings land on 2^-14; F = 2^-28; the "
        "recorded bound 2^-15 exceeds 1000x the scaled tolerance; ||J^-1||_1 = 2^13 sits 5000x "
        "under the absolute threshold, so the verdict is VERIFIED with the bound recorded"
    )
    steps2, x2 = halvings(mpf("1e-12"))
    assert steps2 == 20 and x2 == mpf(2) ** -20
    assert 1 / (2 * x2) == mpf(2) ** 19 > 100 * abs_threshold_seed_1e12
    checks.append(
        "SQ-2: x^2 = 0 from x0 = 1 at tolerance 1e-12: 20 halvings land on 2^-20; "
        "||J^-1||_1 = 2^19 exceeds 100x the absolute threshold 1e-12/eps, so the status is "
        "ILL_CONDITIONED(absolute) and the verdict UNVERIFIED"
    )

    # ---- cross-check with the P01 reference, if present (never copied from) ----
    p01 = Path("benchmarks/syn001/reference_values.yaml")
    if p01.exists():
        loaded = yaml.safe_load(p01.read_text(encoding="utf-8"))["variants"]
        p01_variants = {e["case_id"]: e for e in loaded}
        worst = mpf(0)
        for cid, v in variants.items():
            e = p01_variants[cid]
            pairs = [
                (v["Q_h"], e["Q_heater_W"]),
                (v["Q_f"], e["Q_flash_W"]),
                (v["T_mix"], e["T_mix_K"]),
                (v["V"], e["V_mol_per_s"]),
                (v["L"], e["L_mol_per_s"]),
            ]
            pairs += [(v["S4"][i], e["vapor_product_mol_per_s"][i]) for i in range(3)]
            pairs += [(v["S6"][i], e["recycle_mol_per_s"][i]) for i in range(3)]
            for mine, theirs in pairs:
                ref = mpf(theirs)
                worst = max(worst, abs(mine - ref) / max(abs(ref), mpf(1)))
        assert worst < mpf("5e-19"), worst
        checks.append(
            f"every certified quantity agrees with the P01 20-digit reference to "
            f"{mp.nstr(worst, 3)} relative (independent derivation)"
        )

    floors_note = (
        "measured by Fable on the K02 flowsheet through the CasADi backend and SciPy SuperLU at "
        "the five reconstructed x(t*); regression floors, not closed forms"
    )
    doc: dict[str, Any] = {
        "generated_by": (
            "Fable 5.1, mpmath 1.3.0 at 40 significant digits, from plan §3.1 definitions and "
            "derivation §2, §4.1, §5.1, §6 only; exact rational arithmetic for the triangular "
            "fixtures"
        ),
        "specification": "docs/derivations/K04-certificate-spec.md",
        "independence": (
            "closed-form expectations; no verifier, solver, oracle or process_runtime code was "
            "used. The P01 reference is read in --check to prove two derivations agree and is "
            "never copied."
        ),
        "check_tolerances": {
            kind: {
                "absolute": s(a, 5),
                "relative": s(r, 5),
                "scale": s(scale, 6),
                "total": s(a + r * scale, 6),
                "scaled_total": s((a + r * scale) / SCALES.get(kind, mpf(1)), 6),
            }
            for kind, (a, r, scale) in TOLERANCES.items()
        },
        "scaled_tolerance_minimum": s(tau_hat_min, 3),
        "regularity_policy": {
            "matrix": (
                "the 47x47 scaled target Jacobian after the two alias eliminations, evaluated "
                "at the final state (K04 §7.1)"
            ),
            "recipe": (
                "splu (ADR 0004 options) -> LinearOperator -> onenormest -> "
                "rcond_1 = 1/(||J||_1 ||J^-1||_1) (plan §6.3)"
            ),
            "tau_ill_conditioned": "1e-8",
            "svd_rank_tolerance": "n * eps * sigma_max, eps = 2^-52",
            "svd_dimension_cap": 2000,
            "absolute_conditioning_threshold": {
                "rule": (
                    "||J^-1||_1 <= tau_hat_min / (n eps); violation is ILL_CONDITIONED(absolute)"
                ),
                "syn001_n47": s(abs_threshold_syn001, 6),
                "seed_n1_tol_1e-8": s(abs_threshold_seed_1e8, 6),
                "seed_n1_tol_1e-12": s(abs_threshold_seed_1e12, 6),
            },
            "solution_error_bound": (
                "recorded evidence with a statement, never a pass/fail check (K04 §7.4, amended "
                "2026-09-22)"
            ),
        },
        "variants": {cid: variant_document(v) for cid, v in variants.items()},
        "injections": {
            "INJ-1-energy-bookkeeping": {
                "state": "nominal x(t*) with U-HEAT.Q + delta",
                "fails_at_W": "1",
                "passes_at_W": "5e-4",
                "row_shift": (
                    "HEAT-duty by exactly delta; independent heater and overall energy checks "
                    "by delta"
                ),
                "energy_tolerance_W": s(energy_tol, 6),
            },
            "INJ-2-trivial-root": {
                "state": (
                    "once-through x(t*) with S3's lifted split forced all-liquid and both "
                    "duties closed"
                ),
                "S3_liquid_forced_mol_per_s": vec(once["S2"]),
                "Q_heater_spurious_W": s(q_h_spurious),
                "Q_heater_true_W": s(once["Q_h"]),
                "Q_flash_spurious_W": s(q_f_spurious),
                "Q_flash_true_W": s(once["Q_f"]),
                "offset_W": s(offset),
                "duty_sum_W": s(once["Q_total"]),
                "S3_sum_xK_350K": s(once["S3_sum_zK_350K"]),
                "S3_true_beta": s(once["beta_heater"]),
                "S3_true_V_mol_per_s": s(sum(once["S3_vapor"])),
                "S3_true_vapor_mol_per_s": vec(once["S3_vapor"]),
                "passes": (
                    "residual (all 49 rows), material balances, alias certificates, overall "
                    "energy identity, regularity"
                ),
                "fails": (
                    "phase admissibility (S3, all_liquid); independent split (S3); heater and "
                    "flash unit energy"
                ),
            },
            "INJ-3-consistent-near-state": {
                "state": "nominal, t* + 1e-6 e_C reconstructed through the tear map",
                "t_mol_per_s": vec(near),
                "R_mol_per_s": vec(r_near),
                "R_inf_mol_per_s": s(max(abs(x) for x in r_near)),
                "flow_tolerance_mol_per_s": s(flow_tol, 6),
                "mixer_margin": s(margin),
                "fails": "residual (the three SPLIT-recycle rows); material (splitter ratio rows)",
                "passes": "every other check",
            },
            "INJ-6-one-coordinate": {
                "state": "nominal x(t*) with S6.n.A + delta, rows evaluated at x directly",
                "fails_at_mol_per_s": "1e-6",
                "passes_at_mol_per_s": "1e-8",
                "MIX_energy_shift_per_mol_per_s_W": s(h_a_360, 6),
                "rows_shifted_by_delta": ["U-MIX:MIX-mole:A", "U-SPLIT:SPLIT-recycle:A"],
                "row_shifted_by_delta_h": "U-MIX:MIX-energy",
            },
            "INJ-7-tampered-specification": {
                "state": "nominal x(t*) with S3.T + delta",
                "fails_at_K": "1e-5",
                "passes_at_K": "1e-7",
                "HEAT_duty_shift_per_K_W": s(-CP * n_s3, 12),
                "FLASH_duty_shift_per_K_W": s(CP * n_s3, 12),
                "temperature_tolerance_K": s(t_tol, 3),
            },
        },
        "regularity_fixtures": {
            "triangular_unit_diagonal": {
                str(n): {
                    "definition": (
                        "U = I - N, N strictly upper triangular of ones; every U_ii = 1"
                    ),
                    "rcond_1_exact": s(t["rcond_1_exact"]),
                    "rcond_1_exact_rational": t["rcond_1_exact_rational"],
                    "sigma_min_upper_bound": s(t["sigma_min_upper_bound"], 6),
                    "sigma_min_lower_bound": s(t["sigma_min_lower_bound"], 6),
                    "svd_rank_tolerance_bounds": [
                        s(t["svd_rank_tolerance_lower_bound"], 6),
                        s(t["svd_rank_tolerance_upper_bound"], 6),
                    ],
                    "expected_status": {
                        16: "NO_RANK_LOSS_DETECTED",
                        32: "ILL_CONDITIONED",
                        64: "RANK_DEFICIENT",
                    }[n],
                    "expected_svd_rank": {16: 16, 32: 32, 64: 63}[n],
                    "u_diagonal_ratio": "1",
                }
                for n, t in tri.items()
            },
            "x_squared": {
                "exact_root": {
                    "x": "0",
                    "F": "0",
                    "J": "0",
                    "expected_status": "RANK_DEFICIENT",
                    "svd_rank": 0,
                },
                "k03_newton_from_1": {
                    "steps": 14,
                    "x_final": s(mpf(2) ** -14),
                    "F_final": s(mpf(2) ** -28),
                    "J_final": s(mpf(2) ** -13),
                    "rcond_1": "1",
                    "inverse_one_norm": s(mpf(2) ** 13),
                    "absolute_threshold": s(abs_threshold_seed_1e8, 6),
                    "solution_error_bound_scaled": s(mpf(2) ** -15),
                    "expected_status": "NO_RANK_LOSS_DETECTED",
                    "expected_verdict": "VERIFIED, with the bound recorded and its statement",
                },
                "k03_newton_from_1_tol_1e-12": {
                    "steps": 20,
                    "x_final": s(mpf(2) ** -20),
                    "F_final": s(mpf(2) ** -40),
                    "J_final": s(mpf(2) ** -19),
                    "rcond_1": "1",
                    "inverse_one_norm": s(mpf(2) ** 19),
                    "absolute_threshold": s(abs_threshold_seed_1e12, 6),
                    "solution_error_bound_scaled": s(mpf(2) ** -21),
                    "expected_status": "ILL_CONDITIONED(absolute)",
                    "expected_verdict": "UNVERIFIED",
                },
            },
        },
        "numerical_policy": {
            "id": "K04-numerical-policy-v1",
            "relative": "1e-9",
            "near_threshold_margin": "10",
            "floors": {
                "residual_inf_unscaled": {
                    "floor": s(flow_tol, 6),
                    "why": "ADR 0001 D6 flow rule (the K03 tear rows)",
                },
                "merit": {
                    "floor": s((flow_tol / 3) ** 2 / 2, 6),
                    "why": "half the squared scaled flow tolerance",
                },
                # Added 2026-09-22, on the Fable review of K05's M4: the comparator carried a
                # floor for this and the registry did not, which is the drift that review
                # found. K04 §4.8's registered witness tolerance; the quantity is a maximum
                # over 47 columns of central differences and moves more than a single residual
                # does (measured 2.80e-11 against 2.93e-11 across architectures).
                "witness_max_diff": {
                    "floor": "1e-7",
                    "why": "K04 §4.8 derivative-witness tolerance",
                },
                "step_inf_scaled": {
                    "floor": s(flow_tol / 3, 6),
                    "why": "the scaled flow tolerance",
                },
                "residual_normalized": {"floor": "1e-12", "why": "ADR 0004 D3.2"},
                "eta": {"floor": "1e-10", "why": "K03 §3.4"},
                "constant_mismatch": {"floor": "1e-2", "why": "ADR 0001 D6 pressure"},
                "u_diag_min_abs": {
                    "floor": "1e-10 x u_diag_max_abs",
                    "why": "ADR 0004 D3.4 screen ratio",
                },
                "u_diag_max_abs": {"floor": "0", "why": "compared relatively"},
                "rcond_1": {
                    "floor": "1e-14",
                    "why": "n eps at n = 47; below it the estimate is noise",
                },
                "solution_error_bound_scaled": {
                    "floor": s(tau_hat_min, 3),
                    "why": "the scaled tolerance minimum (recorded evidence, not a check)",
                },
                "inverse_one_norm_estimate": {
                    "floor": "0",
                    "why": "compared relatively; its threshold is a policy-derived constant",
                },
                "check.value": {"floor": "the check's own tolerance", "why": "ADR 0007 D2.2"},
                # Added 2026-09-24 by T02 (ADR 0009 D3, ordinary addition under ADR 0007 D2.3),
                # amended the same day by the T02 review (M4): no absolute floor — the two are
                # compared relatively, and only inside `comparability_windows` below.
                "kappa_2": {
                    "floor": "0",
                    "why": "ADR 0009 D3 as amended: relative only, inside its comparability window",
                },
                "gamma_inf": {
                    "floor": "0",
                    "why": "ADR 0009 D3 as amended: relative only, inside its comparability window",
                },
            },
            # ADR 0007 D2.2's "a comparability window is a scope, not a floor" (T02 review M4):
            # a least-squares quantity of residual differences agrees across platforms as
            # eps / |f_k|, so it is compared only where the committed event's scaled residual is
            # at least `minimum`, and shape-checked below it. The selector itself is a scope and
            # is shape-checked, never value-compared.
            "comparability_windows": {
                name: {
                    "sibling": "residual_inf_scaled",
                    "minimum": "1e-4",
                    "why": (
                        "measured on the CI pair: <= 3.3e-13 relative where |f_k| >= 1e-4, up "
                        "to 1.06e-8 below"
                    ),
                }
                for name in ("kappa_2", "gamma_inf")
            },
            # `beta_substitution` (T02 §5.8, ADR 0009 D3: R0) is one of two registered constants;
            # `delta_scaled_inf` (T03 §8.2, ADR 0005 D7) is the root fingerprint's δ_root, 1e-4.
            "exact_fields": [
                "alpha",
                "scales",
                "bounds",
                "tolerance",
                "beta_substitution",
                "delta_scaled_inf",
            ],
            "unreproducible_counts": [
                "property_calls",
                "requested_evaluations",
                "cache_hits",
                "nnz_L",
                "nnz_U",
            ],
            "digests_never_compared": [
                "state_sha256",
                "full_state_sha256",
                "jacobian_identity",
                "target_state_sha256",
            ],
        },
        "floors_measured_2026_09_22": {
            "note": floors_note,
            "residual_rows_unscaled_max": {
                "molar_flow": "3.6e-15",
                "temperature": "0.0",
                "pressure_or_heat_rate": "1.5e-10",
                "molar_flow_squared": "1.8e-14",
            },
            "material_balance_max_mol_per_s": "3.6e-15",
            "energy_balance_independent_flash_max_W": "9.4e-10",
            "specification_rows_max": "0.0",
            "alias_identity_max_Pa": "1.5e-10",
            "rcond_1_target_47x47_scaled": {
                "nominal": "1.161e-3",
                "once_through": "1.851e-3",
                "high_recycle": "1.331e-4",
                "all_liquid_310K": "2.019e-3",
                "all_vapor_420K": "7.705e-4",
                "trivial_root_spurious": "2.194e-3",
            },
            "rcond_1_target_47x47_unscaled_range": "9.0e-12 to 5.9e-11",
            "onenormest_over_exact_one_norm": "1.000 at every state and fixture",
            "u_diagonal_ratio_range": "4.4e-3 to 2.6e-1",
            "solution_error_bound_scaled_max": "6.9e-13 (high recycle)",
            "fd_compiled_function_scaled_max_abs": {
                "delta=1e-4": "2.7e-8",
                "delta=1e-5": "2.8e-10",
                "delta=1e-6": "2.8e-9",
                "delta=1e-7": "1.2e-8",
                "off_pattern": "0.0",
            },
            "smallest_nonzero_scaled_jacobian_entry": "1.6e-4",
            "provider_vs_oracle_enthalpy_J_per_mol": "0.0",
            "provider_vs_oracle_K_relative": "6.3e-16",
        },
        "checks_passed": checks,
    }
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="re-derive every identity and print the key numbers"
    )
    parser.add_argument("--emit", metavar="PATH", help="write the reference YAML")
    args = parser.parse_args(argv)
    if not (args.check or args.emit):
        parser.error("choose --check and/or --emit PATH")
    ref = build()
    if args.check:
        for line in ref["checks_passed"]:
            print("check passed:", line)
        inj = ref["injections"]["INJ-2-trivial-root"]
        print("INJ-2 Q_heater spurious/true:", inj["Q_heater_spurious_W"], inj["Q_heater_true_W"])
        print("INJ-3 R:", ref["injections"]["INJ-3-consistent-near-state"]["R_mol_per_s"])
        tri = ref["regularity_fixtures"]["triangular_unit_diagonal"]
        print("triangular rcond_1:", {n: t["rcond_1_exact"] for n, t in tri.items()})
    if args.emit:
        with open(args.emit, "w", encoding="utf-8") as handle:
            yaml.safe_dump(ref, handle, sort_keys=False, width=110, allow_unicode=True)
        print("wrote", args.emit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
